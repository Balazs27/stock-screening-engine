# Feature 01 — Earnings Calendar & Surprises

## Goal

Ingest FMP earnings calendar (upcoming/recent earnings dates with EPS estimates) and historical earnings surprises (actual vs. estimated EPS) into Snowflake. Provides two raw tables that enable downstream earnings-driven catalyst detection and post-earnings momentum scoring.

## Why this matters

Earnings events are the single highest-impact catalyst for stock price movement. Without earnings data, the opportunity pipeline cannot flag upcoming catalysts, score post-earnings momentum, or detect surprise-driven breakouts. This is the foundational data for Phase 1+ earnings catalyst agents.

## Scope

- Add `FMPClient.fetch_earnings_calendar()` method to `src/api_clients/fmp_client.py`
- Add `FMPClient.fetch_earnings_surprises()` method to `src/api_clients/fmp_client.py`
- Create `src/jobs/ingest_fmp_earnings_calendar.py` — daily job (global endpoint, filter to S&P 500)
- Create `src/jobs/ingest_fmp_earnings_surprises.py` — daily job (per-ticker)
- Create `src/jobs/ingest_fmp_earnings_surprises_backfill.py` — 5-year historical backfill
- Create `dags/etl/fmp_earnings_calendar_dag.py` — daily DAG gated on `sp500_lookup`
- Create `dags/etl/fmp_earnings_surprises_dag.py` — daily DAG gated on `sp500_lookup`
- Create `dags/etl/fmp_earnings_surprises_backfill_dag.py` — manual trigger backfill DAG
- Raw tables: `sp500_earnings_calendar`, `sp500_earnings_surprises`

## Out of scope

- dbt staging/intermediate/mart models for earnings data (Phase 1+)
- Earnings catalyst scoring logic (Phase 2)
- Earnings-based alerting or notification
- FMP earnings transcript endpoints

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for earnings calendar & surprises endpoints, JSON schemas, grain definitions |
| `src/api_clients/fmp_client.py` | Existing FMP client patterns: `_get()`, `_fetch_batch()`, rate limiting, response parsing |
| `src/jobs/ingest_fmp_income_statement.py` | FMP daily job pattern: session setup, ticker lookup, client call, DDL, loader call |
| `src/loaders/snowflake_loader.py` | Loader API: `overwrite_partition()`, `overwrite_date_range()` |
| `dags/etl/fmp_income_statement_dag.py` | Daily FMP DAG pattern: ExternalTaskSensor + PythonOperator |
| `dags/etl/polygon_prices_backfill_dag.py` | Backfill DAG pattern: schedule=None, no sensor |
| `CLAUDE.md` | Forbidden actions, separation of concerns |
| `.claude/rules/analytics-architecture.md` | Layer boundaries, naming conventions |

## Dependencies

### Upstream features
- None — this is independent and can be implemented first.

### Libraries/packages
- `requests` — already in `requirements.txt`
- `pandas` — already in `requirements.txt`
- `snowflake-snowpark-python` — already in `requirements.txt`
- No new packages required.

### Environment variables
- `FMP_API_KEY` — already used by existing FMP jobs
- `STUDENT_SCHEMA` — already used by all jobs
- `SNOWFLAKE_*` — already used by all jobs

### APIs/data sources
- FMP `/stable/earning-calendar?from={date}&to={date}&apikey={key}` — global endpoint, returns all tickers
- FMP `/stable/earnings-surprises?symbol={ticker}&apikey={key}` — per-ticker endpoint

## Data contracts and schemas

### Raw table: `sp500_earnings_calendar`

**Grain:** (ticker, date) — one row per ticker per expected earnings date.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_earnings_calendar (
    ticker VARCHAR,
    date DATE,
    eps FLOAT,
    eps_estimated FLOAT,
    time VARCHAR,
    revenue NUMBER,
    revenue_estimated NUMBER,
    updated_from_date DATE,
    fiscal_date_ending DATE,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### Raw table: `sp500_earnings_surprises`

**Grain:** (ticker, date) — one row per ticker per historical earnings event.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_earnings_surprises (
    ticker VARCHAR,
    date DATE,
    actual_earning_result FLOAT,
    estimated_earning FLOAT,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### DataFrame schemas

**Earnings Calendar DataFrame** (returned by `fetch_earnings_calendar()`):

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` |
| `date` | str | `date` |
| `eps` | float/None | `eps` |
| `eps_estimated` | float/None | `epsEstimated` |
| `time` | str/None | `time` (bmo/amc/--/null) |
| `revenue` | float/None | `revenue` |
| `revenue_estimated` | float/None | `revenueEstimated` |
| `updated_from_date` | str/None | `updatedFromDate` |
| `fiscal_date_ending` | str/None | `fiscalDateEnding` |
| `extracted_at` | str | Generated at fetch time |

**Earnings Surprises DataFrame** (returned by `fetch_earnings_surprises()`):

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `date` | str | `date` |
| `actual_earning_result` | float/None | `actualEarningResult` |
| `estimated_earning` | float/None | `estimatedEarning` |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 1: Add `fetch_earnings_calendar()` to FMPClient

Add a new method to `src/api_clients/fmp_client.py`. This is NOT a per-ticker endpoint — it is a global calendar filtered to S&P 500 tickers post-fetch.

```python
def fetch_earnings_calendar(
    self, tickers: list[str], from_date: str, to_date: str
) -> pd.DataFrame:
    """Fetch earnings calendar for a date range, filtered to S&P 500 tickers.

    Unlike per-ticker methods, this calls a single global endpoint and
    filters the results to the provided ticker list.
    """
    ticker_set = set(tickers)
    url = (
        f"{BASE_URL}/stable/earning-calendar"
        f"?from={from_date}"
        f"&to={to_date}"
        f"&apikey={self.api_key}"
    )
    response = self._get(url)
    if response.status_code != 200:
        print(f"Earnings calendar HTTP {response.status_code}")
        return pd.DataFrame()

    data = response.json()
    if not data or isinstance(data, dict):
        return pd.DataFrame()

    extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for r in data:
        symbol = r.get("symbol", "")
        if symbol not in ticker_set:
            continue
        rows.append({
            "ticker": symbol,
            "date": r.get("date"),
            "eps": r.get("eps"),
            "eps_estimated": r.get("epsEstimated"),
            "time": r.get("time"),
            "revenue": r.get("revenue"),
            "revenue_estimated": r.get("revenueEstimated"),
            "updated_from_date": r.get("updatedFromDate"),
            "fiscal_date_ending": r.get("fiscalDateEnding"),
            "extracted_at": extracted_at,
        })

    print(f"Earnings calendar: {len(data)} total events, {len(rows)} S&P 500 matches")
    return pd.DataFrame(rows) if rows else pd.DataFrame()
```

### Step 2: Add `fetch_earnings_surprises()` to FMPClient

Add a per-ticker method using the standard `_fetch_batch()` pattern.

```python
def fetch_earnings_surprises(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch historical earnings surprises for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/earnings-surprises"
            f"?symbol={ticker}"
            f"&apikey={self.api_key}"
        )
        response = self._get(url)
        if response.status_code != 200:
            return []
        data = response.json()
        if not data or isinstance(data, dict):
            return []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for r in data:
            rows.append({
                "ticker": ticker,
                "date": r.get("date"),
                "actual_earning_result": r.get("actualEarningResult"),
                "estimated_earning": r.get("estimatedEarning"),
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="earnings surprises")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 3: Create `src/jobs/ingest_fmp_earnings_calendar.py`

Daily job that fetches earnings calendar for a 30-day forward window from run_date.

```python
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_partition,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_earnings_calendar"
DEFAULT_FORWARD_DAYS = 30


def run(run_date: str, forward_days: int = DEFAULT_FORWARD_DAYS):
    print(f"Starting S&P 500 earnings calendar ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    end_date = datetime.strptime(run_date, "%Y-%m-%d").date() + timedelta(days=forward_days)

    client = FMPClient()
    df = client.fetch_earnings_calendar(tickers, run_date, str(end_date))

    if df.empty:
        print("No earnings calendar data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        eps FLOAT,
        eps_estimated FLOAT,
        time VARCHAR,
        revenue NUMBER,
        revenue_estimated NUMBER,
        updated_from_date DATE,
        fiscal_date_ending DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
    )
    """

    fq_table = f"{schema}.{TABLE}"

    overwrite_partition(
        session=session,
        df=df,
        table_name=fq_table,
        partition_col="extracted_at",
        partition_value=df["extracted_at"].iloc[0],
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} earnings calendar events to {fq_table}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

**Note on partition strategy:** The earnings calendar is a forward-looking snapshot. Each daily run replaces the entire calendar table content for idempotency. Use `overwrite_partition()` with `extracted_at` as the partition column. Alternatively, truncate and reload since this is a small table (~200-500 rows). The implementor should choose the simpler approach: truncate the table and append, since the calendar is a complete snapshot on each run. A cleaner pattern is to DELETE all rows (no WHERE clause) and then INSERT:

```python
# Alternative: full table replacement (preferred for calendar snapshots)
session.sql(create_table_sql).collect()
session.sql(f"DELETE FROM {fq_table}").collect()
session.create_dataframe(df).write.mode("append").save_as_table(fq_table)
```

### Step 4: Create `src/jobs/ingest_fmp_earnings_surprises.py`

Daily job using `overwrite_date_range()` since surprises span historical dates.

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
TABLE = "sp500_earnings_surprises"


def run(run_date: str):
    print(f"Starting S&P 500 earnings surprises ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_earnings_surprises(tickers)

    if df.empty:
        print("No earnings surprises data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        actual_earning_result FLOAT,
        estimated_earning FLOAT,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
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

    print(f"Successfully wrote {len(df)} earnings surprises to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 5: Create `src/jobs/ingest_fmp_earnings_surprises_backfill.py`

Identical to daily job — the FMP endpoint returns full history by default. The backfill job exists as a separate entry point for manual trigger via Airflow.

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
TABLE = "sp500_earnings_surprises"


def run(run_date: str):
    print(f"Starting S&P 500 earnings surprises backfill for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_earnings_surprises(tickers)

    if df.empty:
        print("No earnings surprises data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        actual_earning_result FLOAT,
        estimated_earning FLOAT,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
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

    print(f"Successfully wrote {len(df)} earnings surprises to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 6: Create `dags/etl/fmp_earnings_calendar_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_earnings_calendar import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_earnings_calendar",
    default_args=default_args,
    description="Fetch S&P 500 earnings calendar from FMP (30-day forward window)",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "daily"],
) as dag:

    wait_for_universe = ExternalTaskSensor(
        task_id="wait_for_universe",
        external_dag_id="sp500_lookup",
        external_task_id="ingest_sp500_lookup",
        timeout=3600,
        poke_interval=60,
        mode="poke",
    )

    ingest_earnings_calendar = PythonOperator(
        task_id="ingest_fmp_earnings_calendar",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_earnings_calendar
```

### Step 7: Create `dags/etl/fmp_earnings_surprises_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_earnings_surprises import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_earnings_surprises",
    default_args=default_args,
    description="Fetch S&P 500 historical earnings surprises from FMP",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "daily"],
) as dag:

    wait_for_universe = ExternalTaskSensor(
        task_id="wait_for_universe",
        external_dag_id="sp500_lookup",
        external_task_id="ingest_sp500_lookup",
        timeout=3600,
        poke_interval=60,
        mode="poke",
    )

    ingest_earnings_surprises = PythonOperator(
        task_id="ingest_fmp_earnings_surprises",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_earnings_surprises
```

### Step 8: Create `dags/etl/fmp_earnings_surprises_backfill_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_earnings_surprises_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fmp_earnings_surprises_backfill",
    default_args=default_args,
    description="Backfill historical S&P 500 earnings surprises from FMP",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "backfill"],
) as dag:

    backfill_earnings_surprises = PythonOperator(
        task_id="backfill_fmp_earnings_surprises",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

### Step 9: Validate

```bash
# Parse all DAGs
astro dev parse

# Manual test
python -c "from src.jobs.ingest_fmp_earnings_calendar import run; run('2026-02-28')"
python -c "from src.jobs.ingest_fmp_earnings_surprises import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fmp_client.py` | EDIT | Add `fetch_earnings_calendar()` and `fetch_earnings_surprises()` methods |
| `src/jobs/ingest_fmp_earnings_calendar.py` | CREATE | Daily earnings calendar job (global endpoint, filter to S&P 500) |
| `src/jobs/ingest_fmp_earnings_surprises.py` | CREATE | Daily earnings surprises job (per-ticker) |
| `src/jobs/ingest_fmp_earnings_surprises_backfill.py` | CREATE | Backfill earnings surprises job |
| `dags/etl/fmp_earnings_calendar_dag.py` | CREATE | Daily DAG for earnings calendar |
| `dags/etl/fmp_earnings_surprises_dag.py` | CREATE | Daily DAG for earnings surprises |
| `dags/etl/fmp_earnings_surprises_backfill_dag.py` | CREATE | Backfill DAG for earnings surprises |

## Functions and interfaces

### `fmp_client.py` — new methods

```python
def fetch_earnings_calendar(
    self, tickers: list[str], from_date: str, to_date: str
) -> pd.DataFrame:
    """Fetch earnings calendar for a date range, filtered to S&P 500 tickers.

    Args:
        tickers: S&P 500 ticker list for post-fetch filtering.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).

    Returns:
        DataFrame with columns: ticker, date, eps, eps_estimated, time,
        revenue, revenue_estimated, updated_from_date, fiscal_date_ending,
        extracted_at. Empty DataFrame if no data.
    """
    ...

def fetch_earnings_surprises(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch historical earnings surprises for a list of tickers.

    Args:
        tickers: List of ticker symbols.

    Returns:
        DataFrame with columns: ticker, date, actual_earning_result,
        estimated_earning, extracted_at. Empty DataFrame if no data.
    """
    ...
```

### `ingest_fmp_earnings_calendar.py`

```python
def run(run_date: str, forward_days: int = 30) -> None:
    """Fetch and load earnings calendar for run_date + forward window."""
    ...
```

### `ingest_fmp_earnings_surprises.py` / `ingest_fmp_earnings_surprises_backfill.py`

```python
def run(run_date: str) -> None:
    """Fetch and load historical earnings surprises for all S&P 500 tickers."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fmp_client.py` | Adding 2 methods — no existing method signatures change. Backward compatible. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_partition()` and `overwrite_date_range()`. |
| Airflow DAG registry | 3 new DAGs registered. Verify no `dag_id` conflicts. |
| Snowflake schema | 2 new tables created in `{STUDENT_SCHEMA}`. No existing tables modified. |
| Cosmos dbt DAG | NOT updated in this feature. Post-phase integration step. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| FMP returns empty earnings calendar | `df.empty` check; log "No earnings calendar data fetched." and return early. |
| FMP returns 429 (rate limit) | Handled by `_get()` retry logic with exponential backoff (3 attempts). |
| FMP returns 403/500 | `response.status_code != 200` check; return empty list. |
| Earnings calendar has no S&P 500 matches | After filtering, `rows` is empty; return empty DataFrame. |
| `eps` or `epsEstimated` is null in JSON | Stored as NULL in Snowflake (FLOAT columns accept NULL). |
| `time` field has unexpected value (not bmo/amc/--) | Stored as-is (VARCHAR column); no validation at ingest. |
| Ticker not found in surprises endpoint | `_fetch_batch()` returns empty list for that ticker; no error raised. |
| Weekend/holiday run (no new calendar events) | Empty DataFrame path; no data written, no error. |
| Duplicate (ticker, date) in calendar response | Possible if FMP returns duplicates; Snowflake PRIMARY KEY is informational only. Downstream dbt dedup handles this. |
| Backfill job produces same data as daily | `overwrite_date_range()` deletes existing rows first. Idempotent. |

## Observability

- All jobs use `print()` statements (captured by Airflow task logs):
  - Starting message with run_date
  - Ticker count from universe lookup
  - Calendar: total events and S&P 500 match count
  - Surprises: `_fetch_batch()` progress every 50 tickers
  - Final row count written to Snowflake
- Airflow task status (success/failure) visible in Airflow UI
- Snowflake query history shows CREATE TABLE and DELETE/INSERT operations
- No custom metrics at this stage

## Acceptance criteria

- [ ] `FMPClient.fetch_earnings_calendar()` returns a DataFrame with correct columns when called with valid tickers and date range
- [ ] `FMPClient.fetch_earnings_surprises()` returns a DataFrame with correct columns when called with valid tickers
- [ ] `src/jobs/ingest_fmp_earnings_calendar.py` creates `sp500_earnings_calendar` table and populates it
- [ ] `src/jobs/ingest_fmp_earnings_surprises.py` creates `sp500_earnings_surprises` table and populates it
- [ ] `src/jobs/ingest_fmp_earnings_surprises_backfill.py` populates historical surprises data
- [ ] All 3 DAGs parse without errors (`astro dev parse`)
- [ ] Daily calendar DAG is gated on `sp500_lookup` via ExternalTaskSensor
- [ ] Daily surprises DAG is gated on `sp500_lookup` via ExternalTaskSensor
- [ ] Backfill DAG has `schedule=None` (manual trigger only)
- [ ] Running the same job twice produces no duplicate rows (idempotent)
- [ ] Snowflake table schemas match the DDL definitions above
- [ ] `SELECT COUNT(*) FROM sp500_earnings_calendar` returns > 0 after a successful run
- [ ] `SELECT COUNT(*) FROM sp500_earnings_surprises` returns > 0 after a successful run

## Follow-ups

- Phase 1+: Create dbt staging models `stg_fmp_earnings_calendar.sql` and `stg_fmp_earnings_surprises.sql`
- Phase 1+: Create dbt intermediate model for earnings surprise scoring (beat/miss magnitude)
- Phase 2: Earnings catalyst detection agent using calendar + surprise data
- Consider adding `fiscal_date_ending` to the surprises table if FMP exposes it in future API versions
- Source freshness checks for `_sources.yml` once staging models exist
