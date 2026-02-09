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
TABLE = "sp500_income_statements"
DEFAULT_PERIOD = "annual"


def run(run_date: str, period: str = DEFAULT_PERIOD):
    print(f"Starting S&P 500 income statement ingestion for {run_date} (period={period})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_income_statements(tickers, period=period)

    if df.empty:
        print("No income statement data fetched.")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR,
        date DATE,
        reported_currency VARCHAR,
        cik VARCHAR,
        filing_date DATE,
        accepted_date TIMESTAMP_NTZ,
        fiscal_year VARCHAR,
        period VARCHAR,
        revenue NUMBER,
        cost_of_revenue NUMBER,
        gross_profit NUMBER,
        research_and_development_expenses NUMBER,
        general_and_administrative_expenses NUMBER,
        selling_and_marketing_expenses NUMBER,
        selling_general_and_administrative_expenses NUMBER,
        other_expenses NUMBER,
        operating_expenses NUMBER,
        cost_and_expenses NUMBER,
        net_interest_income NUMBER,
        interest_income NUMBER,
        interest_expense NUMBER,
        depreciation_and_amortization NUMBER,
        ebitda NUMBER,
        ebit NUMBER,
        non_operating_income_excluding_interest NUMBER,
        operating_income NUMBER,
        total_other_income_expenses_net NUMBER,
        income_before_tax NUMBER,
        income_tax_expense NUMBER,
        net_income_from_continuing_operations NUMBER,
        net_income_from_discontinued_operations NUMBER,
        other_adjustments_to_net_income NUMBER,
        net_income NUMBER,
        net_income_deductions NUMBER,
        bottom_line_net_income NUMBER,
        eps FLOAT,
        eps_diluted FLOAT,
        weighted_average_shares_out NUMBER,
        weighted_average_shares_out_diluted NUMBER,
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

    print(f"Successfully wrote {len(df)} income statements to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    period = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PERIOD
    run(run_date, period)
