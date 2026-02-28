# Rule: Data Contracts

Defines canonical grains, primary keys, dimensional modeling conventions, and schema standards.

---

## Grain Declarations

Every model MUST have a documented grain. The grain defines the meaning of one row.

| Model | Grain | Meaning of One Row |
|-------|-------|--------------------|
| `stg_sp500_stock_prices` | (ticker, date) | One day's OHLCV for one stock |
| `stg_sp500_rsi` | (ticker, date) | One day's RSI-14 for one stock |
| `stg_sp500_macd` | (ticker, date) | One day's MACD(12,26,9) for one stock |
| `stg_sp500_news` | (ticker, article_id, date) | One article for one stock on one day |
| `stg_fmp_income_statement` | (ticker, date, period) | One filing for one stock for one period |
| `stg_fmp_balance_sheet` | (ticker, date, period) | One filing for one stock for one period |
| `stg_fmp_cash_flow` | (ticker, date, period) | One filing for one stock for one period |
| `stg_sp500_tickers_snapshot` | (ticker, as_of_date) | One stock's membership on one day |
| `stg_sp500_tickers_current` | (ticker) | One stock in the current S&P 500 |
| `int_sp500_daily_price_changes` | (ticker, date) | One day's price change for one stock |
| `int_sp500_technical_indicators` | (ticker, date) | One day's combined indicators for one stock |
| `int_sp500_price_returns` | (ticker, date) | One day's return metrics for one stock |
| `int_sp500_fundamentals` | (ticker, date) | One fiscal year's fundamentals for one stock |
| `dim_sp500_companies_current` | (ticker) | One company in the current S&P 500 |
| `mart_sp500_technical_scores` | (ticker, date) | One day's technical score for one stock |
| `mart_sp500_fundamental_scores` | (ticker, date) | One fiscal year's fundamental score for one stock |
| `mart_sp500_composite_scores` | (ticker, technical_date) | One day's blended score for one stock |
| `mart_sp500_industry_scores` | (ticker, technical_date) | One day's enriched score for one stock |
| `mart_sp500_price_performance` | (ticker, date) | One day's performance metrics for one stock |

## Primary Key Enforcement

### Incremental Models
Grain uniqueness is enforced via `unique_key` in the `{{ config() }}` block:
```sql
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'date']
) }}
```

### Dimension Models
Grain uniqueness is enforced via `unique` + `not_null` tests in YAML:
```yaml
columns:
  - name: ticker
    data_tests:
      - unique
      - not_null
```

### RAW Tables (Python Loader)
Primary keys declared in `CREATE TABLE IF NOT EXISTS` statements within job files. Not enforced by Snowflake (informational only) but used by loaders for delete-before-insert idempotency.

## Dimensional Modeling Conventions

### Conforming Dimension
`dim_sp500_companies_current` is the single conforming dimension. All mart models join to it via `ticker` for enrichment with company_name, sector, industry.

### Star Schema Pattern
```
dim_sp500_companies_current (ticker)
        │
        ├── mart_sp500_industry_scores      (LEFT JOIN on ticker)
        ├── mart_sp500_price_performance    (LEFT JOIN on ticker)
        └── (future marts join here)
```

### Fact-to-Fact Join
`mart_sp500_composite_scores` joins two fact tables:
- `mart_sp500_technical_scores` (daily grain)
- `mart_sp500_fundamental_scores` (annual grain, forward-filled via BETWEEN date range)

This is a deliberate design choice to align daily technical with annual fundamental data.

## Column Naming Standards

| Convention | Example | Enforcement |
|-----------|---------|-------------|
| Snowflake stores UPPERCASE | `TICKER`, `DATE`, `CLOSE` | Automatic (Snowflake default) |
| dbt SQL uses lowercase | `ticker`, `date`, `close` | Convention |
| snake_case for all columns | `technical_score`, `rolling_30d_return` | Convention |
| Score columns: `{domain}_score` | `technical_score`, `fundamentals_score` | Convention |
| Component scores: `{component}_score` | `trend_score`, `momentum_score`, `profitability_score` | Convention |
| Return columns: `{period}_return` | `daily_return`, `rolling_30d_return` | Convention |
| Ratio columns: `{metric}_{basis}` | `debt_to_equity`, `fcf_to_net_income` | Convention |
| YoY growth columns: `{metric}_growth_yoy` | `revenue_growth_yoy`, `eps_growth_yoy` | Convention |

## Score Range Contracts

ALL score columns MUST be in the range [0, 100]:
- `technical_score` = trend(0-40) + momentum(0-30) + price_action(0-20) + MACD(0-10)
- `fundamentals_score` = profitability(0-25) + growth(0-30) + health(0-25) + cash(0-20)
- `composite_score_*` = weighted sum of technical + fundamental, both 0-100

Enforced by custom singular tests: `assert_technical_score_in_range.sql`, `assert_fundamentals_score_in_range.sql`.

## YAML Schema Standards

Every model MUST have a corresponding `.yml` entry with:
1. `description` — one-sentence purpose
2. At minimum, `not_null` test on the grain key column(s)
3. For dimension tables: `unique` test on the natural key
4. For score columns: `not_null` test

YAML files are organized by layer:
- `stg_{source}.yml` per source system
- `int.yml` for all intermediate models
- `dim.yml` for all dimensions
- `mart.yml` for all marts
