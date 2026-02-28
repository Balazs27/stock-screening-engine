# AGENTS.md — Stock Screening & Scoring Engine

Cross-tool context file (Cursor, Windsurf, Copilot Workspace). Mirrors CLAUDE.md.

**NO HALF MEASURES. NO MVP. ONLY FULL PRODUCTION-GRADE ANALYTICS.**

S&P 500 analytics platform: ingest market data (Polygon, FMP, Wikipedia) → transform via dbt on Snowflake → compute 0-100 stock scores → rank daily → expose via Superset dashboards and MCP semantic layer for Claude Desktop.

---

## Environment Setup

```bash
# Python ETL environment (from project root)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# dbt environment (from dbt_project/)
cd dbt_project
python -m venv venv && source venv/bin/activate
pip install -r dbt-requirements.txt
dbt deps

# Airflow local (Astronomer CLI)
astro dev start
```

## Build & Test Commands

```bash
# dbt (run from dbt_project/)
dbt build                                          # run + test all models
dbt run --select +mart_sp500_composite_scores      # run composite and all upstream
dbt test --select mart_sp500_technical_scores      # test a specific model
dbt run --full-refresh --select int_sp500_price_returns  # force full rebuild

# Linting
sqlfluff lint dbt_project/models/                  # SQL linting
sqlfluff fix dbt_project/models/                   # Auto-fix SQL style

# Airflow
astro dev parse                                    # Validate all DAGs parse
astro dev pytest                                   # Run DAG integrity tests
```

## Architecture Reference

See @PROJECT_STRUCTURE.md for directory map, Snowflake schema topology, and data flow diagram.

## File Indexes

- @general_index.md — Every source file with one-sentence description
- @detailed_index.md — Grains, materializations, dependencies, scoring weights, test coverage

## Rule Matrix

- @.claude/rules/analytics-architecture.md — Layer boundaries, naming, dependency rules, separation of concerns
- @.claude/rules/data-contracts.md — Grains, primary keys, dimensional modeling, YAML standards
- @.claude/rules/warehouse-performance.md — Incremental strategies, lookback sizing, scan minimization, cost controls
- @.claude/rules/incremental-and-scd.md — delete+insert patterns, watermarks, idempotency, SCD handling
- @.claude/rules/data-quality-and-observability.md — Test tiers, freshness, stop-the-line failures, coverage gaps
- @.claude/rules/security-and-privacy-guardrails.md — Credentials, MCP isolation, forbidden files, access control
- @.claude/rules/analytics-testing-standards.md — Test hierarchy, reconciliation checks, auditability

## State Management

- @.claude/memory/MEMORY.md — Operational learnings (symptom → cause → solution)
- @.claude/memory/active_plan.md — Current multi-step refactoring blueprint
- @.claude/memory/changelog.md — Pre-commit action ledger

## Core Design Rules

1. **Wikipedia defines WHAT exists** — canonical S&P 500 universe
2. **Strict separation** — api_clients/ fetch only, loaders/ write only, jobs/ glue only, dags/ orchestrate only
3. **Snowflake is truth** — all schemas: RAW → _stg → _int → _dim → _marts
4. **dbt defines meaning** — staging=views, intermediate=incremental, marts=incremental scoring
5. **Airflow controls time** — daily ETL gated by ExternalTaskSensors, Cosmos for dbt
6. **Marts only exposed** — MCP and Superset read from _marts schema exclusively
7. **All incrementals use delete+insert** — never merge, always idempotent
8. **Snowflake identifiers are UPPERCASE** — dbt SQL uses lowercase, Snowflake stores uppercase
9. **Scores are 0-100** — enforced by custom singular tests

## Forbidden Actions

- NEVER read .env, dbt.env, or files containing credentials
- NEVER expose RAW/STG/INT schemas to MCP or Superset
- NEVER mix business logic into DAGs or loaders
- NEVER use merge incremental strategy
- NEVER hardcode dates in incremental watermarks
- NEVER add CLUSTER BY to daily-load tables
- NEVER handle VARIANT parsing in dbt (belongs in Python loader)
- NEVER bypass the semantic layer for AI queries
- NEVER import from deprecated `airflow.operators.*` (use `airflow.providers.standard.*`)

## Mental Model

Wikipedia defines WHAT exists. APIs define WHAT happens. Snowflake stores TRUTH.
dbt defines MEANING. Airflow controls TIME. Superset shows INSIGHT. MCP enables INTELLIGENCE.
