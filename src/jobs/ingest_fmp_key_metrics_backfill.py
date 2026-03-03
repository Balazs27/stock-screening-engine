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
DEFAULT_LOOKBACK_DAYS = 1826  # ~5 years
DEFAULT_PERIOD = "quarter"


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS, period: str = DEFAULT_PERIOD):
    print(f"Starting S&P 500 key metrics backfill for {run_date} (lookback={lookback_days}d)...")

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

    from datetime import datetime, timedelta
    cutoff = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    df = df[df["date"].notna() & (df["date"] >= cutoff)]

    if df.empty:
        print(f"No data within lookback window (>= {cutoff}).")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        ticker VARCHAR,
        date DATE,
        period VARCHAR,
        fiscal_year VARCHAR,
        reported_currency VARCHAR,
        market_cap NUMBER,
        enterprise_value NUMBER,
        ev_to_sales FLOAT,
        ev_to_operating_cash_flow FLOAT,
        ev_to_free_cash_flow FLOAT,
        ev_to_ebitda FLOAT,
        net_debt_to_ebitda FLOAT,
        current_ratio FLOAT,
        income_quality FLOAT,
        graham_number FLOAT,
        graham_net_net FLOAT,
        tax_burden FLOAT,
        interest_burden FLOAT,
        working_capital NUMBER,
        invested_capital FLOAT,
        return_on_assets FLOAT,
        operating_return_on_assets FLOAT,
        return_on_tangible_assets FLOAT,
        return_on_equity FLOAT,
        return_on_invested_capital FLOAT,
        return_on_capital_employed FLOAT,
        earnings_yield FLOAT,
        free_cash_flow_yield FLOAT,
        capex_to_operating_cash_flow FLOAT,
        capex_to_depreciation FLOAT,
        capex_to_revenue FLOAT,
        sales_general_and_administrative_to_revenue FLOAT,
        research_and_development_to_revenue FLOAT,
        stock_based_compensation_to_revenue FLOAT,
        intangibles_to_total_assets FLOAT,
        average_receivables FLOAT,
        average_payables FLOAT,
        average_inventory FLOAT,
        days_of_sales_outstanding FLOAT,
        days_of_payables_outstanding FLOAT,
        days_of_inventory_outstanding FLOAT,
        operating_cycle FLOAT,
        cash_conversion_cycle FLOAT,
        free_cash_flow_to_equity FLOAT,
        free_cash_flow_to_firm FLOAT,
        tangible_asset_value NUMBER,
        net_current_asset_value NUMBER,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date, period)
    )
    """

    overwrite_date_range(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=start_date,
        end_date=end_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} key metrics backfill records to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
