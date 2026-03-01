# Feature 03 — Quarterly Financial Statements

## Goal

Ingest quarterly (Q1-Q4) income statements, balance sheets, and cash flow statements from FMP into separate `_q` raw tables. Reuses existing `FMPClient` methods with `period="quarter"` — NO new client code. Creates 3 daily jobs, 3 backfill jobs, and 6 DAGs.

## Why this matters

The current system uses annual financials only, meaning fundamental scores can be 6-12 months stale. Quarterly data enables trailing-twelve-month (TTM) fundamentals that update every ~90 days, critical for timely valuation and growth scoring. Without quarterly data, the pipeline cannot detect recent earnings deterioration or improvement.

## Scope

- Create `src/jobs/ingest_fmp_income_statement_q.py` — daily job (period=quarter)
- Create `src/jobs/ingest_fmp_balance_sheet_q.py` — daily job (period=quarter)
- Create `src/jobs/ingest_fmp_cash_flow_q.py` — daily job (period=quarter)
- Create `src/jobs/ingest_fmp_income_statement_q_backfill.py` — 5-year backfill
- Create `src/jobs/ingest_fmp_balance_sheet_q_backfill.py` — 5-year backfill
- Create `src/jobs/ingest_fmp_cash_flow_q_backfill.py` — 5-year backfill
- Create `dags/etl/fmp_income_statement_q_dag.py` — daily DAG
- Create `dags/etl/fmp_balance_sheet_q_dag.py` — daily DAG
- Create `dags/etl/fmp_cash_flow_q_dag.py` — daily DAG
- Create `dags/etl/fmp_income_statement_q_backfill_dag.py` — backfill DAG
- Create `dags/etl/fmp_balance_sheet_q_backfill_dag.py` — backfill DAG
- Create `dags/etl/fmp_cash_flow_q_backfill_dag.py` — backfill DAG
- Raw tables: `sp500_income_statements_q`, `sp500_balance_sheets_q`, `sp500_cash_flow_statements_q`

## Out of scope

- New FMP client methods (reuses existing `fetch_income_statements()`, `fetch_balance_sheets()`, `fetch_cash_flow_statements()` with `period="quarter"`)
- dbt TTM intermediate model (`int_sp500_fundamentals_ttm`) — Phase 1+
- Quarterly-specific scoring logic — Phase 1+
- Modification of existing annual financial tables or jobs

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for quarterly statements, schema notes |
| `src/api_clients/fmp_client.py` | Existing methods already accept `period` parameter: `fetch_income_statements(tickers, period="annual")` |
| `src/jobs/ingest_fmp_income_statement.py` | Annual income statement job — this is the EXACT template for the quarterly variant |
| `src/jobs/ingest_fmp_balance_sheet.py` | Annual balance sheet job — template for quarterly variant |
| `src/jobs/ingest_fmp_cash_flow.py` | Annual cash flow job — template for quarterly variant |
| `dags/etl/fmp_income_statement_dag.py` | Daily FMP DAG pattern |
| `dags/etl/polygon_prices_backfill_dag.py` | Backfill DAG pattern |
| `src/loaders/snowflake_loader.py` | Loader API: `overwrite_date_range()` |

## Dependencies

### Upstream features
- None — this is independent. Reuses existing FMP client methods.

### Libraries/packages
- No new packages required. All dependencies already in `requirements.txt`.

### Environment variables
- `FMP_API_KEY` — already used by existing FMP jobs
- `STUDENT_SCHEMA` — already used by all jobs
- `SNOWFLAKE_*` — already used by all jobs

### APIs/data sources
- FMP `/stable/income-statement?symbol={ticker}&period=quarter&apikey={key}`
- FMP `/stable/balance-sheet-statement?symbol={ticker}&period=quarter&apikey={key}`
- FMP `/stable/cash-flow-statement?symbol={ticker}&period=quarter&apikey={key}`

## Data contracts and schemas

### Raw table: `sp500_income_statements_q`

**Grain:** (ticker, date, period) — one row per ticker per fiscal quarter.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_income_statements_q (
    ticker VARCHAR,
    date DATE,
    reported_currency VARCHAR,
    cik VARCHAR,
    filing_date DATE,
    accepted_date TIMESTAMP_NTZ,
    fiscal_year VARCHAR,
    period VARCHAR,
    revenue NUMBER,
    cost_of_revenue NUMBER,
    gross_profit NUMBER,
    research_and_development_expenses NUMBER,
    general_and_administrative_expenses NUMBER,
    selling_and_marketing_expenses NUMBER,
    selling_general_and_administrative_expenses NUMBER,
    other_expenses NUMBER,
    operating_expenses NUMBER,
    cost_and_expenses NUMBER,
    net_interest_income NUMBER,
    interest_income NUMBER,
    interest_expense NUMBER,
    depreciation_and_amortization NUMBER,
    ebitda NUMBER,
    ebit NUMBER,
    non_operating_income_excluding_interest NUMBER,
    operating_income NUMBER,
    total_other_income_expenses_net NUMBER,
    income_before_tax NUMBER,
    income_tax_expense NUMBER,
    net_income_from_continuing_operations NUMBER,
    net_income_from_discontinued_operations NUMBER,
    other_adjustments_to_net_income NUMBER,
    net_income NUMBER,
    net_income_deductions NUMBER,
    bottom_line_net_income NUMBER,
    eps FLOAT,
    eps_diluted FLOAT,
    weighted_average_shares_out NUMBER,
    weighted_average_shares_out_diluted NUMBER,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date, period)
)
```

### Raw table: `sp500_balance_sheets_q`

**Grain:** (ticker, date, period) — one row per ticker per fiscal quarter.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_balance_sheets_q (
    ticker VARCHAR,
    date DATE,
    reported_currency VARCHAR,
    cik VARCHAR,
    filing_date DATE,
    accepted_date TIMESTAMP_NTZ,
    fiscal_year VARCHAR,
    period VARCHAR,
    cash_and_cash_equivalents NUMBER,
    short_term_investments NUMBER,
    cash_and_short_term_investments NUMBER,
    net_receivables NUMBER,
    accounts_receivables NUMBER,
    other_receivables NUMBER,
    inventory NUMBER,
    prepaids NUMBER,
    other_current_assets NUMBER,
    total_current_assets NUMBER,
    property_plant_equipment_net NUMBER,
    goodwill NUMBER,
    intangible_assets NUMBER,
    goodwill_and_intangible_assets NUMBER,
    long_term_investments NUMBER,
    tax_assets NUMBER,
    other_non_current_assets NUMBER,
    total_non_current_assets NUMBER,
    other_assets NUMBER,
    total_assets NUMBER,
    total_payables NUMBER,
    account_payables NUMBER,
    other_payables NUMBER,
    accrued_expenses NUMBER,
    short_term_debt NUMBER,
    capital_lease_obligations_current NUMBER,
    tax_payables NUMBER,
    deferred_revenue NUMBER,
    other_current_liabilities NUMBER,
    total_current_liabilities NUMBER,
    long_term_debt NUMBER,
    deferred_revenue_non_current NUMBER,
    deferred_tax_liabilities_non_current NUMBER,
    other_non_current_liabilities NUMBER,
    total_non_current_liabilities NUMBER,
    other_liabilities NUMBER,
    capital_lease_obligations NUMBER,
    total_liabilities NUMBER,
    treasury_stock NUMBER,
    preferred_stock NUMBER,
    common_stock NUMBER,
    retained_earnings NUMBER,
    additional_paid_in_capital NUMBER,
    accumulated_other_comprehensive_income_loss NUMBER,
    other_total_stockholders_equity NUMBER,
    total_stockholders_equity NUMBER,
    total_equity NUMBER,
    minority_interest NUMBER,
    total_liabilities_and_total_equity NUMBER,
    total_investments NUMBER,
    total_debt NUMBER,
    net_debt NUMBER,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date, period)
)
```

### Raw table: `sp500_cash_flow_statements_q`

**Grain:** (ticker, date, period) — one row per ticker per fiscal quarter.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_cash_flow_statements_q (
    ticker VARCHAR,
    date DATE,
    reported_currency VARCHAR,
    cik VARCHAR,
    filing_date DATE,
    accepted_date TIMESTAMP_NTZ,
    fiscal_year VARCHAR,
    period VARCHAR,
    net_income NUMBER,
    depreciation_and_amortization NUMBER,
    deferred_income_tax NUMBER,
    stock_based_compensation NUMBER,
    change_in_working_capital NUMBER,
    accounts_receivables NUMBER,
    inventory NUMBER,
    accounts_payables NUMBER,
    other_working_capital NUMBER,
    other_non_cash_items NUMBER,
    net_cash_provided_by_operating_activities NUMBER,
    investments_in_property_plant_and_equipment NUMBER,
    acquisitions_net NUMBER,
    purchases_of_investments NUMBER,
    sales_maturities_of_investments NUMBER,
    other_investing_activities NUMBER,
    net_cash_provided_by_investing_activities NUMBER,
    net_debt_issuance NUMBER,
    long_term_net_debt_issuance NUMBER,
    short_term_net_debt_issuance NUMBER,
    net_stock_issuance NUMBER,
    net_common_stock_issuance NUMBER,
    common_stock_issuance NUMBER,
    common_stock_repurchased NUMBER,
    net_preferred_stock_issuance NUMBER,
    net_dividends_paid NUMBER,
    common_dividends_paid NUMBER,
    preferred_dividends_paid NUMBER,
    other_financing_activities NUMBER,
    net_cash_provided_by_financing_activities NUMBER,
    effect_of_forex_changes_on_cash NUMBER,
    net_change_in_cash NUMBER,
    cash_at_end_of_period NUMBER,
    cash_at_beginning_of_period NUMBER,
    operating_cash_flow NUMBER,
    capital_expenditure NUMBER,
    free_cash_flow NUMBER,
    income_taxes_paid NUMBER,
    interest_paid NUMBER,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date, period)
)
```

## Implementation plan

### Step 1: Create `src/jobs/ingest_fmp_income_statement_q.py`

Copy `src/jobs/ingest_fmp_income_statement.py` and make two changes:
1. Change `TABLE = "sp500_income_statements"` to `TABLE = "sp500_income_statements_q"`
2. Change `DEFAULT_PERIOD = "annual"` to `DEFAULT_PERIOD = "quarter"`

```python
import sys
import os
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_date_range,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_income_statements_q"
DEFAULT_PERIOD = "quarter"


def run(run_date: str, period: str = DEFAULT_PERIOD):
    print(f"Starting S&P 500 quarterly income statement ingestion for {run_date} (period={period})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_income_statements(tickers, period=period)

    if df.empty:
        print("No quarterly income statement data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        reported_currency VARCHAR,
        cik VARCHAR,
        filing_date DATE,
        accepted_date TIMESTAMP_NTZ,
        fiscal_year VARCHAR,
        period VARCHAR,
        revenue NUMBER,
        cost_of_revenue NUMBER,
        gross_profit NUMBER,
        research_and_development_expenses NUMBER,
        general_and_administrative_expenses NUMBER,
        selling_and_marketing_expenses NUMBER,
        selling_general_and_administrative_expenses NUMBER,
        other_expenses NUMBER,
        operating_expenses NUMBER,
        cost_and_expenses NUMBER,
        net_interest_income NUMBER,
        interest_income NUMBER,
        interest_expense NUMBER,
        depreciation_and_amortization NUMBER,
        ebitda NUMBER,
        ebit NUMBER,
        non_operating_income_excluding_interest NUMBER,
        operating_income NUMBER,
        total_other_income_expenses_net NUMBER,
        income_before_tax NUMBER,
        income_tax_expense NUMBER,
        net_income_from_continuing_operations NUMBER,
        net_income_from_discontinued_operations NUMBER,
        other_adjustments_to_net_income NUMBER,
        net_income NUMBER,
        net_income_deductions NUMBER,
        bottom_line_net_income NUMBER,
        eps FLOAT,
        eps_diluted FLOAT,
        weighted_average_shares_out NUMBER,
        weighted_average_shares_out_diluted NUMBER,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date, period)
    )
    """

    fq_table = f"{schema}.{TABLE}"

    overwrite_date_range(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=start_date,
        end_date=end_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} quarterly income statements to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    period = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PERIOD
    run(run_date, period)
```

### Step 2: Create `src/jobs/ingest_fmp_balance_sheet_q.py`

Same pattern as Step 1 but for balance sheets:
- `TABLE = "sp500_balance_sheets_q"`
- `DEFAULT_PERIOD = "quarter"`
- Calls `client.fetch_balance_sheets(tickers, period=period)`
- DDL matches `sp500_balance_sheets_q` schema above

### Step 3: Create `src/jobs/ingest_fmp_cash_flow_q.py`

Same pattern as Step 1 but for cash flow:
- `TABLE = "sp500_cash_flow_statements_q"`
- `DEFAULT_PERIOD = "quarter"`
- Calls `client.fetch_cash_flow_statements(tickers, period=period)`
- DDL matches `sp500_cash_flow_statements_q` schema above

### Step 4: Create backfill jobs

Create 3 backfill jobs. Each is identical to its daily counterpart — the FMP endpoint returns full history by default when `period=quarter`. The backfill jobs exist as separate entry points for manual Airflow triggers.

- `src/jobs/ingest_fmp_income_statement_q_backfill.py` — same as daily, TABLE stays `"sp500_income_statements_q"`
- `src/jobs/ingest_fmp_balance_sheet_q_backfill.py` — same as daily, TABLE stays `"sp500_balance_sheets_q"`
- `src/jobs/ingest_fmp_cash_flow_q_backfill.py` — same as daily, TABLE stays `"sp500_cash_flow_statements_q"`

### Step 5: Create daily DAGs

Create 3 daily DAGs following the `fmp_income_statement_dag.py` pattern:

**`dags/etl/fmp_income_statement_q_dag.py`:**
```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_income_statement_q import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_income_statement_q",
    default_args=default_args,
    description="Fetch S&P 500 quarterly income statements from FMP",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "daily", "quarterly"],
) as dag:

    wait_for_universe = ExternalTaskSensor(
        task_id="wait_for_universe",
        external_dag_id="sp500_lookup",
        external_task_id="ingest_sp500_lookup",
        timeout=3600,
        poke_interval=60,
        mode="poke",
    )

    ingest_income_q = PythonOperator(
        task_id="ingest_fmp_income_statement_q",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_income_q
```

**`dags/etl/fmp_balance_sheet_q_dag.py`:**
- `dag_id="fmp_balance_sheet_q"`
- Imports from `src.jobs.ingest_fmp_balance_sheet_q`
- Task id: `"ingest_fmp_balance_sheet_q"`
- Same structure as above

**`dags/etl/fmp_cash_flow_q_dag.py`:**
- `dag_id="fmp_cash_flow_q"`
- Imports from `src.jobs.ingest_fmp_cash_flow_q`
- Task id: `"ingest_fmp_cash_flow_q"`
- Same structure as above

### Step 6: Create backfill DAGs

Create 3 backfill DAGs following the `polygon_prices_backfill_dag.py` pattern:

**`dags/etl/fmp_income_statement_q_backfill_dag.py`:**
```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_income_statement_q_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fmp_income_statement_q_backfill",
    default_args=default_args,
    description="Backfill S&P 500 quarterly income statements from FMP",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "backfill", "quarterly"],
) as dag:

    backfill_income_q = PythonOperator(
        task_id="backfill_fmp_income_statement_q",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

Similarly for `fmp_balance_sheet_q_backfill_dag.py` and `fmp_cash_flow_q_backfill_dag.py`.

### Step 7: Validate

```bash
astro dev parse
python -c "from src.jobs.ingest_fmp_income_statement_q import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fmp_client.py` | NO CHANGE | Existing methods already accept `period="quarter"` |
| `src/jobs/ingest_fmp_income_statement_q.py` | CREATE | Daily quarterly income statement job |
| `src/jobs/ingest_fmp_balance_sheet_q.py` | CREATE | Daily quarterly balance sheet job |
| `src/jobs/ingest_fmp_cash_flow_q.py` | CREATE | Daily quarterly cash flow job |
| `src/jobs/ingest_fmp_income_statement_q_backfill.py` | CREATE | Backfill quarterly income statement job |
| `src/jobs/ingest_fmp_balance_sheet_q_backfill.py` | CREATE | Backfill quarterly balance sheet job |
| `src/jobs/ingest_fmp_cash_flow_q_backfill.py` | CREATE | Backfill quarterly cash flow job |
| `dags/etl/fmp_income_statement_q_dag.py` | CREATE | Daily DAG for quarterly income statements |
| `dags/etl/fmp_balance_sheet_q_dag.py` | CREATE | Daily DAG for quarterly balance sheets |
| `dags/etl/fmp_cash_flow_q_dag.py` | CREATE | Daily DAG for quarterly cash flow |
| `dags/etl/fmp_income_statement_q_backfill_dag.py` | CREATE | Backfill DAG for quarterly income statements |
| `dags/etl/fmp_balance_sheet_q_backfill_dag.py` | CREATE | Backfill DAG for quarterly balance sheets |
| `dags/etl/fmp_cash_flow_q_backfill_dag.py` | CREATE | Backfill DAG for quarterly cash flow |

## Functions and interfaces

### Daily jobs (all 3 follow same signature)

```python
def run(run_date: str, period: str = "quarter") -> None:
    """Fetch and load quarterly financial statements for all S&P 500 tickers."""
    ...
```

### Backfill jobs (all 3 follow same signature)

```python
def run(run_date: str) -> None:
    """Backfill quarterly financial statements for all S&P 500 tickers."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fmp_client.py` | No changes — reuses existing methods with `period="quarter"`. |
| `src/loaders/snowflake_loader.py` | No changes — uses existing `overwrite_date_range()`. |
| Airflow DAG registry | 6 new DAGs registered. Verify no `dag_id` conflicts. |
| Snowflake schema | 3 new tables created in `{STUDENT_SCHEMA}`. No existing tables modified. |
| FMP rate budget | +1,500 requests/day (3 statements x 500 tickers x 0.1s/req = ~2.5 min). |
| Existing annual tables | NOT modified. Annual and quarterly data stored in separate tables. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| FMP returns empty data for a ticker | `_fetch_batch()` counts as failed; empty list returned. |
| FMP returns 429 (rate limit) | Handled by `_get()` retry logic with exponential backoff. |
| `period` field contains unexpected value | Stored as-is in VARCHAR column. Expected: Q1, Q2, Q3, Q4. |
| Quarterly data not yet filed for recent quarter | No data returned for that quarter; existing quarters unaffected. |
| Same date range as annual data | No conflict — separate `_q` tables. |
| Ticker has fewer than 20 quarters of history | Only available quarters returned; no error. |
| `accepted_date` parsing fails | Caught by existing try/except in FMP client; stored as NULL. |
| Duplicate (ticker, date, period) | Snowflake PRIMARY KEY is informational; `overwrite_date_range()` deletes before inserting. |

## Observability

- All jobs use `print()` statements captured by Airflow task logs
- `_fetch_batch()` provides progress logging every 50 tickers
- Final row count and date range printed
- Expected runtime per statement type: ~500 tickers x 0.1s/req = ~50 seconds

## Acceptance criteria

- [ ] All 6 daily/backfill jobs created with correct `TABLE` and `DEFAULT_PERIOD`
- [ ] All 6 DAGs parse without errors (`astro dev parse`)
- [ ] 3 daily DAGs are gated on `sp500_lookup` via ExternalTaskSensor
- [ ] 3 backfill DAGs have `schedule=None`
- [ ] No new methods added to `fmp_client.py` (confirms reuse of existing methods)
- [ ] `period` column contains Q1/Q2/Q3/Q4 values (not FY)
- [ ] DDL schemas for `_q` tables are identical to annual tables (same columns)
- [ ] Running the same job twice produces no duplicate rows
- [ ] `SELECT COUNT(*) FROM sp500_income_statements_q` returns > 0 after a successful run
- [ ] `SELECT COUNT(DISTINCT period) FROM sp500_income_statements_q` returns up to 4

## Follow-ups

- Phase 1+: Create dbt staging models for quarterly tables
- Phase 1+: Create `int_sp500_fundamentals_ttm` — SUM trailing 4 quarters for flow metrics, latest quarter for stock metrics
- Phase 1+: Update `mart_sp500_fundamental_scores` to use TTM data instead of annual
- Add source freshness checks once staging models exist
- Consider combining annual and quarterly into a single table with period filter (deferred — separate tables is simpler for now)
