import hashlib
import time

SUPPORTED_TASKS = {
    "generate_report",
    "process_csv",
    "send_notification",
    "fail_first_n",
    "slow_task",
    "fibonacci",
}

def run_task(job_type, payload, attempt):
    if job_type == "generate_report":
        records = max(1, int(payload.get("records", 1000)))
        time.sleep(min(records / 5000, 2))
        checksum = hashlib.sha256(f"{records}:{attempt}".encode()).hexdigest()[:12]
        return {"records_processed": records, "report_id": f"report-{checksum}"}

    if job_type == "process_csv":
        rows = max(1, int(payload.get("rows", 2500)))
        invalid_ratio = float(payload.get("invalid_ratio", 0.02))
        invalid = int(rows * invalid_ratio)
        time.sleep(min(rows / 7000, 2))
        return {"rows": rows, "valid_rows": rows - invalid, "invalid_rows": invalid}

    if job_type == "send_notification":
        time.sleep(0.3)
        return {
            "channel": payload.get("channel", "email"),
            "recipient": payload.get("recipient", "demo@example.com"),
            "delivered": True,
        }

    if job_type == "fail_first_n":
        fail_first_n = int(payload.get("fail_first_n", 2))
        if attempt <= fail_first_n:
            raise RuntimeError(f"Intentional failure on attempt {attempt}")
        return {"message": "Recovered after retries.", "successful_attempt": attempt}

    if job_type == "slow_task":
        seconds = float(payload.get("seconds", 5))
        time.sleep(seconds)
        return {"slept_seconds": seconds}

    if job_type == "fibonacci":
        n = max(0, min(int(payload.get("n", 30)), 40))
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return {"n": n, "value": a}

    raise ValueError(f"Unsupported job type: {job_type}")
