"use client";

import { ResponsiveContainer, AreaChart, Area } from "recharts";
import { cn } from "@/lib/utils";

interface SparklineProps {
  data: { day: string; value: number }[];
  color?: string;
}

const colorMap: Record<string, { stroke: string; fill: string }> = {
  "text-primary": { stroke: "#3b82f6", fill: "#3b82f6" },
  "text-warning": { stroke: "#f59e0b", fill: "#f59e0b" },
  "text-critical": { stroke: "#f43f5e", fill: "#f43f5e" },
  "text-success": { stroke: "#10b981", fill: "#10b981" },
};

export function Sparkline({ data, color = "text-primary" }: SparklineProps) {
  const colors = colorMap[color] || colorMap["text-primary"];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={colors.fill} stopOpacity={0.3} />
            <stop offset="100%" stopColor={colors.fill} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={colors.stroke}
          strokeWidth={1.5}
          fill={`url(#gradient-${color})`}
          dot={false}
          isAnimationActive={true}
          animationDuration={300}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
