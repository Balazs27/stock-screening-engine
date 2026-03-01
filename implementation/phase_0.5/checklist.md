# Phase 0.5 — Implementation Checklist

Analysis performed: 2026-03-01
Status: PRE-IMPLEMENTATION

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
  - [ ] `FMPClient.fetch_earnings_calendar()` added
  - [ ] `FMPClient.fetch_earnings_surprises()` added
  - [ ] `src/jobs/ingest_fmp_earnings_calendar.py` created
  - [ ] `src/jobs/ingest_fmp_earnings_surprises.py` created
  - [ ] `src/jobs/ingest_fmp_earnings_surprises_backfill.py` created
  - [ ] `dags/etl/fmp_earnings_calendar_dag.py` created
  - [ ] `dags/etl/fmp_earnings_surprises_dag.py` created
  - [ ] `dags/etl/fmp_earnings_surprises_backfill_dag.py` created
  - [ ] Raw tables created: `sp500_earnings_calendar`, `sp500_earnings_surprises`
  - [ ] DAGs parse without errors (`astro dev parse`)
  - [ ] Manual test run succeeds

- [ ] **Feature 02 — Ticker Overview / Market Cap**
  - [ ] `PolygonClient.fetch_ticker_details()` added
  - [ ] `src/jobs/ingest_polygon_ticker_details.py` created
  - [ ] `dags/etl/polygon_ticker_details_dag.py` created
  - [ ] Raw table created: `sp500_ticker_details`
  - [ ] DAG parses without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 03 — Quarterly Financial Statements**
  - [ ] `src/jobs/ingest_fmp_income_statement_q.py` created
  - [ ] `src/jobs/ingest_fmp_balance_sheet_q.py` created
  - [ ] `src/jobs/ingest_fmp_cash_flow_q.py` created
  - [ ] `src/jobs/ingest_fmp_income_statement_q_backfill.py` created
  - [ ] `src/jobs/ingest_fmp_balance_sheet_q_backfill.py` created
  - [ ] `src/jobs/ingest_fmp_cash_flow_q_backfill.py` created
  - [ ] `dags/etl/fmp_income_statement_q_dag.py` created
  - [ ] `dags/etl/fmp_balance_sheet_q_dag.py` created
  - [ ] `dags/etl/fmp_cash_flow_q_dag.py` created
  - [ ] `dags/etl/fmp_income_statement_q_backfill_dag.py` created
  - [ ] `dags/etl/fmp_balance_sheet_q_backfill_dag.py` created
  - [ ] `dags/etl/fmp_cash_flow_q_backfill_dag.py` created
  - [ ] Raw tables created: `sp500_income_statements_q`, `sp500_balance_sheets_q`, `sp500_cash_flow_statements_q`
  - [ ] All 6 DAGs parse without errors
  - [ ] Manual test run succeeds for each statement type

- [ ] **Feature 04 — Valuation Multiples (Key Metrics)**
  - [ ] `FMPClient.fetch_key_metrics()` added
  - [ ] `src/jobs/ingest_fmp_key_metrics.py` created
  - [ ] `src/jobs/ingest_fmp_key_metrics_backfill.py` created
  - [ ] `dags/etl/fmp_key_metrics_dag.py` created
  - [ ] `dags/etl/fmp_key_metrics_backfill_dag.py` created
  - [ ] Raw table created: `sp500_key_metrics`
  - [ ] DAGs parse without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 05 — Analyst Targets & Upgrades/Downgrades**
  - [ ] `FMPClient.fetch_price_target_consensus()` added
  - [ ] `FMPClient.fetch_upgrades_downgrades_consensus()` added
  - [ ] `src/jobs/ingest_fmp_analyst_consensus.py` created
  - [ ] `dags/etl/fmp_analyst_consensus_dag.py` created
  - [ ] Raw tables created: `sp500_price_target_consensus`, `sp500_upgrades_downgrades`
  - [ ] DAG parses without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 06 — Dividends & Splits**
  - [ ] `FMPClient.fetch_dividends()` added
  - [ ] `FMPClient.fetch_splits()` added
  - [ ] `src/jobs/ingest_fmp_dividends.py` created
  - [ ] `src/jobs/ingest_fmp_splits.py` created
  - [ ] `src/jobs/ingest_fmp_dividends_backfill.py` created
  - [ ] `src/jobs/ingest_fmp_splits_backfill.py` created
  - [ ] `dags/etl/fmp_dividends_dag.py` created
  - [ ] `dags/etl/fmp_splits_dag.py` created
  - [ ] `dags/etl/fmp_dividends_backfill_dag.py` created
  - [ ] `dags/etl/fmp_splits_backfill_dag.py` created
  - [ ] Raw tables created: `sp500_dividends`, `sp500_splits`
  - [ ] All 4 DAGs parse without errors
  - [ ] Manual test run succeeds

### Tier 2 — High Leverage

- [ ] **Feature 07 — Benchmarks, Sector ETFs & VIX**
  - [ ] `src/jobs/ingest_polygon_benchmark_prices.py` created
  - [ ] `src/jobs/ingest_polygon_benchmark_prices_backfill.py` created
  - [ ] `dags/etl/polygon_benchmark_prices_dag.py` created
  - [ ] `dags/etl/polygon_benchmark_prices_backfill_dag.py` created
  - [ ] Raw table created: `sp500_benchmark_prices`
  - [ ] DAGs parse without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 08 — Macro Rates (FRED)**
  - [ ] `src/api_clients/fred_client.py` created (new API client)
  - [ ] `FRED_API_KEY` added to `.env.example`
  - [ ] `src/jobs/ingest_fred_macro_rates.py` created
  - [ ] `src/jobs/ingest_fred_macro_rates_backfill.py` created
  - [ ] `dags/etl/fred_macro_rates_dag.py` created
  - [ ] `dags/etl/fred_macro_rates_backfill_dag.py` created
  - [ ] Raw table created: `sp500_macro_rates`
  - [ ] DAGs parse without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 09 — Insider Trades & Institutional Holdings**
  - [ ] `FMPClient.fetch_insider_trades()` added
  - [ ] `FMPClient.fetch_institutional_holders()` added
  - [ ] `src/jobs/ingest_fmp_insider_trades.py` created
  - [ ] `src/jobs/ingest_fmp_institutional_holders.py` created
  - [ ] `src/jobs/ingest_fmp_insider_trades_backfill.py` created
  - [ ] `src/jobs/ingest_fmp_institutional_holders_backfill.py` created
  - [ ] `dags/etl/fmp_insider_trades_dag.py` created
  - [ ] `dags/etl/fmp_institutional_holders_dag.py` created
  - [ ] `dags/etl/fmp_insider_trades_backfill_dag.py` created
  - [ ] `dags/etl/fmp_institutional_holders_backfill_dag.py` created
  - [ ] Raw tables created: `sp500_insider_trades`, `sp500_institutional_holders`
  - [ ] All 4 DAGs parse without errors
  - [ ] Manual test run succeeds

- [ ] **Feature 10 — Short Interest (TENTATIVE)**
  - [ ] **Availability gate:** FMP endpoint tested and returns data (not 403/404)
  - [ ] If available: `FMPClient.fetch_short_interest()` added
  - [ ] `src/jobs/ingest_fmp_short_interest.py` created
  - [ ] `src/jobs/ingest_fmp_short_interest_backfill.py` created
  - [ ] `dags/etl/fmp_short_interest_dag.py` created
  - [ ] `dags/etl/fmp_short_interest_backfill_dag.py` created
  - [ ] Raw table created: `sp500_short_interest`
  - [ ] If unavailable: documented as deprioritized with FINRA alternative noted

- [ ] **Feature 11 — Options Implied Volatility (TENTATIVE)**
  - [ ] **Availability gate:** Polygon options endpoint tested and returns data (not 403/404)
  - [ ] If available: `PolygonClient.fetch_options_iv_summary()` added
  - [ ] `src/jobs/ingest_polygon_options_iv.py` created
  - [ ] `dags/etl/polygon_options_iv_dag.py` created
  - [ ] Raw table created: `sp500_options_iv_summary`
  - [ ] If unavailable: documented as deprioritized

---

## Aggregate Impact Summary

### Files Modified

| File | Changes |
|------|---------|
| `src/api_clients/fmp_client.py` | +9 new methods (earnings calendar, earnings surprises, key metrics, price target consensus, upgrades/downgrades consensus, dividends, splits, insider trades, institutional holders) |
| `src/api_clients/polygon_client.py` | +1-2 new methods (ticker details, optionally options IV) |
| `.env.example` | +1 env var (FRED_API_KEY) |

### Files Created

| Category | Count | Location |
|----------|-------|----------|
| New API client | 1 | `src/api_clients/fred_client.py` |
| Daily jobs | 11-13 | `src/jobs/ingest_fmp_*.py`, `src/jobs/ingest_polygon_*.py`, `src/jobs/ingest_fred_*.py` |
| Backfill jobs | 9-11 | `src/jobs/ingest_*_backfill.py` |
| Daily DAGs | 11-13 | `dags/etl/*_dag.py` |
| Backfill DAGs | 9-11 | `dags/etl/*_backfill_dag.py` |
| **Total** | **41-49** | |

### New Raw Tables

| Table | Grain | Source | Cadence |
|-------|-------|--------|---------|
| `sp500_earnings_calendar` | (ticker, date) | FMP | Daily |
| `sp500_earnings_surprises` | (ticker, date) | FMP | Daily + 5yr backfill |
| `sp500_ticker_details` | (ticker, date) | Polygon | Daily |
| `sp500_income_statements_q` | (ticker, date, period) | FMP | Daily + 5yr backfill |
| `sp500_balance_sheets_q` | (ticker, date, period) | FMP | Daily + 5yr backfill |
| `sp500_cash_flow_statements_q` | (ticker, date, period) | FMP | Daily + 5yr backfill |
| `sp500_key_metrics` | (ticker, date, period) | FMP | Daily + 5yr backfill |
| `sp500_price_target_consensus` | (ticker, date) | FMP | Daily |
| `sp500_upgrades_downgrades` | (ticker, date) | FMP | Daily |
| `sp500_dividends` | (ticker, date) | FMP | Daily + 5yr backfill |
| `sp500_splits` | (ticker, date) | FMP | Daily + 10yr backfill |
| `sp500_benchmark_prices` | (ticker, date) | Polygon | Daily + 5yr backfill |
| `sp500_macro_rates` | (series_id, date) | FRED | Daily + 5yr backfill |
| `sp500_insider_trades` | (ticker, filing_date, ...) | FMP | Daily + 5yr backfill |
| `sp500_institutional_holders` | (ticker, holder, date_reported) | FMP | Daily + 5yr backfill |
| `sp500_short_interest` | (ticker, date) | FMP | Tentative |
| `sp500_options_iv_summary` | (ticker, date) | Polygon | Tentative |

### New Environment Variables

| Variable | Used By | Required? |
|----------|---------|-----------|
| `FRED_API_KEY` | `fred_client.py` | Yes (Feature 08 only) |

### API Rate Budget (Daily Run)

| Source | Features | Requests/Day | Estimated Time |
|--------|----------|-------------|----------------|
| FMP (0.1s/req) | 01, 03, 04, 05, 06, 09 | ~5,500 | ~9 min |
| Polygon (0.8s/req) | 02, 07 | ~520 | ~7 min |
| FRED (0.5s/req) | 08 | 4 | ~2 sec |
| **Total** | | ~6,024 | ~16 min |

---

## Cosmos DAG Integration

After Phase 0.5 is complete, the dbt Cosmos DAG (`dags/dbt/stock_screening_dbt_daily_dag.py`) must be updated to gate on the new ETL DAGs. Currently it waits for 5 DAGs:
- `sp500_lookup`
- `polygon_daily_prices`
- `polygon_daily_rsi`
- `polygon_daily_macd`
- `polygon_daily_news`

New sensors to add for Phase 0.5 data sources (only those that feed dbt models):
- Feature 01: `fmp_earnings_calendar`, `fmp_earnings_surprises`
- Feature 02: `polygon_ticker_details`
- Feature 03: `fmp_income_statement_q`, `fmp_balance_sheet_q`, `fmp_cash_flow_q`
- Feature 04: `fmp_key_metrics`
- Feature 05: `fmp_analyst_consensus`
- Feature 06: `fmp_dividends`, `fmp_splits`
- Feature 07: `polygon_benchmark_prices`
- Feature 08: `fred_macro_rates`
- Feature 09: `fmp_insider_trades`, `fmp_institutional_holders`

**Note:** This Cosmos DAG update should be done AFTER all ETL DAGs are verified working, not during individual feature implementation. It is a post-phase integration step.

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
| dbt source definitions | Phase 0.5 (post) | `_sources.yml` for all new raw tables |
| dbt staging models | Phase 0.5 (post) | `stg_*` views for all new raw tables |
| Index updates | Phase 0.5 (post) | Update `general_index.md`, `detailed_index.md`, `PROJECT_STRUCTURE.md` |

---

## Validation Protocol

After each feature is implemented:

1. **DAG parse test:** `astro dev parse` — all DAGs must parse without import errors
2. **Manual job test:** Run the daily job for a known date with real API credentials
3. **Row count check:** Verify non-empty results in Snowflake: `SELECT COUNT(*) FROM {schema}.{table}`
4. **Schema validation:** Verify column names and types match the DDL
5. **Idempotency test:** Run the same job twice and confirm no duplicate rows
6. **Backfill test (if applicable):** Run the backfill job for a small date range and verify data populates correctly
