"""Unit tests for the Lineage Graph Engine."""

import pytest

from data_quality_engine.models import (
    ColumnRef,
    DatasetId,
    TransformationType,
)
from data_quality_engine.services.lineage_engine import (
    CONFIDENCE_SCORES,
    ColumnNotFoundError,
    CycleDetectedError,
    InferenceMethod,
    LineageGraphEngine,
)
from data_quality_engine.storage import Neo4jGraphStore


@pytest.fixture
def graph_store() -> Neo4jGraphStore:
    """Create a fresh in-memory graph store for each test."""
    return Neo4jGraphStore()


@pytest.fixture
def engine(graph_store: Neo4jGraphStore) -> LineageGraphEngine:
    """Create a LineageGraphEngine backed by an in-memory store."""
    return LineageGraphEngine(graph_store)


@pytest.fixture
def dataset_a() -> DatasetId:
    return DatasetId(namespace="warehouse.public.orders", version=1)


@pytest.fixture
def dataset_b() -> DatasetId:
    return DatasetId(namespace="warehouse.public.order_summary", version=1)


@pytest.fixture
def col_a1(dataset_a: DatasetId) -> ColumnRef:
    return ColumnRef(dataset_id=dataset_a, column_name="amount")


@pytest.fixture
def col_a2(dataset_a: DatasetId) -> ColumnRef:
    return ColumnRef(dataset_id=dataset_a, column_name="currency")


@pytest.fixture
def col_b1(dataset_b: DatasetId) -> ColumnRef:
    return ColumnRef(dataset_id=dataset_b, column_name="total_amount")


@pytest.fixture
def col_b2(dataset_b: DatasetId) -> ColumnRef:
    return ColumnRef(dataset_id=dataset_b, column_name="currency_code")


class TestRegisterTransformation:
    """Tests for registering transformations between existing columns."""

    @pytest.mark.asyncio
    async def test_register_transformation_success(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Can register a transformation between existing columns."""
        # Add columns to graph first
        await engine.add_column(col_a1)
        await engine.add_column(col_b1)

        # Register transformation
        edges = await engine.register_transformation(
            source_columns=[col_a1],
            target_columns=[col_b1],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="etl-pipeline-1",
            user_id="user-123",
            inference_method=InferenceMethod.PARSED_SQL,
        )

        assert len(edges) == 1
        edge = edges[0]
        assert edge.source == col_a1
        assert edge.target == col_b1
        assert edge.transformation_type == TransformationType.DERIVED
        assert edge.pipeline_id == "etl-pipeline-1"
        assert edge.confidence == 1.0
        assert edge.last_observed is not None

    @pytest.mark.asyncio
    async def test_register_multiple_source_to_target(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_a2: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Can register transformation with multiple sources and one target."""
        await engine.add_column(col_a1)
        await engine.add_column(col_a2)
        await engine.add_column(col_b1)

        edges = await engine.register_transformation(
            source_columns=[col_a1, col_a2],
            target_columns=[col_b1],
            transformation_type=TransformationType.AGGREGATED,
            pipeline_id="agg-pipeline",
            user_id="user-456",
        )

        # Should create 2 edges (each source -> target)
        assert len(edges) == 2
        sources = {e.source for e in edges}
        assert col_a1 in sources
        assert col_a2 in sources
        for edge in edges:
            assert edge.target == col_b1


class TestCycleDetection:
    """Tests for DAG validation - rejecting edges that would create cycles."""

    @pytest.mark.asyncio
    async def test_rejects_self_loop(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
    ) -> None:
        """Rejects an edge that would create a self-loop (A -> A)."""
        await engine.add_column(col_a1)

        with pytest.raises(CycleDetectedError) as exc_info:
            await engine.register_transformation(
                source_columns=[col_a1],
                target_columns=[col_a1],
                transformation_type=TransformationType.DIRECT,
                pipeline_id="pipeline-x",
                user_id="user-1",
            )

        assert col_a1 in exc_info.value.cycle_nodes

    @pytest.mark.asyncio
    async def test_rejects_cycle_two_nodes(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Rejects edge that would create a cycle: A -> B -> A."""
        await engine.add_column(col_a1)
        await engine.add_column(col_b1)

        # First edge: A -> B (OK)
        await engine.register_transformation(
            source_columns=[col_a1],
            target_columns=[col_b1],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-1",
            user_id="user-1",
        )

        # Second edge: B -> A (would create cycle)
        with pytest.raises(CycleDetectedError) as exc_info:
            await engine.register_transformation(
                source_columns=[col_b1],
                target_columns=[col_a1],
                transformation_type=TransformationType.DERIVED,
                pipeline_id="pipe-2",
                user_id="user-1",
            )

        # The error should identify the cycle nodes
        assert len(exc_info.value.cycle_nodes) >= 2

    @pytest.mark.asyncio
    async def test_rejects_cycle_three_nodes(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
        col_b2: ColumnRef,
    ) -> None:
        """Rejects edge that would create a 3-node cycle: A -> B -> C -> A."""
        await engine.add_column(col_a1)
        await engine.add_column(col_b1)
        await engine.add_column(col_b2)

        # A -> B
        await engine.register_transformation(
            source_columns=[col_a1],
            target_columns=[col_b1],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-1",
            user_id="user-1",
        )

        # B -> C
        await engine.register_transformation(
            source_columns=[col_b1],
            target_columns=[col_b2],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-2",
            user_id="user-1",
        )

        # C -> A would create cycle
        with pytest.raises(CycleDetectedError):
            await engine.register_transformation(
                source_columns=[col_b2],
                target_columns=[col_a1],
                transformation_type=TransformationType.DERIVED,
                pipeline_id="pipe-3",
                user_id="user-1",
            )


class TestColumnExistenceValidation:
    """Tests for rejecting edges with non-existent source/target columns."""

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_source(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Rejects transformation when source column doesn't exist in graph."""
        # Only add target, not source
        await engine.add_column(col_b1)

        with pytest.raises(ColumnNotFoundError) as exc_info:
            await engine.register_transformation(
                source_columns=[col_a1],
                target_columns=[col_b1],
                transformation_type=TransformationType.DIRECT,
                pipeline_id="pipe-1",
                user_id="user-1",
            )

        assert col_a1 in exc_info.value.missing_columns

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_target(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Rejects transformation when target column doesn't exist in graph."""
        # Only add source, not target
        await engine.add_column(col_a1)

        with pytest.raises(ColumnNotFoundError) as exc_info:
            await engine.register_transformation(
                source_columns=[col_a1],
                target_columns=[col_b1],
                transformation_type=TransformationType.DIRECT,
                pipeline_id="pipe-1",
                user_id="user-1",
            )

        assert col_b1 in exc_info.value.missing_columns

    @pytest.mark.asyncio
    async def test_rejects_both_nonexistent(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Rejects when both source and target don't exist."""
        with pytest.raises(ColumnNotFoundError) as exc_info:
            await engine.register_transformation(
                source_columns=[col_a1],
                target_columns=[col_b1],
                transformation_type=TransformationType.DIRECT,
                pipeline_id="pipe-1",
                user_id="user-1",
            )

        # Both columns should be reported as missing
        assert len(exc_info.value.missing_columns) == 2


class TestConfidenceScores:
    """Tests for correct confidence score assignment based on inference method."""

    @pytest.mark.asyncio
    async def test_parsed_sql_confidence(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Parsed SQL gets confidence score of 1.0."""
        await engine.add_column(col_a1)
        await engine.add_column(col_b1)

        edges = await engine.register_transformation(
            source_columns=[col_a1],
            target_columns=[col_b1],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-1",
            user_id="user-1",
            inference_method=InferenceMethod.PARSED_SQL,
        )

        assert edges[0].confidence == 1.0

    @pytest.mark.asyncio
    async def test_schema_name_matching_confidence(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Schema-name matching gets confidence score of 0.9."""
        await engine.add_column(col_a1)
        await engine.add_column(col_b1)

        edges = await engine.register_transformation(
            source_columns=[col_a1],
            target_columns=[col_b1],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-1",
            user_id="user-1",
            inference_method=InferenceMethod.SCHEMA_NAME_MATCHING,
        )

        assert edges[0].confidence == 0.9

    @pytest.mark.asyncio
    async def test_data_type_matching_confidence(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Data-type matching gets confidence score of 0.7."""
        await engine.add_column(col_a1)
        await engine.add_column(col_b1)

        edges = await engine.register_transformation(
            source_columns=[col_a1],
            target_columns=[col_b1],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-1",
            user_id="user-1",
            inference_method=InferenceMethod.DATA_TYPE_MATCHING,
        )

        assert edges[0].confidence == 0.7

    @pytest.mark.asyncio
    async def test_heuristic_confidence(
        self,
        engine: LineageGraphEngine,
        col_a1: ColumnRef,
        col_b1: ColumnRef,
    ) -> None:
        """Heuristic matching gets confidence score of 0.5."""
        await engine.add_column(col_a1)
        await engine.add_column(col_b1)

        edges = await engine.register_transformation(
            source_columns=[col_a1],
            target_columns=[col_b1],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-1",
            user_id="user-1",
            inference_method=InferenceMethod.HEURISTIC,
        )

        assert edges[0].confidence == 0.5

    def test_confidence_score_lookup(self, engine: LineageGraphEngine) -> None:
        """Verify get_confidence_score returns correct values for all methods."""
        assert engine.get_confidence_score(InferenceMethod.PARSED_SQL) == 1.0
        assert engine.get_confidence_score(InferenceMethod.SCHEMA_NAME_MATCHING) == 0.9
        assert engine.get_confidence_score(InferenceMethod.DATA_TYPE_MATCHING) == 0.7
        assert engine.get_confidence_score(InferenceMethod.HEURISTIC) == 0.5


class TestAddColumn:
    """Tests for registering column nodes."""

    @pytest.mark.asyncio
    async def test_add_column(
        self,
        engine: LineageGraphEngine,
        graph_store: Neo4jGraphStore,
        col_a1: ColumnRef,
    ) -> None:
        """Can add a column to the graph."""
        await engine.add_column(col_a1)
        assert await graph_store.node_exists(col_a1) is True

    @pytest.mark.asyncio
    async def test_add_column_idempotent(
        self,
        engine: LineageGraphEngine,
        graph_store: Neo4jGraphStore,
        col_a1: ColumnRef,
    ) -> None:
        """Adding the same column twice does not error."""
        await engine.add_column(col_a1)
        await engine.add_column(col_a1)
        assert await graph_store.node_exists(col_a1) is True


class TestDownstreamImpact:
    """Tests for get_downstream_impact BFS traversal."""

    @pytest.mark.asyncio
    async def test_bfs_returns_correct_downstream_columns(
        self,
        engine: LineageGraphEngine,
        graph_store: Neo4jGraphStore,
    ) -> None:
        """BFS traversal returns all reachable downstream columns in level order."""
        # Build a graph: A -> B -> C, A -> D
        ds1 = DatasetId(namespace="warehouse.public.source", version=1)
        ds2 = DatasetId(namespace="warehouse.public.intermediate", version=1)
        ds3 = DatasetId(namespace="warehouse.public.target", version=1)

        col_a = ColumnRef(dataset_id=ds1, column_name="id")
        col_b = ColumnRef(dataset_id=ds2, column_name="source_id")
        col_c = ColumnRef(dataset_id=ds3, column_name="final_id")
        col_d = ColumnRef(dataset_id=ds2, column_name="alt_id")

        for col in [col_a, col_b, col_c, col_d]:
            await engine.add_column(col)

        # A -> B
        await engine.register_transformation(
            source_columns=[col_a],
            target_columns=[col_b],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-1",
            user_id="user-1",
        )
        # A -> D
        await engine.register_transformation(
            source_columns=[col_a],
            target_columns=[col_d],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-2",
            user_id="user-1",
        )
        # B -> C
        await engine.register_transformation(
            source_columns=[col_b],
            target_columns=[col_c],
            transformation_type=TransformationType.AGGREGATED,
            pipeline_id="pipe-3",
            user_id="user-1",
        )

        impact = await engine.get_downstream_impact(col_a)

        # Should find B, D at level 1 and C at level 2
        assert impact.total_downstream_count == 3
        assert len(impact.affected_columns) == 3

        # Level 1 columns (B and D) should come before level 2 (C)
        col_names = [c.column_name for c in impact.affected_columns]
        assert col_names.index("final_id") > col_names.index("source_id")
        assert col_names.index("final_id") > col_names.index("alt_id")

        # Check affected datasets
        ds_namespaces = {d.namespace for d in impact.affected_datasets}
        assert "warehouse.public.intermediate" in ds_namespaces
        assert "warehouse.public.target" in ds_namespaces

        # Check affected pipelines
        assert set(impact.affected_pipelines) == {"pipe-1", "pipe-2", "pipe-3"}

        # Root should be source column
        assert impact.root == col_a

    @pytest.mark.asyncio
    async def test_max_depth_is_respected(
        self,
        engine: LineageGraphEngine,
    ) -> None:
        """BFS traversal stops at max_depth and doesn't explore deeper."""
        # Build a chain: A -> B -> C -> D
        ds = DatasetId(namespace="warehouse.public.chain", version=1)
        col_a = ColumnRef(dataset_id=ds, column_name="a")
        col_b = ColumnRef(dataset_id=ds, column_name="b")
        col_c = ColumnRef(dataset_id=ds, column_name="c")
        col_d = ColumnRef(dataset_id=ds, column_name="d")

        for col in [col_a, col_b, col_c, col_d]:
            await engine.add_column(col)

        await engine.register_transformation(
            source_columns=[col_a],
            target_columns=[col_b],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-1",
            user_id="user-1",
        )
        await engine.register_transformation(
            source_columns=[col_b],
            target_columns=[col_c],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-2",
            user_id="user-1",
        )
        await engine.register_transformation(
            source_columns=[col_c],
            target_columns=[col_d],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-3",
            user_id="user-1",
        )

        # With max_depth=2, should find B (depth 1) and C (depth 2), but NOT D (depth 3)
        impact = await engine.get_downstream_impact(col_a, max_depth=2)

        assert impact.total_downstream_count == 2
        col_names = {c.column_name for c in impact.affected_columns}
        assert "b" in col_names
        assert "c" in col_names
        assert "d" not in col_names
        assert impact.max_depth == 2

    @pytest.mark.asyncio
    async def test_no_duplicates_in_results(
        self,
        engine: LineageGraphEngine,
    ) -> None:
        """BFS traversal returns each column at most once, even with multiple paths."""
        # Build a diamond graph: A -> B, A -> C, B -> D, C -> D
        ds = DatasetId(namespace="warehouse.public.diamond", version=1)
        col_a = ColumnRef(dataset_id=ds, column_name="a")
        col_b = ColumnRef(dataset_id=ds, column_name="b")
        col_c = ColumnRef(dataset_id=ds, column_name="c")
        col_d = ColumnRef(dataset_id=ds, column_name="d")

        for col in [col_a, col_b, col_c, col_d]:
            await engine.add_column(col)

        await engine.register_transformation(
            source_columns=[col_a],
            target_columns=[col_b],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-1",
            user_id="user-1",
        )
        await engine.register_transformation(
            source_columns=[col_a],
            target_columns=[col_c],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-2",
            user_id="user-1",
        )
        await engine.register_transformation(
            source_columns=[col_b],
            target_columns=[col_d],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-3",
            user_id="user-1",
        )
        await engine.register_transformation(
            source_columns=[col_c],
            target_columns=[col_d],
            transformation_type=TransformationType.DERIVED,
            pipeline_id="pipe-4",
            user_id="user-1",
        )

        impact = await engine.get_downstream_impact(col_a)

        # D should appear only once despite two paths (A->B->D and A->C->D)
        assert impact.total_downstream_count == 3
        col_names = [c.column_name for c in impact.affected_columns]
        assert col_names.count("d") == 1
        assert col_names.count("b") == 1
        assert col_names.count("c") == 1

    @pytest.mark.asyncio
    async def test_empty_impact_when_no_outgoing_edges(
        self,
        engine: LineageGraphEngine,
    ) -> None:
        """Returns empty ImpactGraph when source has no outgoing edges."""
        ds = DatasetId(namespace="warehouse.public.isolated", version=1)
        col_a = ColumnRef(dataset_id=ds, column_name="lonely")

        await engine.add_column(col_a)

        impact = await engine.get_downstream_impact(col_a)

        assert impact.total_downstream_count == 0
        assert impact.affected_columns == []
        assert impact.affected_datasets == []
        assert impact.affected_pipelines == []
        assert impact.root == col_a

    @pytest.mark.asyncio
    async def test_error_when_source_column_not_found(
        self,
        engine: LineageGraphEngine,
    ) -> None:
        """Raises ColumnNotFoundError when source column doesn't exist in graph."""
        ds = DatasetId(namespace="warehouse.public.nonexistent", version=1)
        col = ColumnRef(dataset_id=ds, column_name="ghost")

        with pytest.raises(ColumnNotFoundError) as exc_info:
            await engine.get_downstream_impact(col)

        assert col in exc_info.value.missing_columns

    @pytest.mark.asyncio
    async def test_max_depth_bounded_to_minimum_1(
        self,
        engine: LineageGraphEngine,
    ) -> None:
        """max_depth values below 1 are clamped to 1."""
        ds = DatasetId(namespace="warehouse.public.bounded", version=1)
        col_a = ColumnRef(dataset_id=ds, column_name="a")
        col_b = ColumnRef(dataset_id=ds, column_name="b")
        col_c = ColumnRef(dataset_id=ds, column_name="c")

        for col in [col_a, col_b, col_c]:
            await engine.add_column(col)

        await engine.register_transformation(
            source_columns=[col_a],
            target_columns=[col_b],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-1",
            user_id="user-1",
        )
        await engine.register_transformation(
            source_columns=[col_b],
            target_columns=[col_c],
            transformation_type=TransformationType.DIRECT,
            pipeline_id="pipe-2",
            user_id="user-1",
        )

        # With max_depth=0 (clamped to 1), should only find B
        impact = await engine.get_downstream_impact(col_a, max_depth=0)

        assert impact.total_downstream_count == 1
        assert impact.affected_columns[0].column_name == "b"
        assert impact.max_depth == 1

    @pytest.mark.asyncio
    async def test_max_depth_bounded_to_maximum_50(
        self,
        engine: LineageGraphEngine,
    ) -> None:
        """max_depth values above 50 are clamped to 50."""
        ds = DatasetId(namespace="warehouse.public.capped", version=1)
        col_a = ColumnRef(dataset_id=ds, column_name="a")

        await engine.add_column(col_a)

        impact = await engine.get_downstream_impact(col_a, max_depth=100)

        assert impact.max_depth == 50
