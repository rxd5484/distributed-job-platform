import multiprocessing as mp
import os, socket, time
from datetime import datetime, timezone
from queue import Empty
from redis import Redis

from .database import SessionLocal, init_db
from .models import Job
from .queue import JobQueue
from .settings import settings
from .tasks import run_task

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"

def utcnow():
    return datetime.now(timezone.utc)

def task_entry(q, job_type, payload, attempt):
    try:
        q.put(("ok", run_task(job_type, payload, attempt)))
    except Exception as exc:
        q.put(("error", f"{type(exc).__name__}: {exc}"))

def execute_with_timeout(job):
    q = mp.Queue()
    p = mp.Process(target=task_entry, args=(q, job.job_type, job.payload, job.attempts))
    p.start()
    p.join(job.timeout_seconds)

    if p.is_alive():
        p.terminate()
        p.join(2)
        raise TimeoutError(f"Job exceeded timeout of {job.timeout_seconds}s")

    try:
        kind, value = q.get_nowait()
    except Empty as exc:
        raise RuntimeError("Task exited without result") from exc

    if kind == "error":
        raise RuntimeError(value)
    return value

def get_priority(job_id):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        return job.priority if job else 5

def recover(queue):
    for job_id in queue.expired_leases():
        if not queue.claim_expired_lease(job_id):
            continue
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if not job or job.status in {"COMPLETED", "DEAD_LETTER", "CANCELLED"}:
                continue
            job.status = "QUEUED"
            job.error = "Recovered after worker lease expired."
            job.updated_at = utcnow()
            session.commit()
            queue.enqueue(job.id, job.priority)

def process_one(queue, job_id):
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if not job or job.status == "CANCELLED":
            return

        job.attempts += 1
        job.status = "PROCESSING"
        job.started_at = utcnow()
        job.error = None
        session.commit()

        queue.mark_processing(job.id, max(settings.default_lease_seconds, job.timeout_seconds + 15))

        try:
            result = execute_with_timeout(job)
            job.result = result
            job.status = "COMPLETED"
            job.finished_at = utcnow()
            job.error = None
            session.commit()
            queue.acknowledge(job.id)
        except Exception as exc:
            queue.acknowledge(job.id)
            job.error = str(exc)[:1000]
            if job.attempts <= job.max_retries:
                delay = min(2 ** job.attempts, 30)
                job.status = "RETRYING"
                session.commit()
                queue.schedule_retry(job.id, delay)
            else:
                job.status = "DEAD_LETTER"
                job.finished_at = utcnow()
                session.commit()
                queue.dead_letter(job.id)

def main():
    init_db()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    queue = JobQueue(redis)

    while True:
        queue.heartbeat(WORKER_ID)
        queue.promote_due_retries(get_priority)
        recover(queue)

        job_id = queue.dequeue()
        if not job_id:
            time.sleep(settings.worker_poll_seconds)
            continue

        process_one(queue, job_id)

if __name__ == "__main__":
    main()
