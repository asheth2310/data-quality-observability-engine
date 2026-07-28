"""Unit tests for the Anomaly Detection Engine service."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import numpy as np
import pytest

from data_quality_engine.models.anomaly import AnomalyCategory, AnomalyEvent
from data_quality_engine.models.base import ColumnType, DatasetId
from data_quality_engine.models.drift import DriftSeverity
from data_quality_engine.models.profile import (
    ColumnProfile,
    DataProfile,
    HistogramBucket,
)
from data_quality_engine.services.anomaly_detector import (
    AnomalyDetectionEngine,
    _DEFAULT_KL_THRESHOLD,
    _DEFAULT_KS_THRESHOLD,
    _MAX_BASELINE_PROFILES,
    _MIN_BASELINE_FOR_ALERTS,
)


@pytest.fixture
def engine() -> AnomalyDetectionEngine:
    """Create an AnomalyDetectionEngine with default thresholds."""
    return AnomalyDetectionEngine()


@pytest.fixture
def dataset_id() -> DatasetId:
    """Create a test dataset ID."""
    return DatasetId(namespace="warehouse.public.sales", version=1)


def _make_histogram(values: list[float], num_bins: int = 10) -> list[HistogramBucket]:
    """Helper to create a histogram from raw values."""
    arr = np.array(values, dtype=np.float64)
    counts, bin_edges = np.histogram(arr, bins=num_bins)
    buckets = []
    for i in range(len(counts)):
        buckets.append(
            HistogramBucket(
                lower_bound=float(bin_edges[i]),
                upper_bound=float(bin_edges[i + 1]),
                count=int(counts[i]),
            )
        )
    return buckets


def _make_column_profile(
    column_name: str,
    values: list[float],
    num_bins: int = 10,
) -> ColumnProfile:
    """Helper to create a ColumnProfile with histogram from raw values."""
    arr = np.array(values, dtype=np.float64)
    return ColumnProfile(
        column_name=column_name,
        dtype=ColumnType.FLOAT,
        total_count=len(values),
        null_count=0,
        distinct_count=len(set(values)),
        mean=float(np.mean(arr)),
        std_dev=float(np.std(arr, ddof=1)) if len(arr) > 1 else None,
        min_val=float(np.min(arr)),
        max_val=float(np.max(arr)),
        histogram=_make_histogram(values, num_bins),
    )


def _make_data_profile(
    dataset_id: DatasetId,
    column_profiles: dict[str, ColumnProfile],
    profiled_at: datetime | None = None,
) -> DataProfile:
    """Helper to create a DataProfile."""
    if profiled_at is None:
        profiled_at = datetime.now(timezone.utc)
    row_count = 0
    if column_profiles:
        first_col = next(iter(column_profiles.values()))
        row_count = first_col.total_count
    return DataProfile(
        dataset_id=dataset_id,
        partition_key="2024-01-15",
        row_count=row_count,
        column_profiles=column_profiles,
        profiled_at=profiled_at,
        profiling_duration_ms=10,
    )


def _populate_baseline(
    engine: AnomalyDetectionEngine,
    dataset_id: DatasetId,
    num_profiles: int = 10,
    base_mean: float = 50.0,
    std: float = 10.0,
    col_name: str = "amount",
) -> None:
    """Populate the engine baseline with normal distribution profiles."""
    rng = np.random.default_rng(seed=42)
    for i in range(num_profiles):
        values = rng.normal(base_mean, std, size=200).tolist()
        col_profile = _make_column_profile(col_name, values)
        profiled_at = datetime.now(timezone.utc) - timedelta(days=num_profiles - i)
        profile = _make_data_profile(
            dataset_id,
            {col_name: col_profile},
            profiled_at=profiled_at,
        )
        engine.update_baseline(dataset_id, profile)


class TestDetectAnomaliesBaseline:
    """Tests for baseline-related behavior."""

    def test_suppresses_alerts_when_baseline_insufficient(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Alerts are suppressed when fewer than 7 baseline profiles exist."""
        # Add only 5 profiles (below minimum)
        _populate_baseline(engine, dataset_id, num_profiles=5)

        # Create a wildly different current profile
        rng = np.random.default_rng(seed=99)
        values = rng.normal(200.0, 5.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine.detect_anomalies(current, dataset_id)
        assert anomalies == []

    def test_emits_alerts_when_baseline_sufficient(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Alerts are emitted when baseline has 7+ profiles and anomaly present."""
        _populate_baseline(engine, dataset_id, num_profiles=10)

        # Create a significantly shifted current profile
        rng = np.random.default_rng(seed=99)
        values = rng.normal(200.0, 5.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine.detect_anomalies(current, dataset_id)
        assert len(anomalies) > 0

    def test_no_anomaly_for_similar_distribution(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """No anomaly when current profile is similar to baseline with relaxed threshold."""
        # Use a higher threshold so that minor histogram quantization noise won't trigger
        engine_relaxed = AnomalyDetectionEngine(ks_threshold=0.3, kl_threshold=1.0)
        _populate_baseline(engine_relaxed, dataset_id, num_profiles=10, base_mean=50.0, std=10.0)

        # Current is from the same distribution
        rng = np.random.default_rng(seed=123)
        values = rng.normal(50.0, 10.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine_relaxed.detect_anomalies(current, dataset_id)
        # Should have no KS-test anomaly (similar distribution)
        ks_anomalies = [a for a in anomalies if a.context.get("algorithm") == "ks_test"]
        assert len(ks_anomalies) == 0


class TestKSTestDetection:
    """Tests for KS-test based anomaly detection."""

    def test_ks_anomaly_has_correct_category(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """KS-test anomalies have DISTRIBUTION_SHIFT category."""
        _populate_baseline(engine, dataset_id, num_profiles=10)

        rng = np.random.default_rng(seed=99)
        values = rng.normal(200.0, 5.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine.detect_anomalies(current, dataset_id)
        ks_anomalies = [a for a in anomalies if a.context.get("algorithm") == "ks_test"]
        for anomaly in ks_anomalies:
            assert anomaly.category == AnomalyCategory.DISTRIBUTION_SHIFT

    def test_ks_anomaly_includes_context(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """KS-test anomalies include ks_statistic, p_value, and threshold in context."""
        _populate_baseline(engine, dataset_id, num_profiles=10)

        rng = np.random.default_rng(seed=99)
        values = rng.normal(200.0, 5.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine.detect_anomalies(current, dataset_id)
        ks_anomalies = [a for a in anomalies if a.context.get("algorithm") == "ks_test"]
        assert len(ks_anomalies) > 0
        ctx = ks_anomalies[0].context
        assert "ks_statistic" in ctx
        assert "p_value" in ctx
        assert "adaptive_threshold" in ctx
        assert ctx["p_value"] < 0.05

    def test_ks_statistic_must_exceed_threshold(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """No KS anomaly when statistic is below threshold."""
        # Use a high threshold that won't be triggered
        engine_high = AnomalyDetectionEngine(ks_threshold=0.99)
        _populate_baseline(engine_high, dataset_id, num_profiles=10)

        rng = np.random.default_rng(seed=99)
        values = rng.normal(55.0, 10.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine_high.detect_anomalies(current, dataset_id)
        ks_anomalies = [a for a in anomalies if a.context.get("algorithm") == "ks_test"]
        assert len(ks_anomalies) == 0


class TestKLDivergenceDetection:
    """Tests for KL-divergence based anomaly detection."""

    def test_kl_divergence_detects_shift(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """KL-divergence detects large distributional shifts."""
        # Use a low KL threshold to ensure detection
        engine_low = AnomalyDetectionEngine(kl_threshold=0.1)
        _populate_baseline(engine_low, dataset_id, num_profiles=10, base_mean=50.0)

        # Create a very different distribution
        rng = np.random.default_rng(seed=77)
        values = rng.exponential(scale=5.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine_low.detect_anomalies(current, dataset_id)
        kl_anomalies = [a for a in anomalies if a.context.get("algorithm") == "kl_divergence"]
        assert len(kl_anomalies) > 0

    def test_kl_divergence_below_threshold_no_anomaly(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """No KL anomaly when divergence is below threshold."""
        # Very high KL threshold - hard to trigger
        engine_high = AnomalyDetectionEngine(kl_threshold=100.0)
        _populate_baseline(engine_high, dataset_id, num_profiles=10)

        rng = np.random.default_rng(seed=99)
        values = rng.normal(55.0, 10.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine_high.detect_anomalies(current, dataset_id)
        kl_anomalies = [a for a in anomalies if a.context.get("algorithm") == "kl_divergence"]
        assert len(kl_anomalies) == 0

    def test_kl_anomaly_has_correct_fields(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """KL anomalies have proper metric_name and context."""
        engine_low = AnomalyDetectionEngine(kl_threshold=0.01)
        _populate_baseline(engine_low, dataset_id, num_profiles=10, base_mean=50.0)

        rng = np.random.default_rng(seed=77)
        values = rng.exponential(scale=5.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine_low.detect_anomalies(current, dataset_id)
        kl_anomalies = [a for a in anomalies if a.context.get("algorithm") == "kl_divergence"]
        assert len(kl_anomalies) > 0
        anomaly = kl_anomalies[0]
        assert anomaly.metric_name == "kl_divergence"
        assert anomaly.category == AnomalyCategory.DISTRIBUTION_SHIFT
        assert "kl_divergence" in anomaly.context
        assert "adaptive_threshold" in anomaly.context


class TestAnomalyScoreAndConfidence:
    """Tests for anomaly score and confidence bounds."""

    def test_anomaly_score_bounded(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Anomaly scores are always in [0.0, 1.0]."""
        _populate_baseline(engine, dataset_id, num_profiles=10)

        rng = np.random.default_rng(seed=99)
        values = rng.normal(500.0, 1.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine.detect_anomalies(current, dataset_id)
        for anomaly in anomalies:
            assert 0.0 <= anomaly.anomaly_score <= 1.0

    def test_confidence_bounded(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Confidence values are always in [0.0, 1.0]."""
        _populate_baseline(engine, dataset_id, num_profiles=10)

        rng = np.random.default_rng(seed=99)
        values = rng.normal(500.0, 1.0, size=200).tolist()
        col_profile = _make_column_profile("amount", values)
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine.detect_anomalies(current, dataset_id)
        for anomaly in anomalies:
            assert 0.0 <= anomaly.confidence <= 1.0

    def test_confidence_scales_with_baseline_count(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Confidence increases with more baseline profiles."""
        conf_7 = engine._compute_confidence(7)
        conf_15 = engine._compute_confidence(15)
        conf_30 = engine._compute_confidence(30)
        conf_50 = engine._compute_confidence(50)

        assert conf_7 < conf_15 < conf_30
        # Max at 30+
        assert conf_30 == 1.0
        assert conf_50 == 1.0

    def test_confidence_zero_for_empty_baseline(
        self, engine: AnomalyDetectionEngine
    ):
        """Confidence is 0 when baseline is empty."""
        assert engine._compute_confidence(0) == 0.0

    def test_anomaly_score_formula(self, engine: AnomalyDetectionEngine):
        """Anomaly score = min(1.0, ks_statistic / threshold)."""
        # Score below 1
        assert engine._compute_anomaly_score(0.10, 0.15) == pytest.approx(0.10 / 0.15)
        # Score capped at 1.0
        assert engine._compute_anomaly_score(0.30, 0.15) == 1.0
        # Exact threshold gives score of 1.0
        assert engine._compute_anomaly_score(0.15, 0.15) == 1.0


class TestBaselineManagement:
    """Tests for update_baseline and get_baseline."""

    def test_update_baseline_adds_profile(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """update_baseline adds profile to the rolling baseline."""
        rng = np.random.default_rng(seed=42)
        values = rng.normal(50.0, 10.0, size=100).tolist()
        col_profile = _make_column_profile("amount", values)
        profile = _make_data_profile(dataset_id, {"amount": col_profile})

        engine.update_baseline(dataset_id, profile)
        baseline = engine.get_baseline(dataset_id)
        assert len(baseline) == 1
        assert baseline[0] == profile

    def test_update_baseline_evicts_old_profiles(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Profiles older than 30 days are evicted from baseline."""
        rng = np.random.default_rng(seed=42)

        # Add a profile from 40 days ago (should be evicted)
        old_values = rng.normal(50.0, 10.0, size=100).tolist()
        old_col = _make_column_profile("amount", old_values)
        old_profile = _make_data_profile(
            dataset_id,
            {"amount": old_col},
            profiled_at=datetime.now(timezone.utc) - timedelta(days=40),
        )
        engine.update_baseline(dataset_id, old_profile)

        # Add a recent profile (should remain)
        new_values = rng.normal(50.0, 10.0, size=100).tolist()
        new_col = _make_column_profile("amount", new_values)
        new_profile = _make_data_profile(
            dataset_id,
            {"amount": new_col},
            profiled_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        engine.update_baseline(dataset_id, new_profile)

        baseline = engine.get_baseline(dataset_id)
        assert len(baseline) == 1
        assert baseline[0] == new_profile

    def test_get_baseline_empty_for_unknown_dataset(
        self, engine: AnomalyDetectionEngine
    ):
        """get_baseline returns empty list for unknown datasets."""
        unknown = DatasetId(namespace="unknown.dataset.test", version=1)
        assert engine.get_baseline(unknown) == []

    def test_multiple_baselines_independent(
        self, engine: AnomalyDetectionEngine
    ):
        """Different datasets have independent baselines."""
        ds1 = DatasetId(namespace="warehouse.public.sales", version=1)
        ds2 = DatasetId(namespace="warehouse.public.orders", version=1)

        rng = np.random.default_rng(seed=42)
        values = rng.normal(50.0, 10.0, size=100).tolist()
        col = _make_column_profile("amount", values)

        p1 = _make_data_profile(ds1, {"amount": col})
        p2 = _make_data_profile(ds2, {"amount": col})

        engine.update_baseline(ds1, p1)
        engine.update_baseline(ds2, p2)

        assert len(engine.get_baseline(ds1)) == 1
        assert len(engine.get_baseline(ds2)) == 1


class TestAdaptiveThresholds:
    """Tests for adaptive threshold support."""

    def test_default_thresholds_used_initially(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Static default thresholds are used when no adaptive thresholds set."""
        ks = engine._get_ks_threshold(dataset_id, "amount")
        kl = engine._get_kl_threshold(dataset_id, "amount")
        assert ks == _DEFAULT_KS_THRESHOLD
        assert kl == _DEFAULT_KL_THRESHOLD

    def test_adaptive_threshold_overrides_default(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Adaptive thresholds override the static defaults."""
        engine.set_adaptive_threshold(dataset_id, "amount", ks_threshold=0.25)
        engine.set_adaptive_threshold(dataset_id, "amount", kl_threshold=0.8)

        assert engine._get_ks_threshold(dataset_id, "amount") == 0.25
        assert engine._get_kl_threshold(dataset_id, "amount") == 0.8


class TestNumericalErrorHandling:
    """Tests for error handling during detection."""

    def test_skips_column_without_histogram(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Columns without histograms are gracefully handled."""
        _populate_baseline(engine, dataset_id, num_profiles=10)

        # Current profile with no histogram
        col_profile = ColumnProfile(
            column_name="amount",
            dtype=ColumnType.FLOAT,
            total_count=100,
            null_count=0,
            distinct_count=50,
            mean=50.0,
            histogram=None,
        )
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        # Should not crash, should return empty or handle gracefully
        anomalies = engine.detect_anomalies(current, dataset_id)
        # No KS or KL anomalies possible without histograms
        assert isinstance(anomalies, list)

    def test_empty_histogram_handled(
        self, engine: AnomalyDetectionEngine, dataset_id: DatasetId
    ):
        """Empty histograms don't cause errors."""
        _populate_baseline(engine, dataset_id, num_profiles=10)

        col_profile = ColumnProfile(
            column_name="amount",
            dtype=ColumnType.FLOAT,
            total_count=100,
            null_count=0,
            distinct_count=50,
            mean=50.0,
            histogram=[],
        )
        current = _make_data_profile(dataset_id, {"amount": col_profile})

        anomalies = engine.detect_anomalies(current, dataset_id)
        assert isinstance(anomalies, list)


class TestKLDivergenceComputation:
    """Tests for the internal KL-divergence computation."""

    def test_kl_divergence_identical_distributions(
        self, engine: AnomalyDetectionEngine
    ):
        """KL-divergence of identical distributions is approximately 0."""
        values = list(range(100))
        col = _make_column_profile("x", [float(v) for v in values])
        kl = engine._compute_kl_divergence(col, col)
        assert kl is not None
        assert kl < 0.01  # Very close to 0

    def test_kl_divergence_different_distributions(
        self, engine: AnomalyDetectionEngine
    ):
        """KL-divergence of very different distributions is positive and non-trivial."""
        rng = np.random.default_rng(seed=42)
        values_a = rng.normal(0, 1, size=500).tolist()
        values_b = rng.normal(10, 1, size=500).tolist()
        col_a = _make_column_profile("x", values_a)
        col_b = _make_column_profile("x", values_b)
        kl = engine._compute_kl_divergence(col_a, col_b)
        assert kl is not None
        # KL-divergence should be positive for different distributions
        # Note: histogram binning limits precision, so we use a lower bound
        assert kl > 0.05

    def test_kl_divergence_none_when_no_histogram(
        self, engine: AnomalyDetectionEngine
    ):
        """Returns None if either profile lacks a histogram."""
        col_no_hist = ColumnProfile(
            column_name="x",
            dtype=ColumnType.FLOAT,
            total_count=100,
            null_count=0,
            distinct_count=50,
            histogram=None,
        )
        col_with_hist = _make_column_profile("x", list(range(100)))
        assert engine._compute_kl_divergence(col_no_hist, col_with_hist) is None
        assert engine._compute_kl_divergence(col_with_hist, col_no_hist) is None
