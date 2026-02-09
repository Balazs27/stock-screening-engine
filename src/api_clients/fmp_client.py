# --------------------
# FMP API Client
# --------------------
# Handles: auth, rate limiting, retries, concurrent fetching.
# Returns: pandas DataFrames. Never touches Snowflake.

import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import pandas as pd
import requests

BASE_URL = "https://financialmodelingprep.com"
MAX_WORKERS = 8
MIN_REQUEST_INTERVAL = 0.1  # ~600 req/min (conservative for 750/min tier)
MAX_RETRIES = 3


class FMPClient:

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ["FMP_API_KEY"]
        self._rate_limit_lock = Lock()
        self._last_request_time = time.time()

    # --------------------------------------------------
    # Core: rate-limited GET with retry
    # --------------------------------------------------

    def _get(self, url: str) -> requests.Response:
        for attempt in range(MAX_RETRIES):
            with self._rate_limit_lock:
                elapsed = time.time() - self._last_request_time
                if elapsed < MIN_REQUEST_INTERVAL:
                    time.sleep(MIN_REQUEST_INTERVAL - elapsed)
                response = requests.get(url, timeout=10)
                self._last_request_time = time.time()

            if response.status_code == 429:
                wait = min(2 ** attempt, 32)
                print(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue

            return response

        return response  # return last response even if still 429

    # --------------------------------------------------
    # Core: concurrent fetch across a list of tickers
    # --------------------------------------------------

    def _fetch_batch(self, tickers, fetch_fn, label="records"):
        all_results = []
        start_time = time.time()
        successful = 0
        failed = 0

        print(f"Starting fetch with {MAX_WORKERS} workers for {len(tickers)} tickers...")
        print(f"Rate limit: ~600 requests/min ({MIN_REQUEST_INTERVAL}s between requests)")
        print(f"Expected time: ~{(len(tickers) * MIN_REQUEST_INTERVAL) / 60:.1f} minutes\n")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_fn, t): t for t in tickers}

            for i, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                all_results.extend(result)

                if result:
                    successful += 1
                else:
                    failed += 1

                if i % 50 == 0 or i == len(tickers):
                    elapsed = time.time() - start_time
                    pct = (i / len(tickers)) * 100
                    eta = ((elapsed / i) * (len(tickers) - i)) / 60
                    print(
                        f"Progress: {i}/{len(tickers)} ({pct:.1f}%) | "
                        f"Elapsed: {elapsed/60:.1f}m | ETA: {eta:.1f}m | "
                        f"{label}: {len(all_results)} | "
                        f"Success: {successful} | Failed: {failed}"
                    )

        total_time = time.time() - start_time
        print(f"\nFetch completed in {total_time/60:.1f} minutes")
        print(f"Total: {len(all_results)} {label} from {successful}/{len(tickers)} tickers\n")

        return all_results

    # --------------------------------------------------
    # Endpoint: Income Statements
    # --------------------------------------------------

    def fetch_income_statements(
        self, tickers: list[str], period: str = "annual"
    ) -> pd.DataFrame:
        """Fetch income statements for a list of tickers."""

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/income-statement"
                f"?symbol={ticker}"
                f"&period={period}"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            if not data or isinstance(data, dict):
                return []
            extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = []
            for r in data:
                accepted_date = None
                if r.get("acceptedDate"):
                    try:
                        accepted_date = datetime.strptime(
                            r["acceptedDate"], "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:
                        accepted_date = None
                rows.append(
                    {
                        "ticker": ticker,
                        "date": r.get("date"),
                        "reported_currency": r.get("reportedCurrency"),
                        "cik": r.get("cik"),
                        "filing_date": r.get("filingDate"),
                        "accepted_date": accepted_date,
                        "fiscal_year": r.get("fiscalYear"),
                        "period": r.get("period"),
                        "revenue": r.get("revenue"),
                        "cost_of_revenue": r.get("costOfRevenue"),
                        "gross_profit": r.get("grossProfit"),
                        "research_and_development_expenses": r.get("researchAndDevelopmentExpenses"),
                        "general_and_administrative_expenses": r.get("generalAndAdministrativeExpenses"),
                        "selling_and_marketing_expenses": r.get("sellingAndMarketingExpenses"),
                        "selling_general_and_administrative_expenses": r.get("sellingGeneralAndAdministrativeExpenses"),
                        "other_expenses": r.get("otherExpenses"),
                        "operating_expenses": r.get("operatingExpenses"),
                        "cost_and_expenses": r.get("costAndExpenses"),
                        "net_interest_income": r.get("netInterestIncome"),
                        "interest_income": r.get("interestIncome"),
                        "interest_expense": r.get("interestExpense"),
                        "depreciation_and_amortization": r.get("depreciationAndAmortization"),
                        "ebitda": r.get("ebitda"),
                        "ebit": r.get("ebit"),
                        "non_operating_income_excluding_interest": r.get("nonOperatingIncomeExcludingInterest"),
                        "operating_income": r.get("operatingIncome"),
                        "total_other_income_expenses_net": r.get("totalOtherIncomeExpensesNet"),
                        "income_before_tax": r.get("incomeBeforeTax"),
                        "income_tax_expense": r.get("incomeTaxExpense"),
                        "net_income_from_continuing_operations": r.get("netIncomeFromContinuingOperations"),
                        "net_income_from_discontinued_operations": r.get("netIncomeFromDiscontinuedOperations"),
                        "other_adjustments_to_net_income": r.get("otherAdjustmentsToNetIncome"),
                        "net_income": r.get("netIncome"),
                        "net_income_deductions": r.get("netIncomeDeductions"),
                        "bottom_line_net_income": r.get("bottomLineNetIncome"),
                        "eps": r.get("eps"),
                        "eps_diluted": r.get("epsDiluted"),
                        "weighted_average_shares_out": r.get("weightedAverageShsOut"),
                        "weighted_average_shares_out_diluted": r.get("weightedAverageShsOutDil"),
                        "extracted_at": extracted_at,
                    }
                )
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="income statements")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Balance Sheets
    # --------------------------------------------------

    def fetch_balance_sheets(
        self, tickers: list[str], period: str = "annual"
    ) -> pd.DataFrame:
        """Fetch balance sheet statements for a list of tickers."""

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/balance-sheet-statement"
                f"?symbol={ticker}"
                f"&period={period}"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            if not data or isinstance(data, dict):
                return []
            extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = []
            for r in data:
                accepted_date = None
                if r.get("acceptedDate"):
                    try:
                        accepted_date = datetime.strptime(
                            r["acceptedDate"], "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:
                        accepted_date = None
                rows.append(
                    {
                        "ticker": ticker,
                        "date": r.get("date"),
                        "reported_currency": r.get("reportedCurrency"),
                        "cik": r.get("cik"),
                        "filing_date": r.get("filingDate"),
                        "accepted_date": accepted_date,
                        "fiscal_year": r.get("fiscalYear"),
                        "period": r.get("period"),
                        "cash_and_cash_equivalents": r.get("cashAndCashEquivalents"),
                        "short_term_investments": r.get("shortTermInvestments"),
                        "cash_and_short_term_investments": r.get("cashAndShortTermInvestments"),
                        "net_receivables": r.get("netReceivables"),
                        "accounts_receivables": r.get("accountsReceivables"),
                        "other_receivables": r.get("otherReceivables"),
                        "inventory": r.get("inventory"),
                        "prepaids": r.get("prepaids"),
                        "other_current_assets": r.get("otherCurrentAssets"),
                        "total_current_assets": r.get("totalCurrentAssets"),
                        "property_plant_equipment_net": r.get("propertyPlantEquipmentNet"),
                        "goodwill": r.get("goodwill"),
                        "intangible_assets": r.get("intangibleAssets"),
                        "goodwill_and_intangible_assets": r.get("goodwillAndIntangibleAssets"),
                        "long_term_investments": r.get("longTermInvestments"),
                        "tax_assets": r.get("taxAssets"),
                        "other_non_current_assets": r.get("otherNonCurrentAssets"),
                        "total_non_current_assets": r.get("totalNonCurrentAssets"),
                        "other_assets": r.get("otherAssets"),
                        "total_assets": r.get("totalAssets"),
                        "total_payables": r.get("totalPayables"),
                        "account_payables": r.get("accountPayables"),
                        "other_payables": r.get("otherPayables"),
                        "accrued_expenses": r.get("accruedExpenses"),
                        "short_term_debt": r.get("shortTermDebt"),
                        "capital_lease_obligations_current": r.get("capitalLeaseObligationsCurrent"),
                        "tax_payables": r.get("taxPayables"),
                        "deferred_revenue": r.get("deferredRevenue"),
                        "other_current_liabilities": r.get("otherCurrentLiabilities"),
                        "total_current_liabilities": r.get("totalCurrentLiabilities"),
                        "long_term_debt": r.get("longTermDebt"),
                        "deferred_revenue_non_current": r.get("deferredRevenueNonCurrent"),
                        "deferred_tax_liabilities_non_current": r.get("deferredTaxLiabilitiesNonCurrent"),
                        "other_non_current_liabilities": r.get("otherNonCurrentLiabilities"),
                        "total_non_current_liabilities": r.get("totalNonCurrentLiabilities"),
                        "other_liabilities": r.get("otherLiabilities"),
                        "capital_lease_obligations": r.get("capitalLeaseObligations"),
                        "total_liabilities": r.get("totalLiabilities"),
                        "treasury_stock": r.get("treasuryStock"),
                        "preferred_stock": r.get("preferredStock"),
                        "common_stock": r.get("commonStock"),
                        "retained_earnings": r.get("retainedEarnings"),
                        "additional_paid_in_capital": r.get("additionalPaidInCapital"),
                        "accumulated_other_comprehensive_income_loss": r.get("accumulatedOtherComprehensiveIncomeLoss"),
                        "other_total_stockholders_equity": r.get("otherTotalStockholdersEquity"),
                        "total_stockholders_equity": r.get("totalStockholdersEquity"),
                        "total_equity": r.get("totalEquity"),
                        "minority_interest": r.get("minorityInterest"),
                        "total_liabilities_and_total_equity": r.get("totalLiabilitiesAndTotalEquity"),
                        "total_investments": r.get("totalInvestments"),
                        "total_debt": r.get("totalDebt"),
                        "net_debt": r.get("netDebt"),
                        "extracted_at": extracted_at,
                    }
                )
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="balance sheets")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Cash Flow Statements
    # --------------------------------------------------

    def fetch_cash_flow_statements(
        self, tickers: list[str], period: str = "annual"
    ) -> pd.DataFrame:
        """Fetch cash flow statements for a list of tickers."""

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/cash-flow-statement"
                f"?symbol={ticker}"
                f"&period={period}"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            if not data or isinstance(data, dict):
                return []
            extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = []
            for r in data:
                accepted_date = None
                if r.get("acceptedDate"):
                    try:
                        accepted_date = datetime.strptime(
                            r["acceptedDate"], "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:
                        accepted_date = None
                rows.append(
                    {
                        "ticker": ticker,
                        "date": r.get("date"),
                        "reported_currency": r.get("reportedCurrency"),
                        "cik": r.get("cik"),
                        "filing_date": r.get("filingDate"),
                        "accepted_date": accepted_date,
                        "fiscal_year": r.get("fiscalYear"),
                        "period": r.get("period"),
                        "net_income": r.get("netIncome"),
                        "depreciation_and_amortization": r.get("depreciationAndAmortization"),
                        "deferred_income_tax": r.get("deferredIncomeTax"),
                        "stock_based_compensation": r.get("stockBasedCompensation"),
                        "change_in_working_capital": r.get("changeInWorkingCapital"),
                        "accounts_receivables": r.get("accountsReceivables"),
                        "inventory": r.get("inventory"),
                        "accounts_payables": r.get("accountsPayables"),
                        "other_working_capital": r.get("otherWorkingCapital"),
                        "other_non_cash_items": r.get("otherNonCashItems"),
                        "net_cash_provided_by_operating_activities": r.get("netCashProvidedByOperatingActivities"),
                        "investments_in_property_plant_and_equipment": r.get("investmentsInPropertyPlantAndEquipment"),
                        "acquisitions_net": r.get("acquisitionsNet"),
                        "purchases_of_investments": r.get("purchasesOfInvestments"),
                        "sales_maturities_of_investments": r.get("salesMaturitiesOfInvestments"),
                        "other_investing_activities": r.get("otherInvestingActivities"),
                        "net_cash_provided_by_investing_activities": r.get("netCashProvidedByInvestingActivities"),
                        "net_debt_issuance": r.get("netDebtIssuance"),
                        "long_term_net_debt_issuance": r.get("longTermNetDebtIssuance"),
                        "short_term_net_debt_issuance": r.get("shortTermNetDebtIssuance"),
                        "net_stock_issuance": r.get("netStockIssuance"),
                        "net_common_stock_issuance": r.get("netCommonStockIssuance"),
                        "common_stock_issuance": r.get("commonStockIssuance"),
                        "common_stock_repurchased": r.get("commonStockRepurchased"),
                        "net_preferred_stock_issuance": r.get("netPreferredStockIssuance"),
                        "net_dividends_paid": r.get("netDividendsPaid"),
                        "common_dividends_paid": r.get("commonDividendsPaid"),
                        "preferred_dividends_paid": r.get("preferredDividendsPaid"),
                        "other_financing_activities": r.get("otherFinancingActivities"),
                        "net_cash_provided_by_financing_activities": r.get("netCashProvidedByFinancingActivities"),
                        "effect_of_forex_changes_on_cash": r.get("effectOfForexChangesOnCash"),
                        "net_change_in_cash": r.get("netChangeInCash"),
                        "cash_at_end_of_period": r.get("cashAtEndOfPeriod"),
                        "cash_at_beginning_of_period": r.get("cashAtBeginningOfPeriod"),
                        "operating_cash_flow": r.get("operatingCashFlow"),
                        "capital_expenditure": r.get("capitalExpenditure"),
                        "free_cash_flow": r.get("freeCashFlow"),
                        "income_taxes_paid": r.get("incomeTaxesPaid"),
                        "interest_paid": r.get("interestPaid"),
                        "extracted_at": extracted_at,
                    }
                )
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="cash flow statements")
        return pd.DataFrame(results) if results else pd.DataFrame()
