"""Freshness SLA monitoring data models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from .base import DatasetId


class FreshnessState(str, Enum):
    """Current freshness status of a dataset."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MaintenanceWindow(BaseModel):
    """A configured maintenance window during which freshness checks are suppressed."""

    start_time: datetime
    end_time: datetime
    recurrence: str | None = None

    @model_validator(mode="after")
    def validate_window_ordering(self) -> "MaintenanceWindow":
        """start_time must be before end_time."""
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class FreshnessSLA(BaseModel):
    """Freshness SLA configuration for a dataset."""

    dataset_id: DatasetId
    max_staleness_seconds: int = Field(..., ge=1, le=2592000)
    expected_schedule: str = Field(..., min_length=1)
    warning_threshold: float = Field(default=0.8, gt=0.0, lt=1.0)
    critical_threshold: float = Field(default=0.9, gt=0.0, le=1.0)
    calendar_aware: bool = True
    maintenance_windows: list[MaintenanceWindow] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_threshold_ordering(self) -> "FreshnessSLA":
        """warning_threshold must be less than critical_threshold."""
        if self.warning_threshold >= self.critical_threshold:
            raise ValueError(
                f"warning_threshold ({self.warning_threshold}) must be < "
                f"critical_threshold ({self.critical_threshold})"
            )
        return self


class FreshnessStatus(BaseModel):
    """Current freshness status for a dataset."""

    model_config = {"frozen": True}

    dataset_id: DatasetId
    last_updated: datetime | None = None
    staleness_seconds: float = Field(..., ge=0.0)
    sla_consumed_pct: float = Field(..., ge=0.0, le=2.0)
    status: FreshnessState
    predicted_next_arrival: datetime | None = None
    check_time: datetime


class ArrivalPrediction(BaseModel):
    """Prediction of next data arrival for a dataset."""

    model_config = {"frozen": True}

    dataset_id: DatasetId
    predicted_arrival: datetime | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    prediction_status: str = Field(default="ok")
