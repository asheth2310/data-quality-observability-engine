"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import { formatRelativeTime } from "@/lib/utils";
import { freshnessEntries } from "@/lib/mock-data";

function CircularProgress({
  pct,
  status,
}: {
  pct: number;
  status: string;
}) {
  const radius = 32;
  const circumference = 2 * Math.PI * radius;
  const clampedPct = Math.min(pct, 120);
  const offset = circumference - (clampedPct / 120) * circumference;

  const getColor = () => {
    if (status === "breached") return "#f43f5e";
    if (status === "warning" || pct > 80) return "#f59e0b";
    return "#10b981";
  };

  return (
    <div className="relative w-20 h-20 flex items-center justify-center">
      <svg
        width="80"
        height="80"
        className="-rotate-90"
        role="img"
        aria-label={`SLA consumption: ${pct}%`}
      >
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke="#334155"
          strokeWidth="6"
        />
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke={getColor()}
          strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500 ease-out"
        />
      </svg>
      <span className="absolute text-sm font-bold text-text-primary">
        {pct}%
      </span>
    </div>
  );
}

export default function FreshnessPage() {
  const [selectedDataset, setSelectedDataset] = useState<string | null>(
    freshnessEntries[0].id
  );

  const selectedEntry = freshnessEntries.find((e) => e.id === selectedDataset);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Freshness SLA Monitor</h1>
        <p className="text-sm text-text-secondary mt-1">
          Dataset staleness tracking and SLA consumption
        </p>
      </div>

      {/* Dataset cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {freshnessEntries.map((entry) => (
          <button
            key={entry.id}
            onClick={() => setSelectedDataset(entry.id)}
            className={cn(
              "card text-left transition-all duration-200 min-h-[44px]",
              selectedDataset === entry.id && "ring-2 ring-primary/50 border-primary/30",
              entry.status === "warning" && "animate-pulse-glow",
              entry.status === "breached" && "border-critical/50"
            )}
            aria-pressed={selectedDataset === entry.id}
            aria-label={`${entry.dataset} - SLA ${entry.sla_consumed_pct}% consumed - Status: ${entry.status}`}
          >
            <div className="flex items-center gap-3">
              <CircularProgress pct={entry.sla_consumed_pct} status={entry.status} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono text-text-primary truncate">
                  {entry.dataset.split(".").slice(-1)[0]}
                </p>
                <p className="text-[10px] text-text-secondary mt-0.5 truncate">
                  {entry.dataset}
                </p>
                <div className="mt-2">
                  <StatusBadge status={entry.status} />
                </div>
                <p className="text-[10px] text-text-secondary mt-1.5">
                  Updated {formatRelativeTime(new Date(entry.last_updated))}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Staleness chart for selected dataset */}
      {selectedEntry && (
        <div className="card animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-text-secondary">
              Staleness History — <span className="text-text-primary font-mono">{selectedEntry.dataset}</span>
            </h2>
            <span className="text-xs text-text-secondary">
              SLA: {selectedEntry.sla_hours}h
            </span>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={selectedEntry.staleness_history}
                margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis
                  dataKey="time"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={{ stroke: "#334155" }}
                  tickLine={false}
                  interval={3}
                />
                <YAxis
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  domain={[0, 120]}
                  unit="%"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => [`${value.toFixed(0)}%`, "SLA Consumed"]}
                />
                <ReferenceLine
                  y={100}
                  stroke="#f43f5e"
                  strokeDasharray="4 4"
                  label={{
                    value: "SLA Breach",
                    fill: "#f43f5e",
                    fontSize: 10,
                    position: "right",
                  }}
                />
                <ReferenceLine
                  y={80}
                  stroke="#f59e0b"
                  strokeDasharray="4 4"
                  label={{
                    value: "Warning",
                    fill: "#f59e0b",
                    fontSize: 10,
                    position: "right",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="pct"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#3b82f6" }}
                  animationDuration={300}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
