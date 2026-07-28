"""Schema drift detection models."""

from datetime import datetime
from enum import Enum
from functools import total_ordering

from pydantic import BaseModel, Field

from .base import DatasetId


class DriftType(str, Enum):
    """Types of schema drift that can be detected."""

    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    TYPE_CHANGED = "type_changed"
    NULLABILITY_CHANGED = "nullability_changed"
    CONSTRAINT_CHANGED = "constraint_changed"


@total_ordering
class DriftSeverity(str, Enum):
    """Severity classification for detected drift with ordering support."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, DriftSeverity):
            return NotImplemented
        order = {DriftSeverity.INFO: 0, DriftSeverity.WARNING: 1, DriftSeverity.CRITICAL: 2}
        return order[self] < order[other]

    def __le__(self, other: object) -> bool:
        if not isinstance(other, DriftSeverity):
            return NotImplemented
        order = {DriftSeverity.INFO: 0, DriftSeverity.WARNING: 1, DriftSeverity.CRITICAL: 2}
        return order[self] <= order[other]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, DriftSeverity):
            return NotImplemented
        order = {DriftSeverity.INFO: 0, DriftSeverity.WARNING: 1, DriftSeverity.CRITICAL: 2}
        return order[self] > order[other]

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, DriftSeverity):
            return NotImplemented
        order = {DriftSeverity.INFO: 0, DriftSeverity.WARNING: 1, DriftSeverity.CRITICAL: 2}
        return order[self] >= order[other]


class ColumnDrift(BaseModel):
    """A detected drift for a single column."""

    model_config = {"frozen": True}

    column_name: str = Field(..., min_length=1)
    drift_type: DriftType
    severity: DriftSeverity
    old_value: str | None = None
    new_value: str | None = None
    affected_downstream: int = Field(default=0, ge=0)


class DriftReport(BaseModel):
    """Complete drift detection report for a dataset."""

    model_config = {"frozen": True}

    dataset_id: DatasetId
    contract_version: int = Field(..., ge=1)
    detected_at: datetime
    drifts: list[ColumnDrift]
    overall_severity: DriftSeverity
    auto_evolvable: bool
    requires_human_review: bool
