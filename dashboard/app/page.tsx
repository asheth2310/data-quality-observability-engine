"use client";

import { Database, AlertTriangle, Clock, Wrench } from "lucide-react";
import { StatCard } from "@/components/stat-card";
import { DonutChart } from "@/components/donut-chart";
import { ActivityFeed } from "@/components/activity-feed";
import { sparklineData, healthStatus, activityFeed } from "@/lib/mock-data";

export default function DashboardPage() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Dashboard Overview</h1>
        <p className="text-sm text-text-secondary mt-1">
          Real-time data quality and observability metrics
        </p>
      </div>

      {/* Summary stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Datasets"
          value={156}
          icon={Database}
          trend={{ direction: "up", value: "4 this week" }}
          sparklineData={sparklineData.datasets}
          accentColor="text-primary"
        />
        <StatCard
          title="Active Anomalies"
          value={7}
          icon={AlertTriangle}
          trend={{ direction: "up", value: "3 today" }}
          sparklineData={sparklineData.anomalies}
          accentColor="text-critical"
        />
        <StatCard
          title="SLA Breaches"
          value={2}
          icon={Clock}
          trend={{ direction: "down", value: "1 less" }}
          sparklineData={sparklineData.slaBreaches}
          accentColor="text-warning"
        />
        <StatCard
          title="Healing Actions"
          value={4}
          icon={Wrench}
          sparklineData={sparklineData.healingActions}
          accentColor="text-success"
        />
      </div>

      {/* Charts and activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Health status donut */}
        <div className="card lg:col-span-1">
          <h2 className="text-sm font-medium text-text-secondary mb-4">
            Dataset Health Status
          </h2>
          <DonutChart
            data={healthStatus}
            centerLabel="Total"
            centerValue={156}
          />
        </div>

        {/* Activity feed */}
        <div className="card lg:col-span-2">
          <h2 className="text-sm font-medium text-text-secondary mb-4">
            Recent Activity
          </h2>
          <div className="max-h-[360px] overflow-y-auto scrollbar-thin">
            <ActivityFeed events={activityFeed} />
          </div>
        </div>
      </div>
    </div>
  );
}
