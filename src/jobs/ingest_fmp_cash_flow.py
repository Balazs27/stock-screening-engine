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
TABLE = "sp500_cash_flow_statements"
DEFAULT_PERIOD = "annual"


def run(run_date: str, period: str = DEFAULT_PERIOD):
    print(f"Starting S&P 500 cash flow statement ingestion for {run_date} (period={period})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_cash_flow_statements(tickers, period=period)

    if df.empty:
        print("No cash flow statement data fetched.")
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
        net_income NUMBER,
        depreciation_and_amortization NUMBER,
        deferred_income_tax NUMBER,
        stock_based_compensation NUMBER,
        change_in_working_capital NUMBER,
        accounts_receivables NUMBER,
        inventory NUMBER,
        accounts_payables NUMBER,
        other_working_capital NUMBER,
        other_non_cash_items NUMBER,
        net_cash_provided_by_operating_activities NUMBER,
        investments_in_property_plant_and_equipment NUMBER,
        acquisitions_net NUMBER,
        purchases_of_investments NUMBER,
        sales_maturities_of_investments NUMBER,
        other_investing_activities NUMBER,
        net_cash_provided_by_investing_activities NUMBER,
        net_debt_issuance NUMBER,
        long_term_net_debt_issuance NUMBER,
        short_term_net_debt_issuance NUMBER,
        net_stock_issuance NUMBER,
        net_common_stock_issuance NUMBER,
        common_stock_issuance NUMBER,
        common_stock_repurchased NUMBER,
        net_preferred_stock_issuance NUMBER,
        net_dividends_paid NUMBER,
        common_dividends_paid NUMBER,
        preferred_dividends_paid NUMBER,
        other_financing_activities NUMBER,
        net_cash_provided_by_financing_activities NUMBER,
        effect_of_forex_changes_on_cash NUMBER,
        net_change_in_cash NUMBER,
        cash_at_end_of_period NUMBER,
        cash_at_beginning_of_period NUMBER,
        operating_cash_flow NUMBER,
        capital_expenditure NUMBER,
        free_cash_flow NUMBER,
        income_taxes_paid NUMBER,
        interest_paid NUMBER,
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

    print(f"Successfully wrote {len(df)} cash flow statements to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    period = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PERIOD
    run(run_date, period)
