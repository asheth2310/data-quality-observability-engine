// ─────────────────────────────────────────────────────────────
// Mock Data for Data Quality & Observability Engine Dashboard
// ─────────────────────────────────────────────────────────────

export interface Anomaly {
  id: string;
  dataset: string;
  column: string;
  type: string;
  severity: "critical" | "warning" | "info";
  score: number;
  confidence: number;
  detected_at: string;
  context: string;
}

export interface SchemaEntry {
  id: string;
  dataset: string;
  version: string;
  evolution_rule: string;
  last_drift: string;
  drift_type: string | null;
  columns: { name: string; type: string; nullable: boolean }[];
}

export interface FreshnessEntry {
  id: string;
  dataset: string;
  sla_hours: number;
  sla_consumed_pct: number;
  status: "healthy" | "warning" | "breached" | "stale";
  last_updated: string;
  staleness_history: { time: string; pct: number }[];
}

export interface HealingAction {
  id: string;
  strategy: string;
  dataset: string;
  outcome: "success" | "failed" | "in_progress";
  duration_ms: number;
  executed_at: string;
  description: string;
}

export interface Alert {
  id: string;
  severity: "critical" | "warning" | "info";
  dataset: string;
  type: string;
  message: string;
  created_at: string;
  escalation_level: number;
  acknowledged: boolean;
  suppressed: boolean;
}

export interface ActivityEvent {
  id: string;
  type: "anomaly" | "schema" | "freshness" | "healing" | "alert";
  message: string;
  timestamp: string;
  severity?: "critical" | "warning" | "info";
}

// ─── Sparkline Data ───
export const sparklineData = {
  datasets: [
    { day: "Mon", value: 142 },
    { day: "Tue", value: 145 },
    { day: "Wed", value: 148 },
    { day: "Thu", value: 147 },
    { day: "Fri", value: 152 },
    { day: "Sat", value: 153 },
    { day: "Sun", value: 156 },
  ],
  anomalies: [
    { day: "Mon", value: 8 },
    { day: "Tue", value: 12 },
    { day: "Wed", value: 6 },
    { day: "Thu", value: 15 },
    { day: "Fri", value: 9 },
    { day: "Sat", value: 4 },
    { day: "Sun", value: 7 },
  ],
  slaBreaches: [
    { day: "Mon", value: 2 },
    { day: "Tue", value: 1 },
    { day: "Wed", value: 3 },
    { day: "Thu", value: 0 },
    { day: "Fri", value: 2 },
    { day: "Sat", value: 1 },
    { day: "Sun", value: 1 },
  ],
  healingActions: [
    { day: "Mon", value: 5 },
    { day: "Tue", value: 8 },
    { day: "Wed", value: 3 },
    { day: "Thu", value: 11 },
    { day: "Fri", value: 6 },
    { day: "Sat", value: 2 },
    { day: "Sun", value: 4 },
  ],
};

// ─── Health Status ───
export const healthStatus = [
  { name: "Healthy", value: 118, color: "#10b981" },
  { name: "Warning", value: 27, color: "#f59e0b" },
  { name: "Critical", value: 11, color: "#f43f5e" },
];

// ─── Anomalies ───
export const anomalies: Anomaly[] = [
  {
    id: "anom-001",
    dataset: "warehouse.finance.transactions",
    column: "amount",
    type: "distribution_shift",
    severity: "critical",
    score: 0.94,
    confidence: 0.97,
    detected_at: "2024-03-15T14:23:00Z",
    context: "Mean shifted from $142.50 to $289.30 (+103%). Likely upstream ETL change in payment processor feed.",
  },
  {
    id: "anom-002",
    dataset: "warehouse.marketing.campaign_events",
    column: "event_timestamp",
    type: "null_spike",
    severity: "critical",
    score: 0.91,
    confidence: 0.95,
    detected_at: "2024-03-15T13:45:00Z",
    context: "Null rate jumped from 0.2% to 34.7%. Kafka consumer lag detected on topic marketing-events.",
  },
  {
    id: "anom-003",
    dataset: "warehouse.ops.server_metrics",
    column: "cpu_utilization",
    type: "outlier_burst",
    severity: "warning",
    score: 0.78,
    confidence: 0.88,
    detected_at: "2024-03-15T12:10:00Z",
    context: "12 outlier data points detected in 5-minute window. Values exceeding 3σ threshold.",
  },
  {
    id: "anom-004",
    dataset: "warehouse.customer.profiles",
    column: "email",
    type: "format_violation",
    severity: "warning",
    score: 0.72,
    confidence: 0.91,
    detected_at: "2024-03-15T11:30:00Z",
    context: "2.3% of new records contain malformed email addresses. Pattern: missing @ symbol.",
  },
  {
    id: "anom-005",
    dataset: "warehouse.supply_chain.inventory",
    column: "quantity_on_hand",
    type: "range_violation",
    severity: "warning",
    score: 0.68,
    confidence: 0.85,
    detected_at: "2024-03-15T10:55:00Z",
    context: "Negative inventory values detected for 47 SKUs. Possible double-counting in warehouse sync.",
  },
  {
    id: "anom-006",
    dataset: "warehouse.finance.invoices",
    column: "due_date",
    type: "temporal_anomaly",
    severity: "info",
    score: 0.55,
    confidence: 0.79,
    detected_at: "2024-03-15T09:20:00Z",
    context: "Due dates set to year 2025 detected. May be intentional for long-term contracts.",
  },
  {
    id: "anom-007",
    dataset: "warehouse.hr.payroll",
    column: "gross_salary",
    type: "distribution_shift",
    severity: "critical",
    score: 0.89,
    confidence: 0.93,
    detected_at: "2024-03-15T08:15:00Z",
    context: "Bimodal distribution detected. Annual bonus processing may have merged with regular payroll.",
  },
  {
    id: "anom-008",
    dataset: "warehouse.analytics.page_views",
    column: "session_duration",
    type: "cardinality_change",
    severity: "info",
    score: 0.45,
    confidence: 0.72,
    detected_at: "2024-03-15T07:40:00Z",
    context: "Distinct value count increased by 340%. New tracking pixel deployed without schema update.",
  },
  {
    id: "anom-009",
    dataset: "warehouse.logistics.shipments",
    column: "delivery_status",
    type: "enum_drift",
    severity: "warning",
    score: 0.71,
    confidence: 0.87,
    detected_at: "2024-03-15T06:30:00Z",
    context: "New enum value 'RETURN_TO_SENDER_V2' appeared. Not in schema contract.",
  },
  {
    id: "anom-010",
    dataset: "warehouse.finance.transactions",
    column: "currency_code",
    type: "null_spike",
    severity: "critical",
    score: 0.88,
    confidence: 0.96,
    detected_at: "2024-03-15T05:00:00Z",
    context: "Currency code null for 18% of transactions from EU region. FX service timeout suspected.",
  },
];

// ─── Anomaly Score Distribution ───
export const anomalyScoreDistribution = [
  { range: "0.0-0.2", count: 12 },
  { range: "0.2-0.4", count: 28 },
  { range: "0.4-0.6", count: 45 },
  { range: "0.6-0.8", count: 34 },
  { range: "0.8-1.0", count: 18 },
];

// ─── Schema Registry ───
export const schemas: SchemaEntry[] = [
  {
    id: "schema-001",
    dataset: "warehouse.finance.transactions",
    version: "v3.2.1",
    evolution_rule: "backward_compatible",
    last_drift: "2024-03-14T18:00:00Z",
    drift_type: "COLUMN_ADDED",
    columns: [
      { name: "transaction_id", type: "STRING", nullable: false },
      { name: "amount", type: "DECIMAL(18,2)", nullable: false },
      { name: "currency_code", type: "STRING(3)", nullable: true },
      { name: "merchant_id", type: "STRING", nullable: false },
      { name: "processed_at", type: "TIMESTAMP", nullable: false },
      { name: "risk_score", type: "FLOAT", nullable: true },
    ],
  },
  {
    id: "schema-002",
    dataset: "warehouse.customer.profiles",
    version: "v2.1.0",
    evolution_rule: "strict",
    last_drift: "2024-03-10T09:30:00Z",
    drift_type: "TYPE_CHANGED",
    columns: [
      { name: "customer_id", type: "UUID", nullable: false },
      { name: "email", type: "STRING(255)", nullable: false },
      { name: "created_at", type: "TIMESTAMP", nullable: false },
      { name: "tier", type: "ENUM(free,pro,enterprise)", nullable: false },
    ],
  },
  {
    id: "schema-003",
    dataset: "warehouse.marketing.campaign_events",
    version: "v1.8.0",
    evolution_rule: "forward_compatible",
    last_drift: "2024-03-12T14:20:00Z",
    drift_type: "COLUMN_REMOVED",
    columns: [
      { name: "event_id", type: "STRING", nullable: false },
      { name: "campaign_id", type: "STRING", nullable: false },
      { name: "event_timestamp", type: "TIMESTAMP", nullable: true },
      { name: "channel", type: "STRING", nullable: false },
      { name: "conversion_value", type: "DECIMAL(10,2)", nullable: true },
    ],
  },
  {
    id: "schema-004",
    dataset: "warehouse.ops.server_metrics",
    version: "v4.0.0",
    evolution_rule: "backward_compatible",
    last_drift: "2024-03-08T22:15:00Z",
    drift_type: "COLUMN_ADDED",
    columns: [
      { name: "host_id", type: "STRING", nullable: false },
      { name: "cpu_utilization", type: "FLOAT", nullable: false },
      { name: "memory_pct", type: "FLOAT", nullable: false },
      { name: "disk_io_mbps", type: "FLOAT", nullable: true },
      { name: "collected_at", type: "TIMESTAMP", nullable: false },
    ],
  },
  {
    id: "schema-005",
    dataset: "warehouse.supply_chain.inventory",
    version: "v2.3.0",
    evolution_rule: "strict",
    last_drift: "2024-03-13T16:45:00Z",
    drift_type: null,
    columns: [
      { name: "sku", type: "STRING", nullable: false },
      { name: "warehouse_id", type: "STRING", nullable: false },
      { name: "quantity_on_hand", type: "INTEGER", nullable: false },
      { name: "last_replenished", type: "TIMESTAMP", nullable: true },
    ],
  },
  {
    id: "schema-006",
    dataset: "warehouse.hr.payroll",
    version: "v1.5.2",
    evolution_rule: "strict",
    last_drift: "2024-03-01T08:00:00Z",
    drift_type: "TYPE_CHANGED",
    columns: [
      { name: "employee_id", type: "STRING", nullable: false },
      { name: "gross_salary", type: "DECIMAL(12,2)", nullable: false },
      { name: "pay_period", type: "DATE", nullable: false },
      { name: "department", type: "STRING", nullable: false },
    ],
  },
];

// ─── Schema Drift Timeline ───
export const driftTimeline = [
  { date: "Mar 1", events: 1 },
  { date: "Mar 3", events: 0 },
  { date: "Mar 5", events: 2 },
  { date: "Mar 7", events: 0 },
  { date: "Mar 9", events: 1 },
  { date: "Mar 11", events: 3 },
  { date: "Mar 13", events: 1 },
  { date: "Mar 15", events: 2 },
  { date: "Mar 17", events: 0 },
  { date: "Mar 19", events: 1 },
  { date: "Mar 21", events: 0 },
  { date: "Mar 23", events: 2 },
  { date: "Mar 25", events: 1 },
  { date: "Mar 27", events: 0 },
  { date: "Mar 29", events: 1 },
];

// ─── Freshness SLAs ───
export const freshnessEntries: FreshnessEntry[] = [
  {
    id: "fresh-001",
    dataset: "warehouse.finance.transactions",
    sla_hours: 1,
    sla_consumed_pct: 87,
    status: "warning",
    last_updated: "2024-03-15T13:48:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: Math.min(95, 20 + Math.random() * 60 + (i > 18 ? 30 : 0)),
    })),
  },
  {
    id: "fresh-002",
    dataset: "warehouse.customer.profiles",
    sla_hours: 6,
    sla_consumed_pct: 32,
    status: "healthy",
    last_updated: "2024-03-15T12:30:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: 15 + Math.random() * 25,
    })),
  },
  {
    id: "fresh-003",
    dataset: "warehouse.marketing.campaign_events",
    sla_hours: 2,
    sla_consumed_pct: 105,
    status: "breached",
    last_updated: "2024-03-15T11:50:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: Math.min(120, 30 + Math.random() * 40 + (i > 12 ? 50 : 0)),
    })),
  },
  {
    id: "fresh-004",
    dataset: "warehouse.ops.server_metrics",
    sla_hours: 0.25,
    sla_consumed_pct: 45,
    status: "healthy",
    last_updated: "2024-03-15T14:20:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: 20 + Math.random() * 35,
    })),
  },
  {
    id: "fresh-005",
    dataset: "warehouse.supply_chain.inventory",
    sla_hours: 4,
    sla_consumed_pct: 68,
    status: "healthy",
    last_updated: "2024-03-15T11:15:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: 30 + Math.random() * 40,
    })),
  },
  {
    id: "fresh-006",
    dataset: "warehouse.hr.payroll",
    sla_hours: 24,
    sla_consumed_pct: 12,
    status: "healthy",
    last_updated: "2024-03-15T06:00:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: 5 + Math.random() * 15,
    })),
  },
  {
    id: "fresh-007",
    dataset: "warehouse.analytics.page_views",
    sla_hours: 1,
    sla_consumed_pct: 92,
    status: "warning",
    last_updated: "2024-03-15T13:15:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: Math.min(100, 25 + Math.random() * 50 + (i > 16 ? 25 : 0)),
    })),
  },
  {
    id: "fresh-008",
    dataset: "warehouse.logistics.shipments",
    sla_hours: 3,
    sla_consumed_pct: 55,
    status: "healthy",
    last_updated: "2024-03-15T12:45:00Z",
    staleness_history: Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      pct: 20 + Math.random() * 40,
    })),
  },
];

// ─── Healing Actions ───
export const healingActions: HealingAction[] = [
  {
    id: "heal-001",
    strategy: "retry_with_backoff",
    dataset: "warehouse.finance.transactions",
    outcome: "success",
    duration_ms: 3200,
    executed_at: "2024-03-15T14:25:00Z",
    description: "Retried failed Kafka consumer batch with exponential backoff. Recovered 1,247 records.",
  },
  {
    id: "heal-002",
    strategy: "schema_rollback",
    dataset: "warehouse.marketing.campaign_events",
    outcome: "success",
    duration_ms: 8500,
    executed_at: "2024-03-15T13:50:00Z",
    description: "Rolled back schema to v1.7.0 after incompatible change detected. Downstream consumers restored.",
  },
  {
    id: "heal-003",
    strategy: "null_imputation",
    dataset: "warehouse.finance.transactions",
    outcome: "success",
    duration_ms: 1800,
    executed_at: "2024-03-15T12:15:00Z",
    description: "Applied mode-based imputation for currency_code nulls using merchant region mapping.",
  },
  {
    id: "heal-004",
    strategy: "partition_repair",
    dataset: "warehouse.ops.server_metrics",
    outcome: "failed",
    duration_ms: 45000,
    executed_at: "2024-03-15T11:00:00Z",
    description: "Attempted to repair corrupted partition dt=2024-03-14. HDFS block recovery failed.",
  },
  {
    id: "heal-005",
    strategy: "dedup_reconciliation",
    dataset: "warehouse.customer.profiles",
    outcome: "success",
    duration_ms: 12300,
    executed_at: "2024-03-15T10:30:00Z",
    description: "Identified and removed 342 duplicate customer records using fuzzy matching on email + phone.",
  },
  {
    id: "heal-006",
    strategy: "retry_with_backoff",
    dataset: "warehouse.logistics.shipments",
    outcome: "success",
    duration_ms: 2100,
    executed_at: "2024-03-15T09:45:00Z",
    description: "Retried API call to carrier tracking service. 98 shipment statuses updated.",
  },
  {
    id: "heal-007",
    strategy: "quarantine_records",
    dataset: "warehouse.hr.payroll",
    outcome: "success",
    duration_ms: 950,
    executed_at: "2024-03-15T08:20:00Z",
    description: "Quarantined 23 payroll records with anomalous gross_salary values for manual review.",
  },
  {
    id: "heal-008",
    strategy: "partition_repair",
    dataset: "warehouse.analytics.page_views",
    outcome: "in_progress",
    duration_ms: 0,
    executed_at: "2024-03-15T14:30:00Z",
    description: "Repairing missing partition dt=2024-03-15/hr=12. Replaying from Kafka offset.",
  },
];

// ─── Healing Strategy Breakdown ───
export const healingStrategyBreakdown = [
  { strategy: "retry_with_backoff", count: 45, success: 42 },
  { strategy: "schema_rollback", count: 12, success: 10 },
  { strategy: "null_imputation", count: 28, success: 26 },
  { strategy: "partition_repair", count: 18, success: 11 },
  { strategy: "dedup_reconciliation", count: 8, success: 7 },
  { strategy: "quarantine_records", count: 15, success: 15 },
];

// ─── Alerts ───
export const alerts: Alert[] = [
  {
    id: "alert-001",
    severity: "critical",
    dataset: "warehouse.finance.transactions",
    type: "anomaly_detected",
    message: "Distribution shift on amount column exceeds 3σ threshold. Revenue impact estimated at $2.4M.",
    created_at: "2024-03-15T14:23:00Z",
    escalation_level: 3,
    acknowledged: false,
    suppressed: false,
  },
  {
    id: "alert-002",
    severity: "critical",
    dataset: "warehouse.marketing.campaign_events",
    type: "sla_breach",
    message: "Freshness SLA breached. Dataset is 2h 10m past deadline. Campaign reporting affected.",
    created_at: "2024-03-15T13:50:00Z",
    escalation_level: 2,
    acknowledged: false,
    suppressed: false,
  },
  {
    id: "alert-003",
    severity: "warning",
    dataset: "warehouse.finance.transactions",
    type: "freshness_warning",
    message: "SLA consumption at 87%. Dataset approaching staleness threshold.",
    created_at: "2024-03-15T13:48:00Z",
    escalation_level: 1,
    acknowledged: true,
    suppressed: false,
  },
  {
    id: "alert-004",
    severity: "warning",
    dataset: "warehouse.ops.server_metrics",
    type: "healing_failed",
    message: "Partition repair strategy failed after 3 attempts. Manual intervention required.",
    created_at: "2024-03-15T11:00:00Z",
    escalation_level: 2,
    acknowledged: false,
    suppressed: false,
  },
  {
    id: "alert-005",
    severity: "info",
    dataset: "warehouse.analytics.page_views",
    type: "schema_drift",
    message: "New tracking fields detected. Schema contract update recommended.",
    created_at: "2024-03-15T07:40:00Z",
    escalation_level: 1,
    acknowledged: true,
    suppressed: false,
  },
  {
    id: "alert-006",
    severity: "critical",
    dataset: "warehouse.hr.payroll",
    type: "anomaly_detected",
    message: "Bimodal salary distribution detected. Possible data merge error.",
    created_at: "2024-03-15T08:15:00Z",
    escalation_level: 2,
    acknowledged: false,
    suppressed: false,
  },
  {
    id: "alert-007",
    severity: "info",
    dataset: "warehouse.supply_chain.inventory",
    type: "healing_completed",
    message: "Quarantine action completed successfully. 47 records isolated for review.",
    created_at: "2024-03-15T10:55:00Z",
    escalation_level: 0,
    acknowledged: true,
    suppressed: true,
  },
  {
    id: "alert-008",
    severity: "warning",
    dataset: "warehouse.logistics.shipments",
    type: "schema_drift",
    message: "New enum value detected in delivery_status. Contract violation.",
    created_at: "2024-03-15T06:30:00Z",
    escalation_level: 1,
    acknowledged: false,
    suppressed: true,
  },
];

// ─── Activity Feed ───
export const activityFeed: ActivityEvent[] = [
  {
    id: "evt-001",
    type: "anomaly",
    message: "Critical distribution shift detected in warehouse.finance.transactions.amount",
    timestamp: "2024-03-15T14:23:00Z",
    severity: "critical",
  },
  {
    id: "evt-002",
    type: "healing",
    message: "Auto-healing: retry_with_backoff succeeded for warehouse.finance.transactions",
    timestamp: "2024-03-15T14:25:00Z",
  },
  {
    id: "evt-003",
    type: "freshness",
    message: "SLA breached: warehouse.marketing.campaign_events (2h 10m overdue)",
    timestamp: "2024-03-15T13:50:00Z",
    severity: "critical",
  },
  {
    id: "evt-004",
    type: "schema",
    message: "Schema rollback executed: warehouse.marketing.campaign_events → v1.7.0",
    timestamp: "2024-03-15T13:50:00Z",
  },
  {
    id: "evt-005",
    type: "alert",
    message: "Alert escalated to L2: SLA breach on campaign_events",
    timestamp: "2024-03-15T13:52:00Z",
    severity: "warning",
  },
  {
    id: "evt-006",
    type: "anomaly",
    message: "Null spike detected in warehouse.marketing.campaign_events.event_timestamp",
    timestamp: "2024-03-15T13:45:00Z",
    severity: "critical",
  },
  {
    id: "evt-007",
    type: "healing",
    message: "Auto-healing: null_imputation applied to warehouse.finance.transactions.currency_code",
    timestamp: "2024-03-15T12:15:00Z",
  },
  {
    id: "evt-008",
    type: "freshness",
    message: "Warning: warehouse.analytics.page_views approaching SLA (92% consumed)",
    timestamp: "2024-03-15T13:15:00Z",
    severity: "warning",
  },
  {
    id: "evt-009",
    type: "healing",
    message: "Healing failed: partition_repair on warehouse.ops.server_metrics",
    timestamp: "2024-03-15T11:00:00Z",
    severity: "warning",
  },
  {
    id: "evt-010",
    type: "schema",
    message: "Schema drift detected: COLUMN_ADDED on warehouse.finance.transactions",
    timestamp: "2024-03-14T18:00:00Z",
  },
];

// ─── Lineage Graph Data ───
export const lineageNodes = [
  { id: "src-kafka-payments", type: "source", label: "kafka.payments.raw", dataset: "payments" },
  { id: "src-kafka-events", type: "source", label: "kafka.marketing.events", dataset: "marketing" },
  { id: "src-api-customers", type: "source", label: "api.crm.customers", dataset: "customers" },
  { id: "src-s3-inventory", type: "source", label: "s3://warehouse/inventory", dataset: "supply_chain" },
  { id: "stg-transactions", type: "staging", label: "staging.finance.transactions", dataset: "payments" },
  { id: "stg-events", type: "staging", label: "staging.marketing.events", dataset: "marketing" },
  { id: "stg-customers", type: "staging", label: "staging.customer.profiles", dataset: "customers" },
  { id: "stg-inventory", type: "staging", label: "staging.supply_chain.raw", dataset: "supply_chain" },
  { id: "wh-transactions", type: "warehouse", label: "warehouse.finance.transactions", dataset: "payments" },
  { id: "wh-campaigns", type: "warehouse", label: "warehouse.marketing.campaign_events", dataset: "marketing" },
  { id: "wh-profiles", type: "warehouse", label: "warehouse.customer.profiles", dataset: "customers" },
  { id: "wh-inventory", type: "warehouse", label: "warehouse.supply_chain.inventory", dataset: "supply_chain" },
  { id: "mart-revenue", type: "mart", label: "mart.finance.daily_revenue", dataset: "payments" },
  { id: "mart-ltv", type: "mart", label: "mart.customer.lifetime_value", dataset: "customers" },
  { id: "mart-campaign-roi", type: "mart", label: "mart.marketing.campaign_roi", dataset: "marketing" },
  { id: "mart-stock-forecast", type: "mart", label: "mart.supply.stock_forecast", dataset: "supply_chain" },
];

export const lineageEdges = [
  { id: "e1", source: "src-kafka-payments", target: "stg-transactions", confidence: 0.99 },
  { id: "e2", source: "src-kafka-events", target: "stg-events", confidence: 0.98 },
  { id: "e3", source: "src-api-customers", target: "stg-customers", confidence: 0.95 },
  { id: "e4", source: "src-s3-inventory", target: "stg-inventory", confidence: 0.97 },
  { id: "e5", source: "stg-transactions", target: "wh-transactions", confidence: 0.99 },
  { id: "e6", source: "stg-events", target: "wh-campaigns", confidence: 0.97 },
  { id: "e7", source: "stg-customers", target: "wh-profiles", confidence: 0.96 },
  { id: "e8", source: "stg-inventory", target: "wh-inventory", confidence: 0.98 },
  { id: "e9", source: "wh-transactions", target: "mart-revenue", confidence: 0.99 },
  { id: "e10", source: "wh-profiles", target: "mart-ltv", confidence: 0.94 },
  { id: "e11", source: "wh-transactions", target: "mart-ltv", confidence: 0.92 },
  { id: "e12", source: "wh-campaigns", target: "mart-campaign-roi", confidence: 0.96 },
  { id: "e13", source: "wh-profiles", target: "mart-campaign-roi", confidence: 0.88 },
  { id: "e14", source: "wh-inventory", target: "mart-stock-forecast", confidence: 0.95 },
  { id: "e15", source: "wh-transactions", target: "mart-stock-forecast", confidence: 0.85 },
];
