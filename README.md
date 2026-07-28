# Data Quality & Observability Engine

Production-grade platform for monitoring data pipelines — schema drift detection, statistical anomaly detection, column-level lineage, freshness SLA monitoring, and self-healing orchestration.

## Features

- **Schema Registry & Drift Detector** — Versioned contracts, type-width severity classification, auto-evolution
- **Statistical Profiler** — Numeric/string stats, HyperLogLog cardinality, histograms
- **Anomaly Detection Engine** — KS-test, KL-divergence, adaptive seasonality-aware thresholds
- **Lineage Graph Engine** — Column-level DAG, cycle detection, BFS impact analysis, root cause tracing
- **Freshness SLA Monitor** — Monotonic degradation, predictive alerting via exponential smoothing
- **Self-Healing Orchestrator** — Diagnose, retry with backoff, quarantine, backfill, escalate

## Tech Stack

Python, FastAPI, Pydantic v2, scipy, numpy, PostgreSQL, TimescaleDB, Neo4j, Redis, Kafka, Celery

## Quick Start

```bash
pip install -e ".[dev]"
pytest
```

## Project Structure

```
src/data_quality_engine/
  models/       # Pydantic v2 data models
  services/     # Core business logic
  storage/      # Storage abstractions (in-memory implementations)
  api/          # FastAPI endpoints (WIP)
  tasks/        # Celery async tasks (WIP)
tests/          # 150+ unit tests
```

## Status

Core engine implemented and tested. Remaining: REST API layer, Kafka events, Celery tasks, integration tests.
