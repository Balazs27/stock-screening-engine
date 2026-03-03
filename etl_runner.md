# ETL Runner — Command Library

**Repo:** `stock-screening-engine`  
**Generated:** 2026-03-01  
**Branch:** `phase-0.5`

> **TL;DR** All ETL scripts share the same invocation pattern: `python src/jobs/<script>.py <run_date> [optional args]`. Run from the project root with the venv activated and `.env` loaded.

---

## Prerequisites

```bash
# From project root
source venv/bin/activate
# .env must contain the variables listed in the Environment Variables section below
```

---

## Universe / Lookup

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_sp500_lookup.py` | Wikipedia | Daily | Single-date | `python -m src.jobs.ingest_sp500_lookup.py <run_date>` | `python -m src.jobs.ingest_sp500_lookup.py 2026-02-27` |

> **Must run first.** All other jobs call `get_sp500_tickers()` against the lookup table this script populates.

---

## Stock Prices & Market Data

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_polygon_prices.py` | Polygon | Business-day | Single-date | `python -m src.jobs.ingest_polygon_prices.py <run_date>` | `python -m src.jobs.ingest_polygon_prices.py 2026-02-27` |
| `ingest_polygon_prices_backfill.py` | Polygon | Business-day | Single-date (anchors lookback) | `python -m src.jobs.ingest_polygon_prices_backfill.py <run_date> [lookback_days]` | `python -m src.jobs.ingest_polygon_prices_backfill.py 2026-02-27 1826` |
| `ingest_polygon_ticker_details.py` | Polygon | Daily | Single-date | `python -m src.jobs.ingest_polygon_ticker_details.py <run_date>` | `python -m src.jobs.ingest_polygon_ticker_details.py 2026-02-27` |
| `ingest_polygon_benchmark_prices.py` | Polygon | Business-day | Single-date | `python -m src.jobs.ingest_polygon_benchmark_prices.py <run_date>` | `python -m src.jobs.ingest_polygon_benchmark_prices.py 2026-02-27` |
| `ingest_polygon_benchmark_prices_backfill.py` | Polygon | Business-day | Single-date (anchors lookback) | `python -m src.jobs.ingest_polygon_benchmark_prices_backfill.py <run_date> [lookback_days]` | `python -m src.jobs.ingest_polygon_benchmark_prices_backfill.py 2026-02-27 1826` |
| `ingest_polygon_stock_snapshot.py` | Polygon | Daily | Single-date (snapshot of price/quote/trade) | `python -m src.jobs.ingest_polygon_stock_snapshot.py <run_date>` | `python -m src.jobs.ingest_polygon_stock_snapshot.py 2026-02-27` |

---

## Technical Indicators

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_polygon_rsi.py` | Polygon | Business-day | Single-date | `python -m src.jobs.ingest_polygon_rsi.py <run_date> [window] [limit]` | `python -m src.jobs.ingest_polygon_rsi.py 2026-02-27 14 1` |
| `ingest_polygon_rsi_backfill.py` | Polygon | Business-day | Single-date (fetches history) | `python -m src.jobs.ingest_polygon_rsi_backfill.py <run_date>` | `python -m src.jobs.ingest_polygon_rsi_backfill.py 2026-02-27 14 1826` |
| `ingest_polygon_macd.py` | Polygon | Business-day | Single-date | `python -m src.jobs.ingest_polygon_macd.py <run_date> [limit]` | `python -m src.jobs.ingest_polygon_macd.py 2026-02-27 1` |
| `ingest_polygon_macd_backfill.py` | Polygon | Business-day | Single-date (fetches history) | `python -m src.jobs.ingest_polygon_macd_backfill.py <run_date>` | `python -m src.jobs.ingest_polygon_macd_backfill.py 2026-02-27 1826` |
| `ingest_polygon_sma.py` | Polygon | Business-day | Single-date | `python -m src.jobs.ingest_polygon_sma.py <run_date> [window] [limit]` | `python -m src.jobs.ingest_polygon_sma.py 2026-02-27 30 120` |

---

## Fundamental Data — Annual Statements

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fmp_income_statement.py` | FMP | Annual | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_income_statement.py <run_date>` | `python -m src.jobs.ingest_fmp_income_statement.py 2026-02-27` |
| `ingest_fmp_balance_sheet.py` | FMP | Annual | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_balance_sheet.py <run_date>` | `python -m src.jobs.ingest_fmp_balance_sheet.py 2026-02-27` |
| `ingest_fmp_cash_flow.py` | FMP | Annual | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_cash_flow.py <run_date>` | `python -m src.jobs.ingest_fmp_cash_flow.py 2026-02-27` |

---

## Fundamental Data — Quarterly Statements

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fmp_income_statement_q.py` | FMP | Quarterly | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_income_statement_q.py <run_date> [period]` | `python -m src.jobs.ingest_fmp_income_statement_q.py 2026-02-27 quarter` |
| `ingest_fmp_balance_sheet_q.py` | FMP | Quarterly | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_balance_sheet_q.py <run_date> [period]` | `python -m src.jobs.ingest_fmp_balance_sheet_q.py 2026-02-27 quarter` |
| `ingest_fmp_cash_flow_q.py` | FMP | Quarterly | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_cash_flow_q.py <run_date> [period]` | `python -m src.jobs.ingest_fmp_cash_flow_q.py 2026-02-27 quarter` |

---

## Valuation & Analyst

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fmp_key_metrics.py` | FMP | Quarterly | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_key_metrics.py <run_date> [period]` | `python -m src.jobs.ingest_fmp_key_metrics.py 2026-02-27 quarter` |
| `ingest_fmp_key_metrics_backfill.py` | FMP | Quarterly | Single-date (fetches all history) | `python -m src.jobs.ingest_fmp_key_metrics_backfill.py <run_date> [period]` | `python -m src.jobs.ingest_fmp_key_metrics_backfill.py 2026-02-27 quarter` |
| `ingest_fmp_analyst_consensus.py` | FMP | Daily | Single-date (snapshot) | `python -m src.jobs.ingest_fmp_analyst_consensus.py <run_date>` | `python -m src.jobs.ingest_fmp_analyst_consensus.py 2026-02-27` |

---

## Earnings

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fmp_earnings_calendar.py` | FMP | Calendar-based | Single-date (fetches 30-day forward window) | `python -m src.jobs.ingest_fmp_earnings_calendar.py <run_date> [forward_days]` | `python -m src.jobs.ingest_fmp_earnings_calendar.py 2026-02-27 30` |

---

## Corporate Actions

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fmp_dividends.py` | FMP | Event-based | Single-date (fetches full history per ticker) | `python -m src.jobs.ingest_fmp_dividends.py <run_date>` | `python -m src.jobs.ingest_fmp_dividends.py 2026-02-27` |
| `ingest_fmp_dividends_backfill.py` | FMP | Event-based | Single-date (same as daily — fetches full history) | `python -m src.jobs.ingest_fmp_dividends_backfill.py <run_date>` | `python -m src.jobs.ingest_fmp_dividends_backfill.py 2026-02-27` |
| `ingest_fmp_splits.py` | FMP | Event-based | Single-date (fetches full history per ticker) | `python -m src.jobs.ingest_fmp_splits.py <run_date>` | `python -m src.jobs.ingest_fmp_splits.py 2026-02-27` |

---

## Insider Trades

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fmp_insider_trades.py` | FMP | Event-based (SEC filings) | Single-date (paginated global feed, filtered to S&P 500) | `python -m src.jobs.ingest_fmp_insider_trades.py <run_date>` | `python -m src.jobs.ingest_fmp_insider_trades.py 2026-02-27` |
| `ingest_fmp_insider_trades_backfill.py` | FMP | Event-based (SEC filings) | Single-date (deep pagination, 5yr lookback) | `python -m src.jobs.ingest_fmp_insider_trades_backfill.py <run_date> [lookback_days] [max_pages]` | `python -m src.jobs.ingest_fmp_insider_trades_backfill.py 2026-02-27 1826` |
| `ingest_fmp_insider_trades_search.py` | FMP | Event-based (SEC filings) | Single-date (search feed, filtered to S&P 500) | `python -m src.jobs.ingest_fmp_insider_trades_search.py <run_date>` | `python -m src.jobs.ingest_fmp_insider_trades_search.py 2026-02-27` |
| `ingest_fmp_insider_trades_search_backfill.py` | FMP | Event-based (SEC filings) | Single-date (deep pagination, 5yr lookback) | `python -m src.jobs.ingest_fmp_insider_trades_search_backfill.py <run_date> [lookback_days] [max_pages]` | `python -m src.jobs.ingest_fmp_insider_trades_search_backfill.py 2026-02-27 1826` |

---

## Macro & Benchmarks

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fred_macro_rates.py` | FRED | Business-day | Single-date | `python -m src.jobs.ingest_fred_macro_rates.py <run_date>` | `python -m src.jobs.ingest_fred_macro_rates.py 2026-02-27` |
| `ingest_fred_macro_rates_backfill.py` | FRED | Business-day | Single-date (anchors 5yr lookback) | `python -m src.jobs.ingest_fred_macro_rates_backfill.py <run_date> [lookback_days]` | `python -m src.jobs.ingest_fred_macro_rates_backfill.py 2026-02-27 1826` |

---

## News — Polygon

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_polygon_news.py` | Polygon | Daily | Single-date | `python -m src.jobs.ingest_polygon_news.py <run_date> [limit_per_ticker]` | `python -m src.jobs.ingest_polygon_news.py 2026-02-27 10` |
| `ingest_polygon_news_backfill.py` | Polygon | Daily | Single-date (anchors lookback) | `python -m src.jobs.ingest_polygon_news_backfill.py <run_date>` | `python -m src.jobs.ingest_polygon_news_backfill.py 2026-02-27 1826` |

---

## News & Articles — FMP

| ETL | Source | Data Frequency | Run Mode | Run Command | Example |
|-----|--------|----------------|----------|-------------|---------|
| `ingest_fmp_articles.py` | FMP | Daily | Single-date (S&P 500 filtered) | `python -m src.jobs.ingest_fmp_articles.py <run_date>` | `python -m src.jobs.ingest_fmp_articles.py 2026-02-27` |
| `ingest_fmp_articles_backfill.py` | FMP | Historical | Deep pagination (5yr, S&P 500 filtered) | `python -m src.jobs.ingest_fmp_articles_backfill.py <run_date> [lookback_days] [max_pages]` | `python -m src.jobs.ingest_fmp_articles_backfill.py 2026-02-27 1826 5000` |
| `ingest_fmp_general_news.py` | FMP | Daily | Single-date (UNFILTERED — no S&P 500 dependency) | `python -m src.jobs.ingest_fmp_general_news.py <run_date>` | `python -m src.jobs.ingest_fmp_general_news.py 2026-02-27` |
| `ingest_fmp_general_news_backfill.py` | FMP | Historical | Deep pagination (5yr, UNFILTERED) | `python -m src.jobs.ingest_fmp_general_news_backfill.py <run_date> [lookback_days] [max_pages]` | `python -m src.jobs.ingest_fmp_general_news_backfill.py 2026-02-27 1826 5000` |
| `ingest_fmp_press_releases.py` | FMP | Daily | Single-date (UNFILTERED — no S&P 500 dependency) | `python -m src.jobs.ingest_fmp_press_releases.py <run_date>` | `python -m src.jobs.ingest_fmp_press_releases.py 2026-02-27` |
| `ingest_fmp_press_releases_backfill.py` | FMP | Historical | Deep pagination (5yr, UNFILTERED) | `python -m src.jobs.ingest_fmp_press_releases_backfill.py <run_date> [lookback_days] [max_pages]` | `python -m src.jobs.ingest_fmp_press_releases_backfill.py 2026-02-27 1826 5000` |
| `ingest_fmp_stock_news.py` | FMP | Daily | Single-date (S&P 500 filtered) | `python -m src.jobs.ingest_fmp_stock_news.py <run_date>` | `python -m src.jobs.ingest_fmp_stock_news.py 2026-02-27` |
| `ingest_fmp_stock_news_backfill.py` | FMP | Historical | Deep pagination (5yr, S&P 500 filtered) | `python -m src.jobs.ingest_fmp_stock_news_backfill.py <run_date> [lookback_days] [max_pages]` | `python -m src.jobs.ingest_fmp_stock_news_backfill.py 2026-02-27 1826 5000` |

> **S&P 500 filtered** means the script calls `get_sp500_tickers()` and requires `ingest_sp500_lookup` to have run first. **UNFILTERED** means the script fetches all available data from the FMP global feed regardless of the S&P 500 universe — it can run independently of the lookup step.

---

## Recommended Execution Order (First-Time Setup / Full Backfill)

Run in this order to satisfy upstream dependencies:

```bash
# Step 1 — Universe (required first by all ticker-dependent jobs)
python -m src.jobs.ingest_sp500_lookup 2026-02-27

# Step 2 — Price history (feeds technical indicators and return calculations)
python -m src.jobs.ingest_polygon_prices_backfill 2026-02-27 1826
python -m src.jobs.ingest_polygon_benchmark_prices_backfill 2026-02-27 1826
python -m src.jobs.ingest_polygon_stock_snapshot 2026-02-27

# Step 3 — Technical indicators
python -m src.jobs.ingest_polygon_rsi_backfill 2026-02-27
python -m src.jobs.ingest_polygon_macd_backfill 2026-02-27
python -m src.jobs.ingest_polygon_sma 2026-02-27

# Step 4 — Fundamentals (all fetch full history regardless of run_date)
python -m src.jobs.ingest_fmp_income_statement 2026-02-27
python -m src.jobs.ingest_fmp_balance_sheet 2026-02-27
python -m src.jobs.ingest_fmp_cash_flow 2026-02-27
python -m src.jobs.ingest_fmp_income_statement_q 2026-02-27
python -m src.jobs.ingest_fmp_balance_sheet_q 2026-02-27
python -m src.jobs.ingest_fmp_cash_flow_q 2026-02-27
python -m src.jobs.ingest_fmp_key_metrics_backfill 2026-02-27

# Step 5 — Earnings
python -m src.jobs.ingest_fmp_earnings_calendar 2026-02-27

# Step 6 — Analyst & valuation (snapshot)
python -m src.jobs.ingest_polygon_ticker_details 2026-02-27
python -m src.jobs.ingest_fmp_analyst_consensus 2026-02-27

# Step 7 — Corporate actions (event-based, fetch full history)
python -m src.jobs.ingest_fmp_dividends_backfill 2026-02-27
python -m src.jobs.ingest_fmp_splits 2026-02-27

# Step 8 — Insider trades (paginated global feeds)
python -m src.jobs.ingest_fmp_insider_trades_backfill 2026-02-27
python -m src.jobs.ingest_fmp_insider_trades_search_backfill 2026-02-27

# Step 9 — Macro (independent of S&P 500 universe)
python -m src.jobs.ingest_fred_macro_rates_backfill 2026-02-27 1826

# Step 10 — News & articles (S&P 500 filtered)
python -m src.jobs.ingest_polygon_news_backfill 2026-02-27 1826
python -m src.jobs.ingest_fmp_articles_backfill 2026-02-27 1826 5000
python -m src.jobs.ingest_fmp_stock_news_backfill 2026-02-27 1826 5000

# Step 11 — News (UNFILTERED — can run independently of Step 1)
python -m src.jobs.ingest_fmp_general_news_backfill 2026-02-27 1826 5000
python -m src.jobs.ingest_fmp_press_releases_backfill 2026-02-27 1826 5000
```

---

## Environment Variables

All scripts require `.env` (loaded automatically via `python-dotenv`). Required variables:

| Variable | Used By | Source |
|----------|---------|--------|
| `POLYGON_API_KEY` | All `ingest_polygon_*.py` | [polygon.io](https://polygon.io) |
| `FMP_API_KEY` | All `ingest_fmp_*.py` | [financialmodelingprep.com](https://financialmodelingprep.com) |
| `FRED_API_KEY` | `ingest_fred_*.py` | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/) |
| `SNOWFLAKE_ACCOUNT` | All jobs (via `snowflake_loader.py`) | Snowflake account identifier |
| `SNOWFLAKE_USER` | All jobs | Snowflake username |
| `SNOWFLAKE_PASSWORD` | All jobs | Snowflake password |
| `SNOWFLAKE_WAREHOUSE` | All jobs | Snowflake virtual warehouse name |
| `SNOWFLAKE_DATABASE` | All jobs | Snowflake database name |
| `STUDENT_SCHEMA` | All jobs | Target schema (e.g., `DEV_BSMITH`) |

---

## Notes

### Scripts that are event-based (empty results on many dates is expected)
- **`ingest_fmp_dividends.py` / `_backfill.py`** — Dividend events are sparse (typically quarterly per stock). Most run dates will return zero new rows.
- **`ingest_fmp_splits.py`** — Stock splits are rare. Empty results on most days are expected.
- **`ingest_fmp_insider_trades.py` / `_backfill.py`** — SEC Form 4 filings are irregular. These are paginated global feeds filtered to S&P 500 tickers. Running daily still produces correct idempotent results.
- **`ingest_fmp_insider_trades_search.py` / `_backfill.py`** — Alternative insider trades feed (search endpoint). Same global-feed pagination pattern as the latest-feed variant.

### Scripts that fetch the full history on every run (NOT ticker x date filtered)
These scripts call FMP bulk endpoints that return all available history per ticker — the `run_date` only gates the S&P 500 universe lookup:
- `ingest_fmp_income_statement_q.py` (and balance sheet, cash flow quarterly)
- `ingest_fmp_income_statement.py`, `ingest_fmp_balance_sheet.py`, `ingest_fmp_cash_flow.py` (annual)
- `ingest_fmp_key_metrics.py` / `_backfill.py`
- `ingest_fmp_dividends.py` / `_backfill.py`
- `ingest_fmp_splits.py`

**Implication:** For these scripts, running the daily variant once is sufficient for initial load since FMP returns full history per ticker unconditionally. Backfill variants (where they exist) are functionally identical.

### Scripts that use deep pagination for backfills
These backfill scripts paginate through a global FMP feed until reaching articles older than `start_date` (derived from `run_date - lookback_days`). They accept an optional `max_pages` parameter (default 5000) to cap pagination depth:
- `ingest_fmp_articles_backfill.py` — S&P 500 filtered
- `ingest_fmp_stock_news_backfill.py` — S&P 500 filtered
- `ingest_fmp_general_news_backfill.py` — UNFILTERED (no S&P 500 dependency)
- `ingest_fmp_press_releases_backfill.py` — UNFILTERED (no S&P 500 dependency)
- `ingest_fmp_insider_trades_backfill.py` — S&P 500 filtered
- `ingest_fmp_insider_trades_search_backfill.py` — S&P 500 filtered

### Scripts that use lookback windows for true date-range backfills
These scripts derive a date range from `run_date - lookback_days` to `run_date`. To backfill a specific historical window, set `run_date` to the desired end date and `lookback_days` to the window length:
- `ingest_polygon_prices_backfill.py` — default 398 days
- `ingest_polygon_benchmark_prices_backfill.py` — use 1826 for 5yr
- `ingest_fred_macro_rates_backfill.py` — default 1826 days (~5 years)

### Scripts that should NOT be treated as ticker x date (calendar/bulk endpoints)
- **`ingest_fmp_earnings_calendar.py`** — Fetches a forward-looking calendar window (`run_date` to `run_date + forward_days`). Running with `forward_days=30` is appropriate for daily use. For a full upcoming calendar sweep, increase `forward_days` to 90 or 180.
- **`ingest_fred_macro_rates.py`** — Fetches series-level data (FEDFUNDS, DGS10, CPIAUCSL, etc.), not per-ticker. The grain is `(series_id, date)`, not `(ticker, date)`. Empty results on weekends/holidays are expected since FRED only publishes on business days.

### Scripts that do NOT depend on the S&P 500 universe
These scripts can run independently of `ingest_sp500_lookup` — they do not call `get_sp500_tickers()`:
- **`ingest_fmp_general_news.py` / `_backfill.py`** — Fetches the FMP general news global feed without filtering by ticker.
- **`ingest_fmp_press_releases.py` / `_backfill.py`** — Fetches the FMP press releases global feed without filtering by ticker.
- **`ingest_polygon_benchmark_prices.py` / `_backfill.py`** — Fetches a hardcoded list of 15 instruments (SPY, QQQ, IWM, 11 sector ETFs, VIXY).
- **`ingest_fred_macro_rates.py` / `_backfill.py`** — Fetches FRED macro rate series (FEDFUNDS, DGS10, CPIAUCSL, etc.).

### Benchmark prices vs. stock prices
- **`ingest_polygon_benchmark_prices.py`** — Does NOT use the S&P 500 ticker lookup. It fetches a hardcoded list of 15 instruments (SPY, QQQ, IWM, 11 sector ETFs, VIXY). Safe to run independently of the universe lookup.

### Quarterly statement jobs (daily only, no backfill variants)
- `ingest_fmp_income_statement_q.py`, `ingest_fmp_balance_sheet_q.py`, `ingest_fmp_cash_flow_q.py` — These daily jobs fetch full history per ticker on every run. There are no separate backfill variants because the daily jobs already retrieve the complete history unconditionally.

### Assumptions documented here
- Annual statement jobs (`ingest_fmp_income_statement.py`, `ingest_fmp_balance_sheet.py`, `ingest_fmp_cash_flow.py`) follow the same pattern as their `_q` quarterly counterparts with `period="annual"` as default. Confirmed by existing pre-Phase-0.5 DAGs.
- `ingest_polygon_rsi_backfill.py` and `ingest_polygon_macd_backfill.py` use a larger `limit` parameter internally (e.g., 500-1000 historical datapoints per ticker) vs. the daily job's `limit=1`.
