"""Anomaly Detection Engine using KS-test and KL-divergence.

Implements statistical anomaly detection by comparing current data profiles
against a rolling 30-day baseline. Uses two-sample Kolmogorov-Smirnov test
and KL-divergence to detect distribution shifts with adaptive thresholds.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import numpy as np
from scipy.stats import ks_2samp

from data_quality_engine.models.anomaly import (
    AdaptiveThreshold,
    AnomalyCategory,
    AnomalyEvent,
)
from data_quality_engine.models.base import DatasetId
from data_quality_engine.models.drift import DriftSeverity
from data_quality_engine.models.profile import ColumnProfile, DataProfile

logger = logging.getLogger(__name__)

# Default static thresholds (used until adaptive thresholds are computed)
_DEFAULT_KS_THRESHOLD = 0.15
_DEFAULT_KL_THRESHOLD = 0.5

# Minimum baseline profiles before alert emission
_MIN_BASELINE_FOR_ALERTS = 7

# Maximum baseline profiles for rolling window
_MAX_BASELINE_PROFILES = 30

# Baseline profiles needed for maximum confidence
_MAX_CONFIDENCE_BASELINE_COUNT = 30

# Rolling window duration in days
_BASELINE_WINDOW_DAYS = 30


class AnomalyDetectionEngine:
    """Multi-algorithm statistical anomaly detection engine.

    Detects distribution shifts by comparing current data profiles against a
    rolling 30-day baseline using:
    - Two-sample Kolmogorov-Smirnov test (scipy.stats.ks_2samp)
    - KL-divergence for distributional distance measurement

    Manages rolling baselines per dataset, supports adaptive thresholds,
    and emits AnomalyEvent instances when anomalies are detected.
    """

    def __init__(
        self,
        ks_threshold: float = _DEFAULT_KS_THRESHOLD,
        kl_threshold: float = _DEFAULT_KL_THRESHOLD,
    ) -> None:
        """Initialize the anomaly detection engine.

        Args:
            ks_threshold: Static threshold for KS-test statistic (default 0.15).
            kl_threshold: Static threshold for KL-divergence (default 0.5).
        """
        self._ks_threshold = ks_threshold
        self._kl_threshold = kl_threshold
        # In-memory baselines: dataset_id namespace -> list of (profiled_at, DataProfile)
        self._baselines: dict[str, list[tuple[datetime, DataProfile]]] = {}
        # Adaptive thresholds per dataset/column
        self._adaptive_thresholds: dict[str, AdaptiveThreshold] = {}

    def _get_baseline_key(self, dataset_id: DatasetId) -> str:
        """Generate a storage key for baseline lookups."""
        return f"{dataset_id.namespace}:v{dataset_id.version}"

    def _get_ks_threshold(self, dataset_id: DatasetId, column_name: str) -> float:
        """Get the effective KS-test threshold for a column.

        Returns adaptive threshold if available, otherwise the static default.
        """
        key = f"{self._get_baseline_key(dataset_id)}:{column_name}:ks"
        if key in self._adaptive_thresholds:
            thresholds = self._adaptive_thresholds[key].thresholds
            if "ks_threshold" in thresholds:
                return thresholds["ks_threshold"]
        return self._ks_threshold

    def _get_kl_threshold(self, dataset_id: DatasetId, column_name: str) -> float:
        """Get the effective KL-divergence threshold for a column.

        Returns adaptive threshold if available, otherwise the static default.
        """
        key = f"{self._get_baseline_key(dataset_id)}:{column_name}:kl"
        if key in self._adaptive_thresholds:
            thresholds = self._adaptive_thresholds[key].thresholds
            if "kl_threshold" in thresholds:
                return thresholds["kl_threshold"]
        return self._kl_threshold

    def _compute_confidence(self, baseline_count: int) -> float:
        """Compute detection confidence based on baseline size.

        Confidence scales linearly from 0.0 to 1.0 with baseline count,
        reaching maximum at 30+ profiles.

        Args:
            baseline_count: Number of profiles in the baseline.

        Returns:
            Confidence value in [0.0, 1.0].
        """
        if baseline_count <= 0:
            return 0.0
        confidence = min(1.0, baseline_count / _MAX_CONFIDENCE_BASELINE_COUNT)
        return max(0.0, min(1.0, confidence))

    def _compute_anomaly_score(self, ks_statistic: float, threshold: float) -> float:
        """Compute bounded anomaly score from KS-statistic.

        Score is min(1.0, ks_statistic / threshold), bounded in [0.0, 1.0].

        Args:
            ks_statistic: The KS-test statistic value.
            threshold: The threshold used for comparison.

        Returns:
            Anomaly score in [0.0, 1.0].
        """
        if threshold <= 0:
            return 1.0
        score = ks_statistic / threshold
        return max(0.0, min(1.0, score))

    def _compute_kl_anomaly_score(self, kl_divergence: float, threshold: float) -> float:
        """Compute bounded anomaly score from KL-divergence.

        Score is min(1.0, kl_divergence / threshold), bounded in [0.0, 1.0].

        Args:
            kl_divergence: The KL-divergence value.
            threshold: The threshold used for comparison.

        Returns:
            Anomaly score in [0.0, 1.0].
        """
        if threshold <= 0:
            return 1.0
        score = kl_divergence / threshold
        return max(0.0, min(1.0, score))

    def _extract_histogram_values(self, profile: ColumnProfile) -> np.ndarray | None:
        """Extract representative values from a column profile's histogram.

        Reconstructs a sample array from histogram bucket midpoints and counts
        for use with ks_2samp. Returns None if histogram is unavailable or empty.
        """
        if profile.histogram is None or len(profile.histogram) == 0:
            return None

        values = []
        for bucket in profile.histogram:
            midpoint = (bucket.lower_bound + bucket.upper_bound) / 2.0
            values.extend([midpoint] * bucket.count)

        if len(values) == 0:
            return None

        return np.array(values, dtype=np.float64)

    def _compute_kl_divergence(
        self, current_profile: ColumnProfile, baseline_profile: ColumnProfile
    ) -> float | None:
        """Compute KL-divergence between two histogram distributions.

        Uses the histograms from the column profiles. Applies Laplace smoothing
        to avoid division by zero / log of zero.

        Args:
            current_profile: The current column profile.
            baseline_profile: A baseline column profile to compare against.

        Returns:
            KL-divergence value, or None if computation is not possible.
        """
        if (
            current_profile.histogram is None
            or baseline_profile.histogram is None
            or len(current_profile.histogram) == 0
            or len(baseline_profile.histogram) == 0
        ):
            return None

        # Extract counts from histograms
        current_counts = np.array(
            [b.count for b in current_profile.histogram], dtype=np.float64
        )
        baseline_counts = np.array(
            [b.count for b in baseline_profile.histogram], dtype=np.float64
        )

        # Align histograms by padding the shorter one with zeros
        max_len = max(len(current_counts), len(baseline_counts))
        if len(current_counts) < max_len:
            current_counts = np.pad(
                current_counts, (0, max_len - len(current_counts))
            )
        if len(baseline_counts) < max_len:
            baseline_counts = np.pad(
                baseline_counts, (0, max_len - len(baseline_counts))
            )

        # Convert counts to probability distributions with Laplace smoothing
        epsilon = 1e-10
        current_total = current_counts.sum()
        baseline_total = baseline_counts.sum()

        if current_total == 0 or baseline_total == 0:
            return None

        p = current_counts / current_total + epsilon
        q = baseline_counts / baseline_total + epsilon

        # Normalize after smoothing
        p = p / p.sum()
        q = q / q.sum()

        # Compute KL(P || Q)
        kl_div = float(np.sum(p * np.log(p / q)))

        # KL-divergence should be non-negative
        return max(0.0, kl_div)

    def _run_ks_test(
        self,
        current_profile: ColumnProfile,
        baseline_profiles: list[ColumnProfile],
    ) -> tuple[float, float] | None:
        """Run two-sample KS-test comparing current profile against baseline.

        Combines all baseline histogram values into a single sample and runs
        scipy.stats.ks_2samp against the current profile's histogram values.

        Args:
            current_profile: Current column profile.
            baseline_profiles: Historical baseline profiles for the same column.

        Returns:
            Tuple of (ks_statistic, p_value) or None if test cannot be run.
        """
        current_values = self._extract_histogram_values(current_profile)
        if current_values is None or len(current_values) < 2:
            return None

        # Combine baseline histograms into a single reference sample
        baseline_values_list = []
        for bp in baseline_profiles:
            bv = self._extract_histogram_values(bp)
            if bv is not None:
                baseline_values_list.append(bv)

        if not baseline_values_list:
            return None

        baseline_combined = np.concatenate(baseline_values_list)
        if len(baseline_combined) < 2:
            return None

        # Run two-sample KS test
        statistic, p_value = ks_2samp(current_values, baseline_combined)
        return float(statistic), float(p_value)

    def detect_anomalies(
        self, current_profile: DataProfile, dataset_id: DatasetId
    ) -> list[AnomalyEvent]:
        """Detect anomalies by comparing current profile to baseline.

        Applies KS-test and KL-divergence to each column that has a histogram.
        Emits AnomalyEvent for columns where:
        - KS-statistic exceeds threshold AND p-value < 0.05
        - KL-divergence exceeds threshold

        Suppresses alert emission when baseline has fewer than 7 profiles.
        Skips algorithms on numerical error and continues with remaining.

        Args:
            current_profile: The current data profile to evaluate.
            dataset_id: Identifier for the dataset being checked.

        Returns:
            List of detected AnomalyEvent instances (empty if no anomalies
            or if baseline is insufficient).
        """
        baseline_key = self._get_baseline_key(dataset_id)
        baseline_entries = self._baselines.get(baseline_key, [])
        baseline_count = len(baseline_entries)

        # Check if we have enough baseline data
        if baseline_count < _MIN_BASELINE_FOR_ALERTS:
            logger.info(
                "Insufficient baseline for dataset %s: %d profiles "
                "(minimum %d required). Suppressing anomaly alerts.",
                dataset_id.namespace,
                baseline_count,
                _MIN_BASELINE_FOR_ALERTS,
            )
            return []

        # Extract baseline DataProfiles
        baseline_profiles = [entry[1] for entry in baseline_entries]
        confidence = self._compute_confidence(baseline_count)
        anomalies: list[AnomalyEvent] = []
        now = datetime.now(timezone.utc)

        # Evaluate each column in the current profile
        for col_name, current_col_profile in current_profile.column_profiles.items():
            # Collect matching baseline column profiles
            baseline_col_profiles = []
            for bp in baseline_profiles:
                if col_name in bp.column_profiles:
                    baseline_col_profiles.append(bp.column_profiles[col_name])

            if not baseline_col_profiles:
                continue

            # --- KS-test ---
            ks_threshold = self._get_ks_threshold(dataset_id, col_name)
            try:
                ks_result = self._run_ks_test(current_col_profile, baseline_col_profiles)
                if ks_result is not None:
                    ks_statistic, p_value = ks_result
                    if ks_statistic > ks_threshold and p_value < 0.05:
                        anomaly_score = self._compute_anomaly_score(
                            ks_statistic, ks_threshold
                        )
                        # Compute expected value from baseline means
                        baseline_means = [
                            bp.mean for bp in baseline_col_profiles
                            if bp.mean is not None
                        ]
                        expected_value = (
                            float(np.mean(baseline_means))
                            if baseline_means
                            else 0.0
                        )
                        observed_value = (
                            current_col_profile.mean
                            if current_col_profile.mean is not None
                            else 0.0
                        )

                        anomalies.append(
                            AnomalyEvent(
                                anomaly_id=uuid4(),
                                dataset_id=dataset_id,
                                column_name=col_name,
                                category=AnomalyCategory.DISTRIBUTION_SHIFT,
                                severity=self._classify_severity(anomaly_score),
                                detected_at=now,
                                anomaly_score=anomaly_score,
                                confidence=confidence,
                                metric_name="ks_statistic",
                                observed_value=ks_statistic,
                                expected_value=ks_threshold,
                                expected_range=(0.0, ks_threshold),
                                description=(
                                    f"Distribution shift detected in column '{col_name}': "
                                    f"KS-statistic={ks_statistic:.4f} exceeds threshold "
                                    f"{ks_threshold:.4f} (p-value={p_value:.6f})"
                                ),
                                context={
                                    "ks_statistic": ks_statistic,
                                    "p_value": p_value,
                                    "adaptive_threshold": ks_threshold,
                                    "anomaly_score": anomaly_score,
                                    "algorithm": "ks_test",
                                },
                            )
                        )
            except (ValueError, FloatingPointError, RuntimeError) as exc:
                logger.warning(
                    "Numerical error in KS-test for column '%s' in dataset %s: %s. "
                    "Skipping KS-test and continuing with remaining algorithms.",
                    col_name,
                    dataset_id.namespace,
                    str(exc),
                )

            # --- KL-divergence ---
            kl_threshold = self._get_kl_threshold(dataset_id, col_name)
            try:
                # Compute KL-divergence against each baseline profile and take the max
                max_kl_div = 0.0
                kl_computed = False
                for bp_col in baseline_col_profiles:
                    kl_div = self._compute_kl_divergence(current_col_profile, bp_col)
                    if kl_div is not None:
                        max_kl_div = max(max_kl_div, kl_div)
                        kl_computed = True

                if kl_computed and max_kl_div > kl_threshold:
                    anomaly_score = self._compute_kl_anomaly_score(
                        max_kl_div, kl_threshold
                    )
                    anomalies.append(
                        AnomalyEvent(
                            anomaly_id=uuid4(),
                            dataset_id=dataset_id,
                            column_name=col_name,
                            category=AnomalyCategory.DISTRIBUTION_SHIFT,
                            severity=self._classify_severity(anomaly_score),
                            detected_at=now,
                            anomaly_score=anomaly_score,
                            confidence=confidence,
                            metric_name="kl_divergence",
                            observed_value=max_kl_div,
                            expected_value=kl_threshold,
                            expected_range=(0.0, kl_threshold),
                            description=(
                                f"Distribution shift detected in column '{col_name}': "
                                f"KL-divergence={max_kl_div:.4f} exceeds threshold "
                                f"{kl_threshold:.4f}"
                            ),
                            context={
                                "kl_divergence": max_kl_div,
                                "adaptive_threshold": kl_threshold,
                                "anomaly_score": anomaly_score,
                                "algorithm": "kl_divergence",
                            },
                        )
                    )
            except (ValueError, FloatingPointError, RuntimeError) as exc:
                logger.warning(
                    "Numerical error in KL-divergence for column '%s' in dataset %s: %s. "
                    "Skipping KL-divergence and continuing.",
                    col_name,
                    dataset_id.namespace,
                    str(exc),
                )

        return anomalies

    def update_baseline(
        self, dataset_id: DatasetId, profile: DataProfile
    ) -> None:
        """Incorporate a non-anomalous profile into the rolling 30-day baseline.

        Evicts profiles older than 30 days from the baseline.

        Args:
            dataset_id: The dataset identifier.
            profile: The profile to add to the baseline.
        """
        baseline_key = self._get_baseline_key(dataset_id)

        if baseline_key not in self._baselines:
            self._baselines[baseline_key] = []

        # Add the new profile
        self._baselines[baseline_key].append((profile.profiled_at, profile))

        # Evict profiles older than 30 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=_BASELINE_WINDOW_DAYS)
        self._baselines[baseline_key] = [
            (ts, p)
            for ts, p in self._baselines[baseline_key]
            if ts >= cutoff
        ]

    def get_baseline(self, dataset_id: DatasetId) -> list[DataProfile]:
        """Retrieve current baseline profiles for a dataset.

        Args:
            dataset_id: The dataset identifier.

        Returns:
            List of DataProfile instances in the rolling baseline.
        """
        baseline_key = self._get_baseline_key(dataset_id)
        entries = self._baselines.get(baseline_key, [])
        return [entry[1] for entry in entries]

    def set_adaptive_threshold(
        self,
        dataset_id: DatasetId,
        column_name: str,
        ks_threshold: float | None = None,
        kl_threshold: float | None = None,
    ) -> None:
        """Set adaptive thresholds for a specific column.

        Args:
            dataset_id: The dataset identifier.
            column_name: The column name.
            ks_threshold: Optional KS-test threshold override.
            kl_threshold: Optional KL-divergence threshold override.
        """
        now = datetime.now(timezone.utc)
        if ks_threshold is not None:
            key = f"{self._get_baseline_key(dataset_id)}:{column_name}:ks"
            self._adaptive_thresholds[key] = AdaptiveThreshold(
                column_name=column_name,
                thresholds={"ks_threshold": ks_threshold},
                last_computed=now,
            )
        if kl_threshold is not None:
            key = f"{self._get_baseline_key(dataset_id)}:{column_name}:kl"
            self._adaptive_thresholds[key] = AdaptiveThreshold(
                column_name=column_name,
                thresholds={"kl_threshold": kl_threshold},
                last_computed=now,
            )

    @staticmethod
    def _classify_severity(anomaly_score: float) -> DriftSeverity:
        """Classify drift severity based on anomaly score.

        Args:
            anomaly_score: Anomaly score in [0.0, 1.0].

        Returns:
            DriftSeverity classification.
        """
        if anomaly_score >= 0.8:
            return DriftSeverity.CRITICAL
        elif anomaly_score >= 0.5:
            return DriftSeverity.WARNING
        else:
            return DriftSeverity.INFO
