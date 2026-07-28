"""Schema contract and validation models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .base import ColumnType, DatasetId, EvolutionRule


class ColumnContract(BaseModel):
    """Contract definition for a single column within a dataset."""

    name: str = Field(..., min_length=1, max_length=128)
    dtype: ColumnType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[Any] | None = None
    pattern: str | None = None
    max_null_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_primary_key_non_nullable(self) -> "ColumnContract":
        """Primary key columns must be non-nullable."""
        if self.primary_key and self.nullable:
            object.__setattr__(self, "nullable", False)
        return self

    @model_validator(mode="after")
    def validate_min_max_ordering(self) -> "ColumnContract":
        """min_value must be <= max_value when both are specified."""
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise ValueError(
                    f"min_value ({self.min_value}) must be <= max_value ({self.max_value})"
                )
        return self


class SchemaContract(BaseModel):
    """Versioned schema contract for a dataset."""

    dataset_id: DatasetId
    version: int = Field(..., ge=1)
    columns: list[ColumnContract] = Field(..., min_length=1, max_length=1000)
    evolution_rule: EvolutionRule = EvolutionRule.ADDITIVE_ONLY
    min_row_count: int | None = Field(default=None, ge=0)
    max_row_count: int | None = Field(default=None, ge=0)
    created_at: datetime | None = None
    created_by: str = ""

    @field_validator("columns")
    @classmethod
    def validate_unique_column_names(cls, v: list[ColumnContract]) -> list[ColumnContract]:
        """Column names must be unique within a contract (case-sensitive)."""
        names = [col.name for col in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(
                f"Column names must be unique. Duplicates: {set(duplicates)}"
            )
        return v

    @model_validator(mode="after")
    def validate_row_count_ordering(self) -> "SchemaContract":
        """min_row_count must be <= max_row_count when both are specified."""
        if self.min_row_count is not None and self.max_row_count is not None:
            if self.min_row_count > self.max_row_count:
                raise ValueError(
                    f"min_row_count ({self.min_row_count}) must be <= "
                    f"max_row_count ({self.max_row_count})"
                )
        return self


class ObservedSchema(BaseModel):
    """Schema observed from actual data at a point in time."""

    dataset_id: DatasetId
    columns: list[ColumnContract]
    observed_at: datetime | None = None


class ContractVersion(BaseModel):
    """A versioned schema contract with its creation timestamp."""

    dataset_id: DatasetId
    version: int = Field(..., ge=1)
    contract: SchemaContract
    created_at: datetime | None = None


class ValidationResult(BaseModel):
    """Result of schema validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
