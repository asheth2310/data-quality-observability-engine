"use client";

import { cn } from "@/lib/utils";

interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (item: T) => void;
  expandedRow?: string | null;
  renderExpanded?: (item: T) => React.ReactNode;
  getRowId: (item: T) => string;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  expandedRow,
  renderExpanded,
  getRowId,
}: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto scrollbar-thin rounded-xl border border-border">
      <table className="w-full text-sm" role="grid">
        <thead>
          <tr className="border-b border-border bg-background/50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider",
                  col.className
                )}
                scope="col"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.map((item) => {
            const rowId = getRowId(item);
            const isExpanded = expandedRow === rowId;
            return (
              <tr key={rowId}>
                <td colSpan={columns.length} className="p-0">
                  <div
                    className={cn(
                      "grid grid-cols-subgrid",
                      onRowClick && "cursor-pointer hover:bg-white/[0.02]",
                      isExpanded && "bg-primary/[0.03]"
                    )}
                    style={{
                      display: "grid",
                      gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))`,
                    }}
                    onClick={() => onRowClick?.(item)}
                    role={onRowClick ? "button" : undefined}
                    tabIndex={onRowClick ? 0 : undefined}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onRowClick?.(item);
                      }
                    }}
                    aria-expanded={isExpanded}
                  >
                    {columns.map((col) => (
                      <div
                        key={col.key}
                        className={cn("px-4 py-3 text-text-primary", col.className)}
                      >
                        {col.render
                          ? col.render(item)
                          : String((item as Record<string, unknown>)[col.key] ?? "")}
                      </div>
                    ))}
                  </div>
                  {isExpanded && renderExpanded && (
                    <div className="px-4 py-4 bg-background/30 border-t border-border animate-fade-in">
                      {renderExpanded(item)}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
