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

    # --------------------------------------------------
    # Endpoint: News - FMP Articles (global paginated feed)
    # --------------------------------------------------

    def fetch_fmp_articles(
        self, tickers: list[str], run_date: str, max_pages: int = 20, start_date: str = None
    ) -> pd.DataFrame:
        """Fetch FMP articles for a date (or date range), filtered to S&P 500 tickers.

        Unlike other methods, this is NOT per-ticker. FMP exposes a global
        article feed (/stable/fmp-articles) that we paginate through and filter.
        Ticker format: "NYSE:MRK" or "NYSE:MRK,NASDAQ:AAPL" — exchange prefix stripped.

        Args:
            start_date: If provided, fetch articles from start_date to run_date (backfill mode).
                        If None, fetch only articles matching run_date (daily mode).
        """
        effective_start = start_date or run_date
        ticker_set = set(tickers)
        all_articles = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Fetching FMP articles from {effective_start} to {run_date} (filtering to {len(tickers)} S&P 500 tickers)...")

        for page in range(max_pages):
            url = (
                f"{BASE_URL}/stable/fmp-articles"
                f"?page={page}"
                f"&limit=250"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  Page {page}: HTTP {response.status_code}, stopping.")
                break

            data = response.json()
            if not data:
                print(f"  Page {page}: empty response, stopping.")
                break

            page_matches = 0
            found_older = False

            for article in data:
                article_date_str = article.get("date", "")
                article_date = article_date_str[:10] if article_date_str else None

                if not article_date or article_date > run_date:
                    continue

                if article_date < effective_start:
                    found_older = True
                    continue

                # Parse tickers — format: "NYSE:MRK" or "NYSE:MRK,NASDAQ:AAPL"
                raw_tickers = article.get("tickers", "")
                mentioned = [
                    t.split(":")[-1].strip()
                    for t in raw_tickers.split(",")
                    if t.strip()
                ]
                matching = [t for t in mentioned if t in ticker_set]

                for ticker in matching:
                    all_articles.append(
                        {
                            "ticker": ticker,
                            "title": article.get("title"),
                            "date": article_date,
                            "content": article.get("content"),
                            "article_tickers": raw_tickers,
                            "image_url": article.get("image"),
                            "article_url": article.get("link"),
                            "author": article.get("author"),
                            "site": article.get("site"),
                            "extracted_at": extracted_at,
                        }
                    )
                    page_matches += 1

            print(
                f"  Page {page}: {len(data)} articles, "
                f"{page_matches} matched S&P 500 tickers"
            )

            if found_older:
                print(f"  Reached articles older than {effective_start}, stopping.")
                break

        print(f"\nTotal: {len(all_articles)} articles from {effective_start} to {run_date}\n")
        return pd.DataFrame(all_articles) if all_articles else pd.DataFrame()
    
    # --------------------------------------------------
    # Endpoint: News - FMP General News (global paginated feed)
    # --------------------------------------------------

    def fetch_general_news(
        self, run_date: str, max_pages: int = 20, start_date: str = None
    ) -> pd.DataFrame:
        """Fetch general news for a date (or date range), unfiltered.

        Global paginated feed (/stable/news/general-latest). Not stock-specific —
        returns all general market news regardless of ticker.

        Args:
            start_date: If provided, fetch articles from start_date to run_date (backfill mode).
                        If None, fetch only articles matching run_date (daily mode).
        """
        effective_start = start_date or run_date
        all_articles = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Fetching FMP general news from {effective_start} to {run_date}...")

        for page in range(max_pages):
            url = (
                f"{BASE_URL}/stable/news/general-latest"
                f"?page={page}"
                f"&limit=250"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  Page {page}: HTTP {response.status_code}, stopping.")
                break

            data = response.json()
            if not data:
                print(f"  Page {page}: empty response, stopping.")
                break

            page_matches = 0
            found_older = False

            for article in data:
                # general-latest uses "publishedDate" as the date field
                article_date_str = article.get("publishedDate", "")
                article_date = article_date_str[:10] if article_date_str else None

                if not article_date or article_date > run_date:
                    continue

                if article_date < effective_start:
                    found_older = True
                    continue

                symbol = (article.get("symbol") or "").strip() or None

                all_articles.append(
                    {
                        "symbol": symbol,
                        "published_date": article.get("publishedDate"),
                        "publisher": article.get("publisher"),
                        "title": article.get("title"),
                        "site": article.get("site"),
                        "content": article.get("text"),
                        "image_url": article.get("image"),
                        "article_url": article.get("url"),
                        "date": article_date,
                        "extracted_at": extracted_at,
                    }
                )
                page_matches += 1

            print(
                f"  Page {page}: {len(data)} articles, "
                f"{page_matches} within date range"
            )

            if found_older:
                print(f"  Reached articles older than {effective_start}, stopping.")
                break

        print(f"\nTotal: {len(all_articles)} general news articles from {effective_start} to {run_date}\n")
        return pd.DataFrame(all_articles) if all_articles else pd.DataFrame()
    
    # --------------------------------------------------
    # Endpoint: News - FMP Press Releases (global paginated feed)
    # --------------------------------------------------

    def fetch_press_releases(
        self, run_date: str, max_pages: int = 20, start_date: str = None
    ) -> pd.DataFrame:
        """Fetch press releases for a date (or date range), unfiltered.

        Global paginated feed (/stable/news/press-releases-latest). Not stock-specific —
        returns all press releases regardless of ticker.

        Args:
            start_date: If provided, fetch articles from start_date to run_date (backfill mode).
                        If None, fetch only articles matching run_date (daily mode).
        """
        effective_start = start_date or run_date
        all_articles = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Fetching FMP press releases from {effective_start} to {run_date}...")

        for page in range(max_pages):
            url = (
                f"{BASE_URL}/stable/news/press-releases-latest"
                f"?page={page}"
                f"&limit=250"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  Page {page}: HTTP {response.status_code}, stopping.")
                break

            data = response.json()
            if not data:
                print(f"  Page {page}: empty response, stopping.")
                break

            page_matches = 0
            found_older = False

            for article in data:
                article_date_str = article.get("publishedDate", "")
                article_date = article_date_str[:10] if article_date_str else None

                if not article_date or article_date > run_date:
                    continue

                if article_date < effective_start:
                    found_older = True
                    continue

                symbol = (article.get("symbol") or "").strip() or None

                all_articles.append(
                    {
                        "symbol": symbol,
                        "title": article.get("title"),
                        "date": article_date,
                        "content": article.get("text"),
                        "image_url": article.get("image"),
                        "article_url": article.get("url"),
                        "site": article.get("site"),
                        "extracted_at": extracted_at,
                    }
                )
                page_matches += 1

            print(
                f"  Page {page}: {len(data)} press releases, "
                f"{page_matches} within date range"
            )

            if found_older:
                print(f"  Reached articles older than {effective_start}, stopping.")
                break

        print(f"\nTotal: {len(all_articles)} press releases from {effective_start} to {run_date}\n")
        return pd.DataFrame(all_articles) if all_articles else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: News - FMP Stock News (global paginated feed)
    # --------------------------------------------------

    def fetch_stock_news(
        self, tickers: list[str], run_date: str, max_pages: int = 20, start_date: str = None
    ) -> pd.DataFrame:
        """Fetch stock-specific news for a date (or date range), filtered to S&P 500 tickers.

        Endpoint: /stable/news/stock-latest
        Ticker field: "symbol" — plain ticker, no exchange prefix (can be null).

        Args:
            start_date: If provided, fetch articles from start_date to run_date (backfill mode).
                        If None, fetch only articles matching run_date (daily mode).
        """
        effective_start = start_date or run_date
        ticker_set = set(tickers)
        all_articles = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Fetching FMP stock news from {effective_start} to {run_date} (filtering to {len(tickers)} S&P 500 tickers)...")

        for page in range(max_pages):
            url = (
                f"{BASE_URL}/stable/news/stock-latest"
                f"?page={page}"
                f"&limit=250"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  Page {page}: HTTP {response.status_code}, stopping.")
                break

            data = response.json()
            if not data:
                print(f"  Page {page}: empty response, stopping.")
                break

            page_matches = 0
            found_older = False

            for article in data:
                article_date_str = article.get("publishedDate", "")
                article_date = article_date_str[:10] if article_date_str else None

                if not article_date or article_date > run_date:
                    continue

                if article_date < effective_start:
                    found_older = True
                    continue

                symbol = (article.get("symbol") or "").strip()
                if not symbol or symbol not in ticker_set:
                    continue

                all_articles.append(
                    {
                        "ticker": symbol,
                        "published_date": article.get("publishedDate"),
                        "title": article.get("title"),
                        "date": article_date,
                        "content": article.get("text"),
                        "image_url": article.get("image"),
                        "article_url": article.get("url"),
                        "site": article.get("site"),
                        "extracted_at": extracted_at,
                    }
                )
                page_matches += 1

            print(
                f"  Page {page}: {len(data)} stock news articles, "
                f"{page_matches} matched S&P 500 tickers"
            )

            if found_older:
                print(f"  Reached articles older than {effective_start}, stopping.")
                break

        print(f"\nTotal: {len(all_articles)} stock news articles from {effective_start} to {run_date}\n")
        return pd.DataFrame(all_articles) if all_articles else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Earnings Calendar (global, filtered to S&P 500)
    # --------------------------------------------------

    def fetch_earnings_calendar(
        self, tickers: list[str], from_date: str, to_date: str
    ) -> pd.DataFrame:
        """Fetch earnings calendar for a date range, filtered to S&P 500 tickers.

        Unlike per-ticker methods, this calls a single global endpoint and
        filters the results to the provided ticker list.

        Args:
            tickers: S&P 500 ticker list for post-fetch filtering.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).

        Returns:
            DataFrame with columns: ticker, date, eps, eps_estimated, time,
            revenue, revenue_estimated, updated_from_date, fiscal_date_ending,
            extracted_at. Empty DataFrame if no data.
        """
        # NOTE: Max 90-day date range per API call. Retrieve historical values up to 5 years.
        ticker_set = set(tickers)
        url = (
            f"{BASE_URL}/stable/earnings-calendar"
            f"?from={from_date}"
            f"&to={to_date}"
            f"&apikey={self.api_key}"
        )
        response = self._get(url)
        if response.status_code != 200:
            print(f"Earnings calendar HTTP {response.status_code}")
            return pd.DataFrame()

        data = response.json()
        if not data or isinstance(data, dict):
            return pd.DataFrame()

        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for r in data:
            symbol = r.get("symbol", "")
            if symbol not in ticker_set:
                continue
            rows.append({
                "ticker": symbol,
                "date": r.get("date"),
                "eps_actual": r.get("epsActual"),
                "eps_estimated": r.get("epsEstimated"),
                "revenue_actual": r.get("revenueActual"),
                "revenue_estimated": r.get("revenueEstimated"),
                "last_updated": r.get("lastUpdated"),
                "extracted_at": extracted_at,
            })

        print(f"Earnings calendar: {len(data)} total events, {len(rows)} S&P 500 matches")
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Key Metrics / Valuation Multiples
    # --------------------------------------------------

    def fetch_key_metrics(
        self, tickers: list[str], period: str = "quarter"
    ) -> pd.DataFrame:
        """Fetch key valuation metrics for a list of tickers.

        Args:
            tickers: List of ticker symbols.
            period: Fiscal period — "quarter" or "annual".

        Returns:
            DataFrame with 48 columns including valuation ratios, per-share
            metrics, efficiency ratios, and profitability metrics.
            Empty DataFrame if no data.
        """

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/key-metrics"
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
                rows.append({
                    "ticker": r.get("symbol"),
                    "date": r.get("date"),
                    "period": r.get("period"),
                    "fiscal_year": r.get("fiscalYear"),
                    "reported_currency": r.get("reportedCurrency"),
                    "market_cap": r.get("marketCap"),
                    "enterprise_value": r.get("enterpriseValue"),
                    "ev_to_sales": r.get("evToSales"),
                    "ev_to_operating_cash_flow": r.get("evToOperatingCashFlow"),
                    "ev_to_free_cash_flow": r.get("evToFreeCashFlow"),
                    "ev_to_ebitda": r.get("evToEBITDA"),
                    "net_debt_to_ebitda": r.get("netDebtToEBITDA"),
                    "current_ratio": r.get("currentRatio"),
                    "income_quality": r.get("incomeQuality"),
                    "graham_number": r.get("grahamNumber"),
                    "graham_net_net": r.get("grahamNetNet"),
                    "tax_burden": r.get("taxBurden"),
                    "interest_burden": r.get("interestBurden"),
                    "working_capital": r.get("workingCapital"),
                    "invested_capital": r.get("investedCapital"),
                    "return_on_assets": r.get("returnOnAssets"),
                    "operating_return_on_assets": r.get("operatingReturnOnAssets"),
                    "return_on_tangible_assets": r.get("returnOnTangibleAssets"),
                    "return_on_equity": r.get("returnOnEquity"),
                    "return_on_invested_capital": r.get("returnOnInvestedCapital"),
                    "return_on_capital_employed": r.get("returnOnCapitalEmployed"),
                    "earnings_yield": r.get("earningsYield"),
                    "free_cash_flow_yield": r.get("freeCashFlowYield"),
                    "capex_to_operating_cash_flow": r.get("capexToOperatingCashFlow"),
                    "capex_to_depreciation": r.get("capexToDepreciation"),
                    "capex_to_revenue": r.get("capexToRevenue"),
                    "sales_general_and_administrative_to_revenue": r.get("salesGeneralAndAdministrativeToRevenue"),
                    "research_and_development_to_revenue": r.get("researchAndDevelopementToRevenue"),
                    "stock_based_compensation_to_revenue": r.get("stockBasedCompensationToRevenue"),
                    "intangibles_to_total_assets": r.get("intangiblesToTotalAssets"),
                    "average_receivables": r.get("averageReceivables"),
                    "average_payables": r.get("averagePayables"),
                    "average_inventory": r.get("averageInventory"),
                    "days_of_sales_outstanding": r.get("daysOfSalesOutstanding"),
                    "days_of_payables_outstanding": r.get("daysOfPayablesOutstanding"),
                    "days_of_inventory_outstanding": r.get("daysOfInventoryOutstanding"),
                    "operating_cycle": r.get("operatingCycle"),
                    "cash_conversion_cycle": r.get("cashConversionCycle"),
                    "free_cash_flow_to_equity": r.get("freeCashFlowToEquity"),
                    "free_cash_flow_to_firm": r.get("freeCashFlowToFirm"),
                    "tangible_asset_value": r.get("tangibleAssetValue"),
                    "net_current_asset_value": r.get("netCurrentAssetValue"),
                    "extracted_at": extracted_at,
                })
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="key metrics")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Price Target Consensus
    # --------------------------------------------------

    ### NEED A BACKFILL PIPELINE AS WELL FOR THE PAST 5 YEARS!!!
    def fetch_price_target_consensus(
        self, tickers: list[str], run_date: str
    ) -> pd.DataFrame:
        """Fetch analyst price target consensus for a list of tickers.

        Args:
            tickers: List of ticker symbols.
            run_date: Date string for snapshot dating.

        Returns:
            DataFrame with columns: ticker, target_high, target_low,
            target_consensus, target_median, date, extracted_at.
        """

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/price-target-consensus"
                f"?symbol={ticker}"
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
                rows.append({
                    "ticker": ticker,
                    "target_high": r.get("targetHigh"),
                    "target_low": r.get("targetLow"),
                    "target_consensus": r.get("targetConsensus"),
                    "target_median": r.get("targetMedian"),
                    "date": run_date,
                    "extracted_at": extracted_at,
                })
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="price targets")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Analyst Grades Consensus
    # --------------------------------------------------

    ### NEED A BACKFILL PIPELINE AS WELL FOR THE PAST 5 YEARS!!!
    def fetch_upgrades_downgrades_consensus(
        self, tickers: list[str], run_date: str
    ) -> pd.DataFrame:
        """Fetch analyst grades consensus for a list of tickers.

        Args:
            tickers: List of ticker symbols.
            run_date: Date string for snapshot dating.

        Returns:
            DataFrame with columns: ticker, strong_buy, buy, hold, sell,
            strong_sell, consensus, date, extracted_at.
        """

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/grades-consensus"
                f"?symbol={ticker}"
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
                rows.append({
                    "ticker": ticker,
                    "strong_buy": r.get("strongBuy"),
                    "buy": r.get("buy"),
                    "hold": r.get("hold"),
                    "sell": r.get("sell"),
                    "strong_sell": r.get("strongSell"),
                    "consensus": r.get("consensus"),
                    "date": run_date,
                    "extracted_at": extracted_at,
                })
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="ratings consensus")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Dividends
    # --------------------------------------------------

    def fetch_dividends(self, tickers: list[str]) -> pd.DataFrame:
        """Fetch historical dividend data for a list of tickers.

        Returns:
            DataFrame with columns: ticker, date, adj_dividend, dividend,
            record_date, payment_date, declaration_date, extracted_at.
        """
        def _null_if_empty(v):
            return None if v in ("", None) else v
    
        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/dividends"
                f"?symbol={ticker}"
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
                rows.append({
                    "ticker": ticker,
                    "date": r.get("date"),
                    "record_date": _null_if_empty(r.get("recordDate")),
                    "payment_date": _null_if_empty(r.get("paymentDate")),
                    "declaration_date": _null_if_empty(r.get("declarationDate")),
                    "adj_dividend": r.get("adjDividend"),
                    "dividend": r.get("dividend"),
                    "yield": r.get("yield"),
                    "extracted_at": extracted_at,
                })
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="dividends")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Stock Splits
    # --------------------------------------------------

    def fetch_splits(self, tickers: list[str]) -> pd.DataFrame:
        """Fetch historical stock split data for a list of tickers.

        Returns:
            DataFrame with columns: ticker, date, numerator, denominator,
            extracted_at.
        """

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/stable/splits"
                f"?symbol={ticker}"
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
                rows.append({
                    "ticker": ticker,
                    "date": r.get("date"),
                    "numerator": r.get("numerator"),
                    "denominator": r.get("denominator"),
                    "split_type": r.get("splitType"),
                    "extracted_at": extracted_at,
                })
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="splits")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Insider Trades Latest (paginated global feed)
    # --------------------------------------------------

    def fetch_insider_trades_latest(
        self, tickers: list[str], run_date: str, max_pages: int = 20
    ) -> pd.DataFrame:
        """Fetch insider trades from the latest paginated global feed.

        Endpoint: /stable/insider-trading/latest
        Filters results to provided S&P 500 ticker set via "symbol" field.

        Args:
            tickers: S&P 500 ticker list for post-fetch filtering.
            run_date: Date string (YYYY-MM-DD) — stop paginating when we
                reach filingDate older than run_date.
            max_pages: Max pages to paginate (default 20).

        Returns:
            DataFrame with 16 columns: ticker, filing_date, transaction_date,
            reporting_cik, company_cik, transaction_type, securities_owned,
            reporting_name, type_of_owner, acquisition_or_disposition,
            direct_or_indirect, form_type, securities_transacted, price,
            security_name, url, extracted_at.
        """
        ticker_set = set(tickers)
        all_rows = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Fetching insider trades (latest feed) for {run_date}...")

        for page in range(max_pages):
            url = (
                f"{BASE_URL}/stable/insider-trading/latest"
                f"?page={page}"
                f"&limit=100"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  Page {page}: HTTP {response.status_code}, stopping.")
                break

            data = response.json()
            if not data:
                print(f"  Page {page}: empty response, stopping.")
                break

            page_matches = 0
            found_older = False

            for r in data:
                filing_date = (r.get("filingDate") or "")[:10]
                if filing_date and filing_date < run_date:
                    found_older = True
                    continue

                symbol = r.get("symbol", "")
                if symbol not in ticker_set:
                    continue

                all_rows.append({
                    "ticker": symbol,
                    "filing_date": r.get("filingDate"),
                    "transaction_date": r.get("transactionDate"),
                    "reporting_cik": r.get("reportingCik"),
                    "company_cik": r.get("companyCik"),
                    "transaction_type": r.get("transactionType"),
                    "securities_owned": r.get("securitiesOwned"),
                    "reporting_name": r.get("reportingName"),
                    "type_of_owner": r.get("typeOfOwner"),
                    "acquisition_or_disposition": r.get("acquisitionOrDisposition"),
                    "direct_or_indirect": r.get("directOrIndirect"),
                    "form_type": r.get("formType"),
                    "securities_transacted": r.get("securitiesTransacted"),
                    "price": r.get("price"),
                    "security_name": r.get("securityName"),
                    "url": r.get("url"),
                    "extracted_at": extracted_at,
                })
                page_matches += 1

            print(f"  Page {page}: {len(data)} trades, {page_matches} matched S&P 500 tickers")

            if found_older:
                print(f"  Reached trades older than {run_date}, stopping.")
                break

        print(f"\nTotal: {len(all_rows)} insider trades (latest) for {run_date}\n")
        return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Insider Trades Search (paginated global feed)
    # --------------------------------------------------

    def fetch_insider_trades_search(
        self, tickers: list[str], run_date: str, max_pages: int = 20
    ) -> pd.DataFrame:
        """Fetch insider trades from the searchable paginated global feed.

        Endpoint: /stable/insider-trading/search
        Same JSON schema as fetch_insider_trades_latest.

        Args:
            tickers: S&P 500 ticker list for post-fetch filtering.
            run_date: Date string (YYYY-MM-DD) — stop paginating when we
                reach filingDate older than run_date.
            max_pages: Max pages to paginate (default 20).

        Returns:
            Same schema as fetch_insider_trades_latest.
        """
        ticker_set = set(tickers)
        all_rows = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Fetching insider trades (search feed) for {run_date}...")

        for page in range(max_pages):
            url = (
                f"{BASE_URL}/stable/insider-trading/search"
                f"?page={page}"
                f"&limit=100"
                f"&apikey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  Page {page}: HTTP {response.status_code}, stopping.")
                break

            data = response.json()
            if not data:
                print(f"  Page {page}: empty response, stopping.")
                break

            page_matches = 0
            found_older = False

            for r in data:
                filing_date = (r.get("filingDate") or "")[:10]
                if filing_date and filing_date < run_date:
                    found_older = True
                    continue

                symbol = r.get("symbol", "")
                if symbol not in ticker_set:
                    continue

                all_rows.append({
                    "ticker": symbol,
                    "filing_date": r.get("filingDate"),
                    "transaction_date": r.get("transactionDate"),
                    "reporting_cik": r.get("reportingCik"),
                    "company_cik": r.get("companyCik"),
                    "transaction_type": r.get("transactionType"),
                    "securities_owned": r.get("securitiesOwned"),
                    "reporting_name": r.get("reportingName"),
                    "type_of_owner": r.get("typeOfOwner"),
                    "acquisition_or_disposition": r.get("acquisitionOrDisposition"),
                    "direct_or_indirect": r.get("directOrIndirect"),
                    "form_type": r.get("formType"),
                    "securities_transacted": r.get("securitiesTransacted"),
                    "price": r.get("price"),
                    "security_name": r.get("securityName"),
                    "url": r.get("url"),
                    "extracted_at": extracted_at,
                })
                page_matches += 1

            print(f"  Page {page}: {len(data)} trades, {page_matches} matched S&P 500 tickers")

            if found_older:
                print(f"  Reached trades older than {run_date}, stopping.")
                break

        print(f"\nTotal: {len(all_rows)} insider trades (search) for {run_date}\n")
        return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
