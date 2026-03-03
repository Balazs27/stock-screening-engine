# General Index — Stock Screening Engine

Every source file with a one-sentence description of its exact responsibility.

---

## Root Configuration

| File | Responsibility |
|------|---------------|
| `CLAUDE.md` | Master routing file for agentic context with progressive disclosure references to rules, indexes, and state files. |
| `AGENTS.md` | Cross-tool mirror of CLAUDE.md for Cursor, Windsurf, and other AI coding tools. |
| `PROJECT_STRUCTURE.md` | High-level directory-to-purpose map, Snowflake schema topology, and data flow diagram. |
| `Dockerfile` | Astro Runtime 3.1-9 image that installs Python deps and copies the dbt project. |
| `docker-compose.yml` | Superset container orchestration with Snowflake-backed analytics. |
| `requirements.txt` | Python dependencies: airflow-snowflake, cosmos, dbt-snowflake, boring-semantic-layer, ibis, pandas, requests. |
| `packages.txt` | OS-level package list (currently empty). |
| `.mcp.json` | MCP server configuration pointing Claude Desktop to the stock-screening MCP server via stdio transport. |
| `.gitignore` | Git exclusion rules for .env files, venvs, dbt build artifacts, __pycache__, and agentic workspace files. |
| `.dockerignore` | Docker build exclusions for .git, .env, logs, and airflow state files. |
| `README.md` | Project overview, tech stack summary, architecture description, and current capabilities. |
| `airflow_settings.yaml` | Astronomer local development settings for Airflow connections, pools, and variables (template). |

## Astronomer CLI (`.astro/`)

| File | Responsibility |
|------|---------------|
| `.astro/config.yaml` | Astro project config: project name, webserver port 8080, postgres port 5431, debug verbosity. |
| `.astro/dag_integrity_exceptions.txt` | Exclusion list for DAGs exempt from parse integrity testing (currently empty). |
| `.astro/test_dag_integrity_default.py` | Monkeypatched DAG parse validator that tests all DAGs import without errors. |

## Airflow DAGs (`dags/`)

### Daily ETL DAGs (27)

| File | Responsibility |
|------|---------------|
| `dags/etl/sp500_lookup_dag.py` | Root universe DAG: fetches S&P 500 constituents from Wikipedia daily; all other daily DAGs depend on this. |
| `dags/etl/polygon_daily_prices_dag.py` | Fetches single-day OHLCV prices from Polygon for all S&P 500 tickers; gated on sp500_lookup. |
| `dags/etl/polygon_daily_rsi_dag.py` | Fetches latest RSI-14 value from Polygon for all tickers; gated on sp500_lookup. |
| `dags/etl/polygon_daily_macd_dag.py` | Fetches latest MACD(12,26,9) from Polygon for all tickers; gated on sp500_lookup. |
| `dags/etl/polygon_daily_news_dag.py` | Fetches up to 10 news articles per ticker from Polygon for the run date; gated on sp500_lookup. |
| `dags/etl/polygon_sma_dag.py` | Fetches Polygon SMA-30 indicator daily; gated on sp500_lookup. |
| `dags/etl/polygon_ticker_details_dag.py` | Fetches Polygon ticker details daily; gated on sp500_lookup. |
| `dags/etl/polygon_benchmark_prices_dag.py` | Fetches Polygon benchmark/sector ETF and VIX prices daily; gated on sp500_lookup. |
| `dags/etl/polygon_stock_snapshot_dag.py` | Fetches Polygon stock snapshot daily; gated on sp500_lookup. |
| `dags/etl/fmp_income_statement_dag.py` | Fetches annual income statements from FMP for all tickers; gated on sp500_lookup. |
| `dags/etl/fmp_balance_sheet_dag.py` | Fetches annual balance sheets from FMP for all tickers; gated on sp500_lookup. |
| `dags/etl/fmp_cash_flow_dag.py` | Fetches annual cash flow statements from FMP for all tickers; gated on sp500_lookup. |
| `dags/etl/fmp_income_statement_q_dag.py` | Fetches FMP quarterly income statements daily; gated on sp500_lookup. |
| `dags/etl/fmp_balance_sheet_q_dag.py` | Fetches FMP quarterly balance sheets daily; gated on sp500_lookup. |
| `dags/etl/fmp_cash_flow_q_dag.py` | Fetches FMP quarterly cash flow statements daily; gated on sp500_lookup. |
| `dags/etl/fmp_articles_daily_dag.py` | Fetches FMP articles for S&P 500 tickers daily (dag_id=fmp_news_daily); gated on sp500_lookup. |
| `dags/etl/fmp_stock_news_dag.py` | Fetches FMP stock news for S&P 500 tickers daily; gated on sp500_lookup. |
| `dags/etl/fmp_global_news_dag.py` | Fetches FMP general news daily; no upstream sensor (independent source). |
| `dags/etl/fmp_press_releases_dag.py` | Fetches FMP press releases daily; no upstream sensor (independent source). |
| `dags/etl/fmp_earnings_calendar_dag.py` | Fetches FMP earnings calendar daily; gated on sp500_lookup. |
| `dags/etl/fmp_key_metrics_dag.py` | Fetches FMP key metrics daily; gated on sp500_lookup. |
| `dags/etl/fmp_analyst_consensus_dag.py` | Fetches FMP analyst price targets and upgrades/downgrades consensus daily; gated on sp500_lookup. |
| `dags/etl/fmp_dividends_dag.py` | Fetches FMP dividend history daily; gated on sp500_lookup. |
| `dags/etl/fmp_splits_dag.py` | Fetches FMP stock splits daily; gated on sp500_lookup. |
| `dags/etl/fmp_insider_trades_dag.py` | Fetches FMP insider trades from paginated global feed daily; gated on sp500_lookup. |
| `dags/etl/fmp_insider_trades_search_dag.py` | Fetches FMP insider trades search feed daily; gated on sp500_lookup. |
| `dags/etl/fred_macro_rates_dag.py` | Fetches FRED macro rate series observations daily; no upstream sensor (independent source). |

### Backfill DAGs (14, Manual Trigger)

| File | Responsibility |
|------|---------------|
| `dags/etl/polygon_prices_backfill_dag.py` | Backfills 398 days of historical prices from Polygon; schedule=None, manual trigger only. |
| `dags/etl/polygon_rsi_backfill_dag.py` | Backfills 730 days of historical RSI from Polygon; schedule=None. |
| `dags/etl/polygon_macd_backfill_dag.py` | Backfills 730 days of historical MACD from Polygon; schedule=None. |
| `dags/etl/polygon_news_backfill_dag.py` | Backfills 398 days of historical news from Polygon with VARIANT column handling; schedule=None. |
| `dags/etl/polygon_benchmark_prices_backfill_dag.py` | Backfills 5yr of Polygon benchmark prices; schedule=None. |
| `dags/etl/fmp_articles_backfill_dag.py` | Backfills 5yr of FMP articles; schedule=None. |
| `dags/etl/fmp_general_news_backfill_dag.py` | Backfills 5yr of FMP general news; schedule=None. |
| `dags/etl/fmp_press_releases_backfill_dag.py` | Backfills 5yr of FMP press releases; schedule=None. |
| `dags/etl/fmp_stock_news_backfill_dag.py` | Backfills 5yr of FMP stock news; schedule=None. |
| `dags/etl/fmp_key_metrics_backfill_dag.py` | Backfills 5yr of key metrics; schedule=None. |
| `dags/etl/fmp_dividends_backfill_dag.py` | Backfills 5yr of dividend history; schedule=None. |
| `dags/etl/fmp_insider_trades_backfill_dag.py` | Backfills 5yr of insider trades; schedule=None. |
| `dags/etl/fmp_insider_trades_search_backfill_dag.py` | Backfills 5yr of insider trades search; schedule=None. |
| `dags/etl/fred_macro_rates_backfill_dag.py` | Backfills 5yr of FRED macro rates; schedule=None. |

### dbt DAG

| File | Responsibility |
|------|---------------|
| `dags/dbt/stock_screening_dbt_daily_dag.py` | Cosmos-based dbt DAG that gates on all 5 daily ETL DAGs via ExternalTaskSensors, then runs full dbt build. |

### Other

| File | Responsibility |
|------|---------------|
| `dags/exampledag.py` | Astronomer example DAG (astronaut API); not part of the analytics pipeline. |
| `dags/stock_screening_dag.py` | Legacy/placeholder DAG (empty or negligible). |

## Python Source (`src/`)

### API Clients

| File | Responsibility |
|------|---------------|
| `src/api_clients/polygon_client.py` | Polygon.io client with rate limiting (0.8s/req), 3x retries, 8-worker concurrent fetch; 9 methods: fetch_reference_tickers, fetch_stock_prices, fetch_stock_prices_range, fetch_indicator (RSI/SMA), fetch_macd, fetch_news, fetch_news_range, fetch_ticker_details, fetch_stock_snapshot. |
| `src/api_clients/fmp_client.py` | FMP API client with rate limiting (0.1s/req), 3x retries, 8-worker concurrent fetch; 15 methods: fetch_income_statements, fetch_balance_sheets, fetch_cash_flow_statements, fetch_fmp_articles, fetch_general_news, fetch_press_releases, fetch_stock_news, fetch_earnings_calendar, fetch_key_metrics, fetch_price_target_consensus, fetch_upgrades_downgrades_consensus, fetch_dividends, fetch_splits, fetch_insider_trades_latest, fetch_insider_trades_search. |
| `src/api_clients/wikipedia_client.py` | Wikipedia client that scrapes S&P 500 constituent table with retry-with-backoff on 403 rate limits. |
| `src/api_clients/fred_client.py` | FRED API client for macro rate series (Fed Funds Rate, 10Y Treasury, CPI, etc.); 0.5s rate limiting per request. |

### Daily Jobs (27)

| File | Responsibility |
|------|---------------|
| `src/jobs/ingest_sp500_lookup.py` | Fetches Wikipedia S&P 500 universe and writes to Snowflake via `overwrite_partition()`. |
| `src/jobs/ingest_polygon_prices.py` | Fetches single-day Polygon prices for all tickers and writes via `overwrite_partition()`. |
| `src/jobs/ingest_polygon_rsi.py` | Fetches latest Polygon RSI-14 (limit=1) and writes via `overwrite_partition()`. |
| `src/jobs/ingest_polygon_macd.py` | Fetches latest Polygon MACD (limit=1) and writes via `overwrite_partition()`. |
| `src/jobs/ingest_polygon_news.py` | Fetches daily Polygon news (10/ticker) and writes via `overwrite_partition_with_variants()`. |
| `src/jobs/ingest_polygon_sma.py` | Fetches Polygon SMA-30 (limit=120) and writes via `overwrite_partition()`. |
| `src/jobs/ingest_polygon_ticker_details.py` | Fetches Polygon ticker details (market cap, description, employees, SIC) for all tickers and writes to `sp500_ticker_details` via `overwrite_partition()`. |
| `src/jobs/ingest_polygon_benchmark_prices.py` | Fetches Polygon daily prices for benchmark/sector ETFs and VIX and writes to `sp500_benchmark_prices` via `overwrite_partition()`. |
| `src/jobs/ingest_polygon_stock_snapshot.py` | Fetches Polygon stock snapshot (price, quote, trade) for all tickers and writes to `sp500_stock_snapshot` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_income_statement.py` | Fetches FMP annual income statements and writes via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_balance_sheet.py` | Fetches FMP annual balance sheets and writes via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_cash_flow.py` | Fetches FMP annual cash flow statements and writes via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_income_statement_q.py` | Fetches FMP quarterly income statements for all tickers and writes to `sp500_income_statements_q` via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_balance_sheet_q.py` | Fetches FMP quarterly balance sheets for all tickers and writes to `sp500_balance_sheets_q` via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_cash_flow_q.py` | Fetches FMP quarterly cash flow statements for all tickers and writes to `sp500_cash_flow_statements_q` via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_articles.py` | Fetches FMP articles for S&P 500 tickers and writes to `sp500_fmp_news` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_general_news.py` | Fetches FMP general news unfiltered (no S&P 500 dependency) and writes to `sp500_fmp_general_news` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_press_releases.py` | Fetches FMP press releases unfiltered (no S&P 500 dependency) and writes to `sp500_fmp_press_releases` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_stock_news.py` | Fetches FMP stock news for S&P 500 tickers and writes to `sp500_fmp_stock_news` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_earnings_calendar.py` | Fetches FMP earnings calendar (upcoming earnings dates) per ticker and writes to `sp500_earnings_calendar` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_key_metrics.py` | Fetches FMP key metrics (P/E, EV/EBITDA, P/B, etc.) per ticker and writes to `sp500_key_metrics` via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_analyst_consensus.py` | Fetches FMP price target consensus and upgrades/downgrades consensus per ticker and writes to `sp500_price_target_consensus` and `sp500_upgrades_downgrades` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_dividends.py` | Fetches FMP dividend history per ticker and writes to `sp500_dividends` via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_splits.py` | Fetches FMP stock split history per ticker and writes to `sp500_splits` via `overwrite_date_range()`. |
| `src/jobs/ingest_fmp_insider_trades.py` | Fetches FMP insider trades from paginated global feed and writes to `sp500_insider_trades` via `overwrite_partition()`. |
| `src/jobs/ingest_fmp_insider_trades_search.py` | Fetches FMP insider trades search feed (paginated global) and writes to `sp500_insider_trades_search` via `overwrite_partition()`. |
| `src/jobs/ingest_fred_macro_rates.py` | Fetches latest FRED macro rate series observations and writes to `sp500_macro_rates` via `overwrite_partition()`. |

### Backfill Jobs (14)

| File | Responsibility |
|------|---------------|
| `src/jobs/ingest_polygon_prices_backfill.py` | Backfills 398 days of Polygon prices via `overwrite_date_range()` with CLUSTER BY. |
| `src/jobs/ingest_polygon_rsi_backfill.py` | Backfills 730 days of Polygon RSI via `overwrite_date_range()`. |
| `src/jobs/ingest_polygon_macd_backfill.py` | Backfills 730 days of Polygon MACD via `overwrite_date_range()`. |
| `src/jobs/ingest_polygon_news_backfill.py` | Backfills 398 days of Polygon news via `overwrite_date_range_with_variants()`. |
| `src/jobs/ingest_polygon_benchmark_prices_backfill.py` | Backfills 5yr of Polygon benchmark prices via `overwrite_date_range()`; DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_articles_backfill.py` | Backfills 5yr of FMP articles via deep pagination (max_pages=5000); DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_general_news_backfill.py` | Backfills 5yr of FMP general news via deep pagination; DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_press_releases_backfill.py` | Backfills 5yr of FMP press releases via deep pagination; DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_stock_news_backfill.py` | Backfills 5yr of FMP stock news via deep pagination; DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_key_metrics_backfill.py` | Backfills 5yr of key metrics (quarterly); DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_dividends_backfill.py` | Backfills 5yr of dividend history per ticker; DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_insider_trades_backfill.py` | Backfills 5yr of insider trades via deep pagination; DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fmp_insider_trades_search_backfill.py` | Backfills 5yr of insider trades search feed; DEFAULT_LOOKBACK_DAYS = 1826. |
| `src/jobs/ingest_fred_macro_rates_backfill.py` | Backfills 5yr of FRED macro rate series via `overwrite_date_range()`; DEFAULT_LOOKBACK_DAYS = 1826. |

### Loaders

| File | Responsibility |
|------|---------------|
| `src/loaders/snowflake_loader.py` | Snowflake write operations: `get_snowflake_session()`, `get_sp500_tickers()`, `overwrite_partition()`, `overwrite_date_range()`, plus VARIANT-aware variants for JSON columns. |

### MCP + Semantic Layer

| File | Responsibility |
|------|---------------|
| `src/mcp/mcp_server.py` | MCP server exposing 5 whitelisted mart tables via boring-semantic-layer + ibis for Snowflake; connects to `{STUDENT_SCHEMA}_marts`. |
| `src/mcp/semantic_layer.yaml` | 616-line semantic layer defining 5 models (technical_scores, fundamental_scores, composite_scores, industry_scores, price_performance) with dimensions, measures, and AI analytical guide. |

### Utilities

| File | Responsibility |
|------|---------------|
| `src/utils/dates.py` | Single function `today()` returning current date as YYYY-MM-DD string. |

## dbt Project (`dbt_project/`)

### Configuration

| File | Responsibility |
|------|---------------|
| `dbt_project/dbt_project.yml` | Project config: name=stock_screening_engine, schema routing (staging=_stg, intermediate=_int, dimensions=_dim, marts=_marts). |
| `dbt_project/profiles.yml` | Snowflake connection profiles (dev + prod targets) using env-var credentials, ALL_USERS_ROLE, COMPUTE_WH. |
| `dbt_project/packages.yml` | dbt packages: dbt_utils 1.1.1, dbt_expectations 0.10.3, codegen 0.12.1. |
| `dbt_project/dbt-requirements.txt` | dbt Python deps: dbt-snowflake 1.10.4, sqlfluff 3.4.0. |

### Staging Models (Views)

| File | Responsibility |
|------|---------------|
| `models/staging/polygon/stg_sp500_stock_prices.sql` | Passthrough view selecting ticker, OHLCV, vwap, transactions, date from raw prices. |
| `models/staging/polygon/stg_sp500_rsi.sql` | Passthrough view selecting ticker, timestamp, rsi_value, window params, date from raw RSI. |
| `models/staging/polygon/stg_sp500_macd.sql` | Passthrough view selecting ticker, timestamp, MACD/signal/histogram values, window params, date from raw MACD. |
| `models/staging/polygon/stg_sp500_news.sql` | Passthrough view selecting ticker, article metadata, publisher info, tickers, keywords, date from raw Polygon news. |
| `models/staging/fmp/stg_fmp_income_statement.sql` | Passthrough view selecting 45+ income statement fields from raw FMP income statements. |
| `models/staging/fmp/stg_fmp_balance_sheet.sql` | Passthrough view selecting 60+ balance sheet fields from raw FMP balance sheets. |
| `models/staging/fmp/stg_fmp_cash_flow.sql` | Passthrough view selecting 45+ cash flow fields from raw FMP cash flow statements. |
| `models/staging/fmp/stg_fmp_news.sql` | Passthrough view selecting ticker, title, content, article metadata from raw FMP news. |
| `models/staging/wikipedia/stg_sp500_tickers_snapshot.sql` | View transforming raw Wikipedia lookup into typed columns with date_added_year extraction; grain=(ticker, as_of_date). |
| `models/staging/wikipedia/stg_sp500_tickers_current.sql` | Latest-date filter view on snapshot staging; grain=(ticker), unique on ticker. |

### Source Definitions

| File | Responsibility |
|------|---------------|
| `models/staging/polygon/_sources.yml` | Declares 8 Polygon raw tables (daily + backfill for prices, RSI, MACD, news). |
| `models/staging/fmp/_sources.yml` | Declares 4 FMP raw tables (income, balance, cash flow, news). |
| `models/staging/wikipedia/_sources.yml` | Declares 1 Wikipedia raw table (sp500_tickers_lookup). |

### Schema Definitions

| File | Responsibility |
|------|---------------|
| `models/staging/polygon/stg_polygon.yml` | Schema definitions for 4 Polygon staging models with not_null tests on ticker. |
| `models/staging/fmp/stg_fmp.yml` | Schema definitions for 4 FMP staging models with not_null tests on ticker. |
| `models/staging/wikipedia/stg_wikipedia.yml` | Schema definitions for 2 Wikipedia staging models with not_null+unique tests. |
| `models/intermediate/int.yml` | Schema definitions for 4 intermediate models with not_null tests on ticker. |
| `models/dimensions/dim.yml` | Schema definition for dim_sp500_companies_current with unique+not_null tests on ticker. |
| `models/marts/mart.yml` | Schema definitions for 5 mart models with not_null tests on ticker and score columns. |

### Intermediate Models (Incremental Tables)

| File | Responsibility |
|------|---------------|
| `models/intermediate/int_sp500_daily_price_changes.sql` | Incremental delete+insert computing daily price changes via LAG(); 4-day source lookback, 3-day output filter. |
| `models/intermediate/int_sp500_technical_indicators.sql` | Incremental delete+insert joining SMA-20/50/200 + RSI + MACD; 300-day source lookback for SMA-200. |
| `models/intermediate/int_sp500_price_returns.sql` | Incremental delete+insert computing daily/cumulative/rolling returns, volatility, drawdowns; full-scan source for FIRST_VALUE/MAX unbounded. |
| `models/intermediate/int_sp500_fundamentals.sql` | Full-refresh table joining income+balance+cash-flow statements, computing 15+ derived ratios and 5 YoY growth metrics. |

### Dimension Models (Full-Refresh Tables)

| File | Responsibility |
|------|---------------|
| `models/dimensions/dim_sp500_companies_current.sql` | Current S&P 500 universe dimension: ticker, company name, sector, industry, location, CIK, founded year. |

### Mart Models (Incremental Tables)

| File | Responsibility |
|------|---------------|
| `models/marts/mart_sp500_technical_scores.sql` | Incremental 0-100 scoring: trend(40pts) + momentum(30pts) + price_action(20pts) + MACD(10pts); 40-day lookback. |
| `models/marts/mart_sp500_fundamental_scores.sql` | Full-refresh 0-100 scoring: profitability(25pts) + growth(30pts) + health(25pts) + cash(20pts). |
| `models/marts/mart_sp500_composite_scores.sql` | Incremental blending: technical × fundamental with 3 weighting variants (50/50, 60/40, 40/60); fiscal-year period join. |
| `models/marts/mart_sp500_industry_scores.sql` | Incremental enrichment: composite scores joined with dim_sp500_companies_current for sector/industry metadata. |
| `models/marts/mart_sp500_price_performance.sql` | Incremental enrichment: price returns joined with dim for company/sector/industry metadata; 7-day lookback. |

### Custom Tests

| File | Responsibility |
|------|---------------|
| `tests/assert_technical_score_in_range.sql` | Validates technical_score is between 0-100 and not null; returns violating rows. |
| `tests/assert_fundamentals_score_in_range.sql` | Validates fundamentals_score is between 0-100 and not null; returns violating rows. |

## Superset (`superset/`)

| File | Responsibility |
|------|---------------|
| `superset/Dockerfile` | Superset container image with snowflake-sqlalchemy driver for Snowflake connectivity. |
| `superset/superset_config.py` | Superset app configuration. |

## Airflow Tests (`tests/`)

| File | Responsibility |
|------|---------------|
| `tests/dags/test_dag_example.py` | Example DAG test file for Astronomer CI/CD pipeline validation. |
