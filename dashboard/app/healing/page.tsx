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
  Legend,
} from "recharts";
import { Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { DonutChart } from "@/components/donut-chart";
import { StatusBadge } from "@/components/status-badge";
import { formatRelativeTime } from "@/lib/utils";
import { healingActions, healingStrategyBreakdown } from "@/lib/mock-data";

type StrategyFilter = "all" | string;

export default function HealingPage() {
  const [filter, setFilter] = useState<StrategyFilter>("all");

  const strategies = [...new Set(healingActions.map((a) => a.strategy))];
  const filteredActions =
    filter === "all"
      ? healingActions
      : healingActions.filter((a) => a.strategy === filter);

  const successCount = healingActions.filter((a) => a.outcome === "success").length;
  const failedCount = healingActions.filter((a) => a.outcome === "failed").length;
  const totalCompleted = successCount + failedCount;

  const successRateData = [
    { name: "Success", value: successCount, color: "#10b981" },
    { name: "Failed", value: failedCount, color: "#f43f5e" },
  ];

  const getOutcomeIcon = (outcome: string) => {
    switch (outcome) {
      case "success":
        return <CheckCircle2 className="w-4 h-4 text-success" aria-hidden="true" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-critical" aria-hidden="true" />;
      case "in_progress":
        return <Loader2 className="w-4 h-4 text-primary animate-spin" aria-hidden="true" />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Self-Healing Activity</h1>
        <p className="text-sm text-text-secondary mt-1">
          Automated remediation actions and their outcomes
        </p>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Success rate donut */}
        <div className="card">
          <h2 className="text-sm font-medium text-text-secondary mb-4">
            Healing Success Rate
          </h2>
          <DonutChart
            data={successRateData}
            centerLabel="Success Rate"
            centerValue={`${totalCompleted > 0 ? Math.round((successCount / totalCompleted) * 100) : 0}%`}
          />
        </div>

        {/* Strategy breakdown */}
        <div className="card">
          <h2 className="text-sm font-medium text-text-secondary mb-4">
            Strategy Breakdown
          </h2>
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={healingStrategyBreakdown}
                layout="vertical"
                margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="strategy"
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={120}
                  tickFormatter={(value) => value.replace(/_/g, " ")}
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
                <Legend
                  verticalAlign="top"
                  height={30}
                  formatter={(value) => (
                    <span className="text-xs text-text-secondary capitalize">{value}</span>
                  )}
                />
                <Bar dataKey="success" fill="#10b981" radius={[0, 4, 4, 0]} name="Success" />
                <Bar dataKey="count" fill="#334155" radius={[0, 4, 4, 0]} name="Total" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Strategy filter */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by strategy">
        <button
          onClick={() => setFilter("all")}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors duration-150 min-h-[44px]",
            filter === "all"
              ? "bg-primary/10 text-primary border-primary/30"
              : "text-text-secondary border-border hover:border-primary/30"
          )}
        >
          All Strategies
        </button>
        {strategies.map((strategy) => (
          <button
            key={strategy}
            onClick={() => setFilter(strategy)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors duration-150 min-h-[44px] capitalize",
              filter === strategy
                ? "bg-primary/10 text-primary border-primary/30"
                : "text-text-secondary border-border hover:border-primary/30"
            )}
          >
            {strategy.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Healing timeline */}
      <div className="space-y-3">
        {filteredActions.map((action) => (
          <div
            key={action.id}
            className="card flex items-start gap-4 animate-slide-in"
          >
            <div className="mt-0.5">{getOutcomeIcon(action.outcome)}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 capitalize">
                  {action.strategy.replace(/_/g, " ")}
                </span>
                <span className="font-mono text-xs text-text-secondary">
                  {action.dataset}
                </span>
              </div>
              <p className="text-sm text-text-primary mt-1.5 leading-relaxed">
                {action.description}
              </p>
              <div className="flex items-center gap-4 mt-2">
                <StatusBadge status={action.outcome} />
                {action.duration_ms > 0 && (
                  <span className="flex items-center gap-1 text-xs text-text-secondary">
                    <Clock className="w-3 h-3" aria-hidden="true" />
                    {action.duration_ms >= 1000
                      ? `${(action.duration_ms / 1000).toFixed(1)}s`
                      : `${action.duration_ms}ms`}
                  </span>
                )}
                <time className="text-xs text-text-secondary">
                  {formatRelativeTime(new Date(action.executed_at))}
                </time>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
