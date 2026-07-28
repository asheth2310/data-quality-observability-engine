"""Statistical profiling data models."""

from datetime import datetime

from pydantic import BaseModel, Field

from .base import ColumnType, DatasetId


class HistogramBucket(BaseModel):
    """A single bucket in a histogram."""

    model_config = {"frozen": True}

    lower_bound: float
    upper_bound: float
    count: int = Field(..., ge=0)


class ValueCount(BaseModel):
    """Frequency count for a specific value."""

    model_config = {"frozen": True}

    value: str
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=1.0)


class ColumnProfile(BaseModel):
    """Statistical profile for a single column."""

    model_config = {"frozen": True}

    column_name: str = Field(..., min_length=1)
    dtype: ColumnType
    total_count: int = Field(..., ge=0)
    null_count: int = Field(..., ge=0)
    distinct_count: int = Field(..., ge=0)

    # Numeric statistics (None for non-numeric columns)
    mean: float | None = None
    std_dev: float | None = None
    min_val: float | None = None
    max_val: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p99: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None

    # String statistics (None for non-string columns)
    avg_length: float | None = None
    max_length: int | None = None

    # Distribution data
    histogram: list[HistogramBucket] | None = None
    top_values: list[ValueCount] | None = None


class DataProfile(BaseModel):
    """Full statistical profile for a dataset partition."""

    model_config = {"frozen": True}

    dataset_id: DatasetId
    partition_key: str
    row_count: int = Field(..., ge=0)
    column_profiles: dict[str, ColumnProfile]
    profiled_at: datetime
    profiling_duration_ms: int = Field(..., ge=1)
    is_partial: bool = False
