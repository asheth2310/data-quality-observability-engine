"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";
import { schemas, driftTimeline } from "@/lib/mock-data";

function DriftTypeBadge({ type }: { type: string | null }) {
  if (!type) {
    return (
      <span className="text-xs text-text-secondary italic">No drift</span>
    );
  }

  const colors: Record<string, string> = {
    COLUMN_ADDED: "text-success bg-success/10 border-success/30",
    TYPE_CHANGED: "text-warning bg-warning/10 border-warning/30",
    COLUMN_REMOVED: "text-critical bg-critical/10 border-critical/30",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border",
        colors[type] || "text-text-secondary bg-surface border-border"
      )}
    >
      {type.replace("_", " ")}
    </span>
  );
}

export default function SchemasPage() {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Schema Registry</h1>
        <p className="text-sm text-text-secondary mt-1">
          Schema contracts, evolution rules, and drift monitoring
        </p>
      </div>

      {/* Drift timeline chart */}
      <div className="card">
        <h2 className="text-sm font-medium text-text-secondary mb-4">
          Schema Drift Events (30 days)
        </h2>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={driftTimeline} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="driftGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                axisLine={{ stroke: "#334155" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  fontSize: "12px",
                }}
              />
              <Area
                type="monotone"
                dataKey="events"
                stroke="#f59e0b"
                strokeWidth={2}
                fill="url(#driftGradient)"
                dot={{ fill: "#f59e0b", r: 3 }}
                activeDot={{ r: 5, fill: "#f59e0b" }}
                animationDuration={300}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Schema table */}
      <div className="overflow-x-auto scrollbar-thin rounded-xl border border-border">
        <table className="w-full text-sm" aria-label="Schema registry">
          <thead>
            <tr className="border-b border-border bg-background/50">
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Dataset</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Version</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Evolution Rule</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Last Drift</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Drift Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {schemas.map((schema) => (
              <>
                <tr
                  key={schema.id}
                  className={`cursor-pointer hover:bg-white/[0.02] transition-colors duration-150 ${
                    expandedRow === schema.id ? "bg-primary/[0.03]" : ""
                  }`}
                  onClick={() =>
                    setExpandedRow(expandedRow === schema.id ? null : schema.id)
                  }
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setExpandedRow(expandedRow === schema.id ? null : schema.id);
                    }
                  }}
                  aria-expanded={expandedRow === schema.id}
                >
                  <td className="px-4 py-3 font-mono text-xs text-text-primary">
                    {schema.dataset}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-primary">
                    {schema.version}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary capitalize">
                    {schema.evolution_rule.replace("_", " ")}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary">
                    {formatRelativeTime(new Date(schema.last_drift))}
                  </td>
                  <td className="px-4 py-3">
                    <DriftTypeBadge type={schema.drift_type} />
                  </td>
                </tr>
                {expandedRow === schema.id && (
                  <tr key={`${schema.id}-expanded`}>
                    <td colSpan={5} className="px-4 py-4 bg-background/30 border-t border-border">
                      <div className="animate-fade-in">
                        <p className="text-xs font-medium text-text-secondary mb-3">
                          Schema Contract — {schema.columns.length} columns
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                          {schema.columns.map((col) => (
                            <div
                              key={col.name}
                              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface border border-border"
                            >
                              <span className="font-mono text-xs text-text-primary">
                                {col.name}
                              </span>
                              <span className="text-[10px] text-text-secondary ml-auto">
                                {col.type}
                              </span>
                              {col.nullable && (
                                <span className="text-[10px] text-warning">null</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
