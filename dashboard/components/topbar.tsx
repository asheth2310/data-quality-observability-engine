"use client";

import { useState } from "react";
import { Search, Bell, User } from "lucide-react";
import { cn } from "@/lib/utils";

export function Topbar() {
  const [searchValue, setSearchValue] = useState("");

  return (
    <header
      className="sticky top-0 z-30 h-16 border-b border-border bg-surface/80 backdrop-blur-md flex items-center justify-between px-6"
      role="banner"
    >
      {/* Search */}
      <div className="relative w-full max-w-md">
        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary"
          aria-hidden="true"
        />
        <input
          type="search"
          placeholder="Search datasets, anomalies, alerts..."
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          className="w-full h-10 pl-10 pr-4 rounded-lg bg-background border border-border text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-150"
          aria-label="Search datasets, anomalies, and alerts"
        />
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-3 ml-4">
        {/* Notifications */}
        <button
          className="relative w-10 h-10 flex items-center justify-center rounded-lg hover:bg-white/5 transition-colors duration-150"
          aria-label="Notifications (3 unread)"
        >
          <Bell className="w-5 h-5 text-text-secondary" aria-hidden="true" />
          <span
            className="absolute top-1.5 right-1.5 w-5 h-5 bg-critical text-white text-[10px] font-bold rounded-full flex items-center justify-center"
            aria-hidden="true"
          >
            3
          </span>
        </button>

        {/* User avatar */}
        <button
          className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center hover:bg-primary/30 transition-colors duration-150"
          aria-label="User menu"
        >
          <User className="w-5 h-5 text-primary" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
