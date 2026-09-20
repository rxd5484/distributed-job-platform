# Architecture

## Components

### Next.js frontend
Dashboard for submitting jobs and watching state changes.

### FastAPI API
Creates jobs, validates inputs, stores metadata, enqueues work, exposes stats, and requeues dead-letter jobs.

### PostgreSQL
Source of truth for job metadata, attempts, errors, and results.

### Redis
Operational queue structures:

```text
taskforge:ready
taskforge:delayed
taskforge:processing
taskforge:dlq
```

### Workers
Workers independently poll Redis, claim jobs, execute tasks, retry failures, and recover expired leases.

## Reliability

- Idempotency keys prevent duplicate job creation.
- Exponential retry backoff reduces hot-loop failures.
- Processing leases allow jobs to be recovered after worker crashes.
- Timeouts kill tasks that run too long.
- Exhausted jobs move to the DLQ.
