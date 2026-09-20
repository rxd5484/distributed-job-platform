# TaskForge — Distributed Job Processing Platform
https://youtu.be/Teggh4Mi_Iw - video link

TaskForge is a backend-focused software engineering project that demonstrates asynchronous job processing with priorities, retries, timeouts, worker recovery, idempotency, and a dead-letter queue.

## Architecture

```text
Next.js UI
    |
    v
FastAPI API
    |
    +------> PostgreSQL (durable job metadata)
    |
    v
Redis priority queue
    |
    +------> Worker 1
    +------> Worker 2
    +------> Worker N
               |
               +--> retries / delayed queue
               +--> dead-letter queue
```

## Features

- FastAPI REST API
- Redis-backed priority queue
- PostgreSQL job persistence
- Multiple workers
- Retry logic with exponential backoff
- Dead-letter queue
- Idempotency keys
- Per-job timeouts
- Worker lease recovery
- Queue statistics
- Docker Compose
- Next.js dashboard
- Pytest tests
- GitHub Actions CI

## Run locally

Requirements:

- Docker Desktop
- Docker Compose

Start everything:

```bash
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Stats: http://localhost:8000/stats

## Demo jobs

### Normal job

```json
{
  "job_type": "generate_report",
  "payload": {"records": 5000},
  "priority": 8,
  "timeout_seconds": 10,
  "max_retries": 3
}
```

### Retry demo

```json
{
  "job_type": "fail_first_n",
  "payload": {"fail_first_n": 2},
  "priority": 6,
  "timeout_seconds": 10,
  "max_retries": 3
}
```

### Timeout / DLQ demo

```json
{
  "job_type": "slow_task",
  "payload": {"seconds": 10},
  "priority": 5,
  "timeout_seconds": 2,
  "max_retries": 1
}
```

## API

Create job:

```http
POST /jobs
```

Read job:

```http
GET /jobs/{job_id}
```

List jobs:

```http
GET /jobs
```

Stats:

```http
GET /stats
```

DLQ:

```http
GET /dlq
```

Requeue dead-letter job:

```http
POST /dlq/{job_id}/requeue
```

Cancel queued job:

```http
POST /jobs/{job_id}/cancel
```

## Statuses

```text
QUEUED
PROCESSING
RETRYING
COMPLETED
FAILED
DEAD_LETTER
CANCELLED
FAILED_TO_QUEUE
```



## License

MIT
