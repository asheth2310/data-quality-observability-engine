"use client";

import { useCallback, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { lineageNodes, lineageEdges } from "@/lib/mock-data";

const datasetColors: Record<string, string> = {
  payments: "#3b82f6",
  marketing: "#f59e0b",
  customers: "#10b981",
  supply_chain: "#a855f7",
};

const typePositions: Record<string, { x: number; col: number }> = {
  source: { x: 0, col: 0 },
  staging: { x: 300, col: 1 },
  warehouse: { x: 600, col: 2 },
  mart: { x: 900, col: 3 },
};

function CustomNode({ data }: { data: { label: string; color: string; type: string } }) {
  return (
    <div
      className="px-3 py-2 rounded-lg border text-xs font-medium shadow-lg min-w-[160px] text-center"
      style={{
        backgroundColor: `${data.color}15`,
        borderColor: `${data.color}50`,
        color: data.color,
      }}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-60 mb-0.5">
        {data.type}
      </div>
      <div className="text-text-primary text-xs font-medium">{data.label}</div>
    </div>
  );
}

const nodeTypes = { custom: CustomNode };

export function LineageGraph() {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const nodes: Node[] = useMemo(() => {
    const typeCounters: Record<string, number> = {};

    return lineageNodes.map((node) => {
      const pos = typePositions[node.type] || { x: 0, col: 0 };
      const color = datasetColors[node.dataset] || "#94a3b8";

      if (!typeCounters[node.type]) typeCounters[node.type] = 0;
      const yOffset = typeCounters[node.type] * 120;
      typeCounters[node.type]++;

      const matchesSearch =
        !searchQuery ||
        node.label.toLowerCase().includes(searchQuery.toLowerCase());

      return {
        id: node.id,
        type: "custom",
        position: { x: pos.x, y: 50 + yOffset },
        data: { label: node.label, color, type: node.type },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          opacity: searchQuery && !matchesSearch ? 0.2 : 1,
          transition: "opacity 200ms ease",
        },
      };
    });
  }, [searchQuery]);

  const edges: Edge[] = useMemo(() => {
    return lineageEdges.map((edge) => {
      const isHighlighted =
        selectedNode &&
        (edge.source === selectedNode || edge.target === selectedNode);

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: edge.confidence > 0.95,
        style: {
          stroke: isHighlighted ? "#3b82f6" : edge.confidence > 0.9 ? "#475569" : "#334155",
          strokeWidth: isHighlighted ? 2.5 : 1.5,
          opacity: selectedNode && !isHighlighted ? 0.2 : 1,
          transition: "all 200ms ease",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isHighlighted ? "#3b82f6" : "#475569",
          width: 16,
          height: 16,
        },
        label: edge.confidence < 0.95 ? `${(edge.confidence * 100).toFixed(0)}%` : undefined,
        labelStyle: { fill: "#94a3b8", fontSize: 10 },
        labelBgStyle: { fill: "#1e293b", fillOpacity: 0.8 },
      };
    });
  }, [selectedNode]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode((prev) => (prev === node.id ? null : node.id));
  }, []);

  const downstreamCount = useMemo(() => {
    if (!selectedNode) return 0;
    const visited = new Set<string>();
    const queue = [selectedNode];
    while (queue.length > 0) {
      const current = queue.shift()!;
      lineageEdges.forEach((edge) => {
        if (edge.source === current && !visited.has(edge.target)) {
          visited.add(edge.target);
          queue.push(edge.target);
        }
      });
    }
    return visited.size;
  }, [selectedNode]);

  return (
    <div className="h-full w-full relative">
      {/* Search & info bar */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
        <input
          type="text"
          placeholder="Filter by dataset name..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-9 px-3 rounded-lg bg-surface border border-border text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/50 w-56"
          aria-label="Filter lineage graph by dataset name"
        />
        {selectedNode && (
          <div className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-text-secondary animate-fade-in">
            <span className="text-text-primary font-medium">{downstreamCount}</span>{" "}
            downstream dependencies
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-10 bg-surface border border-border rounded-lg p-3 space-y-1.5">
        <p className="text-[10px] uppercase tracking-wider text-text-secondary font-medium mb-2">
          Datasets
        </p>
        {Object.entries(datasetColors).map(([name, color]) => (
          <div key={name} className="flex items-center gap-2">
            <span
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: color }}
              aria-hidden="true"
            />
            <span className="text-xs text-text-secondary capitalize">{name.replace("_", " ")}</span>
          </div>
        ))}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.3}
        maxZoom={2}
      >
        <Background color="#334155" gap={20} size={1} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(node) => node.data?.color || "#475569"}
          maskColor="rgba(15, 23, 42, 0.7)"
          style={{ borderRadius: 8 }}
        />
      </ReactFlow>
    </div>
  );
}
