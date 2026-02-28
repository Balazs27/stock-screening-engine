# Rule: Data Quality & Observability

Defines dbt test strategy, freshness checks, alerting conventions, and what constitutes a stop-the-line failure.

---

## Test Tiers

### Tier 1: Schema Tests (YAML — runs on every `dbt build`)

Defined in `.yml` files alongside models. Current coverage:

| Test | Applied To | Purpose |
|------|-----------|---------|
| `not_null` | `ticker` on every model | Prevents null grain keys from propagating |
| `unique` | `ticker` on `stg_sp500_tickers_current`, `dim_sp500_companies_current` | Enforces current-state dimension uniqueness |
| `not_null` | `technical_score` on `mart_sp500_technical_scores` | Score column completeness |
| `not_null` | `fundamentals_score` on `mart_sp500_fundamental_scores` | Score column completeness |

### Tier 2: Custom Singular Tests (SQL — runs on every `dbt build`)

Located in `dbt_project/tests/`:

| Test | Target | Logic | Risk Covered |
|------|--------|-------|-------------|
| `assert_technical_score_in_range.sql` | mart_sp500_technical_scores | `WHERE score < 0 OR score > 100 OR score IS NULL` | Score overflow from additive components |
| `assert_fundamentals_score_in_range.sql` | mart_sp500_fundamental_scores | `WHERE score < 0 OR score > 100 OR score IS NULL` | Score overflow from additive components |

Pattern for new score range tests:
```sql
-- Test passes when 0 rows returned
SELECT ticker, date, {score_column}
FROM {{ ref('{model_name}') }}
WHERE {score_column} < 0
   OR {score_column} > 100
   OR {score_column} IS NULL
```

### Tier 3: dbt Packages (Available but Underused)

Installed packages with testing capabilities:
- `dbt_utils 1.1.1` — `unique_combination_of_columns`, `not_null_proportion`, `at_least_one`
- `dbt_expectations 0.10.3` — `expect_column_values_to_be_between`, `expect_table_row_count_to_be_between`, `expect_column_to_exist`
- `codegen 0.12.1` — schema/test generation helpers

**Current state: these packages are installed but NO tests from them are actively used.**

## Test Execution

Tests run as part of the Cosmos dbt DAG:
- `DbtTaskGroup` with default `TestBehavior.AFTER_EACH` renders each model + its tests as Airflow tasks
- A test failure on model X blocks downstream models that depend on X
- Test failures surface as Airflow task failures in the dbt task group

## Freshness Monitoring

**Current state: NO source freshness checks are configured.**

Source freshness should be added to `_sources.yml` files:
```yaml
sources:
  - name: balazsillovai30823
    freshness:
      warn_after: { count: 2, period: day }
      error_after: { count: 4, period: day }
    loaded_at_field: date  # or extracted_at
    tables:
      - name: sp500_stock_prices
```

This would surface stale data before it silently flows through the pipeline.

## Stop-the-Line Failures

These conditions MUST halt the pipeline:

| Condition | Detection | Response |
|-----------|-----------|----------|
| Score outside [0, 100] | Custom singular tests | Block all downstream marts until fixed |
| Null ticker in any model | `not_null` schema test | Block downstream; investigate loader |
| Duplicate grain keys | `unique_combination_of_columns` (not yet active) | Block downstream; investigate incremental logic |
| Zero rows in a daily model | `dbt_expectations.expect_table_row_count_to_be_between` (not yet active) | Block downstream; check if market was closed or API failed |
| Source freshness > 4 days | Source freshness check (not yet active) | Block staging; investigate ETL DAG |

## Warning-Level Issues (Non-Blocking)

| Condition | Detection | Response |
|-----------|-----------|----------|
| Source freshness 2-4 days | Source freshness warn | Log warning; may be a holiday weekend |
| Row count anomaly (>20% deviation) | Manual / future automation | Investigate but do not block |
| Null in non-key columns | Not currently tested | Investigate on a per-column basis |

## Recommended Test Additions (Priority Order)

1. **Grain uniqueness on all incremental models** — `dbt_utils.unique_combination_of_columns` on `(ticker, date)` or `(ticker, technical_date)`
2. **Composite score range test** — `assert_composite_score_in_range.sql` for `mart_sp500_composite_scores`
3. **Source freshness** — `loaded_at_field` on all 3 source groups (Polygon, FMP, Wikipedia)
4. **Referential integrity** — `relationships` test between mart tickers and `dim_sp500_companies_current`
5. **Row count bounds** — `dbt_expectations.expect_table_row_count_to_be_between` on daily models (expect ~500 rows per date)

## Ownership

| Layer | Owner | Responsibility |
|-------|-------|---------------|
| RAW data quality | Python ETL (api_clients + loaders) | Correct API parsing, type casting, null handling |
| Staging data quality | dbt schema tests | not_null, type enforcement |
| Intermediate computation quality | dbt schema + singular tests | Window function correctness, join integrity |
| Mart scoring quality | dbt singular tests | Score range, score completeness |
| Pipeline execution quality | Airflow | DAG success/failure, ExternalTaskSensor gating |
| Freshness | Source freshness checks (to be added) | Stale data detection |
