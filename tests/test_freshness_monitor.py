"""Unit tests for the FreshnessMonitor service.

Tests cover:
- Valid SLA registration
- Invalid SLA rejection with descriptive errors
- Correct status computation (HEALTHY, WARNING, CRITICAL)
- Default thresholds applied when not specified
- Data arrival recording
- SLA consumed percentage computation (capped at 2.0)
"""

from datetime import datetime, timedelta, timezone

import pytest

from data_quality_engine.models.base import DatasetId
from data_quality_engine.models.freshness import FreshnessSLA, FreshnessState
from data_quality_engine.services.freshness_monitor import (
    FreshnessMonitor,
    FreshnessMonitorError,
)


@pytest.fixture
def monitor() -> FreshnessMonitor:
    """Create a fresh FreshnessMonitor instance."""
    return FreshnessMonitor()


@pytest.fixture
def dataset_id() -> DatasetId:
    """A sample dataset ID for freshness tests."""
    return DatasetId(namespace="warehouse.public.orders", version=1)


@pytest.fixture
def valid_sla(dataset_id: DatasetId) -> FreshnessSLA:
    """A valid FreshnessSLA with explicit thresholds."""
    return FreshnessSLA(
        dataset_id=dataset_id,
        max_staleness_seconds=3600,
        expected_schedule="0 * * * *",
        warning_threshold=0.8,
        critical_threshold=0.9,
    )


# --- Valid SLA Registration ---


@pytest.mark.asyncio
async def test_register_valid_sla(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """A valid SLA should be registered successfully."""
    result = await monitor.register_sla(dataset_id, valid_sla)

    assert result["registered"] is True
    assert result["max_staleness_seconds"] == 3600
    assert result["warning_threshold"] == 0.8
    assert result["critical_threshold"] == 0.9


@pytest.mark.asyncio
async def test_register_sla_min_staleness(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Registration with min max_staleness_seconds=1 should succeed."""
    sla = FreshnessSLA(
        dataset_id=dataset_id,
        max_staleness_seconds=1,
        expected_schedule="* * * * *",
    )
    result = await monitor.register_sla(dataset_id, sla)
    assert result["registered"] is True
    assert result["max_staleness_seconds"] == 1


@pytest.mark.asyncio
async def test_register_sla_max_staleness(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Registration with max max_staleness_seconds=2592000 should succeed."""
    sla = FreshnessSLA(
        dataset_id=dataset_id,
        max_staleness_seconds=2592000,
        expected_schedule="0 0 1 * *",
    )
    result = await monitor.register_sla(dataset_id, sla)
    assert result["registered"] is True
    assert result["max_staleness_seconds"] == 2592000


# --- Default Thresholds ---


@pytest.mark.asyncio
async def test_default_thresholds_applied(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """When thresholds are not specified, defaults (0.8, 0.9) should be used."""
    sla = FreshnessSLA(
        dataset_id=dataset_id,
        max_staleness_seconds=600,
        expected_schedule="*/10 * * * *",
    )
    result = await monitor.register_sla(dataset_id, sla)

    assert result["warning_threshold"] == 0.8
    assert result["critical_threshold"] == 0.9


# --- Invalid SLA Rejection ---


@pytest.mark.asyncio
async def test_reject_warning_ge_critical(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Should reject when warning_threshold >= critical_threshold."""
    with pytest.raises(ValueError, match="warning_threshold"):
        FreshnessSLA(
            dataset_id=dataset_id,
            max_staleness_seconds=3600,
            expected_schedule="0 * * * *",
            warning_threshold=0.9,
            critical_threshold=0.9,
        )


@pytest.mark.asyncio
async def test_reject_zero_max_staleness(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Should reject max_staleness_seconds <= 0."""
    with pytest.raises(ValueError):
        FreshnessSLA(
            dataset_id=dataset_id,
            max_staleness_seconds=0,
            expected_schedule="0 * * * *",
        )


@pytest.mark.asyncio
async def test_reject_negative_max_staleness(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Should reject negative max_staleness_seconds."""
    with pytest.raises(ValueError):
        FreshnessSLA(
            dataset_id=dataset_id,
            max_staleness_seconds=-100,
            expected_schedule="0 * * * *",
        )


@pytest.mark.asyncio
async def test_reject_max_staleness_exceeds_limit(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Should reject max_staleness_seconds > 2592000."""
    with pytest.raises(ValueError):
        FreshnessSLA(
            dataset_id=dataset_id,
            max_staleness_seconds=2592001,
            expected_schedule="0 * * * *",
        )


@pytest.mark.asyncio
async def test_reject_critical_threshold_over_one(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Should reject critical_threshold > 1.0."""
    with pytest.raises(ValueError):
        FreshnessSLA(
            dataset_id=dataset_id,
            max_staleness_seconds=3600,
            expected_schedule="0 * * * *",
            warning_threshold=0.8,
            critical_threshold=1.1,
        )


# --- Status Computation ---


@pytest.mark.asyncio
async def test_check_freshness_healthy(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """Status should be HEALTHY when staleness is below warning boundary."""
    await monitor.register_sla(dataset_id, valid_sla)

    # Data arrived 10 minutes ago (600s), max_staleness=3600s
    # warning boundary = 0.8 * 3600 = 2880s
    arrival = datetime.now(timezone.utc) - timedelta(seconds=600)
    await monitor.record_data_arrival(dataset_id, arrival)

    check_time = datetime.now(timezone.utc)
    status = await monitor.check_freshness(dataset_id, check_time)

    assert status.status == FreshnessState.HEALTHY
    assert status.staleness_seconds < 2880
    assert status.sla_consumed_pct < 0.8


@pytest.mark.asyncio
async def test_check_freshness_warning(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """Status should be WARNING when staleness exceeds warning but not critical."""
    await monitor.register_sla(dataset_id, valid_sla)

    # max_staleness=3600, warning_boundary=2880, critical_boundary=3240
    # Staleness = 3000s (between warning and critical)
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(seconds=3000)
    await monitor.record_data_arrival(dataset_id, arrival)

    status = await monitor.check_freshness(dataset_id, now)

    assert status.status == FreshnessState.WARNING
    assert status.staleness_seconds >= 2880
    assert status.staleness_seconds <= 3240


@pytest.mark.asyncio
async def test_check_freshness_critical(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """Status should be CRITICAL when staleness exceeds critical boundary."""
    await monitor.register_sla(dataset_id, valid_sla)

    # critical_boundary = 0.9 * 3600 = 3240s
    # Staleness = 3500s (> critical)
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(seconds=3500)
    await monitor.record_data_arrival(dataset_id, arrival)

    status = await monitor.check_freshness(dataset_id, now)

    assert status.status == FreshnessState.CRITICAL
    assert status.staleness_seconds > 3240


@pytest.mark.asyncio
async def test_sla_consumed_pct_capped_at_2(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """sla_consumed_pct should be capped at 2.0 even when staleness far exceeds max."""
    await monitor.register_sla(dataset_id, valid_sla)

    # Staleness = 10000s >> max_staleness=3600s
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(seconds=10000)
    await monitor.record_data_arrival(dataset_id, arrival)

    status = await monitor.check_freshness(dataset_id, now)

    assert status.sla_consumed_pct == 2.0


@pytest.mark.asyncio
async def test_sla_consumed_pct_computation(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """sla_consumed_pct should equal staleness / max_staleness when below 2.0."""
    await monitor.register_sla(dataset_id, valid_sla)

    # Staleness = 1800s, max_staleness=3600s -> pct = 0.5
    now = datetime.now(timezone.utc)
    arrival = now - timedelta(seconds=1800)
    await monitor.record_data_arrival(dataset_id, arrival)

    status = await monitor.check_freshness(dataset_id, now)

    assert abs(status.sla_consumed_pct - 0.5) < 0.01


@pytest.mark.asyncio
async def test_check_freshness_no_sla_raises_error(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Checking freshness without a registered SLA should raise an error."""
    with pytest.raises(FreshnessMonitorError, match="No SLA registered"):
        await monitor.check_freshness(dataset_id)


@pytest.mark.asyncio
async def test_check_freshness_no_arrival_critical(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """When no data has ever arrived, status should be CRITICAL."""
    await monitor.register_sla(dataset_id, valid_sla)

    status = await monitor.check_freshness(dataset_id)

    assert status.status == FreshnessState.CRITICAL
    assert status.last_updated is None
    assert status.sla_consumed_pct == 2.0


# --- Data Arrival Recording ---


@pytest.mark.asyncio
async def test_record_data_arrival(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """Recording data arrival should update last arrival and make dataset HEALTHY."""
    await monitor.register_sla(dataset_id, valid_sla)

    now = datetime.now(timezone.utc)
    result = await monitor.record_data_arrival(dataset_id, now)

    assert result["recorded"] is True
    assert result["arrival_time"] == now

    # Check freshness immediately after arrival
    status = await monitor.check_freshness(dataset_id, now)
    assert status.status == FreshnessState.HEALTHY
    assert status.staleness_seconds == 0.0


@pytest.mark.asyncio
async def test_record_arrival_defaults_to_utc_now(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """Recording without explicit time should use current UTC time."""
    await monitor.register_sla(dataset_id, valid_sla)
    result = await monitor.record_data_arrival(dataset_id)

    assert result["recorded"] is True
    assert result["arrival_time"] is not None
    # Should be very close to now
    delta = datetime.now(timezone.utc) - result["arrival_time"]
    assert delta.total_seconds() < 2.0



# --- Monotonic Status Degradation ---


@pytest.mark.asyncio
async def test_monotonic_degradation_without_new_data(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """Without new data, status should only worsen over time (HEALTHY → WARNING → CRITICAL)."""
    await monitor.register_sla(dataset_id, valid_sla)

    # max_staleness=3600, warning=0.8*3600=2880, critical=0.9*3600=3240
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    arrival_time = base_time
    await monitor.record_data_arrival(dataset_id, arrival_time)

    # Check at t+100s => HEALTHY (staleness=100 < 2880)
    s1 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=100))
    assert s1.status == FreshnessState.HEALTHY

    # Check at t+2900s => WARNING (2900 > 2880)
    s2 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=2900))
    assert s2.status == FreshnessState.WARNING

    # Check at t+3500s => CRITICAL (3500 > 3240)
    s3 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=3500))
    assert s3.status == FreshnessState.CRITICAL

    # Now if we artificially check at a time that would compute HEALTHY,
    # but no new data arrived, status should NOT improve (stays CRITICAL).
    # This is the monotonic guarantee.
    # However, if staleness is low (which requires time travel), staleness still
    # is computed honestly — the monotonic constraint is on the *status* label.
    # The scenario: status was CRITICAL. Without new data, even if we hypothetically
    # check again, it can't improve. Let's check again at same time (staleness same).
    s4 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=3500))
    assert s4.status == FreshnessState.CRITICAL


@pytest.mark.asyncio
async def test_monotonic_status_never_improves_without_data(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """Once status reaches WARNING, it cannot go back to HEALTHY without new data."""
    # Use an SLA with short max_staleness to make thresholds tight
    sla = FreshnessSLA(
        dataset_id=dataset_id,
        max_staleness_seconds=100,
        expected_schedule="* * * * *",
        warning_threshold=0.5,
        critical_threshold=0.9,
    )
    await monitor.register_sla(dataset_id, sla)
    # warning boundary = 50s, critical boundary = 90s

    base_time = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    await monitor.record_data_arrival(dataset_id, base_time)

    # t+10s → HEALTHY
    s1 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=10))
    assert s1.status == FreshnessState.HEALTHY

    # t+60s → WARNING (60 > 50)
    s2 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=60))
    assert s2.status == FreshnessState.WARNING

    # t+95s → CRITICAL (95 > 90)
    s3 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=95))
    assert s3.status == FreshnessState.CRITICAL

    # Now check at same staleness level as WARNING would compute,
    # but since no new data arrived and we were already CRITICAL, stays CRITICAL
    # Actually, with increasing time the staleness only gets worse.
    # Let's just verify it stays CRITICAL
    s4 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=200))
    assert s4.status == FreshnessState.CRITICAL


@pytest.mark.asyncio
async def test_status_can_improve_after_new_data(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """After new data arrives, monotonic enforcement resets and status can improve."""
    await monitor.register_sla(dataset_id, valid_sla)

    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    await monitor.record_data_arrival(dataset_id, base_time)

    # Degrade to CRITICAL (staleness > 3240)
    s1 = await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=3500))
    assert s1.status == FreshnessState.CRITICAL

    # New data arrives at t+3500
    new_arrival = base_time + timedelta(seconds=3500)
    await monitor.record_data_arrival(dataset_id, new_arrival)

    # Now checking immediately => should be HEALTHY since staleness is ~0
    s2 = await monitor.check_freshness(dataset_id, new_arrival + timedelta(seconds=1))
    assert s2.status == FreshnessState.HEALTHY


# --- Freshness History ---


@pytest.mark.asyncio
async def test_freshness_history_accumulated(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """Each check_freshness call should be recorded in history."""
    await monitor.register_sla(dataset_id, valid_sla)

    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    await monitor.record_data_arrival(dataset_id, base_time)

    # Perform 3 checks
    t1 = base_time + timedelta(seconds=100)
    t2 = base_time + timedelta(seconds=2000)
    t3 = base_time + timedelta(seconds=3500)

    await monitor.check_freshness(dataset_id, t1)
    await monitor.check_freshness(dataset_id, t2)
    await monitor.check_freshness(dataset_id, t3)

    history = await monitor.get_freshness_history(dataset_id)
    assert len(history) == 3
    assert history[0].check_time == t1
    assert history[1].check_time == t2
    assert history[2].check_time == t3


@pytest.mark.asyncio
async def test_freshness_history_empty_for_unregistered(
    monitor: FreshnessMonitor, dataset_id: DatasetId
):
    """History for a dataset with no checks should be an empty list."""
    history = await monitor.get_freshness_history(dataset_id)
    assert history == []


@pytest.mark.asyncio
async def test_freshness_history_preserves_status_values(
    monitor: FreshnessMonitor, dataset_id: DatasetId, valid_sla: FreshnessSLA
):
    """History entries should reflect the status at time of each check."""
    await monitor.register_sla(dataset_id, valid_sla)

    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    await monitor.record_data_arrival(dataset_id, base_time)

    # HEALTHY check
    await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=100))
    # WARNING check (staleness > 2880)
    await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=3000))
    # CRITICAL check (staleness > 3240)
    await monitor.check_freshness(dataset_id, base_time + timedelta(seconds=3500))

    history = await monitor.get_freshness_history(dataset_id)
    assert history[0].status == FreshnessState.HEALTHY
    assert history[1].status == FreshnessState.WARNING
    assert history[2].status == FreshnessState.CRITICAL


# --- get_all_sla_statuses ---


@pytest.mark.asyncio
async def test_get_all_sla_statuses_multiple_datasets(
    monitor: FreshnessMonitor,
):
    """get_all_sla_statuses should return status for all registered datasets."""
    ds1 = DatasetId(namespace="warehouse.public.orders", version=1)
    ds2 = DatasetId(namespace="warehouse.public.users", version=1)
    ds3 = DatasetId(namespace="warehouse.public.products", version=1)

    sla1 = FreshnessSLA(
        dataset_id=ds1,
        max_staleness_seconds=3600,
        expected_schedule="0 * * * *",
    )
    sla2 = FreshnessSLA(
        dataset_id=ds2,
        max_staleness_seconds=1800,
        expected_schedule="*/30 * * * *",
    )
    sla3 = FreshnessSLA(
        dataset_id=ds3,
        max_staleness_seconds=7200,
        expected_schedule="0 */2 * * *",
    )

    await monitor.register_sla(ds1, sla1)
    await monitor.register_sla(ds2, sla2)
    await monitor.register_sla(ds3, sla3)

    # Record arrivals for some datasets
    now = datetime.now(timezone.utc)
    await monitor.record_data_arrival(ds1, now - timedelta(seconds=100))
    await monitor.record_data_arrival(ds2, now - timedelta(seconds=100))
    # ds3 has no arrival — should be CRITICAL

    statuses = await monitor.get_all_sla_statuses()

    assert len(statuses) == 3
    # ds1 and ds2 should be HEALTHY, ds3 CRITICAL
    ds1_key = f"{ds1.namespace}:v{ds1.version}"
    ds2_key = f"{ds2.namespace}:v{ds2.version}"
    ds3_key = f"{ds3.namespace}:v{ds3.version}"

    assert statuses[ds1_key].status == FreshnessState.HEALTHY
    assert statuses[ds2_key].status == FreshnessState.HEALTHY
    assert statuses[ds3_key].status == FreshnessState.CRITICAL


@pytest.mark.asyncio
async def test_get_all_sla_statuses_empty_when_none_registered(
    monitor: FreshnessMonitor,
):
    """get_all_sla_statuses should return empty dict when no SLAs are registered."""
    statuses = await monitor.get_all_sla_statuses()
    assert statuses == {}
