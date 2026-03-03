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

# Fixed benchmark and sector ETF list — independent of S&P 500 universe lookup
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

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
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
