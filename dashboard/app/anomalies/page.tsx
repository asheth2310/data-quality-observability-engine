"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { SeverityBadge } from "@/components/severity-badge";
import { anomalies, anomalyScoreDistribution } from "@/lib/mock-data";
import { formatRelativeTime } from "@/lib/utils";

type SeverityFilter = "all" | "critical" | "warning" | "info";

export default function AnomaliesPage() {
  const [filter, setFilter] = useState<SeverityFilter>("all");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const filteredAnomalies =
    filter === "all"
      ? anomalies
      : anomalies.filter((a) => a.severity === filter);

  const tabs: { value: SeverityFilter; label: string; count: number }[] = [
    { value: "all", label: "All", count: anomalies.length },
    { value: "critical", label: "Critical", count: anomalies.filter((a) => a.severity === "critical").length },
    { value: "warning", label: "Warning", count: anomalies.filter((a) => a.severity === "warning").length },
    { value: "info", label: "Info", count: anomalies.filter((a) => a.severity === "info").length },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Anomaly Detection</h1>
        <p className="text-sm text-text-secondary mt-1">
          Statistical anomalies detected across monitored datasets
        </p>
      </div>

      {/* Score distribution chart */}
      <div className="card">
        <h2 className="text-sm font-medium text-text-secondary mb-4">
          Anomaly Score Distribution
        </h2>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={anomalyScoreDistribution} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis
                dataKey="range"
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                axisLine={{ stroke: "#334155" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  fontSize: "12px",
                }}
                cursor={{ fill: "rgba(59, 130, 246, 0.05)" }}
              />
              <Bar
                dataKey="count"
                fill="#3b82f6"
                radius={[4, 4, 0, 0]}
                animationDuration={300}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 bg-surface border border-border rounded-lg p-1 w-fit" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setFilter(tab.value)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors duration-150 min-h-[44px] ${
              filter === tab.value
                ? "bg-primary/10 text-primary"
                : "text-text-secondary hover:text-text-primary"
            }`}
            role="tab"
            aria-selected={filter === tab.value}
            aria-controls="anomalies-table"
          >
            {tab.label}
            <span className="ml-1.5 text-xs opacity-70">({tab.count})</span>
          </button>
        ))}
      </div>

      {/* Anomalies table */}
      <div id="anomalies-table" className="overflow-x-auto scrollbar-thin rounded-xl border border-border" role="tabpanel">
        <table className="w-full text-sm" role="grid" aria-label="Detected anomalies">
          <thead>
            <tr className="border-b border-border bg-background/50">
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Dataset</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Column</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Type</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Severity</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Score</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Confidence</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Detected</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredAnomalies.map((anomaly) => (
              <>
                <tr
                  key={anomaly.id}
                  className={`cursor-pointer hover:bg-white/[0.02] transition-colors duration-150 ${
                    expandedRow === anomaly.id ? "bg-primary/[0.03]" : ""
                  }`}
                  onClick={() =>
                    setExpandedRow(expandedRow === anomaly.id ? null : anomaly.id)
                  }
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setExpandedRow(expandedRow === anomaly.id ? null : anomaly.id);
                    }
                  }}
                  aria-expanded={expandedRow === anomaly.id}
                >
                  <td className="px-4 py-3 font-mono text-xs text-text-primary">
                    {anomaly.dataset}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-text-secondary">
                    {anomaly.column}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary">
                    {anomaly.type.replace("_", " ")}
                  </td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={anomaly.severity} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-text-primary">
                    {anomaly.score.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-text-secondary">
                    {(anomaly.confidence * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary">
                    {formatRelativeTime(new Date(anomaly.detected_at))}
                  </td>
                </tr>
                {expandedRow === anomaly.id && (
                  <tr key={`${anomaly.id}-expanded`}>
                    <td colSpan={7} className="px-4 py-4 bg-background/30 border-t border-border">
                      <div className="animate-fade-in">
                        <p className="text-xs font-medium text-text-secondary mb-1">Context</p>
                        <p className="text-sm text-text-primary leading-relaxed">
                          {anomaly.context}
                        </p>
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
