# Rule: Incremental & SCD Patterns

Defines incremental model conventions, watermark strategies, idempotency guarantees, and snapshot/SCD handling.

---

## Incremental Strategy: delete+insert

Every incremental model follows this exact pattern:

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'date']   -- or ['ticker', 'technical_date']
) }}

WITH source_data AS (
    SELECT * FROM {{ ref('upstream_model') }}
    {% if is_incremental() %}
    WHERE date >= (SELECT MAX(date) - INTERVAL 'N days' FROM {{ this }})
    {% endif %}
),

-- ... transformations ...

final AS (
    SELECT * FROM transformed
)

SELECT * FROM final
{% if is_incremental() %}
WHERE date >= (SELECT MAX(date) - INTERVAL 'M days' FROM {{ this }})
{% endif %}
```

Where:
- `N` = source lookback (wide, to satisfy window functions)
- `M` = output filter (narrow, to limit write volume; typically 3 days)

## Watermark Strategy

All watermarks reference `{{ this }}` (the target table):

```sql
(SELECT MAX(date) FROM {{ this }})
```

**Why MAX(date) from {{ this }}:**
- Self-referential: no external state dependency
- Idempotent: re-running after failure resumes from the correct point
- Gap-safe: the overlap window (3 days) covers weekends and market holidays

**NEVER use:**
- `current_date()` or `GETDATE()` as watermarks
- External variables or Airflow macros for watermarks
- Hardcoded date literals

## Idempotency Guarantee

`delete+insert` with `unique_key` ensures:

1. **First run**: `is_incremental()` returns FALSE → full table build
2. **Subsequent runs**: DELETE rows matching `unique_key` values in the incoming batch, then INSERT
3. **Re-runs**: Same output regardless of how many times executed (delete removes previous results first)

This means:
- Failed runs leave no partial state (Snowflake transaction semantics)
- Re-runs are safe and produce identical results
- No duplicate rows are possible for the same `unique_key` combination

## Late-Arriving Data Handling

The 3-day overlap window in output filters handles:
- Market holidays (e.g., prices missing for 1-2 days)
- API delays (Polygon data arrives T+1 for some endpoints)
- Timezone edge cases (Polygon timestamps in UTC, market closes at 4pm ET)

If data arrives more than 3 days late (unusual), a targeted backfill is needed:
```bash
dbt run --select int_sp500_daily_price_changes --full-refresh
```

## Full-Scan Exceptions

One model requires a full source scan on every incremental run:

**`int_sp500_price_returns`**
- Uses `FIRST_VALUE(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`
- Uses `MAX(close) OVER (...UNBOUNDED PRECEDING...)` for drawdown computation
- Cannot be windowed to a lookback because the cumulative return baseline is the FIRST ever price

The output filter still restricts inserts to the last 3 days, but the source CTE scans the full `stg_sp500_stock_prices` table.

**If this model becomes a performance bottleneck**, consider:
1. Materializing a separate `first_price_per_ticker` model (one-time, full refresh)
2. Joining to it instead of using FIRST_VALUE with unbounded preceding
3. This trades one full scan for a small lookup table + windowed scan

## Lookback Window Reference

| Model | unique_key | Source Lookback | Output Filter | Full Scan? |
|-------|-----------|----------------|---------------|-----------|
| `int_sp500_daily_price_changes` | [ticker, date] | 4 days | 3 days | No |
| `int_sp500_technical_indicators` | [ticker, date] | 300 days (prices), 3 days (RSI/MACD) | 3 days | No |
| `int_sp500_price_returns` | [ticker, date] | FULL | 3 days | Yes |
| `mart_sp500_technical_scores` | [ticker, date] | 40 days | 3 days | No |
| `mart_sp500_composite_scores` | [ticker, technical_date] | 3 days | — | No |
| `mart_sp500_industry_scores` | [ticker, technical_date] | 3 days | — | No |
| `mart_sp500_price_performance` | [ticker, date] | 7 days | — | No |

## SCD / Snapshot Patterns

### Type 2 Snapshot: S&P 500 Universe

```
stg_sp500_tickers_snapshot
    Grain: (ticker, as_of_date)
    One row per ticker per day the lookup was run.
    Captures universe membership over time.
```

```
stg_sp500_tickers_current
    Grain: (ticker)
    Filters to MAX(as_of_date) from snapshot.
    Represents the CURRENT S&P 500 membership.
```

This is a manual SCD2 pattern: Python writes a full snapshot daily, and the staging view provides both the history (snapshot) and the current state (current).

### Why Not dbt Snapshots?

The project does not use `dbt snapshot` because:
1. The Wikipedia scraper already captures a dated snapshot per run
2. The raw table `sp500_tickers_lookup` already contains (ticker, date) grain
3. A simple max-date filter achieves the "current" view without snapshot overhead

## Non-Incremental Models

Two models are full-refresh tables (no incremental logic):

| Model | Why Full Refresh |
|-------|-----------------|
| `int_sp500_fundamentals` | Annual data; small volume (~500 tickers × 5 years); YoY LAG requires full history per ticker |
| `mart_sp500_fundamental_scores` | Derived directly from fundamentals; same small volume; config block is commented out |

These models rebuild completely on every `dbt run`. This is acceptable because:
- ~2,500 rows (500 tickers × 5 fiscal years) is trivial for Snowflake
- Annual data changes infrequently (only when new fiscal year filings appear)

## Adding a New Incremental Model — Checklist

1. Define the grain and document it in this file and `data-contracts.md`
2. Set `unique_key` in `{{ config() }}` matching the grain columns
3. Determine the widest window function and calculate the source lookback
4. Add the double-filter pattern (source CTE + output WHERE)
5. Add `not_null` test on grain columns in the layer YAML file
6. Add a grain uniqueness test (e.g., `dbt_utils.unique_combination_of_columns`)
7. Verify idempotency: run twice and confirm identical row counts
