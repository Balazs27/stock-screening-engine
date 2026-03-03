# Feature 06 — Dividends & Splits

## Goal

Ingest per-ticker historical dividend declarations and stock split events from FMP. Provides two raw tables enabling total return calculations, yield-based scoring, and price discontinuity flagging for technical indicators. Symbol changes are tracked via the existing Wikipedia S&P 500 lookup table.

## Why this matters

Dividends affect total return calculations and yield-based scoring. Splits cause price discontinuities that can corrupt technical indicators if not flagged. Without dividend data, the yield dimension is missing from composite scoring. Without split data, post-split price jumps may be misinterpreted as momentum signals.

## Scope

- Add `FMPClient.fetch_dividends()` method to `src/api_clients/fmp_client.py`
- Add `FMPClient.fetch_splits()` method to `src/api_clients/fmp_client.py`
- Create `src/jobs/ingest_fmp_dividends.py` — daily job
- Create `src/jobs/ingest_fmp_splits.py` — daily job
- Create `src/jobs/ingest_fmp_dividends_backfill.py` — 5-year backfill
- Create `src/jobs/ingest_fmp_splits_backfill.py` — 10-year backfill
- Create `dags/etl/fmp_dividends_dag.py` — daily DAG
- Create `dags/etl/fmp_splits_dag.py` — daily DAG
- Create `dags/etl/fmp_dividends_backfill_dag.py` — backfill DAG
- Create `dags/etl/fmp_splits_backfill_dag.py` — backfill DAG
- Raw tables: `sp500_dividends`, `sp500_splits`

## Out of scope

- Symbol change tracking (handled by existing `sp500_tickers_lookup` via Wikipedia)
- Total return computation in dbt (Phase 1+)
- Dividend yield scoring logic (Phase 1+)
- Split-adjusted price restatement (Polygon already provides adjusted prices)
- Forward dividend yield computation

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for dividends and splits endpoints, JSON schemas |
| `src/api_clients/fmp_client.py` | Existing FMP client patterns |
| `src/jobs/ingest_fmp_income_statement.py` | FMP daily job pattern using `overwrite_date_range()` |
| `src/jobs/ingest_polygon_prices_backfill.py` | Backfill job pattern |
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
- FMP `/stable/stock-dividend?symbol={ticker}&apikey={key}` — per-ticker dividend history
- FMP `/stable/historical-stock-split?symbol={ticker}&apikey={key}` — per-ticker split history

## Data contracts and schemas

### Raw table: `sp500_dividends`

**Grain:** (ticker, date) — one row per ex-dividend date per ticker.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_dividends (
    ticker VARCHAR,
    date DATE,
    adj_dividend FLOAT,
    dividend FLOAT,
    record_date DATE,
    payment_date DATE,
    declaration_date DATE,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### Raw table: `sp500_splits`

**Grain:** (ticker, date) — one row per split execution date per ticker.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_splits (
    ticker VARCHAR,
    date DATE,
    numerator FLOAT,
    denominator FLOAT,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### DataFrame schemas

**Dividends DataFrame:**

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `date` | str | `date` (ex-dividend date) |
| `adj_dividend` | float/None | `adjDividend` |
| `dividend` | float/None | `dividend` |
| `record_date` | str/None | `recordDate` |
| `payment_date` | str/None | `paymentDate` |
| `declaration_date` | str/None | `declarationDate` |
| `extracted_at` | str | Generated at fetch time |

**Splits DataFrame:**

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `date` | str | `date` |
| `numerator` | float/None | `numerator` |
| `denominator` | float/None | `denominator` |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 1: Add `fetch_dividends()` to FMPClient

```python
def fetch_dividends(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch historical dividend data for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/stock-dividend"
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
                "adj_dividend": r.get("adjDividend"),
                "dividend": r.get("dividend"),
                "record_date": r.get("recordDate"),
                "payment_date": r.get("paymentDate"),
                "declaration_date": r.get("declarationDate"),
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="dividends")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 2: Add `fetch_splits()` to FMPClient

```python
def fetch_splits(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch historical stock split data for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/historical-stock-split"
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
                "numerator": r.get("numerator"),
                "denominator": r.get("denominator"),
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="splits")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 3: Create `src/jobs/ingest_fmp_dividends.py`

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
TABLE = "sp500_dividends"


def run(run_date: str):
    print(f"Starting S&P 500 dividends ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_dividends(tickers)

    if df.empty:
        print("No dividend data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        adj_dividend FLOAT,
        dividend FLOAT,
        record_date DATE,
        payment_date DATE,
        declaration_date DATE,
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

    print(f"Successfully wrote {len(df)} dividend records to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 4: Create `src/jobs/ingest_fmp_splits.py`

Same pattern as dividends but for splits table.

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
TABLE = "sp500_splits"


def run(run_date: str):
    print(f"Starting S&P 500 splits ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_splits(tickers)

    if df.empty:
        print("No split data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        numerator FLOAT,
        denominator FLOAT,
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

    print(f"Successfully wrote {len(df)} split records to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 5: Create backfill jobs

- `src/jobs/ingest_fmp_dividends_backfill.py` — identical to daily job (FMP returns full history)
- `src/jobs/ingest_fmp_splits_backfill.py` — identical to daily job (FMP returns full history)

### Step 6: Create daily DAGs

**`dags/etl/fmp_dividends_dag.py`:**
```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_dividends import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_dividends",
    default_args=default_args,
    description="Fetch S&P 500 dividend history from FMP",
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

    ingest_dividends = PythonOperator(
        task_id="ingest_fmp_dividends",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_dividends
```

**`dags/etl/fmp_splits_dag.py`:**
- `dag_id="fmp_splits"`
- Imports from `src.jobs.ingest_fmp_splits`
- Task id: `"ingest_fmp_splits"`
- Same structure as dividends DAG

### Step 7: Create backfill DAGs

**`dags/etl/fmp_dividends_backfill_dag.py`:**
```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_dividends_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fmp_dividends_backfill",
    default_args=default_args,
    description="Backfill S&P 500 dividend history from FMP",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "backfill"],
) as dag:

    backfill_dividends = PythonOperator(
        task_id="backfill_fmp_dividends",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

**`dags/etl/fmp_splits_backfill_dag.py`:**
- `dag_id="fmp_splits_backfill"`
- Same structure as dividends backfill

### Step 8: Validate

```bash
astro dev parse
python -c "from src.jobs.ingest_fmp_dividends import run; run('2026-02-28')"
python -c "from src.jobs.ingest_fmp_splits import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fmp_client.py` | EDIT | Add `fetch_dividends()` and `fetch_splits()` methods |
| `src/jobs/ingest_fmp_dividends.py` | CREATE | Daily dividends job |
| `src/jobs/ingest_fmp_splits.py` | CREATE | Daily splits job |
| `src/jobs/ingest_fmp_dividends_backfill.py` | CREATE | Backfill dividends job |
| `src/jobs/ingest_fmp_splits_backfill.py` | CREATE | Backfill splits job |
| `dags/etl/fmp_dividends_dag.py` | CREATE | Daily DAG for dividends |
| `dags/etl/fmp_splits_dag.py` | CREATE | Daily DAG for splits |
| `dags/etl/fmp_dividends_backfill_dag.py` | CREATE | Backfill DAG for dividends |
| `dags/etl/fmp_splits_backfill_dag.py` | CREATE | Backfill DAG for splits |

## Functions and interfaces

### `fmp_client.py` — new methods

```python
def fetch_dividends(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch historical dividend data for a list of tickers.

    Returns:
        DataFrame with columns: ticker, date, adj_dividend, dividend,
        record_date, payment_date, declaration_date, extracted_at.
    """
    ...

def fetch_splits(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch historical stock split data for a list of tickers.

    Returns:
        DataFrame with columns: ticker, date, numerator, denominator,
        extracted_at.
    """
    ...
```

### Job functions

```python
# ingest_fmp_dividends.py / ingest_fmp_dividends_backfill.py
def run(run_date: str) -> None: ...

# ingest_fmp_splits.py / ingest_fmp_splits_backfill.py
def run(run_date: str) -> None: ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fmp_client.py` | Adding 2 methods. No existing signatures change. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_date_range()`. |
| Airflow DAG registry | 4 new DAGs registered. |
| Snowflake schema | 2 new tables created. |
| FMP rate budget | +1,000 requests/day (~1.7 min). |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| Ticker has never paid a dividend | FMP returns empty array; no rows for that ticker. |
| Ticker has never split | FMP returns empty array; no rows for that ticker. |
| `record_date` or `payment_date` is null | Stored as NULL in DATE column. Common for pending dividends. |
| `adj_dividend` differs from `dividend` | Both stored; `adj_dividend` accounts for subsequent splits. |
| Reverse split (numerator < denominator) | Stored as-is. Example: 1-for-10 = numerator=1, denominator=10. |
| Forward split (numerator > denominator) | Stored as-is. Example: 4-for-1 = numerator=4, denominator=1. |
| Special/extra dividends | Stored as regular dividend rows. No type distinction in FMP response. |
| Duplicate (ticker, date) for same-day dividend and split | Separate tables, so no conflict. |

## Observability

- `_fetch_batch()` logs progress every 50 tickers
- Final row count and date range printed for each table
- Expected runtime: ~1,000 requests at 0.1s/req = ~1.7 min

## Acceptance criteria

- [ ] `FMPClient.fetch_dividends()` returns DataFrame with correct columns
- [ ] `FMPClient.fetch_splits()` returns DataFrame with correct columns
- [ ] Daily and backfill jobs create and populate both tables
- [ ] All 4 DAGs parse without errors (`astro dev parse`)
- [ ] 2 daily DAGs are gated on `sp500_lookup`
- [ ] 2 backfill DAGs have `schedule=None`
- [ ] Running the same job twice produces no duplicate rows
- [ ] `sp500_dividends` contains records for dividend-paying tickers
- [ ] `sp500_splits` contains records (may be sparse — splits are rare)
- [ ] `numerator` and `denominator` columns correctly represent split ratios

## Follow-ups

- Phase 1+: Create dbt staging models for dividends and splits
- Phase 1+: Compute forward/trailing dividend yield in dbt intermediate layer
- Phase 1+: Add split flag to technical indicators for discontinuity handling
- Consider adding dividend type classification (regular, special, interim) if FMP exposes it
- Monitor for symbol changes via `sp500_tickers_lookup` diff between consecutive dates
