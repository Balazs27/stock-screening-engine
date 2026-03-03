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
TABLE_RATINGS = "sp500_analyst_grades_consensus"


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
        fq_targets = f"{schema}.{TABLE_TARGETS}"
        create_targets_sql = f"""
        CREATE TABLE IF NOT EXISTS {fq_targets} (
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
        fq_ratings = f"{schema}.{TABLE_RATINGS}"
        create_ratings_sql = f"""
        CREATE TABLE IF NOT EXISTS {fq_ratings} (
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
