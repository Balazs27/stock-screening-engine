# Detailed Index — Stock Screening Engine

Deep structural index covering grains, materializations, dependencies, scoring logic, and semantic definitions.

---

## dbt Model Dependency Graph

```
SOURCES (RAW)
├── sp500_stock_prices ──→ stg_sp500_stock_prices
├── sp500_rsi ──→ stg_sp500_rsi
├── sp500_macd ──→ stg_sp500_macd
├── sp500_news ──→ stg_sp500_news
├── sp500_income_statements ──→ stg_fmp_income_statement
├── sp500_balance_sheets ──→ stg_fmp_balance_sheet
├── sp500_cash_flow_statements ──→ stg_fmp_cash_flow
├── sp500_fmp_news ──→ stg_fmp_news
└── sp500_tickers_lookup ──→ stg_sp500_tickers_snapshot ──→ stg_sp500_tickers_current

STAGING → INTERMEDIATE
stg_sp500_stock_prices ──→ int_sp500_daily_price_changes
stg_sp500_stock_prices ──→ int_sp500_technical_indicators
stg_sp500_stock_prices ──→ int_sp500_price_returns
stg_sp500_rsi ──→ int_sp500_technical_indicators
stg_sp500_macd ──→ int_sp500_technical_indicators
stg_fmp_income_statement ──→ int_sp500_fundamentals
stg_fmp_balance_sheet ──→ int_sp500_fundamentals
stg_fmp_cash_flow ──→ int_sp500_fundamentals

STAGING → DIMENSIONS
stg_sp500_tickers_current ──→ dim_sp500_companies_current

INTERMEDIATE + DIMENSIONS → MARTS
int_sp500_technical_indicators ──→ mart_sp500_technical_scores
int_sp500_fundamentals ──→ mart_sp500_fundamental_scores
mart_sp500_technical_scores + mart_sp500_fundamental_scores ──→ mart_sp500_composite_scores
mart_sp500_composite_scores + dim_sp500_companies_current ──→ mart_sp500_industry_scores
int_sp500_price_returns + dim_sp500_companies_current ──→ mart_sp500_price_performance
```

---

## dbt Model Details

### Staging Layer (All Views)

| Model | Grain | Source | Upstream Refs | Downstream Refs | Notes |
|-------|-------|--------|--------------|-----------------|-------|
| `stg_sp500_stock_prices` | (ticker, date) | `sp500_stock_prices` | — | int_daily_price_changes, int_technical_indicators, int_price_returns | OHLCV + vwap + transactions |
| `stg_sp500_rsi` | (ticker, date) | `sp500_rsi` | — | int_technical_indicators | RSI-14 daily |
| `stg_sp500_macd` | (ticker, date) | `sp500_macd` | — | int_technical_indicators | MACD(12,26,9) daily |
| `stg_sp500_news` | (ticker, article_id, date) | `sp500_news` | — | (none currently) | VARIANT tickers/keywords |
| `stg_fmp_income_statement` | (ticker, date, period) | `sp500_income_statements` | — | int_fundamentals | 45+ fields, FY only used downstream |
| `stg_fmp_balance_sheet` | (ticker, date, period) | `sp500_balance_sheets` | — | int_fundamentals | 60+ fields |
| `stg_fmp_cash_flow` | (ticker, date, period) | `sp500_cash_flow_statements` | — | int_fundamentals | 45+ fields |
| `stg_fmp_news` | (ticker, date, article_url) | `sp500_fmp_news` | — | (none currently) | Experimental |
| `stg_sp500_tickers_snapshot` | (ticker, as_of_date) | `sp500_tickers_lookup` | — | stg_sp500_tickers_current | Daily snapshot of S&P 500 universe |
| `stg_sp500_tickers_current` | (ticker) | — | stg_sp500_tickers_snapshot | dim_sp500_companies_current | Latest-date filter, unique on ticker |

### Intermediate Layer

| Model | Grain | Materialization | Incremental Strategy | Lookback Window | Key Computations |
|-------|-------|----------------|---------------------|-----------------|-----------------|
| `int_sp500_daily_price_changes` | (ticker, date) | incremental | delete+insert | Source: 4d, Output: 3d | `LAG(close)` for daily change |
| `int_sp500_technical_indicators` | (ticker, date) | incremental | delete+insert | Source: 300d (SMA-200), RSI/MACD: 3d, Output: 3d | SMA-20/50/200 + RSI + MACD join |
| `int_sp500_price_returns` | (ticker, date) | incremental | delete+insert | Source: FULL SCAN (FIRST_VALUE + MAX unbounded), Output: 3d | daily_return, cumulative_return, rolling_30d/90d/1y_return, rolling_30d_volatility, drawdown_pct |
| `int_sp500_fundamentals` | (ticker, date) | table (full refresh) | N/A | N/A | 3-statement INNER JOIN on (ticker, date, fiscal_year), 15+ derived ratios, 5 YoY growth metrics |

### Dimension Layer

| Model | Grain | Materialization | Key Columns | Tests |
|-------|-------|----------------|-------------|-------|
| `dim_sp500_companies_current` | (ticker) | table | ticker, company_name, sector, industry, location, cik, founded_year | unique(ticker), not_null(ticker) |

### Mart Layer

| Model | Grain | Materialization | Incremental Strategy | Lookback | Unique Key | Score Range |
|-------|-------|----------------|---------------------|----------|------------|-------------|
| `mart_sp500_technical_scores` | (ticker, date) | incremental | delete+insert | Source: 40d, Output: 3d | [ticker, date] | 0-100 |
| `mart_sp500_fundamental_scores` | (ticker, date) | table | N/A | N/A | N/A | 0-100 |
| `mart_sp500_composite_scores` | (ticker, technical_date) | incremental | delete+insert | 3d | [ticker, technical_date] | 0-100 per variant |
| `mart_sp500_industry_scores` | (ticker, technical_date) | incremental | delete+insert | 3d | [ticker, technical_date] | Inherits from composite |
| `mart_sp500_price_performance` | (ticker, date) | incremental | delete+insert | 7d | [ticker, date] | N/A (returns/pcts) |

---

## Scoring Architecture

### Technical Score (0-100) — `mart_sp500_technical_scores`

| Component | Max Points | Signal | Logic |
|-----------|-----------|--------|-------|
| Trend Confirmation | 40 | SMA alignment | 40 if close > SMA-20/50/200; tiered down to 5 |
| Momentum Quality | 30 | RSI regime | 30 if RSI 50-70 (bullish); tiered by RSI bucket |
| Price Action | 20 | 20-day % change | 20 if >10% gain; tiered down to 0 |
| MACD Signal | 10 | MACD vs signal line | 10 if MACD > signal AND >0; tiered down to 3 |

### Fundamental Score (0-100) — `mart_sp500_fundamental_scores`

| Component | Max Points | Signal | Logic |
|-----------|-----------|--------|-------|
| Profitability Quality | 25 | Margins + ROE | Gross/operating/net margin tiers (15pts) + ROE tiers (10pts) |
| Growth Momentum | 30 | YoY growth | Revenue YoY (10pts) + EPS YoY (10pts) + FCF YoY (10pts) |
| Financial Health | 25 | Balance sheet | Current ratio (10pts) + D/E ratio (10pts) + FCF margin (5pts) |
| Cash Quality | 20 | FCF vs NI | FCF-to-NI ratio (15pts) + FCF margin (5pts) |

### Composite Score (0-100) — `mart_sp500_composite_scores`

| Variant | Technical Weight | Fundamental Weight | Use Case |
|---------|-----------------|-------------------|----------|
| `composite_score_equal` | 50% | 50% | Default balanced screening |
| `composite_score_technical_bias` | 60% | 40% | Trending/momentum markets |
| `composite_score_fundamental_bias` | 40% | 60% | Volatile/uncertain markets |

Fundamental scores are forward-filled: each daily technical score is paired with the most recent fiscal-year fundamental score via `BETWEEN fiscal_year_start_date AND fiscal_year_end_date`.

---

## Incremental Lookback Reference

| Model | Source Lookback | Output Filter | Why |
|-------|----------------|---------------|-----|
| `int_sp500_daily_price_changes` | `max(date) - 4 days` | `max(date) - 3 days` | LAG(1) needs 1 extra day |
| `int_sp500_technical_indicators` | `max(date) - 300 days` (prices) / `- 3 days` (RSI/MACD) | `max(date) - 3 days` | SMA-200 needs 199 preceding rows; 300 calendar days covers ~210 trading days |
| `int_sp500_price_returns` | FULL SCAN | `max(date) - 3 days` | FIRST_VALUE + MAX UNBOUNDED PRECEDING require complete history |
| `mart_sp500_technical_scores` | `max(date) - 40 days` | `max(date) - 3 days` | LAG(close, 20) needs 20 trading days buffer |
| `mart_sp500_composite_scores` | `max(technical_date) - 3 days` | N/A (output = source) | Direct overlay on latest technical scores |
| `mart_sp500_industry_scores` | `max(technical_date) - 3 days` | N/A | Direct join on latest composite scores |
| `mart_sp500_price_performance` | `max(date) - 7 days` | N/A | 7-day lookback for return recalculation stability |

---

## Airflow DAG Dependency Graph

```
                    sp500_lookup (root, @daily)
                           │
            ┌──────────────┼──────────────┬──────────────┬──────────────┐
            ▼              ▼              ▼              ▼              ▼
    polygon_daily    polygon_daily   polygon_daily  polygon_daily   fmp_*_dag(s)
      _prices          _rsi           _macd          _news         (4 FMP DAGs)
            │              │              │              │
            └──────────────┴──────────────┴──────────────┘
                                    │
                    stock_screening_dbt_daily (Cosmos)
                    [waits for 5 sensors: sp500_lookup,
                     polygon_prices, polygon_rsi,
                     polygon_macd, polygon_news]
                                    │
                         dbt build (all models + tests)

Backfill DAGs (schedule=None, manual trigger):
    polygon_prices_backfill
    polygon_rsi_backfill
    polygon_macd_backfill
    polygon_news_backfill
```

Note: FMP DAGs run daily but are NOT gated by the dbt Cosmos DAG (commented out in `DAILY_ETL_DEPENDENCIES`). This is intentional because FMP data is annual.

---

## Semantic Layer Models

### Exposed to MCP (5 models)

| Semantic Name | Snowflake Table | Dimensions | Measures | Primary Use |
|--------------|-----------------|------------|----------|-------------|
| `technical_scores` | `mart_sp500_technical_scores` | ticker, date | avg/max/min/std technical_score, avg trend/momentum/price_action/macd scores, ticker_count | Entry/exit timing, momentum screening |
| `fundamental_scores` | `mart_sp500_fundamental_scores` | ticker, date, fiscal_year | avg/max/min/std fundamentals_score, avg profitability/growth/health/cash scores, margin metrics | Quality investing, value screening |
| `composite_scores` | `mart_sp500_composite_scores` | ticker, technical_date, fiscal_year | avg/max/min/std composite (3 variants), avg technical/fundamental raw scores, counts | Holistic ranking, portfolio construction |
| `industry_scores` | `mart_sp500_industry_scores` | ticker, company_name, sector, industry, technical_date, fiscal_year | Same as composite + sector_count | Sector rotation, peer comparison |
| `price_performance` | `mart_sp500_price_performance` | ticker, company_name, sector, industry, date | avg daily/cumulative/rolling returns, volatility, drawdown, risk-adjusted return, positive_return_rate | Performance attribution, risk screening |

---

## Test Coverage Matrix

### Generic Schema Tests (YAML)

| Model | not_null | unique | Other |
|-------|---------|--------|-------|
| stg_sp500_stock_prices | ticker | — | — |
| stg_sp500_rsi | ticker | — | — |
| stg_sp500_macd | ticker | — | — |
| stg_sp500_news | ticker | — | — |
| stg_fmp_income_statement | ticker | — | — |
| stg_fmp_balance_sheet | ticker | — | — |
| stg_fmp_cash_flow | ticker | — | — |
| stg_fmp_news | ticker | — | — |
| stg_sp500_tickers_snapshot | ticker | — | — |
| stg_sp500_tickers_current | ticker | ticker | — |
| int_sp500_daily_price_changes | ticker | — | — |
| int_sp500_technical_indicators | ticker | — | — |
| int_sp500_fundamentals | ticker | — | — |
| int_sp500_price_returns | ticker | — | — |
| dim_sp500_companies_current | ticker | ticker | — |
| mart_sp500_technical_scores | ticker, technical_score | — | — |
| mart_sp500_fundamental_scores | ticker, fundamentals_score | — | — |
| mart_sp500_composite_scores | ticker | — | — |
| mart_sp500_price_performance | ticker | — | — |

### Custom Singular Tests

| Test File | Target Model | Validates | Risk Covered |
|-----------|-------------|-----------|--------------|
| `assert_technical_score_in_range.sql` | mart_sp500_technical_scores | 0 <= score <= 100, not null | Score overflow from additive component logic |
| `assert_fundamentals_score_in_range.sql` | mart_sp500_fundamental_scores | 0 <= score <= 100, not null | Score overflow from additive component logic |

### Coverage Gaps

| Gap | Risk | Recommended Fix |
|-----|------|----------------|
| No composite score range test | Composite could exceed 100 if weighting math drifts | Add `assert_composite_score_in_range.sql` |
| No source freshness checks | Stale raw data processed silently | Add `loaded_at_field` + `warn_after`/`error_after` to `_sources.yml` |
| No grain uniqueness tests on intermediate/mart models | Silent duplicates from broken incremental logic | Add `dbt_utils.unique_combination_of_columns` |
| No referential integrity tests | Orphan tickers (in marts but not in dimension) | Add `relationships` test on ticker between marts and dim |
| `dbt_expectations` installed but unused | Package bloat without value | Either add expectations tests or remove package |
| No row-count or anomaly detection | Sudden data volume changes go unnoticed | Add `dbt_expectations.expect_table_row_count_to_be_between` |
