# Stock Screening & Scoring Engine — Project Summary

A production-grade analytics platform that ingests market data for every S&P 500 company, transforms it through a multi-layer data warehouse on Snowflake, computes quantitative 0-100 scores across technical and fundamental dimensions, and exposes daily-ranked investment insights through BI dashboards and an AI-powered semantic layer.

---

## Table of Contents

1. [What This Project Is (Infrastructure)](#1-what-this-project-is-infrastructure)
2. [What I Am Trying to Build](#2-what-i-am-trying-to-build)
3. [All Data Gathered and Stored](#3-all-data-gathered-and-stored)

---

## 1. What This Project Is (Infrastructure)

### Technology Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Data Ingestion** | Python 3.12, pandas, requests | Fetch data from external APIs into DataFrames |
| **Data Warehouse** | Snowflake (DATAEXPERT_STUDENT database) | Central source of truth for all raw and transformed data |
| **Transformation** | dbt-snowflake 1.10.4 | SQL-based transformations: staging views, incremental tables, scoring marts |
| **Orchestration** | Apache Airflow 3.x (Astronomer Runtime 3.1-9) | Daily scheduling, dependency gating, backfill management |
| **BI Visualization** | Apache Superset | Interactive dashboards connected to Snowflake marts |
| **AI Interface** | MCP Server + boring-semantic-layer + ibis | Natural language analytics via Claude Desktop |
| **Containerization** | Docker, docker-compose, Astronomer CLI | Local development and deployment |
| **Agent Pipeline** | Anthropic Claude API (anthropic SDK, pydantic) | LLM-driven investment thesis generation (in development) |

### Snowflake Schema Topology

The warehouse is organized into five strictly layered schemas within the `DATAEXPERT_STUDENT` database:

```
BALAZSILLOVAI30823          ← RAW layer (Python loaders write here)
BALAZSILLOVAI30823_STG      ← Staging layer (dbt views, source-cleaning)
BALAZSILLOVAI30823_INT      ← Intermediate layer (dbt incremental computations)
BALAZSILLOVAI30823_DIM      ← Dimension layer (dbt full-refresh entity tables)
BALAZSILLOVAI30823_MARTS    ← Marts layer (dbt scoring, ranking — exposed to consumers)
```

Only the `_MARTS` schema is exposed to external consumers (Superset and MCP). RAW, STG, INT, and DIM schemas are internal to the dbt pipeline.

### Python ETL Architecture

The Python layer follows strict separation of concerns:

- **`src/api_clients/`** — Fetch-only API clients. Return pandas DataFrames. Never touch Snowflake.
  - `PolygonClient`: Polygon.io (prices, RSI, MACD, SMA, news). Rate limited at 0.8s/request (~75 req/min), 3x retries, 8-worker concurrent fetching.
  - `FMPClient`: Financial Modeling Prep (income statements, balance sheets, cash flow, news). Rate limited at 0.1s/request (~600 req/min), 3x retries, 8-worker concurrent fetching.
  - `wikipedia_client.fetch_sp500_constituents()`: Wikipedia S&P 500 table scraper with retry-on-403 backoff.

- **`src/loaders/snowflake_loader.py`** — Write-only Snowflake operations. Never calls APIs. Provides four write strategies:
  - `overwrite_partition()` — Delete-then-insert for a single date partition (daily loads).
  - `overwrite_date_range()` — Delete-then-insert for a date range (backfills).
  - `overwrite_partition_with_variants()` — Same as partition, but applies `parse_json()` for VARIANT columns (news articles with JSON arrays).
  - `overwrite_date_range_with_variants()` — Same as date range, with VARIANT handling.

- **`src/jobs/`** — Thin glue layer. Each job calls one API client method, then one loader method. No business logic. 14 job files covering daily ingestion and backfill for all data sources.

- **`src/mcp/`** — Read-only MCP server exposing 5 whitelisted mart tables to Claude Desktop via boring-semantic-layer and ibis-framework.

- **`src/agents/`** — Agentic pipeline infrastructure (in development). Includes:
  - `config/pipeline_config.yaml` — Tunable parameters for scoring weights, shortlisting thresholds, LLM model selection.
  - `config/config_loader.py` — YAML config reader with environment variable overrides and validation.
  - `data/snowflake_reader.py` — Read-only Snowflake access layer for agents. Reads from marts, staging, and dimension schemas.
  - `core/output_manager.py` — Daily output directory management for PDF reports, manifests, and logs.

### Airflow Orchestration

**14 DAGs total**: 9 daily ETL + 4 manual backfill + 1 dbt Cosmos DAG.

**Daily execution flow:**

```
sp500_lookup (root)  ──── Fetches S&P 500 universe from Wikipedia
       │
       ├── polygon_daily_prices    (ExternalTaskSensor on sp500_lookup)
       ├── polygon_daily_rsi       (ExternalTaskSensor on sp500_lookup)
       ├── polygon_daily_macd      (ExternalTaskSensor on sp500_lookup)
       ├── polygon_daily_news      (ExternalTaskSensor on sp500_lookup)
       ├── fmp_income_statement    (ExternalTaskSensor on sp500_lookup, not gated by dbt)
       ├── fmp_balance_sheet       (ExternalTaskSensor on sp500_lookup, not gated by dbt)
       ├── fmp_cash_flow           (ExternalTaskSensor on sp500_lookup, not gated by dbt)
       └── fmp_news_daily          (ExternalTaskSensor on sp500_lookup, not gated by dbt)
              │
              ▼
stock_screening_dbt_daily  ──── Cosmos dbt DAG
    [Waits for: sp500_lookup, polygon_prices, polygon_rsi, polygon_macd, polygon_news]
    [Runs: full dbt build (staging → intermediate → dimensions → marts + tests)]
```

FMP DAGs run daily but are intentionally not gated by the dbt DAG, since FMP data is annual and changes infrequently.

**Backfill DAGs (manual trigger, schedule=None):**
- `polygon_prices_backfill` — 398 days of historical prices
- `polygon_rsi_backfill` — 730 days of historical RSI
- `polygon_macd_backfill` — 730 days of historical MACD
- `polygon_news_backfill` — 398 days of historical news

### dbt Transformation Layer

**Project**: `stock_screening_engine`, profile targeting Snowflake via environment-variable credentials.

**dbt packages installed**: dbt_utils 1.1.1, dbt_expectations 0.10.3, codegen 0.12.1.

**Layer rules:**
- **Staging** (views): Clean and rename raw columns. No business logic. References only `source()`.
- **Intermediate** (incremental tables or full-refresh tables): Derived computations, window functions, multi-source joins. References staging or other intermediate models.
- **Dimensions** (full-refresh tables): Conforming entity attributes. References staging only.
- **Marts** (incremental tables or full-refresh tables): Analytics-ready scoring, ranking, enrichment. References intermediate, dimensions, or other marts.

**Incremental strategy**: All incremental models use `delete+insert` (never merge). Double-filter pattern: wide source lookback (for window functions) + narrow output filter (to limit write volume). Watermarks always reference `{{ this }}` (self-referential, idempotent).

### Consumer Layer

**Apache Superset**: Containerized via docker-compose on port 8088. Connects to Snowflake `_MARTS` schema via snowflake-sqlalchemy. Provides interactive dashboards for stock screening and scoring visualization.

**MCP Server**: Exposes 5 mart tables (technical_scores, fundamental_scores, composite_scores, industry_scores, price_performance) to Claude Desktop via the Model Context Protocol. Uses boring-semantic-layer for a 616-line semantic definition that gives Claude deep analytical context about dimensions, measures, and how to interpret each metric.

### Data Quality & Testing

**Test tiers:**
1. **Schema tests (YAML)**: `not_null` on ticker across all models; `unique` on dimension natural keys; `not_null` on score columns.
2. **Custom singular tests (SQL)**: `assert_technical_score_in_range.sql` and `assert_fundamentals_score_in_range.sql` validate all scores are within [0, 100].
3. **Package-based tests**: dbt_utils and dbt_expectations are installed but not yet actively used. Planned additions include grain uniqueness, referential integrity, row count bounds, and source freshness.

---

## 2. What I Am Trying to Build

### Current Capabilities (Implemented)

The platform currently delivers a complete, end-to-end daily stock scoring pipeline:

1. **S&P 500 Universe Definition**: Wikipedia-sourced, daily-refreshed canonical list of all ~500 S&P 500 constituents with sector, industry, and company metadata.

2. **Daily Technical Scoring (0-100)**: Every S&P 500 stock receives a daily technical score based on four signal families:
   - **Trend Confirmation (40 pts)**: SMA-20/50/200 alignment — how well price sits above short, medium, and long-term moving averages.
   - **Momentum Quality (30 pts)**: RSI-14 regime classification — bullish (50-70), overbought (>70), oversold (<30).
   - **Price Action (20 pts)**: 20-day percentage price change — strength of recent moves.
   - **MACD Signal (10 pts)**: MACD histogram direction and signal line crossovers.

3. **Annual Fundamental Scoring (0-100)**: Every stock receives a fundamental quality score based on audited financial statements:
   - **Profitability Quality (25 pts)**: Gross/operating/net margin tiers + return on equity.
   - **Growth Momentum (30 pts)**: YoY revenue growth + EPS growth + free cash flow growth.
   - **Financial Health (25 pts)**: Current ratio (liquidity) + debt-to-equity (leverage) + FCF margin.
   - **Cash Quality (20 pts)**: FCF-to-net-income ratio (earnings quality) + FCF margin.

4. **Composite Scoring (0-100)**: Daily blended scores combining technical and fundamental signals with three weighting variants:
   - **Equal (50/50)**: Balanced screening.
   - **Technical Bias (60/40)**: For trending/momentum markets.
   - **Fundamental Bias (40/60)**: For volatile/uncertain markets.

5. **Industry-Enriched Rankings**: Composite scores joined with company metadata (sector, industry, company name) for sector rotation analysis, peer comparison, and top-down screening.

6. **Price Performance Analytics**: Daily returns (daily, cumulative, rolling 30d/90d/1y), 30-day rolling volatility, running maximum price, drawdown from peak — all enriched with company metadata.

7. **Multi-Year Backfill Capability**: Manual-trigger DAGs to backfill 1-2 years of historical data for prices, RSI, MACD, and news.

8. **AI-Powered Natural Language Analytics**: Claude Desktop can query all scoring marts through the MCP semantic layer, answering questions like "Which tech stocks have the strongest composite scores?", "Show me momentum leaders", or "What are the most volatile stocks near all-time highs?"

### What's Being Built Next (In Development / Planned)

**Phase 0.5 — Agentic Stock Opportunity Pipeline** (current branch: `phase-0.5`):

An LLM-driven agent pipeline that goes beyond quantitative scoring to produce daily investment intelligence:

- **Configurable scoring weights**: Pipeline-level weights (technical 25%, fundamental 20%, price trajectory 20%, catalyst strength 20%, sector favorability 15%) that can be tuned via YAML or environment variables.
- **News-driven catalyst analysis**: AI agents scan 7 days of news per stock for the top-50 scored candidates, assessing catalyst strength and investment implications.
- **Shortlist generation**: Filtered output applying minimum score threshold (65), maximum drawdown (-20%), sector concentration limits (3 per sector), and total cap (15 stocks).
- **Investment thesis generation**: Claude Opus generates detailed investment theses for shortlisted stocks.
- **Risk assessment**: Claude Sonnet evaluates risk profiles for each opportunity.
- **PDF report output**: Daily sector-level and aggregate opportunity reports written to `output/{YYYY-MM-DD}/`.
- **Read-only Snowflake access**: Agent pipeline reads from marts and staging schemas but never writes.

**Future Roadmap** (from README):
- Strategy backtesting
- Portfolio simulation
- Factor modeling
- Risk-adjusted ranking
- ML-enhanced signals

### Design Philosophy

The project follows seven core principles:

1. **Wikipedia defines WHAT exists** — The S&P 500 universe is the canonical stock list.
2. **APIs define WHAT happens** — Polygon and FMP provide the raw market and financial data.
3. **Snowflake stores TRUTH** — All data flows through a five-layer schema (RAW → STG → INT → DIM → MARTS).
4. **dbt defines MEANING** — All business logic, scoring formulas, and derived metrics live in dbt SQL.
5. **Airflow controls TIME** — Daily scheduling, dependency gating, and backfill orchestration.
6. **Superset shows INSIGHT** — Interactive dashboards for human analysts.
7. **MCP enables INTELLIGENCE** — AI-powered natural language analytics for Claude Desktop.

---

## 3. All Data Gathered and Stored

### External Data Sources

| Source | API | Data Type | Frequency | Rate Limit |
|--------|-----|-----------|-----------|-----------|
| **Wikipedia** | HTML table scrape | S&P 500 constituent list | Daily | ~3 req with backoff on 403 |
| **Polygon.io** | REST API (v2/v1) | Prices, RSI, MACD, SMA, News | Daily + backfill | 0.8s/req (~75/min, Basic tier) |
| **Financial Modeling Prep** | REST API (stable) | Income statements, balance sheets, cash flow, news | Daily (annual data) | 0.1s/req (~600/min) |

### Raw Data Tables (Snowflake RAW Schema)

#### 1. S&P 500 Universe — `sp500_tickers_lookup`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Stock ticker symbol (e.g., AAPL, MSFT) |
| security_name | STRING | Full company name (e.g., Apple Inc.) |
| gics_sector | STRING | GICS sector classification (e.g., Information Technology) |
| gics_sub_industry | STRING | GICS sub-industry (e.g., Technology Hardware, Storage & Peripherals) |
| headquarters_location | STRING | Company headquarters (e.g., Cupertino, California) |
| date_added | STRING | Date the company was added to the S&P 500 |
| cik | STRING | SEC Central Index Key identifier |
| founded_year | STRING | Year the company was founded |
| date | STRING | As-of date of the lookup (run date) |
| extracted_at | STRING | Timestamp when the data was fetched |

**Source**: Wikipedia "List of S&P 500 companies" table. **Grain**: (ticker, date). **~503 rows per daily run** (current S&P 500 membership).

---

#### 2. Stock Prices — `sp500_stock_prices` + `sp500_stock_prices_backfill`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Stock ticker symbol |
| open | FLOAT | Opening price |
| high | FLOAT | Intraday high price |
| low | FLOAT | Intraday low price |
| close | FLOAT | Closing price (adjusted) |
| volume | FLOAT | Trading volume (shares) |
| vwap | FLOAT | Volume-weighted average price |
| transactions | INT | Number of transactions |
| date | STRING | Trading date (YYYY-MM-DD) |
| extracted_at | STRING | Extraction timestamp |

**Source**: Polygon.io Aggregates API (`/v2/aggs/ticker/{ticker}/range/1/day/`). **Grain**: (ticker, date). **~500 rows per trading day**. Backfill table covers 398 days of history with `CLUSTER BY (date, ticker)`.

---

#### 3. RSI (Relative Strength Index) — `sp500_rsi` + `sp500_rsi_backfill`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Stock ticker symbol |
| timestamp | TIMESTAMP | Indicator timestamp |
| rsi_value | FLOAT | RSI-14 value (0-100 scale) |
| window_size | INT | Window size (always 14) |
| timespan | STRING | Timespan (always "day") |
| series_type | STRING | Price series used (always "close") |
| date | STRING | Run date |
| extracted_at | STRING | Extraction timestamp |

**Source**: Polygon.io Technical Indicators API (`/v1/indicators/rsi/{ticker}`). **Grain**: (ticker, date). Daily runs fetch `limit=1` (latest value). Backfill covers 730 days with `limit=120` per ticker.

---

#### 4. MACD (Moving Average Convergence Divergence) — `sp500_macd` + `sp500_macd_backfill`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Stock ticker symbol |
| timestamp | TIMESTAMP | Indicator timestamp |
| macd_value | FLOAT | MACD line value |
| signal_value | FLOAT | Signal line value |
| histogram_value | FLOAT | MACD histogram (MACD - signal) |
| short_window | INT | Short EMA window (always 12) |
| long_window | INT | Long EMA window (always 26) |
| signal_window | INT | Signal EMA window (always 9) |
| timespan | STRING | Timespan (always "day") |
| series_type | STRING | Price series (always "close") |
| date | STRING | Run date |
| extracted_at | STRING | Extraction timestamp |

**Source**: Polygon.io Technical Indicators API (`/v1/indicators/macd/{ticker}`). **Grain**: (ticker, date). Parameters: MACD(12, 26, 9). Daily runs fetch `limit=1`. Backfill covers 730 days.

---

#### 5. News Articles (Polygon) — `sp500_news` + `sp500_news_backfill`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Primary ticker for the article |
| article_id | STRING | Unique article identifier |
| publisher_name | STRING | Publisher name |
| publisher_homepage_url | STRING | Publisher homepage URL |
| publisher_logo_url | STRING | Publisher logo URL |
| title | STRING | Article title |
| author | STRING | Article author |
| published_utc | TIMESTAMP | Publication timestamp (UTC) |
| article_url | STRING | Full article URL |
| tickers | VARIANT | JSON array of all ticker symbols mentioned |
| image_url | STRING | Article image URL |
| description | STRING | Article description/summary |
| keywords | VARIANT | JSON array of article keywords |
| date | STRING | Run date |
| extracted_at | STRING | Extraction timestamp |

**Source**: Polygon.io Reference News API (`/v2/reference/news`). **Grain**: (ticker, article_id, date). Daily runs fetch up to 10 articles per ticker. Backfill covers 398 days with up to 100 articles per ticker. VARIANT columns (tickers, keywords) stored as native Snowflake JSON via `parse_json()` at load time.

---

#### 6. Income Statements — `sp500_income_statements`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Stock ticker symbol |
| date | STRING | Fiscal period end date |
| reported_currency | STRING | Reporting currency (typically USD) |
| cik | STRING | SEC CIK identifier |
| filing_date | STRING | SEC filing date |
| accepted_date | TIMESTAMP | SEC acceptance timestamp |
| fiscal_year | INT | Fiscal year |
| period | STRING | Reporting period (FY, Q1, Q2, Q3, Q4) |
| revenue | FLOAT | Total revenue |
| cost_of_revenue | FLOAT | Cost of goods sold |
| gross_profit | FLOAT | Gross profit (revenue - COGS) |
| research_and_development_expenses | FLOAT | R&D expenses |
| selling_general_and_administrative_expenses | FLOAT | SG&A expenses |
| operating_expenses | FLOAT | Total operating expenses |
| operating_income | FLOAT | Operating income (EBIT proxy) |
| ebitda | FLOAT | Earnings before interest, taxes, depreciation, amortization |
| ebit | FLOAT | Earnings before interest and taxes |
| interest_expense | FLOAT | Interest expense |
| income_before_tax | FLOAT | Pre-tax income |
| income_tax_expense | FLOAT | Income tax expense |
| net_income | FLOAT | Net income |
| eps | FLOAT | Basic earnings per share |
| eps_diluted | FLOAT | Diluted earnings per share |
| weighted_average_shares_out | FLOAT | Basic weighted average shares |
| weighted_average_shares_out_diluted | FLOAT | Diluted weighted average shares |
| *(+ 10 more fields)* | | Additional income statement line items |
| extracted_at | STRING | Extraction timestamp |

**Source**: FMP Income Statement API (`/stable/income-statement`). **Grain**: (ticker, date, period). **~2,500 rows** (~500 tickers x ~5 fiscal years). Annual data (`period=annual`), fetched daily but changes infrequently.

---

#### 7. Balance Sheets — `sp500_balance_sheets`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Stock ticker symbol |
| date | STRING | Fiscal period end date |
| fiscal_year | INT | Fiscal year |
| period | STRING | Reporting period |
| cash_and_cash_equivalents | FLOAT | Cash and equivalents |
| short_term_investments | FLOAT | Short-term investments |
| total_current_assets | FLOAT | Total current assets |
| property_plant_equipment_net | FLOAT | Net PP&E |
| goodwill | FLOAT | Goodwill |
| intangible_assets | FLOAT | Intangible assets |
| total_assets | FLOAT | Total assets |
| total_current_liabilities | FLOAT | Total current liabilities |
| long_term_debt | FLOAT | Long-term debt |
| total_liabilities | FLOAT | Total liabilities |
| total_stockholders_equity | FLOAT | Total stockholders' equity |
| total_debt | FLOAT | Total debt (short + long-term) |
| net_debt | FLOAT | Net debt (total debt - cash) |
| *(+ 35 more fields)* | | Additional balance sheet line items |
| extracted_at | STRING | Extraction timestamp |

**Source**: FMP Balance Sheet API (`/stable/balance-sheet-statement`). **Grain**: (ticker, date, period). **~2,500 rows**. 65 total columns covering every major balance sheet line item.

---

#### 8. Cash Flow Statements — `sp500_cash_flow_statements`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Stock ticker symbol |
| date | STRING | Fiscal period end date |
| fiscal_year | INT | Fiscal year |
| period | STRING | Reporting period |
| net_income | FLOAT | Net income (starting point for operating CF) |
| depreciation_and_amortization | FLOAT | D&A add-back |
| stock_based_compensation | FLOAT | SBC add-back |
| change_in_working_capital | FLOAT | Working capital changes |
| net_cash_provided_by_operating_activities | FLOAT | Operating cash flow |
| investments_in_property_plant_and_equipment | FLOAT | Capital expenditures |
| net_cash_provided_by_investing_activities | FLOAT | Investing cash flow |
| net_cash_provided_by_financing_activities | FLOAT | Financing cash flow |
| net_change_in_cash | FLOAT | Net cash change |
| operating_cash_flow | FLOAT | Operating cash flow (alternate field) |
| capital_expenditure | FLOAT | CapEx |
| free_cash_flow | FLOAT | Free cash flow (OCF - CapEx) |
| *(+ 25 more fields)* | | Additional cash flow line items |
| extracted_at | STRING | Extraction timestamp |

**Source**: FMP Cash Flow Statement API (`/stable/cash-flow-statement`). **Grain**: (ticker, date, period). **~2,500 rows**. 52 total columns covering all three sections of the cash flow statement.

---

#### 9. FMP News Articles — `sp500_fmp_news`

| Column | Type | Description |
|--------|------|-------------|
| ticker | STRING | Matched S&P 500 ticker |
| title | STRING | Article title |
| date | STRING | Publication date |
| content | STRING | Full article content |
| article_tickers | STRING | Raw ticker string (e.g., "NYSE:MRK,NASDAQ:AAPL") |
| image_url | STRING | Article image |
| article_url | STRING | Article URL |
| author | STRING | Author |
| site | STRING | Publishing site |
| extracted_at | STRING | Extraction timestamp |

**Source**: FMP Articles API (`/stable/fmp-articles`). **Grain**: (ticker, date, article_url). Experimental — paginated global feed filtered to S&P 500 tickers.

---

### Transformed Data (dbt Models)

#### Staging Layer (Views — No Business Logic)

| Model | Grain | Source Table | Description |
|-------|-------|-------------|-------------|
| `stg_sp500_stock_prices` | (ticker, date) | sp500_stock_prices | Passthrough: ticker, OHLCV, vwap, transactions, date |
| `stg_sp500_rsi` | (ticker, date) | sp500_rsi | Passthrough: ticker, timestamp, rsi_value, window params |
| `stg_sp500_macd` | (ticker, date) | sp500_macd | Passthrough: ticker, timestamp, MACD/signal/histogram, window params |
| `stg_sp500_news` | (ticker, article_id, date) | sp500_news | Passthrough: ticker, article metadata, VARIANT tickers/keywords |
| `stg_fmp_income_statement` | (ticker, date, period) | sp500_income_statements | Passthrough: 44 income statement columns |
| `stg_fmp_balance_sheet` | (ticker, date, period) | sp500_balance_sheets | Passthrough: 65 balance sheet columns |
| `stg_fmp_cash_flow` | (ticker, date, period) | sp500_cash_flow_statements | Passthrough: 52 cash flow columns |
| `stg_fmp_news` | (ticker, date, article_url) | sp500_fmp_news | Passthrough: FMP article metadata |
| `stg_sp500_tickers_snapshot` | (ticker, as_of_date) | sp500_tickers_lookup | Renames columns, extracts date_added_year |
| `stg_sp500_tickers_current` | (ticker) | stg_sp500_tickers_snapshot | MAX(as_of_date) filter for current S&P 500 membership |

#### Intermediate Layer (Computed Metrics)

| Model | Grain | Materialization | Key Computations |
|-------|-------|----------------|-----------------|
| `int_sp500_daily_price_changes` | (ticker, date) | Incremental (4-day source lookback, 3-day output) | `LAG(close)` for daily price change and previous close |
| `int_sp500_technical_indicators` | (ticker, date) | Incremental (300-day source lookback, 3-day output) | SMA-20/50/200 via window averages; LEFT JOIN with RSI and MACD |
| `int_sp500_price_returns` | (ticker, date) | Incremental (full source scan, 3-day output) | Daily return, cumulative return (FIRST_VALUE), rolling 30d/90d/1y returns (LAG), 30-day volatility (STDDEV), running max price, drawdown % |
| `int_sp500_fundamentals` | (ticker, date) | Full-refresh table | 3-statement INNER JOIN (income + balance + cash flow) on (ticker, date, fiscal_year). Computes: gross/operating/net margin, ROE, ROA, current ratio, quick ratio, debt-to-equity, debt-to-assets, FCF margin, FCF-to-NI, revenue/EPS/FCF YoY growth |

#### Dimension Layer

| Model | Grain | Materialization | Description |
|-------|-------|----------------|-------------|
| `dim_sp500_companies_current` | (ticker) | Full-refresh table | Conforming dimension: ticker, company_name, sector, industry, location, CIK, founded_year. Unique + not_null on ticker. |

#### Marts Layer (Analytics-Ready Scoring)

| Model | Grain | Materialization | Score Range | Description |
|-------|-------|----------------|------------|-------------|
| `mart_sp500_technical_scores` | (ticker, date) | Incremental (40-day source, 3-day output) | 0-100 | Trend (40pts) + Momentum (30pts) + Price Action (20pts) + MACD (10pts) |
| `mart_sp500_fundamental_scores` | (ticker, date) | Full-refresh | 0-100 | Profitability (25pts) + Growth (30pts) + Health (25pts) + Cash (20pts) |
| `mart_sp500_composite_scores` | (ticker, technical_date) | Incremental (3-day) | 0-100 per variant | 3 weighting variants: equal (50/50), technical-bias (60/40), fundamental-bias (40/60) |
| `mart_sp500_industry_scores` | (ticker, technical_date) | Incremental (3-day) | Inherited | Composite scores + company_name, sector, industry from dimension |
| `mart_sp500_price_performance` | (ticker, date) | Incremental (7-day) | N/A (returns) | Returns + volatility + drawdown + company metadata |

### Data Volume Estimates

| Data Category | Approximate Daily Volume | Historical Depth |
|--------------|------------------------|-----------------|
| S&P 500 universe | ~503 rows | Daily snapshots |
| Stock prices | ~500 rows/trading day | 398-day backfill available |
| RSI values | ~500 rows/trading day | 730-day backfill available |
| MACD values | ~500 rows/trading day | 730-day backfill available |
| News articles (Polygon) | ~5,000 rows/day (10 per ticker) | 398-day backfill available |
| Income statements | ~2,500 total (annual, ~5 years x 500 tickers) | Full history per ticker |
| Balance sheets | ~2,500 total (annual) | Full history per ticker |
| Cash flow statements | ~2,500 total (annual) | Full history per ticker |
| Technical scores (mart) | ~500 rows/trading day | Incremental accumulation |
| Fundamental scores (mart) | ~2,500 total (annual) | Full rebuild each run |
| Composite scores (mart) | ~500 rows/trading day | Incremental accumulation |

### Semantic Layer Exposure (MCP → Claude Desktop)

The MCP server exposes 5 mart tables with rich semantic definitions:

| Semantic Model | Dimensions | Measures | Primary Use Cases |
|---------------|-----------|---------|------------------|
| `technical_scores` | ticker, date | avg/max/min/std technical_score, avg trend/momentum/price_action/macd scores, ticker_count | Entry/exit timing, momentum screening, trend detection |
| `fundamental_scores` | ticker, date, fiscal_year | avg/max/min/std fundamentals_score, avg profitability/growth/health/cash scores, margin metrics, ROE, current ratio, D/E | Quality investing, value screening, financial health assessment |
| `composite_scores` | ticker, technical_date, fiscal_year | avg/max/min/std for 3 composite variants, avg technical/fundamental raw scores | Holistic stock ranking, portfolio construction, regime-adaptive screening |
| `industry_scores` | ticker, company_name, sector, industry, technical_date, fiscal_year | Same as composite + sector_count | Sector rotation analysis, peer comparison, best-in-sector screening |
| `price_performance` | ticker, company_name, sector, industry, date | avg daily/cumulative/rolling returns, volatility, drawdown, risk-adjusted return, positive_return_rate | Performance attribution, risk screening, momentum identification |

### Data Lineage Summary

```
Wikipedia ─────────────────────────── → stg_tickers_snapshot → stg_tickers_current → dim_companies_current
                                                                                             │
Polygon Prices ─── → stg_stock_prices ──┬── → int_daily_price_changes                       │
                                        ├── → int_technical_indicators → mart_technical_scores │
                                        └── → int_price_returns ──────→ mart_price_performance ◄┘
                                                                                             │
Polygon RSI ────── → stg_rsi ───────────┘                                                    │
Polygon MACD ───── → stg_macd ──────────┘                                                    │
                                                                                             │
FMP Income ─────── → stg_income_statement ──┐                                                │
FMP Balance Sheet → stg_balance_sheet ──────┼── → int_fundamentals → mart_fundamental_scores  │
FMP Cash Flow ──── → stg_cash_flow ─────────┘                               │                │
                                                                            ▼                │
                                                          mart_composite_scores              │
                                                                   │                        │
                                                                   ▼                        │
                                                          mart_industry_scores ◄────────────┘
                                                                   │
                                                          ┌────────┴────────┐
                                                          ▼                 ▼
                                                       Superset         MCP Server
                                                     (dashboards)    (Claude Desktop)
```
