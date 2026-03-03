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
  - `PolygonClient`: Polygon.io (prices, RSI, MACD, SMA, news, ticker details, benchmark prices, stock snapshot). Rate limited at 0.8s/request (~75 req/min), 3x retries, 8-worker concurrent fetching.
  - `FMPClient`: Financial Modeling Prep with 15 fetch methods as of Phase 0.5 — financial statements (income, balance sheet, cash flow), key metrics, earnings calendar, analyst consensus (price targets + upgrades/downgrades), dividends, splits, insider trades (2 feed variants), and news (FMP articles, general news, press releases, stock news). Rate limited at 0.1s/request (~600 req/min), 3x retries, 8-worker concurrent fetching.
  - `FREDClient`: FRED API client for macro rate series (Fed Funds Rate, 10Y Treasury, 2Y Treasury, HY OAS); 0.5s rate limiting per request.
  - `wikipedia_client.fetch_sp500_constituents()`: Wikipedia S&P 500 table scraper with retry-on-403 backoff.

- **`src/loaders/snowflake_loader.py`** — Write-only Snowflake operations. Never calls APIs. Provides four write strategies:
  - `overwrite_partition()` — Delete-then-insert for a single date partition (daily loads).
  - `overwrite_date_range()` — Delete-then-insert for a date range (backfills).
  - `overwrite_partition_with_variants()` — Same as partition, but applies `parse_json()` for VARIANT columns (news articles with JSON arrays).
  - `overwrite_date_range_with_variants()` — Same as date range, with VARIANT handling.

- **`src/jobs/`** — Thin glue layer. Each job calls one API client method, then one loader method. No business logic. 41 job files covering daily ingestion and backfill for all data sources.

- **`src/mcp/`** — Read-only MCP server exposing 5 whitelisted mart tables to Claude Desktop via boring-semantic-layer and ibis-framework.

- **`src/agents/`** — Agentic pipeline infrastructure (in development). Includes:
  - `config/pipeline_config.yaml` — Tunable parameters for scoring weights, shortlisting thresholds, LLM model selection.
  - `config/config_loader.py` — YAML config reader with environment variable overrides and validation.
  - `data/snowflake_reader.py` — Read-only Snowflake access layer for agents. Reads from marts, staging, and dimension schemas.
  - `core/output_manager.py` — Daily output directory management for PDF reports, manifests, and logs.

### Airflow Orchestration

**44 DAGs total**: 27 daily ETL + 14 manual backfill + 1 dbt Cosmos DAG + 2 other (example, legacy).

**Daily execution flow:**

```
sp500_lookup (root)  ──── Fetches S&P 500 universe from Wikipedia
       │
       ├── Polygon (8 daily DAGs, all gated on sp500_lookup):
       │     polygon_daily_prices, polygon_daily_rsi, polygon_daily_macd,
       │     polygon_daily_news, polygon_sma, polygon_benchmark_prices,
       │     polygon_ticker_details, polygon_stock_snapshot
       │
       ├── FMP Phase 0 (4 daily DAGs, gated on sp500_lookup):
       │     fmp_income_statement, fmp_balance_sheet, fmp_cash_flow, fmp_articles_daily
       │
       ├── FMP Phase 0.5 (13 daily DAGs, gated on sp500_lookup):
       │     fmp_income_statement_q, fmp_balance_sheet_q, fmp_cash_flow_q,
       │     fmp_key_metrics, fmp_earnings_calendar, fmp_analyst_consensus,
       │     fmp_dividends, fmp_splits, fmp_insider_trades, fmp_insider_trades_search,
       │     fmp_global_news, fmp_press_releases, fmp_stock_news
       │
       └── FRED (1 daily DAG, independent — no upstream sensor):
             fred_macro_rates
              │
              ▼
stock_screening_dbt_daily  ──── Cosmos dbt DAG
    [Waits for: sp500_lookup, polygon_prices, polygon_rsi, polygon_macd, polygon_news]
    [Runs: full dbt build (staging → intermediate → dimensions → marts + tests)]
```

FMP DAGs run daily but are intentionally not gated by the dbt DAG, since FMP data is annual/quarterly and changes infrequently. FRED runs independently with no upstream sensor.

**Backfill DAGs (manual trigger, schedule=None):**
- `polygon_prices_backfill` — 398 days of historical prices
- `polygon_rsi_backfill` — 730 days of historical RSI
- `polygon_macd_backfill` — 730 days of historical MACD
- `polygon_news_backfill` — 398 days of historical news
- `polygon_benchmark_prices_backfill` — 5 years of benchmark/ETF prices
- `fmp_dividends_backfill` — 5 years of dividend history
- `fmp_key_metrics_backfill` — 5 years of key metrics (quarterly)
- `fmp_insider_trades_backfill` — 5 years of insider trades
- `fmp_insider_trades_search_backfill` — 5 years of insider trades search
- `fmp_articles_backfill` — 5 years of FMP articles
- `fmp_general_news_backfill` — 5 years of FMP general news
- `fmp_press_releases_backfill` — 5 years of FMP press releases
- `fmp_stock_news_backfill` — 5 years of FMP stock news
- `fred_macro_rates_backfill` — 5 years of FRED macro rates

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
| **Polygon.io** | REST API (v2/v1) | Prices, RSI, MACD, SMA, News, Ticker details, Benchmark prices, Stock snapshot | Daily + backfill | 0.8s/req (~75/min, Basic tier) |
| **Financial Modeling Prep** | REST API (stable) | Income statements, balance sheets, cash flow, key metrics, earnings calendar, dividends, splits, analyst consensus, insider trades, FMP articles, general news, press releases, stock news | Daily + backfill | 0.1s/req (~600/min) |
| **FRED** | REST API (fred.stlouisfed.org) | Macro rates (Fed Funds, 10Y Treasury, 2Y Treasury, HY OAS) | Daily + backfill | 0.5s/req (120/min) |

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

#### 10. Earnings Calendar — `sp500_earnings_calendar`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| date | DATE | Earnings date |
| eps_actual | FLOAT | Actual EPS reported |
| eps_estimated | FLOAT | Consensus EPS estimate |
| revenue_actual | NUMBER | Actual revenue reported |
| revenue_estimated | NUMBER | Consensus revenue estimate |
| last_updated | DATE | Last update date from FMP |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Earnings Calendar API (`/stable/earnings-calendar`). **Grain**: (ticker, date). Forward-looking snapshot — truncated and reloaded each run (up to 30 days forward, max 90 days).

---

#### 11. Ticker Details — `sp500_ticker_details`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| name | VARCHAR | Company name |
| market | VARCHAR | Market (e.g., stocks) |
| primary_exchange | VARCHAR | Primary exchange (e.g., XNAS) |
| active | BOOLEAN | Whether the ticker is actively traded |
| cik | VARCHAR | SEC CIK identifier |
| market_cap | NUMBER | Market capitalization |
| sic_code | VARCHAR | SIC industry code |
| sic_description | VARCHAR | SIC industry description |
| total_employees | NUMBER | Employee count |
| description | VARCHAR | Company description |
| *(+ 7 more fields)* | | locale, type, currency_name, share_class/weighted shares, list_date, homepage_url |
| date | DATE | Run date |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: Polygon Reference Tickers API (`/v3/reference/tickers/{ticker}`). **Grain**: (ticker, date). 20 total columns. Daily snapshot of company metadata, market cap, and employee count.

---

#### 12. Quarterly Income Statements — `sp500_income_statements_q`

Same schema as annual `sp500_income_statements` (table 6) but with quarterly periods (Q1-Q4).

**Source**: FMP Income Statement API (`/stable/income-statement?period=quarter`). **Grain**: (ticker, date, period). **~10,000 rows** (~500 tickers x ~20 quarters).

---

#### 13. Quarterly Balance Sheets — `sp500_balance_sheets_q`

Same schema as annual `sp500_balance_sheets` (table 7) but with quarterly periods (Q1-Q4).

**Source**: FMP Balance Sheet API (`/stable/balance-sheet-statement?period=quarter`). **Grain**: (ticker, date, period). **~10,000 rows**.

---

#### 14. Quarterly Cash Flow — `sp500_cash_flow_statements_q`

Same schema as annual `sp500_cash_flow_statements` (table 8) but with quarterly periods (Q1-Q4).

**Source**: FMP Cash Flow API (`/stable/cash-flow-statement?period=quarter`). **Grain**: (ticker, date, period). **~10,000 rows**.

---

#### 15. Key Metrics — `sp500_key_metrics`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| date | DATE | Fiscal period end date |
| period | VARCHAR | Reporting period (Q1-Q4, FY) |
| fiscal_year | VARCHAR | Fiscal year |
| market_cap | NUMBER | Market capitalization |
| enterprise_value | NUMBER | Enterprise value |
| ev_to_ebitda | FLOAT | EV/EBITDA ratio |
| ev_to_free_cash_flow | FLOAT | EV/FCF ratio |
| current_ratio | FLOAT | Current ratio |
| return_on_equity | FLOAT | Return on equity |
| return_on_invested_capital | FLOAT | ROIC |
| earnings_yield | FLOAT | Earnings yield |
| free_cash_flow_yield | FLOAT | FCF yield |
| *(+ 35 more fields)* | | Additional valuation, profitability, efficiency, and capital allocation ratios |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Key Metrics API (`/stable/key-metrics`). **Grain**: (ticker, date, period). 50 total columns covering valuation ratios (EV/EBITDA, P/E proxies), return metrics (ROE, ROA, ROIC), efficiency ratios (days outstanding, cash conversion cycle), and capital allocation metrics.

---

#### 16. Price Target Consensus — `sp500_price_target_consensus`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| target_high | FLOAT | Highest analyst price target |
| target_low | FLOAT | Lowest analyst price target |
| target_consensus | FLOAT | Consensus (mean) price target |
| target_median | FLOAT | Median price target |
| date | DATE | Run date |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Price Target Consensus API (`/stable/price-target-consensus`). **Grain**: (ticker, date). ~500 rows per daily run.

---

#### 17. Analyst Grades Consensus — `sp500_analyst_grades_consensus`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| strong_buy | INTEGER | Count of Strong Buy ratings |
| buy | INTEGER | Count of Buy ratings |
| hold | INTEGER | Count of Hold ratings |
| sell | INTEGER | Count of Sell ratings |
| strong_sell | INTEGER | Count of Strong Sell ratings |
| consensus | VARCHAR | Overall consensus rating (e.g., Buy, Hold) |
| date | DATE | Run date |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Upgrades/Downgrades Consensus API (`/stable/upgrades-downgrades-consensus`). **Grain**: (ticker, date). ~500 rows per daily run.

---

#### 18. Dividends — `sp500_dividends`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| date | DATE | Ex-dividend date |
| record_date | DATE | Record date |
| payment_date | DATE | Payment date |
| declaration_date | DATE | Declaration date |
| adj_dividend | FLOAT | Adjusted dividend amount |
| dividend | FLOAT | Dividend amount |
| yield | FLOAT | Dividend yield |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Dividends API (`/stable/stock-dividend`). **Grain**: (ticker, date). Full history per ticker.

---

#### 19. Splits — `sp500_splits`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| date | DATE | Split date |
| numerator | FLOAT | Split numerator (e.g., 4 in a 4:1 split) |
| denominator | FLOAT | Split denominator (e.g., 1 in a 4:1 split) |
| split_type | VARCHAR | Type of split |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Splits API (`/stable/historical-stock-split`). **Grain**: (ticker, date). Full history per ticker.

---

#### 20. Benchmark Prices — `sp500_benchmark_prices`

Same schema as `sp500_stock_prices` (table 2): ticker, open, high, low, close, volume, vwap, transactions, date, extracted_at.

**Source**: Polygon Aggregates API. **Grain**: (ticker, date). Covers 15 instruments: SPY, QQQ, IWM (broad market), XLF/XLK/XLE/XLV/XLI/XLY/XLP/XLU/XLC/XLRE/XLB (11 GICS sector ETFs), VIXY (VIX proxy). **~15 rows per trading day**. Backfill covers 5 years.

---

#### 21. Macro Rates — `sp500_macro_rates`

| Column | Type | Description |
|--------|------|-------------|
| series_id | VARCHAR | FRED series identifier (e.g., DFF, DGS10) |
| date | DATE | Observation date |
| value | FLOAT | Rate/index value |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FRED API (`/fred/series/observations`). **Grain**: (series_id, date). Series: DFF (Federal Funds Rate), DGS10 (10-Year Treasury), DGS2 (2-Year Treasury), BAMLH0A0HYM2 (High Yield OAS). **~4 rows per trading day**. Backfill covers 5 years.

---

#### 22. Insider Trades — `sp500_insider_trades`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol (filtered to S&P 500) |
| filing_date | DATE | SEC filing date |
| transaction_date | DATE | Transaction date |
| reporting_name | VARCHAR | Name of the insider |
| transaction_type | VARCHAR | Transaction type (e.g., P-Purchase, S-Sale) |
| securities_transacted | NUMBER | Number of securities transacted |
| price | FLOAT | Transaction price per share |
| *(+ 9 more fields)* | | reporting_cik, company_cik, type_of_owner, securities_owned, acquisition_or_disposition, direct_or_indirect, form_type, security_name, url |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Insider Trading Latest API (`/stable/insider-trading/latest`). **Grain**: (ticker, filing_date, reporting_name, transaction_type). 17 total columns. Paginated global feed filtered to S&P 500 tickers.

---

#### 23. Insider Trades Search — `sp500_insider_trades_search`

Same schema as `sp500_insider_trades` (table 22). 17 total columns.

**Source**: FMP Insider Trading Search API (`/stable/insider-trading/search`). **Grain**: (ticker, filing_date, reporting_name, transaction_type). Paginated global search feed filtered to S&P 500 tickers.

---

#### 24. FMP General News — `sp500_fmp_general_news`

| Column | Type | Description |
|--------|------|-------------|
| symbol | VARCHAR | Ticker symbol(s) mentioned (may be null) |
| published_date | TIMESTAMP_NTZ | Publication timestamp |
| publisher | VARCHAR | Publisher name |
| title | VARCHAR | Article title |
| content | VARCHAR | Full article content |
| article_url | VARCHAR | Article URL |
| *(+ 3 more fields)* | | image_url, site, date |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP General News API (`/stable/news/general-latest`). **Grain**: (article_url). UNFILTERED — not filtered to S&P 500. Paginated global feed.

---

#### 25. FMP Press Releases — `sp500_fmp_press_releases`

| Column | Type | Description |
|--------|------|-------------|
| symbol | VARCHAR | Ticker symbol mentioned |
| title | VARCHAR | Press release title |
| date | DATE | Publication date |
| content | VARCHAR | Full press release content |
| article_url | VARCHAR | Press release URL |
| *(+ 2 more fields)* | | image_url, site |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Press Releases API (`/stable/news/press-releases-latest`). **Grain**: (article_url). Paginated global feed.

---

#### 26. FMP Stock News — `sp500_fmp_stock_news`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Matched S&P 500 ticker |
| published_date | TIMESTAMP_NTZ | Publication timestamp |
| title | VARCHAR | Article title |
| date | DATE | Publication date |
| content | VARCHAR | Full article content |
| article_url | VARCHAR | Article URL |
| *(+ 2 more fields)* | | image_url, site |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: FMP Stock News API (`/stable/news/stock-latest`). **Grain**: (ticker, article_url). Paginated global feed filtered to S&P 500 tickers.

---

#### 27. Stock Snapshot — `sp500_stock_snapshot`

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock ticker symbol |
| name | VARCHAR | Company name |
| market_status | VARCHAR | Market status (open, closed, etc.) |
| session_change | FLOAT | Session price change |
| session_change_percent | FLOAT | Session percentage change |
| session_close | FLOAT | Session close price |
| session_high | FLOAT | Session high price |
| session_low | FLOAT | Session low price |
| session_open | FLOAT | Session open price |
| session_volume | NUMBER | Session volume |
| session_vwap | FLOAT | Session VWAP |
| *(+ 13 more fields)* | | type, early/regular trading changes, previous_close, price, last_minute OHLCV/vwap/transactions |
| date | DATE | Run date |
| extracted_at | TIMESTAMP_NTZ | Extraction timestamp |

**Source**: Polygon Snapshot API (`/v3/snapshot?ticker={ticker}`). **Grain**: (ticker, date). 26 total columns covering session data (change, OHLCV, VWAP), last-minute bar data, and ticker metadata. **~500 rows per daily run**.

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
| Income statements (annual) | ~2,500 total (~5 years x 500 tickers) | Full history per ticker |
| Balance sheets (annual) | ~2,500 total | Full history per ticker |
| Cash flow statements (annual) | ~2,500 total | Full history per ticker |
| FMP articles | ~500 rows (varies by news volume) | 398-day backfill available |
| Earnings calendar | ~100-200 rows (forward-looking snapshot) | 30-day forward window |
| Ticker details | ~500 rows | Daily snapshot |
| Quarterly income statements | ~10,000 total (~20 quarters x 500 tickers) | 5-year backfill available |
| Quarterly balance sheets | ~10,000 total | 5-year backfill available |
| Quarterly cash flow | ~10,000 total | 5-year backfill available |
| Key metrics | ~10,000 total (quarterly) | 5-year backfill available |
| Price target consensus | ~500 rows | Daily snapshot |
| Analyst grades consensus | ~500 rows | Daily snapshot |
| Dividends | ~2,000-5,000 total (varies by history) | Full history per ticker |
| Splits | ~50-200 total (infrequent events) | Full history per ticker |
| Benchmark prices | ~15 rows/trading day (15 instruments) | 5-year backfill available |
| Macro rates (FRED) | ~4 rows/trading day (4 series) | 5-year backfill available |
| Insider trades | ~50-200 rows/day (filtered to S&P 500) | 5-year backfill available |
| Insider trades search | ~50-200 rows/day (filtered to S&P 500) | 5-year backfill available |
| FMP general news | ~100-500 rows/day (unfiltered) | 5-year backfill available |
| FMP press releases | ~50-200 rows/day | 5-year backfill available |
| FMP stock news | ~100-500 rows/day (filtered to S&P 500) | 5-year backfill available |
| Stock snapshot | ~500 rows | Daily snapshot |
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
