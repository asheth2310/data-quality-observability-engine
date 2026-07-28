"use client";

import {
  AlertTriangle,
  Database,
  Clock,
  Wrench,
  Bell,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";
import { type ActivityEvent } from "@/lib/mock-data";

const typeIcons: Record<string, LucideIcon> = {
  anomaly: AlertTriangle,
  schema: Database,
  freshness: Clock,
  healing: Wrench,
  alert: Bell,
};

const typeColors: Record<string, string> = {
  anomaly: "text-critical bg-critical/10",
  schema: "text-primary bg-primary/10",
  freshness: "text-warning bg-warning/10",
  healing: "text-success bg-success/10",
  alert: "text-warning bg-warning/10",
};

interface ActivityFeedProps {
  events: ActivityEvent[];
}

export function ActivityFeed({ events }: ActivityFeedProps) {
  return (
    <div className="space-y-1" role="feed" aria-label="Recent activity">
      {events.map((event) => {
        const Icon = typeIcons[event.type] || Bell;
        const colorClass = typeColors[event.type] || "text-text-secondary bg-surface";

        return (
          <article
            key={event.id}
            className="flex items-start gap-3 p-3 rounded-lg hover:bg-white/[0.02] transition-colors duration-150"
          >
            <div
              className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5",
                colorClass
              )}
            >
              <Icon className="w-3.5 h-3.5" aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-text-primary leading-snug">
                {event.message}
              </p>
              <time
                className="text-xs text-text-secondary mt-1 block"
                dateTime={event.timestamp}
              >
                {formatRelativeTime(new Date(event.timestamp))}
              </time>
            </div>
            {event.severity && (
              <span
                className={cn(
                  "w-2 h-2 rounded-full flex-shrink-0 mt-2",
                  event.severity === "critical" && "bg-critical",
                  event.severity === "warning" && "bg-warning",
                  event.severity === "info" && "bg-primary"
                )}
                aria-label={`${event.severity} severity`}
              />
            )}
          </article>
        );
      })}
    </div>
  );
}
