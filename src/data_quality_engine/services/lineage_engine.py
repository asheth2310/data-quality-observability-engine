"""Lineage Graph Engine for column-level lineage tracking.

Maintains a directed acyclic graph of column-level data lineage in Neo4j,
enabling impact analysis, root cause tracing, and dependency-aware alerting.
"""

from collections import deque
from datetime import datetime, timezone
from enum import Enum

from data_quality_engine.models import (
    ColumnRef,
    DatasetId,
    ImpactGraph,
    LineageEdge,
    TransformationType,
)
from data_quality_engine.storage.interfaces import GraphStore


class InferenceMethod(str, Enum):
    """Method used to infer lineage relationships."""

    PARSED_SQL = "parsed_sql"
    SCHEMA_NAME_MATCHING = "schema_name_matching"
    DATA_TYPE_MATCHING = "data_type_matching"
    HEURISTIC = "heuristic"


# Confidence score mapping for each inference method
CONFIDENCE_SCORES: dict[InferenceMethod, float] = {
    InferenceMethod.PARSED_SQL: 1.0,
    InferenceMethod.SCHEMA_NAME_MATCHING: 0.9,
    InferenceMethod.DATA_TYPE_MATCHING: 0.7,
    InferenceMethod.HEURISTIC: 0.5,
}


class LineageValidationError(Exception):
    """Raised when a lineage operation fails validation."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CycleDetectedError(LineageValidationError):
    """Raised when adding an edge would create a cycle in the DAG."""

    def __init__(self, cycle_nodes: list[ColumnRef]) -> None:
        node_names = [
            f"{n.dataset_id.namespace}.{n.column_name}" for n in cycle_nodes
        ]
        message = f"Adding edge would create cycle involving nodes: {node_names}"
        super().__init__(message, details={"cycle_nodes": cycle_nodes})
        self.cycle_nodes = cycle_nodes


class ColumnNotFoundError(LineageValidationError):
    """Raised when a referenced column does not exist in the graph."""

    def __init__(self, missing_columns: list[ColumnRef]) -> None:
        col_names = [
            f"{c.dataset_id.namespace}.{c.column_name}" for c in missing_columns
        ]
        message = f"Column(s) not found in graph: {col_names}"
        super().__init__(message, details={"missing_columns": missing_columns})
        self.missing_columns = missing_columns


class LineageGraphEngine:
    """Column-level lineage tracking and impact analysis.

    Maintains a directed acyclic graph (DAG) of column-level data lineage,
    storing it in a GraphStore (Neo4j-backed). Provides methods for registering
    transformations, validating DAG integrity, and querying lineage.
    """

    def __init__(self, graph_store: GraphStore) -> None:
        """Initialize the engine with a graph store backend.

        Args:
            graph_store: The graph storage backend (e.g., Neo4jGraphStore).
        """
        self._store = graph_store

    async def add_column(self, column: ColumnRef) -> None:
        """Register a column node in the lineage graph.

        Args:
            column: The column reference to add.
        """
        await self._store.add_node(column)

    async def register_transformation(
        self,
        source_columns: list[ColumnRef],
        target_columns: list[ColumnRef],
        transformation_type: TransformationType,
        pipeline_id: str,
        user_id: str,
        inference_method: InferenceMethod = InferenceMethod.PARSED_SQL,
        transformation_expr: str | None = None,
    ) -> list[LineageEdge]:
        """Register a data transformation creating directed edges from sources to targets.

        Creates directed edges from each source column to each target column with
        the given transformation type, timestamp, and user ID. Validates that all
        source/target columns exist in the graph and that adding the edges would
        not create cycles in the DAG.

        Args:
            source_columns: List of source column references.
            target_columns: List of target column references.
            transformation_type: The type of transformation.
            pipeline_id: Identifier for the pipeline performing the transformation.
            user_id: Identifier of the user registering the transformation.
            inference_method: How the lineage was determined (affects confidence score).
            transformation_expr: Optional expression describing the transformation.

        Returns:
            List of created LineageEdge instances.

        Raises:
            ColumnNotFoundError: If any source or target column does not exist in the graph.
            CycleDetectedError: If adding any edge would create a cycle in the DAG.
        """
        # Validate that all referenced columns exist in the graph
        missing_columns: list[ColumnRef] = []
        for col in source_columns + target_columns:
            if not await self._store.node_exists(col):
                missing_columns.append(col)

        if missing_columns:
            raise ColumnNotFoundError(missing_columns)

        # Check for cycles: for each source->target pair, verify no cycle would form
        for source in source_columns:
            for target in target_columns:
                would_cycle = await self._store.has_cycle(source, target)
                if would_cycle:
                    # Identify the cycle nodes
                    cycle_nodes = await self._find_cycle_nodes(source, target)
                    raise CycleDetectedError(cycle_nodes)

        # All validations passed — create edges
        confidence = CONFIDENCE_SCORES[inference_method]
        timestamp = datetime.now(timezone.utc)

        created_edges: list[LineageEdge] = []
        for source in source_columns:
            for target in target_columns:
                edge = LineageEdge(
                    source=source,
                    target=target,
                    transformation_type=transformation_type,
                    transformation_expr=transformation_expr,
                    pipeline_id=pipeline_id,
                    confidence=confidence,
                    last_observed=timestamp,
                )
                await self._store.add_edge(edge)
                created_edges.append(edge)

        return created_edges

    async def _find_cycle_nodes(
        self, source: ColumnRef, target: ColumnRef
    ) -> list[ColumnRef]:
        """Find the nodes that form the cycle if edge source->target is added.

        The cycle is: target -> ... -> source -> target.
        We do BFS from target following forward edges until we reach source,
        then report the path as cycle nodes.
        """
        # BFS from target to find path back to source
        visited: dict[str, ColumnRef | None] = {}
        target_key = f"{target.dataset_id.namespace}:{target.column_name}"
        source_key = f"{source.dataset_id.namespace}:{source.column_name}"

        queue: deque[ColumnRef] = deque([target])
        visited[target_key] = None  # No parent for the start

        while queue:
            current = queue.popleft()
            current_key = f"{current.dataset_id.namespace}:{current.column_name}"

            # Get downstream neighbors from current
            downstream = await self._store.get_downstream(current, max_depth=1)
            for neighbor in downstream:
                neighbor_key = f"{neighbor.dataset_id.namespace}:{neighbor.column_name}"
                if neighbor_key not in visited:
                    visited[neighbor_key] = current
                    if neighbor_key == source_key:
                        # Found the path: reconstruct cycle
                        cycle = [source, target]
                        # Walk back from source's parent to target
                        node = current
                        while node is not None:
                            node_key = f"{node.dataset_id.namespace}:{node.column_name}"
                            if node_key == target_key:
                                break
                            cycle.insert(1, node)
                            parent = visited.get(node_key)
                            node = parent
                        return cycle
                    queue.append(neighbor)

        # Fallback: return source and target as cycle participants
        return [source, target]

    def get_confidence_score(self, inference_method: InferenceMethod) -> float:
        """Get the confidence score for a given inference method.

        Args:
            inference_method: The method used to infer lineage.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        return CONFIDENCE_SCORES[inference_method]

    async def get_downstream_impact(
        self, source_column: ColumnRef, max_depth: int = 10
    ) -> ImpactGraph:
        """Get all downstream columns affected by a source column via BFS traversal.

        Performs a breadth-first traversal of the lineage graph starting from
        source_column, collecting all reachable downstream columns within max_depth
        hops. Returns columns ordered by BFS level (closer columns first), with
        deterministic ordering within the same level.

        Args:
            source_column: The starting column for impact analysis.
            max_depth: Maximum traversal depth, bounded [1, 50]. Defaults to 10.

        Returns:
            ImpactGraph with all affected columns, datasets, and pipelines.

        Raises:
            ColumnNotFoundError: If source_column does not exist in the graph.
        """
        # Bound max_depth to [1, 50]
        max_depth = max(1, min(50, max_depth))

        # Validate source column exists
        if not await self._store.node_exists(source_column):
            raise ColumnNotFoundError([source_column])

        # BFS traversal with level tracking
        source_key = f"{source_column.dataset_id.namespace}:v{source_column.dataset_id.version}:{source_column.column_name}"
        visited: set[str] = {source_key}
        # Each entry: (column_key, ColumnRef, depth)
        queue: deque[tuple[str, ColumnRef, int]] = deque([(source_key, source_column, 0)])

        affected_columns: list[ColumnRef] = []
        affected_datasets_set: dict[str, DatasetId] = {}
        affected_pipelines_set: dict[str, str] = {}

        while queue:
            current_key, current_col, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Get outgoing edges from current node
            edges = await self._store.get_edges_from(current_col)

            # Sort edges for deterministic ordering within same level
            sorted_edges = sorted(
                edges,
                key=lambda e: (
                    e.target.dataset_id.namespace,
                    e.target.column_name,
                ),
            )

            for edge in sorted_edges:
                target = edge.target
                target_key = f"{target.dataset_id.namespace}:v{target.dataset_id.version}:{target.column_name}"

                # Collect pipeline info regardless of whether target was visited
                pipeline_key = edge.pipeline_id
                if pipeline_key not in affected_pipelines_set:
                    affected_pipelines_set[pipeline_key] = edge.pipeline_id

                if target_key not in visited:
                    visited.add(target_key)
                    affected_columns.append(target)

                    # Track affected datasets
                    ds_key = f"{target.dataset_id.namespace}:v{target.dataset_id.version}"
                    if ds_key not in affected_datasets_set:
                        affected_datasets_set[ds_key] = target.dataset_id

                    queue.append((target_key, target, depth + 1))

        return ImpactGraph(
            root=source_column,
            affected_columns=affected_columns,
            affected_datasets=list(affected_datasets_set.values()),
            affected_pipelines=list(affected_pipelines_set.values()),
            max_depth=max_depth,
            total_downstream_count=len(affected_columns),
        )
