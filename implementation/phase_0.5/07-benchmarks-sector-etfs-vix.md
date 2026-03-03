# Feature 07 — Benchmarks, Sector ETFs & VIX

## Goal

Ingest daily OHLCV prices for benchmark indices (SPY, QQQ, IWM), 11 sector ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLU, XLC, XLRE, XLB), and volatility proxy (VIXY) into a dedicated benchmark prices table. Reuses existing `PolygonClient.fetch_stock_prices()` and `fetch_stock_prices_range()` — NO new client code.

## Why this matters

Enables relative-performance scoring (stock vs. sector vs. market), market regime detection (bull/bear/sideways via SPY trend), and risk-adjusted rankings. Without benchmarks, all scores are absolute and miss macro context. Sector ETFs enable peer-relative scoring for sector rotation strategies.

## Scope

- Create `src/jobs/ingest_polygon_benchmark_prices.py` — daily job with fixed benchmark ticker list
- Create `src/jobs/ingest_polygon_benchmark_prices_backfill.py` — 5-year backfill (1,826 days)
- Create `dags/etl/polygon_benchmark_prices_dag.py` — daily DAG (NOT gated on sp500_lookup; benchmarks are independent of S&P 500 universe)
- Create `dags/etl/polygon_benchmark_prices_backfill_dag.py` — backfill DAG (schedule=None)
- Raw table: `sp500_benchmark_prices`
- NO new client methods — reuses existing Polygon price methods

## Out of scope

- Relative performance computation in dbt (Phase 1+)
- Market regime classification (Phase 1+)
- Sector rotation scoring logic (Phase 1+)
- VIX index directly (VIXY ETF is the tradeable proxy)
- Additional benchmarks (DIA, MDY, etc.)

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for benchmarks, ticker list, and schema |
| `src/api_clients/polygon_client.py` | Existing `fetch_stock_prices()` and `fetch_stock_prices_range()` methods |
| `src/jobs/ingest_polygon_prices.py` | Daily Polygon prices job pattern |
| `src/jobs/ingest_polygon_prices_backfill.py` | Backfill job pattern with `overwrite_date_range()` |
| `dags/etl/polygon_daily_prices_dag.py` | Daily Polygon DAG pattern |
| `dags/etl/polygon_prices_backfill_dag.py` | Backfill DAG pattern |
| `src/loaders/snowflake_loader.py` | Loader API |

## Dependencies

### Upstream features
- None — this is independent. Does NOT require `sp500_tickers_lookup` (uses hardcoded ticker list).

### Libraries/packages
- No new packages required.

### Environment variables
- `POLYGON_API_KEY` — already used
- `STUDENT_SCHEMA` — already used
- `SNOWFLAKE_*` — already used

### APIs/data sources
- Polygon `/v2/aggs/ticker/{symbol}/range/1/day/{date}/{date}` — same endpoint as existing prices

## Data contracts and schemas

### Benchmark ticker list (hardcoded constant)

```python
BENCHMARK_TICKERS = [
    # Broad market
    "SPY",   # S&P 500 ETF
    "QQQ",   # Nasdaq 100 ETF
    "IWM",   # Russell 2000 ETF
    # Sector ETFs (11 GICS sectors)
    "XLF",   # Financials
    "XLK",   # Technology
    "XLE",   # Energy
    "XLV",   # Health Care
    "XLI",   # Industrials
    "XLY",   # Consumer Discretionary
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLC",   # Communication Services
    "XLRE",  # Real Estate
    "XLB",   # Materials
    # Volatility proxy
    "VIXY",  # VIX Short-Term Futures ETF
]
```

### Raw table: `sp500_benchmark_prices`

**Grain:** (ticker, date) — one row per benchmark/ETF per day.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_benchmark_prices (
    ticker VARCHAR(50),
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    vwap FLOAT,
    transactions BIGINT,
    date DATE,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

**Note:** Schema is identical to `sp500_stock_prices`. Stored in a separate table to maintain clear separation between S&P 500 constituents and benchmarks.

## Implementation plan

### Step 1: Create `src/jobs/ingest_polygon_benchmark_prices.py`

Key difference from `ingest_polygon_prices.py`: uses a hardcoded benchmark ticker list instead of querying `sp500_tickers_lookup`. This job does NOT depend on the sp500_lookup DAG.

```python
import sys
import os
from dotenv import load_dotenv

from src.api_clients.polygon_client import PolygonClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_partition,
)
from src.utils.dates import today

TABLE = "sp500_benchmark_prices"

BENCHMARK_TICKERS = [
    "SPY", "QQQ", "IWM",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLC", "XLRE", "XLB",
    "VIXY",
]


def run(run_date: str):
    print(f"Starting benchmark prices ingestion for {run_date}...")
    print(f"Benchmark tickers: {len(BENCHMARK_TICKERS)} symbols")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = PolygonClient()
    df = client.fetch_stock_prices(BENCHMARK_TICKERS, run_date)

    if df.empty:
        print("No benchmark price data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR(50),
        open FLOAT,
        high FLOAT,
        low FLOAT,
        close FLOAT,
        volume BIGINT,
        vwap FLOAT,
        transactions BIGINT,
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

    print(f"Successfully wrote {len(df)} benchmark prices to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 2: Create `src/jobs/ingest_polygon_benchmark_prices_backfill.py`

```python
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.api_clients.polygon_client import PolygonClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_date_range,
)
from src.utils.dates import today

TABLE = "sp500_benchmark_prices"
DEFAULT_LOOKBACK_DAYS = 1826  # ~5 years

BENCHMARK_TICKERS = [
    "SPY", "QQQ", "IWM",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLC", "XLRE", "XLB",
    "VIXY",
]


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS):
    end_date = datetime.strptime(run_date, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=lookback_days)

    print(f"Starting benchmark prices backfill: {start_date} to {end_date} ({lookback_days} days)...")
    print(f"Benchmark tickers: {len(BENCHMARK_TICKERS)} symbols")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = PolygonClient()
    df = client.fetch_stock_prices_range(BENCHMARK_TICKERS, str(start_date), str(end_date))

    if df.empty:
        print("No benchmark price data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR(50),
        open FLOAT,
        high FLOAT,
        low FLOAT,
        close FLOAT,
        volume BIGINT,
        vwap FLOAT,
        transactions BIGINT,
        date DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
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

    print(f"Successfully wrote {len(df)} benchmark prices to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
```

### Step 3: Create `dags/etl/polygon_benchmark_prices_dag.py`

**Note:** This DAG does NOT have an ExternalTaskSensor on sp500_lookup because benchmarks are independent of the S&P 500 universe. It runs on its own schedule.

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_polygon_benchmark_prices import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="polygon_benchmark_prices",
    default_args=default_args,
    description="Fetch daily benchmark and sector ETF prices from Polygon",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "polygon", "daily", "benchmarks"],
) as dag:

    ingest_benchmark_prices = PythonOperator(
        task_id="ingest_polygon_benchmark_prices",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

### Step 4: Create `dags/etl/polygon_benchmark_prices_backfill_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_polygon_benchmark_prices_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="polygon_benchmark_prices_backfill",
    default_args=default_args,
    description="Backfill 5 years of benchmark and sector ETF prices from Polygon",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "polygon", "backfill", "benchmarks"],
) as dag:

    backfill_benchmark_prices = PythonOperator(
        task_id="backfill_polygon_benchmark_prices",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

### Step 5: Validate

```bash
astro dev parse
python -c "from src.jobs.ingest_polygon_benchmark_prices import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/polygon_client.py` | NO CHANGE | Reuses existing `fetch_stock_prices()` and `fetch_stock_prices_range()` |
| `src/jobs/ingest_polygon_benchmark_prices.py` | CREATE | Daily benchmark prices job |
| `src/jobs/ingest_polygon_benchmark_prices_backfill.py` | CREATE | 5-year backfill job |
| `dags/etl/polygon_benchmark_prices_dag.py` | CREATE | Daily DAG (no sp500_lookup dependency) |
| `dags/etl/polygon_benchmark_prices_backfill_dag.py` | CREATE | Backfill DAG |

## Functions and interfaces

### `ingest_polygon_benchmark_prices.py`

```python
BENCHMARK_TICKERS: list[str]  # 15 symbols (3 broad + 11 sector + 1 vol)

def run(run_date: str) -> None:
    """Fetch and load daily benchmark prices for fixed ticker list."""
    ...
```

### `ingest_polygon_benchmark_prices_backfill.py`

```python
def run(run_date: str, lookback_days: int = 1826) -> None:
    """Backfill 5 years of benchmark prices for fixed ticker list."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/polygon_client.py` | No changes. Reuses existing methods. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_partition()` and `overwrite_date_range()`. |
| Airflow DAG registry | 2 new DAGs. Note: benchmark DAG has NO sp500_lookup dependency. |
| Snowflake schema | 1 new table. Schema identical to `sp500_stock_prices`. |
| Polygon rate budget | +15 requests/day for daily (~12 seconds). Backfill: 15 range requests (~12 seconds). |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| VIXY is delisted or replaced | Will return empty from Polygon. Log as failed in `_fetch_batch()`. Consider replacing with VXX or similar. |
| ETF ticker changes | BENCHMARK_TICKERS list is hardcoded. Must be manually updated if sector ETFs change. |
| Weekend/holiday run | Polygon returns no results for non-trading days. `df.empty` check handles gracefully. |
| Market half-day (e.g., day after Thanksgiving) | Partial data returned. Stored as normal. |
| New sector ETF added to GICS | Must manually add to BENCHMARK_TICKERS constant. |

## Observability

- `_fetch_batch()` provides progress logging
- Very fast: only 15 tickers, ~12 seconds at Polygon rate limit
- Final row count printed

## Acceptance criteria

- [ ] No new methods added to `polygon_client.py` (confirmed reuse)
- [ ] Daily job uses hardcoded `BENCHMARK_TICKERS` list (not sp500_tickers_lookup)
- [ ] Daily DAG has NO ExternalTaskSensor (no sp500_lookup dependency)
- [ ] Both DAGs parse without errors (`astro dev parse`)
- [ ] Backfill DAG has `schedule=None`
- [ ] `sp500_benchmark_prices` table schema matches `sp500_stock_prices` schema
- [ ] `SELECT COUNT(DISTINCT ticker) FROM sp500_benchmark_prices WHERE date = '{run_date}'` returns 15 (or close to 15)
- [ ] Running the same job twice produces no duplicate rows
- [ ] SPY, QQQ, IWM prices are populated for trading days
- [ ] All 11 sector ETF tickers have data

## Follow-ups

- Phase 1+: Create dbt staging model `stg_polygon_benchmark_prices.sql`
- Phase 1+: Create intermediate model computing benchmark returns (daily, rolling)
- Phase 1+: Relative performance scoring (stock return - SPY return)
- Phase 1+: Market regime detection using SPY SMA-200 and VIX levels
- Consider adding DIA (Dow), MDY (S&P 400 Mid-Cap) if mid-cap relative scoring is needed
- Monitor VIXY availability — ProShares may delist/restructure volatility ETFs periodically
