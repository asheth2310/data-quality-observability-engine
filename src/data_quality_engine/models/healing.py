"""Self-healing orchestrator data models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from .base import DatasetId


class HealingStrategy(str, Enum):
    """Available automated healing strategies."""

    AUTO_RETRY = "auto_retry"
    QUARANTINE = "quarantine"
    BACKFILL = "backfill"
    ESCALATE = "escalate"
    IGNORE = "ignore"


class JobStatus(str, Enum):
    """Status of an async job (e.g., backfill)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Diagnosis(BaseModel):
    """Result of automated issue diagnosis."""

    alert_id: UUID
    root_cause: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    suggested_strategy: HealingStrategy
    context: dict[str, Any] = Field(default_factory=dict)
    upstream_failures: list[str] = Field(default_factory=list)


class HealingResult(BaseModel):
    """Result of executing a healing strategy."""

    healing_id: UUID
    strategy: HealingStrategy
    started_at: datetime
    completed_at: datetime | None = None
    success: bool
    records_affected: int = Field(..., ge=0)
    details: str
    retry_count: int = Field(default=0, ge=0)


class QuarantineReceipt(BaseModel):
    """Receipt documenting quarantined data with full audit trail."""

    quarantine_id: UUID
    dataset_id: DatasetId
    record_count: int = Field(..., ge=0)
    reason: str = Field(..., min_length=1, max_length=1000)
    quarantined_at: datetime
    expiry: datetime | None = None
    reprocessable: bool


class BackfillJob(BaseModel):
    """A backfill job targeting a specific time range."""

    job_id: UUID
    dataset_id: DatasetId
    time_range_start: datetime
    time_range_end: datetime
    triggered_by: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    status: JobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    records_processed: int = Field(default=0, ge=0)
    records_failed: int = Field(default=0, ge=0)


class RetryConfig(BaseModel):
    """Configuration for retry with exponential backoff."""

    base_delay_seconds: float = Field(default=1.0, ge=1.0, le=60.0)
    multiplier: float = Field(default=2.0, ge=1.1, le=10.0)
    max_delay_seconds: float = Field(default=300.0, gt=0.0)
    max_retries: int = Field(default=5, ge=1, le=20)
