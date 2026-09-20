import time
from redis import Redis

READY_KEY = "taskforge:ready"
DELAYED_KEY = "taskforge:delayed"
PROCESSING_KEY = "taskforge:processing"
DLQ_KEY = "taskforge:dlq"
HEARTBEAT_PREFIX = "taskforge:worker:heartbeat:"

def priority_score(priority: int, created_ms: int | None = None) -> float:
    if created_ms is None:
        created_ms = int(time.time() * 1000)
    return float((10 - priority) * 10_000_000_000_000 + created_ms)

class JobQueue:
    def __init__(self, redis: Redis):
        self.redis = redis

    def enqueue(self, job_id: str, priority: int) -> None:
        self.redis.zadd(READY_KEY, {job_id: priority_score(priority)})

    def dequeue(self) -> str | None:
        item = self.redis.zpopmin(READY_KEY, 1)
        return str(item[0][0]) if item else None

    def mark_processing(self, job_id: str, lease_seconds: int) -> None:
        self.redis.zadd(PROCESSING_KEY, {job_id: time.time() + lease_seconds})

    def acknowledge(self, job_id: str) -> None:
        self.redis.zrem(PROCESSING_KEY, job_id)

    def schedule_retry(self, job_id: str, delay_seconds: int) -> None:
        self.redis.zadd(DELAYED_KEY, {job_id: time.time() + delay_seconds})

    def promote_due_retries(self, priority_lookup):
        for job_id in self.redis.zrangebyscore(DELAYED_KEY, 0, time.time()):
            if self.redis.zrem(DELAYED_KEY, job_id):
                self.enqueue(str(job_id), int(priority_lookup(str(job_id))))

    def expired_leases(self):
        return [str(x) for x in self.redis.zrangebyscore(PROCESSING_KEY, 0, time.time())]

    def claim_expired_lease(self, job_id: str) -> bool:
        return bool(self.redis.zrem(PROCESSING_KEY, job_id))

    def dead_letter(self, job_id: str) -> None:
        self.redis.lpush(DLQ_KEY, job_id)

    def remove_from_ready(self, job_id: str) -> None:
        self.redis.zrem(READY_KEY, job_id)

    def remove_from_delayed(self, job_id: str) -> None:
        self.redis.zrem(DELAYED_KEY, job_id)

    def heartbeat(self, worker_id: str) -> None:
        self.redis.setex(f"{HEARTBEAT_PREFIX}{worker_id}", 10, "1")

    def stats(self):
        return {
            "ready": int(self.redis.zcard(READY_KEY)),
            "delayed": int(self.redis.zcard(DELAYED_KEY)),
            "processing": int(self.redis.zcard(PROCESSING_KEY)),
            "dead_letter": int(self.redis.llen(DLQ_KEY)),
            "active_workers": len(list(self.redis.scan_iter(f"{HEARTBEAT_PREFIX}*"))),
        }
