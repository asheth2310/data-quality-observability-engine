"use client";

import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";

interface DonutChartProps {
  data: { name: string; value: number; color: string }[];
  centerLabel?: string;
  centerValue?: string | number;
}

export function DonutChart({ data, centerLabel, centerValue }: DonutChartProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={90}
            paddingAngle={3}
            dataKey="value"
            strokeWidth={0}
            animationDuration={300}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              color: "#f8fafc",
              fontSize: "12px",
            }}
            formatter={(value: number, name: string) => [
              `${value} (${((value / total) * 100).toFixed(1)}%)`,
              name,
            ]}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value) => (
              <span className="text-xs text-text-secondary">{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
      {centerLabel && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[calc(50%+18px)] text-center pointer-events-none">
          <p className="text-2xl font-bold text-text-primary">{centerValue}</p>
          <p className="text-xs text-text-secondary">{centerLabel}</p>
        </div>
      )}
    </div>
  );
}
