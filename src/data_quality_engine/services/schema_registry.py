"""Schema Registry service for contract registration, versioning, and validation.

Manages versioned schema contracts for datasets, enforces business logic
validation rules, and provides schema validation against registered contracts.
"""

from datetime import datetime, timezone

from data_quality_engine.models import (
    ColumnContract,
    ContractVersion,
    DatasetId,
    ObservedSchema,
    SchemaContract,
    ValidationResult,
)
from data_quality_engine.storage.interfaces import MetadataStore


class SchemaRegistryError(Exception):
    """Raised when a schema registry operation fails validation."""

    def __init__(self, message: str, violated_rule: str) -> None:
        super().__init__(message)
        self.violated_rule = violated_rule


class SchemaRegistry:
    """Versioned schema contract management.

    Handles registration of new contracts with auto-incrementing versions,
    business-logic validation beyond Pydantic model constraints, and
    schema validation against registered contracts.
    """

    def __init__(self, metadata_store: MetadataStore) -> None:
        self._store = metadata_store

    async def register_contract(
        self, dataset_id: DatasetId, schema: SchemaContract
    ) -> ContractVersion:
        """Register or update a schema contract for a dataset.

        Validates the contract, assigns the next version number, and stores it.
        Version numbers start at 1 per dataset and increment by 1.

        Args:
            dataset_id: The dataset this contract applies to.
            schema: The schema contract to register.

        Returns:
            The stored ContractVersion with the assigned version number.

        Raises:
            SchemaRegistryError: If the contract fails validation.
        """
        # Perform business-logic validation
        self._validate_contract(schema)

        # Determine the next version number
        latest = await self._store.get_contract(dataset_id)
        next_version = 1 if latest is None else latest.version + 1

        # Create the contract with the correct version and timestamp
        contract_to_store = SchemaContract(
            dataset_id=dataset_id,
            version=next_version,
            columns=schema.columns,
            evolution_rule=schema.evolution_rule,
            min_row_count=schema.min_row_count,
            max_row_count=schema.max_row_count,
            created_at=datetime.now(timezone.utc),
            created_by=schema.created_by,
        )

        # Store and return
        return await self._store.store_contract(contract_to_store)

    async def get_contract_history(
        self, dataset_id: DatasetId, limit: int = 50
    ) -> list[ContractVersion]:
        """Retrieve version history of schema contracts for a dataset.

        Args:
            dataset_id: The dataset to retrieve history for.
            limit: Maximum number of versions to return (default 50).

        Returns:
            List of ContractVersion in reverse chronological order (newest first).
        """
        return await self._store.get_contract_history(dataset_id, limit=limit)

    async def validate_schema(
        self, dataset_id: DatasetId, observed_schema: ObservedSchema
    ) -> ValidationResult:
        """Validate an observed schema against the registered contract.

        Checks the observed schema's columns against the latest registered
        contract for the dataset, reporting any discrepancies.

        Args:
            dataset_id: The dataset to validate against.
            observed_schema: The schema observed from actual data.

        Returns:
            ValidationResult indicating whether the schema is valid and any errors.
        """
        latest = await self._store.get_contract(dataset_id)
        if latest is None:
            return ValidationResult(
                valid=False,
                errors=[f"No registered contract found for dataset '{dataset_id.namespace}'"],
            )

        contract = latest.contract
        errors: list[str] = []

        # Build lookup of contract columns by name
        contract_columns = {col.name: col for col in contract.columns}
        observed_columns = {col.name: col for col in observed_schema.columns}

        # Check for missing columns (in contract but not observed)
        for col_name, col_contract in contract_columns.items():
            if col_name not in observed_columns:
                if col_contract.primary_key or not col_contract.nullable:
                    errors.append(
                        f"Required column '{col_name}' is missing from observed schema"
                    )
                else:
                    errors.append(
                        f"Optional column '{col_name}' is missing from observed schema"
                    )

        # Check for type mismatches
        for col_name, observed_col in observed_columns.items():
            if col_name in contract_columns:
                expected = contract_columns[col_name]
                if observed_col.dtype != expected.dtype:
                    errors.append(
                        f"Column '{col_name}' type mismatch: "
                        f"expected {expected.dtype.value}, got {observed_col.dtype.value}"
                    )
                # Check nullability: if contract says non-nullable, observed must agree
                if not expected.nullable and observed_col.nullable:
                    errors.append(
                        f"Column '{col_name}' is nullable but contract requires non-nullable"
                    )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
        )

    def _validate_contract(self, schema: SchemaContract) -> None:
        """Perform business-logic validation on a schema contract.

        Pydantic already validates field-level constraints (min_length, ge/le, etc.),
        but this method enforces cross-field business rules that the registry must
        additionally guarantee.

        Raises:
            SchemaRegistryError: If any validation rule is violated.
        """
        columns = schema.columns

        # Rule: column count must be [1, 1000]
        if len(columns) < 1:
            raise SchemaRegistryError(
                "Contract must define at least 1 column",
                violated_rule="column_count_minimum",
            )
        if len(columns) > 1000:
            raise SchemaRegistryError(
                f"Contract defines {len(columns)} columns, maximum is 1000",
                violated_rule="column_count_maximum",
            )

        # Rule: column names must be unique (case-sensitive)
        names = [col.name for col in columns]
        seen: set[str] = set()
        for name in names:
            if name in seen:
                raise SchemaRegistryError(
                    f"Duplicate column name: '{name}'",
                    violated_rule="unique_column_names",
                )
            seen.add(name)

        for col in columns:
            # Rule: column name length [1, 128]
            if len(col.name) < 1:
                raise SchemaRegistryError(
                    "Column name cannot be empty",
                    violated_rule="column_name_length_minimum",
                )
            if len(col.name) > 128:
                raise SchemaRegistryError(
                    f"Column name '{col.name[:50]}...' exceeds 128 characters",
                    violated_rule="column_name_length_maximum",
                )

            # Rule: primary key must be non-nullable
            if col.primary_key and col.nullable:
                raise SchemaRegistryError(
                    f"Primary key column '{col.name}' must be non-nullable",
                    violated_rule="primary_key_non_nullable",
                )

            # Rule: max_null_rate must be in [0.0, 1.0]
            if col.max_null_rate < 0.0 or col.max_null_rate > 1.0:
                raise SchemaRegistryError(
                    f"Column '{col.name}' max_null_rate ({col.max_null_rate}) "
                    f"must be in range [0.0, 1.0]",
                    violated_rule="max_null_rate_range",
                )

            # Rule: min_value <= max_value when both are specified
            if col.min_value is not None and col.max_value is not None:
                if col.min_value > col.max_value:
                    raise SchemaRegistryError(
                        f"Column '{col.name}' min_value ({col.min_value}) "
                        f"must be <= max_value ({col.max_value})",
                        violated_rule="min_max_value_ordering",
                    )
