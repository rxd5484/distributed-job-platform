from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .database import SessionLocal, init_db
from .models import Job
from .queue import JobQueue
from .schemas import JobCreate, JobRead
from .settings import settings
from .tasks import SUPPORTED_TASKS

def utcnow():
    return datetime.now(timezone.utc)

redis = Redis.from_url(settings.redis_url, decode_responses=True)
queue = JobQueue(redis)

@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield

app = FastAPI(title="TaskForge API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    try:
        redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}

@app.post("/jobs", response_model=JobRead, status_code=201)
def create_job(body: JobCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if body.job_type not in SUPPORTED_TASKS:
        raise HTTPException(status_code=400, detail=f"Unsupported job type: {body.job_type}")

    with SessionLocal() as session:
        if idempotency_key:
            existing = session.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing:
                return existing

        job = Job(
            job_type=body.job_type,
            payload=body.payload,
            priority=body.priority,
            timeout_seconds=body.timeout_seconds,
            max_retries=body.max_retries,
            idempotency_key=idempotency_key,
        )
        session.add(job)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing:
                return existing
            raise

        session.refresh(job)
        try:
            queue.enqueue(job.id, job.priority)
        except Exception as exc:
            job.status = "FAILED_TO_QUEUE"
            job.error = str(exc)[:1000]
            session.commit()
            raise HTTPException(status_code=503, detail="Persisted but could not queue.") from exc

        return job

@app.get("/jobs", response_model=list[JobRead])
def list_jobs(status: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    with SessionLocal() as session:
        stmt = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if status:
            stmt = select(Job).where(Job.status == status).order_by(Job.created_at.desc()).limit(limit)
        return list(session.scalars(stmt))

@app.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

@app.post("/jobs/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: str):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status not in {"QUEUED", "RETRYING", "FAILED_TO_QUEUE"}:
            raise HTTPException(status_code=409, detail=f"Cannot cancel {job.status}")
        queue.remove_from_ready(job.id)
        queue.remove_from_delayed(job.id)
        job.status = "CANCELLED"
        job.finished_at = utcnow()
        session.commit()
        return job

@app.get("/stats")
def stats():
    with SessionLocal() as session:
        rows = session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
        by_status = {status: count for status, count in rows}
    return {**queue.stats(), "by_status": by_status}

@app.get("/dlq", response_model=list[JobRead])
def dlq(limit: int = Query(default=50, ge=1, le=200)):
    with SessionLocal() as session:
        return list(session.scalars(
            select(Job).where(Job.status == "DEAD_LETTER").order_by(Job.finished_at.desc()).limit(limit)
        ))

@app.post("/dlq/{job_id}/requeue", response_model=JobRead)
def requeue(job_id: str):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status != "DEAD_LETTER":
            raise HTTPException(status_code=409, detail="Job is not in DLQ")
        job.status = "QUEUED"
        job.attempts = 0
        job.error = None
        job.finished_at = None
        session.commit()
        queue.enqueue(job.id, job.priority)
        return job
