"""Tests for DriftDetector service.

Verifies all severity classifications for:
- Column removal (CRITICAL for primary_key/non-nullable, WARNING for nullable)
- Column addition (always INFO)
- Type changes (narrowing=CRITICAL, widening=WARNING)
- Nullability changes (non-nullable→nullable=CRITICAL, nullable→non-nullable=WARNING)
- Overall severity computation (max across all drifts)
- auto_evolvable flag (true iff all INFO)
- requires_human_review flag (true iff any CRITICAL)
"""

import pytest

from data_quality_engine.models import (
    ColumnContract,
    ColumnDrift,
    ColumnType,
    DatasetId,
    DriftReport,
    DriftSeverity,
    DriftType,
    ObservedSchema,
    SchemaContract,
)
from data_quality_engine.services.drift_detector import DriftDetector


@pytest.fixture
def detector() -> DriftDetector:
    """Create a DriftDetector instance."""
    return DriftDetector()


@pytest.fixture
def dataset_id() -> DatasetId:
    """Create a standard dataset ID for testing."""
    return DatasetId(namespace="warehouse.public.users")


def make_contract(
    dataset_id: DatasetId, columns: list[ColumnContract]
) -> SchemaContract:
    """Helper to create a SchemaContract."""
    return SchemaContract(
        dataset_id=dataset_id,
        version=1,
        columns=columns,
    )


def make_observed(
    dataset_id: DatasetId, columns: list[ColumnContract]
) -> ObservedSchema:
    """Helper to create an ObservedSchema."""
    return ObservedSchema(dataset_id=dataset_id, columns=columns)


# =============================================================================
# Column Removal Tests
# =============================================================================


class TestColumnRemoval:
    """Tests for column removal detection and severity classification."""

    def test_removal_of_primary_key_column_is_critical(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Removing a primary key column should be CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(dataset_id, [])

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.column_name == "id"
        assert drift.drift_type == DriftType.COLUMN_REMOVED
        assert drift.severity == DriftSeverity.CRITICAL

    def test_removal_of_non_nullable_column_is_critical(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Removing a non-nullable column should be CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="email", dtype=ColumnType.STRING, nullable=False)],
        )
        observed = make_observed(dataset_id, [])

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.column_name == "email"
        assert drift.drift_type == DriftType.COLUMN_REMOVED
        assert drift.severity == DriftSeverity.CRITICAL

    def test_removal_of_nullable_column_is_warning(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Removing a nullable column should be WARNING."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="nickname", dtype=ColumnType.STRING, nullable=True)],
        )
        observed = make_observed(dataset_id, [])

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.column_name == "nickname"
        assert drift.drift_type == DriftType.COLUMN_REMOVED
        assert drift.severity == DriftSeverity.WARNING


# =============================================================================
# Column Addition Tests
# =============================================================================


class TestColumnAddition:
    """Tests for column addition detection and severity classification."""

    def test_addition_is_always_info(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Adding a new column should always be INFO severity."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="new_col", dtype=ColumnType.STRING, nullable=True),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.column_name == "new_col"
        assert drift.drift_type == DriftType.COLUMN_ADDED
        assert drift.severity == DriftSeverity.INFO

    def test_multiple_additions_all_info(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Adding multiple columns should all be INFO severity."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="col_a", dtype=ColumnType.STRING),
                ColumnContract(name="col_b", dtype=ColumnType.FLOAT),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 2
        for drift in report.drifts:
            assert drift.drift_type == DriftType.COLUMN_ADDED
            assert drift.severity == DriftSeverity.INFO


# =============================================================================
# Type Change Tests
# =============================================================================


class TestTypeChange:
    """Tests for type change detection with width ordering severity."""

    def test_narrowing_is_critical(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Narrowing type change (STRING → INTEGER) should be CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="val", dtype=ColumnType.STRING, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="val", dtype=ColumnType.INTEGER, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.drift_type == DriftType.TYPE_CHANGED
        assert drift.severity == DriftSeverity.CRITICAL
        assert drift.old_value == "string"
        assert drift.new_value == "integer"

    def test_widening_is_warning(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Widening type change (INTEGER → STRING) should be WARNING."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="val", dtype=ColumnType.INTEGER, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="val", dtype=ColumnType.STRING, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.drift_type == DriftType.TYPE_CHANGED
        assert drift.severity == DriftSeverity.WARNING
        assert drift.old_value == "integer"
        assert drift.new_value == "string"

    def test_boolean_to_integer_is_widening_warning(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """BOOLEAN → INTEGER is widening, should be WARNING."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="flag", dtype=ColumnType.BOOLEAN, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="flag", dtype=ColumnType.INTEGER, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        drift = report.drifts[0]
        assert drift.drift_type == DriftType.TYPE_CHANGED
        assert drift.severity == DriftSeverity.WARNING

    def test_float_to_boolean_is_narrowing_critical(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """FLOAT → BOOLEAN is narrowing, should be CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="score", dtype=ColumnType.FLOAT, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="score", dtype=ColumnType.BOOLEAN, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        drift = report.drifts[0]
        assert drift.drift_type == DriftType.TYPE_CHANGED
        assert drift.severity == DriftSeverity.CRITICAL

    def test_decimal_to_string_is_widening_warning(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """DECIMAL → STRING is widening, should be WARNING."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="amount", dtype=ColumnType.DECIMAL, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="amount", dtype=ColumnType.STRING, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        drift = report.drifts[0]
        assert drift.drift_type == DriftType.TYPE_CHANGED
        assert drift.severity == DriftSeverity.WARNING

    def test_type_not_in_width_order_is_critical(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Type change involving types not in width order should be CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="ts", dtype=ColumnType.TIMESTAMP, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="ts", dtype=ColumnType.STRING, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        drift = report.drifts[0]
        assert drift.drift_type == DriftType.TYPE_CHANGED
        assert drift.severity == DriftSeverity.CRITICAL


# =============================================================================
# Nullability Change Tests
# =============================================================================


class TestNullabilityChange:
    """Tests for nullability change detection and severity classification."""

    def test_non_nullable_to_nullable_is_critical(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """non-nullable → nullable should be CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="email", dtype=ColumnType.STRING, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="email", dtype=ColumnType.STRING, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.drift_type == DriftType.NULLABILITY_CHANGED
        assert drift.severity == DriftSeverity.CRITICAL
        assert drift.old_value == "False"
        assert drift.new_value == "True"

    def test_nullable_to_non_nullable_is_warning(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """nullable → non-nullable should be WARNING."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="name", dtype=ColumnType.STRING, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="name", dtype=ColumnType.STRING, nullable=False)],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 1
        drift = report.drifts[0]
        assert drift.drift_type == DriftType.NULLABILITY_CHANGED
        assert drift.severity == DriftSeverity.WARNING
        assert drift.old_value == "True"
        assert drift.new_value == "False"


# =============================================================================
# Overall Severity Tests
# =============================================================================


class TestOverallSeverity:
    """Tests for overall severity computation and flags."""

    def test_all_info_drifts_overall_info(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """When all drifts are INFO, overall_severity should be INFO."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="new_col", dtype=ColumnType.STRING),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert report.overall_severity == DriftSeverity.INFO

    def test_mixed_warning_and_info_overall_warning(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """When max severity is WARNING, overall_severity should be WARNING."""
        contract = make_contract(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="score", dtype=ColumnType.INTEGER, nullable=True),
            ],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                # Type widening: INTEGER → STRING = WARNING
                ColumnContract(name="score", dtype=ColumnType.STRING, nullable=True),
                # Column addition = INFO
                ColumnContract(name="extra", dtype=ColumnType.BOOLEAN),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert report.overall_severity == DriftSeverity.WARNING

    def test_any_critical_overall_critical(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """When any drift is CRITICAL, overall_severity should be CRITICAL."""
        contract = make_contract(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="name", dtype=ColumnType.STRING, nullable=True),
            ],
        )
        # Remove non-nullable primary key (CRITICAL) + add a column (INFO)
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="name", dtype=ColumnType.STRING, nullable=True),
                ColumnContract(name="added", dtype=ColumnType.BOOLEAN),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert report.overall_severity == DriftSeverity.CRITICAL

    def test_no_drifts_overall_info(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """When there are no drifts, overall_severity defaults to INFO."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 0
        assert report.overall_severity == DriftSeverity.INFO


# =============================================================================
# auto_evolvable Flag Tests
# =============================================================================


class TestAutoEvolvable:
    """Tests for auto_evolvable flag computation."""

    def test_all_info_is_auto_evolvable(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """auto_evolvable=true when ALL drifts are INFO."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="new_col", dtype=ColumnType.STRING),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert report.auto_evolvable is True

    def test_any_warning_not_auto_evolvable(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """auto_evolvable=false when any drift is WARNING."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="val", dtype=ColumnType.INTEGER, nullable=True)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="val", dtype=ColumnType.STRING, nullable=True)],
        )

        report = detector.detect_drift(contract, observed)

        assert report.auto_evolvable is False

    def test_any_critical_not_auto_evolvable(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """auto_evolvable=false when any drift is CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="email", dtype=ColumnType.STRING, nullable=False)],
        )
        observed = make_observed(dataset_id, [])

        report = detector.detect_drift(contract, observed)

        assert report.auto_evolvable is False

    def test_no_drifts_is_auto_evolvable(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """auto_evolvable=true when there are no drifts."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )

        report = detector.detect_drift(contract, observed)

        assert report.auto_evolvable is True


# =============================================================================
# requires_human_review Flag Tests
# =============================================================================


class TestRequiresHumanReview:
    """Tests for requires_human_review flag computation."""

    def test_critical_requires_human_review(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """requires_human_review=true when ANY drift is CRITICAL."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="email", dtype=ColumnType.STRING, nullable=False)],
        )
        observed = make_observed(dataset_id, [])

        report = detector.detect_drift(contract, observed)

        assert report.requires_human_review is True

    def test_warning_only_no_human_review(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """requires_human_review=false when max severity is WARNING (no CRITICAL)."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="nickname", dtype=ColumnType.STRING, nullable=True)],
        )
        # Remove nullable column → WARNING
        observed = make_observed(dataset_id, [])

        report = detector.detect_drift(contract, observed)

        assert report.overall_severity == DriftSeverity.WARNING
        assert report.requires_human_review is False

    def test_info_only_no_human_review(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """requires_human_review=false when all drifts are INFO."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="new_col", dtype=ColumnType.STRING),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert report.requires_human_review is False

    def test_no_drifts_no_human_review(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """requires_human_review=false when there are no drifts."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )

        report = detector.detect_drift(contract, observed)

        assert report.requires_human_review is False


# =============================================================================
# Combined / Integration Tests
# =============================================================================


class TestDriftReportIntegration:
    """Integration tests combining multiple drift types."""

    def test_warning_severity_flags(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """When max severity is WARNING: auto_evolvable=false, requires_human_review=false."""
        contract = make_contract(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="nickname", dtype=ColumnType.STRING, nullable=True),
            ],
        )
        # Remove nullable column → WARNING
        observed = make_observed(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )

        report = detector.detect_drift(contract, observed)

        assert report.overall_severity == DriftSeverity.WARNING
        assert report.auto_evolvable is False
        assert report.requires_human_review is False

    def test_multiple_drift_types(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """Report should contain all detected drifts from different categories."""
        contract = make_contract(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="email", dtype=ColumnType.STRING, nullable=False),
                ColumnContract(name="score", dtype=ColumnType.INTEGER, nullable=True),
            ],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                # email removed → CRITICAL (non-nullable)
                # score type changed INTEGER → FLOAT (widening) → WARNING
                ColumnContract(name="score", dtype=ColumnType.FLOAT, nullable=True),
                # new_field added → INFO
                ColumnContract(name="new_field", dtype=ColumnType.BOOLEAN),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert len(report.drifts) == 3

        # Check individual drifts
        drift_map = {d.column_name: d for d in report.drifts}

        assert drift_map["email"].drift_type == DriftType.COLUMN_REMOVED
        assert drift_map["email"].severity == DriftSeverity.CRITICAL

        assert drift_map["score"].drift_type == DriftType.TYPE_CHANGED
        assert drift_map["score"].severity == DriftSeverity.WARNING

        assert drift_map["new_field"].drift_type == DriftType.COLUMN_ADDED
        assert drift_map["new_field"].severity == DriftSeverity.INFO

        # Overall assessment
        assert report.overall_severity == DriftSeverity.CRITICAL
        assert report.auto_evolvable is False
        assert report.requires_human_review is True

    def test_drift_report_has_correct_metadata(
        self, detector: DriftDetector, dataset_id: DatasetId
    ) -> None:
        """DriftReport should have correct dataset_id, contract_version, and timestamp."""
        contract = make_contract(
            dataset_id,
            [ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False)],
        )
        observed = make_observed(
            dataset_id,
            [
                ColumnContract(name="id", dtype=ColumnType.INTEGER, primary_key=True, nullable=False),
                ColumnContract(name="new", dtype=ColumnType.STRING),
            ],
        )

        report = detector.detect_drift(contract, observed)

        assert report.dataset_id == dataset_id
        assert report.contract_version == 1
        assert report.detected_at is not None
