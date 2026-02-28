# Rule: Warehouse Performance

Snowflake-specific performance rules governing incremental strategies, scan minimization, and cost controls.

---

## Incremental Strategy: delete+insert

All incremental models in this project use `delete+insert` exclusively. Never use `merge`.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['ticker', 'date']
) }}
```

**Why delete+insert over merge:**
- Simpler semantics (delete matching rows, then insert)
- No risk of partial updates
- Idempotent: re-running produces identical results
- Better performance for batch-oriented daily loads

## Double-Filter Pattern

Incremental models in this project apply TWO filters:

1. **Source CTE filter** — fetches a wider lookback from upstream to satisfy window functions
2. **Final output filter** — restricts the output to only the new/updated rows

```sql
-- Source CTE: wide lookback for window functions
select * from {{ ref('stg_sp500_stock_prices') }}
{% if is_incremental() %}
where date >= (select max(date) - interval '300 days' from {{ this }})
{% endif %}

-- ... window function computations ...

-- Final output: narrow filter for actual insert
select * from joined
{% if is_incremental() %}
where date >= (select max(date) - interval '3 days' from {{ this }})
{% endif %}
```

**NEVER remove the source CTE filter** — it prevents full table scans on multi-year data.
**NEVER make the output filter wider than necessary** — it controls write volume.

## Lookback Window Sizing

Each lookback is precisely sized to the widest window function in the model:

| Model | Widest Window Function | Required Rows | Calendar Day Buffer |
|-------|----------------------|---------------|-------------------|
| `int_sp500_daily_price_changes` | `LAG(close, 1)` | 1 row | 4 days |
| `int_sp500_technical_indicators` | `AVG(close) OVER (ROWS 199 PRECEDING)` | 200 rows | 300 days |
| `int_sp500_price_returns` | `FIRST_VALUE()`, `MAX()` UNBOUNDED PRECEDING | ALL rows | FULL SCAN |
| `mart_sp500_technical_scores` | `LAG(close, 20)` | 20 rows | 40 days |
| `mart_sp500_composite_scores` | Direct ref, no window | 0 | 3 days (overlap) |
| `mart_sp500_industry_scores` | Direct ref, no window | 0 | 3 days (overlap) |
| `mart_sp500_price_performance` | Direct ref, no window | 0 | 7 days (stability) |

**Rule:** When adding a new window function, recalculate the required lookback:
- `trading_days_needed = window_size + buffer`
- `calendar_days = trading_days_needed * 1.5` (accounts for weekends/holidays)

## CLUSTER BY (Backfill Tables Only)

Only backfill tables use `CLUSTER BY` because they have multi-year data volumes:

```python
# In ingest_polygon_prices_backfill.py
create_table_sql = f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    ...
) CLUSTER BY (date, ticker)
"""
```

Daily tables do not need clustering — their data volume is small per partition.

**NEVER add CLUSTER BY to daily-load tables** — the overhead exceeds the benefit.

## Scan Minimization Rules

1. **Always filter in the source CTE** — never scan the entire upstream table when only recent data is needed
2. **Use `{{ this }}` for watermarks** — reference the target table's max date, not a hardcoded value
3. **Avoid `SELECT *` in intermediate CTEs** — project only the columns needed for downstream computation
4. **LEFT JOIN over CROSS JOIN** — all dimension enrichment uses LEFT JOIN on ticker; never generate cartesian products
5. **Full scans are documented** — `int_sp500_price_returns` is the only model with a justified full scan (cumulative return from first available date)

## VARIANT Column Handling

News articles contain JSON array fields (tickers, keywords) stored as Snowflake VARIANT:

```python
# In snowflake_loader.py — VARIANT columns handled at load time
# parse_json() converts JSON strings to native VARIANT
INSERT INTO {table_name} (..., tickers, keywords)
SELECT ..., parse_json(column3), parse_json(column4) FROM ...
```

**NEVER handle VARIANT parsing in dbt** — it belongs in the loader layer.

## Cost Controls

| Setting | Value | Location | Purpose |
|---------|-------|----------|---------|
| `threads: 1` | 1 | profiles.yml | Single concurrent query (shared warehouse) |
| `warehouse: COMPUTE_WH` | Shared | profiles.yml | Shared compute, no dedicated warehouse |
| `query_tag` | `{{ env_var('STUDENT_SCHEMA') }}` | profiles.yml | Cost attribution per student |
| `client_session_keep_alive: False` | False | profiles.yml | Release connections promptly |
| Rate limiting | 0.8s/req (Polygon), 0.1s/req (FMP) | api_clients/ | Respect API limits, avoid 429s |

## Anti-Patterns to Avoid

1. **Never use `merge` strategy** — this project standardizes on delete+insert
2. **Never hardcode dates in incremental filters** — always use `{{ this }}` watermarks
3. **Never add ORDER BY in intermediate CTEs** — Snowflake optimizes this away but it adds parse cost
4. **Never use `QUALIFY` without a preceding window** — Snowflake-specific, but ensure filter logic is in WHERE
5. **Never create temporary tables in dbt** — use CTEs instead; Snowflake materializes CTEs efficiently
6. **Never join two incremental models without aligning their lookback windows** — ensure both sides have overlapping date ranges
