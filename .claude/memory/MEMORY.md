# Operational Memory — Stock Screening Engine

Long-term learnings and incident resolutions. Organized by symptom for fast retrieval.

---

## Entry 1: Wikipedia 403 Rate Limiting

**Symptom:** Wikipedia scraper returns HTTP 403 on rapid successive calls during S&P 500 lookup.

**Cause:** Wikipedia rate-limits aggressive crawlers. Rapid successive requests from the same IP trigger 403 Forbidden.

**Solution:** Added retry-with-exponential-backoff to `wikipedia_client.py`. Retries up to 3 times with increasing delay.

**Red Flags:** Any new Wikipedia endpoint will hit the same rate limits. Do not parallelize Wikipedia requests.

**Preventative Guardrail:** All Wikipedia fetches must go through `wikipedia_client.py` which has built-in retry logic.

---

## Entry 2: Polygon News VARIANT Columns

**Symptom:** News articles have `tickers` and `keywords` fields that are JSON arrays, which fail on standard Snowflake INSERT.

**Cause:** Snowflake requires `parse_json()` to convert JSON strings to native VARIANT type. Standard pandas-to-Snowflake write path does not handle this.

**Solution:** Created separate loader methods: `overwrite_partition_with_variants()` and `overwrite_date_range_with_variants()` in `snowflake_loader.py`. These use INSERT ... SELECT with `parse_json()` column wrappers.

**Red Flags:** Any new data source with JSON array or nested JSON fields will need the VARIANT loader path.

**Preventative Guardrail:** Handle VARIANT parsing at the loader level, NEVER in dbt. Check if new API response fields contain arrays or nested objects before choosing the loader method.

---

## Entry 3: Airflow Import Conventions

**Symptom:** DAGs fail to parse when using deprecated Airflow operator imports.

**Cause:** Airflow 3.x (Astronomer Runtime 3.1) uses `airflow.providers.standard.*` namespace. The older `airflow.operators.*` imports are deprecated.

**Solution:** All DAGs use `from airflow.providers.standard.operators.python import PythonOperator` and `from airflow.providers.standard.sensors.external_task import ExternalTaskSensor`.

**Red Flags:** Any new DAG must use the `airflow.providers.standard.*` import path. The `airflow.operators.*` path will cause import errors in the Astronomer test suite.

**Preventative Guardrail:** Before creating a new DAG, check existing DAGs for the correct import pattern. The dbt Cosmos DAG uses `from airflow.decorators import dag` (decorator style).

---

## Entry 4: SMA-200 Incremental Lookback

**Symptom:** SMA-200 values are incorrect after incremental run — they compute on a truncated window.

**Cause:** `int_sp500_technical_indicators` had too small a lookback window. SMA-200 requires 199 preceding rows. With weekends/holidays, 200 calendar days only covers ~140 trading days.

**Solution:** Set source CTE lookback to 300 calendar days (`max(date) - interval '300 days'`), which covers ~210 trading days — sufficient for SMA-200 with buffer.

**Red Flags:** Any new window function with a wide lookback needs its lookback calculated as: `calendar_days = trading_days_needed * 1.5`.

**Preventative Guardrail:** See `@.claude/rules/warehouse-performance.md` — Lookback Window Sizing table.

---

## Entry 5: Composite Score Fiscal-Year Forward-Fill

**Symptom:** Many rows in `mart_sp500_composite_scores` have NULL fundamentals_score.

**Cause:** The JOIN condition uses `BETWEEN fiscal_year_start_date AND fiscal_year_end_date`. The fiscal_year_start_date is derived via `LAG(fiscal_year_end_date)`, which returns NULL for the earliest fiscal year (no prior year to LAG from).

**Solution:** This is a known edge case. The first available fiscal year for each ticker will have NULL `fiscal_year_start_date`, causing those daily technical rows to not match any fundamental period. This is acceptable for the first year of data.

**Red Flags:** If the fundamentals table is refreshed and a new oldest year appears, the NULL window shifts. Verify composite JOIN after fundamentals backfills.

---

## Entry 6: FMP Annual vs Daily Cadence

**Symptom:** FMP DAGs run daily but only fetch annual data — redundant API calls.

**Cause:** Design choice: FMP DAGs are scheduled `@daily` but fetch `period="annual"` data. Most days, the fetched data is identical to what already exists.

**Solution:** The `overwrite_date_range()` loader strategy is idempotent — re-inserting the same annual data is harmless. The daily schedule ensures new annual filings are picked up within 24 hours of publication.

**Red Flags:** FMP rate limits (~600 req/min) should not be exceeded even with daily runs for 500 tickers. But if FMP adds stricter limits, consider reducing to weekly schedule.

---

*Add new entries below this line following the same template.*
