"""Unit tests for the Statistical Profiler service."""

import math

import pytest

from data_quality_engine.models.base import ColumnType, DatasetId
from data_quality_engine.models.profile import ColumnProfile, DataProfile, HistogramBucket
from data_quality_engine.services.profiler import (
    HyperLogLog,
    StatisticalProfiler,
    _HLL_THRESHOLD,
    _MAX_COLUMNS,
)
from data_quality_engine.storage.timescale import TimescaleTimeSeriesStore


@pytest.fixture
def profiler() -> StatisticalProfiler:
    """Create a StatisticalProfiler with in-memory store."""
    store = TimescaleTimeSeriesStore(retention_days=90)
    return StatisticalProfiler(time_series_store=store, retention_days=90)


@pytest.fixture
def profiler_no_store() -> StatisticalProfiler:
    """Create a StatisticalProfiler without a store."""
    return StatisticalProfiler()


class TestComputeProfileNumeric:
    """Tests for numeric column profiling."""

    def test_basic_numeric_stats(self, profiler_no_store: StatisticalProfiler):
        """Test mean, std, min, max for a simple numeric column."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        profile = profiler_no_store.compute_profile(
            column_name="value",
            column_data=data,
            dtype=ColumnType.FLOAT,
        )

        assert profile.column_name == "value"
        assert profile.dtype == ColumnType.FLOAT
        assert profile.total_count == 5
        assert profile.null_count == 0
        assert profile.distinct_count == 5
        assert profile.mean == pytest.approx(3.0)
        assert profile.min_val == pytest.approx(1.0)
        assert profile.max_val == pytest.approx(5.0)
        assert profile.std_dev is not None
        assert profile.std_dev > 0

    def test_percentiles(self, profiler_no_store: StatisticalProfiler):
        """Test percentile computation for numeric columns."""
        data = list(range(1, 101))  # 1 to 100
        profile = profiler_no_store.compute_profile(
            column_name="numbers",
            column_data=data,
            dtype=ColumnType.INTEGER,
        )

        assert profile.p25 is not None
        assert profile.p50 is not None
        assert profile.p75 is not None
        assert profile.p99 is not None
        # p50 should be approximately the median
        assert profile.p50 == pytest.approx(50.5, abs=1.0)
        assert profile.p25 < profile.p50 < profile.p75 < profile.p99

    def test_skewness_and_kurtosis(self, profiler_no_store: StatisticalProfiler):
        """Test skewness and kurtosis computation."""
        # Symmetric distribution - skewness should be near 0
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        profile = profiler_no_store.compute_profile(
            column_name="symmetric",
            column_data=data,
            dtype=ColumnType.FLOAT,
        )

        assert profile.skewness is not None
        assert abs(profile.skewness) < 0.5  # Nearly symmetric
        assert profile.kurtosis is not None

    def test_single_value_numeric(self, profiler_no_store: StatisticalProfiler):
        """Test numeric column with a single non-null value."""
        data = [42.0]
        profile = profiler_no_store.compute_profile(
            column_name="single",
            column_data=data,
            dtype=ColumnType.FLOAT,
        )

        assert profile.total_count == 1
        assert profile.null_count == 0
        assert profile.distinct_count == 1
        assert profile.mean == pytest.approx(42.0)
        assert profile.min_val == pytest.approx(42.0)
        assert profile.max_val == pytest.approx(42.0)
        # std is undefined for single value
        assert profile.std_dev is None
        # skewness needs at least 3 values
        assert profile.skewness is None
        # kurtosis needs at least 4 values
        assert profile.kurtosis is None

    def test_two_values_numeric(self, profiler_no_store: StatisticalProfiler):
        """Test numeric column with two values - std is defined but skewness is not."""
        data = [1.0, 3.0]
        profile = profiler_no_store.compute_profile(
            column_name="two",
            column_data=data,
            dtype=ColumnType.FLOAT,
        )

        assert profile.std_dev is not None
        assert profile.skewness is None  # Needs 3+ values
        assert profile.kurtosis is None  # Needs 4+ values

    def test_numeric_with_nulls(self, profiler_no_store: StatisticalProfiler):
        """Test numeric column with mixed null and non-null values."""
        data = [1.0, None, 3.0, None, 5.0]
        profile = profiler_no_store.compute_profile(
            column_name="nullable",
            column_data=data,
            dtype=ColumnType.FLOAT,
        )

        assert profile.total_count == 5
        assert profile.null_count == 2
        assert profile.distinct_count == 3
        assert profile.mean == pytest.approx(3.0)


class TestComputeProfileString:
    """Tests for string column profiling."""

    def test_basic_string_stats(self, profiler_no_store: StatisticalProfiler):
        """Test avg_length and max_length for string columns."""
        data = ["hi", "hello", "hey"]
        profile = profiler_no_store.compute_profile(
            column_name="greeting",
            column_data=data,
            dtype=ColumnType.STRING,
        )

        assert profile.column_name == "greeting"
        assert profile.dtype == ColumnType.STRING
        assert profile.total_count == 3
        assert profile.null_count == 0
        assert profile.distinct_count == 3
        # avg_length = (2 + 5 + 3) / 3 = 3.33...
        assert profile.avg_length == pytest.approx(10.0 / 3.0)
        assert profile.max_length == 5
        # Numeric stats should be None for strings
        assert profile.mean is None
        assert profile.std_dev is None

    def test_unicode_string_length(self, profiler_no_store: StatisticalProfiler):
        """Test that string length is measured in Unicode code points."""
        # Each emoji is 1 code point
        data = ["hello", "🎉🎊🎈"]  # 5 chars, 3 code points
        profile = profiler_no_store.compute_profile(
            column_name="unicode_col",
            column_data=data,
            dtype=ColumnType.STRING,
        )

        assert profile.max_length == 5  # "hello" is 5 code points
        assert profile.avg_length == pytest.approx(4.0)  # (5 + 3) / 2

    def test_string_with_nulls(self, profiler_no_store: StatisticalProfiler):
        """Test string column with null values."""
        data = ["abc", None, "de", None]
        profile = profiler_no_store.compute_profile(
            column_name="nullable_str",
            column_data=data,
            dtype=ColumnType.STRING,
        )

        assert profile.total_count == 4
        assert profile.null_count == 2
        assert profile.distinct_count == 2
        # avg_length over non-null values: (3 + 2) / 2 = 2.5
        assert profile.avg_length == pytest.approx(2.5)
        assert profile.max_length == 3


class TestAllNullColumn:
    """Tests for all-null column handling."""

    def test_all_null_numeric(self, profiler_no_store: StatisticalProfiler):
        """Test all-null numeric column returns proper null profile."""
        data = [None, None, None, None, None]
        profile = profiler_no_store.compute_profile(
            column_name="all_null",
            column_data=data,
            dtype=ColumnType.FLOAT,
        )

        assert profile.total_count == 5
        assert profile.null_count == 5
        assert profile.distinct_count == 0
        assert profile.mean is None
        assert profile.std_dev is None
        assert profile.min_val is None
        assert profile.max_val is None
        assert profile.p25 is None
        assert profile.p50 is None
        assert profile.p75 is None
        assert profile.p99 is None
        assert profile.skewness is None
        assert profile.kurtosis is None
        assert profile.avg_length is None
        assert profile.max_length is None
        assert profile.histogram is None

    def test_all_null_string(self, profiler_no_store: StatisticalProfiler):
        """Test all-null string column."""
        data = [None, None, None]
        profile = profiler_no_store.compute_profile(
            column_name="null_str",
            column_data=data,
            dtype=ColumnType.STRING,
        )

        assert profile.null_count == profile.total_count
        assert profile.distinct_count == 0
        assert profile.avg_length is None
        assert profile.max_length is None


class TestDistinctCount:
    """Tests for distinct count computation (exact and HLL)."""

    def test_exact_distinct_count(self, profiler_no_store: StatisticalProfiler):
        """Test exact distinct count for low cardinality."""
        data = [1, 2, 3, 2, 1, 4, 5, 5]
        profile = profiler_no_store.compute_profile(
            column_name="low_card",
            column_data=data,
            dtype=ColumnType.INTEGER,
        )

        assert profile.distinct_count == 5

    def test_hll_distinct_count_approximation(self, profiler_no_store: StatisticalProfiler):
        """Test HLL approximation for high cardinality (>100K distinct values)."""
        # Generate 150K unique values to trigger HLL
        data = list(range(150_000))
        profile = profiler_no_store.compute_profile(
            column_name="high_card",
            column_data=data,
            dtype=ColumnType.INTEGER,
        )

        # HLL should be within 2% relative error
        expected = 150_000
        relative_error = abs(profile.distinct_count - expected) / expected
        assert relative_error <= 0.02, (
            f"HLL relative error {relative_error:.4f} exceeds 2% threshold. "
            f"Got {profile.distinct_count}, expected {expected}"
        )


class TestHistogram:
    """Tests for histogram generation."""

    def test_default_bins(self, profiler_no_store: StatisticalProfiler):
        """Test histogram with default 20 bins."""
        data = list(range(100))
        profile = profiler_no_store.compute_profile(
            column_name="hist_col",
            column_data=data,
            dtype=ColumnType.INTEGER,
        )

        assert profile.histogram is not None
        assert len(profile.histogram) == 20

    def test_custom_bins(self, profiler_no_store: StatisticalProfiler):
        """Test histogram with custom bin count."""
        data = list(range(100))
        profile = profiler_no_store.compute_profile(
            column_name="hist_col",
            column_data=data,
            dtype=ColumnType.INTEGER,
            num_bins=10,
        )

        assert profile.histogram is not None
        assert len(profile.histogram) == 10

    def test_bins_clamped_minimum(self, profiler_no_store: StatisticalProfiler):
        """Test that bins below 5 are clamped to 5."""
        data = list(range(100))
        profile = profiler_no_store.compute_profile(
            column_name="hist_col",
            column_data=data,
            dtype=ColumnType.INTEGER,
            num_bins=2,
        )

        assert profile.histogram is not None
        assert len(profile.histogram) == 5

    def test_bins_clamped_maximum(self, profiler_no_store: StatisticalProfiler):
        """Test that bins above 100 are clamped to 100."""
        data = list(range(200))
        profile = profiler_no_store.compute_profile(
            column_name="hist_col",
            column_data=data,
            dtype=ColumnType.INTEGER,
            num_bins=200,
        )

        assert profile.histogram is not None
        assert len(profile.histogram) == 100

    def test_histogram_counts_sum(self, profiler_no_store: StatisticalProfiler):
        """Test that histogram bucket counts sum to total non-null values."""
        data = list(range(50))
        profile = profiler_no_store.compute_profile(
            column_name="hist_col",
            column_data=data,
            dtype=ColumnType.INTEGER,
            num_bins=10,
        )

        assert profile.histogram is not None
        total = sum(b.count for b in profile.histogram)
        assert total == 50

    def test_no_histogram_for_strings(self, profiler_no_store: StatisticalProfiler):
        """Test that string columns do not get histograms."""
        data = ["a", "b", "c"]
        profile = profiler_no_store.compute_profile(
            column_name="str_col",
            column_data=data,
            dtype=ColumnType.STRING,
        )

        assert profile.histogram is None


class TestSampling:
    """Tests for sample_rate behavior."""

    def test_sampling_produces_profile(self, profiler_no_store: StatisticalProfiler):
        """Test that sampling still produces a valid profile."""
        data = list(range(1000))
        profile = profiler_no_store.compute_profile(
            column_name="sampled",
            column_data=data,
            dtype=ColumnType.INTEGER,
            sample_rate=0.5,
        )

        # total_count reflects the full dataset
        assert profile.total_count == 1000
        assert profile.null_count == 0
        # Stats should still be computed (approximately correct)
        assert profile.mean is not None

    def test_sampling_rate_clamped(self, profiler_no_store: StatisticalProfiler):
        """Test that invalid sample rates are clamped to [0.01, 0.99]."""
        data = list(range(100))
        # Rate below 0.01 should be clamped to 0.01
        profile = profiler_no_store.compute_profile(
            column_name="low_rate",
            column_data=data,
            dtype=ColumnType.INTEGER,
            sample_rate=0.001,
        )
        assert profile.total_count == 100
        assert profile.mean is not None


class TestProfileDataset:
    """Tests for the profile_dataset entry point."""

    @pytest.mark.asyncio
    async def test_profile_dataset_basic(self, profiler: StatisticalProfiler):
        """Test profiling a full dataset with multiple columns."""
        dataset_id = DatasetId(namespace="warehouse.public.sales", version=1)
        columns = {
            "amount": ([10.0, 20.0, 30.0, 40.0, 50.0], ColumnType.FLOAT),
            "name": (["Alice", "Bob", "Charlie", "Dave", "Eve"], ColumnType.STRING),
        }

        result = await profiler.profile_dataset(
            dataset_id=dataset_id,
            partition_key="2024-01-15",
            columns=columns,
        )

        assert isinstance(result, DataProfile)
        assert result.dataset_id == dataset_id
        assert result.partition_key == "2024-01-15"
        assert result.row_count == 5
        assert result.profiling_duration_ms >= 1
        assert "amount" in result.column_profiles
        assert "name" in result.column_profiles

        # Check numeric column
        amount_profile = result.column_profiles["amount"]
        assert amount_profile.mean == pytest.approx(30.0)
        assert amount_profile.histogram is not None

        # Check string column
        name_profile = result.column_profiles["name"]
        assert name_profile.avg_length is not None
        assert name_profile.max_length is not None

    @pytest.mark.asyncio
    async def test_profile_dataset_stores_result(self, profiler: StatisticalProfiler):
        """Test that profile_dataset stores the result in the time-series store."""
        dataset_id = DatasetId(namespace="warehouse.public.orders", version=1)
        columns = {
            "total": ([100.0, 200.0], ColumnType.FLOAT),
        }

        result = await profiler.profile_dataset(
            dataset_id=dataset_id,
            partition_key="2024-02-01",
            columns=columns,
        )

        # Verify it was stored
        stored = await profiler._store.get_latest_profile(dataset_id)
        assert stored is not None
        assert stored.partition_key == "2024-02-01"

    @pytest.mark.asyncio
    async def test_profile_dataset_exceeds_max_columns(self, profiler: StatisticalProfiler):
        """Test that exceeding 1024 columns raises ValueError."""
        dataset_id = DatasetId(namespace="warehouse.public.wide", version=1)
        columns = {
            f"col_{i}": ([1.0, 2.0], ColumnType.FLOAT) for i in range(1025)
        }

        with pytest.raises(ValueError, match="exceeds maximum column limit"):
            await profiler.profile_dataset(
                dataset_id=dataset_id,
                partition_key="2024-01-01",
                columns=columns,
            )

    @pytest.mark.asyncio
    async def test_profile_dataset_duration_at_least_one(self, profiler: StatisticalProfiler):
        """Test that profiling_duration_ms is always at least 1."""
        dataset_id = DatasetId(namespace="warehouse.public.tiny", version=1)
        columns = {"x": ([1.0], ColumnType.FLOAT)}

        result = await profiler.profile_dataset(
            dataset_id=dataset_id,
            partition_key="2024-01-01",
            columns=columns,
        )

        assert result.profiling_duration_ms >= 1

    @pytest.mark.asyncio
    async def test_profile_dataset_no_store(self, profiler_no_store: StatisticalProfiler):
        """Test profiling works without a store."""
        dataset_id = DatasetId(namespace="warehouse.public.nostored", version=1)
        columns = {"val": ([1.0, 2.0, 3.0], ColumnType.FLOAT)}

        result = await profiler_no_store.profile_dataset(
            dataset_id=dataset_id,
            partition_key="2024-01-01",
            columns=columns,
        )

        assert isinstance(result, DataProfile)
        assert result.profiling_duration_ms >= 1


class TestHyperLogLog:
    """Tests for the HyperLogLog implementation."""

    def test_hll_empty(self):
        """Test HLL with no values gives 0."""
        hll = HyperLogLog(precision=14)
        assert hll.estimate() == 0

    def test_hll_single_value(self):
        """Test HLL with a single unique value."""
        hll = HyperLogLog(precision=14)
        hll.add("hello")
        estimate = hll.estimate()
        assert estimate >= 1

    def test_hll_accuracy(self):
        """Test HLL accuracy for moderate cardinality."""
        hll = HyperLogLog(precision=14)
        n = 50_000
        for i in range(n):
            hll.add(f"value_{i}")

        estimate = hll.estimate()
        relative_error = abs(estimate - n) / n
        # Should be well within 2% for precision=14
        assert relative_error <= 0.02, (
            f"HLL error {relative_error:.4f} exceeds 2%. Got {estimate}, expected {n}"
        )
