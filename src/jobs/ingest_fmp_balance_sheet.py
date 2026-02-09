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
TABLE = "sp500_balance_sheets"
DEFAULT_PERIOD = "annual"


def run(run_date: str, period: str = DEFAULT_PERIOD):
    print(f"Starting S&P 500 balance sheet ingestion for {run_date} (period={period})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_balance_sheets(tickers, period=period)

    if df.empty:
        print("No balance sheet data fetched.")
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
        cash_and_cash_equivalents NUMBER,
        short_term_investments NUMBER,
        cash_and_short_term_investments NUMBER,
        net_receivables NUMBER,
        accounts_receivables NUMBER,
        other_receivables NUMBER,
        inventory NUMBER,
        prepaids NUMBER,
        other_current_assets NUMBER,
        total_current_assets NUMBER,
        property_plant_equipment_net NUMBER,
        goodwill NUMBER,
        intangible_assets NUMBER,
        goodwill_and_intangible_assets NUMBER,
        long_term_investments NUMBER,
        tax_assets NUMBER,
        other_non_current_assets NUMBER,
        total_non_current_assets NUMBER,
        other_assets NUMBER,
        total_assets NUMBER,
        total_payables NUMBER,
        account_payables NUMBER,
        other_payables NUMBER,
        accrued_expenses NUMBER,
        short_term_debt NUMBER,
        capital_lease_obligations_current NUMBER,
        tax_payables NUMBER,
        deferred_revenue NUMBER,
        other_current_liabilities NUMBER,
        total_current_liabilities NUMBER,
        long_term_debt NUMBER,
        deferred_revenue_non_current NUMBER,
        deferred_tax_liabilities_non_current NUMBER,
        other_non_current_liabilities NUMBER,
        total_non_current_liabilities NUMBER,
        other_liabilities NUMBER,
        capital_lease_obligations NUMBER,
        total_liabilities NUMBER,
        treasury_stock NUMBER,
        preferred_stock NUMBER,
        common_stock NUMBER,
        retained_earnings NUMBER,
        additional_paid_in_capital NUMBER,
        accumulated_other_comprehensive_income_loss NUMBER,
        other_total_stockholders_equity NUMBER,
        total_stockholders_equity NUMBER,
        total_equity NUMBER,
        minority_interest NUMBER,
        total_liabilities_and_total_equity NUMBER,
        total_investments NUMBER,
        total_debt NUMBER,
        net_debt NUMBER,
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

    print(f"Successfully wrote {len(df)} balance sheets to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    period = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PERIOD
    run(run_date, period)
