# Phase 0.5 — Implementation Checklist

Analysis performed: 2026-03-01
Status: **ETL CODE PARTIALLY COMPLETE — Features 01/03/06/09 have gaps; Features 10/11 not started; Pending Snowflake table creation & manual test runs**

---

## Phase 0.5 Corrections

Correction work performed on 2026-03-03 after initial Phase 0.5 implementation was found to contain incorrect API endpoints, duplicate method names, broken ticker parsing logic, and hardcoded credentials in comments.

### Feature 09 — Insider Trades (Corrected)

**Original broken methods (removed):**
- `FMPClient.fetch_insider_trades()` — used non-existent endpoint `/stable/insider-trading?symbol={ticker}`; FMP returns `[]` silently (not 404)
- `FMPClient.fetch_institutional_holders()` — used non-existent endpoint `/stable/institutional-holder?symbol={ticker}`; same silent empty response

**Replacement methods added to `fmp_client.py`:**

Insider trades → two paginated global feed methods:
- `fetch_insider_trades_latest` — endpoint: `/stable/insider-trading/latest?page={p}&limit=100`
- `fetch_insider_trades_search` — endpoint: `/stable/insider-trading/search?page={p}&limit=100`

**Note:** The five institutional ownership methods (`fetch_institutional_ownership_holder_analytics`, `fetch_institutional_positions_summary`, `fetch_institutional_ownership_extract`, `fetch_institutional_holder_performance_summary`, `fetch_institutional_holder_industry_breakdown`) were planned but NOT implemented. Their corresponding jobs, DAGs, and backfills also do not exist.

**Job files rewritten:**
- `src/jobs/ingest_fmp_insider_trades.py` — complete rewrite for paginated feed; new 17-column schema; table: `sp500_insider_trades`

### FMP News Method Shadowing (Corrected)

**Original bug:** Two Python methods with the same name `fetch_news` in `fmp_client.py`. Python silently used the second definition, causing the FMP articles job to ingest general news data instead of FMP article data.

**Fix:**
- First `fetch_news` renamed to `fetch_fmp_articles` — endpoint: `/stable/fmp-articles`
- Second `fetch_news` renamed to `fetch_general_news` — endpoint: `/stable/general-latest`; now UNFILTERED (does not depend on S&P 500 tickers)
- `src/jobs/ingest_fmp_news.py` renamed to `src/jobs/ingest_fmp_articles.py`, updated to call `fetch_fmp_articles`
- `src/jobs/ingest_fmp_global_news.py` renamed to `src/jobs/ingest_fmp_general_news.py`, updated to call `fetch_general_news`
- `dags/etl/fmp_news_daily_dag.py` renamed to `dags/etl/fmp_articles_daily_dag.py`
- Hardcoded API key removed from comment in `fmp_client.py`
- Debug `print` statements removed from `src/jobs/ingest_fmp_dividends.py`
- Earnings calendar endpoint corrected from `/stable/earning-calendar` to `/stable/earnings-calendar`

### Additional Pipelines Created (Beyond Original Plan)

The following pipelines were created during correction work as valid additional data sources not covered in the original Feature 09 plan:

**New daily jobs (4 files):**
- `ingest_fmp_press_releases.py` — table: `sp500_fmp_press_releases` (UNFILTERED — no S&P 500 dependency)
- `ingest_fmp_stock_news.py` — table: `sp500_fmp_stock_news`
- `ingest_fmp_insider_trades_search.py` — table: `sp500_insider_trades_search`
- `ingest_polygon_stock_snapshot.py` — table: `sp500_stock_snapshot`

**New backfill jobs (3 files):** `ingest_fmp_insider_trades_search_backfill.py`, `ingest_fmp_press_releases_backfill.py`, `ingest_fmp_stock_news_backfill.py`. All with `DEFAULT_LOOKBACK_DAYS = 1826` (~5 years).

**New daily DAGs (5 files):** `fmp_press_releases_dag.py` (no ExternalTaskSensor — unfiltered), `fmp_stock_news_dag.py`, `fmp_insider_trades_search_dag.py`, `polygon_stock_snapshot_dag.py`, `fmp_global_news_dag.py` (no ExternalTaskSensor — unfiltered).

**New backfill DAGs (3 files):** `fmp_insider_trades_search_backfill_dag.py`, `fmp_press_releases_backfill_dag.py`, `fmp_stock_news_backfill_dag.py`.

### Updated DAG Parse Result

- Total daily ETL DAGs (implemented): **27** (including pre-existing Phase 0 DAGs)
- Total backfill DAGs (implemented): **14** (including pre-existing Phase 0 backfills)
- All implemented DAGs parse without errors
- The Cosmos dbt DAG (`stock_screening_dbt_daily_dag.py`) has a pre-existing parse failure in `astro dev parse` test environment due to dbt deps mock — NOT related to Phase 0.5 work.

---

## Overview

Phase 0.5 bridges Phase 0 (foundation scoring on annual financials + technical indicators) and Phase 1 (agent infrastructure). It adds 11 missing data sources across 2 tiers, transforming the system from a technical-only screener into a multi-factor daily ranking engine with earnings catalysts, quarterly fundamentals, valuation multiples, analyst sentiment, corporate actions, benchmarks, and macro context.

**Source:** `phase_0.5.md` at project root defines all data gaps, API endpoints, JSON schemas, grains, and join strategies.

---

## Implementation Order & Dependencies

Features are ordered by: (1) Tier 1 before Tier 2, (2) dependency chains, (3) standalone features first.

| # | Feature | Tier | Source | Depends On | New Client Code? | Tentative? |
|---|---------|------|--------|------------|-------------------|------------|
| 01 | Earnings Calendar & Surprises | 1 | FMP | — | Yes (2 new methods) | No |
| 02 | Ticker Overview / Market Cap | 1 | Polygon | — | Yes (1 new method) | No |
| 03 | Quarterly Financial Statements | 1 | FMP | — | No (reuses existing) | No |
| 04 | Valuation Multiples (Key Metrics) | 1 | FMP | — | Yes (1 new method) | No |
| 05 | Analyst Targets & Upgrades/Downgrades | 1 | FMP | — | Yes (2 new methods) | No |
| 06 | Dividends & Splits | 1 | FMP | — | Yes (2 new methods) | No |
| 07 | Benchmarks, Sector ETFs & VIX | 2 | Polygon | — | No (reuses existing) | No |
| 08 | Macro Rates (FRED) | 2 | FRED | — | Yes (new client file) | No |
| 09 | Insider Trades & Institutional Holdings | 2 | FMP | — | Yes (2 new methods) | No |
| 10 | Short Interest | 2 | FMP | — | Yes (1 new method) | **Yes** |
| 11 | Options Implied Volatility | 2 | Polygon | — | Yes (1 new method) | **Yes** |

**Tentative features (10, 11):** Require endpoint availability testing before implementation. If the endpoint returns 403/404, the feature is deprioritized and documented as unavailable.

---

## Feature Status Tracker

### Tier 1 — Critical

- [ ] **Feature 01 — Earnings Calendar & Surprises**
  - [x] `FMPClient.fetch_earnings_calendar()` added
  - [ ] `FMPClient.fetch_earnings_surprises()` — NOT IMPLEMENTED
  - [x] `src/jobs/ingest_fmp_earnings_calendar.py` created
  - [ ] `src/jobs/ingest_fmp_earnings_surprises.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_earnings_surprises_backfill.py` — NOT IMPLEMENTED
  - [x] `dags/etl/fmp_earnings_calendar_dag.py` created
  - [ ] `dags/etl/fmp_earnings_surprises_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_earnings_surprises_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] Raw tables created: `sp500_earnings_calendar`, `sp500_earnings_surprises`
  - [x] DAGs parse without errors (earnings calendar DAG only)
  - [ ] Manual test run succeeds

- [x] **Feature 02 — Ticker Overview / Market Cap**
  - [x] `PolygonClient.fetch_ticker_details()` added
  - [x] `src/jobs/ingest_polygon_ticker_details.py` created
  - [x] `dags/etl/polygon_ticker_details_dag.py` created
  - [ ] Raw table created: `sp500_ticker_details`
  - [x] DAG parses without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 03 — Quarterly Financial Statements**
  - [x] `src/jobs/ingest_fmp_income_statement_q.py` created
  - [x] `src/jobs/ingest_fmp_balance_sheet_q.py` created
  - [x] `src/jobs/ingest_fmp_cash_flow_q.py` created
  - [ ] `src/jobs/ingest_fmp_income_statement_q_backfill.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_balance_sheet_q_backfill.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_cash_flow_q_backfill.py` — NOT IMPLEMENTED
  - [x] `dags/etl/fmp_income_statement_q_dag.py` created
  - [x] `dags/etl/fmp_balance_sheet_q_dag.py` created
  - [x] `dags/etl/fmp_cash_flow_q_dag.py` created
  - [ ] `dags/etl/fmp_income_statement_q_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_balance_sheet_q_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_cash_flow_q_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] Raw tables created: `sp500_income_statements_q`, `sp500_balance_sheets_q`, `sp500_cash_flow_statements_q`
  - [x] Daily DAGs parse without errors (3 of 3)
  - [ ] Manual test run succeeds for each statement type

- [x] **Feature 04 — Valuation Multiples (Key Metrics)**
  - [x] `FMPClient.fetch_key_metrics()` added
  - [x] `src/jobs/ingest_fmp_key_metrics.py` created
  - [x] `src/jobs/ingest_fmp_key_metrics_backfill.py` created
  - [x] `dags/etl/fmp_key_metrics_dag.py` created
  - [x] `dags/etl/fmp_key_metrics_backfill_dag.py` created
  - [ ] Raw table created: `sp500_key_metrics`
  - [x] DAGs parse without errors
  - [ ] Manual test run succeeds

- [x] **Feature 05 — Analyst Targets & Upgrades/Downgrades**
  - [x] `FMPClient.fetch_price_target_consensus()` added
  - [x] `FMPClient.fetch_upgrades_downgrades_consensus()` added
  - [x] `src/jobs/ingest_fmp_analyst_consensus.py` created
  - [x] `dags/etl/fmp_analyst_consensus_dag.py` created
  - [ ] Raw tables created: `sp500_price_target_consensus`, `sp500_upgrades_downgrades`
  - [x] DAG parses without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 06 — Dividends & Splits**
  - [x] `FMPClient.fetch_dividends()` added
  - [x] `FMPClient.fetch_splits()` added
  - [x] `src/jobs/ingest_fmp_dividends.py` created
  - [x] `src/jobs/ingest_fmp_splits.py` created
  - [x] `src/jobs/ingest_fmp_dividends_backfill.py` created
  - [ ] `src/jobs/ingest_fmp_splits_backfill.py` — NOT IMPLEMENTED
  - [x] `dags/etl/fmp_dividends_dag.py` created
  - [x] `dags/etl/fmp_splits_dag.py` created
  - [x] `dags/etl/fmp_dividends_backfill_dag.py` created
  - [ ] `dags/etl/fmp_splits_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] Raw tables created: `sp500_dividends`, `sp500_splits`
  - [x] Daily + dividends backfill DAGs parse without errors (3 of 3)
  - [ ] Manual test run succeeds

### Tier 2 — High Leverage

- [x] **Feature 07 — Benchmarks, Sector ETFs & VIX**
  - [x] `src/jobs/ingest_polygon_benchmark_prices.py` created
  - [x] `src/jobs/ingest_polygon_benchmark_prices_backfill.py` created
  - [x] `dags/etl/polygon_benchmark_prices_dag.py` created
  - [x] `dags/etl/polygon_benchmark_prices_backfill_dag.py` created
  - [ ] Raw table created: `sp500_benchmark_prices`
  - [x] DAGs parse without errors
  - [ ] Manual test run succeeds

- [x] **Feature 08 — Macro Rates (FRED)**
  - [x] `src/api_clients/fred_client.py` created (new API client)
  - [x] `FRED_API_KEY` added to `.env.example`
  - [x] `src/jobs/ingest_fred_macro_rates.py` created
  - [x] `src/jobs/ingest_fred_macro_rates_backfill.py` created
  - [x] `dags/etl/fred_macro_rates_dag.py` created
  - [x] `dags/etl/fred_macro_rates_backfill_dag.py` created
  - [ ] Raw table created: `sp500_macro_rates`
  - [x] DAGs parse without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 09 — Insider Trades & Institutional Holdings** *(partially corrected — see Phase 0.5 Corrections section above)*
  - [x] ~~`FMPClient.fetch_insider_trades()` added~~ — **REMOVED** (non-existent endpoint)
  - [x] ~~`FMPClient.fetch_institutional_holders()` added~~ — **REMOVED** (non-existent endpoint)
  - [x] `FMPClient.fetch_insider_trades_latest()` added (replacement — paginated global feed)
  - [x] `FMPClient.fetch_insider_trades_search()` added (replacement — paginated search feed)
  - [ ] `FMPClient.fetch_institutional_ownership_holder_analytics()` — NOT IMPLEMENTED
  - [ ] `FMPClient.fetch_institutional_positions_summary()` — NOT IMPLEMENTED
  - [ ] `FMPClient.fetch_institutional_ownership_extract()` — NOT IMPLEMENTED (CIK-based)
  - [ ] `FMPClient.fetch_institutional_holder_performance_summary()` — NOT IMPLEMENTED (CIK-based)
  - [ ] `FMPClient.fetch_institutional_holder_industry_breakdown()` — NOT IMPLEMENTED (CIK-based)
  - [x] `src/jobs/ingest_fmp_insider_trades.py` rewritten (paginated feed, 17-column schema)
  - [ ] `src/jobs/ingest_fmp_institutional_holders.py` — NOT IMPLEMENTED
  - [x] `src/jobs/ingest_fmp_insider_trades_search.py` created
  - [ ] `src/jobs/ingest_fmp_institutional_positions_summary.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_institutional_ownership_extract.py` — NOT IMPLEMENTED (CIK-based)
  - [ ] `src/jobs/ingest_fmp_institutional_holder_perf_summary.py` — NOT IMPLEMENTED (CIK-based)
  - [ ] `src/jobs/ingest_fmp_institutional_holder_industry.py` — NOT IMPLEMENTED (CIK-based)
  - [x] `src/jobs/ingest_fmp_insider_trades_backfill.py` created
  - [ ] `src/jobs/ingest_fmp_institutional_holders_backfill.py` — NOT IMPLEMENTED
  - [x] `src/jobs/ingest_fmp_insider_trades_search_backfill.py` created
  - [ ] `src/jobs/ingest_fmp_institutional_positions_summary_backfill.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_institutional_ownership_extract_backfill.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_institutional_holder_perf_summary_backfill.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_institutional_holder_industry_backfill.py` — NOT IMPLEMENTED
  - [x] `dags/etl/fmp_insider_trades_dag.py` created
  - [ ] `dags/etl/fmp_institutional_holders_dag.py` — NOT IMPLEMENTED
  - [x] `dags/etl/fmp_insider_trades_backfill_dag.py` created
  - [ ] `dags/etl/fmp_institutional_holders_backfill_dag.py` — NOT IMPLEMENTED
  - [x] `dags/etl/fmp_insider_trades_search_dag.py` created
  - [ ] `dags/etl/fmp_institutional_positions_summary_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_institutional_ownership_extract_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_institutional_holder_perf_summary_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_institutional_holder_industry_dag.py` — NOT IMPLEMENTED
  - [x] `dags/etl/fmp_insider_trades_search_backfill_dag.py` created
  - [ ] `dags/etl/fmp_institutional_positions_summary_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_institutional_ownership_extract_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_institutional_holder_perf_summary_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_institutional_holder_industry_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] Raw tables created: `sp500_insider_trades`, `sp500_institutional_holders`, `sp500_insider_trades_search`, `sp500_institutional_positions_summary`, `sp500_institutional_ownership_extract`, `sp500_institutional_holder_perf_summary`, `sp500_institutional_holder_industry`
  - [x] Insider trades DAGs parse without errors (4 of 4: daily + backfill for both feeds)
  - [ ] Manual test run succeeds

- [ ] **Feature 10 — Short Interest (TENTATIVE)** — NOT IMPLEMENTED
  - [ ] **Availability gate:** FMP endpoint tested and returns data (not 403/404)
  - [ ] `FMPClient.fetch_short_interest()` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_short_interest.py` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_fmp_short_interest_backfill.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_short_interest_dag.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/fmp_short_interest_backfill_dag.py` — NOT IMPLEMENTED
  - [ ] Raw table created: `sp500_short_interest`
  - [ ] If unavailable: documented as deprioritized with FINRA alternative noted

- [ ] **Feature 11 — Options Implied Volatility (TENTATIVE)** — NOT IMPLEMENTED
  - [ ] **Availability gate:** Polygon options endpoint tested and returns data (not 403/404)
  - [ ] `PolygonClient.fetch_options_iv_summary()` — NOT IMPLEMENTED
  - [ ] `src/jobs/ingest_polygon_options_iv.py` — NOT IMPLEMENTED
  - [ ] `dags/etl/polygon_options_iv_dag.py` — NOT IMPLEMENTED
  - [ ] Raw table created: `sp500_options_iv_summary`
  - [ ] If unavailable: documented as deprioritized

---

## Aggregate Impact Summary

### Files Modified

| File | Changes |
|------|---------|
| `src/api_clients/fmp_client.py` | +7 new methods (earnings calendar, key metrics, price target consensus, upgrades/downgrades consensus, dividends, splits, insider_trades_latest); +2 corrected news methods (fetch_fmp_articles, fetch_general_news); +1 corrected insider trade search method; earnings calendar endpoint corrected; hardcoded API key removed from comment |
| `src/api_clients/polygon_client.py` | +2 new methods (ticker details, stock snapshot) |
| `.env.example` | +1 env var (FRED_API_KEY) |
| `src/jobs/ingest_fmp_news.py` | Renamed to `ingest_fmp_articles.py`; updated method call from `fetch_news` to `fetch_fmp_articles` |
| `src/jobs/ingest_fmp_global_news.py` | Renamed to `ingest_fmp_general_news.py`; updated method call from `fetch_news` to `fetch_general_news` |
| `src/jobs/ingest_fmp_insider_trades.py` | Complete rewrite for paginated feed; new 17-column schema |
| `src/jobs/ingest_fmp_dividends.py` | Removed debug print statements |
| `dags/etl/fmp_news_daily_dag.py` | Renamed to `fmp_articles_daily_dag.py` |

### Files Created

| Category | Count | Location |
|----------|-------|----------|
| New API client | 1 | `src/api_clients/fred_client.py` |
| Daily jobs (new) | 17 | `src/jobs/ingest_fmp_*.py`, `src/jobs/ingest_polygon_*.py`, `src/jobs/ingest_fred_*.py` |
| Backfill jobs (new) | 10 | `src/jobs/ingest_*_backfill.py` (all DEFAULT_LOOKBACK_DAYS=1826) |
| Daily DAGs (new) | 18 | `dags/etl/*_dag.py` |
| Backfill DAGs (new) | 10 | `dags/etl/*_backfill_dag.py` |
| **Total new files** | **56** | |

Note: Daily job count (17) excludes the 10 pre-existing Phase 0 jobs (sp500_lookup, polygon prices/rsi/macd/news + backfills, fmp income/balance/cash_flow/news). Daily DAG count (18) excludes the 14 pre-existing Phase 0 DAGs. Counts reflect only files created during Phase 0.5.

### New Raw Tables (Implemented)

| Table | Grain | Source | Cadence |
|-------|-------|--------|---------|
| `sp500_earnings_calendar` | (ticker, date) | FMP | Daily |
| `sp500_ticker_details` | (ticker, date) | Polygon | Daily |
| `sp500_income_statements_q` | (ticker, date, period) | FMP | Daily (backfill NOT implemented) |
| `sp500_balance_sheets_q` | (ticker, date, period) | FMP | Daily (backfill NOT implemented) |
| `sp500_cash_flow_statements_q` | (ticker, date, period) | FMP | Daily (backfill NOT implemented) |
| `sp500_key_metrics` | (ticker, date, period) | FMP | Daily + 5yr backfill |
| `sp500_price_target_consensus` | (ticker, date) | FMP | Daily |
| `sp500_upgrades_downgrades` | (ticker, date) | FMP | Daily |
| `sp500_dividends` | (ticker, date) | FMP | Daily + 5yr backfill |
| `sp500_splits` | (ticker, date) | FMP | Daily (backfill NOT implemented) |
| `sp500_benchmark_prices` | (ticker, date) | Polygon | Daily + 5yr backfill |
| `sp500_macro_rates` | (series_id, date) | FRED | Daily + 5yr backfill |
| `sp500_insider_trades` | (ticker, filing_date, ...) | FMP | Daily + 5yr backfill |
| `sp500_insider_trades_search` | (filing_date, ...) | FMP | Daily + 5yr backfill |
| `sp500_fmp_press_releases` | (date) | FMP | Daily + 5yr backfill (UNFILTERED) |
| `sp500_fmp_stock_news` | (ticker, date) | FMP | Daily + 5yr backfill |
| `sp500_stock_snapshot` | (ticker, date) | Polygon | Daily |

### New Raw Tables (NOT Implemented)

| Table | Grain | Source | Status |
|-------|-------|--------|--------|
| `sp500_earnings_surprises` | (ticker, date) | FMP | Feature 01 — method + job + DAG not implemented |
| `sp500_short_interest` | (ticker, date) | FMP | Feature 10 — tentative, not implemented |
| `sp500_options_iv_summary` | (ticker, date) | Polygon | Feature 11 — tentative, not implemented |
| `sp500_institutional_holders` | (ticker, ...) | FMP | Feature 09 — not implemented |
| `sp500_institutional_positions_summary` | (ticker, ...) | FMP | Feature 09 — not implemented |
| `sp500_institutional_ownership_extract` | (cik, ...) | FMP | Feature 09 — not implemented |
| `sp500_institutional_holder_perf_summary` | (cik, ...) | FMP | Feature 09 — not implemented |
| `sp500_institutional_holder_industry` | (cik, ...) | FMP | Feature 09 — not implemented |

### New Environment Variables

| Variable | Used By | Required? |
|----------|---------|-----------|
| `FRED_API_KEY` | `fred_client.py` | Yes (Feature 08 only) |

### API Rate Budget (Daily Run)

| Source | Features | Requests/Day | Estimated Time |
|--------|----------|-------------|----------------|
| FMP (0.1s/req) | 01 (partial), 03, 04, 05, 06, 09 (partial) | ~3,500 | ~6 min |
| Polygon (0.8s/req) | 02, 07 | ~520 | ~7 min |
| FRED (0.5s/req) | 08 | 4 | ~2 sec |
| **Total** | | ~4,024 | ~13 min |

---

## Cosmos DAG Integration

After Phase 0.5 is complete, the dbt Cosmos DAG (`dags/dbt/stock_screening_dbt_daily_dag.py`) must be updated to gate on the new ETL DAGs. Currently it waits for 5 DAGs:
- `sp500_lookup`
- `polygon_daily_prices`
- `polygon_daily_rsi`
- `polygon_daily_macd`
- `polygon_daily_news`

New sensors to add for Phase 0.5 data sources (only those that feed dbt models):
- Feature 01: `fmp_earnings_calendar` (earnings surprises NOT implemented)
- Feature 02: `polygon_ticker_details`
- Feature 03: `fmp_income_statement_q`, `fmp_balance_sheet_q`, `fmp_cash_flow_q`
- Feature 04: `fmp_key_metrics`
- Feature 05: `fmp_analyst_consensus`
- Feature 06: `fmp_dividends`, `fmp_splits`
- Feature 07: `polygon_benchmark_prices`
- Feature 08: `fred_macro_rates`
- Feature 09: `fmp_insider_trades` (institutional holdings NOT implemented)

**Note:** This Cosmos DAG update should be done AFTER all ETL DAGs are verified working, not during individual feature implementation. It is a post-phase integration step.

---

## Remaining Work (Post-Code)

The following items require Snowflake access or a running environment:

| Item | Owner | Notes |
|------|-------|-------|
| Create 17 raw tables in Snowflake | DBA / Ops | DDL definitions in each job file |
| Run manual job tests per feature | Engineer | Requires real API credentials in `.env` |
| Verify row counts in Snowflake | Engineer | `SELECT COUNT(*) FROM RAW.{table}` |
| Implement missing features (10, 11) | Engineer | Short interest and options IV — tentative, need endpoint testing |
| Implement missing Feature 01 items | Engineer | Earnings surprises method, job, DAGs |
| Implement missing Feature 03 backfills | Engineer | Quarterly income/balance/cash flow backfill jobs + DAGs |
| Implement missing Feature 06 backfill | Engineer | Splits backfill job + DAG |
| Implement missing Feature 09 institutional items | Engineer | 5 FMP methods, 5 jobs, 5 daily DAGs, 5 backfill jobs, 5 backfill DAGs |
| Update Cosmos DAG sensors | Engineer | Add new `ExternalTaskSensor` entries for implemented ETL DAGs |
| Add `dbt/sources/_sources.yml` entries | Engineer | One source block per new raw table |
| Add `stg_*` dbt staging views | Engineer | One view per raw table in `_stg` schema |
| Update `general_index.md` | Engineer | Document all new files |
| Update `detailed_index.md` | Engineer | Grain, materialization, test coverage for each |
| Update `PROJECT_STRUCTURE.md` | Engineer | Reflect new DAGs and job files |

---

## Post-Phase Steps (Not Part of Phase 0.5)

These items are enabled by Phase 0.5 data but are implemented in later phases:

| Item | Phase | Description |
|------|-------|-------------|
| `int_sp500_fundamentals_ttm` | Phase 1+ | TTM computation from quarterly statements (SUM trailing 4 quarters for flow metrics) |
| Valuation scoring model | Phase 1+ | dbt mart scoring P/E, P/B, EV/EBITDA from key_metrics |
| Earnings catalyst detection | Phase 2 | Agent-based earnings surprise analysis |
| Relative performance scoring | Phase 1+ | Stock vs benchmark/sector returns using benchmark prices |
| Market regime detection | Phase 1+ | Rate environment classification using macro rates |
| Ownership signal scoring | Phase 3 | Insider buy/sell ratio scoring |

---

## Validation Protocol

After each feature is implemented:

1. **DAG parse test:** `astro dev parse` — all DAGs must parse without import errors
2. **Manual job test:** Run the daily job for a known date with real API credentials
3. **Row count check:** Verify non-empty results in Snowflake: `SELECT COUNT(*) FROM {schema}.{table}`
4. **Schema validation:** Verify column names and types match the DDL
5. **Idempotency test:** Run the same job twice and confirm no duplicate rows
6. **Backfill test (if applicable):** Run the backfill job for a small date range and verify data populates correctly
