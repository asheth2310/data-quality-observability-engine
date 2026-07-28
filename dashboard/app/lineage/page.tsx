"use client";

import { LineageGraph } from "@/components/lineage-graph";

export default function LineagePage() {
  return (
    <div className="h-[calc(100vh-8rem)] -m-6">
      <div className="h-full w-full">
        <LineageGraph />
      </div>
    </div>
  );
}
