# Project Structure — Stock Screening & Scoring Engine

## High-Level Architecture Map

```
stock-screening-engine/
│
├── dags/                          ORCHESTRATION LAYER
│   ├── etl/                       14 Airflow DAGs (9 daily + 5 backfill)
│   │   ├── sp500_lookup_dag.py         Root universe DAG (Wikipedia → Snowflake)
│   │   ├── polygon_daily_prices_dag.py Daily prices (gated on sp500_lookup)
│   │   ├── polygon_daily_rsi_dag.py    Daily RSI-14 (gated on sp500_lookup)
│   │   ├── polygon_daily_macd_dag.py   Daily MACD (gated on sp500_lookup)
│   │   ├── polygon_daily_news_dag.py   Daily news articles (gated on sp500_lookup)
│   │   ├── fmp_balance_sheet_dag.py    Annual balance sheets (gated on sp500_lookup)
│   │   ├── fmp_cash_flow_dag.py        Annual cash flow stmts (gated on sp500_lookup)
│   │   ├── fmp_income_statement_dag.py Annual income stmts (gated on sp500_lookup)
│   │   ├── fmp_news_daily_dag.py       FMP news (experimental, gated on sp500_lookup)
│   │   ├── polygon_prices_backfill_dag.py   398-day price backfill (manual trigger)
│   │   ├── polygon_rsi_backfill_dag.py      730-day RSI backfill (manual trigger)
│   │   ├── polygon_macd_backfill_dag.py     730-day MACD backfill (manual trigger)
│   │   └── polygon_news_backfill_dag.py     398-day news backfill (manual trigger)
│   └── dbt/
│       └── stock_screening_dbt_daily_dag.py Cosmos dbt DAG (gated on ALL daily ETL)
│
├── src/                           PYTHON ETL LAYER
│   ├── api_clients/               Fetch-only API clients (return DataFrames)
│   │   ├── polygon_client.py           Polygon.io: prices, RSI, MACD, SMA, news
│   │   ├── fmp_client.py               FMP: income stmts, balance sheets, cash flow, news
│   │   └── wikipedia_client.py         Wikipedia: S&P 500 constituent table
│   ├── jobs/                      Thin glue layer (fetch → load)
│   │   ├── ingest_sp500_lookup.py      Universe definition job
│   │   ├── ingest_polygon_prices.py    Daily prices job
│   │   ├── ingest_polygon_rsi.py       Daily RSI job
│   │   ├── ingest_polygon_macd.py      Daily MACD job
│   │   ├── ingest_polygon_news.py      Daily news job
│   │   ├── ingest_polygon_sma.py       SMA indicator job
│   │   ├── ingest_fmp_income_statement.py  FMP income stmts job
│   │   ├── ingest_fmp_balance_sheet.py     FMP balance sheets job
│   │   ├── ingest_fmp_cash_flow.py         FMP cash flow job
│   │   ├── ingest_fmp_news.py              FMP news job
│   │   ├── ingest_polygon_prices_backfill.py   Backfill variant
│   │   ├── ingest_polygon_rsi_backfill.py      Backfill variant
│   │   ├── ingest_polygon_macd_backfill.py     Backfill variant
│   │   └── ingest_polygon_news_backfill.py     Backfill variant
│   ├── loaders/                   Snowflake write-only operations
│   │   └── snowflake_loader.py         4 write strategies (partition/range × standard/VARIANT)
│   ├── mcp/                       MCP + Semantic Layer
│   │   ├── mcp_server.py               MCP server exposing 5 whitelisted mart tables
│   │   └── semantic_layer.yaml          616-line semantic definitions for AI queries
│   └── utils/
│       └── dates.py                Stateless date helpers
│
├── dbt_project/                   TRANSFORMATION LAYER
│   ├── dbt_project.yml            Project config: name, profile, schema routing
│   ├── profiles.yml               Snowflake connection (env-var based, dev + prod targets)
│   ├── packages.yml               dbt_utils, dbt_expectations, codegen
│   ├── models/
│   │   ├── staging/               Views — clean raw data, no business logic
│   │   │   ├── polygon/                4 models (prices, RSI, MACD, news) + sources
│   │   │   ├── fmp/                    4 models (income, balance, cash flow, news) + sources
│   │   │   └── wikipedia/              2 models (snapshot + current) + sources
│   │   ├── intermediate/          Incremental tables — derived computations
│   │   │   ├── int_sp500_daily_price_changes.sql   LAG-based daily changes
│   │   │   ├── int_sp500_technical_indicators.sql  SMA+RSI+MACD join
│   │   │   ├── int_sp500_price_returns.sql         Returns, volatility, drawdowns
│   │   │   └── int_sp500_fundamentals.sql          3-statement join + ratios + YoY growth
│   │   ├── dimensions/            Full-refresh tables — conforming dimensions
│   │   │   └── dim_sp500_companies_current.sql     Current S&P 500 universe dimension
│   │   └── marts/                 Incremental tables — analytics-ready scoring
│   │       ├── mart_sp500_technical_scores.sql      0-100 technical scoring
│   │       ├── mart_sp500_fundamental_scores.sql    0-100 fundamental scoring
│   │       ├── mart_sp500_composite_scores.sql      Blended tech+fundamental (3 weights)
│   │       ├── mart_sp500_industry_scores.sql       Composite + company/sector metadata
│   │       └── mart_sp500_price_performance.sql     Returns + risk + company metadata
│   └── tests/                     Custom singular tests
│       ├── assert_technical_score_in_range.sql
│       └── assert_fundamentals_score_in_range.sql
│
├── superset/                      BI LAYER
│   ├── Dockerfile                 Superset container image
│   └── superset_config.py         Superset configuration
│
├── tests/                         AIRFLOW TESTS
│   └── dags/test_dag_example.py   DAG integrity test
│
├── .astro/                        ASTRONOMER CLI
│   ├── config.yaml                Astro project config (port 8080, postgres 5431)
│   └── test_dag_integrity_default.py  DAG parse validation
│
├── Dockerfile                     Astro Runtime 3.1-9 image for Airflow
├── docker-compose.yml             Superset container orchestration
├── requirements.txt               Python deps (airflow-snowflake, cosmos, dbt-snowflake, etc.)
├── packages.txt                   OS-level packages (empty)
└── .mcp.json                      MCP server configuration for Claude Desktop
```

## Snowflake Schema Topology

```
Database: DATAEXPERT_STUDENT

BALAZSILLOVAI30823          ← RAW layer (Python loaders write here)
    sp500_stock_prices           Daily OHLCV prices (Polygon)
    sp500_stock_prices_backfill  Historical prices (Polygon)
    sp500_rsi / _backfill        RSI-14 daily (Polygon)
    sp500_macd / _backfill       MACD daily (Polygon)
    sp500_news / _backfill       News articles (Polygon)
    sp500_income_statements      Annual income stmts (FMP)
    sp500_balance_sheets         Annual balance sheets (FMP)
    sp500_cash_flow_statements   Annual cash flow stmts (FMP)
    sp500_fmp_news               News articles (FMP)
    sp500_tickers_lookup         S&P 500 universe (Wikipedia)

BALAZSILLOVAI30823_STG      ← dbt staging (views, source-cleaning)
BALAZSILLOVAI30823_INT      ← dbt intermediate (incremental computations)
BALAZSILLOVAI30823_DIM      ← dbt dimensions (current-state tables)
BALAZSILLOVAI30823_MARTS    ← dbt marts (scoring + ranking, exposed to MCP/Superset)
```

## Data Flow

```
Wikipedia ──→ sp500_lookup_dag ──→ sp500_tickers_lookup (RAW)
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
Polygon APIs ──→ daily ETL DAGs    FMP APIs ──→ FMP DAGs    (backfill DAGs)
    prices         │                 income      │
    RSI            │                 balance     │
    MACD           │                 cash flow   │
    news           │                 news        │
                   ▼                             ▼
            RAW tables (Snowflake base schema)
                              │
                    ExternalTaskSensors gate
                              │
                              ▼
              stock_screening_dbt_daily_dag (Cosmos)
                              │
                    ┌─────────┼──────────┐
                    ▼         ▼          ▼
                staging → intermediate → marts
                (views)   (incremental)  (incremental)
                              │
                    ┌─────────┼──────────┐
                    ▼                    ▼
              Superset              MCP Server
            (dashboards)         (Claude Desktop)
```

## Environment Topology

| Target | Schema Suffix | Purpose |
|--------|--------------|---------|
| `dev` | `BALAZSILLOVAI30823` | Development iteration |
| `prod` | `BALAZSILLOVAI30823_prod` | Production (not yet active) |

Both targets share `DATAEXPERT_STUDENT` database, `COMPUTE_WH` warehouse, `ALL_USERS_ROLE` role.
