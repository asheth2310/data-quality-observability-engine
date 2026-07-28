import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const getColors = () => {
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
      case "success":
        return "text-success bg-success/10 border-success/30";
      case "failed":
        return "text-critical bg-critical/10 border-critical/30";
      case "in_progress":
        return "text-primary bg-primary/10 border-primary/30";
      default:
        return "text-text-secondary bg-surface border-border";
    }
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border capitalize",
        getColors(),
        className
      )}
      role="status"
      aria-label={`Status: ${status}`}
    >
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          status === "healthy" && "bg-success",
          status === "warning" && "bg-warning",
          (status === "critical" || status === "breached") && "bg-critical",
          status === "success" && "bg-success",
          status === "failed" && "bg-critical",
          status === "in_progress" && "bg-primary animate-pulse"
        )}
        aria-hidden="true"
      />
      {status.replace("_", " ")}
    </span>
  );
}
