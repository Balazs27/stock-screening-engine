# Project Structure — Stock Screening & Scoring Engine

## High-Level Architecture Map

```
stock-screening-engine/
│
├── dags/                          ORCHESTRATION LAYER
│   ├── etl/                       41 Airflow DAGs (27 daily + 14 backfill)
│   │   │
│   │   │── # Root Universe DAG
│   │   ├── sp500_lookup_dag.py                    Root universe DAG (Wikipedia → Snowflake)
│   │   │
│   │   │── # Polygon Daily DAGs (8, all gated on sp500_lookup)
│   │   ├── polygon_daily_prices_dag.py            Daily OHLCV prices
│   │   ├── polygon_daily_rsi_dag.py               Daily RSI-14
│   │   ├── polygon_daily_macd_dag.py              Daily MACD(12,26,9)
│   │   ├── polygon_daily_news_dag.py              Daily news articles
│   │   ├── polygon_sma_dag.py                     Daily SMA-30
│   │   ├── polygon_ticker_details_dag.py          Ticker details (market cap, SIC, etc.)
│   │   ├── polygon_benchmark_prices_dag.py        Benchmark/sector ETF + VIX prices
│   │   ├── polygon_stock_snapshot_dag.py          Stock snapshot (price, quote, trade)
│   │   │
│   │   │── # FMP Financial Statement DAGs (6, all gated on sp500_lookup)
│   │   ├── fmp_income_statement_dag.py            Annual income statements
│   │   ├── fmp_balance_sheet_dag.py               Annual balance sheets
│   │   ├── fmp_cash_flow_dag.py                   Annual cash flow statements
│   │   ├── fmp_income_statement_q_dag.py          Quarterly income statements
│   │   ├── fmp_balance_sheet_q_dag.py             Quarterly balance sheets
│   │   ├── fmp_cash_flow_q_dag.py                 Quarterly cash flow statements
│   │   │
│   │   │── # FMP Market Data DAGs (6, all gated on sp500_lookup)
│   │   ├── fmp_key_metrics_dag.py                 Key metrics (P/E, EV/EBITDA, P/B, etc.)
│   │   ├── fmp_analyst_consensus_dag.py           Price target + upgrades/downgrades consensus
│   │   ├── fmp_earnings_calendar_dag.py           Earnings calendar dates
│   │   ├── fmp_dividends_dag.py                   Dividend history
│   │   ├── fmp_splits_dag.py                      Stock split history
│   │   ├── fmp_insider_trades_dag.py              Insider trades (paginated global feed)
│   │   │
│   │   │── # FMP News/Text DAGs (5)
│   │   ├── fmp_articles_daily_dag.py              FMP articles (gated on sp500_lookup)
│   │   ├── fmp_stock_news_dag.py                  Stock news (gated on sp500_lookup)
│   │   ├── fmp_insider_trades_search_dag.py       Insider trades search feed (gated on sp500_lookup)
│   │   ├── fmp_global_news_dag.py                 General news (no sensor, unfiltered feed)
│   │   ├── fmp_press_releases_dag.py              Press releases (no sensor, unfiltered feed)
│   │   │
│   │   │── # FRED DAG (1, gated on sp500_lookup)
│   │   ├── fred_macro_rates_dag.py                Macro rate series (Fed Funds, 10Y, CPI, etc.)
│   │   │
│   │   │── # Polygon Backfill DAGs (5, schedule=None, manual trigger)
│   │   ├── polygon_prices_backfill_dag.py         398-day price backfill
│   │   ├── polygon_rsi_backfill_dag.py            730-day RSI backfill
│   │   ├── polygon_macd_backfill_dag.py           730-day MACD backfill
│   │   ├── polygon_news_backfill_dag.py           398-day news backfill
│   │   ├── polygon_benchmark_prices_backfill_dag.py  5yr benchmark prices backfill
│   │   │
│   │   │── # FMP Backfill DAGs (7, schedule=None, manual trigger)
│   │   ├── fmp_articles_backfill_dag.py           5yr FMP articles backfill
│   │   ├── fmp_general_news_backfill_dag.py       5yr general news backfill
│   │   ├── fmp_press_releases_backfill_dag.py     5yr press releases backfill
│   │   ├── fmp_stock_news_backfill_dag.py         5yr stock news backfill
│   │   ├── fmp_dividends_backfill_dag.py          5yr dividend history backfill
│   │   ├── fmp_key_metrics_backfill_dag.py        5yr key metrics backfill
│   │   ├── fmp_insider_trades_backfill_dag.py     5yr insider trades backfill
│   │   │
│   │   │── # Other Backfill DAGs (2, schedule=None, manual trigger)
│   │   ├── fmp_insider_trades_search_backfill_dag.py  5yr insider trades search backfill
│   │   └── fred_macro_rates_backfill_dag.py       5yr FRED macro rates backfill
│   │
│   └── dbt/
│       └── stock_screening_dbt_daily_dag.py Cosmos dbt DAG (gated on ALL daily ETL)
│
├── src/                           PYTHON ETL LAYER
│   ├── api_clients/               Fetch-only API clients (return DataFrames)
│   │   ├── polygon_client.py           Polygon.io: prices, RSI, MACD, SMA, news, ticker details, snapshot, benchmark prices
│   │   ├── fmp_client.py               FMP: financials, key metrics, earnings, analyst consensus, dividends, splits, insider trades, news
│   │   ├── wikipedia_client.py         Wikipedia: S&P 500 constituent table
│   │   └── fred_client.py              FRED: macro rate series (Fed Funds, 10Y Treasury, CPI, etc.)
│   ├── jobs/                      41 job files (27 daily + 14 backfill)
│   │   │
│   │   │── # Universe
│   │   ├── ingest_sp500_lookup.py                 Universe definition job
│   │   │
│   │   │── # Polygon Daily Jobs (8)
│   │   ├── ingest_polygon_prices.py               Daily OHLCV prices
│   │   ├── ingest_polygon_rsi.py                  Daily RSI-14 (limit=1)
│   │   ├── ingest_polygon_macd.py                 Daily MACD (limit=1)
│   │   ├── ingest_polygon_news.py                 Daily news (10/ticker, VARIANT columns)
│   │   ├── ingest_polygon_sma.py                  SMA-30 (limit=120)
│   │   ├── ingest_polygon_ticker_details.py       Ticker details (market cap, SIC, employees)
│   │   ├── ingest_polygon_benchmark_prices.py     Benchmark/sector ETF + VIX daily prices
│   │   ├── ingest_polygon_stock_snapshot.py       Stock snapshot (price, quote, trade)
│   │   │
│   │   │── # FMP Financial Statement Jobs (6)
│   │   ├── ingest_fmp_income_statement.py         Annual income statements
│   │   ├── ingest_fmp_balance_sheet.py            Annual balance sheets
│   │   ├── ingest_fmp_cash_flow.py                Annual cash flow statements
│   │   ├── ingest_fmp_income_statement_q.py       Quarterly income statements
│   │   ├── ingest_fmp_balance_sheet_q.py          Quarterly balance sheets
│   │   ├── ingest_fmp_cash_flow_q.py              Quarterly cash flow statements
│   │   │
│   │   │── # FMP Market Data Jobs (6)
│   │   ├── ingest_fmp_key_metrics.py              Key metrics (P/E, EV/EBITDA, P/B, etc.)
│   │   ├── ingest_fmp_analyst_consensus.py        Price target + upgrades/downgrades consensus
│   │   ├── ingest_fmp_earnings_calendar.py        Earnings calendar dates
│   │   ├── ingest_fmp_dividends.py                Dividend history
│   │   ├── ingest_fmp_splits.py                   Stock split history
│   │   ├── ingest_fmp_insider_trades.py           Insider trades (paginated global feed)
│   │   │
│   │   │── # FMP News/Text Jobs (4)
│   │   ├── ingest_fmp_articles.py                 FMP articles (per-ticker)
│   │   ├── ingest_fmp_stock_news.py               Stock news (paginated global feed)
│   │   ├── ingest_fmp_general_news.py             General news (unfiltered global feed)
│   │   ├── ingest_fmp_press_releases.py           Press releases (paginated global feed)
│   │   │
│   │   │── # FMP Insider Trades Search Job (1)
│   │   ├── ingest_fmp_insider_trades_search.py    Insider trades search (paginated global feed)
│   │   │
│   │   │── # FRED Job (1)
│   │   ├── ingest_fred_macro_rates.py             Macro rate series observations
│   │   │
│   │   │── # Polygon Backfill Jobs (5)
│   │   ├── ingest_polygon_prices_backfill.py      398-day price backfill
│   │   ├── ingest_polygon_rsi_backfill.py         730-day RSI backfill
│   │   ├── ingest_polygon_macd_backfill.py        730-day MACD backfill
│   │   ├── ingest_polygon_news_backfill.py        398-day news backfill (VARIANT columns)
│   │   ├── ingest_polygon_benchmark_prices_backfill.py  5yr benchmark prices backfill
│   │   │
│   │   │── # FMP Backfill Jobs (7)
│   │   ├── ingest_fmp_articles_backfill.py        5yr FMP articles backfill (deep pagination)
│   │   ├── ingest_fmp_general_news_backfill.py    5yr general news backfill
│   │   ├── ingest_fmp_press_releases_backfill.py  5yr press releases backfill
│   │   ├── ingest_fmp_stock_news_backfill.py      5yr stock news backfill
│   │   ├── ingest_fmp_dividends_backfill.py       5yr dividend history backfill
│   │   ├── ingest_fmp_key_metrics_backfill.py     5yr key metrics backfill
│   │   ├── ingest_fmp_insider_trades_backfill.py  5yr insider trades backfill
│   │   │
│   │   │── # Other Backfill Jobs (2)
│   │   ├── ingest_fmp_insider_trades_search_backfill.py  5yr insider trades search backfill
│   │   └── ingest_fred_macro_rates_backfill.py    5yr FRED macro rates backfill
│   │
│   ├── loaders/                   Snowflake write-only operations
│   │   └── snowflake_loader.py         4 write strategies (partition/range x standard/VARIANT)
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

BALAZSILLOVAI30823          <- RAW layer (Python loaders write here)

    # Polygon — Prices & Indicators
    sp500_stock_prices               Daily OHLCV prices (Polygon)
    sp500_stock_prices_backfill      Historical prices (Polygon)
    sp500_rsi / _backfill            RSI-14 daily (Polygon)
    sp500_macd / _backfill           MACD daily (Polygon)
    sp500_sma                        SMA-30 daily (Polygon)
    sp500_benchmark_prices           Benchmark/sector ETF + VIX prices (Polygon)
    sp500_ticker_details             Ticker details: market cap, SIC, employees (Polygon)
    sp500_stock_snapshot             Stock snapshot: price, quote, trade (Polygon)

    # Polygon — News
    sp500_news / _backfill           News articles (Polygon, VARIANT columns)

    # FMP — Annual Financial Statements
    sp500_income_statements          Annual income statements (FMP)
    sp500_balance_sheets             Annual balance sheets (FMP)
    sp500_cash_flow_statements       Annual cash flow statements (FMP)

    # FMP — Quarterly Financial Statements
    sp500_income_statements_q        Quarterly income statements (FMP)
    sp500_balance_sheets_q           Quarterly balance sheets (FMP)
    sp500_cash_flow_statements_q     Quarterly cash flow statements (FMP)

    # FMP — Market Data
    sp500_key_metrics                Key metrics: P/E, EV/EBITDA, P/B, etc. (FMP)
    sp500_price_target_consensus     Price target consensus (FMP)
    sp500_upgrades_downgrades        Upgrades/downgrades consensus (FMP)
    sp500_earnings_calendar          Earnings calendar dates (FMP)
    sp500_dividends                  Dividend history (FMP)
    sp500_splits                     Stock split history (FMP)
    sp500_insider_trades             Insider trades from paginated feed (FMP)
    sp500_insider_trades_search      Insider trades from search feed (FMP)

    # FMP — News & Text
    sp500_fmp_news                   FMP articles (FMP)
    sp500_fmp_stock_news             Stock news (FMP)
    sp500_fmp_general_news           General market news (FMP)
    sp500_fmp_press_releases         Press releases (FMP)

    # FRED — Macro
    sp500_macro_rates                Macro rate series: Fed Funds, 10Y, CPI, etc. (FRED)

    # Wikipedia — Universe
    sp500_tickers_lookup             S&P 500 universe (Wikipedia)

BALAZSILLOVAI30823_STG      <- dbt staging (views, source-cleaning)
BALAZSILLOVAI30823_INT      <- dbt intermediate (incremental computations)
BALAZSILLOVAI30823_DIM      <- dbt dimensions (current-state tables)
BALAZSILLOVAI30823_MARTS    <- dbt marts (scoring + ranking, exposed to MCP/Superset)
```

## Data Flow

```
Wikipedia ──> sp500_lookup_dag ──> sp500_tickers_lookup (RAW)
                                           |
                 ┌─────────────────────────┼─────────────────────────────────┐
                 v                         v                                 v
Polygon APIs ──> Polygon DAGs       FMP APIs ──> FMP DAGs           FRED API ──> FRED DAG
  prices (daily+backfill)             income/balance/cash flow         macro rates
  RSI (daily+backfill)                income_q/balance_q/cash_flow_q   (daily+backfill)
  MACD (daily+backfill)               key metrics
  SMA                                 analyst consensus
  news (daily+backfill)               earnings calendar
  ticker details                      dividends / splits
  benchmark prices (daily+backfill)   insider trades / search
  stock snapshot                      articles / stock news
                                      general news / press releases
                 |                         |                                 |
                 v                         v                                 v
                        RAW tables (Snowflake base schema)
                                           |
                             ExternalTaskSensors gate
                                           |
                                           v
                     stock_screening_dbt_daily_dag (Cosmos)
                                           |
                             ┌─────────────┼──────────────┐
                             v             v              v
                         staging -> intermediate -> marts
                         (views)   (incremental)   (incremental)
                                           |
                             ┌─────────────┼──────────────┐
                             v                            v
                       Superset                     MCP Server
                     (dashboards)                (Claude Desktop)
```

## Environment Topology

| Target | Schema Suffix | Purpose |
|--------|--------------|---------|
| `dev` | `BALAZSILLOVAI30823` | Development iteration |
| `prod` | `BALAZSILLOVAI30823_prod` | Production (not yet active) |

Both targets share `DATAEXPERT_STUDENT` database, `COMPUTE_WH` warehouse, `ALL_USERS_ROLE` role.
