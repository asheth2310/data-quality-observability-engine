"""Anomaly detection data models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from .base import DatasetId
from .drift import DriftSeverity


class AnomalyCategory(str, Enum):
    """Categories of data anomalies."""

    DISTRIBUTION_SHIFT = "distribution_shift"
    VOLUME_ANOMALY = "volume_anomaly"
    NULL_RATE_SPIKE = "null_rate_spike"
    CARDINALITY_CHANGE = "cardinality_change"
    CORRELATION_BREAK = "correlation_break"
    OUTLIER_BURST = "outlier_burst"
    PATTERN_VIOLATION = "pattern_violation"


class AnomalyEvent(BaseModel):
    """A detected anomaly event with full context."""

    model_config = {"frozen": True}

    anomaly_id: UUID
    dataset_id: DatasetId
    column_name: str | None = None
    category: AnomalyCategory
    severity: DriftSeverity
    detected_at: datetime
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    metric_name: str
    observed_value: float
    expected_value: float
    expected_range: tuple[float, float]
    description: str
    context: dict[str, Any] = Field(default_factory=dict)


class AdaptiveThreshold(BaseModel):
    """Adaptive threshold configuration for a column."""

    column_name: str = Field(..., min_length=1)
    thresholds: dict[str, float]
    last_computed: datetime
