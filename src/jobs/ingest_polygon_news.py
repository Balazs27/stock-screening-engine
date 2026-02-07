import sys
import os
from dotenv import load_dotenv

from src.api_clients.polygon_client import PolygonClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_partition_with_variants,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_news"
DEFAULT_LIMIT_PER_TICKER = 10


def run(run_date: str, limit_per_ticker: int = DEFAULT_LIMIT_PER_TICKER):
    print(f"Starting S&P 500 news ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_news(tickers, run_date, limit_per_ticker=limit_per_ticker)

    if df.empty:
        print("No news articles fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        TICKER VARCHAR,
        ARTICLE_ID VARCHAR,
        PUBLISHER_NAME VARCHAR,
        PUBLISHER_HOMEPAGE_URL VARCHAR,
        PUBLISHER_LOGO_URL VARCHAR,
        TITLE VARCHAR,
        AUTHOR VARCHAR,
        PUBLISHED_UTC TIMESTAMP_NTZ,
        ARTICLE_URL VARCHAR,
        TICKERS VARIANT,
        IMAGE_URL VARCHAR,
        DESCRIPTION VARCHAR,
        KEYWORDS VARIANT,
        DATE DATE,
        EXTRACTED_AT TIMESTAMP_NTZ,
        PRIMARY KEY (ARTICLE_ID, TICKER)
    )
    """

    fq_table = f"{schema}.{TABLE}"

    overwrite_partition_with_variants(
        session=session,
        df=df,
        table_name=fq_table,
        partition_col="DATE",
        partition_value=run_date,
        create_table_sql=create_table_sql,
        variant_columns=["tickers", "keywords"],
    )

    print(f"Successfully wrote {len(df)} articles to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LIMIT_PER_TICKER
    run(run_date, limit)
