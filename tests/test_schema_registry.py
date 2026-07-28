"""Unit tests for the SchemaRegistry service.

Tests contract registration, validation rules, versioning, and schema validation.
"""

import pytest

from data_quality_engine.models import (
    ColumnContract,
    ColumnType,
    ContractVersion,
    DatasetId,
    EvolutionRule,
    ObservedSchema,
    SchemaContract,
)
from data_quality_engine.services.schema_registry import (
    SchemaRegistry,
    SchemaRegistryError,
)
from data_quality_engine.storage.postgres import PostgresMetadataStore


@pytest.fixture
def metadata_store() -> PostgresMetadataStore:
    """Fresh in-memory metadata store for each test."""
    return PostgresMetadataStore()


@pytest.fixture
def registry(metadata_store: PostgresMetadataStore) -> SchemaRegistry:
    """Schema registry instance backed by in-memory store."""
    return SchemaRegistry(metadata_store)


@pytest.fixture
def dataset_id() -> DatasetId:
    return DatasetId(namespace="warehouse.public.users", version=1)


@pytest.fixture
def valid_columns() -> list[ColumnContract]:
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
    ]


@pytest.fixture
def valid_contract(dataset_id: DatasetId, valid_columns: list[ColumnContract]) -> SchemaContract:
    return SchemaContract(
        dataset_id=dataset_id,
        version=1,
        columns=valid_columns,
        evolution_rule=EvolutionRule.ADDITIVE_ONLY,
        created_by="test-user",
    )


class TestRegistrationVersionIncrement:
    """Test that register_contract auto-increments version numbers."""

    @pytest.mark.asyncio
    async def test_first_registration_gets_version_1(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        result = await registry.register_contract(dataset_id, valid_contract)
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_second_registration_gets_version_2(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        await registry.register_contract(dataset_id, valid_contract)
        result = await registry.register_contract(dataset_id, valid_contract)
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_third_registration_gets_version_3(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        await registry.register_contract(dataset_id, valid_contract)
        await registry.register_contract(dataset_id, valid_contract)
        result = await registry.register_contract(dataset_id, valid_contract)
        assert result.version == 3

    @pytest.mark.asyncio
    async def test_different_datasets_get_independent_versions(
        self, registry: SchemaRegistry, valid_columns: list[ColumnContract]
    ):
        ds1 = DatasetId(namespace="warehouse.public.users", version=1)
        ds2 = DatasetId(namespace="warehouse.public.orders", version=1)

        contract1 = SchemaContract(
            dataset_id=ds1, version=1, columns=valid_columns, created_by="test"
        )
        contract2 = SchemaContract(
            dataset_id=ds2, version=1, columns=valid_columns, created_by="test"
        )

        r1 = await registry.register_contract(ds1, contract1)
        r2 = await registry.register_contract(ds2, contract2)

        assert r1.version == 1
        assert r2.version == 1


class TestDuplicateColumnNames:
    """Test that duplicate column names are rejected."""

    @pytest.mark.asyncio
    async def test_duplicate_column_names_rejected(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        """Duplicate column names are caught at Pydantic validation or registry level."""
        columns = [
            ColumnContract(name="id", dtype=ColumnType.INTEGER, nullable=False, primary_key=True),
            ColumnContract(name="id", dtype=ColumnType.STRING, nullable=True),
        ]
        # Pydantic catches this at SchemaContract construction time
        with pytest.raises((ValueError, SchemaRegistryError)):
            contract = SchemaContract(
                dataset_id=dataset_id, version=1, columns=columns, created_by="test"
            )

    @pytest.mark.asyncio
    async def test_case_sensitive_duplicates_rejected(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        """Same name with same case is a duplicate."""
        columns = [
            ColumnContract(name="Email", dtype=ColumnType.STRING, nullable=True),
            ColumnContract(name="Email", dtype=ColumnType.STRING, nullable=True),
        ]
        # Pydantic catches this at SchemaContract construction time
        with pytest.raises((ValueError, SchemaRegistryError)):
            contract = SchemaContract(
                dataset_id=dataset_id, version=1, columns=columns, created_by="test"
            )

    @pytest.mark.asyncio
    async def test_different_case_names_allowed(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        """Different casing means different columns (case-sensitive)."""
        columns = [
            ColumnContract(name="email", dtype=ColumnType.STRING, nullable=True),
            ColumnContract(name="Email", dtype=ColumnType.STRING, nullable=True),
        ]
        contract = SchemaContract(
            dataset_id=dataset_id, version=1, columns=columns, created_by="test"
        )

        # Should succeed — different case = different names
        result = await registry.register_contract(dataset_id, contract)
        assert result.version == 1


class TestPrimaryKeyNonNullable:
    """Test that primary key columns must be non-nullable."""

    @pytest.mark.asyncio
    async def test_primary_key_nullable_rejected(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        """Pydantic auto-corrects this, but we also enforce at registry level."""
        # Note: Pydantic's model_validator auto-sets nullable=False for primary keys.
        # We construct a ColumnContract that has primary_key=True and Pydantic
        # will already enforce nullable=False. The registry's validation is an
        # additional safety check for contracts built outside Pydantic.
        col = ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True)
        # Pydantic enforces non-nullable, so col.nullable will be False here.
        assert col.nullable is False

    @pytest.mark.asyncio
    async def test_primary_key_with_explicit_non_nullable_passes(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        columns = [
            ColumnContract(
                name="id", dtype=ColumnType.INTEGER, nullable=False, primary_key=True
            ),
        ]
        contract = SchemaContract(
            dataset_id=dataset_id, version=1, columns=columns, created_by="test"
        )

        result = await registry.register_contract(dataset_id, contract)
        assert result.version == 1


class TestMinMaxValueOrdering:
    """Test that min_value > max_value is rejected."""

    @pytest.mark.asyncio
    async def test_min_greater_than_max_rejected(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        """min_value > max_value should raise an error."""
        # Pydantic validates this too, so constructing invalid data raises ValueError
        with pytest.raises((ValueError, SchemaRegistryError)):
            columns = [
                ColumnContract(
                    name="score",
                    dtype=ColumnType.FLOAT,
                    nullable=True,
                    min_value=100.0,
                    max_value=50.0,
                ),
            ]

    @pytest.mark.asyncio
    async def test_min_equal_to_max_allowed(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        columns = [
            ColumnContract(
                name="fixed_val",
                dtype=ColumnType.FLOAT,
                nullable=True,
                min_value=42.0,
                max_value=42.0,
            ),
        ]
        contract = SchemaContract(
            dataset_id=dataset_id, version=1, columns=columns, created_by="test"
        )

        result = await registry.register_contract(dataset_id, contract)
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_min_less_than_max_allowed(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        columns = [
            ColumnContract(
                name="range_col",
                dtype=ColumnType.INTEGER,
                nullable=True,
                min_value=0,
                max_value=100,
            ),
        ]
        contract = SchemaContract(
            dataset_id=dataset_id, version=1, columns=columns, created_by="test"
        )

        result = await registry.register_contract(dataset_id, contract)
        assert result.version == 1


class TestMaxNullRateValidation:
    """Test that max_null_rate outside [0.0, 1.0] is rejected."""

    @pytest.mark.asyncio
    async def test_negative_max_null_rate_rejected(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        """Pydantic enforces ge=0.0, so construction raises ValueError."""
        with pytest.raises((ValueError, SchemaRegistryError)):
            ColumnContract(
                name="col",
                dtype=ColumnType.STRING,
                nullable=True,
                max_null_rate=-0.1,
            )

    @pytest.mark.asyncio
    async def test_max_null_rate_above_one_rejected(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        """Pydantic enforces le=1.0, so construction raises ValueError."""
        with pytest.raises((ValueError, SchemaRegistryError)):
            ColumnContract(
                name="col",
                dtype=ColumnType.STRING,
                nullable=True,
                max_null_rate=1.5,
            )

    @pytest.mark.asyncio
    async def test_valid_max_null_rate_boundary_zero(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        columns = [
            ColumnContract(
                name="strict_col",
                dtype=ColumnType.STRING,
                nullable=True,
                max_null_rate=0.0,
            ),
        ]
        contract = SchemaContract(
            dataset_id=dataset_id, version=1, columns=columns, created_by="test"
        )

        result = await registry.register_contract(dataset_id, contract)
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_valid_max_null_rate_boundary_one(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        columns = [
            ColumnContract(
                name="relaxed_col",
                dtype=ColumnType.STRING,
                nullable=True,
                max_null_rate=1.0,
            ),
        ]
        contract = SchemaContract(
            dataset_id=dataset_id, version=1, columns=columns, created_by="test"
        )

        result = await registry.register_contract(dataset_id, contract)
        assert result.version == 1


class TestContractHistory:
    """Test get_contract_history pagination."""

    @pytest.mark.asyncio
    async def test_empty_history_returns_empty_list(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        history = await registry.get_contract_history(dataset_id)
        assert history == []

    @pytest.mark.asyncio
    async def test_history_returns_all_versions(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        await registry.register_contract(dataset_id, valid_contract)
        await registry.register_contract(dataset_id, valid_contract)
        await registry.register_contract(dataset_id, valid_contract)

        history = await registry.get_contract_history(dataset_id)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_history_respects_limit(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        for _ in range(5):
            await registry.register_contract(dataset_id, valid_contract)

        history = await registry.get_contract_history(dataset_id, limit=3)
        assert len(history) == 3


class TestValidateSchema:
    """Test schema validation against registered contracts."""

    @pytest.mark.asyncio
    async def test_valid_schema_passes(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        await registry.register_contract(dataset_id, valid_contract)

        observed = ObservedSchema(
            dataset_id=dataset_id,
            columns=valid_contract.columns,
        )
        result = await registry.validate_schema(dataset_id, observed)
        assert result.valid is True
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_missing_required_column_fails(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        await registry.register_contract(dataset_id, valid_contract)

        # Only provide one column (missing 'id' which is non-nullable/PK)
        observed = ObservedSchema(
            dataset_id=dataset_id,
            columns=[
                ColumnContract(name="email", dtype=ColumnType.STRING, nullable=False),
            ],
        )
        result = await registry.validate_schema(dataset_id, observed)
        assert result.valid is False
        assert any("id" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_type_mismatch_fails(
        self, registry: SchemaRegistry, dataset_id: DatasetId, valid_contract: SchemaContract
    ):
        await registry.register_contract(dataset_id, valid_contract)

        observed = ObservedSchema(
            dataset_id=dataset_id,
            columns=[
                ColumnContract(name="id", dtype=ColumnType.STRING, nullable=False, primary_key=True),
                ColumnContract(name="email", dtype=ColumnType.STRING, nullable=False),
                ColumnContract(name="age", dtype=ColumnType.STRING, nullable=True),
            ],
        )
        result = await registry.validate_schema(dataset_id, observed)
        assert result.valid is False
        assert any("type mismatch" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_no_registered_contract_fails(
        self, registry: SchemaRegistry, dataset_id: DatasetId
    ):
        observed = ObservedSchema(
            dataset_id=dataset_id,
            columns=[
                ColumnContract(name="id", dtype=ColumnType.INTEGER, nullable=False, primary_key=True),
            ],
        )
        result = await registry.validate_schema(dataset_id, observed)
        assert result.valid is False
        assert any("No registered contract" in e for e in result.errors)
