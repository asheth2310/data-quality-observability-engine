"""TimescaleDB time-series store implementation (in-memory for testing).

Implements TimeSeriesStore for storing statistical profiles, freshness metrics,
and adaptive threshold history. Uses in-memory lists to allow testing
without requiring a real TimescaleDB instance.
"""

from datetime import datetime

from data_quality_engine.models import (
    AdaptiveThreshold,
    DataProfile,
    DatasetId,
    FreshnessStatus,
)
from data_quality_engine.storage.interfaces import TimeSeriesStore


class TimescaleTimeSeriesStore(TimeSeriesStore):
    """In-memory implementation of TimeSeriesStore (to be backed by TimescaleDB).

    Stores all time-series data in Python lists for testing purposes.
    In production, this would use hypertables with retention policies.
    """

    def __init__(self, retention_days: int = 90) -> None:
        self._retention_days = retention_days
        # profiles: dataset_key -> list of DataProfile (ordered by profiled_at)
        self._profiles: dict[str, list[DataProfile]] = {}
        # freshness: dataset_key -> list of FreshnessStatus (ordered by check_time)
        self._freshness: dict[str, list[FreshnessStatus]] = {}
        # thresholds: (dataset_key, column_name) -> list of AdaptiveThreshold
        self._thresholds: dict[tuple[str, str], list[AdaptiveThreshold]] = {}

    def _dataset_key(self, dataset_id: DatasetId) -> str:
        """Create a unique key for a dataset."""
        return f"{dataset_id.namespace}:v{dataset_id.version}"

    # --- Profiles ---

    async def store_profile(self, profile: DataProfile) -> None:
        """Store a statistical data profile."""
        key = self._dataset_key(profile.dataset_id)
        if key not in self._profiles:
            self._profiles[key] = []
        self._profiles[key].append(profile)
        # Keep sorted by profiled_at
        self._profiles[key].sort(key=lambda p: p.profiled_at)

    async def get_profiles(
        self,
        dataset_id: DatasetId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[DataProfile]:
        """Retrieve profiles for a dataset within a time range."""
        key = self._dataset_key(dataset_id)
        profiles = self._profiles.get(key, [])

        if start_time is not None:
            profiles = [p for p in profiles if p.profiled_at >= start_time]
        if end_time is not None:
            profiles = [p for p in profiles if p.profiled_at <= end_time]

        # Return most recent first, limited
        return list(reversed(profiles))[:limit]

    async def get_latest_profile(self, dataset_id: DatasetId) -> DataProfile | None:
        """Retrieve the most recent profile for a dataset."""
        key = self._dataset_key(dataset_id)
        profiles = self._profiles.get(key, [])
        if not profiles:
            return None
        return profiles[-1]

    # --- Freshness Metrics ---

    async def store_freshness_status(self, status: FreshnessStatus) -> None:
        """Store a freshness status measurement."""
        key = self._dataset_key(status.dataset_id)
        if key not in self._freshness:
            self._freshness[key] = []
        self._freshness[key].append(status)
        # Keep sorted by check_time
        self._freshness[key].sort(key=lambda s: s.check_time)

    async def get_freshness_history(
        self,
        dataset_id: DatasetId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[FreshnessStatus]:
        """Retrieve freshness history for a dataset."""
        key = self._dataset_key(dataset_id)
        statuses = self._freshness.get(key, [])

        if start_time is not None:
            statuses = [s for s in statuses if s.check_time >= start_time]
        if end_time is not None:
            statuses = [s for s in statuses if s.check_time <= end_time]

        # Return most recent first, limited
        return list(reversed(statuses))[:limit]

    # --- Threshold History ---

    async def store_threshold(self, dataset_id: DatasetId, column_name: str, threshold: AdaptiveThreshold) -> None:
        """Store an adaptive threshold value."""
        key = (self._dataset_key(dataset_id), column_name)
        if key not in self._thresholds:
            self._thresholds[key] = []
        self._thresholds[key].append(threshold)

    async def get_threshold_history(
        self,
        dataset_id: DatasetId,
        column_name: str,
        limit: int = 100,
    ) -> list[AdaptiveThreshold]:
        """Retrieve threshold history for a column."""
        key = (self._dataset_key(dataset_id), column_name)
        thresholds = self._thresholds.get(key, [])
        # Return most recent first, limited
        return list(reversed(thresholds))[:limit]
