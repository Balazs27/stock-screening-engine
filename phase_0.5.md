# Phase 0.5 — Missing Data Acquisition Plan

## Overview

Phase 0.5 bridges the gap between the current baseline scoring system (Phase 0) and a production-grade daily opportunity pipeline. The existing platform computes technical scores (price/momentum/MACD) and fundamental scores (annual financials only), but lacks the data density required for reliable stock ranking and catalyst detection.

This document catalogs every Tier 1 (critical) and Tier 2 (high-leverage) data gap, specifying exact API endpoints, response schemas, grain definitions, and join strategies. Each item is scoped so that an engineer can immediately write ETL scripts following the patterns already established in `src/`.

Phase 0.5 delivers: earnings-driven catalyst detection, proper valuation scoring via quarterly TTM fundamentals, analyst sentiment signals, corporate action handling, and market-relative benchmarking — transforming the system from a technical-only screener into a multi-factor daily ranking engine.

---

## Constraints & Guardrails

- **Architecture authority:** `.claude/rules/analytics-architecture.md` governs all layer boundaries, naming, and dependency rules. No exceptions.
- **ETL patterns:** All new scripts MUST follow existing patterns in `src/`:
  - API clients in `src/api_clients/` — fetch only, return DataFrames, never touch Snowflake.
  - Loaders in `src/loaders/snowflake_loader.py` — write only, never call APIs.
  - Jobs in `src/jobs/` — thin glue (client -> loader), no business logic.
  - DAGs in `dags/etl/` — orchestration only, `PythonOperator` + `ExternalTaskSensor` gating on `sp500_lookup`.
- **Incremental strategy:** All incremental dbt models use `delete+insert` with the double-filter pattern. Never `merge`.
- **Rate limiting:** Use the existing `_get()` + `_fetch_batch()` concurrency pattern (0.8s/req Polygon, 0.1s/req FMP, 3x retry with exponential backoff, 8 workers).
- **Idempotency:** All loaders use `overwrite_partition()` or `overwrite_date_range()`. Re-runs must be safe.
- **VARIANT columns:** JSON arrays/objects must use `overwrite_partition_with_variants()` at the loader level. Never parse JSON in dbt.
- **Snowflake identifiers:** Raw DDL uses UPPERCASE column names. dbt SQL uses lowercase.
- **Backfills:** Every new data source MUST have a backfill job + DAG (schedule=None, manual trigger).
- **Forbidden:** Never expose RAW/STG/INT to MCP or Superset. Never hardcode dates in incremental watermarks. Never use `merge` incremental strategy.

---

## Tier 1 — Earnings Calendar & Surprises

- **What it is:** Scheduled earnings report dates (with pre/post-market timing) and historical actual-vs-estimated EPS surprise data for each ticker.
- **Why Phase 0.5 needs it:** Earnings events are the single highest-impact catalyst for stock price movement. Without them, the opportunity pipeline cannot flag upcoming catalysts or score post-earnings momentum.
- **Primary Source:** FMP — provides both calendar and historical surprises with per-ticker granularity; Polygon does not offer earnings calendar data.
- **Endpoint(s):**
  - `GET /stable/earning-calendar?from={YYYY-MM-DD}&to={YYYY-MM-DD}&apikey={key}`
  - `GET /stable/earnings-surprises?symbol={ticker}&apikey={key}`
- **Request pattern:**
  - Method: GET
  - Calendar: date-range params (`from`, `to`); fetch 30-day forward window daily; global endpoint, filter to S&P 500 tickers post-fetch
  - Surprises: per-ticker; use `_fetch_batch()` across S&P 500 universe
  - Rate limit: use repo standard FMP rate-limit guards (0.1s/req)
- **Grain & cadence:**
  - Calendar grain: (ticker, date) — one row per ticker per expected earnings date
  - Surprises grain: (ticker, date) — one row per ticker per historical earnings event
  - Refresh: daily (calendar shifts as dates are confirmed/revised)
  - Backfill: 5 years of historical surprises for trend analysis
- **Join keys:** `ticker`
- **Raw tables:** `sp500_earnings_calendar`, `sp500_earnings_surprises`
- **JSON output schema:**

**Earnings Calendar** (expected_schema):
```json
[
  {
    "date": "string (YYYY-MM-DD)",
    "symbol": "string",
    "eps": "number | null",
    "epsEstimated": "number | null",
    "time": "string (bmo|amc|--|null)",
    "revenue": "number | null",
    "revenueEstimated": "number | null",
    "updatedFromDate": "string (YYYY-MM-DD) | null",
    "fiscalDateEnding": "string (YYYY-MM-DD)"
  }
]
```

**Earnings Surprises** (expected_schema):
```json
[
  {
    "date": "string (YYYY-MM-DD)",
    "symbol": "string",
    "actualEarningResult": "number | null",
    "estimatedEarning": "number | null"
  }
]
```

Validate by sampling a real API response during implementation.

---

## Tier 1 — Ticker Overview (Market Cap & Shares Outstanding)

- **What it is:** Per-ticker reference data including market capitalization, total and weighted shares outstanding, and company metadata that changes with price.
- **Why Phase 0.5 needs it:** Market cap is required for valuation multiples (P/E, P/B, EV/EBITDA), size-based scoring, and index weighting. Shares outstanding are needed to compute per-share metrics from raw financials.
- **Primary Source:** Polygon — the `/v3/reference/tickers/{ticker}` endpoint returns market cap and share counts as part of the reference snapshot; this is a natural fit for reference data and avoids conflating it with FMP's derived financial ratios.
- **Endpoint(s):**
  - `GET /v3/reference/tickers/{ticker}?apiKey={key}`
- **Request pattern:**
  - Method: GET
  - Per-ticker call; use `_fetch_batch()` across S&P 500 universe
  - Rate limit: use repo standard Polygon rate-limit guards (0.8s/req); ~500 tickers x 0.8s = ~7 min
- **Grain & cadence:**
  - Grain: (ticker, date) — one row per ticker per snapshot date
  - Refresh: daily (market cap changes with price)
  - Backfill: not applicable (point-in-time snapshot; historical mcap can be derived from price x shares)
- **Join keys:** `ticker`
- **Raw table:** `sp500_ticker_details`
- **JSON output schema:**

```json
{
  "status": "string",
  "results": {
    "ticker": "string",
    "name": "string",
    "market": "string",
    "locale": "string",
    "primary_exchange": "string",
    "type": "string",
    "active": "boolean",
    "currency_name": "string",
    "cik": "string | null",
    "market_cap": "number | null",
    "share_class_shares_outstanding": "number | null",
    "weighted_shares_outstanding": "number | null",
    "list_date": "string (YYYY-MM-DD) | null",
    "sic_code": "string | null",
    "sic_description": "string | null",
    "total_employees": "number | null",
    "homepage_url": "string | null",
    "description": "string | null"
  }
}
```

Note: Response is a single object (not array). Extract `results` and flatten into one DataFrame row per ticker.

---

## Tier 1 — Quarterly Financial Statements & TTM Fundamentals

- **What it is:** Quarterly (Q1-Q4) income statements, balance sheets, and cash flow statements, plus trailing-twelve-month (TTM) aggregations computed from the most recent 4 quarters.
- **Why Phase 0.5 needs it:** The current system uses annual financials only, meaning fundamental scores can be 6-12 months stale. Quarterly data enables TTM fundamentals that update every ~90 days, critical for timely valuation and growth scoring.
- **Primary Source:** FMP — same endpoints already used for annual statements with `period=quarter`; no new API client methods needed.
- **Endpoint(s):**
  - `GET /stable/income-statement?symbol={ticker}&period=quarter&apikey={key}`
  - `GET /stable/balance-sheet-statement?symbol={ticker}&period=quarter&apikey={key}`
  - `GET /stable/cash-flow-statement?symbol={ticker}&period=quarter&apikey={key}`
- **Request pattern:**
  - Method: GET
  - Per-ticker call for each of 3 statements; use existing `FMPClient.fetch_income_statements(tickers, period="quarter")` etc.
  - Rate limit: use repo standard FMP rate-limit guards (0.1s/req)
  - Note: 3 endpoints x ~500 tickers = ~1,500 requests per refresh (~2.5 min)
- **Grain & cadence:**
  - Grain: (ticker, date, period) — one row per ticker per fiscal quarter per statement type
  - Refresh: daily (idempotent; most days return same data, picks up new filings within 24h)
  - Backfill: 5 years (20 quarters) for robust TTM and YoY computation
- **Join keys:** `ticker`, `date`, `fiscal_year`, `period`
- **Raw tables:** `sp500_income_statements_q`, `sp500_balance_sheets_q`, `sp500_cash_flow_statements_q`
- **JSON output schema:** Identical to existing annual statement schemas. See `src/api_clients/fmp_client.py`:
  - Income: lines 99-175 (45+ fields)
  - Balance sheet: lines 181-278 (60+ fields)
  - Cash flow: lines 284-368 (45+ fields)

  The `period` field will contain `Q1`, `Q2`, `Q3`, or `Q4` instead of `FY`.
- **TTM computation:** Performed in dbt intermediate layer (new model: `int_sp500_fundamentals_ttm`). SUM trailing 4 quarters for flow metrics (revenue, net_income, FCF, operating_cash_flow). Latest-quarter snapshot for stock metrics (total_assets, total_debt, total_equity).

---

## Tier 1 — Valuation Multiples & Valuation Score

- **What it is:** Pre-computed valuation ratios (P/E, P/B, P/S, EV/EBITDA, EV/FCF, dividend yield, earnings yield) and per-share metrics per ticker per fiscal period.
- **Why Phase 0.5 needs it:** The current scoring system has no valuation dimension. Without P/E, P/B, and EV/EBITDA, the system cannot distinguish cheap stocks from expensive ones, making composite rankings incomplete for value-aware screening.
- **Primary Source:** FMP — the `/stable/key-metrics` endpoint provides 40+ pre-computed ratios per ticker per period, avoiding the complexity of computing ratios from raw price + TTM fundamentals while providing consistent cross-ticker data.
- **Endpoint(s):**
  - `GET /stable/key-metrics?symbol={ticker}&period=quarter&apikey={key}`
  - (Also fetch `period=annual` for annual-level ratios used in historical screening)
- **Request pattern:**
  - Method: GET
  - Per-ticker; use `_fetch_batch()` across S&P 500 universe
  - Rate limit: use repo standard FMP rate-limit guards (0.1s/req)
- **Grain & cadence:**
  - Grain: (ticker, date, period) — one row per ticker per fiscal period
  - Refresh: daily (picks up new quarterly filings)
  - Backfill: 5 years for trend and relative-value analysis
- **Join keys:** `ticker`, `date`
- **Raw table:** `sp500_key_metrics`
- **JSON output schema** (expected_schema — fields relevant to Phase 0.5 scoring):

```json
[
  {
    "symbol": "string",
    "date": "string (YYYY-MM-DD)",
    "period": "string (FY|Q1|Q2|Q3|Q4)",
    "revenuePerShare": "number | null",
    "netIncomePerShare": "number | null",
    "operatingCashFlowPerShare": "number | null",
    "freeCashFlowPerShare": "number | null",
    "cashPerShare": "number | null",
    "bookValuePerShare": "number | null",
    "marketCap": "number | null",
    "enterpriseValue": "number | null",
    "peRatio": "number | null",
    "priceToSalesRatio": "number | null",
    "pbRatio": "number | null",
    "evToSales": "number | null",
    "enterpriseValueOverEBITDA": "number | null",
    "evToFreeCashFlow": "number | null",
    "earningsYield": "number | null",
    "freeCashFlowYield": "number | null",
    "dividendYield": "number | null",
    "debtToEquity": "number | null",
    "debtToAssets": "number | null",
    "currentRatio": "number | null",
    "interestCoverage": "number | null",
    "roe": "number | null",
    "roic": "number | null",
    "payoutRatio": "number | null"
  }
]
```

Validate by sampling a real API response during implementation.

---

## Tier 1 — Analyst Price Targets & Upgrades/Downgrades

- **What it is:** Consensus analyst price targets (high/low/median/consensus) and aggregate ratings distribution (strong buy/buy/hold/sell/strong sell) per ticker.
- **Why Phase 0.5 needs it:** Analyst sentiment is a leading indicator of institutional capital flows. Price target upside/downside provides a forward-looking valuation anchor, and rating changes (upgrades/downgrades) are near-term catalysts for the opportunity pipeline.
- **Primary Source:** FMP — only FMP in our stack provides analyst consensus data; Polygon does not offer analyst targets or ratings.
- **Endpoint(s):**
  - `GET /stable/price-target-consensus?symbol={ticker}&apikey={key}`
  - `GET /stable/upgrades-downgrades-consensus?symbol={ticker}&apikey={key}`
- **Request pattern:**
  - Method: GET
  - Per-ticker; use `_fetch_batch()` for each endpoint across S&P 500 universe
  - Rate limit: use repo standard FMP rate-limit guards (0.1s/req)
  - Note: 2 endpoints x ~500 tickers = ~1,000 requests per refresh (~1.7 min)
- **Grain & cadence:**
  - Price targets grain: (ticker, date) — one consensus snapshot per ticker per day (store daily for trend)
  - Ratings grain: (ticker, date) — one consensus distribution per ticker per day
  - Refresh: daily (consensus shifts as analysts publish)
  - Backfill: not applicable (consensus is point-in-time; begin storing daily snapshots from first run)
- **Join keys:** `ticker`
- **Raw tables:** `sp500_price_target_consensus`, `sp500_upgrades_downgrades`
- **JSON output schema:**

**Price Target Consensus** (expected_schema):
```json
[
  {
    "symbol": "string",
    "targetHigh": "number | null",
    "targetLow": "number | null",
    "targetConsensus": "number | null",
    "targetMedian": "number | null"
  }
]
```

**Upgrades/Downgrades Consensus** (expected_schema):
```json
[
  {
    "symbol": "string",
    "strongBuy": "integer",
    "buy": "integer",
    "hold": "integer",
    "sell": "integer",
    "strongSell": "integer",
    "consensus": "string (Strong Buy|Buy|Hold|Sell|Strong Sell)"
  }
]
```

Validate by sampling a real API response during implementation.

---

## Tier 1 — Dividends, Splits & Symbol Changes

- **What it is:** Historical and upcoming dividend declarations (ex-date, pay date, amount), stock split events (ratio, execution date), and ticker symbol changes.
- **Why Phase 0.5 needs it:** Dividends affect total return calculations and yield-based scoring. Splits cause price discontinuities that can corrupt technical indicators if not flagged. Symbol changes break ticker-based joins across the pipeline.
- **Primary Source:** FMP — provides per-ticker dividend history and split history via clean endpoints that fit the existing `_fetch_batch()` pattern; Polygon also offers dividends/splits but FMP's per-ticker structure is more consistent with existing FMP job conventions.
- **Endpoint(s):**
  - `GET /stable/stock-dividend?symbol={ticker}&apikey={key}` (per-ticker dividend history)
  - `GET /stable/historical-stock-split?symbol={ticker}&apikey={key}` (per-ticker split history)
- **Request pattern:**
  - Method: GET
  - Per-ticker; use `_fetch_batch()` across S&P 500 universe
  - Rate limit: use repo standard FMP rate-limit guards (0.1s/req)
- **Grain & cadence:**
  - Dividends grain: (ticker, date) — one row per ex-dividend date per ticker
  - Splits grain: (ticker, date) — one row per split execution date per ticker
  - Refresh: daily (picks up new declarations)
  - Backfill: 5 years for dividend yield trend; 10 years for splits (rare events)
- **Join keys:** `ticker`, `date`
- **Raw tables:** `sp500_dividends`, `sp500_splits`
- **Symbol changes:** No reliable Polygon/FMP endpoint for historical symbol changes. Best alternative: track membership changes via the Wikipedia S&P 500 constituent table already ingested in `sp500_tickers_lookup`, supplemented by manual mapping when detected.
- **JSON output schema:**

**Dividends** (expected_schema):
```json
[
  {
    "symbol": "string",
    "date": "string (YYYY-MM-DD, ex-dividend date)",
    "adjDividend": "number",
    "dividend": "number",
    "recordDate": "string (YYYY-MM-DD) | null",
    "paymentDate": "string (YYYY-MM-DD) | null",
    "declarationDate": "string (YYYY-MM-DD) | null"
  }
]
```

**Splits** (expected_schema):
```json
[
  {
    "symbol": "string",
    "date": "string (YYYY-MM-DD)",
    "numerator": "number",
    "denominator": "number"
  }
]
```

Validate by sampling a real API response during implementation.

---

## Tier 2 — Benchmarks, Sector ETFs & VIX

- **What it is:** Daily OHLCV prices for benchmark indices (SPY, QQQ, IWM), sector ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLU, XLC, XLRE, XLB), and volatility proxy (VIXY or VXX).
- **Why Phase 0.5 needs it:** Enables relative-performance scoring (stock vs. sector vs. market), market regime detection (bull/bear/sideways), and risk-adjusted rankings. Without benchmarks, all scores are absolute and miss macro context.
- **Primary Source:** Polygon — reuses the existing `PolygonClient.fetch_stock_prices()` method with a fixed benchmark ticker list; no new client code needed.
- **Endpoint(s):**
  - `GET /v2/aggs/ticker/{symbol}/range/1/day/{date}/{date}?adjusted=true&sort=asc&apiKey={key}`
  - (Identical to existing daily prices endpoint)
- **Request pattern:**
  - Method: GET
  - Fixed list of ~15-20 symbols (not per S&P 500 ticker); pass benchmark list to existing `fetch_stock_prices()`
  - Rate limit: use repo standard Polygon rate-limit guards (0.8s/req); ~20 symbols x 0.8s = ~16s
- **Grain & cadence:**
  - Grain: (ticker, date) — one row per benchmark/ETF per day
  - Refresh: daily (same cadence as existing price DAG)
  - Backfill: 5 years for regime detection rolling windows
- **Join keys:** `ticker`, `date` (joined in dbt by date across stock and benchmark tables; no ticker-to-ticker join)
- **Raw table:** `sp500_benchmark_prices`
- **JSON output schema:** Identical to existing `sp500_stock_prices` schema:

```json
{
  "ticker": "string",
  "open": "number",
  "high": "number",
  "low": "number",
  "close": "number",
  "volume": "number",
  "vwap": "number",
  "transactions": "number",
  "date": "string (YYYY-MM-DD)",
  "extracted_at": "string (YYYY-MM-DD HH:MM:SS)"
}
```

---

## Tier 2 — Macro Rates Series

- **What it is:** Key macroeconomic interest rate series: Federal Funds Rate, 10-Year Treasury Yield, 2-Year Treasury Yield, 10Y-2Y spread (computed), and High-Yield OAS spread.
- **Why Phase 0.5 needs it:** Interest rates drive sector rotation (rate-sensitive sectors like financials, REITs, utilities) and risk appetite. The 10Y-2Y spread is a recession indicator. Without macro context, sector favorability scoring is impossible.
- **Primary Source:** No Polygon/FMP coverage. Best alternative: FRED (Federal Reserve Economic Data) API — free, authoritative, daily updates for all required series.
- **Endpoint(s):**
  - `GET https://api.stlouisfed.org/fred/series/observations?series_id={id}&api_key={key}&file_type=json&observation_start={date}&observation_end={date}`
  - Series IDs: `DFF` (Fed Funds), `DGS10` (10Y Treasury), `DGS2` (2Y Treasury), `BAMLH0A0HYM2` (HY OAS)
- **Request pattern:**
  - Method: GET
  - One request per series (4 requests total per day)
  - Rate limit: FRED allows 120 req/min; no special rate limiting needed
  - Requires free FRED API key (new env var: `FRED_API_KEY`)
- **Grain & cadence:**
  - Grain: (series_id, date) — one row per series per observation date
  - Refresh: daily (FRED publishes most series T+1)
  - Backfill: 5 years for regime classification
- **Join keys:** `date` (joined to stock data by date; no ticker join)
- **Raw table:** `sp500_macro_rates`
- **JSON output schema:**

```json
{
  "realtime_start": "string (YYYY-MM-DD)",
  "realtime_end": "string (YYYY-MM-DD)",
  "observation_start": "string (YYYY-MM-DD)",
  "observation_end": "string (YYYY-MM-DD)",
  "units": "string",
  "output_type": "integer",
  "file_type": "string",
  "order_by": "string",
  "sort_order": "string",
  "count": "integer",
  "offset": "integer",
  "limit": "integer",
  "observations": [
    {
      "realtime_start": "string (YYYY-MM-DD)",
      "realtime_end": "string (YYYY-MM-DD)",
      "date": "string (YYYY-MM-DD)",
      "value": "string (numeric or '.')"
    }
  ]
}
```

Note: FRED returns `value` as string; `"."` indicates missing data (weekends/holidays). Parse to float in the API client, coerce `"."` to `None`.

---

## Tier 2 — Short Interest

- **What it is:** Short interest as a percentage of float and days-to-cover ratio for each S&P 500 ticker, indicating bearish positioning and crowding risk.
- **Why Phase 0.5 needs it:** High short interest is both a risk signal (crowding, potential squeeze) and a contrarian buy signal when combined with positive catalysts. It adds a crowding dimension to risk overlays.
- **Primary Source:** No reliable free Polygon/FMP endpoint. FMP may offer short interest data on certain plan tiers but availability is inconsistent. Best alternative: FINRA short interest files (published bi-monthly, free but requires file parsing).
- **Endpoint(s):**
  - `GET /stable/short-interest?symbol={ticker}&apikey={key}` (FMP — test availability first)
- **Request pattern:**
  - Method: GET
  - Per-ticker; use `_fetch_batch()` if FMP endpoint is available
  - Rate limit: use repo standard FMP rate-limit guards (0.1s/req)
  - **Implementation note:** Test FMP endpoint availability first. If 403/404, deprioritize and revisit with FINRA file download approach.
- **Grain & cadence:**
  - Grain: (ticker, date) — one row per ticker per settlement date
  - Refresh: bi-monthly (FINRA publishes 2x/month); daily if FMP provides daily data
  - Backfill: 5 years for trend analysis
- **Join keys:** `ticker`, `date`
- **Raw table:** `sp500_short_interest`
- **JSON output schema** (expected_schema — FMP, if available):

```json
[
  {
    "symbol": "string",
    "date": "string (YYYY-MM-DD)",
    "shortInterest": "number",
    "shortInterestChangePercent": "number | null",
    "floatShort": "number | null",
    "daysToCover": "number | null"
  }
]
```

Validate by sampling a real API response during implementation. If endpoint returns 403/404, deprioritize and revisit with FINRA approach.

---

## Tier 2 — Options Implied Volatility Summary

- **What it is:** Daily implied volatility (IV) summary per ticker: 30-day IV, IV rank (percentile vs. 1-year range), and put/call ratio derived from options chain snapshots.
- **Why Phase 0.5 needs it:** IV is the market's forward-looking risk estimate. IV rank identifies when options are cheap or expensive relative to history, which serves as a risk/opportunity signal in the scoring model.
- **Primary Source:** Polygon — the `/v3/snapshot/options/{underlyingAsset}` endpoint returns current options chain with IV per contract; requires Polygon Options subscription (often separate from Basic stocks plan).
- **Endpoint(s):**
  - `GET /v3/snapshot/options/{underlyingAsset}?apiKey={key}` (full chain snapshot)
- **Request pattern:**
  - Method: GET
  - Per-ticker; use `_fetch_batch()` across S&P 500 universe
  - Rate limit: use repo standard Polygon rate-limit guards (0.8s/req)
  - **Implementation note:** Options snapshots return hundreds of contracts per ticker. The API client must aggregate to ATM IV, total volume, and open interest before returning the DataFrame. Do not load raw per-contract data to Snowflake.
- **Grain & cadence:**
  - Grain: (ticker, date) — one aggregated IV summary row per ticker per day
  - Refresh: daily (post-market)
  - Backfill: 1 year for IV rank percentile computation
- **Join keys:** `ticker`, `date`
- **Raw table:** `sp500_options_iv_summary`
- **JSON output schema** (expected_schema — aggregated from raw snapshot in API client):

```json
{
  "ticker": "string",
  "date": "string (YYYY-MM-DD)",
  "iv_30d": "number | null",
  "iv_rank_1y": "number | null",
  "put_call_ratio": "number | null",
  "total_call_volume": "number | null",
  "total_put_volume": "number | null",
  "total_call_oi": "number | null",
  "total_put_oi": "number | null",
  "extracted_at": "string (YYYY-MM-DD HH:MM:SS)"
}
```

Note: This is a derived/aggregated schema. The raw Polygon response contains per-contract data. Validate raw response shape and build aggregation logic during implementation.

---

## Tier 2 — Insider Trades & Institutional Holdings (13F)

- **What it is:** SEC Form 4 insider transactions (buys/sells by officers, directors, 10%+ holders) and quarterly 13F institutional holding snapshots showing large-fund positions.
- **Why Phase 0.5 needs it:** Insider buying is a strong bullish signal (insiders risk their own capital). Institutional ownership changes indicate smart-money conviction. Both add an ownership dimension to the scoring model.
- **Primary Source:** FMP — provides both insider trading and institutional holder endpoints with per-ticker access, fitting the existing `_fetch_batch()` pattern; SEC EDGAR is the raw source but requires complex filing parsing.
- **Endpoint(s):**
  - `GET /stable/insider-trading?symbol={ticker}&limit=100&apikey={key}`
  - `GET /stable/institutional-holder?symbol={ticker}&apikey={key}`
- **Request pattern:**
  - Method: GET
  - Per-ticker; use `_fetch_batch()` for each endpoint across S&P 500 universe
  - Rate limit: use repo standard FMP rate-limit guards (0.1s/req)
  - Note: 2 endpoints x ~500 tickers = ~1,000 requests per refresh (~1.7 min)
- **Grain & cadence:**
  - Insider trades grain: (ticker, filing_date, reporting_name, transaction_type) — one row per insider per transaction
  - Institutional holders grain: (ticker, holder, date_reported) — one row per holder per ticker per quarter
  - Refresh: daily for insider trades (SEC filings arrive continuously), quarterly for 13F
  - Backfill: 5 years for insider trade pattern analysis; 5 years for 13F trends
- **Join keys:** `ticker`
- **Raw tables:** `sp500_insider_trades`, `sp500_institutional_holders`
- **JSON output schema:**

**Insider Trades** (expected_schema):
```json
[
  {
    "symbol": "string",
    "filingDate": "string (YYYY-MM-DD)",
    "transactionDate": "string (YYYY-MM-DD)",
    "reportingName": "string",
    "transactionType": "string (P-Purchase|S-Sale|...)",
    "securitiesOwned": "number",
    "securitiesTransacted": "number",
    "price": "number | null",
    "typeOfOwner": "string (officer|director|10percent|...)",
    "link": "string (SEC filing URL)"
  }
]
```

**Institutional Holders** (expected_schema):
```json
[
  {
    "holder": "string",
    "shares": "number",
    "dateReported": "string (YYYY-MM-DD)",
    "change": "number",
    "changePercentage": "number | null"
  }
]
```

Validate by sampling a real API response during implementation.
