"""Neo4j graph store implementation (in-memory for testing).

Implements GraphStore for storing lineage graph nodes (datasets/columns)
and directed edges (transformations). Uses in-memory adjacency lists
to allow testing without requiring a real Neo4j instance.
"""

from collections import deque

from data_quality_engine.models import (
    ColumnRef,
    LineageEdge,
)
from data_quality_engine.storage.interfaces import GraphStore


class Neo4jGraphStore(GraphStore):
    """In-memory implementation of GraphStore (to be backed by Neo4j).

    Uses dict-based adjacency lists for the lineage DAG.
    Nodes are ColumnRef instances, edges are LineageEdge instances.
    """

    def __init__(self) -> None:
        # Set of all known nodes (serialized as string keys for lookups)
        self._nodes: set[str] = set()
        # Forward adjacency: source_key -> list of (target_key, edge)
        self._forward: dict[str, list[tuple[str, LineageEdge]]] = {}
        # Reverse adjacency: target_key -> list of (source_key, edge)
        self._reverse: dict[str, list[tuple[str, LineageEdge]]] = {}

    def _column_key(self, column: ColumnRef) -> str:
        """Create a unique string key for a ColumnRef."""
        return f"{column.dataset_id.namespace}:v{column.dataset_id.version}:{column.column_name}"

    async def add_node(self, column: ColumnRef) -> None:
        """Add a column node to the graph."""
        key = self._column_key(column)
        self._nodes.add(key)
        if key not in self._forward:
            self._forward[key] = []
        if key not in self._reverse:
            self._reverse[key] = []

    async def node_exists(self, column: ColumnRef) -> bool:
        """Check if a column node exists in the graph."""
        return self._column_key(column) in self._nodes

    async def add_edge(self, edge: LineageEdge) -> None:
        """Add a directed edge to the lineage graph."""
        source_key = self._column_key(edge.source)
        target_key = self._column_key(edge.target)

        # Ensure both nodes exist
        self._nodes.add(source_key)
        self._nodes.add(target_key)

        if source_key not in self._forward:
            self._forward[source_key] = []
        if target_key not in self._reverse:
            self._reverse[target_key] = []

        # Add to forward and reverse adjacency
        self._forward[source_key].append((target_key, edge))
        self._reverse[target_key].append((source_key, edge))

    async def remove_edge(self, source: ColumnRef, target: ColumnRef) -> bool:
        """Remove an edge from the graph. Returns True if edge existed."""
        source_key = self._column_key(source)
        target_key = self._column_key(target)

        # Remove from forward adjacency
        forward_edges = self._forward.get(source_key, [])
        original_len = len(forward_edges)
        self._forward[source_key] = [
            (tk, e) for tk, e in forward_edges if tk != target_key
        ]
        removed_forward = len(self._forward[source_key]) < original_len

        # Remove from reverse adjacency
        reverse_edges = self._reverse.get(target_key, [])
        self._reverse[target_key] = [
            (sk, e) for sk, e in reverse_edges if sk != source_key
        ]

        return removed_forward

    async def get_downstream(self, source: ColumnRef, max_depth: int = 10) -> list[ColumnRef]:
        """Get all downstream columns reachable from source via BFS, up to max_depth."""
        source_key = self._column_key(source)
        if source_key not in self._nodes:
            return []

        visited: set[str] = {source_key}
        result: list[ColumnRef] = []
        queue: deque[tuple[str, int]] = deque([(source_key, 0)])

        while queue:
            current_key, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for neighbor_key, edge in self._forward.get(current_key, []):
                if neighbor_key not in visited:
                    visited.add(neighbor_key)
                    result.append(edge.target)
                    queue.append((neighbor_key, depth + 1))

        return result

    async def get_upstream(self, target: ColumnRef, max_depth: int = 10) -> list[ColumnRef]:
        """Get all upstream columns that lead to target via reverse BFS, up to max_depth."""
        target_key = self._column_key(target)
        if target_key not in self._nodes:
            return []

        visited: set[str] = {target_key}
        result: list[ColumnRef] = []
        queue: deque[tuple[str, int]] = deque([(target_key, 0)])

        while queue:
            current_key, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for neighbor_key, edge in self._reverse.get(current_key, []):
                if neighbor_key not in visited:
                    visited.add(neighbor_key)
                    result.append(edge.source)
                    queue.append((neighbor_key, depth + 1))

        return result

    async def has_cycle(self, source: ColumnRef, target: ColumnRef) -> bool:
        """Check if adding an edge from source to target would create a cycle.

        A cycle would be created if target can already reach source
        (i.e., source is downstream of target in the current graph).
        """
        target_key = self._column_key(target)
        source_key = self._column_key(source)

        # If source == target, it's a self-loop (cycle)
        if source_key == target_key:
            return True

        # BFS from target following forward edges to see if we can reach source
        visited: set[str] = {target_key}
        queue: deque[str] = deque([target_key])

        while queue:
            current = queue.popleft()
            for neighbor_key, _ in self._forward.get(current, []):
                if neighbor_key == source_key:
                    return True
                if neighbor_key not in visited:
                    visited.add(neighbor_key)
                    queue.append(neighbor_key)

        return False

    async def get_edges_from(self, source: ColumnRef) -> list[LineageEdge]:
        """Get all outgoing edges from a source column."""
        source_key = self._column_key(source)
        return [edge for _, edge in self._forward.get(source_key, [])]

    async def get_edges_to(self, target: ColumnRef) -> list[LineageEdge]:
        """Get all incoming edges to a target column."""
        target_key = self._column_key(target)
        return [edge for _, edge in self._reverse.get(target_key, [])]
