# Feature 02 — Ticker Overview / Market Cap

## Goal

Ingest per-ticker reference data from Polygon's `/v3/reference/tickers/{ticker}` endpoint, capturing market capitalization, shares outstanding, SIC classification, and company metadata. Provides a daily snapshot table that enables size-based scoring, valuation multiples, and index weighting computations.

## Why this matters

Market cap is required for valuation multiples (P/E, P/B, EV/EBITDA), size-based scoring (large-cap vs. mid-cap behavior), and proper index weighting. Shares outstanding are needed to compute per-share metrics from raw financial statements. Without this data, the scoring engine cannot distinguish a $3T company from a $10B company.

## Scope

- Add `PolygonClient.fetch_ticker_details()` method to `src/api_clients/polygon_client.py`
- Create `src/jobs/ingest_polygon_ticker_details.py` — daily job (per-ticker)
- Create `dags/etl/polygon_ticker_details_dag.py` — daily DAG gated on `sp500_lookup`
- Raw table: `sp500_ticker_details`
- NO backfill job — this is a point-in-time snapshot; historical market cap can be derived from price x shares

## Out of scope

- dbt staging/intermediate/mart models for ticker details (Phase 1+)
- Historical market cap reconstruction from price x shares outstanding
- Backfill job/DAG (not applicable for point-in-time snapshots)
- Company description text analysis

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for ticker overview endpoint, JSON schema, grain definition |
| `src/api_clients/polygon_client.py` | Existing Polygon client patterns: `_get()`, `_fetch_batch()`, rate limiting |
| `src/jobs/ingest_polygon_prices.py` | Polygon daily job pattern: session setup, ticker lookup, client call, DDL, loader call |
| `src/loaders/snowflake_loader.py` | Loader API: `overwrite_partition()` |
| `dags/etl/polygon_daily_prices_dag.py` | Daily Polygon DAG pattern: ExternalTaskSensor + PythonOperator |
| `CLAUDE.md` | Forbidden actions, separation of concerns |
| `.claude/rules/analytics-architecture.md` | Layer boundaries, naming conventions |

## Dependencies

### Upstream features
- None — this is independent.

### Libraries/packages
- `requests` — already in `requirements.txt`
- `pandas` — already in `requirements.txt`
- `snowflake-snowpark-python` — already in `requirements.txt`
- No new packages required.

### Environment variables
- `POLYGON_API_KEY` — already used by existing Polygon jobs
- `STUDENT_SCHEMA` — already used by all jobs
- `SNOWFLAKE_*` — already used by all jobs

### APIs/data sources
- Polygon `/v3/reference/tickers/{ticker}?apiKey={key}` — per-ticker reference endpoint

## Data contracts and schemas

### Raw table: `sp500_ticker_details`

**Grain:** (ticker, date) — one row per ticker per snapshot date.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_ticker_details (
    ticker VARCHAR,
    name VARCHAR,
    market VARCHAR,
    locale VARCHAR,
    primary_exchange VARCHAR,
    type VARCHAR,
    active BOOLEAN,
    currency_name VARCHAR,
    cik VARCHAR,
    market_cap NUMBER,
    share_class_shares_outstanding NUMBER,
    weighted_shares_outstanding NUMBER,
    list_date DATE,
    sic_code VARCHAR,
    sic_description VARCHAR,
    total_employees NUMBER,
    homepage_url VARCHAR,
    description VARCHAR,
    date DATE,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### DataFrame schema

**Ticker Details DataFrame** (returned by `fetch_ticker_details()`):

| Column | Type | Source JSON Path |
|--------|------|------------------|
| `ticker` | str | `results.ticker` |
| `name` | str/None | `results.name` |
| `market` | str/None | `results.market` |
| `locale` | str/None | `results.locale` |
| `primary_exchange` | str/None | `results.primary_exchange` |
| `type` | str/None | `results.type` |
| `active` | bool/None | `results.active` |
| `currency_name` | str/None | `results.currency_name` |
| `cik` | str/None | `results.cik` |
| `market_cap` | float/None | `results.market_cap` |
| `share_class_shares_outstanding` | int/None | `results.share_class_shares_outstanding` |
| `weighted_shares_outstanding` | int/None | `results.weighted_shares_outstanding` |
| `list_date` | str/None | `results.list_date` |
| `sic_code` | str/None | `results.sic_code` |
| `sic_description` | str/None | `results.sic_description` |
| `total_employees` | int/None | `results.total_employees` |
| `homepage_url` | str/None | `results.homepage_url` |
| `description` | str/None | `results.description` |
| `date` | str | Injected from run_date parameter |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 1: Add `fetch_ticker_details()` to PolygonClient

Add a new method to `src/api_clients/polygon_client.py`. **Critical difference from other methods:** The response is a single object under `results`, NOT an array. The method must extract `results` and return one row per ticker.

```python
def fetch_ticker_details(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch ticker details (market cap, shares outstanding) for a list of tickers.

    Note: Unlike other Polygon endpoints, /v3/reference/tickers/{ticker}
    returns a single object (not an array). Each ticker yields exactly one row.
    """

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/v3/reference/tickers/{ticker}"
            f"?apiKey={self.api_key}"
        )
        response = self._get(url)
        if response.status_code != 200:
            return []
        data = response.json()
        if data.get("status") != "OK" or not data.get("results"):
            return []
        r = data["results"]
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return [{
            "ticker": r.get("ticker", ticker),
            "name": r.get("name"),
            "market": r.get("market"),
            "locale": r.get("locale"),
            "primary_exchange": r.get("primary_exchange"),
            "type": r.get("type"),
            "active": r.get("active"),
            "currency_name": r.get("currency_name"),
            "cik": r.get("cik"),
            "market_cap": r.get("market_cap"),
            "share_class_shares_outstanding": r.get("share_class_shares_outstanding"),
            "weighted_shares_outstanding": r.get("weighted_shares_outstanding"),
            "list_date": r.get("list_date"),
            "sic_code": r.get("sic_code"),
            "sic_description": r.get("sic_description"),
            "total_employees": r.get("total_employees"),
            "homepage_url": r.get("homepage_url"),
            "description": r.get("description"),
            "date": run_date,
            "extracted_at": extracted_at,
        }]

    results = self._fetch_batch(tickers, _fetch_one, label="ticker details")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 2: Create `src/jobs/ingest_polygon_ticker_details.py`

```python
import sys
import os
from dotenv import load_dotenv

from src.api_clients.polygon_client import PolygonClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_partition,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_ticker_details"


def run(run_date: str):
    print(f"Starting S&P 500 ticker details ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_ticker_details(tickers, run_date)

    if df.empty:
        print("No ticker details fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        name VARCHAR,
        market VARCHAR,
        locale VARCHAR,
        primary_exchange VARCHAR,
        type VARCHAR,
        active BOOLEAN,
        currency_name VARCHAR,
        cik VARCHAR,
        market_cap NUMBER,
        share_class_shares_outstanding NUMBER,
        weighted_shares_outstanding NUMBER,
        list_date DATE,
        sic_code VARCHAR,
        sic_description VARCHAR,
        total_employees NUMBER,
        homepage_url VARCHAR,
        description VARCHAR,
        date DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
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

    print(f"Successfully wrote {len(df)} ticker details to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 3: Create `dags/etl/polygon_ticker_details_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_polygon_ticker_details import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="polygon_ticker_details",
    default_args=default_args,
    description="Fetch S&P 500 ticker details (market cap, shares) from Polygon",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "polygon", "daily"],
) as dag:

    wait_for_universe = ExternalTaskSensor(
        task_id="wait_for_universe",
        external_dag_id="sp500_lookup",
        external_task_id="ingest_sp500_lookup",
        timeout=3600,
        poke_interval=60,
        mode="poke",
    )

    ingest_ticker_details = PythonOperator(
        task_id="ingest_polygon_ticker_details",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_ticker_details
```

### Step 4: Validate

```bash
astro dev parse
python -c "from src.jobs.ingest_polygon_ticker_details import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/polygon_client.py` | EDIT | Add `fetch_ticker_details()` method |
| `src/jobs/ingest_polygon_ticker_details.py` | CREATE | Daily ticker details job |
| `dags/etl/polygon_ticker_details_dag.py` | CREATE | Daily DAG for ticker details |

## Functions and interfaces

### `polygon_client.py` — new method

```python
def fetch_ticker_details(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch ticker details (market cap, shares outstanding) for a list of tickers.

    Args:
        tickers: List of ticker symbols.
        run_date: Date string (YYYY-MM-DD) used as the snapshot date.

    Returns:
        DataFrame with columns: ticker, name, market, locale, primary_exchange,
        type, active, currency_name, cik, market_cap, share_class_shares_outstanding,
        weighted_shares_outstanding, list_date, sic_code, sic_description,
        total_employees, homepage_url, description, date, extracted_at.
        Empty DataFrame if no data.

    Note:
        Response is a single object per ticker (not an array).
        Each successful API call yields exactly one DataFrame row.
    """
    ...
```

### `ingest_polygon_ticker_details.py`

```python
def run(run_date: str) -> None:
    """Fetch and load ticker details for all S&P 500 tickers."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/polygon_client.py` | Adding 1 method — no existing method signatures change. Backward compatible. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_partition()`. |
| Airflow DAG registry | 1 new DAG registered. Verify no `dag_id` conflicts. |
| Snowflake schema | 1 new table created in `{STUDENT_SCHEMA}`. No existing tables modified. |
| Polygon rate budget | +500 requests/day (~7 min at 0.8s/req). Runs in parallel with existing Polygon DAGs. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| Polygon returns 403 (unauthorized) | `response.status_code != 200` check; return empty list for that ticker. |
| Polygon returns 429 (rate limit) | Handled by `_get()` retry logic with exponential backoff. |
| `market_cap` is null (e.g., newly listed ticker) | Stored as NULL in Snowflake (NUMBER column accepts NULL). |
| `share_class_shares_outstanding` is null | Stored as NULL. Downstream models must handle NULL shares. |
| `description` field is very long (>16MB) | Snowflake VARCHAR max is 16MB. No truncation needed for typical descriptions. |
| Ticker delisted between universe lookup and API call | Polygon returns 404 or empty results; logged as failed in `_fetch_batch()`. |
| Weekend/holiday run | Market cap reflects last trading day's close price. Data is still valid. |
| `active` field is false | Stored as-is. Downstream dbt can filter inactive tickers if needed. |
| Polygon response missing `results` key | `data.get("results")` returns None; empty list returned. |

## Observability

- Job uses `print()` statements captured by Airflow task logs:
  - Starting message with run_date
  - Ticker count from universe lookup
  - `_fetch_batch()` progress every 50 tickers (built into PolygonClient)
  - Final row count written to Snowflake
- Expected runtime: ~500 tickers x 0.8s/req = ~7 minutes
- Airflow task status visible in UI

## Acceptance criteria

- [ ] `PolygonClient.fetch_ticker_details()` returns a DataFrame with correct columns when called with valid tickers
- [ ] Response parsing handles the single-object format (not array) correctly
- [ ] `src/jobs/ingest_polygon_ticker_details.py` creates `sp500_ticker_details` table and populates it
- [ ] DAG parses without errors (`astro dev parse`)
- [ ] DAG is gated on `sp500_lookup` via ExternalTaskSensor
- [ ] Running the same job twice produces no duplicate rows (idempotent)
- [ ] `market_cap` column is populated for the majority of tickers (some may be NULL)
- [ ] `share_class_shares_outstanding` column is populated for the majority of tickers
- [ ] Snowflake table schema matches the DDL definition above
- [ ] `SELECT COUNT(*) FROM sp500_ticker_details WHERE date = '{run_date}'` returns ~500

## Follow-ups

- Phase 1+: Create dbt staging model `stg_polygon_ticker_details.sql`
- Phase 1+: Use market_cap in valuation scoring (P/E = market_cap / net_income)
- Phase 1+: Use shares_outstanding to derive per-share metrics from raw financials
- Consider adding `phone_number`, `address`, `branding` fields if needed for enrichment
- Monitor for tickers where `market_cap` is consistently NULL and investigate
