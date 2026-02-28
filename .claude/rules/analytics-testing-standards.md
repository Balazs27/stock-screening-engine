# Rule: Analytics Testing Standards

Enforces dbt testing conventions, reconciliation checks, and auditability requirements.

---

## Test Hierarchy

### Layer 1: Schema Tests (YAML — Baseline)

Every model MUST have:
- `not_null` on all grain key columns (ticker, date)
- `unique` on natural key for dimension tables
- `not_null` on critical output columns (score columns in marts)

```yaml
# Example: mart.yml
models:
  - name: mart_sp500_technical_scores
    columns:
      - name: ticker
        data_tests:
          - not_null
      - name: technical_score
        data_tests:
          - not_null
```

### Layer 2: Custom Singular Tests (SQL — Business Logic Validation)

Located in `dbt_project/tests/`. Each test returns rows that VIOLATE the assertion. Test passes when 0 rows returned.

**Pattern:**
```sql
-- Test: {assertion_description}
-- Returns rows that violate the constraint (test passes when 0 rows returned)

SELECT
    ticker,
    date,
    {column_under_test}
FROM {{ ref('{model_name}') }}
WHERE {violation_condition}
```

**Existing tests:**
| Test | Assertion | Violation Condition |
|------|-----------|-------------------|
| `assert_technical_score_in_range` | Score between 0-100 | `score < 0 OR score > 100 OR score IS NULL` |
| `assert_fundamentals_score_in_range` | Score between 0-100 | `score < 0 OR score > 100 OR score IS NULL` |

### Layer 3: Package-Based Tests (dbt_utils, dbt_expectations)

Available but not yet active. Priority additions:

```yaml
# Grain uniqueness
- dbt_utils.unique_combination_of_columns:
    combination_of_columns:
      - ticker
      - date

# Score bounds
- dbt_expectations.expect_column_values_to_be_between:
    min_value: 0
    max_value: 100

# Row count sanity
- dbt_expectations.expect_table_row_count_to_be_between:
    min_value: 400   # ~500 S&P 500 stocks, allow for delists
    max_value: 600

# Referential integrity
- relationships:
    to: ref('dim_sp500_companies_current')
    field: ticker
```

## Test Coverage Requirements by Layer

| Layer | Minimum Required Tests | Notes |
|-------|----------------------|-------|
| **Staging** | `not_null` on ticker | Source-level quality gate |
| **Intermediate** | `not_null` on ticker + grain uniqueness | Computation correctness |
| **Dimensions** | `not_null` + `unique` on natural key | Entity integrity |
| **Marts** | `not_null` on ticker + score not_null + score range test | Analytics contract |

## Source-to-Target Reconciliation

For any new model or significant change, verify:

1. **Row count alignment**: Compare upstream row count with downstream for the same date
   ```sql
   -- Expected: staging rows for date X >= mart rows for date X (some tickers may not have all indicators)
   SELECT COUNT(*) FROM {{ ref('stg_sp500_stock_prices') }} WHERE date = '2024-01-02'
   -- vs
   SELECT COUNT(*) FROM {{ ref('mart_sp500_technical_scores') }} WHERE date = '2024-01-02'
   ```

2. **Ticker coverage**: All tickers in the dimension should appear in daily marts
   ```sql
   SELECT d.ticker
   FROM {{ ref('dim_sp500_companies_current') }} d
   LEFT JOIN {{ ref('mart_sp500_technical_scores') }} t
     ON d.ticker = t.ticker AND t.date = '2024-01-02'
   WHERE t.ticker IS NULL
   -- Should return 0 rows (or explainable exceptions like newly added tickers)
   ```

3. **Score distribution sanity**: Score averages should be reasonable
   ```sql
   SELECT
     AVG(technical_score) as avg_score,    -- Expect 30-70 range
     MIN(technical_score) as min_score,    -- Should be >= 0
     MAX(technical_score) as max_score     -- Should be <= 100
   FROM {{ ref('mart_sp500_technical_scores') }}
   WHERE date = '2024-01-02'
   ```

## Auditability Requirements

### Every Scoring Model Must Have:
1. **Component scores visible**: Individual components (trend_score, momentum_score, etc.) must be in the output alongside the composite
2. **Score is deterministic**: Same inputs must always produce the same score
3. **Score decomposition**: It must be possible to trace why a stock received its score by inspecting component values

### Data Lineage:
- Every mart column should be traceable back to a staging source
- The dbt dependency graph (accessible via `dbt docs generate`) provides automated lineage
- Cosmos renders the dbt DAG in Airflow, providing operational lineage

## Testing New Score Components — Checklist

When adding a new scoring component:

1. Verify component max points sum to the target total (e.g., 100)
2. Verify all CASE WHEN branches are exhaustive (include ELSE clause)
3. Add a custom singular test: `assert_{model}_score_in_range.sql`
4. Run `dbt test --select {model}` and verify 0 failures
5. Spot-check edge cases: what happens when input is NULL? When input is 0? When input is negative?
6. Verify the score range test catches NULLs (include `OR column IS NULL` in the WHERE clause)

## Airflow DAG Testing

The Astronomer test suite (`test_dag_integrity_default.py`) validates:
- All DAGs in `dags/` parse without import errors
- Connections and variables are monkeypatched to avoid runtime dependency
- DAGs excluded via `.astro/dag_integrity_exceptions.txt` are skipped

This runs on `astro dev parse` and in CI/CD. It does NOT test task execution — only import/parse integrity.
