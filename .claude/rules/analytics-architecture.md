# Rule: Analytics Architecture

Defines layer boundaries, dependency rules, naming conventions, and what belongs where in this analytics system.

---

## Layer Definitions

| Layer | Schema Suffix | Materialization | Purpose | Business Logic Allowed |
|-------|--------------|-----------------|---------|----------------------|
| **RAW** | (base schema) | N/A (Python loader) | Land API data exactly as fetched | NO |
| **Staging** | `_stg` | view | Clean, type-cast, rename raw columns | NO |
| **Intermediate** | `_int` | incremental table or table | Derive computed metrics, join related staging models | YES (computations only) |
| **Dimensions** | `_dim` | table (full refresh) | Conforming entity attributes for joins | NO (attribute pass-through only) |
| **Marts** | `_marts` | incremental table or table | Analytics-ready scoring, ranking, enrichment | YES (scoring, weighting, enrichment) |

## Dependency Rules (STRICTLY ENFORCED)

```
staging    → refs ONLY source()
intermediate → refs staging OR other intermediate (same layer)
dimensions → refs staging ONLY
marts      → refs intermediate, dimensions, OR other marts
```

**Forbidden cross-layer references:**
- Staging must NEVER ref intermediate, dimensions, or marts
- Dimensions must NEVER ref intermediate or marts
- No model may ref raw tables directly (must go through staging)
- Marts must NEVER ref staging directly (must flow through intermediate)

## Naming Conventions

| Layer | Pattern | Example |
|-------|---------|---------|
| Staging | `stg_{source}_{entity}` | `stg_polygon_stock_prices`, `stg_fmp_balance_sheet` |
| Intermediate | `int_sp500_{concept}` | `int_sp500_technical_indicators`, `int_sp500_price_returns` |
| Dimensions | `dim_{entity}_{qualifier}` | `dim_sp500_companies_current` |
| Marts | `mart_sp500_{domain}` | `mart_sp500_technical_scores`, `mart_sp500_price_performance` |
| Sources YAML | `_sources.yml` (per source system) | `models/staging/polygon/_sources.yml` |
| Schema YAML | `stg_{source}.yml` or `int.yml` / `mart.yml` | One YAML per layer group |

## Schema Routing (dbt_project.yml)

```yaml
models:
  stock_screening_engine:
    staging:
      +materialized: view
      +schema: stg
    intermediate:
      +materialized: table
      +schema: int
    dimensions:
      +materialized: table
      +schema: dim
    marts:
      +materialized: table
      +schema: marts
```

Individual models override `+materialized` via `{{ config() }}` blocks (e.g., incremental).

## Source System Boundaries

| Source | API Client | Loader Strategy | Raw Tables |
|--------|-----------|-----------------|------------|
| Polygon | `polygon_client.py` | `overwrite_partition()` / `overwrite_date_range()` | prices, RSI, MACD, news (+ backfill variants) |
| FMP | `fmp_client.py` | `overwrite_partition()` / `overwrite_date_range()` | income, balance, cash flow, news |
| Wikipedia | `wikipedia_client.py` | `overwrite_partition()` | sp500_tickers_lookup |

## Exposure Rules

| Consumer | Allowed Schema | Enforcement |
|----------|---------------|-------------|
| MCP Server | `_marts` ONLY | Hardcoded whitelist in `mcp_server.py` |
| Superset | `_marts` ONLY | Connection string points to marts schema |
| Internal dbt | All schemas | Normal dbt ref/source resolution |

**NEVER expose RAW, STG, or INT schemas to external consumers (MCP, Superset, APIs).**

## Separation of Concerns (Python Layer)

```
api_clients/  → Fetch data from external APIs, return DataFrames. NEVER touch Snowflake.
loaders/      → Write DataFrames to Snowflake. NEVER call APIs.
jobs/         → Thin glue: call client → call loader. NO business logic.
dags/         → Orchestration only: task ordering, dependencies, scheduling. NO data logic.
mcp/          → Read-only exposure of marts. NEVER write to warehouse.
```
