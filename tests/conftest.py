"""Shared test fixtures for the Data Quality & Observability Engine test suite."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from data_quality_engine.models.base import (
    ColumnRef,
    ColumnType,
    DatasetId,
    DataTier,
    EvolutionRule,
)
from data_quality_engine.models.schema import ColumnContract, SchemaContract


@pytest.fixture
def sample_dataset_id() -> DatasetId:
    """A sample DatasetId for testing."""
    return DatasetId(namespace="warehouse.public.users", version=1)


@pytest.fixture
def sample_column_ref(sample_dataset_id: DatasetId) -> ColumnRef:
    """A sample ColumnRef for testing."""
    return ColumnRef(dataset_id=sample_dataset_id, column_name="email")


@pytest.fixture
def sample_columns() -> list[ColumnContract]:
    """A list of sample ColumnContracts for testing."""
    return [
        ColumnContract(
            name="id",
            dtype=ColumnType.INTEGER,
            nullable=False,
            primary_key=True,
        ),
        ColumnContract(
            name="email",
            dtype=ColumnType.STRING,
            nullable=False,
        ),
        ColumnContract(
            name="age",
            dtype=ColumnType.INTEGER,
            nullable=True,
            min_value=0,
            max_value=150,
        ),
        ColumnContract(
            name="score",
            dtype=ColumnType.FLOAT,
            nullable=True,
            max_null_rate=0.1,
        ),
    ]


@pytest.fixture
def sample_schema_contract(
    sample_dataset_id: DatasetId, sample_columns: list[ColumnContract]
) -> SchemaContract:
    """A sample SchemaContract for testing."""
    return SchemaContract(
        dataset_id=sample_dataset_id,
        version=1,
        columns=sample_columns,
        evolution_rule=EvolutionRule.ADDITIVE_ONLY,
        created_at=datetime.now(timezone.utc),
        created_by="test-user",
    )


@pytest.fixture
def utc_now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


@pytest.fixture
def random_uuid():
    """Generate a random UUID."""
    return uuid4()
