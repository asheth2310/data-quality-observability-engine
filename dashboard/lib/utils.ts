import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

export function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
}

export function getSeverityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case "critical":
      return "text-critical bg-critical/10 border-critical/30";
    case "warning":
      return "text-warning bg-warning/10 border-warning/30";
    case "info":
      return "text-primary bg-primary/10 border-primary/30";
    default:
      return "text-text-secondary bg-surface border-border";
  }
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "healthy":
      return "text-success bg-success/10 border-success/30";
    case "warning":
      return "text-warning bg-warning/10 border-warning/30";
    case "critical":
    case "breached":
      return "text-critical bg-critical/10 border-critical/30";
    case "stale":
      return "text-warning bg-warning/10 border-warning/30";
    default:
      return "text-text-secondary bg-surface border-border";
  }
}
