"use client";

import { cn } from "@/lib/utils";
import { Sparkline } from "./sparkline";
import { type LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: { direction: "up" | "down"; value: string };
  sparklineData?: { day: string; value: number }[];
  accentColor?: string;
}

export function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  sparklineData,
  accentColor = "text-primary",
}: StatCardProps) {
  return (
    <div className="card group animate-fade-in">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-9 h-9 rounded-lg flex items-center justify-center",
              accentColor === "text-primary" && "bg-primary/10",
              accentColor === "text-warning" && "bg-warning/10",
              accentColor === "text-critical" && "bg-critical/10",
              accentColor === "text-success" && "bg-success/10"
            )}
          >
            <Icon
              className={cn("w-4.5 h-4.5", accentColor)}
              aria-hidden="true"
            />
          </div>
        </div>
        {trend && (
          <span
            className={cn(
              "text-xs font-medium px-2 py-0.5 rounded-full",
              trend.direction === "up"
                ? "text-critical bg-critical/10"
                : "text-success bg-success/10"
            )}
          >
            {trend.direction === "up" ? "↑" : "↓"} {trend.value}
          </span>
        )}
      </div>

      <p className="text-2xl font-bold text-text-primary mb-1">{value}</p>
      <p className="text-sm text-text-secondary">{title}</p>

      {sparklineData && (
        <div className="mt-3 h-10">
          <Sparkline data={sparklineData} color={accentColor} />
        </div>
      )}
    </div>
  );
}
