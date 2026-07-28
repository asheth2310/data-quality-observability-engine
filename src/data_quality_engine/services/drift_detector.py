"""Schema Drift Detector service.

Compares observed schemas against registered contracts, classifies changes
by severity, and produces DriftReport with overall assessment.
"""

from datetime import datetime, timezone

from data_quality_engine.models import (
    ColumnContract,
    ColumnDrift,
    DriftReport,
    DriftSeverity,
    DriftType,
    ObservedSchema,
    SchemaContract,
)

# Type width ordering: narrower types have lower values.
# Narrowing (higher → lower) is CRITICAL; widening (lower → higher) is WARNING.
TYPE_WIDTH_ORDER: dict[str, int] = {
    "boolean": 0,
    "integer": 1,
    "float": 2,
    "decimal": 3,
    "string": 4,
}


class DriftDetector:
    """Schema drift detection and classification.

    Compares an observed schema against a registered contract and produces
    a DriftReport containing all detected column-level drifts with severity
    classifications. Also computes overall severity, auto_evolvable, and
    requires_human_review flags.
    """

    def detect_drift(
        self, contract: SchemaContract, observed: ObservedSchema
    ) -> DriftReport:
        """Compare observed schema against contract and classify changes.

        Detects:
        - Column removals (in contract but not observed)
        - Column additions (in observed but not contract)
        - Type changes (with width-based severity)
        - Nullability changes

        Args:
            contract: The registered schema contract.
            observed: The schema observed from actual data.

        Returns:
            DriftReport with all detected drifts and overall assessment.
        """
        drifts: list[ColumnDrift] = []

        # Build lookup maps
        contract_columns: dict[str, ColumnContract] = {
            col.name: col for col in contract.columns
        }
        observed_columns: dict[str, ColumnContract] = {
            col.name: col for col in observed.columns
        }

        # Detect column removals (in contract but not in observed)
        for col_name, col_contract in contract_columns.items():
            if col_name not in observed_columns:
                severity = self._classify_removal_severity(col_contract)
                drifts.append(
                    ColumnDrift(
                        column_name=col_name,
                        drift_type=DriftType.COLUMN_REMOVED,
                        severity=severity,
                        old_value=col_contract.dtype.value,
                        new_value=None,
                        affected_downstream=0,
                    )
                )

        # Detect column additions (in observed but not in contract)
        for col_name in observed_columns:
            if col_name not in contract_columns:
                observed_col = observed_columns[col_name]
                drifts.append(
                    ColumnDrift(
                        column_name=col_name,
                        drift_type=DriftType.COLUMN_ADDED,
                        severity=DriftSeverity.INFO,
                        old_value=None,
                        new_value=observed_col.dtype.value,
                        affected_downstream=0,
                    )
                )

        # Detect type changes and nullability changes for shared columns
        for col_name in contract_columns:
            if col_name in observed_columns:
                contract_col = contract_columns[col_name]
                observed_col = observed_columns[col_name]

                # Type change detection
                if contract_col.dtype != observed_col.dtype:
                    severity = self._classify_type_change_severity(
                        contract_col.dtype.value, observed_col.dtype.value
                    )
                    drifts.append(
                        ColumnDrift(
                            column_name=col_name,
                            drift_type=DriftType.TYPE_CHANGED,
                            severity=severity,
                            old_value=contract_col.dtype.value,
                            new_value=observed_col.dtype.value,
                            affected_downstream=0,
                        )
                    )

                # Nullability change detection
                if contract_col.nullable != observed_col.nullable:
                    severity = self._classify_nullability_change_severity(
                        contract_nullable=contract_col.nullable,
                        observed_nullable=observed_col.nullable,
                    )
                    drifts.append(
                        ColumnDrift(
                            column_name=col_name,
                            drift_type=DriftType.NULLABILITY_CHANGED,
                            severity=severity,
                            old_value=str(contract_col.nullable),
                            new_value=str(observed_col.nullable),
                            affected_downstream=0,
                        )
                    )

        # Compute overall severity, auto_evolvable, and requires_human_review
        overall_severity = self._compute_overall_severity(drifts)
        auto_evolvable = self._compute_auto_evolvable(drifts)
        requires_human_review = self._compute_requires_human_review(drifts)

        return DriftReport(
            dataset_id=contract.dataset_id,
            contract_version=contract.version,
            detected_at=datetime.now(timezone.utc),
            drifts=drifts,
            overall_severity=overall_severity,
            auto_evolvable=auto_evolvable,
            requires_human_review=requires_human_review,
        )

    def _classify_removal_severity(self, col: ColumnContract) -> DriftSeverity:
        """Classify severity for a removed column.

        - CRITICAL if column is primary_key or non-nullable
        - WARNING if column is nullable (and not primary_key)
        """
        if col.primary_key or not col.nullable:
            return DriftSeverity.CRITICAL
        return DriftSeverity.WARNING

    def _classify_type_change_severity(
        self, old_type: str, new_type: str
    ) -> DriftSeverity:
        """Classify severity for a type change using width ordering.

        - Narrowing (wider → narrower): CRITICAL
        - Widening (narrower → wider): WARNING
        - Types not in width order: default to CRITICAL (unknown transition)
        """
        old_width = TYPE_WIDTH_ORDER.get(old_type)
        new_width = TYPE_WIDTH_ORDER.get(new_type)

        # If either type is not in the width order, treat as CRITICAL
        if old_width is None or new_width is None:
            return DriftSeverity.CRITICAL

        if new_width < old_width:
            # Narrowing: e.g. STRING → INTEGER
            return DriftSeverity.CRITICAL
        else:
            # Widening: e.g. INTEGER → STRING
            return DriftSeverity.WARNING

    def _classify_nullability_change_severity(
        self, contract_nullable: bool, observed_nullable: bool
    ) -> DriftSeverity:
        """Classify severity for a nullability change.

        - non-nullable → nullable: CRITICAL
        - nullable → non-nullable: WARNING
        """
        if not contract_nullable and observed_nullable:
            # non-nullable → nullable: CRITICAL
            return DriftSeverity.CRITICAL
        else:
            # nullable → non-nullable: WARNING
            return DriftSeverity.WARNING

    def _compute_overall_severity(self, drifts: list[ColumnDrift]) -> DriftSeverity:
        """Compute overall severity as max across all drifts.

        Uses ordering INFO < WARNING < CRITICAL.
        If no drifts, defaults to INFO.
        """
        if not drifts:
            return DriftSeverity.INFO
        return max(d.severity for d in drifts)

    def _compute_auto_evolvable(self, drifts: list[ColumnDrift]) -> bool:
        """Determine if all drifts are auto-evolvable.

        auto_evolvable is true iff ALL drifts are INFO severity.
        """
        if not drifts:
            return True
        return all(d.severity == DriftSeverity.INFO for d in drifts)

    def _compute_requires_human_review(self, drifts: list[ColumnDrift]) -> bool:
        """Determine if human review is required.

        requires_human_review is true iff ANY drift is CRITICAL severity.
        """
        return any(d.severity == DriftSeverity.CRITICAL for d in drifts)
