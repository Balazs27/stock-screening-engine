# Feature 05 — Analyst Price Targets & Upgrades/Downgrades

## Goal

Ingest consensus analyst price targets (high/low/median/consensus) and aggregate ratings distribution (strong buy/buy/hold/sell/strong sell) from FMP. Two per-ticker endpoints captured as daily point-in-time snapshots. Single job writes to 2 raw tables. No backfill — consensus is inherently point-in-time.

## Why this matters

Analyst sentiment is a leading indicator of institutional capital flows. Price target upside/downside provides a forward-looking valuation anchor, and rating changes (upgrades/downgrades) are near-term catalysts. Without analyst data, the pipeline lacks a forward-looking institutional sentiment dimension.

## Scope

- Add `FMPClient.fetch_price_target_consensus()` method to `src/api_clients/fmp_client.py`
- Add `FMPClient.fetch_upgrades_downgrades_consensus()` method to `src/api_clients/fmp_client.py`
- Create `src/jobs/ingest_fmp_analyst_consensus.py` — single daily job that fetches both endpoints and writes to 2 tables
- Create `dags/etl/fmp_analyst_consensus_dag.py` — daily DAG gated on `sp500_lookup`
- Raw tables: `sp500_price_target_consensus`, `sp500_upgrades_downgrades`
- NO backfill — consensus is point-in-time; begin storing daily snapshots from first run

## Out of scope

- Individual analyst-level price targets (only consensus)
- Individual upgrade/downgrade events (only consensus distribution)
- Historical analyst target reconstruction
- dbt staging/intermediate/mart models (Phase 1+)
- Analyst sentiment scoring logic (Phase 1+)
- Backfill job/DAG (not applicable for point-in-time consensus)

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for price target consensus and upgrades/downgrades endpoints |
| `src/api_clients/fmp_client.py` | Existing FMP client patterns: `_get()`, `_fetch_batch()` |
| `src/jobs/ingest_fmp_income_statement.py` | FMP daily job pattern |
| `dags/etl/fmp_income_statement_dag.py` | Daily FMP DAG pattern |
| `src/loaders/snowflake_loader.py` | Loader API: `overwrite_partition()` |

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
- FMP `/stable/price-target-consensus?symbol={ticker}&apikey={key}` — per-ticker
- FMP `/stable/upgrades-downgrades-consensus?symbol={ticker}&apikey={key}` — per-ticker

## Data contracts and schemas

### Raw table: `sp500_price_target_consensus`

**Grain:** (ticker, date) — one consensus snapshot per ticker per day.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_price_target_consensus (
    ticker VARCHAR,
    target_high FLOAT,
    target_low FLOAT,
    target_consensus FLOAT,
    target_median FLOAT,
    date DATE,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### Raw table: `sp500_upgrades_downgrades`

**Grain:** (ticker, date) — one consensus distribution per ticker per day.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_upgrades_downgrades (
    ticker VARCHAR,
    strong_buy INTEGER,
    buy INTEGER,
    hold INTEGER,
    sell INTEGER,
    strong_sell INTEGER,
    consensus VARCHAR,
    date DATE,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### DataFrame schemas

**Price Target Consensus DataFrame:**

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `target_high` | float/None | `targetHigh` |
| `target_low` | float/None | `targetLow` |
| `target_consensus` | float/None | `targetConsensus` |
| `target_median` | float/None | `targetMedian` |
| `date` | str | Injected from run_date |
| `extracted_at` | str | Generated at fetch time |

**Upgrades/Downgrades Consensus DataFrame:**

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `strong_buy` | int/None | `strongBuy` |
| `buy` | int/None | `buy` |
| `hold` | int/None | `hold` |
| `sell` | int/None | `sell` |
| `strong_sell` | int/None | `strongSell` |
| `consensus` | str/None | `consensus` |
| `date` | str | Injected from run_date |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 1: Add `fetch_price_target_consensus()` to FMPClient

The consensus endpoint returns an array (typically with 1 element per ticker). Use `_fetch_batch()` pattern.

```python
def fetch_price_target_consensus(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch analyst price target consensus for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/price-target-consensus"
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
                "target_high": r.get("targetHigh"),
                "target_low": r.get("targetLow"),
                "target_consensus": r.get("targetConsensus"),
                "target_median": r.get("targetMedian"),
                "date": run_date,
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="price targets")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 2: Add `fetch_upgrades_downgrades_consensus()` to FMPClient

```python
def fetch_upgrades_downgrades_consensus(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch analyst upgrades/downgrades consensus for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/upgrades-downgrades-consensus"
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
                "strong_buy": r.get("strongBuy"),
                "buy": r.get("buy"),
                "hold": r.get("hold"),
                "sell": r.get("sell"),
                "strong_sell": r.get("strongSell"),
                "consensus": r.get("consensus"),
                "date": run_date,
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="ratings consensus")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 3: Create `src/jobs/ingest_fmp_analyst_consensus.py`

Single job that calls both endpoints and writes to 2 tables. This keeps the two datasets synchronized per run.

```python
import sys
import os
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_partition,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE_TARGETS = "sp500_price_target_consensus"
TABLE_RATINGS = "sp500_upgrades_downgrades"


def run(run_date: str):
    print(f"Starting S&P 500 analyst consensus ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()

    # --- Price Target Consensus ---
    df_targets = client.fetch_price_target_consensus(tickers, run_date)

    if not df_targets.empty:
        create_targets_sql = f"""
        CREATE TABLE IF NOT EXISTS {schema}.{TABLE_TARGETS} (
            ticker VARCHAR,
            target_high FLOAT,
            target_low FLOAT,
            target_consensus FLOAT,
            target_median FLOAT,
            date DATE,
            extracted_at TIMESTAMP_NTZ,
            PRIMARY KEY (ticker, date)
        )
        """

        fq_targets = f"{schema}.{TABLE_TARGETS}"
        overwrite_partition(
            session=session,
            df=df_targets,
            table_name=fq_targets,
            partition_col="date",
            partition_value=run_date,
            create_table_sql=create_targets_sql,
        )
        print(f"Successfully wrote {len(df_targets)} price targets to {fq_targets}")
    else:
        print("No price target data fetched.")

    # --- Upgrades/Downgrades Consensus ---
    df_ratings = client.fetch_upgrades_downgrades_consensus(tickers, run_date)

    if not df_ratings.empty:
        create_ratings_sql = f"""
        CREATE TABLE IF NOT EXISTS {schema}.{TABLE_RATINGS} (
            ticker VARCHAR,
            strong_buy INTEGER,
            buy INTEGER,
            hold INTEGER,
            sell INTEGER,
            strong_sell INTEGER,
            consensus VARCHAR,
            date DATE,
            extracted_at TIMESTAMP_NTZ,
            PRIMARY KEY (ticker, date)
        )
        """

        fq_ratings = f"{schema}.{TABLE_RATINGS}"
        overwrite_partition(
            session=session,
            df=df_ratings,
            table_name=fq_ratings,
            partition_col="date",
            partition_value=run_date,
            create_table_sql=create_ratings_sql,
        )
        print(f"Successfully wrote {len(df_ratings)} ratings to {fq_ratings}")
    else:
        print("No ratings data fetched.")

    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 4: Create `dags/etl/fmp_analyst_consensus_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_analyst_consensus import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_analyst_consensus",
    default_args=default_args,
    description="Fetch S&P 500 analyst price targets and ratings consensus from FMP",
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

    ingest_analyst_consensus = PythonOperator(
        task_id="ingest_fmp_analyst_consensus",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_analyst_consensus
```

### Step 5: Validate

```bash
astro dev parse
python -c "from src.jobs.ingest_fmp_analyst_consensus import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fmp_client.py` | EDIT | Add `fetch_price_target_consensus()` and `fetch_upgrades_downgrades_consensus()` |
| `src/jobs/ingest_fmp_analyst_consensus.py` | CREATE | Daily job writing to 2 tables |
| `dags/etl/fmp_analyst_consensus_dag.py` | CREATE | Daily DAG for analyst consensus |

## Functions and interfaces

### `fmp_client.py` — new methods

```python
def fetch_price_target_consensus(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch analyst price target consensus for a list of tickers.

    Args:
        tickers: List of ticker symbols.
        run_date: Date string for snapshot dating.

    Returns:
        DataFrame with columns: ticker, target_high, target_low,
        target_consensus, target_median, date, extracted_at.
    """
    ...

def fetch_upgrades_downgrades_consensus(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch analyst upgrades/downgrades consensus for a list of tickers.

    Args:
        tickers: List of ticker symbols.
        run_date: Date string for snapshot dating.

    Returns:
        DataFrame with columns: ticker, strong_buy, buy, hold, sell,
        strong_sell, consensus, date, extracted_at.
    """
    ...
```

### `ingest_fmp_analyst_consensus.py`

```python
def run(run_date: str) -> None:
    """Fetch and load analyst consensus data (price targets + ratings) for all S&P 500 tickers."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fmp_client.py` | Adding 2 methods. No existing signatures change. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_partition()`. |
| Airflow DAG registry | 1 new DAG registered. |
| Snowflake schema | 2 new tables created. |
| FMP rate budget | +1,000 requests/day (2 endpoints x 500 tickers). ~1.7 min at 0.1s/req. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| FMP returns empty array for a ticker (no analyst coverage) | `_fetch_batch()` returns empty list. Common for smaller S&P 500 constituents. |
| Price target values are 0 or null | Stored as-is. Some tickers may lack analyst coverage. |
| All rating counts are 0 | Stored as-is. Ticker has no active ratings. |
| `consensus` string has unexpected value | Stored as VARCHAR. Expected: "Strong Buy", "Buy", "Hold", "Sell", "Strong Sell". |
| One endpoint succeeds but the other fails | Job writes successful data and logs warning for failed endpoint. Both are independent writes. |
| Weekend/holiday run | Consensus data is unchanged from Friday. Stored with current date as snapshot. |

## Observability

- `_fetch_batch()` logs progress every 50 tickers for each endpoint
- Separate completion messages for price targets and ratings
- Expected runtime: ~1,000 requests total at 0.1s/req = ~1.7 minutes

## Acceptance criteria

- [ ] `FMPClient.fetch_price_target_consensus()` returns DataFrame with correct columns
- [ ] `FMPClient.fetch_upgrades_downgrades_consensus()` returns DataFrame with correct columns
- [ ] Single job writes to both `sp500_price_target_consensus` and `sp500_upgrades_downgrades`
- [ ] DAG parses without errors (`astro dev parse`)
- [ ] DAG is gated on `sp500_lookup`
- [ ] Running the same job twice produces no duplicate rows (per-date partition)
- [ ] `target_consensus` column is populated for most tickers
- [ ] `strong_buy + buy + hold + sell + strong_sell` sums to a reasonable total per ticker
- [ ] No backfill DAG exists (confirmed as intentional — point-in-time data)

## Follow-ups

- Phase 1+: Create dbt staging models for both tables
- Phase 1+: Compute price target upside/downside ratio (target_consensus / current_price - 1)
- Phase 1+: Create analyst sentiment scoring mart
- Track consensus changes over time (daily snapshots enable trend analysis)
- Consider adding individual analyst targets endpoint if per-analyst granularity is needed
