"""Alert and escalation data models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from .base import DatasetId


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(BaseModel):
    """A quality alert with deduplication tracking."""

    alert_id: UUID
    dataset_id: DatasetId
    anomaly_type: str = Field(..., min_length=1)
    metric_name: str = Field(..., min_length=1)
    severity: AlertSeverity
    created_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    occurrence_count: int = Field(default=1, ge=1)
    suppressed: bool = False
    correlated_alert_ids: list[UUID] = Field(default_factory=list)


class AlertGroup(BaseModel):
    """A group of correlated alerts sharing a common root cause."""

    group_id: UUID
    root_cause_alert_id: UUID
    correlated_alerts: list[UUID] = Field(default_factory=list)
    created_at: datetime


class EscalationLevel(BaseModel):
    """A single level in an escalation chain."""

    level: int = Field(..., ge=1)
    notification_channels: list[str] = Field(..., min_length=1)
    timeout_seconds: int = Field(default=300, ge=1)


class EscalationPolicy(BaseModel):
    """Escalation policy configuration for an organization."""

    organization_id: str = Field(..., min_length=1)
    levels: list[EscalationLevel] = Field(..., min_length=1, max_length=5)
    default_timeout_seconds: int = Field(default=300, ge=1)


class EscalationChain(BaseModel):
    """Active escalation chain for an alert."""

    chain_id: UUID
    alert_id: UUID
    policy: EscalationPolicy
    current_level: int = Field(..., ge=1)
    started_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
