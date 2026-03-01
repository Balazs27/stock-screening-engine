# Feature 09 — Insider Trades & Institutional Holdings

## Goal

Ingest SEC Form 4 insider transactions (buys/sells by officers, directors, 10%+ holders) and quarterly 13F institutional holding snapshots from FMP. Provides two raw tables enabling ownership-based sentiment scoring and smart-money conviction signals.

## Why this matters

Insider buying is a strong bullish signal — insiders risk their own capital when they buy. Institutional ownership changes indicate smart-money conviction. Both add an ownership dimension to the scoring model that is orthogonal to technical and fundamental signals, improving composite ranking quality.

## Scope

- Add `FMPClient.fetch_insider_trades()` method to `src/api_clients/fmp_client.py`
- Add `FMPClient.fetch_institutional_holders()` method to `src/api_clients/fmp_client.py`
- Create `src/jobs/ingest_fmp_insider_trades.py` — daily job
- Create `src/jobs/ingest_fmp_institutional_holders.py` — daily job
- Create `src/jobs/ingest_fmp_insider_trades_backfill.py` — 5-year backfill
- Create `src/jobs/ingest_fmp_institutional_holders_backfill.py` — 5-year backfill
- Create `dags/etl/fmp_insider_trades_dag.py` — daily DAG
- Create `dags/etl/fmp_institutional_holders_dag.py` — daily DAG
- Create `dags/etl/fmp_insider_trades_backfill_dag.py` — backfill DAG
- Create `dags/etl/fmp_institutional_holders_backfill_dag.py` — backfill DAG
- Raw tables: `sp500_insider_trades`, `sp500_institutional_holders`

## Out of scope

- Insider trade aggregation or scoring (Phase 3)
- Institutional ownership percentage computation (Phase 1+)
- SEC EDGAR filing parsing (FMP abstracts this)
- 13F portfolio reconstruction
- dbt staging/intermediate/mart models (Phase 1+)

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for insider trades and institutional holdings endpoints |
| `src/api_clients/fmp_client.py` | Existing FMP client patterns |
| `src/jobs/ingest_fmp_income_statement.py` | FMP daily job pattern |
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
- FMP `/stable/insider-trading?symbol={ticker}&limit=100&apikey={key}` — per-ticker
- FMP `/stable/institutional-holder?symbol={ticker}&apikey={key}` — per-ticker

## Data contracts and schemas

### Raw table: `sp500_insider_trades`

**Grain:** (ticker, filing_date, reporting_name, transaction_type) — one row per insider per transaction.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_insider_trades (
    ticker VARCHAR,
    filing_date DATE,
    transaction_date DATE,
    reporting_name VARCHAR,
    transaction_type VARCHAR,
    securities_owned NUMBER,
    securities_transacted NUMBER,
    price FLOAT,
    type_of_owner VARCHAR,
    link VARCHAR,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, filing_date, reporting_name, transaction_type)
)
```

### Raw table: `sp500_institutional_holders`

**Grain:** (ticker, holder, date_reported) — one row per holder per ticker per quarter.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_institutional_holders (
    ticker VARCHAR,
    holder VARCHAR,
    shares NUMBER,
    date_reported DATE,
    change NUMBER,
    change_percentage FLOAT,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, holder, date_reported)
)
```

### DataFrame schemas

**Insider Trades DataFrame:**

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `filing_date` | str | `filingDate` |
| `transaction_date` | str | `transactionDate` |
| `reporting_name` | str | `reportingName` |
| `transaction_type` | str | `transactionType` |
| `securities_owned` | int/None | `securitiesOwned` |
| `securities_transacted` | int/None | `securitiesTransacted` |
| `price` | float/None | `price` |
| `type_of_owner` | str/None | `typeOfOwner` |
| `link` | str/None | `link` |
| `extracted_at` | str | Generated at fetch time |

**Institutional Holders DataFrame:**

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | Injected from request |
| `holder` | str | `holder` |
| `shares` | int/None | `shares` |
| `date_reported` | str | `dateReported` |
| `change` | int/None | `change` |
| `change_percentage` | float/None | `changePercentage` |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 1: Add `fetch_insider_trades()` to FMPClient

```python
def fetch_insider_trades(
    self, tickers: list[str], limit: int = 100
) -> pd.DataFrame:
    """Fetch insider trading transactions for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/insider-trading"
            f"?symbol={ticker}"
            f"&limit={limit}"
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
                "filing_date": r.get("filingDate"),
                "transaction_date": r.get("transactionDate"),
                "reporting_name": r.get("reportingName"),
                "transaction_type": r.get("transactionType"),
                "securities_owned": r.get("securitiesOwned"),
                "securities_transacted": r.get("securitiesTransacted"),
                "price": r.get("price"),
                "type_of_owner": r.get("typeOfOwner"),
                "link": r.get("link"),
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="insider trades")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 2: Add `fetch_institutional_holders()` to FMPClient

```python
def fetch_institutional_holders(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch institutional holder snapshots for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/institutional-holder"
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
                "holder": r.get("holder"),
                "shares": r.get("shares"),
                "date_reported": r.get("dateReported"),
                "change": r.get("change"),
                "change_percentage": r.get("changePercentage"),
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="institutional holders")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 3: Create `src/jobs/ingest_fmp_insider_trades.py`

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
TABLE = "sp500_insider_trades"


def run(run_date: str):
    print(f"Starting S&P 500 insider trades ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_insider_trades(tickers)

    if df.empty:
        print("No insider trades data fetched.")
        session.close()
        return

    start_date = df["filing_date"].min()
    end_date = df["filing_date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        filing_date DATE,
        transaction_date DATE,
        reporting_name VARCHAR,
        transaction_type VARCHAR,
        securities_owned NUMBER,
        securities_transacted NUMBER,
        price FLOAT,
        type_of_owner VARCHAR,
        link VARCHAR,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, filing_date, reporting_name, transaction_type)
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

    print(f"Successfully wrote {len(df)} insider trades to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

**Note on `overwrite_date_range`:** Insider trades use `filing_date` as the date column for the DELETE range. The loader's `overwrite_date_range()` deletes by `date` column by default. The implementor must ensure the DELETE statement references `filing_date`:
```python
session.sql(
    f"DELETE FROM {fq_table} WHERE filing_date BETWEEN '{start_date}' AND '{end_date}'"
).collect()
```

If `overwrite_date_range()` hardcodes `date` as the column name, either:
1. Add a `date` column derived from `filing_date` and use standard loader, or
2. Write custom delete+insert logic in the job

The recommended approach is to add a `date` column set to `filing_date` value, keeping the loader interface consistent.

### Step 4: Create `src/jobs/ingest_fmp_institutional_holders.py`

Similar pattern. Use `date_reported` as the date reference.

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
TABLE = "sp500_institutional_holders"


def run(run_date: str):
    print(f"Starting S&P 500 institutional holders ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_institutional_holders(tickers)

    if df.empty:
        print("No institutional holders data fetched.")
        session.close()
        return

    start_date = df["date_reported"].min()
    end_date = df["date_reported"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        holder VARCHAR,
        shares NUMBER,
        date_reported DATE,
        change NUMBER,
        change_percentage FLOAT,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, holder, date_reported)
    )
    """

    fq_table = f"{schema}.{TABLE}"

    # Custom delete+insert since date column is date_reported, not date
    session.sql(create_table_sql).collect()
    session.sql(
        f"DELETE FROM {fq_table} WHERE date_reported BETWEEN '{start_date}' AND '{end_date}'"
    ).collect()
    session.create_dataframe(df).write.mode("append").save_as_table(fq_table)

    print(f"Successfully wrote {len(df)} institutional holder records to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 5: Create backfill jobs

- `src/jobs/ingest_fmp_insider_trades_backfill.py` — identical to daily (FMP returns full history with `limit=100`)
- `src/jobs/ingest_fmp_institutional_holders_backfill.py` — identical to daily (FMP returns all quarters)

### Step 6: Create daily DAGs

**`dags/etl/fmp_insider_trades_dag.py`:**
```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_insider_trades import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_insider_trades",
    default_args=default_args,
    description="Fetch S&P 500 insider trading transactions from FMP",
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

    ingest_insider_trades = PythonOperator(
        task_id="ingest_fmp_insider_trades",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_insider_trades
```

**`dags/etl/fmp_institutional_holders_dag.py`:**
- `dag_id="fmp_institutional_holders"`
- Imports from `src.jobs.ingest_fmp_institutional_holders`
- Same structure with ExternalTaskSensor

### Step 7: Create backfill DAGs

**`dags/etl/fmp_insider_trades_backfill_dag.py`:**
```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_insider_trades_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fmp_insider_trades_backfill",
    default_args=default_args,
    description="Backfill S&P 500 insider trading transactions from FMP",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "backfill"],
) as dag:

    backfill_insider_trades = PythonOperator(
        task_id="backfill_fmp_insider_trades",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

**`dags/etl/fmp_institutional_holders_backfill_dag.py`:**
- `dag_id="fmp_institutional_holders_backfill"`
- Same structure

### Step 8: Validate

```bash
astro dev parse
python -c "from src.jobs.ingest_fmp_insider_trades import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fmp_client.py` | EDIT | Add `fetch_insider_trades()` and `fetch_institutional_holders()` |
| `src/jobs/ingest_fmp_insider_trades.py` | CREATE | Daily insider trades job |
| `src/jobs/ingest_fmp_institutional_holders.py` | CREATE | Daily institutional holders job |
| `src/jobs/ingest_fmp_insider_trades_backfill.py` | CREATE | Backfill insider trades job |
| `src/jobs/ingest_fmp_institutional_holders_backfill.py` | CREATE | Backfill institutional holders job |
| `dags/etl/fmp_insider_trades_dag.py` | CREATE | Daily DAG |
| `dags/etl/fmp_institutional_holders_dag.py` | CREATE | Daily DAG |
| `dags/etl/fmp_insider_trades_backfill_dag.py` | CREATE | Backfill DAG |
| `dags/etl/fmp_institutional_holders_backfill_dag.py` | CREATE | Backfill DAG |

## Functions and interfaces

### `fmp_client.py` — new methods

```python
def fetch_insider_trades(
    self, tickers: list[str], limit: int = 100
) -> pd.DataFrame:
    """Fetch insider trading transactions for a list of tickers.

    Args:
        tickers: List of ticker symbols.
        limit: Max transactions per ticker (default 100).

    Returns:
        DataFrame with columns: ticker, filing_date, transaction_date,
        reporting_name, transaction_type, securities_owned,
        securities_transacted, price, type_of_owner, link, extracted_at.
    """
    ...

def fetch_institutional_holders(self, tickers: list[str]) -> pd.DataFrame:
    """Fetch institutional holder snapshots for a list of tickers.

    Args:
        tickers: List of ticker symbols.

    Returns:
        DataFrame with columns: ticker, holder, shares, date_reported,
        change, change_percentage, extracted_at.
    """
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fmp_client.py` | Adding 2 methods. No existing signatures change. |
| `src/loaders/snowflake_loader.py` | Institutional holders job uses custom delete+insert (not standard `overwrite_date_range()`) because date column is `date_reported`. Consider adding a `date_column` parameter to `overwrite_date_range()` as a future enhancement. |
| Airflow DAG registry | 4 new DAGs. |
| Snowflake schema | 2 new tables. |
| FMP rate budget | +1,000 requests/day (~1.7 min). |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| Ticker has no insider trades | FMP returns empty array. No rows for that ticker. |
| Ticker has no institutional holders | FMP returns empty array. No rows for that ticker. |
| `price` is null (options exercise, gift) | Stored as NULL. Common for non-market transactions. |
| `transaction_type` has many variants | Stored as-is. Common values: "P-Purchase", "S-Sale", "A-Award", "M-Exercise". |
| `type_of_owner` has many variants | Stored as-is. Common: "officer", "director", "10percent owner", "other". |
| `change_percentage` is null for new position | Stored as NULL. First 13F filing has no prior comparison. |
| Multiple insiders with same (ticker, filing_date) | Different `reporting_name` values. Composite PK handles this. |
| Duplicate institutional holder entries | Composite PK (ticker, holder, date_reported) ensures uniqueness. |
| Very large holder lists (>100 institutions per ticker) | All stored. Volume is manageable (~50K total rows for 500 tickers). |

## Observability

- `_fetch_batch()` logs progress every 50 tickers for each endpoint
- Final row count and date range printed for each table
- Expected runtime: ~1,000 requests at 0.1s/req = ~1.7 min

## Acceptance criteria

- [ ] `FMPClient.fetch_insider_trades()` returns DataFrame with correct columns
- [ ] `FMPClient.fetch_institutional_holders()` returns DataFrame with correct columns
- [ ] Daily and backfill jobs create and populate both tables
- [ ] All 4 DAGs parse without errors (`astro dev parse`)
- [ ] 2 daily DAGs are gated on `sp500_lookup`
- [ ] 2 backfill DAGs have `schedule=None`
- [ ] Running the same job twice produces no duplicate rows
- [ ] `sp500_insider_trades` contains records with valid `transaction_type` values
- [ ] `sp500_institutional_holders` contains records with valid `holder` names
- [ ] Date columns are correctly used for delete range in each table

## Follow-ups

- Phase 1+: Create dbt staging models for both tables
- Phase 3: Insider buy/sell ratio scoring (net insider buying as bullish signal)
- Phase 3: Institutional ownership change detection (13F quarter-over-quarter)
- Consider increasing `limit` parameter for insider trades if 100 is insufficient for active tickers
- Consider adding `overwrite_date_range()` variant that accepts custom date column name
- Add data quality check: insider trade `price` should be positive when not null
