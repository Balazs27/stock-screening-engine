import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.api_clients.polygon_client import PolygonClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_date_range_with_variants,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_news_backfill"
DEFAULT_LOOKBACK_DAYS = 398


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS):
    end_date = datetime.strptime(run_date, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=lookback_days)

    print(f"Starting S&P 500 news backfill: {start_date} to {end_date} ({lookback_days} days)...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_news_range(tickers, str(start_date), str(end_date))

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

    overwrite_date_range_with_variants(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=str(start_date),
        end_date=str(end_date),
        create_table_sql=create_table_sql,
        variant_columns=["tickers", "keywords"],
    )

    print(f"Successfully wrote {len(df)} articles to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
