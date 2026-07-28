"""Statistical Profiler service for computing column-level data profiles.

Implements comprehensive statistical profiling including numeric stats (mean, std,
percentiles, skewness, kurtosis), string stats (avg/max length), cardinality
estimation (exact or HyperLogLog-based), and histogram generation.
"""

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np

from data_quality_engine.models.base import ColumnType, DatasetId
from data_quality_engine.models.profile import (
    ColumnProfile,
    DataProfile,
    HistogramBucket,
)
from data_quality_engine.storage.interfaces import TimeSeriesStore


# HyperLogLog cardinality threshold - exact counting below this
_HLL_THRESHOLD = 100_000

# Maximum supported columns per dataset
_MAX_COLUMNS = 1024


class HyperLogLog:
    """Simple HyperLogLog implementation for approximate distinct counting.

    Uses a hash-based approach with configurable precision to achieve
    ≤2% relative error for high-cardinality columns.
    """

    def __init__(self, precision: int = 14) -> None:
        """Initialize HyperLogLog with given precision (number of register bits).

        Args:
            precision: Number of bits for register addressing. Higher = more accurate.
                       14 bits gives ~0.8% standard error with 16384 registers.
        """
        self._precision = precision
        self._num_registers = 1 << precision
        self._registers = np.zeros(self._num_registers, dtype=np.uint8)

    def add(self, value: Any) -> None:
        """Add a value to the HyperLogLog sketch."""
        # Use a 64-bit hash for consistent behavior
        h = int(hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16], 16)
        # Use first `precision` bits as register index
        register_idx = h & (self._num_registers - 1)
        # Use remaining bits to count trailing zeros (position of first 1-bit)
        remaining = h >> self._precision
        # Count trailing zeros + 1 (rho function)
        run_length = self._rho(remaining)
        self._registers[register_idx] = max(
            self._registers[register_idx], run_length
        )

    def estimate(self) -> int:
        """Estimate the cardinality (distinct count)."""
        m = self._num_registers
        alpha = self._get_alpha(m)

        # Harmonic mean of 2^(-register[j])
        indicator = np.sum(2.0 ** (-self._registers.astype(np.float64)))
        raw_estimate = alpha * m * m / indicator

        # Small range correction (linear counting)
        if raw_estimate <= 2.5 * m:
            zeros = int(np.count_nonzero(self._registers == 0))
            if zeros > 0:
                raw_estimate = m * np.log(m / zeros)

        # Large range correction (for 64-bit hash)
        two_to_64 = 2.0 ** 64
        if raw_estimate > two_to_64 / 30.0:
            raw_estimate = -two_to_64 * np.log(1.0 - raw_estimate / two_to_64)

        return max(0, int(round(raw_estimate)))

    @staticmethod
    def _rho(value: int) -> int:
        """Count trailing zeros + 1 (position of lowest set bit).

        This is the standard HLL rho function. Returns 1 if LSB is set,
        2 if second bit is first set, etc.
        """
        if value == 0:
            return 50  # Max run length for our 64-bit hash
        # Count trailing zeros
        count = 1
        while (value & 1) == 0 and count <= 50:
            value >>= 1
            count += 1
        return count

    @staticmethod
    def _get_alpha(m: int) -> float:
        """Get the bias-correction constant alpha for m registers."""
        if m == 16:
            return 0.673
        elif m == 32:
            return 0.697
        elif m == 64:
            return 0.709
        else:
            return 0.7213 / (1.0 + 1.079 / m)


class StatisticalProfiler:
    """Column-level statistical profiling engine.

    Computes comprehensive profiles for numeric and string columns including
    distribution statistics, cardinality estimation, and histogram generation.
    """

    def __init__(
        self,
        time_series_store: TimeSeriesStore | None = None,
        retention_days: int = 90,
        default_histogram_bins: int = 20,
    ) -> None:
        """Initialize the profiler.

        Args:
            time_series_store: Storage backend for persisting profiles.
            retention_days: How long to retain profiles (default 90 days).
            default_histogram_bins: Default number of histogram bins (default 20).
        """
        self._store = time_series_store
        self._retention_days = retention_days
        self._default_histogram_bins = default_histogram_bins

    def compute_profile(
        self,
        column_name: str,
        column_data: list[Any],
        dtype: ColumnType,
        num_bins: int | None = None,
        sample_rate: float | None = None,
    ) -> ColumnProfile:
        """Compute a full statistical profile for a column.

        Args:
            column_name: Name of the column being profiled.
            column_data: Raw column values (may contain None for nulls).
            dtype: The data type of the column.
            num_bins: Number of histogram bins (default 20, range [5, 100]).
            sample_rate: Optional sampling rate [0.01, 0.99] for approximate stats.

        Returns:
            A ColumnProfile with computed statistics.
        """
        bins = num_bins if num_bins is not None else self._default_histogram_bins
        if bins < 5:
            bins = 5
        elif bins > 100:
            bins = 100

        total_count = len(column_data)
        null_count = sum(1 for v in column_data if v is None)

        # Handle all-null columns
        if null_count == total_count:
            return ColumnProfile(
                column_name=column_name,
                dtype=dtype,
                total_count=total_count,
                null_count=null_count,
                distinct_count=0,
                mean=None,
                std_dev=None,
                min_val=None,
                max_val=None,
                p25=None,
                p50=None,
                p75=None,
                p99=None,
                skewness=None,
                kurtosis=None,
                avg_length=None,
                max_length=None,
                histogram=None,
                top_values=None,
            )

        # Filter non-null values
        non_null_values = [v for v in column_data if v is not None]

        # Apply sampling if specified
        if sample_rate is not None:
            sample_rate = max(0.01, min(0.99, sample_rate))
            rng = np.random.default_rng(seed=42)
            sample_size = max(1, int(len(non_null_values) * sample_rate))
            indices = rng.choice(len(non_null_values), size=sample_size, replace=False)
            non_null_values = [non_null_values[i] for i in sorted(indices)]

        # Compute distinct count
        distinct_count = self._compute_distinct_count(non_null_values)

        # Compute type-specific stats
        numeric_stats = {}
        string_stats = {}
        histogram = None

        if dtype in (
            ColumnType.INTEGER,
            ColumnType.FLOAT,
            ColumnType.DECIMAL,
        ):
            numeric_stats = self._compute_numeric_stats(non_null_values)
            histogram = self._compute_histogram(non_null_values, bins)
        elif dtype == ColumnType.STRING:
            string_stats = self._compute_string_stats(non_null_values)

        return ColumnProfile(
            column_name=column_name,
            dtype=dtype,
            total_count=total_count,
            null_count=null_count,
            distinct_count=distinct_count,
            mean=numeric_stats.get("mean"),
            std_dev=numeric_stats.get("std_dev"),
            min_val=numeric_stats.get("min_val"),
            max_val=numeric_stats.get("max_val"),
            p25=numeric_stats.get("p25"),
            p50=numeric_stats.get("p50"),
            p75=numeric_stats.get("p75"),
            p99=numeric_stats.get("p99"),
            skewness=numeric_stats.get("skewness"),
            kurtosis=numeric_stats.get("kurtosis"),
            avg_length=string_stats.get("avg_length"),
            max_length=string_stats.get("max_length"),
            histogram=histogram,
            top_values=None,
        )

    def _compute_numeric_stats(self, values: list[Any]) -> dict[str, float | None]:
        """Compute numeric statistics: mean, std, percentiles, skewness, kurtosis.

        Returns a dict of stat name to value. Returns None for metrics that
        are mathematically undefined (e.g., std with <2 values).
        """
        arr = np.array(values, dtype=np.float64)

        if len(arr) == 0:
            return {
                "mean": None,
                "std_dev": None,
                "min_val": None,
                "max_val": None,
                "p25": None,
                "p50": None,
                "p75": None,
                "p99": None,
                "skewness": None,
                "kurtosis": None,
            }

        mean_val = float(np.mean(arr))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))

        # Standard deviation (needs at least 2 values for sample std)
        std_val: float | None = None
        if len(arr) >= 2:
            std_val = float(np.std(arr, ddof=1))
        else:
            std_val = None

        # Percentiles
        p25 = float(np.percentile(arr, 25))
        p50 = float(np.percentile(arr, 50))
        p75 = float(np.percentile(arr, 75))
        p99 = float(np.percentile(arr, 99))

        # Skewness (needs at least 3 values)
        skewness: float | None = None
        if len(arr) >= 3 and std_val is not None and std_val > 0:
            n = len(arr)
            skewness = float(
                (n / ((n - 1) * (n - 2)))
                * np.sum(((arr - mean_val) / std_val) ** 3)
            )

        # Kurtosis (needs at least 4 values) - excess kurtosis
        kurtosis: float | None = None
        if len(arr) >= 4 and std_val is not None and std_val > 0:
            n = len(arr)
            m4 = float(np.mean((arr - mean_val) ** 4))
            m2 = float(np.mean((arr - mean_val) ** 2))
            if m2 > 0:
                kurtosis = float(m4 / (m2 ** 2) - 3.0)

        return {
            "mean": mean_val,
            "std_dev": std_val,
            "min_val": min_val,
            "max_val": max_val,
            "p25": p25,
            "p50": p50,
            "p75": p75,
            "p99": p99,
            "skewness": skewness,
            "kurtosis": kurtosis,
        }

    def _compute_string_stats(self, values: list[Any]) -> dict[str, float | int | None]:
        """Compute string statistics: average length and max length in Unicode code points."""
        if not values:
            return {"avg_length": None, "max_length": None}

        lengths = [len(str(v)) for v in values]
        avg_length = float(sum(lengths) / len(lengths))
        max_length = max(lengths)

        return {"avg_length": avg_length, "max_length": max_length}

    def _compute_distinct_count(self, values: list[Any]) -> int:
        """Compute distinct count - exact for ≤100K cardinality, HLL above.

        Uses exact set counting for cardinality up to 100,000.
        For higher cardinalities, uses HyperLogLog with ≤2% relative error.
        """
        # First try exact counting
        unique_set: set[Any] = set()
        use_hll = False

        for v in values:
            unique_set.add(v)
            if len(unique_set) > _HLL_THRESHOLD:
                use_hll = True
                break

        if not use_hll:
            return len(unique_set)

        # Fall back to HyperLogLog for high cardinality
        hll = HyperLogLog(precision=14)
        for v in values:
            hll.add(v)
        return hll.estimate()

    def _compute_histogram(
        self, values: list[Any], num_bins: int
    ) -> list[HistogramBucket]:
        """Generate an equal-width histogram from numeric values.

        Args:
            values: Non-null numeric values.
            num_bins: Number of bins (already validated to [5, 100]).

        Returns:
            List of HistogramBucket objects.
        """
        arr = np.array(values, dtype=np.float64)

        if len(arr) == 0:
            return []

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

    async def profile_dataset(
        self,
        dataset_id: DatasetId,
        partition_key: str,
        columns: dict[str, tuple[list[Any], ColumnType]],
        num_bins: int | None = None,
        sample_rate: float | None = None,
    ) -> DataProfile:
        """Profile all columns in a dataset and return a DataProfile.

        This is the main entry point for profiling a dataset partition.

        Args:
            dataset_id: Identifier of the dataset being profiled.
            partition_key: Partition identifier (e.g. "2024-01-15").
            columns: Dict mapping column_name to (data, dtype) tuples.
            num_bins: Number of histogram bins (default 20, range [5, 100]).
            sample_rate: Optional sampling rate [0.01, 0.99].

        Returns:
            A DataProfile containing profiles for all columns.

        Raises:
            ValueError: If more than 1024 columns are provided.
        """
        if len(columns) > _MAX_COLUMNS:
            raise ValueError(
                f"Dataset exceeds maximum column limit: {len(columns)} > {_MAX_COLUMNS}"
            )

        start_time = time.perf_counter()

        column_profiles: dict[str, ColumnProfile] = {}
        row_count = 0

        for col_name, (col_data, col_dtype) in columns.items():
            profile = self.compute_profile(
                column_name=col_name,
                column_data=col_data,
                dtype=col_dtype,
                num_bins=num_bins,
                sample_rate=sample_rate,
            )
            column_profiles[col_name] = profile
            # Track row count from the first column
            if row_count == 0:
                row_count = profile.total_count

        end_time = time.perf_counter()
        duration_ms = max(1, int((end_time - start_time) * 1000))

        data_profile = DataProfile(
            dataset_id=dataset_id,
            partition_key=partition_key,
            row_count=row_count,
            column_profiles=column_profiles,
            profiled_at=datetime.now(timezone.utc),
            profiling_duration_ms=duration_ms,
        )

        # Persist profile to time-series store if available
        if self._store is not None:
            await self._store.store_profile(data_profile)

        return data_profile
