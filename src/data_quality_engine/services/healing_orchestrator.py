"""Self-healing orchestrator service.

Coordinates automated remediation actions when quality issues are detected.
Diagnoses root causes from alert context, selects appropriate healing strategies,
and tracks healing history to avoid repeating failed strategies.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from data_quality_engine.models.alert import Alert
from data_quality_engine.models.healing import (
    Diagnosis,
    HealingResult,
    HealingStrategy,
)

logger = logging.getLogger(__name__)


# Anomaly type to strategy mapping
_STRATEGY_MAP: dict[str, HealingStrategy] = {
    "upstream_timeout": HealingStrategy.AUTO_RETRY,
    "schema_violation": HealingStrategy.QUARANTINE,
    "data_gap": HealingStrategy.BACKFILL,
    "freshness_breach": HealingStrategy.BACKFILL,
}

# Confidence levels for anomaly type classification
_HIGH_CONFIDENCE = 0.8  # Clear match to known pattern
_PARTIAL_CONFIDENCE = 0.6  # Partial match
_UNKNOWN_CONFIDENCE = 0.3  # Unknown anomaly type


class HealingOrchestratorError(Exception):
    """Raised when the healing orchestrator encounters an invalid operation."""

    pass


class HealingOrchestrator:
    """Automated remediation for data quality issues.

    Diagnoses root causes from alert context, selects healing strategies
    based on confidence and failure history, and logs all selection events.
    """

    def __init__(self) -> None:
        """Initialize HealingOrchestrator with empty healing history and logs."""
        self._healing_history: list[HealingResult] = []
        self._selection_log: list[dict] = []

    @property
    def healing_history(self) -> list[HealingResult]:
        """Access the internal healing history."""
        return self._healing_history

    @property
    def selection_log(self) -> list[dict]:
        """Access the internal selection event log."""
        return self._selection_log

    def diagnose_issue(self, alert: Alert) -> Diagnosis:
        """Analyze alert context to determine root cause and suggest a healing strategy.

        Classifies the anomaly_type from the alert to determine root cause and
        assigns confidence based on how clearly it maps to a known pattern.

        Args:
            alert: The quality alert to diagnose.

        Returns:
            Diagnosis with root_cause, confidence, suggested_strategy, and alert_id.
        """
        anomaly_type = alert.anomaly_type.lower().strip()

        # Determine strategy and confidence based on anomaly_type
        if anomaly_type in _STRATEGY_MAP:
            suggested_strategy = _STRATEGY_MAP[anomaly_type]
            confidence = _HIGH_CONFIDENCE
        else:
            # Check for partial matches (contains known keywords)
            partial_match = self._find_partial_match(anomaly_type)
            if partial_match is not None:
                suggested_strategy = partial_match
                confidence = _PARTIAL_CONFIDENCE
            else:
                suggested_strategy = HealingStrategy.ESCALATE
                confidence = _UNKNOWN_CONFIDENCE

        root_cause = self._classify_root_cause(anomaly_type)

        return Diagnosis(
            alert_id=alert.alert_id,
            root_cause=root_cause,
            confidence=confidence,
            suggested_strategy=suggested_strategy,
            context={
                "anomaly_type": alert.anomaly_type,
                "dataset_id": alert.dataset_id.namespace,
                "severity": alert.severity.value,
            },
            upstream_failures=[],
        )

    def select_strategy(
        self, diagnosis: Diagnosis, healing_history: list[HealingResult]
    ) -> HealingStrategy:
        """Select the healing strategy based on diagnosis and failure history.

        Rules (applied in order):
        1. ESCALATE when confidence < 0.5
        2. ESCALATE when same strategy failed >= 3 times for same root cause
           in rolling 24-hour window
        3. Otherwise return diagnosis.suggested_strategy

        Logs a selection event with alert_id, root_cause, confidence, strategy,
        and timestamp.

        Args:
            diagnosis: The diagnosis result from diagnose_issue.
            healing_history: List of past healing results to check for repeated failures.

        Returns:
            The selected HealingStrategy.
        """
        now = datetime.now(timezone.utc)

        # Rule 1: ESCALATE when confidence is too low
        if diagnosis.confidence < 0.5:
            selected = HealingStrategy.ESCALATE
            self._log_selection(diagnosis, selected, now)
            return selected

        # Rule 2: ESCALATE when same strategy failed >= 3 times for same root cause
        # in rolling 24-hour window
        suggested = diagnosis.suggested_strategy
        failure_count = self._count_recent_failures(
            strategy=suggested,
            root_cause=diagnosis.root_cause,
            healing_history=healing_history,
            window=timedelta(hours=24),
            now=now,
        )

        if failure_count >= 3:
            selected = HealingStrategy.ESCALATE
            self._log_selection(diagnosis, selected, now)
            return selected

        # Rule 3: Use the suggested strategy
        selected = suggested
        self._log_selection(diagnosis, selected, now)
        return selected

    def record_healing_result(self, result: HealingResult) -> None:
        """Store a healing result in the internal history.

        Args:
            result: The healing result to record.
        """
        self._healing_history.append(result)

    def _count_recent_failures(
        self,
        strategy: HealingStrategy,
        root_cause: str,
        healing_history: list[HealingResult],
        window: timedelta,
        now: datetime,
    ) -> int:
        """Count failures for a given strategy and root cause within a time window.

        Args:
            strategy: The strategy to check failures for.
            root_cause: The root cause classification to match.
            healing_history: The healing history to search.
            window: The rolling time window.
            now: Current time for window calculation.

        Returns:
            Count of failed healing attempts matching criteria within the window.
        """
        cutoff = now - window
        count = 0
        for result in healing_history:
            if (
                result.strategy == strategy
                and not result.success
                and result.started_at >= cutoff
                and root_cause in result.details
            ):
                count += 1
        return count

    def _log_selection(
        self, diagnosis: Diagnosis, strategy: HealingStrategy, timestamp: datetime
    ) -> None:
        """Log a strategy selection event.

        Args:
            diagnosis: The diagnosis that led to this selection.
            strategy: The selected strategy.
            timestamp: When the selection was made.
        """
        event = {
            "alert_id": str(diagnosis.alert_id),
            "root_cause": diagnosis.root_cause,
            "confidence": diagnosis.confidence,
            "strategy": strategy.value,
            "timestamp": timestamp.isoformat(),
        }
        self._selection_log.append(event)
        logger.info(
            "Healing strategy selected: alert_id=%s root_cause=%s "
            "confidence=%.2f strategy=%s",
            diagnosis.alert_id,
            diagnosis.root_cause,
            diagnosis.confidence,
            strategy.value,
        )

    def _find_partial_match(self, anomaly_type: str) -> HealingStrategy | None:
        """Check if anomaly_type partially matches known patterns.

        Args:
            anomaly_type: The normalized anomaly type string.

        Returns:
            The matching HealingStrategy or None if no partial match found.
        """
        partial_keywords = {
            "timeout": HealingStrategy.AUTO_RETRY,
            "schema": HealingStrategy.QUARANTINE,
            "gap": HealingStrategy.BACKFILL,
            "freshness": HealingStrategy.BACKFILL,
        }
        for keyword, strategy in partial_keywords.items():
            if keyword in anomaly_type:
                return strategy
        return None

    def _classify_root_cause(self, anomaly_type: str) -> str:
        """Classify the root cause from an anomaly type.

        Args:
            anomaly_type: The normalized anomaly type string.

        Returns:
            A human-readable root cause classification string.
        """
        if anomaly_type == "upstream_timeout":
            return "upstream_timeout"
        elif anomaly_type == "schema_violation":
            return "schema_violation"
        elif anomaly_type in ("data_gap", "freshness_breach"):
            return anomaly_type
        else:
            return f"unknown:{anomaly_type}"
