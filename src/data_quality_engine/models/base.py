"""Base data models and enums for the Data Quality & Observability Engine."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class DataTier(str, Enum):
    """Dataset criticality tier determining SLA targets and escalation urgency."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ColumnType(str, Enum):
    """Supported column data types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    DECIMAL = "decimal"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"
    BINARY = "binary"


class EvolutionRule(str, Enum):
    """Schema evolution policy for a dataset contract."""

    STRICT = "strict"
    ADDITIVE_ONLY = "additive"
    PERMISSIVE = "permissive"


class TransformationType(str, Enum):
    """Classification of data transformation between columns."""

    DIRECT = "direct"
    DERIVED = "derived"
    AGGREGATED = "aggregated"
    JOINED = "joined"
    FILTERED = "filtered"
    PIVOTED = "pivoted"


class DatasetId(BaseModel):
    """Unique identifier for a dataset following dot-notation namespace."""

    model_config = {"frozen": True}

    namespace: str = Field(
        ...,
        min_length=1,
        description="Dot-notation namespace, e.g. 'warehouse.schema.table'",
    )
    version: int = Field(default=1, ge=1)

    @field_validator("namespace")
    @classmethod
    def validate_namespace_dot_notation(cls, v: str) -> str:
        """Validate that namespace follows dot-notation pattern."""
        parts = v.split(".")
        if len(parts) < 1:
            raise ValueError("Namespace must have at least one segment")
        for part in parts:
            if not part:
                raise ValueError(
                    "Namespace segments cannot be empty (no consecutive dots)"
                )
        return v


class ColumnRef(BaseModel):
    """Reference to a specific column within a dataset."""

    model_config = {"frozen": True}

    dataset_id: DatasetId
    column_name: str = Field(..., min_length=1)


class DatasetRegistration(BaseModel):
    """Registration metadata for a monitored dataset."""

    dataset_id: DatasetId
    owner: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    tier: DataTier
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
