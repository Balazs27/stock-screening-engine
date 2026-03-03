# Feature 08 — Macro Rates (FRED)

## Goal

Create a new FRED API client and ingest key macroeconomic interest rate series (Federal Funds Rate, 10-Year Treasury, 2-Year Treasury, High-Yield OAS) from the Federal Reserve Economic Data (FRED) API. Introduces a new API client file, new environment variable, and daily + 5-year backfill pipelines.

## Why this matters

Interest rates drive sector rotation (rate-sensitive sectors like financials, REITs, utilities) and risk appetite. The 10Y-2Y spread is a recession indicator. Without macro context, sector favorability scoring is impossible and the pipeline operates in a vacuum without understanding the rate environment.

## Scope

- Create `src/api_clients/fred_client.py` — new API client for FRED
- Create `src/jobs/ingest_fred_macro_rates.py` — daily job (4 series, 1 date)
- Create `src/jobs/ingest_fred_macro_rates_backfill.py` — 5-year backfill
- Create `dags/etl/fred_macro_rates_dag.py` — daily DAG (no sp500_lookup dependency)
- Create `dags/etl/fred_macro_rates_backfill_dag.py` — backfill DAG (schedule=None)
- Add `FRED_API_KEY` documentation to `.env.example` (if it exists) or note in implementation
- Raw table: `sp500_macro_rates`

## Out of scope

- 10Y-2Y spread computation (derived in dbt intermediate layer, Phase 1+)
- Market regime classification (Phase 1+)
- Interest rate impact on sector rotation scoring (Phase 1+)
- Additional FRED series (GDP, unemployment, CPI, etc.)
- FRED series metadata or release schedule tracking

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for FRED API, series IDs, JSON schema |
| `src/api_clients/polygon_client.py` | API client pattern: `__init__`, `_get()`, rate limiting |
| `src/api_clients/fmp_client.py` | Alternative client pattern for comparison |
| `src/jobs/ingest_polygon_prices.py` | Daily job pattern with `overwrite_partition()` |
| `src/jobs/ingest_polygon_prices_backfill.py` | Backfill job pattern with `overwrite_date_range()` |
| `dags/etl/polygon_daily_prices_dag.py` | Daily DAG pattern |
| `src/loaders/snowflake_loader.py` | Loader API |
| `.claude/rules/analytics-architecture.md` | API clients in `src/api_clients/` — fetch only, return DataFrames |

## Dependencies

### Upstream features
- None — this is independent. Does NOT depend on S&P 500 universe.

### Libraries/packages
- `requests` — already in `requirements.txt`
- `pandas` — already in `requirements.txt`
- No new packages required.

### Environment variables
- `FRED_API_KEY` — **NEW**. Free API key from https://fred.stlouisfed.org/docs/api/api_key.html
- `STUDENT_SCHEMA` — already used
- `SNOWFLAKE_*` — already used

### APIs/data sources
- FRED API: `GET https://api.stlouisfed.org/fred/series/observations?series_id={id}&api_key={key}&file_type=json&observation_start={date}&observation_end={date}`
- Series IDs:
  - `DFF` — Federal Funds Effective Rate
  - `DGS10` — 10-Year Treasury Constant Maturity Rate
  - `DGS2` — 2-Year Treasury Constant Maturity Rate
  - `BAMLH0A0HYM2` — ICE BofA US High Yield OAS

## Data contracts and schemas

### FRED Series Reference

| Series ID | Name | Frequency | Units |
|-----------|------|-----------|-------|
| `DFF` | Federal Funds Effective Rate | Daily | Percent |
| `DGS10` | 10-Year Treasury Yield | Daily | Percent |
| `DGS2` | 2-Year Treasury Yield | Daily | Percent |
| `BAMLH0A0HYM2` | High Yield OAS | Daily | Percent |

### Raw table: `sp500_macro_rates`

**Grain:** (series_id, date) — one row per series per observation date.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_macro_rates (
    series_id VARCHAR,
    date DATE,
    value FLOAT,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (series_id, date)
)
```

### DataFrame schema

**Macro Rates DataFrame** (returned by `FREDClient.fetch_series()`):

| Column | Type | Source JSON Path |
|--------|------|------------------|
| `series_id` | str | Injected from request parameter |
| `date` | str | `observations[].date` |
| `value` | float/None | `observations[].value` (parsed from string; "." becomes None) |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 1: Create `src/api_clients/fred_client.py`

New API client following the patterns of `polygon_client.py` and `fmp_client.py` but simplified — FRED has very generous rate limits (120 req/min) and we only make 4 requests per day.

```python
# --------------------
# FRED API Client
# --------------------
# Handles: auth, retries, response parsing.
# Returns: pandas DataFrames. Never touches Snowflake.

import os
import time
from datetime import datetime
from threading import Lock

import pandas as pd
import requests

BASE_URL = "https://api.stlouisfed.org/fred"
MAX_RETRIES = 3
MIN_REQUEST_INTERVAL = 0.5  # Conservative; FRED allows 120 req/min

MACRO_SERIES = ["DFF", "DGS10", "DGS2", "BAMLH0A0HYM2"]


class FREDClient:

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ["FRED_API_KEY"]
        self._rate_limit_lock = Lock()
        self._last_request_time = time.time()

    def _get(self, url: str) -> requests.Response:
        for attempt in range(MAX_RETRIES):
            with self._rate_limit_lock:
                elapsed = time.time() - self._last_request_time
                if elapsed < MIN_REQUEST_INTERVAL:
                    time.sleep(MIN_REQUEST_INTERVAL - elapsed)
                response = requests.get(url, timeout=10)
                self._last_request_time = time.time()

            if response.status_code == 429:
                wait = min(2 ** attempt, 32)
                print(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue

            return response

        return response

    def fetch_series(
        self,
        series_ids: list[str],
        observation_start: str,
        observation_end: str,
    ) -> pd.DataFrame:
        """Fetch FRED time series observations for multiple series.

        Args:
            series_ids: List of FRED series IDs (e.g., ["DFF", "DGS10"]).
            observation_start: Start date (YYYY-MM-DD).
            observation_end: End date (YYYY-MM-DD).

        Returns:
            DataFrame with columns: series_id, date, value, extracted_at.
            Value is parsed to float; FRED's "." (missing) becomes None.
        """
        all_rows = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for series_id in series_ids:
            print(f"Fetching FRED series {series_id}: {observation_start} to {observation_end}...")
            url = (
                f"{BASE_URL}/series/observations"
                f"?series_id={series_id}"
                f"&api_key={self.api_key}"
                f"&file_type=json"
                f"&observation_start={observation_start}"
                f"&observation_end={observation_end}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  {series_id}: HTTP {response.status_code}")
                continue

            data = response.json()
            observations = data.get("observations", [])

            count = 0
            for obs in observations:
                raw_value = obs.get("value", ".")
                # FRED returns "." for missing data (weekends, holidays)
                value = None
                if raw_value != ".":
                    try:
                        value = float(raw_value)
                    except (ValueError, TypeError):
                        value = None

                all_rows.append({
                    "series_id": series_id,
                    "date": obs.get("date"),
                    "value": value,
                    "extracted_at": extracted_at,
                })
                count += 1

            print(f"  {series_id}: {count} observations")

        print(f"\nTotal: {len(all_rows)} observations across {len(series_ids)} series")
        return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()

    def fetch_macro_rates(
        self, observation_start: str, observation_end: str
    ) -> pd.DataFrame:
        """Convenience method: fetch all standard macro rate series."""
        return self.fetch_series(MACRO_SERIES, observation_start, observation_end)
```

### Step 2: Create `src/jobs/ingest_fred_macro_rates.py`

```python
import sys
import os
from dotenv import load_dotenv

from src.api_clients.fred_client import FREDClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_partition,
)
from src.utils.dates import today

TABLE = "sp500_macro_rates"


def run(run_date: str):
    print(f"Starting macro rates ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = FREDClient()
    df = client.fetch_macro_rates(run_date, run_date)

    if df.empty:
        print("No macro rate data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        series_id VARCHAR,
        date DATE,
        value FLOAT,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (series_id, date)
    )
    """

    fq_table = f"{schema}.{TABLE}"

    overwrite_partition(
        session=session,
        df=df,
        table_name=fq_table,
        partition_col="date",
        partition_value=run_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} macro rate observations to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 3: Create `src/jobs/ingest_fred_macro_rates_backfill.py`

```python
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.api_clients.fred_client import FREDClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_date_range,
)
from src.utils.dates import today

TABLE = "sp500_macro_rates"
DEFAULT_LOOKBACK_DAYS = 1826  # ~5 years


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS):
    end_date = datetime.strptime(run_date, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=lookback_days)

    print(f"Starting macro rates backfill: {start_date} to {end_date} ({lookback_days} days)...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = FREDClient()
    df = client.fetch_macro_rates(str(start_date), str(end_date))

    if df.empty:
        print("No macro rate data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        series_id VARCHAR,
        date DATE,
        value FLOAT,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (series_id, date)
    )
    """

    fq_table = f"{schema}.{TABLE}"

    overwrite_date_range(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=str(start_date),
        end_date=str(end_date),
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} macro rate observations to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
```

### Step 4: Create `dags/etl/fred_macro_rates_dag.py`

No sp500_lookup dependency — macro rates are independent.

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fred_macro_rates import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fred_macro_rates",
    default_args=default_args,
    description="Fetch daily macro interest rates from FRED (Fed Funds, 10Y, 2Y, HY OAS)",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fred", "daily", "macro"],
) as dag:

    ingest_macro_rates = PythonOperator(
        task_id="ingest_fred_macro_rates",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

### Step 5: Create `dags/etl/fred_macro_rates_backfill_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fred_macro_rates_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fred_macro_rates_backfill",
    default_args=default_args,
    description="Backfill 5 years of macro interest rates from FRED",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fred", "backfill", "macro"],
) as dag:

    backfill_macro_rates = PythonOperator(
        task_id="backfill_fred_macro_rates",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

### Step 6: Validate

```bash
astro dev parse
python -c "from src.api_clients.fred_client import FREDClient; c = FREDClient(); print(c.fetch_macro_rates('2026-02-01', '2026-02-28'))"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fred_client.py` | CREATE | New FRED API client |
| `src/jobs/ingest_fred_macro_rates.py` | CREATE | Daily macro rates job |
| `src/jobs/ingest_fred_macro_rates_backfill.py` | CREATE | 5-year backfill job |
| `dags/etl/fred_macro_rates_dag.py` | CREATE | Daily DAG (no sp500_lookup dependency) |
| `dags/etl/fred_macro_rates_backfill_dag.py` | CREATE | Backfill DAG |

## Functions and interfaces

### `fred_client.py`

```python
class FREDClient:
    def __init__(self, api_key: str = None):
        """Initialize with FRED_API_KEY from env or parameter."""
        ...

    def _get(self, url: str) -> requests.Response:
        """Rate-limited GET with retry (same pattern as Polygon/FMP)."""
        ...

    def fetch_series(
        self, series_ids: list[str], observation_start: str, observation_end: str
    ) -> pd.DataFrame:
        """Fetch observations for multiple FRED series.

        Returns DataFrame with columns: series_id, date, value, extracted_at.
        FRED's "." (missing data) is parsed to None.
        """
        ...

    def fetch_macro_rates(
        self, observation_start: str, observation_end: str
    ) -> pd.DataFrame:
        """Convenience: fetch DFF, DGS10, DGS2, BAMLH0A0HYM2."""
        ...
```

### Job functions

```python
# ingest_fred_macro_rates.py
def run(run_date: str) -> None:
    """Fetch and load macro rates for run_date."""
    ...

# ingest_fred_macro_rates_backfill.py
def run(run_date: str, lookback_days: int = 1826) -> None:
    """Backfill 5 years of macro rates."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fred_client.py` | New file. No existing files modified. |
| `requirements.txt` | No changes — `requests` and `pandas` already present. |
| `.env` | New env var `FRED_API_KEY` required. Must be added before running. |
| Airflow DAG registry | 2 new DAGs. No sp500_lookup dependency. |
| Snowflake schema | 1 new table. |
| FRED rate budget | 4 requests/day for daily. ~5,200 for 5-year backfill (4 series x 1,300 days with data). All within 120 req/min limit. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| `FRED_API_KEY` not set | `os.environ["FRED_API_KEY"]` raises `KeyError`. Clear error message. |
| FRED returns "." for value (weekend/holiday) | Parsed to `None`. Stored as NULL in FLOAT column. |
| FRED returns 429 (rate limit) | `_get()` retry with exponential backoff. Very unlikely with 4 requests. |
| FRED returns 400 (invalid series ID) | `response.status_code != 200` check. Logged and skipped. |
| Series not yet published for run_date (T+1 delay) | Empty observations array. No data written for that series/date. |
| Weekend/holiday run | FRED returns "." for most series on non-business days. Stored as NULL. |
| `BAMLH0A0HYM2` has different publication schedule | May have gaps. Stored as NULL for missing dates. |
| Backfill date range has no data (pre-series start) | Empty observations. No error. |

## Observability

- Per-series logging: series ID, observation count
- Total observation count across all series
- Expected runtime: ~2 seconds (4 requests at 0.5s/req)
- FRED is extremely fast and reliable

## Acceptance criteria

- [ ] `src/api_clients/fred_client.py` created following the client pattern (auth, rate limit, retry)
- [ ] `FREDClient.fetch_series()` returns DataFrame with correct columns
- [ ] `FREDClient.fetch_macro_rates()` returns data for all 4 series
- [ ] FRED "." values are correctly parsed to None (not stored as string ".")
- [ ] Daily job creates `sp500_macro_rates` table and populates it
- [ ] Backfill job populates 5 years of historical data
- [ ] Both DAGs parse without errors (`astro dev parse`)
- [ ] Neither DAG depends on sp500_lookup
- [ ] Backfill DAG has `schedule=None`
- [ ] `SELECT COUNT(DISTINCT series_id) FROM sp500_macro_rates` returns 4
- [ ] `FRED_API_KEY` environment variable is documented
- [ ] Running the same job twice produces no duplicate rows

## Follow-ups

- Phase 1+: Create dbt staging model `stg_fred_macro_rates.sql`
- Phase 1+: Compute 10Y-2Y spread in dbt intermediate layer
- Phase 1+: Market regime classification (rising rates, falling rates, inverted yield curve)
- Phase 1+: Sector sensitivity scoring based on rate environment
- Consider adding CPI, unemployment rate, GDP growth for broader macro context
- Consider adding FRED series metadata table for self-documenting reference
