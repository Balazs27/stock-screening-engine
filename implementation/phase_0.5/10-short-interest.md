# Feature 10 — Short Interest (TENTATIVE)

## Goal

Ingest short interest data (short interest as percentage of float, days-to-cover) from FMP for all S&P 500 tickers. **This feature is TENTATIVE** — the FMP endpoint must be tested for availability before implementation proceeds. If the endpoint returns 403/404, this feature is deprioritized and documented as unavailable.

## Why this matters

High short interest is both a risk signal (crowding, potential squeeze) and a contrarian buy signal when combined with positive catalysts. It adds a crowding dimension to risk overlays. Days-to-cover indicates how long it would take shorts to unwind, signaling squeeze potential.

## Scope

- **Availability gate:** Test FMP `/stable/short-interest?symbol={ticker}&apikey={key}` before proceeding
- If available:
  - Add `FMPClient.fetch_short_interest()` method to `src/api_clients/fmp_client.py`
  - Create `src/jobs/ingest_fmp_short_interest.py` — daily job
  - Create `src/jobs/ingest_fmp_short_interest_backfill.py` — 5-year backfill
  - Create `dags/etl/fmp_short_interest_dag.py` — daily DAG
  - Create `dags/etl/fmp_short_interest_backfill_dag.py` — backfill DAG
  - Raw table: `sp500_short_interest`
- If unavailable:
  - Document as deprioritized with FINRA alternative noted
  - No code changes

## Out of scope

- FINRA short interest file parsing (alternative if FMP unavailable)
- Short squeeze detection logic (Phase 3)
- Short interest scoring (Phase 1+)
- dbt staging/intermediate/mart models (Phase 1+)
- Real-time short interest data

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for short interest endpoint, JSON schema |
| `src/api_clients/fmp_client.py` | Existing FMP client patterns |
| `src/jobs/ingest_fmp_income_statement.py` | FMP daily job pattern |
| `dags/etl/fmp_income_statement_dag.py` | Daily FMP DAG pattern |
| `dags/etl/polygon_prices_backfill_dag.py` | Backfill DAG pattern |
| `src/loaders/snowflake_loader.py` | Loader API |

## Dependencies

### Upstream features
- None — this is independent.

### Libraries/packages
- No new packages required.

### Environment variables
- `FMP_API_KEY` — already used
- `STUDENT_SCHEMA` — already used
- `SNOWFLAKE_*` — already used

### APIs/data sources
- FMP `/stable/short-interest?symbol={ticker}&apikey={key}` — per-ticker (availability uncertain)

## Data contracts and schemas

### Availability gate procedure

**Before writing any production code,** run this manual test:

```python
import os
import requests

api_key = os.environ["FMP_API_KEY"]
test_ticker = "AAPL"
url = f"https://financialmodelingprep.com/stable/short-interest?symbol={test_ticker}&apikey={api_key}"
response = requests.get(url, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")
```

**Decision matrix:**

| Response | Action |
|----------|--------|
| 200 + valid JSON array | Proceed with implementation |
| 200 + empty array `[]` | Proceed but note limited data |
| 403 Forbidden | **STOP** — endpoint not available on current plan. Document as deprioritized. |
| 404 Not Found | **STOP** — endpoint does not exist. Document as deprioritized. |
| 200 + `{"error": ...}` | **STOP** — endpoint requires higher plan tier. Document as deprioritized. |

### Raw table: `sp500_short_interest` (if available)

**Grain:** (ticker, date) — one row per ticker per settlement date.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_short_interest (
    ticker VARCHAR,
    date DATE,
    short_interest NUMBER,
    short_interest_change_percent FLOAT,
    float_short FLOAT,
    days_to_cover FLOAT,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### DataFrame schema (if available)

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `date` | str | `date` |
| `short_interest` | int/None | `shortInterest` |
| `short_interest_change_percent` | float/None | `shortInterestChangePercent` |
| `float_short` | float/None | `floatShort` |
| `days_to_cover` | float/None | `daysToCover` |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 0: Availability gate (MUST DO FIRST)

Run the availability gate test described above. If the endpoint is not available, skip all subsequent steps and:

1. Create a note in `.claude/memory/MEMORY.md`:
   ```
   ## Entry N: FMP Short Interest Endpoint Unavailable
   **Symptom:** FMP `/stable/short-interest` returns 403/404.
   **Cause:** Endpoint requires higher FMP plan tier or does not exist.
   **Solution:** Deprioritized. Alternative: FINRA bi-monthly short interest files.
   ```
2. Mark Feature 10 as "Unavailable" in the checklist
3. Stop implementation

### Step 1: Add `fetch_short_interest()` to FMPClient (if available)

```python
def fetch_short_interest(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch short interest data for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/short-interest"
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
                "short_interest": r.get("shortInterest"),
                "short_interest_change_percent": r.get("shortInterestChangePercent"),
                "float_short": r.get("floatShort"),
                "days_to_cover": r.get("daysToCover"),
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="short interest")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 2: Create `src/jobs/ingest_fmp_short_interest.py` (if available)

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
TABLE = "sp500_short_interest"


def run(run_date: str):
    print(f"Starting S&P 500 short interest ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_short_interest(tickers)

    if df.empty:
        print("No short interest data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        short_interest NUMBER,
        short_interest_change_percent FLOAT,
        float_short FLOAT,
        days_to_cover FLOAT,
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

    print(f"Successfully wrote {len(df)} short interest records to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 3: Create `src/jobs/ingest_fmp_short_interest_backfill.py` (if available)

Identical to daily job — FMP returns historical data by default.

### Step 4: Create `dags/etl/fmp_short_interest_dag.py` (if available)

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_short_interest import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_short_interest",
    default_args=default_args,
    description="Fetch S&P 500 short interest data from FMP",
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

    ingest_short_interest = PythonOperator(
        task_id="ingest_fmp_short_interest",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_short_interest
```

### Step 5: Create `dags/etl/fmp_short_interest_backfill_dag.py` (if available)

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_short_interest_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fmp_short_interest_backfill",
    default_args=default_args,
    description="Backfill S&P 500 short interest data from FMP",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "backfill"],
) as dag:

    backfill_short_interest = PythonOperator(
        task_id="backfill_fmp_short_interest",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

### Step 6: Validate (if available)

```bash
astro dev parse
python -c "from src.jobs.ingest_fmp_short_interest import run; run('2026-02-28')"
```

## File-level change list

**If endpoint is available:**

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fmp_client.py` | EDIT | Add `fetch_short_interest()` method |
| `src/jobs/ingest_fmp_short_interest.py` | CREATE | Daily short interest job |
| `src/jobs/ingest_fmp_short_interest_backfill.py` | CREATE | Backfill short interest job |
| `dags/etl/fmp_short_interest_dag.py` | CREATE | Daily DAG |
| `dags/etl/fmp_short_interest_backfill_dag.py` | CREATE | Backfill DAG |

**If endpoint is NOT available:**

| File | Action | Description |
|------|--------|-------------|
| `.claude/memory/MEMORY.md` | EDIT | Add unavailability entry |
| `implementation/phase_0.5/checklist.md` | EDIT | Mark Feature 10 as "Unavailable" |

## Functions and interfaces

### `fmp_client.py` — new method (if available)

```python
def fetch_short_interest(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch short interest data for a list of tickers.

    Args:
        tickers: List of ticker symbols.

    Returns:
        DataFrame with columns: ticker, date, short_interest,
        short_interest_change_percent, float_short, days_to_cover,
        extracted_at. Empty DataFrame if no data.
    """
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fmp_client.py` | Adding 1 method (if available). No existing signatures change. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_date_range()`. |
| Airflow DAG registry | 2 new DAGs (if available). |
| Snowflake schema | 1 new table (if available). |
| FMP rate budget | +500 requests/day (~50 seconds at 0.1s/req). |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| Endpoint returns 403/404 | **STOP implementation.** Document as unavailable. |
| Endpoint returns data but `float_short` is always null | Partial data; proceed but note in MEMORY.md. |
| Short interest data is bi-monthly (not daily) | Stored as-is. FINRA publishes 2x/month. Gaps expected. |
| `days_to_cover` is null or 0 | Stored as-is. May indicate low short interest. |
| `short_interest` is 0 for some tickers | Valid; not all S&P 500 stocks are heavily shorted. |
| Data has different settlement dates per ticker | Stored as-is. Dates may not align across tickers. |

## Observability

- Availability gate test result logged
- If proceeding: `_fetch_batch()` progress logging
- Expected runtime: ~500 requests at 0.1s/req = ~50 seconds

## Acceptance criteria

### If endpoint is available:
- [ ] Availability gate passed (200 + valid data for test ticker)
- [ ] `FMPClient.fetch_short_interest()` returns DataFrame with correct columns
- [ ] Daily and backfill jobs create and populate `sp500_short_interest`
- [ ] Both DAGs parse without errors
- [ ] Daily DAG is gated on `sp500_lookup`
- [ ] Backfill DAG has `schedule=None`
- [ ] Running the same job twice produces no duplicate rows

### If endpoint is NOT available:
- [ ] Unavailability documented in `.claude/memory/MEMORY.md`
- [ ] Feature 10 marked as "Unavailable" in checklist
- [ ] FINRA alternative noted for future consideration
- [ ] No production code changes committed

## Follow-ups

- If available: Phase 1+ staging model and short squeeze scoring
- If unavailable: Evaluate FINRA short interest file download approach
- If unavailable: Evaluate alternative data vendors (Ortex, S3 Partners) for paid short interest data
- Consider short interest percentile ranking within S&P 500 for relative scoring
