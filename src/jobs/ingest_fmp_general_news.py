import sys
import os
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_partition,
)
from src.utils.dates import today

TABLE = "sp500_fmp_general_news"


def run(run_date: str):
    print(f"Starting FMP general news ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = FMPClient()
    df = client.fetch_general_news(run_date)

    if df.empty:
        print("No FMP general news articles fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        symbol VARCHAR,
        published_date TIMESTAMP_NTZ,
        publisher VARCHAR,
        title VARCHAR,
        image_url VARCHAR,
        site VARCHAR,
        content VARCHAR,
        article_url VARCHAR,
        date DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (article_url)
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

    print(f"Successfully wrote {len(df)} FMP general news articles to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    run(run_date)
