"""PostgreSQL metadata store implementation (in-memory for testing).

Implements MetadataStore for storing schema contracts, dataset registrations,
drift reports, healing logs, and alert state. Uses in-memory dicts
to allow testing without requiring a real PostgreSQL instance.
"""

from datetime import datetime
from uuid import UUID

from data_quality_engine.models import (
    Alert,
    ContractVersion,
    DatasetId,
    DatasetRegistration,
    DriftReport,
    HealingResult,
    SchemaContract,
)
from data_quality_engine.storage.interfaces import MetadataStore


class PostgresMetadataStore(MetadataStore):
    """In-memory implementation of MetadataStore (to be backed by PostgreSQL/psycopg).

    Stores all data in Python dicts for testing purposes.
    In production, this would use psycopg async connection pool.
    """

    def __init__(self) -> None:
        # contracts: dataset_namespace -> list of ContractVersion (ordered by version)
        self._contracts: dict[str, list[ContractVersion]] = {}
        # registrations: dataset_namespace -> DatasetRegistration
        self._registrations: dict[str, DatasetRegistration] = {}
        # drift_reports: dataset_namespace -> list of DriftReport (most recent first)
        self._drift_reports: dict[str, list[DriftReport]] = {}
        # healing_results: dataset_namespace -> list of HealingResult (most recent first)
        self._healing_results: dict[str, list[HealingResult]] = {}
        # alerts: alert_id -> Alert
        self._alerts: dict[UUID, Alert] = {}

    def _dataset_key(self, dataset_id: DatasetId) -> str:
        """Create a unique key for a dataset."""
        return f"{dataset_id.namespace}:v{dataset_id.version}"

    # --- Schema Contracts ---

    async def store_contract(self, contract: SchemaContract) -> ContractVersion:
        """Store a schema contract and return the versioned record."""
        key = self._dataset_key(contract.dataset_id)
        if key not in self._contracts:
            self._contracts[key] = []

        contract_version = ContractVersion(
            dataset_id=contract.dataset_id,
            version=contract.version,
            contract=contract,
            created_at=contract.created_at or datetime.utcnow(),
        )
        self._contracts[key].append(contract_version)
        return contract_version

    async def get_contract(self, dataset_id: DatasetId, version: int | None = None) -> ContractVersion | None:
        """Get a contract by dataset_id. Returns latest version if version is None."""
        key = self._dataset_key(dataset_id)
        versions = self._contracts.get(key, [])
        if not versions:
            return None

        if version is None:
            return versions[-1]

        for cv in versions:
            if cv.version == version:
                return cv
        return None

    async def get_contract_history(self, dataset_id: DatasetId, limit: int = 50) -> list[ContractVersion]:
        """Retrieve version history of schema contracts for a dataset."""
        key = self._dataset_key(dataset_id)
        versions = self._contracts.get(key, [])
        # Return in reverse chronological order (newest first)
        return list(reversed(versions[-limit:]))

    # --- Dataset Registrations ---

    async def register_dataset(self, registration: DatasetRegistration) -> DatasetRegistration:
        """Register or update a dataset registration."""
        key = self._dataset_key(registration.dataset_id)
        now = datetime.utcnow()
        if key not in self._registrations:
            registration.created_at = now
        registration.updated_at = now
        self._registrations[key] = registration
        return registration

    async def get_dataset(self, dataset_id: DatasetId) -> DatasetRegistration | None:
        """Retrieve a dataset registration by ID."""
        key = self._dataset_key(dataset_id)
        return self._registrations.get(key)

    async def list_datasets(self, domain: str | None = None) -> list[DatasetRegistration]:
        """List all registered datasets, optionally filtered by domain."""
        datasets = list(self._registrations.values())
        if domain is not None:
            datasets = [d for d in datasets if d.domain == domain]
        return datasets

    # --- Drift Reports ---

    async def store_drift_report(self, report: DriftReport) -> None:
        """Store a drift detection report."""
        key = self._dataset_key(report.dataset_id)
        if key not in self._drift_reports:
            self._drift_reports[key] = []
        self._drift_reports[key].insert(0, report)

    async def get_drift_reports(self, dataset_id: DatasetId, limit: int = 50) -> list[DriftReport]:
        """Retrieve drift reports for a dataset, most recent first."""
        key = self._dataset_key(dataset_id)
        reports = self._drift_reports.get(key, [])
        return reports[:limit]

    # --- Healing History ---

    async def store_healing_result(self, result: HealingResult) -> None:
        """Store a healing execution result."""
        # Use the healing_id to associate with a dataset — in real impl, the dataset_id
        # would be stored. For in-memory, store globally and filter by context.
        # We'll use a special "_global" key for now.
        key = "_global"
        if key not in self._healing_results:
            self._healing_results[key] = []
        self._healing_results[key].insert(0, result)

    async def get_healing_history(
        self, dataset_id: DatasetId, limit: int = 50
    ) -> list[HealingResult]:
        """Retrieve healing history for a dataset."""
        # In the in-memory implementation, return all results (real impl filters by dataset)
        key = "_global"
        results = self._healing_results.get(key, [])
        return results[:limit]

    # --- Alert State ---

    async def store_alert(self, alert: Alert) -> None:
        """Store or update an alert."""
        self._alerts[alert.alert_id] = alert

    async def get_alert(self, alert_id: UUID) -> Alert | None:
        """Retrieve an alert by ID."""
        return self._alerts.get(alert_id)

    async def get_active_alerts(self, dataset_id: DatasetId | None = None) -> list[Alert]:
        """Retrieve active (unacknowledged) alerts, optionally filtered by dataset."""
        alerts = [a for a in self._alerts.values() if a.acknowledged_at is None]
        if dataset_id is not None:
            key = self._dataset_key(dataset_id)
            alerts = [a for a in alerts if self._dataset_key(a.dataset_id) == key]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)
