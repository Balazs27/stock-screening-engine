# Feature 04 — Valuation Multiples (Key Metrics)

## Goal

Ingest pre-computed valuation ratios (P/E, P/B, P/S, EV/EBITDA, EV/FCF, dividend yield, earnings yield) and per-share metrics from FMP's `/stable/key-metrics` endpoint. Provides a raw table with 40+ ratios per ticker per fiscal period, enabling valuation scoring without computing ratios from raw price + TTM fundamentals.

## Why this matters

The current scoring system has no valuation dimension. Without P/E, P/B, and EV/EBITDA, the system cannot distinguish cheap stocks from expensive ones, making composite rankings incomplete for value-aware screening. Pre-computed ratios from FMP provide consistent cross-ticker data with proper adjustments.

## Scope

- Add `FMPClient.fetch_key_metrics()` method to `src/api_clients/fmp_client.py`
- Create `src/jobs/ingest_fmp_key_metrics.py` — daily job
- Create `src/jobs/ingest_fmp_key_metrics_backfill.py` — 5-year backfill
- Create `dags/etl/fmp_key_metrics_dag.py` — daily DAG gated on `sp500_lookup`
- Create `dags/etl/fmp_key_metrics_backfill_dag.py` — backfill DAG (schedule=None)
- Raw table: `sp500_key_metrics`

## Out of scope

- dbt staging/intermediate/mart models for key metrics (Phase 1+)
- Valuation scoring logic (Phase 1+)
- Sector-relative valuation percentiles (Phase 1+)
- Computing ratios manually from price + fundamentals (FMP provides these pre-computed)

## Required context to read first

| File | Why |
|------|-----|
| `phase_0.5.md` | Full spec for key metrics endpoint, JSON schema with 24+ fields |
| `src/api_clients/fmp_client.py` | Existing FMP client patterns: `_get()`, `_fetch_batch()` |
| `src/jobs/ingest_fmp_income_statement.py` | FMP daily job pattern using `overwrite_date_range()` |
| `src/jobs/ingest_polygon_prices_backfill.py` | Backfill job pattern |
| `dags/etl/fmp_income_statement_dag.py` | Daily FMP DAG pattern |
| `dags/etl/polygon_prices_backfill_dag.py` | Backfill DAG pattern |
| `src/loaders/snowflake_loader.py` | Loader API: `overwrite_date_range()` |

## Dependencies

### Upstream features
- None — this is independent.

### Libraries/packages
- No new packages required.

### Environment variables
- `FMP_API_KEY` — already used by existing FMP jobs
- `STUDENT_SCHEMA` — already used by all jobs
- `SNOWFLAKE_*` — already used by all jobs

### APIs/data sources
- FMP `/stable/key-metrics?symbol={ticker}&period=quarter&apikey={key}` — per-ticker, quarterly
- FMP `/stable/key-metrics?symbol={ticker}&period=annual&apikey={key}` — per-ticker, annual

## Data contracts and schemas

### Raw table: `sp500_key_metrics`

**Grain:** (ticker, date, period) — one row per ticker per fiscal period.

```sql
CREATE TABLE IF NOT EXISTS {schema}.sp500_key_metrics (
    ticker VARCHAR,
    date DATE,
    period VARCHAR,
    fiscal_year VARCHAR,
    revenue_per_share FLOAT,
    net_income_per_share FLOAT,
    operating_cash_flow_per_share FLOAT,
    free_cash_flow_per_share FLOAT,
    cash_per_share FLOAT,
    book_value_per_share FLOAT,
    tangible_book_value_per_share FLOAT,
    shareholders_equity_per_share FLOAT,
    interest_debt_per_share FLOAT,
    market_cap NUMBER,
    enterprise_value NUMBER,
    pe_ratio FLOAT,
    price_to_sales_ratio FLOAT,
    pb_ratio FLOAT,
    ptb_ratio FLOAT,
    ev_to_sales FLOAT,
    enterprise_value_over_ebitda FLOAT,
    ev_to_operating_cash_flow FLOAT,
    ev_to_free_cash_flow FLOAT,
    earnings_yield FLOAT,
    free_cash_flow_yield FLOAT,
    dividend_yield FLOAT,
    payout_ratio FLOAT,
    debt_to_equity FLOAT,
    debt_to_assets FLOAT,
    net_debt_to_ebitda FLOAT,
    current_ratio FLOAT,
    interest_coverage FLOAT,
    income_quality FLOAT,
    roe FLOAT,
    roa FLOAT,
    roic FLOAT,
    invested_capital FLOAT,
    average_receivables FLOAT,
    average_payables FLOAT,
    average_inventory FLOAT,
    days_sales_outstanding FLOAT,
    days_payables_outstanding FLOAT,
    days_of_inventory_on_hand FLOAT,
    receivables_turnover FLOAT,
    payables_turnover FLOAT,
    inventory_turnover FLOAT,
    capex_per_share FLOAT,
    working_capital NUMBER,
    tangible_asset_value NUMBER,
    extracted_at TIMESTAMP_NTZ,
    PRIMARY KEY (ticker, date, period)
)
```

### DataFrame schema

**Key Metrics DataFrame** (returned by `fetch_key_metrics()`):

| Column | Type | Source JSON Key |
|--------|------|-----------------|
| `ticker` | str | `symbol` (injected from request) |
| `date` | str | `date` |
| `period` | str | `period` |
| `fiscal_year` | str/None | `fiscalYear` |
| `revenue_per_share` | float/None | `revenuePerShare` |
| `net_income_per_share` | float/None | `netIncomePerShare` |
| `operating_cash_flow_per_share` | float/None | `operatingCashFlowPerShare` |
| `free_cash_flow_per_share` | float/None | `freeCashFlowPerShare` |
| `cash_per_share` | float/None | `cashPerShare` |
| `book_value_per_share` | float/None | `bookValuePerShare` |
| `tangible_book_value_per_share` | float/None | `tangibleBookValuePerShare` |
| `shareholders_equity_per_share` | float/None | `shareholdersEquityPerShare` |
| `interest_debt_per_share` | float/None | `interestDebtPerShare` |
| `market_cap` | float/None | `marketCap` |
| `enterprise_value` | float/None | `enterpriseValue` |
| `pe_ratio` | float/None | `peRatio` |
| `price_to_sales_ratio` | float/None | `priceToSalesRatio` |
| `pb_ratio` | float/None | `pbRatio` |
| `ptb_ratio` | float/None | `ptbRatio` |
| `ev_to_sales` | float/None | `evToSales` |
| `enterprise_value_over_ebitda` | float/None | `enterpriseValueOverEBITDA` |
| `ev_to_operating_cash_flow` | float/None | `evToOperatingCashFlow` |
| `ev_to_free_cash_flow` | float/None | `evToFreeCashFlow` |
| `earnings_yield` | float/None | `earningsYield` |
| `free_cash_flow_yield` | float/None | `freeCashFlowYield` |
| `dividend_yield` | float/None | `dividendYield` |
| `payout_ratio` | float/None | `payoutRatio` |
| `debt_to_equity` | float/None | `debtToEquity` |
| `debt_to_assets` | float/None | `debtToAssets` |
| `net_debt_to_ebitda` | float/None | `netDebtToEBITDA` |
| `current_ratio` | float/None | `currentRatio` |
| `interest_coverage` | float/None | `interestCoverage` |
| `income_quality` | float/None | `incomeQuality` |
| `roe` | float/None | `roe` |
| `roa` | float/None | `roa` |
| `roic` | float/None | `roic` |
| `invested_capital` | float/None | `investedCapital` |
| `average_receivables` | float/None | `averageReceivables` |
| `average_payables` | float/None | `averagePayables` |
| `average_inventory` | float/None | `averageInventory` |
| `days_sales_outstanding` | float/None | `daysSalesOutstanding` |
| `days_payables_outstanding` | float/None | `daysPayablesOutstanding` |
| `days_of_inventory_on_hand` | float/None | `daysOfInventoryOnHand` |
| `receivables_turnover` | float/None | `receivablesTurnover` |
| `payables_turnover` | float/None | `payablesTurnover` |
| `inventory_turnover` | float/None | `inventoryTurnover` |
| `capex_per_share` | float/None | `capexPerShare` |
| `working_capital` | float/None | `workingCapital` |
| `tangible_asset_value` | float/None | `tangibleAssetValue` |
| `extracted_at` | str | Generated at fetch time |

## Implementation plan

### Step 1: Add `fetch_key_metrics()` to FMPClient

Add a new per-ticker method to `src/api_clients/fmp_client.py` using the standard `_fetch_batch()` pattern.

```python
def fetch_key_metrics(
    self, tickers: list[str], period: str = "quarter"
) -> pd.DataFrame:
    """Fetch key valuation metrics for a list of tickers."""

    def _fetch_one(ticker):
        url = (
            f"{BASE_URL}/stable/key-metrics"
            f"?symbol={ticker}"
            f"&period={period}"
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
                "period": r.get("period"),
                "fiscal_year": r.get("fiscalYear"),
                "revenue_per_share": r.get("revenuePerShare"),
                "net_income_per_share": r.get("netIncomePerShare"),
                "operating_cash_flow_per_share": r.get("operatingCashFlowPerShare"),
                "free_cash_flow_per_share": r.get("freeCashFlowPerShare"),
                "cash_per_share": r.get("cashPerShare"),
                "book_value_per_share": r.get("bookValuePerShare"),
                "tangible_book_value_per_share": r.get("tangibleBookValuePerShare"),
                "shareholders_equity_per_share": r.get("shareholdersEquityPerShare"),
                "interest_debt_per_share": r.get("interestDebtPerShare"),
                "market_cap": r.get("marketCap"),
                "enterprise_value": r.get("enterpriseValue"),
                "pe_ratio": r.get("peRatio"),
                "price_to_sales_ratio": r.get("priceToSalesRatio"),
                "pb_ratio": r.get("pbRatio"),
                "ptb_ratio": r.get("ptbRatio"),
                "ev_to_sales": r.get("evToSales"),
                "enterprise_value_over_ebitda": r.get("enterpriseValueOverEBITDA"),
                "ev_to_operating_cash_flow": r.get("evToOperatingCashFlow"),
                "ev_to_free_cash_flow": r.get("evToFreeCashFlow"),
                "earnings_yield": r.get("earningsYield"),
                "free_cash_flow_yield": r.get("freeCashFlowYield"),
                "dividend_yield": r.get("dividendYield"),
                "payout_ratio": r.get("payoutRatio"),
                "debt_to_equity": r.get("debtToEquity"),
                "debt_to_assets": r.get("debtToAssets"),
                "net_debt_to_ebitda": r.get("netDebtToEBITDA"),
                "current_ratio": r.get("currentRatio"),
                "interest_coverage": r.get("interestCoverage"),
                "income_quality": r.get("incomeQuality"),
                "roe": r.get("roe"),
                "roa": r.get("roa"),
                "roic": r.get("roic"),
                "invested_capital": r.get("investedCapital"),
                "average_receivables": r.get("averageReceivables"),
                "average_payables": r.get("averagePayables"),
                "average_inventory": r.get("averageInventory"),
                "days_sales_outstanding": r.get("daysSalesOutstanding"),
                "days_payables_outstanding": r.get("daysPayablesOutstanding"),
                "days_of_inventory_on_hand": r.get("daysOfInventoryOnHand"),
                "receivables_turnover": r.get("receivablesTurnover"),
                "payables_turnover": r.get("payablesTurnover"),
                "inventory_turnover": r.get("inventoryTurnover"),
                "capex_per_share": r.get("capexPerShare"),
                "working_capital": r.get("workingCapital"),
                "tangible_asset_value": r.get("tangibleAssetValue"),
                "extracted_at": extracted_at,
            })
        return rows

    results = self._fetch_batch(tickers, _fetch_one, label="key metrics")
    return pd.DataFrame(results) if results else pd.DataFrame()
```

### Step 2: Create `src/jobs/ingest_fmp_key_metrics.py`

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
TABLE = "sp500_key_metrics"
DEFAULT_PERIOD = "quarter"


def run(run_date: str, period: str = DEFAULT_PERIOD):
    print(f"Starting S&P 500 key metrics ingestion for {run_date} (period={period})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_key_metrics(tickers, period=period)

    if df.empty:
        print("No key metrics data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        period VARCHAR,
        fiscal_year VARCHAR,
        revenue_per_share FLOAT,
        net_income_per_share FLOAT,
        operating_cash_flow_per_share FLOAT,
        free_cash_flow_per_share FLOAT,
        cash_per_share FLOAT,
        book_value_per_share FLOAT,
        tangible_book_value_per_share FLOAT,
        shareholders_equity_per_share FLOAT,
        interest_debt_per_share FLOAT,
        market_cap NUMBER,
        enterprise_value NUMBER,
        pe_ratio FLOAT,
        price_to_sales_ratio FLOAT,
        pb_ratio FLOAT,
        ptb_ratio FLOAT,
        ev_to_sales FLOAT,
        enterprise_value_over_ebitda FLOAT,
        ev_to_operating_cash_flow FLOAT,
        ev_to_free_cash_flow FLOAT,
        earnings_yield FLOAT,
        free_cash_flow_yield FLOAT,
        dividend_yield FLOAT,
        payout_ratio FLOAT,
        debt_to_equity FLOAT,
        debt_to_assets FLOAT,
        net_debt_to_ebitda FLOAT,
        current_ratio FLOAT,
        interest_coverage FLOAT,
        income_quality FLOAT,
        roe FLOAT,
        roa FLOAT,
        roic FLOAT,
        invested_capital FLOAT,
        average_receivables FLOAT,
        average_payables FLOAT,
        average_inventory FLOAT,
        days_sales_outstanding FLOAT,
        days_payables_outstanding FLOAT,
        days_of_inventory_on_hand FLOAT,
        receivables_turnover FLOAT,
        payables_turnover FLOAT,
        inventory_turnover FLOAT,
        capex_per_share FLOAT,
        working_capital NUMBER,
        tangible_asset_value NUMBER,
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

    print(f"Successfully wrote {len(df)} key metrics records to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    period = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PERIOD
    run(run_date, period)
```

### Step 3: Create `src/jobs/ingest_fmp_key_metrics_backfill.py`

Identical to daily job — FMP returns full history by default. Separate entry point for manual Airflow trigger.

### Step 4: Create `dags/etl/fmp_key_metrics_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_key_metrics import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_key_metrics",
    default_args=default_args,
    description="Fetch S&P 500 valuation key metrics from FMP",
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

    ingest_key_metrics = PythonOperator(
        task_id="ingest_fmp_key_metrics",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_key_metrics
```

### Step 5: Create `dags/etl/fmp_key_metrics_backfill_dag.py`

```python
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_key_metrics_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fmp_key_metrics_backfill",
    default_args=default_args,
    description="Backfill S&P 500 valuation key metrics from FMP",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "backfill"],
) as dag:

    backfill_key_metrics = PythonOperator(
        task_id="backfill_fmp_key_metrics",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
```

### Step 6: Validate

```bash
astro dev parse
python -c "from src.jobs.ingest_fmp_key_metrics import run; run('2026-02-28')"
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/api_clients/fmp_client.py` | EDIT | Add `fetch_key_metrics()` method |
| `src/jobs/ingest_fmp_key_metrics.py` | CREATE | Daily key metrics job |
| `src/jobs/ingest_fmp_key_metrics_backfill.py` | CREATE | Backfill key metrics job |
| `dags/etl/fmp_key_metrics_dag.py` | CREATE | Daily DAG for key metrics |
| `dags/etl/fmp_key_metrics_backfill_dag.py` | CREATE | Backfill DAG for key metrics |

## Functions and interfaces

### `fmp_client.py` — new method

```python
def fetch_key_metrics(
    self, tickers: list[str], period: str = "quarter"
) -> pd.DataFrame:
    """Fetch key valuation metrics for a list of tickers.

    Args:
        tickers: List of ticker symbols.
        period: Fiscal period — "quarter" or "annual".

    Returns:
        DataFrame with 48 columns including valuation ratios, per-share
        metrics, efficiency ratios, and profitability metrics.
        Empty DataFrame if no data.
    """
    ...
```

### `ingest_fmp_key_metrics.py`

```python
def run(run_date: str, period: str = "quarter") -> None:
    """Fetch and load key metrics for all S&P 500 tickers."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/api_clients/fmp_client.py` | Adding 1 method — no existing method signatures change. |
| `src/loaders/snowflake_loader.py` | No changes. Uses existing `overwrite_date_range()`. |
| Airflow DAG registry | 2 new DAGs registered. |
| Snowflake schema | 1 new table created. |
| FMP rate budget | +500 requests/day (~50 seconds at 0.1s/req). |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| FMP returns empty array for a ticker | `_fetch_batch()` counts as failed; empty list returned. |
| FMP returns 429 (rate limit) | Handled by `_get()` retry logic. |
| `pe_ratio` is null (negative earnings) | Stored as NULL. Common for loss-making companies. |
| `enterprise_value_over_ebitda` is null (negative EBITDA) | Stored as NULL. |
| `dividend_yield` is 0 or null (non-dividend payer) | Stored as-is. 0 is valid. |
| Extremely large ratio values (>1000x P/E) | Stored as-is. Downstream dbt can cap or percentile-rank. |
| Negative ratio values (e.g., negative P/E) | Stored as-is in FLOAT column. |

## Observability

- `_fetch_batch()` logs progress every 50 tickers
- Final row count and date range printed
- Expected runtime: ~500 tickers x 0.1s/req = ~50 seconds

## Acceptance criteria

- [ ] `FMPClient.fetch_key_metrics()` returns a DataFrame with 48+ columns when called with valid tickers
- [ ] `src/jobs/ingest_fmp_key_metrics.py` creates `sp500_key_metrics` table and populates it
- [ ] Both DAGs parse without errors (`astro dev parse`)
- [ ] Daily DAG is gated on `sp500_lookup`
- [ ] Backfill DAG has `schedule=None`
- [ ] Running the same job twice produces no duplicate rows
- [ ] Key valuation columns (`pe_ratio`, `pb_ratio`, `ev_to_sales`, `dividend_yield`) are populated for most tickers
- [ ] `SELECT COUNT(*) FROM sp500_key_metrics` returns > 0 after a successful run
- [ ] `period` column contains Q1/Q2/Q3/Q4 or FY values

## Follow-ups

- Phase 1+: Create dbt staging model `stg_fmp_key_metrics.sql`
- Phase 1+: Create valuation scoring mart with P/E, P/B, EV/EBITDA percentile ranks
- Phase 1+: Sector-relative valuation (compare P/E within same GICS sector)
- Consider fetching both `period=quarter` and `period=annual` in a single job for completeness
- Validate all 48 fields against real API response during implementation — some fields may be null or missing for certain sectors (e.g., inventory_turnover for financials)
