"""Unit tests for the HealingOrchestrator service.

Tests cover:
- Correct strategy selection based on anomaly_type
- ESCALATE when confidence < 0.5
- ESCALATE after 3 failures of same strategy for same root cause
- Logging of selection events
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from data_quality_engine.models.alert import Alert, AlertSeverity
from data_quality_engine.models.base import DatasetId
from data_quality_engine.models.healing import (
    Diagnosis,
    HealingResult,
    HealingStrategy,
)
from data_quality_engine.services.healing_orchestrator import HealingOrchestrator


@pytest.fixture
def orchestrator() -> HealingOrchestrator:
    """Create a fresh HealingOrchestrator instance."""
    return HealingOrchestrator()


@pytest.fixture
def dataset_id() -> DatasetId:
    """A sample dataset ID."""
    return DatasetId(namespace="warehouse.public.orders", version=1)


def _make_alert(
    dataset_id: DatasetId,
    anomaly_type: str,
    severity: AlertSeverity = AlertSeverity.WARNING,
) -> Alert:
    """Helper to create an Alert with given anomaly_type."""
    return Alert(
        alert_id=uuid4(),
        dataset_id=dataset_id,
        anomaly_type=anomaly_type,
        metric_name="test_metric",
        severity=severity,
        created_at=datetime.now(timezone.utc),
    )


def _make_failed_healing_result(
    strategy: HealingStrategy,
    root_cause: str,
    started_at: datetime | None = None,
) -> HealingResult:
    """Helper to create a failed HealingResult."""
    if started_at is None:
        started_at = datetime.now(timezone.utc)
    return HealingResult(
        healing_id=uuid4(),
        strategy=strategy,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=5),
        success=False,
        records_affected=0,
        details=f"Failed healing for root cause: {root_cause}",
    )


# --- Strategy Selection Based on anomaly_type ---


class TestDiagnoseIssue:
    """Tests for diagnose_issue method."""

    def test_upstream_timeout_selects_auto_retry(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """upstream_timeout anomaly_type should suggest AUTO_RETRY with high confidence."""
        alert = _make_alert(dataset_id, "upstream_timeout")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.suggested_strategy == HealingStrategy.AUTO_RETRY
        assert diagnosis.confidence == 0.8
        assert diagnosis.alert_id == alert.alert_id
        assert diagnosis.root_cause == "upstream_timeout"

    def test_schema_violation_selects_quarantine(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """schema_violation anomaly_type should suggest QUARANTINE with high confidence."""
        alert = _make_alert(dataset_id, "schema_violation")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.suggested_strategy == HealingStrategy.QUARANTINE
        assert diagnosis.confidence == 0.8
        assert diagnosis.root_cause == "schema_violation"

    def test_data_gap_selects_backfill(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """data_gap anomaly_type should suggest BACKFILL with high confidence."""
        alert = _make_alert(dataset_id, "data_gap")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.suggested_strategy == HealingStrategy.BACKFILL
        assert diagnosis.confidence == 0.8
        assert diagnosis.root_cause == "data_gap"

    def test_freshness_breach_selects_backfill(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """freshness_breach anomaly_type should suggest BACKFILL with high confidence."""
        alert = _make_alert(dataset_id, "freshness_breach")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.suggested_strategy == HealingStrategy.BACKFILL
        assert diagnosis.confidence == 0.8
        assert diagnosis.root_cause == "freshness_breach"

    def test_unknown_anomaly_type_selects_escalate(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """Unknown anomaly_type should suggest ESCALATE with low confidence."""
        alert = _make_alert(dataset_id, "some_unknown_issue")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.suggested_strategy == HealingStrategy.ESCALATE
        assert diagnosis.confidence == 0.3
        assert "unknown:" in diagnosis.root_cause

    def test_partial_match_timeout_keyword(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """Anomaly type containing 'timeout' should partially match AUTO_RETRY."""
        alert = _make_alert(dataset_id, "connection_timeout_error")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.suggested_strategy == HealingStrategy.AUTO_RETRY
        assert diagnosis.confidence == 0.6

    def test_partial_match_schema_keyword(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """Anomaly type containing 'schema' should partially match QUARANTINE."""
        alert = _make_alert(dataset_id, "schema_mismatch_detected")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.suggested_strategy == HealingStrategy.QUARANTINE
        assert diagnosis.confidence == 0.6

    def test_diagnosis_includes_alert_id(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """Diagnosis should contain the original alert_id."""
        alert = _make_alert(dataset_id, "upstream_timeout")
        diagnosis = orchestrator.diagnose_issue(alert)

        assert diagnosis.alert_id == alert.alert_id

    def test_confidence_is_bounded(
        self, orchestrator: HealingOrchestrator, dataset_id: DatasetId
    ):
        """Confidence should always be in [0.0, 1.0]."""
        for anomaly_type in [
            "upstream_timeout",
            "schema_violation",
            "data_gap",
            "freshness_breach",
            "some_random_thing",
            "partial_timeout_issue",
        ]:
            alert = _make_alert(dataset_id, anomaly_type)
            diagnosis = orchestrator.diagnose_issue(alert)
            assert 0.0 <= diagnosis.confidence <= 1.0


# --- ESCALATE When Confidence < 0.5 ---


class TestSelectStrategyLowConfidence:
    """Tests for ESCALATE when confidence is below 0.5."""

    def test_escalate_when_confidence_below_threshold(
        self, orchestrator: HealingOrchestrator
    ):
        """Should select ESCALATE when confidence < 0.5 regardless of suggested strategy."""
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="upstream_timeout",
            confidence=0.3,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        strategy = orchestrator.select_strategy(diagnosis, [])
        assert strategy == HealingStrategy.ESCALATE

    def test_escalate_at_confidence_049(self, orchestrator: HealingOrchestrator):
        """Should select ESCALATE at confidence 0.49 (just below threshold)."""
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="schema_violation",
            confidence=0.49,
            suggested_strategy=HealingStrategy.QUARANTINE,
        )
        strategy = orchestrator.select_strategy(diagnosis, [])
        assert strategy == HealingStrategy.ESCALATE

    def test_no_escalate_at_confidence_050(self, orchestrator: HealingOrchestrator):
        """Should NOT escalate when confidence == 0.5 (at boundary)."""
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="upstream_timeout",
            confidence=0.5,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        strategy = orchestrator.select_strategy(diagnosis, [])
        assert strategy == HealingStrategy.AUTO_RETRY

    def test_no_escalate_at_high_confidence(self, orchestrator: HealingOrchestrator):
        """Should NOT escalate when confidence is high."""
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="data_gap",
            confidence=0.8,
            suggested_strategy=HealingStrategy.BACKFILL,
        )
        strategy = orchestrator.select_strategy(diagnosis, [])
        assert strategy == HealingStrategy.BACKFILL


# --- ESCALATE After 3 Failures ---


class TestSelectStrategyFailureEscalation:
    """Tests for ESCALATE when same strategy failed >= 3 times in 24h."""

    def test_escalate_after_three_failures(self, orchestrator: HealingOrchestrator):
        """Should ESCALATE when same strategy failed 3+ times for same root cause in 24h."""
        root_cause = "upstream_timeout"
        now = datetime.now(timezone.utc)

        # Create 3 failed results within the last 24 hours
        history = [
            _make_failed_healing_result(
                HealingStrategy.AUTO_RETRY,
                root_cause,
                started_at=now - timedelta(hours=i + 1),
            )
            for i in range(3)
        ]

        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause=root_cause,
            confidence=0.8,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        strategy = orchestrator.select_strategy(diagnosis, history)
        assert strategy == HealingStrategy.ESCALATE

    def test_no_escalate_with_only_two_failures(
        self, orchestrator: HealingOrchestrator
    ):
        """Should NOT escalate when only 2 failures exist (below threshold)."""
        root_cause = "upstream_timeout"
        now = datetime.now(timezone.utc)

        history = [
            _make_failed_healing_result(
                HealingStrategy.AUTO_RETRY,
                root_cause,
                started_at=now - timedelta(hours=i + 1),
            )
            for i in range(2)
        ]

        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause=root_cause,
            confidence=0.8,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        strategy = orchestrator.select_strategy(diagnosis, history)
        assert strategy == HealingStrategy.AUTO_RETRY

    def test_no_escalate_when_failures_outside_window(
        self, orchestrator: HealingOrchestrator
    ):
        """Should NOT escalate when failures are older than 24 hours."""
        root_cause = "upstream_timeout"
        now = datetime.now(timezone.utc)

        # All failures are > 24 hours old
        history = [
            _make_failed_healing_result(
                HealingStrategy.AUTO_RETRY,
                root_cause,
                started_at=now - timedelta(hours=25 + i),
            )
            for i in range(5)
        ]

        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause=root_cause,
            confidence=0.8,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        strategy = orchestrator.select_strategy(diagnosis, history)
        assert strategy == HealingStrategy.AUTO_RETRY

    def test_no_escalate_when_different_strategy(
        self, orchestrator: HealingOrchestrator
    ):
        """Should NOT escalate when failures are for a different strategy."""
        root_cause = "upstream_timeout"
        now = datetime.now(timezone.utc)

        # Failures are for QUARANTINE, but diagnosis suggests AUTO_RETRY
        history = [
            _make_failed_healing_result(
                HealingStrategy.QUARANTINE,
                root_cause,
                started_at=now - timedelta(hours=i + 1),
            )
            for i in range(5)
        ]

        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause=root_cause,
            confidence=0.8,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        strategy = orchestrator.select_strategy(diagnosis, history)
        assert strategy == HealingStrategy.AUTO_RETRY

    def test_no_escalate_when_different_root_cause(
        self, orchestrator: HealingOrchestrator
    ):
        """Should NOT escalate when failures have a different root cause."""
        now = datetime.now(timezone.utc)

        # Failures are for "schema_violation" root cause
        history = [
            _make_failed_healing_result(
                HealingStrategy.AUTO_RETRY,
                "schema_violation",
                started_at=now - timedelta(hours=i + 1),
            )
            for i in range(5)
        ]

        # Diagnosis is for "upstream_timeout"
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="upstream_timeout",
            confidence=0.8,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        strategy = orchestrator.select_strategy(diagnosis, history)
        assert strategy == HealingStrategy.AUTO_RETRY

    def test_escalate_with_exactly_three_failures(
        self, orchestrator: HealingOrchestrator
    ):
        """Should ESCALATE at exactly 3 failures (boundary condition)."""
        root_cause = "data_gap"
        now = datetime.now(timezone.utc)

        history = [
            _make_failed_healing_result(
                HealingStrategy.BACKFILL,
                root_cause,
                started_at=now - timedelta(hours=1),
            ),
            _make_failed_healing_result(
                HealingStrategy.BACKFILL,
                root_cause,
                started_at=now - timedelta(hours=2),
            ),
            _make_failed_healing_result(
                HealingStrategy.BACKFILL,
                root_cause,
                started_at=now - timedelta(hours=3),
            ),
        ]

        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause=root_cause,
            confidence=0.8,
            suggested_strategy=HealingStrategy.BACKFILL,
        )
        strategy = orchestrator.select_strategy(diagnosis, history)
        assert strategy == HealingStrategy.ESCALATE


# --- Logging of Selection Events ---


class TestSelectionLogging:
    """Tests for strategy selection event logging."""

    def test_selection_event_logged(self, orchestrator: HealingOrchestrator):
        """Strategy selection should log an event with required fields."""
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="upstream_timeout",
            confidence=0.8,
            suggested_strategy=HealingStrategy.AUTO_RETRY,
        )
        orchestrator.select_strategy(diagnosis, [])

        assert len(orchestrator.selection_log) == 1
        event = orchestrator.selection_log[0]
        assert event["alert_id"] == str(diagnosis.alert_id)
        assert event["root_cause"] == "upstream_timeout"
        assert event["confidence"] == 0.8
        assert event["strategy"] == "auto_retry"
        assert "timestamp" in event

    def test_escalate_selection_logged(self, orchestrator: HealingOrchestrator):
        """ESCALATE selection due to low confidence should be logged."""
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="unknown:weird_error",
            confidence=0.3,
            suggested_strategy=HealingStrategy.ESCALATE,
        )
        orchestrator.select_strategy(diagnosis, [])

        assert len(orchestrator.selection_log) == 1
        event = orchestrator.selection_log[0]
        assert event["strategy"] == "escalate"
        assert event["confidence"] == 0.3

    def test_multiple_selections_logged(self, orchestrator: HealingOrchestrator):
        """Multiple selections should accumulate in the log."""
        for i in range(3):
            diagnosis = Diagnosis(
                alert_id=uuid4(),
                root_cause=f"root_cause_{i}",
                confidence=0.8,
                suggested_strategy=HealingStrategy.AUTO_RETRY,
            )
            orchestrator.select_strategy(diagnosis, [])

        assert len(orchestrator.selection_log) == 3

    def test_log_contains_timestamp(self, orchestrator: HealingOrchestrator):
        """Selection events should include a parseable ISO timestamp."""
        diagnosis = Diagnosis(
            alert_id=uuid4(),
            root_cause="data_gap",
            confidence=0.8,
            suggested_strategy=HealingStrategy.BACKFILL,
        )
        orchestrator.select_strategy(diagnosis, [])

        event = orchestrator.selection_log[0]
        # Verify timestamp is a valid ISO format string
        parsed = datetime.fromisoformat(event["timestamp"])
        assert parsed.tzinfo is not None
