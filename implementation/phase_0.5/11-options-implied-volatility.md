# Feature 11 — Options Implied Volatility (TENTATIVE)

## Goal

Ingest options-derived implied volatility (IV) summary data for S&P 500 tickers from Polygon's options snapshot endpoint. The API client must aggregate per-contract data into a ticker-level IV summary (30-day IV, put/call ratio, total volume/OI). **This feature is TENTATIVE** — it requires a Polygon Options subscription that may not be included in the Basic plan.

## Why this matters

Implied volatility is the market's forward-looking risk estimate. IV rank identifies when options are cheap or expensive relative to history, serving as a risk/opportunity signal. Put/call ratio indicates directional sentiment. These signals add a derivatives-based dimension orthogonal to price, fundamental, and analyst data.

## Scope

- **Availability gate:** Test Polygon `/v3/snapshot/options/{underlyingAsset}` before proceeding
- If available:
  - Add `PolygonClient.fetch_options_iv_summary()` method to `src/api_clients/polygon_client.py`
  - Create `src/jobs/ingest_polygon_options_iv.py` — daily job
  - Create `dags/etl/polygon_options_iv_dag.py` — daily DAG gated on `sp500_lookup`
  - Raw table: `sp500_options_iv_summary`
- If unavailable:
  - Document as deprioritized
  - No code changes
- NO backfill — options snapshots are point-in-time; historical IV must be built from daily collection

## Out of scope

- Raw per-contract options chain storage (aggregated in API client, never stored)
- Historical IV rank computation (requires accumulated daily snapshots; computed in dbt Phase 1+)
- Greeks computation (delta, gamma, theta, vega)
- Options strategy analysis
- Backfill job/DAG (not possible for point-in-time snapshots)
- dbt staging/intermediate/mart models (Phase 1+)

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for options IV endpoint, aggregation requirements |
| `src/api_clients/polygon_client.py` | Existing Polygon client patterns |
| `src/jobs/ingest_polygon_prices.py` | Polygon daily job pattern |
| `dags/etl/polygon_daily_prices_dag.py` | Daily Polygon DAG pattern |
| `src/loaders/snowflake_loader.py` | Loader API |

## Dependencies

### Upstream features
- None — this is independent.

### Libraries/packages
- No new packages required.

### Environment variables
- `POLYGON_API_KEY` — already used (but may need Options subscription tier)
- `STUDENT_SCHEMA` — already used
- `SNOWFLAKE_*` — already used

### APIs/data sources
- Polygon `/v3/snapshot/options/{underlyingAsset}?apiKey={key}` — per-ticker options chain snapshot

## Data contracts and schemas

### Availability gate procedure

**Before writing any production code,** run this manual test:

```python
import os
import requests

api_key = os.environ["POLYGON_API_KEY"]
test_ticker = "AAPL"
url = f"https://api.polygon.io/v3/snapshot/options/{test_ticker}?apiKey={api_key}"
response = requests.get(url, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:1000]}")
```

**Decision matrix:**

| Response | Action |
|----------|--------|
| 200 + valid JSON with `results` array | Proceed with implementation |
| 200 + empty results | Proceed but note limited data for that ticker |
| 403 Forbidden | **STOP** — Options subscription required. Document as deprioritized. |
| 401 Unauthorized | **STOP** — API key does not have options access. Document as deprioritized. |
| 404 Not Found | **STOP** — Endpoint not available. Document as deprioritized. |

### Polygon options snapshot response structure (raw)

The raw response contains hundreds of individual options contracts:

```json
{
  "status": "OK",
  "results": [
    {
      "details": {
        "contract_type": "call",
        "exercise_style": "american",
        "expiration_date": "2026-03-21",
        "shares_per_contract": 100,
        "strike_price": 200.0,
        "ticker": "O:AAPL260321C00200000"
      },
      "greeks": {
        "delta": 0.65,
        "gamma": 0.02,
        "theta": -0.15,
        "vega": 0.25
      },
      "implied_volatility": 0.28,
      "open_interest": 5000,
      "day": {
        "volume": 1200,
        "close": 5.50,
        "open": 5.20,
        "high": 5.80,
        "low": 5.10
      },
      "underlying_asset": {
        "ticker": "AAPL",
        "price": 195.50
      }
    }
  ]
}
```

**Critical:** Do NOT store raw per-contract data. The API client MUST aggregate to a summary.

### Aggregated summary schema (stored in Snowflake)

**Raw table:** `sp500_options_iv_summary`

**Grain:** (ticker, date) — one aggregated IV summary row per ticker per day.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_options_iv_summary (
    ticker VARCHAR,
    date DATE,
    iv_30d FLOAT,
    put_call_ratio FLOAT,
    total_call_volume NUMBER,
    total_put_volume NUMBER,
    total_call_oi NUMBER,
    total_put_oi NUMBER,
    underlying_price FLOAT,
    contract_count INTEGER,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date)
)
```

### DataFrame schema (aggregated output)

| Column | Type | Computation |
|--------|------|-------------|
| `ticker` | str | From `underlying_asset.ticker` |
| `date` | str | Injected from run_date |
| `iv_30d` | float/None | Median IV of contracts expiring within 25-35 days (ATM +-10% strike) |
| `put_call_ratio` | float/None | `total_put_volume / total_call_volume` (or None if call volume = 0) |
| `total_call_volume` | int | SUM of `day.volume` where `contract_type = "call"` |
| `total_put_volume` | int | SUM of `day.volume` where `contract_type = "put"` |
| `total_call_oi` | int | SUM of `open_interest` where `contract_type = "call"` |
| `total_put_oi` | int | SUM of `open_interest` where `contract_type = "put"` |
| `underlying_price` | float/None | From `underlying_asset.price` (first non-null) |
| `contract_count` | int | Total number of contracts in snapshot |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 0: Availability gate (MUST DO FIRST)

Run the availability gate test. If 403/401/404, skip all steps and document.

### Step 1: Add `fetch_options_iv_summary()` to PolygonClient (if available)

This method is unique because it must aggregate per-contract data into a summary. The aggregation logic runs in the API client (not in dbt) because raw per-contract data should never be stored in Snowflake.

```python
def fetch_options_iv_summary(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch options chain snapshot and aggregate to IV summary per ticker.

    Aggregation logic:
    1. Fetch all contracts for the ticker
    2. Filter to near-ATM contracts (strike within +-10% of underlying price)
    3. Filter to near-term expiry (25-35 calendar days out)
    4. Compute median IV from filtered contracts as iv_30d
    5. Sum call/put volume and open interest
    6. Compute put/call ratio

    Note: This is a heavy endpoint. Each ticker returns hundreds of contracts.
    The aggregation runs in-memory in the API client.
    """
    from statistics import median

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/v3/snapshot/options/{ticker}"
            f"?apiKey={self.api_key}"
        )
        response = self._get(url)
        if response.status_code != 200:
            return []
        data = response.json()
        if data.get("status") != "OK" or not data.get("results"):
            return []

        results = data["results"]
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get underlying price from first contract
        underlying_price = None
        for r in results:
            ua = r.get("underlying_asset", {})
            if ua.get("price"):
                underlying_price = ua["price"]
                break

        if not underlying_price:
            return []

        # Parse run_date for expiry filtering
        from datetime import datetime as dt, timedelta
        run_dt = dt.strptime(run_date, "%Y-%m-%d").date()
        min_expiry = run_dt + timedelta(days=25)
        max_expiry = run_dt + timedelta(days=35)

        # ATM range
        strike_low = underlying_price * 0.90
        strike_high = underlying_price * 1.10

        # Aggregate
        call_volume = 0
        put_volume = 0
        call_oi = 0
        put_oi = 0
        near_atm_ivs = []

        for r in results:
            details = r.get("details", {})
            contract_type = details.get("contract_type", "")
            strike = details.get("strike_price", 0)
            expiry_str = details.get("expiration_date", "")
            iv = r.get("implied_volatility")
            oi = r.get("open_interest", 0) or 0
            day_data = r.get("day", {})
            vol = day_data.get("volume", 0) or 0

            # Volume and OI aggregation (all contracts)
            if contract_type == "call":
                call_volume += vol
                call_oi += oi
            elif contract_type == "put":
                put_volume += vol
                put_oi += oi

            # IV filtering (near-ATM, near-term only)
            if iv and expiry_str and strike_low <= strike <= strike_high:
                try:
                    expiry_dt = dt.strptime(expiry_str, "%Y-%m-%d").date()
                    if min_expiry <= expiry_dt <= max_expiry:
                        near_atm_ivs.append(iv)
                except ValueError:
                    pass

        iv_30d = median(near_atm_ivs) if near_atm_ivs else None
        put_call_ratio = (
            put_volume / call_volume if call_volume > 0 else None
        )

        return [{
            "ticker": ticker,
            "date": run_date,
            "iv_30d": iv_30d,
            "put_call_ratio": put_call_ratio,
            "total_call_volume": call_volume,
            "total_put_volume": put_volume,
            "total_call_oi": call_oi,
            "total_put_oi": put_oi,
            "underlying_price": underlying_price,
            "contract_count": len(results),
            "extracted_at": extracted_at,
        }]

    results = self._fetch_batch(tickers, _fetch_one, label="options IV summaries")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 2: Create `src/jobs/ingest_polygon_options_iv.py` (if available)

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
TABLE = "sp500_options_iv_summary"


def run(run_date: str):
    print(f"Starting S&P 500 options IV summary ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_options_iv_summary(tickers, run_date)

    if df.empty:
        print("No options IV data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        iv_30d FLOAT,
        put_call_ratio FLOAT,
        total_call_volume NUMBER,
        total_put_volume NUMBER,
        total_call_oi NUMBER,
        total_put_oi NUMBER,
        underlying_price FLOAT,
        contract_count INTEGER,
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

    print(f"Successfully wrote {len(df)} options IV summaries to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
```

### Step 3: Create `dags/etl/polygon_options_iv_dag.py` (if available)

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_polygon_options_iv import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="polygon_options_iv",
    default_args=default_args,
    description="Fetch S&P 500 options implied volatility summaries from Polygon",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "polygon", "daily", "options"],
) as dag:

    wait_for_universe = ExternalTaskSensor(
        task_id="wait_for_universe",
        external_dag_id="sp500_lookup",
        external_task_id="ingest_sp500_lookup",
        timeout=3600,
        poke_interval=60,
        mode="poke",
    )

    ingest_options_iv = PythonOperator(
        task_id="ingest_polygon_options_iv",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_options_iv
```

### Step 4: Validate (if available)

```bash
astro dev parse
# Test with a small set of tickers first (options snapshot is heavy)
python -c "
from src.api_clients.polygon_client import PolygonClient
c = PolygonClient()
df = c.fetch_options_iv_summary(['AAPL', 'MSFT', 'GOOG'], '2026-02-28')
print(df)
"
```

## File-level change list

**If endpoint is available:**

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/polygon_client.py` | EDIT | Add `fetch_options_iv_summary()` method with aggregation logic |
| `src/jobs/ingest_polygon_options_iv.py` | CREATE | Daily options IV job |
| `dags/etl/polygon_options_iv_dag.py` | CREATE | Daily DAG |

**If endpoint is NOT available:**

| File | Action | Description |
|------|--------|-------------|
| `.claude/memory/MEMORY.md` | EDIT | Add unavailability entry |
| `implementation/phase_0.5/checklist.md` | EDIT | Mark Feature 11 as "Unavailable" |

## Functions and interfaces

### `polygon_client.py` — new method (if available)

```python
def fetch_options_iv_summary(
    self, tickers: list[str], run_date: str
) -> pd.DataFrame:
    """Fetch options chain snapshot and aggregate to IV summary per ticker.

    Aggregation:
    - iv_30d: Median IV of near-ATM (+-10% strike), near-term (25-35 day) contracts
    - put_call_ratio: total_put_volume / total_call_volume
    - Volume and OI: SUM across all contracts by type

    Args:
        tickers: List of ticker symbols.
        run_date: Date string (YYYY-MM-DD) for the snapshot.

    Returns:
        DataFrame with columns: ticker, date, iv_30d, put_call_ratio,
        total_call_volume, total_put_volume, total_call_oi, total_put_oi,
        underlying_price, contract_count, extracted_at.

    Note:
        This is a heavy endpoint. Each ticker may return hundreds of contracts.
        Aggregation runs in-memory. Raw per-contract data is never stored.
    """
    ...
```

### `ingest_polygon_options_iv.py`

```python
def run(run_date: str) -> None:
    """Fetch and load options IV summaries for all S&P 500 tickers."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/polygon_client.py` | Adding 1 method with complex aggregation logic. No existing signatures change. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_partition()`. |
| Airflow DAG registry | 1 new DAG (if available). |
| Snowflake schema | 1 new table (if available). |
| Polygon rate budget | +500 requests/day (~7 min at 0.8s/req). **Warning:** Options snapshot responses can be very large (100KB+ per ticker). Monitor memory usage. |
| Python `statistics` module | Used for `median()`. Standard library, no install needed. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| Endpoint returns 403 (no options subscription) | **STOP implementation.** Document as deprioritized. |
| No near-ATM, near-term contracts found | `iv_30d` is None. Row still stored with volume/OI data. |
| `underlying_price` is None or 0 | Cannot compute ATM range. Return empty list for that ticker. |
| Very large response (>1MB per ticker) | Processed in-memory. Monitor for OOM on workers. Consider processing in smaller batches. |
| No options trading on weekends/holidays | Empty or stale snapshot. Normal behavior. |
| `call_volume` is 0 (illiquid options) | `put_call_ratio` is None (division by zero guard). |
| Contract with missing `implied_volatility` | Skipped in IV aggregation. Still counted in volume/OI. |
| Expiry date parsing fails | `try/except ValueError` — contract skipped for IV but counted for volume/OI. |
| Contract `contract_type` is neither "call" nor "put" | Skipped (should not happen but defensive). |

## Observability

- Availability gate test result logged before implementation
- `_fetch_batch()` progress logging every 50 tickers
- Per-ticker: contract count and number of near-ATM IVs found
- Expected runtime: ~500 tickers x 0.8s/req = ~7 minutes (API latency may be higher due to large responses)

## Acceptance criteria

### If endpoint is available:
- [ ] Availability gate passed (200 + valid data for test ticker)
- [ ] `PolygonClient.fetch_options_iv_summary()` aggregates per-contract data correctly
- [ ] `iv_30d` is computed from near-ATM, near-term contracts (not all contracts)
- [ ] `put_call_ratio` handles zero call volume gracefully (returns None)
- [ ] Raw per-contract data is NOT stored in Snowflake
- [ ] Daily job creates and populates `sp500_options_iv_summary`
- [ ] DAG parses without errors (`astro dev parse`)
- [ ] DAG is gated on `sp500_lookup`
- [ ] No backfill DAG exists (confirmed as intentional — point-in-time only)
- [ ] Running the same job twice produces no duplicate rows

### If endpoint is NOT available:
- [ ] Unavailability documented in `.claude/memory/MEMORY.md`
- [ ] Feature 11 marked as "Unavailable" in checklist
- [ ] No production code changes committed

## Follow-ups

- If available: Phase 1+ staging model and IV rank computation (percentile of iv_30d vs. 252-day history)
- If available: Consider paginated options endpoint if snapshot truncates at a limit
- If unavailable: Evaluate CBOE data for IV index (VIX is already proxied via VIXY in Feature 07)
- If unavailable: Evaluate third-party IV data providers (IVolatility, OptionMetrics)
- Consider adding IV skew metric (difference between OTM put IV and ATM call IV) for crash risk
- Consider separating aggregation into a utility function for testability
- Monitor memory usage during options snapshot processing for all 500 tickers
