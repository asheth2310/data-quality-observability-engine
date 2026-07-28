"""Lineage graph data models."""

from datetime import datetime

from pydantic import BaseModel, Field

from .base import ColumnRef, DatasetId, TransformationType


class LineageEdge(BaseModel):
    """A directed edge in the lineage graph between two columns."""

    model_config = {"frozen": True}

    source: ColumnRef
    target: ColumnRef
    transformation_type: TransformationType
    transformation_expr: str | None = None
    pipeline_id: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    last_observed: datetime


class ImpactGraph(BaseModel):
    """Result of downstream impact analysis from a source column."""

    model_config = {"frozen": True}

    root: ColumnRef
    affected_columns: list[ColumnRef]
    affected_datasets: list[DatasetId]
    affected_pipelines: list[str]
    max_depth: int = Field(..., ge=1)
    total_downstream_count: int = Field(..., ge=0)


class RootCauseCandidate(BaseModel):
    """A candidate root cause column identified via upstream tracing."""

    model_config = {"frozen": True}

    column: ColumnRef
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str
    hops_from_target: int = Field(..., ge=0)


class LineageTrace(BaseModel):
    """Result of upstream lineage tracing."""

    model_config = {"frozen": True}

    target: ColumnRef
    source_columns: list[ColumnRef]
    max_depth: int = Field(..., ge=1)
