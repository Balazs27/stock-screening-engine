import sys
import os
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_partition,
)
from src.utils.dates import today

TABLE = "sp500_fmp_press_releases"


def run(run_date: str):
    print(f"Starting FMP press releases ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = FMPClient()
    df = client.fetch_press_releases(run_date)

    if df.empty:
        print("No FMP press releases fetched.")
        session.close()
        return

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        symbol VARCHAR,
        title VARCHAR,
        date DATE,
        content VARCHAR,
        image_url VARCHAR,
        article_url VARCHAR,
        site VARCHAR,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (article_url)
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

    print(f"Successfully wrote {len(df)} press releases to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    run(run_date)
