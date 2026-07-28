"""Freshness SLA monitoring service.

Monitors dataset freshness against configured SLAs, detects staleness,
and reports status (HEALTHY, WARNING, CRITICAL) based on elapsed time
since last data arrival.
"""

from datetime import datetime, timezone
from typing import Any

from data_quality_engine.models.base import DatasetId
from data_quality_engine.models.freshness import (
    FreshnessSLA,
    FreshnessState,
    FreshnessStatus,
)

# Severity ordering for monotonic enforcement: higher value = worse status
_STATUS_SEVERITY: dict[FreshnessState, int] = {
    FreshnessState.HEALTHY: 0,
    FreshnessState.WARNING: 1,
    FreshnessState.CRITICAL: 2,
    FreshnessState.UNKNOWN: 3,
}


class FreshnessMonitorError(Exception):
    """Raised when freshness monitor encounters an invalid operation."""

    pass


class FreshnessMonitor:
    """Dataset freshness monitoring with SLA enforcement.

    Tracks data arrival times and evaluates freshness status against
    registered SLA configurations. Enforces monotonic degradation:
    without new data, status can only worsen (HEALTHY → WARNING → CRITICAL).
    """

    def __init__(self) -> None:
        """Initialize FreshnessMonitor with empty SLA and arrival registries."""
        self._sla_configs: dict[str, FreshnessSLA] = {}
        self._last_arrivals: dict[str, datetime] = {}
        # Track the last known status per dataset for monotonic enforcement
        self._last_status: dict[str, FreshnessState] = {}
        # Track the arrival time that was active when last status was computed
        self._last_status_arrival: dict[str, datetime | None] = {}
        # History of freshness checks per dataset
        self._freshness_history: dict[str, list[FreshnessStatus]] = {}

    async def register_sla(
        self, dataset_id: DatasetId, sla: FreshnessSLA
    ) -> dict[str, Any]:
        """Register a freshness SLA for a dataset.

        Validates the SLA parameters and stores the configuration.

        Args:
            dataset_id: The dataset to register the SLA for.
            sla: The FreshnessSLA configuration with max_staleness, thresholds, etc.

        Returns:
            A dict with registration confirmation details.

        Raises:
            FreshnessMonitorError: If SLA parameters fail validation.
        """
        # Validate max_staleness_seconds range [1, 2592000]
        if not isinstance(sla.max_staleness_seconds, int):
            raise FreshnessMonitorError(
                "max_staleness_seconds must be a positive integer"
            )
        if sla.max_staleness_seconds < 1 or sla.max_staleness_seconds > 2592000:
            raise FreshnessMonitorError(
                f"max_staleness_seconds must be between 1 and 2592000, "
                f"got {sla.max_staleness_seconds}"
            )

        # Validate threshold ordering: 0 < warning < critical <= 1.0
        if sla.warning_threshold <= 0.0:
            raise FreshnessMonitorError(
                f"warning_threshold must be > 0.0, got {sla.warning_threshold}"
            )
        if sla.warning_threshold >= 1.0:
            raise FreshnessMonitorError(
                f"warning_threshold must be < 1.0, got {sla.warning_threshold}"
            )
        if sla.critical_threshold <= 0.0:
            raise FreshnessMonitorError(
                f"critical_threshold must be > 0.0, got {sla.critical_threshold}"
            )
        if sla.critical_threshold > 1.0:
            raise FreshnessMonitorError(
                f"critical_threshold must be <= 1.0, got {sla.critical_threshold}"
            )
        if sla.warning_threshold >= sla.critical_threshold:
            raise FreshnessMonitorError(
                f"warning_threshold ({sla.warning_threshold}) must be < "
                f"critical_threshold ({sla.critical_threshold})"
            )

        key = self._dataset_key(dataset_id)
        self._sla_configs[key] = sla

        return {
            "dataset_id": dataset_id,
            "max_staleness_seconds": sla.max_staleness_seconds,
            "warning_threshold": sla.warning_threshold,
            "critical_threshold": sla.critical_threshold,
            "registered": True,
        }

    async def record_data_arrival(
        self, dataset_id: DatasetId, arrival_time: datetime | None = None
    ) -> dict[str, Any]:
        """Record when new data arrives for a dataset.

        Resets the monotonic status enforcement since new data arrived,
        allowing the status to potentially improve.

        Args:
            dataset_id: The dataset that received new data.
            arrival_time: When the data arrived. Defaults to current UTC time.

        Returns:
            A dict with the recorded arrival details.
        """
        if arrival_time is None:
            arrival_time = datetime.now(timezone.utc)

        key = self._dataset_key(dataset_id)
        self._last_arrivals[key] = arrival_time

        # Reset monotonic enforcement since new data arrived
        # Status can now improve on next check
        self._last_status.pop(key, None)
        self._last_status_arrival.pop(key, None)

        return {
            "dataset_id": dataset_id,
            "arrival_time": arrival_time,
            "recorded": True,
        }

    async def check_freshness(
        self, dataset_id: DatasetId, check_time: datetime | None = None
    ) -> FreshnessStatus:
        """Check current freshness status against registered SLA.

        Computes staleness as elapsed seconds since last data arrival and
        determines status based on configured thresholds.

        Enforces monotonic degradation: without new data, status can only
        worsen (HEALTHY → WARNING → CRITICAL), never improve.

        Args:
            dataset_id: The dataset to check freshness for.
            check_time: The time to evaluate freshness at. Defaults to current UTC time.

        Returns:
            FreshnessStatus with computed staleness, SLA percentage, and status.

        Raises:
            FreshnessMonitorError: If no SLA is registered for the dataset.
        """
        if check_time is None:
            check_time = datetime.now(timezone.utc)

        key = self._dataset_key(dataset_id)

        if key not in self._sla_configs:
            raise FreshnessMonitorError(
                f"No SLA registered for dataset: {dataset_id.namespace}"
            )

        sla = self._sla_configs[key]
        last_arrival = self._last_arrivals.get(key)

        if last_arrival is None:
            # No data has ever arrived - report as CRITICAL with max staleness
            result = FreshnessStatus(
                dataset_id=dataset_id,
                last_updated=None,
                staleness_seconds=float(sla.max_staleness_seconds),
                sla_consumed_pct=2.0,
                status=FreshnessState.CRITICAL,
                predicted_next_arrival=None,
                check_time=check_time,
            )
            self._record_check(key, result, last_arrival)
            return result

        # Compute staleness as elapsed seconds since last arrival
        staleness_delta = check_time - last_arrival
        staleness_seconds = max(0.0, staleness_delta.total_seconds())

        # Compute SLA consumed percentage, capped at 2.0
        sla_consumed_pct = min(
            staleness_seconds / sla.max_staleness_seconds, 2.0
        )

        # Determine status based on thresholds
        critical_boundary = sla.critical_threshold * sla.max_staleness_seconds
        warning_boundary = sla.warning_threshold * sla.max_staleness_seconds

        if staleness_seconds > critical_boundary:
            computed_status = FreshnessState.CRITICAL
        elif staleness_seconds > warning_boundary:
            computed_status = FreshnessState.WARNING
        else:
            computed_status = FreshnessState.HEALTHY

        # Enforce monotonic degradation: without new data, status only worsens
        status = self._enforce_monotonic(key, computed_status, last_arrival)

        result = FreshnessStatus(
            dataset_id=dataset_id,
            last_updated=last_arrival,
            staleness_seconds=staleness_seconds,
            sla_consumed_pct=sla_consumed_pct,
            status=status,
            predicted_next_arrival=None,
            check_time=check_time,
        )

        self._record_check(key, result, last_arrival)
        return result

    def _enforce_monotonic(
        self, key: str, computed_status: FreshnessState, current_arrival: datetime | None
    ) -> FreshnessState:
        """Enforce monotonic status degradation.

        Without new data arriving, status can only worsen:
        HEALTHY → WARNING → CRITICAL, never improve.

        If new data has arrived since the last check (detected by comparing
        arrival timestamps), the monotonic constraint is relaxed.
        """
        previous_status = self._last_status.get(key)
        previous_arrival = self._last_status_arrival.get(key)

        if previous_status is None:
            # First check — no enforcement needed
            return computed_status

        # If same arrival time (no new data), enforce monotonic degradation
        if current_arrival == previous_arrival:
            prev_severity = _STATUS_SEVERITY.get(previous_status, 0)
            computed_severity = _STATUS_SEVERITY.get(computed_status, 0)
            if computed_severity < prev_severity:
                # Would improve — not allowed without new data
                return previous_status

        return computed_status

    def _record_check(
        self, key: str, result: FreshnessStatus, last_arrival: datetime | None
    ) -> None:
        """Record a freshness check result for history and monotonic tracking."""
        # Update last known status for monotonic enforcement
        self._last_status[key] = result.status
        self._last_status_arrival[key] = last_arrival

        # Append to history
        if key not in self._freshness_history:
            self._freshness_history[key] = []
        self._freshness_history[key].append(result)

    async def get_freshness_history(
        self, dataset_id: DatasetId
    ) -> list[FreshnessStatus]:
        """Return the history of freshness checks for a dataset.

        Args:
            dataset_id: The dataset to retrieve history for.

        Returns:
            A list of FreshnessStatus objects in chronological order.
        """
        key = self._dataset_key(dataset_id)
        return list(self._freshness_history.get(key, []))

    async def get_all_sla_statuses(self) -> dict[str, FreshnessStatus]:
        """Get current freshness status for all registered datasets.

        Performs a freshness check for every dataset with a registered SLA
        and returns the results keyed by dataset key.

        Returns:
            A dict mapping dataset keys to their current FreshnessStatus.
        """
        results: dict[str, FreshnessStatus] = {}
        now = datetime.now(timezone.utc)

        for key, sla in self._sla_configs.items():
            dataset_id = sla.dataset_id
            status = await self.check_freshness(dataset_id, now)
            results[key] = status

        return results

    def _dataset_key(self, dataset_id: DatasetId) -> str:
        """Generate a stable string key for a dataset ID."""
        return f"{dataset_id.namespace}:v{dataset_id.version}"
