"""Abstract base classes for storage layer interfaces."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from data_quality_engine.models import (
    Alert,
    AdaptiveThreshold,
    ColumnRef,
    ContractVersion,
    DataProfile,
    DatasetId,
    DatasetRegistration,
    DriftReport,
    FreshnessStatus,
    HealingResult,
    LineageEdge,
    SchemaContract,
)


class MetadataStore(ABC):
    """Abstract interface for persistent metadata storage (e.g., PostgreSQL).

    Stores schema contracts, dataset registrations, healing history, and alert state.
    """

    # --- Schema Contracts ---

    @abstractmethod
    async def store_contract(self, contract: SchemaContract) -> ContractVersion:
        """Store a schema contract and return the versioned record."""
        ...

    @abstractmethod
    async def get_contract(self, dataset_id: DatasetId, version: int | None = None) -> ContractVersion | None:
        """Get a contract by dataset_id. Returns latest version if version is None."""
        ...

    @abstractmethod
    async def get_contract_history(self, dataset_id: DatasetId, limit: int = 50) -> list[ContractVersion]:
        """Retrieve version history of schema contracts for a dataset."""
        ...

    # --- Dataset Registrations ---

    @abstractmethod
    async def register_dataset(self, registration: DatasetRegistration) -> DatasetRegistration:
        """Register or update a dataset registration."""
        ...

    @abstractmethod
    async def get_dataset(self, dataset_id: DatasetId) -> DatasetRegistration | None:
        """Retrieve a dataset registration by ID."""
        ...

    @abstractmethod
    async def list_datasets(self, domain: str | None = None) -> list[DatasetRegistration]:
        """List all registered datasets, optionally filtered by domain."""
        ...

    # --- Drift Reports ---

    @abstractmethod
    async def store_drift_report(self, report: DriftReport) -> None:
        """Store a drift detection report."""
        ...

    @abstractmethod
    async def get_drift_reports(self, dataset_id: DatasetId, limit: int = 50) -> list[DriftReport]:
        """Retrieve drift reports for a dataset, most recent first."""
        ...

    # --- Healing History ---

    @abstractmethod
    async def store_healing_result(self, result: HealingResult) -> None:
        """Store a healing execution result."""
        ...

    @abstractmethod
    async def get_healing_history(
        self, dataset_id: DatasetId, limit: int = 50
    ) -> list[HealingResult]:
        """Retrieve healing history for a dataset."""
        ...

    # --- Alert State ---

    @abstractmethod
    async def store_alert(self, alert: Alert) -> None:
        """Store or update an alert."""
        ...

    @abstractmethod
    async def get_alert(self, alert_id: UUID) -> Alert | None:
        """Retrieve an alert by ID."""
        ...

    @abstractmethod
    async def get_active_alerts(self, dataset_id: DatasetId | None = None) -> list[Alert]:
        """Retrieve active (unacknowledged) alerts, optionally filtered by dataset."""
        ...


class TimeSeriesStore(ABC):
    """Abstract interface for time-series data storage (e.g., TimescaleDB).

    Stores statistical profiles, freshness metrics, and threshold history.
    """

    # --- Profiles ---

    @abstractmethod
    async def store_profile(self, profile: DataProfile) -> None:
        """Store a statistical data profile."""
        ...

    @abstractmethod
    async def get_profiles(
        self,
        dataset_id: DatasetId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[DataProfile]:
        """Retrieve profiles for a dataset within a time range."""
        ...

    @abstractmethod
    async def get_latest_profile(self, dataset_id: DatasetId) -> DataProfile | None:
        """Retrieve the most recent profile for a dataset."""
        ...

    # --- Freshness Metrics ---

    @abstractmethod
    async def store_freshness_status(self, status: FreshnessStatus) -> None:
        """Store a freshness status measurement."""
        ...

    @abstractmethod
    async def get_freshness_history(
        self,
        dataset_id: DatasetId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[FreshnessStatus]:
        """Retrieve freshness history for a dataset."""
        ...

    # --- Threshold History ---

    @abstractmethod
    async def store_threshold(self, dataset_id: DatasetId, column_name: str, threshold: AdaptiveThreshold) -> None:
        """Store an adaptive threshold value."""
        ...

    @abstractmethod
    async def get_threshold_history(
        self,
        dataset_id: DatasetId,
        column_name: str,
        limit: int = 100,
    ) -> list[AdaptiveThreshold]:
        """Retrieve threshold history for a column."""
        ...


class GraphStore(ABC):
    """Abstract interface for graph database storage (e.g., Neo4j).

    Stores lineage graph: nodes (datasets/columns) and directed edges (transformations).
    """

    @abstractmethod
    async def add_edge(self, edge: LineageEdge) -> None:
        """Add a directed edge to the lineage graph."""
        ...

    @abstractmethod
    async def remove_edge(self, source: ColumnRef, target: ColumnRef) -> bool:
        """Remove an edge from the graph. Returns True if edge existed."""
        ...

    @abstractmethod
    async def get_downstream(self, source: ColumnRef, max_depth: int = 10) -> list[ColumnRef]:
        """Get all downstream columns reachable from source via BFS, up to max_depth."""
        ...

    @abstractmethod
    async def get_upstream(self, target: ColumnRef, max_depth: int = 10) -> list[ColumnRef]:
        """Get all upstream columns that lead to target via reverse BFS, up to max_depth."""
        ...

    @abstractmethod
    async def has_cycle(self, source: ColumnRef, target: ColumnRef) -> bool:
        """Check if adding an edge from source to target would create a cycle."""
        ...

    @abstractmethod
    async def get_edges_from(self, source: ColumnRef) -> list[LineageEdge]:
        """Get all outgoing edges from a source column."""
        ...

    @abstractmethod
    async def get_edges_to(self, target: ColumnRef) -> list[LineageEdge]:
        """Get all incoming edges to a target column."""
        ...

    @abstractmethod
    async def node_exists(self, column: ColumnRef) -> bool:
        """Check if a column node exists in the graph."""
        ...

    @abstractmethod
    async def add_node(self, column: ColumnRef) -> None:
        """Add a column node to the graph."""
        ...


class CacheStore(ABC):
    """Abstract interface for a cache layer (e.g., Redis).

    Provides get/set/delete with TTL for caching profiles, rate limiting, etc.
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value by key. Returns None if not found or expired."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set a value with optional TTL (time-to-live) in seconds."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if the key existed."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists and has not expired."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached entries."""
        ...
