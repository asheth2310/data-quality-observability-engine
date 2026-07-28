"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  AlertTriangle,
  Database,
  GitBranch,
  Clock,
  Wrench,
  Bell,
  ChevronLeft,
  ChevronRight,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/anomalies", label: "Anomalies", icon: AlertTriangle },
  { href: "/schemas", label: "Schemas", icon: Database },
  { href: "/lineage", label: "Lineage", icon: GitBranch },
  { href: "/freshness", label: "Freshness", icon: Clock },
  { href: "/healing", label: "Healing", icon: Wrench },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "h-screen sticky top-0 flex flex-col border-r border-border bg-surface transition-all duration-250 z-40",
        collapsed ? "w-16" : "w-60"
      )}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
          <Activity className="w-4 h-4 text-primary" aria-hidden="true" />
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold text-text-primary truncate">
            DQ Observatory
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1" aria-label="Sidebar navigation">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 min-h-[44px]",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-text-secondary hover:text-text-primary hover:bg-white/5"
              )}
              aria-current={isActive ? "page" : undefined}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="px-2 pb-4">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center w-full h-10 rounded-lg text-text-secondary hover:text-text-primary hover:bg-white/5 transition-colors duration-150"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          ) : (
            <ChevronLeft className="w-4 h-4" aria-hidden="true" />
          )}
        </button>
      </div>
    </aside>
  );
}
