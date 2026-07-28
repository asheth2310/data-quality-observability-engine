"use client";

import { useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Shield,
  AlertTriangle,
  Info,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SeverityBadge } from "@/components/severity-badge";
import { formatRelativeTime } from "@/lib/utils";
import { alerts } from "@/lib/mock-data";

export default function AlertsPage() {
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState<Set<string>>(
    new Set(alerts.filter((a) => a.acknowledged).map((a) => a.id))
  );
  const [showSuppressed, setShowSuppressed] = useState(false);

  const activeAlerts = alerts.filter((a) => !a.suppressed);
  const suppressedAlerts = alerts.filter((a) => a.suppressed);

  const handleAcknowledge = (alertId: string) => {
    setAcknowledgedAlerts((prev) => {
      const next = new Set(prev);
      next.add(alertId);
      return next;
    });
  };

  const getEscalationLabel = (level: number) => {
    switch (level) {
      case 0:
        return "Auto-resolved";
      case 1:
        return "L1 — On-call Engineer";
      case 2:
        return "L2 — Team Lead";
      case 3:
        return "L3 — Engineering Manager";
      default:
        return `L${level}`;
    }
  };

  const getEscalationColor = (level: number) => {
    switch (level) {
      case 0:
        return "text-text-secondary";
      case 1:
        return "text-primary";
      case 2:
        return "text-warning";
      case 3:
        return "text-critical";
      default:
        return "text-text-secondary";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Alert Management</h1>
        <p className="text-sm text-text-secondary mt-1">
          Active alerts, escalation chains, and acknowledgment tracking
        </p>
      </div>

      {/* Escalation chain visualization */}
      <div className="card">
        <h2 className="text-sm font-medium text-text-secondary mb-4">
          Escalation Chain
        </h2>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {[0, 1, 2, 3].map((level) => {
            const count = activeAlerts.filter((a) => a.escalation_level === level).length;
            return (
              <div key={level} className="flex items-center gap-2">
                <div
                  className={cn(
                    "flex items-center gap-2 px-4 py-2.5 rounded-lg border min-w-[160px]",
                    level === 0 && "border-border bg-surface",
                    level === 1 && "border-primary/30 bg-primary/5",
                    level === 2 && "border-warning/30 bg-warning/5",
                    level === 3 && "border-critical/30 bg-critical/5"
                  )}
                >
                  <Shield
                    className={cn("w-4 h-4", getEscalationColor(level))}
                    aria-hidden="true"
                  />
                  <div>
                    <p className={cn("text-xs font-medium", getEscalationColor(level))}>
                      {getEscalationLabel(level)}
                    </p>
                    <p className="text-xs text-text-secondary">
                      {count} alert{count !== 1 ? "s" : ""}
                    </p>
                  </div>
                </div>
                {level < 3 && (
                  <ChevronRight className="w-4 h-4 text-text-secondary flex-shrink-0" aria-hidden="true" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Active alerts table */}
      <div className="overflow-x-auto scrollbar-thin rounded-xl border border-border">
        <table className="w-full text-sm" aria-label="Active alerts">
          <thead>
            <tr className="border-b border-border bg-background/50">
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Severity</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Dataset</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Type</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Message</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Escalation</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Created</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider" scope="col">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {activeAlerts.map((alert) => {
              const isAcknowledged = acknowledgedAlerts.has(alert.id);
              return (
                <tr
                  key={alert.id}
                  className={cn(
                    "transition-colors duration-150",
                    isAcknowledged ? "opacity-60" : "hover:bg-white/[0.02]"
                  )}
                >
                  <td className="px-4 py-3">
                    <SeverityBadge severity={alert.severity} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-text-primary">
                    {alert.dataset.split(".").slice(-1)[0]}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary capitalize">
                    {alert.type.replace(/_/g, " ")}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-primary max-w-[300px] truncate">
                    {alert.message}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn("text-xs font-medium", getEscalationColor(alert.escalation_level))}>
                      L{alert.escalation_level}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
                    {formatRelativeTime(new Date(alert.created_at))}
                  </td>
                  <td className="px-4 py-3">
                    {isAcknowledged ? (
                      <span className="flex items-center gap-1 text-xs text-success">
                        <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
                        Ack&apos;d
                      </span>
                    ) : (
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20 transition-colors duration-150 min-h-[44px] min-w-[44px]"
                        aria-label={`Acknowledge alert: ${alert.message}`}
                      >
                        Acknowledge
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Suppressed/correlated alerts */}
      <div className="card">
        <button
          onClick={() => setShowSuppressed(!showSuppressed)}
          className="flex items-center gap-2 w-full text-left min-h-[44px]"
          aria-expanded={showSuppressed}
          aria-controls="suppressed-section"
        >
          {showSuppressed ? (
            <ChevronDown className="w-4 h-4 text-text-secondary" aria-hidden="true" />
          ) : (
            <ChevronRight className="w-4 h-4 text-text-secondary" aria-hidden="true" />
          )}
          <span className="text-sm font-medium text-text-secondary">
            Suppressed / Correlated Alerts
          </span>
          <span className="text-xs text-text-secondary ml-auto">
            {suppressedAlerts.length} suppressed
          </span>
        </button>

        {showSuppressed && (
          <div id="suppressed-section" className="mt-4 space-y-2 animate-fade-in">
            {suppressedAlerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-background/50 border border-border opacity-70"
              >
                {alert.severity === "critical" && (
                  <AlertTriangle className="w-3.5 h-3.5 text-critical flex-shrink-0" aria-hidden="true" />
                )}
                {alert.severity === "warning" && (
                  <AlertTriangle className="w-3.5 h-3.5 text-warning flex-shrink-0" aria-hidden="true" />
                )}
                {alert.severity === "info" && (
                  <Info className="w-3.5 h-3.5 text-primary flex-shrink-0" aria-hidden="true" />
                )}
                <span className="text-xs text-text-secondary flex-1 truncate">
                  {alert.message}
                </span>
                <span className="text-[10px] text-text-secondary whitespace-nowrap">
                  {formatRelativeTime(new Date(alert.created_at))}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
