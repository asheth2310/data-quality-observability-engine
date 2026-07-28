import { cn } from "@/lib/utils";

interface SeverityBadgeProps {
  severity: "critical" | "warning" | "info";
  className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border",
        severity === "critical" && "text-critical bg-critical/10 border-critical/30",
        severity === "warning" && "text-warning bg-warning/10 border-warning/30",
        severity === "info" && "text-primary bg-primary/10 border-primary/30",
        className
      )}
      role="status"
      aria-label={`Severity: ${severity}`}
    >
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          severity === "critical" && "bg-critical",
          severity === "warning" && "bg-warning",
          severity === "info" && "bg-primary"
        )}
        aria-hidden="true"
      />
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  );
}
