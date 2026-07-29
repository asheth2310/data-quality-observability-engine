# 🔬 Data Quality & Observability Engine

> Production-grade platform for monitoring data pipelines — catch schema drift, detect statistical anomalies, track column-level lineage, enforce freshness SLAs, and self-heal automatically.

**🌐 Live Dashboard:** [https://dashboard-iota-tan-86.vercel.app](https://dashboard-iota-tan-86.vercel.app)  
**📦 Source Code:** [https://github.com/asheth2310/data-quality-observability-engine](https://github.com/asheth2310/data-quality-observability-engine)

---

## 📸 Dashboard Preview

### Overview Page
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔬 Data Quality Observatory                          🔔 3  👤       │
├────────┬────────────────────────────────────────────────────────────┤
│        │                                                            │
│ 📊 Ovr │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                     │
│ ⚠️ Anom│  │ 156  │ │  7   │ │  2   │ │  4   │                     │
│ 📋 Sche│  │Dsets │ │Anom. │ │SLA ⚠️│ │Healed│                     │
│ 🔗 Line│  └──────┘ └──────┘ └──────┘ └──────┘                     │
│ ⏱️ Fres│                                                            │
│ 🔧 Heal│  ┌─────────────┐  ┌──────────────────────────────┐        │
│ 🚨 Aler│  │ Health      │  │ Recent Activity              │        │
│        │  │   🟢 78%    │  │ • Schema drift detected...   │        │
│        │  │   🟡 14%    │  │ • Anomaly in transactions... │        │
│        │  │   🔴  8%    │  │ • Backfill completed for...  │        │
│        │  └─────────────┘  │ • SLA warning: orders stale  │        │
│        │                    └──────────────────────────────┘        │
├────────┴────────────────────────────────────────────────────────────┤
│ Backend: Python + FastAPI · github.com/asheth2310/data-quality-...  │
└─────────────────────────────────────────────────────────────────────┘
```

### Lineage Graph Page
```
┌─────────────────────────────────────────────────────────────────────┐
│  Data Lineage Graph                          [Search datasets...]   │
│                                                                     │
│    ┌─────────────┐        ┌─────────────────┐                      │
│    │ raw.orders  │───────►│ staging.orders  │                      │
│    │  • amount   │        │  • total_amount │──┐                   │
│    │  • currency │──┐     │  • currency_code│  │                   │
│    └─────────────┘  │     └─────────────────┘  │                   │
│                     │                           ▼                   │
│    ┌─────────────┐  │     ┌─────────────────────────┐              │
│    │ raw.users   │  └────►│ analytics.daily_revenue │              │
│    │  • user_id  │───────►│  • revenue              │              │
│    │  • name     │        │  • avg_transaction      │              │
│    └─────────────┘        └─────────────────────────┘              │
│                                                                     │
│  ┌──────┐ Nodes: 47  Edges: 83  Depth: 5                          │
│  │minimp│                                                          │
│  └──────┘                                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DATA QUALITY OBSERVATORY                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        DATA SOURCES                                       │   │
│  │   Database CDC  │  Object Storage Events  │  API Hooks  │  Kafka Streams  │   │
│  └────────────────────────────────┬─────────────────────────────────────────┘   │
│                                   │                                              │
│                                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     INGESTION & COLLECTION LAYER                          │   │
│  │                                                                           │   │
│  │   ┌──────────────┐  ┌────────────────┐  ┌────────────────┐              │   │
│  │   │  Metadata    │  │  Statistical   │  │   Lineage      │              │   │
│  │   │  Collector   │  │  Profiler      │  │   Extractor    │              │   │
│  │   └──────────────┘  └────────────────┘  └────────────────┘              │   │
│  └────────────────────────────────┬─────────────────────────────────────────┘   │
│                                   │                                              │
│                                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      PROCESSING ENGINE                                    │   │
│  │                                                                           │   │
│  │   ┌──────────────┐  ┌────────────────┐  ┌────────────────┐              │   │
│  │   │ Schema Drift │  │   Anomaly      │  │  Freshness     │              │   │
│  │   │  Detector    │  │   Detection    │  │  Monitor       │              │   │
│  │   │              │  │  (KS-test +    │  │  (Predictive   │              │   │
│  │   │ Type-width   │  │   KL-div)      │  │   alerting)    │              │   │
│  │   │ severity     │  │                │  │                │              │   │
│  │   └──────────────┘  └────────────────┘  └────────────────┘              │   │
│  │                                                                           │   │
│  │   ┌──────────────────────────────────────────────────────┐               │   │
│  │   │              Lineage Graph Engine                     │               │   │
│  │   │         (Column-level DAG + BFS Impact)               │               │   │
│  │   └──────────────────────────────────────────────────────┘               │   │
│  └────────────────────────────────┬─────────────────────────────────────────┘   │
│                                   │                                              │
│                                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    SELF-HEALING ENGINE                                     │   │
│  │                                                                           │   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │   │  Retry   │  │Quarantine│  │ Backfill │  │ Escalate │               │   │
│  │   │ (exp.    │  │ (isolate │  │ (fill    │  │ (page    │               │   │
│  │   │  backoff)│  │  bad recs)│  │  gaps)   │  │  human)  │               │   │
│  │   └──────────┘  └──────────┘  └──────────┘  └──────────┘               │   │
│  └────────────────────────────────┬─────────────────────────────────────────┘   │
│                                   │                                              │
│                                   ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                  ALERT ENGINE & ESCALATION                                │   │
│  │                                                                           │   │
│  │   Deduplication → Lineage Correlation → Time-based Escalation            │   │
│  │                                                                           │   │
│  │   ┌────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐                  │   │
│  │   │ Slack  │  │PagerDuty │  │  Email  │  │ Webhook  │                  │   │
│  │   └────────┘  └──────────┘  └─────────┘  └──────────┘                  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                           STORAGE LAYER                                          │
│                                                                                  │
│   PostgreSQL         TimescaleDB          Neo4j             Redis                │
│   (Metadata)         (Time-series)        (Lineage Graph)   (Cache/State)        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 How It Works — End-to-End Workflow

### Flow 1: Schema Drift Detection & Auto-Healing

```
Data arrives → Extract schema → Compare with contract
                                        │
                                ┌───────┴───────┐
                                │               │
                          No Drift          Drift Found
                          (continue)              │
                                          ┌───────┴───────┐
                                          │               │
                                    Additive          Breaking
                                    (INFO)            (CRITICAL)
                                      │                   │
                              Auto-evolve           Quarantine records
                              contract              + Alert owners
```

### Flow 2: Statistical Anomaly Detection

```
New data batch → Profile all columns (mean, std, distribution, nulls)
                         │
                         ▼
              Compare against 30-day rolling baseline
                         │
                    ┌────┴─────┐
                    │          │
              Normal         Anomalous
              (update         (KS-stat > threshold
               baseline)       AND p-value < 0.05)
                                   │
                                   ▼
                          Compute anomaly score [0-1]
                                   │
                                   ▼
                          Emit AnomalyEvent → Alert Engine
                                   │
                                   ▼
                          Trace root cause via lineage graph
```

### Flow 3: Freshness SLA Monitoring

```
Every 30 seconds:
    For each registered dataset:
        │
        ▼
    staleness = now - last_data_arrival
    sla_consumed = staleness / max_staleness
        │
        ├── < 80% max → HEALTHY ✅
        ├── 80-90% → WARNING ⚠️ (notify owner)
        └── > 90% → CRITICAL 🔴 (trigger self-healing)
                         │
                         ▼
                  Diagnose root cause
                         │
              ┌──────────┼──────────┐
              │          │          │
          Timeout    Data Gap    Unknown
              │          │          │
           Retry     Backfill   Escalate
        (exp backoff)  (targeted)  (page human)
```

### Flow 4: Impact Analysis (Lineage)

```
"What happens if I change column X?"
              │
              ▼
    BFS traversal of lineage DAG
              │
              ▼
    ┌─────────────────────────┐
    │ Impact Report:          │
    │  • 47 downstream columns│
    │  • 12 affected datasets │
    │  • 8 pipelines impacted │
    │                         │
    │ Closest affected:       │
    │  → staging.orders.total │
    │  → analytics.revenue    │
    └─────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.11+, FastAPI | REST API, async processing |
| **Models** | Pydantic v2 | Strict validation, type safety |
| **Statistics** | scipy, numpy | KS-test, KL-divergence, profiling |
| **Graph DB** | Neo4j | Column-level lineage DAG |
| **Time-series** | TimescaleDB | Profiles, freshness metrics, thresholds |
| **Metadata** | PostgreSQL | Contracts, registrations, policies |
| **Cache** | Redis | State, rate limiting, profile cache |
| **Streaming** | Apache Kafka | Event streaming between components |
| **Async Jobs** | Celery | Healing execution, threshold recomputation |
| **Frontend** | Next.js 14, React 18 | Dashboard UI |
| **UI Components** | shadcn/ui, Tailwind CSS | Design system |
| **Charts** | Recharts | Data visualization |
| **Graph Viz** | React Flow | Lineage graph visualization |
| **Hosting** | Vercel | Dashboard deployment |
| **Testing** | pytest, hypothesis | Unit + property-based testing |

---

## 📂 Project Structure

```
data-quality-observability-engine/
│
├── src/data_quality_engine/          # Python backend
│   ├── models/                       # Pydantic v2 data models
│   │   ├── base.py                   # DatasetId, ColumnRef, enums
│   │   ├── schema.py                 # SchemaContract, ColumnContract
│   │   ├── profile.py               # DataProfile, ColumnProfile, histograms
│   │   ├── drift.py                 # DriftReport, severity classification
│   │   ├── anomaly.py              # AnomalyEvent, AdaptiveThreshold
│   │   ├── lineage.py              # LineageEdge, ImpactGraph
│   │   ├── freshness.py            # FreshnessSLA, FreshnessStatus
│   │   ├── healing.py              # Diagnosis, HealingResult, QuarantineReceipt
│   │   └── alert.py                # Alert, EscalationPolicy, EscalationChain
│   │
│   ├── services/                    # Core business logic
│   │   ├── schema_registry.py      # Contract registration & versioning
│   │   ├── drift_detector.py       # Schema drift detection & classification
│   │   ├── profiler.py             # Statistical profiling + HyperLogLog
│   │   ├── anomaly_detector.py     # KS-test + KL-divergence detection
│   │   ├── lineage_engine.py       # DAG management + BFS impact analysis
│   │   ├── freshness_monitor.py    # SLA enforcement + predictive alerting
│   │   └── healing_orchestrator.py # Diagnosis + strategy selection
│   │
│   └── storage/                     # Database abstractions
│       ├── interfaces.py            # Abstract base classes
│       ├── postgres.py              # Metadata store (in-memory impl)
│       ├── timescale.py             # Time-series store (in-memory impl)
│       ├── neo4j_store.py           # Graph store (in-memory impl)
│       └── redis_cache.py           # Cache store (in-memory impl)
│
├── tests/                           # 150+ unit tests
│   ├── test_schema_registry.py      # 23 tests
│   ├── test_drift_detector.py       # 28 tests
│   ├── test_profiler.py             # 29 tests
│   ├── test_anomaly_detector.py     # 25 tests
│   ├── test_lineage_engine.py       # 22 tests
│   ├── test_freshness_monitor.py    # 26 tests
│   └── test_healing_orchestrator.py # 23 tests
│
├── dashboard/                       # Next.js frontend (Vercel)
│   ├── app/                         # 7 pages (App Router)
│   │   ├── page.tsx                 # Dashboard overview
│   │   ├── anomalies/page.tsx       # Anomaly detection
│   │   ├── schemas/page.tsx         # Schema registry
│   │   ├── lineage/page.tsx         # Data lineage graph
│   │   ├── freshness/page.tsx       # Freshness SLA monitor
│   │   ├── healing/page.tsx         # Self-healing activity
│   │   └── alerts/page.tsx          # Alert management
│   │
│   ├── components/                  # Reusable UI components
│   │   ├── sidebar.tsx              # Collapsible navigation
│   │   ├── topbar.tsx               # Search + notifications
│   │   ├── stat-card.tsx            # Summary cards with sparklines
│   │   ├── donut-chart.tsx          # Health status visualization
│   │   ├── lineage-graph.tsx        # React Flow graph
│   │   └── ...                      # More components
│   │
│   └── lib/mock-data.ts            # Realistic mock data
│
└── pyproject.toml                   # Python project configuration
```

---

## 🚀 Quick Start

### Backend (Python)
```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests (150+ passing)
pytest

# Run specific test file
pytest tests/test_anomaly_detector.py -v
```

### Dashboard (Next.js)
```bash
cd dashboard
npm install
npm run dev
# → http://localhost:3000
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/data_quality_engine

# Run property-based tests only
pytest -m property

# Run specific component tests
pytest tests/test_drift_detector.py -v
pytest tests/test_lineage_engine.py -v
```

---

## 📊 Key Algorithms

| Algorithm | Purpose | Implementation |
|-----------|---------|---------------|
| **KS-test** | Detect distribution shifts | `scipy.stats.ks_2samp` comparing current vs 30-day baseline |
| **KL-divergence** | Measure distributional distance | Histogram-based with Laplace smoothing |
| **HyperLogLog** | Approximate distinct count | Custom impl with ≤2% error for cardinality >100K |
| **BFS Impact** | Find all downstream dependents | Breadth-first traversal of lineage DAG |
| **Exponential Smoothing** | Predict next data arrival | Inter-arrival intervals with α=0.3 |
| **Adaptive Thresholds** | Seasonality-aware detection | 7-day seasonal decomposition + smoothing |

---

## 🎯 Design Decisions

1. **Separation of detection from remediation** — Pluggable healing strategies, not hardcoded responses
2. **Graph-based lineage** — Enables impact analysis before changes propagate
3. **Adaptive thresholds** — Learn from history instead of relying on static rules
4. **Monotonic freshness** — Status can only worsen without new data (prevents false recovery)
5. **Bounded healing** — Max retries, max backoff, automatic escalation prevents infinite loops
6. **Lineage-driven alerting** — Only alert on root cause, not downstream symptoms

---

## 📜 License

MIT

---

**Built with 🔬 by [asheth2310](https://github.com/asheth2310)**
