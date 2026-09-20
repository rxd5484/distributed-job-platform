from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class JobCreate(BaseModel):
    job_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)
    timeout_seconds: int = Field(default=10, ge=1, le=120)
    max_retries: int = Field(default=3, ge=0, le=10)

class JobRead(BaseModel):
    id: str
    job_type: str
    payload: dict[str, Any]
    status: str
    priority: int
    timeout_seconds: int
    max_retries: int
    attempts: int
    result: dict[str, Any] | None
    error: str | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
