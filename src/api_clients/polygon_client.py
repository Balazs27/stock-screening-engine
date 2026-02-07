# --------------------
# Polygon API Client
# --------------------
# Handles: auth, rate limiting, retries, concurrent fetching.
# Returns: pandas DataFrames. Never touches Snowflake.

import os
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import pandas as pd
import requests

BASE_URL = "https://api.polygon.io"
MAX_WORKERS = 8
MIN_REQUEST_INTERVAL = 0.8  # ~75 req/min (conservative for Basic tier = 100/min)
MAX_RETRIES = 3


class PolygonClient:

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ["POLYGON_API_KEY"]
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
        print(f"Rate limit: ~75 requests/min ({MIN_REQUEST_INTERVAL}s between requests)")
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
    # Endpoint: Reference Tickers (paginated, all tickers)
    # --------------------------------------------------

    def fetch_reference_tickers(self) -> list[dict]:
        """Fetch all tickers from Polygon reference API with pagination."""
        url = f"{BASE_URL}/v3/reference/tickers?limit=1000&apiKey={self.api_key}"
        all_tickers = []
        page = 1

        while url:
            print(f"Fetching reference tickers page {page}...")
            response = self._get(url)
            if response.status_code != 200:
                break
            data = response.json()
            if data.get("status") != "OK":
                break
            all_tickers.extend(data.get("results", []))
            next_url = data.get("next_url")
            url = f"{next_url}&apiKey={self.api_key}" if next_url else None
            page += 1

        print(f"Fetched {len(all_tickers)} total tickers from Polygon reference API")
        return all_tickers

    # --------------------------------------------------
    # Endpoint: Stock Prices (single day)
    # --------------------------------------------------

    def fetch_stock_prices(self, tickers: list[str], run_date: str) -> pd.DataFrame:
        """Fetch single-day prices for a list of tickers."""

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{run_date}/{run_date}"
                f"?adjusted=true&sort=asc&apiKey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            if data.get("status") != "OK" or not data.get("results"):
                return []
            extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return [
                {
                    "ticker": ticker,
                    "open": r.get("o"),
                    "high": r.get("h"),
                    "low": r.get("l"),
                    "close": r.get("c"),
                    "volume": r.get("v"),
                    "vwap": r.get("vw"),
                    "transactions": r.get("n"),
                    "date": run_date,
                    "extracted_at": extracted_at,
                }
                for r in data["results"]
            ]

        results = self._fetch_batch(tickers, _fetch_one, label="price records")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Stock Prices (date range — backfill)
    # --------------------------------------------------

    def fetch_stock_prices_range(
        self, tickers: list[str], start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch historical prices over a date range (1 API call per ticker)."""

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
                f"?adjusted=true&sort=asc&apiKey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            if data.get("status") != "OK" or not data.get("results"):
                return []
            extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = []
            for r in data["results"]:
                ts = r.get("t")
                date_val = (
                    datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                    if ts
                    else None
                )
                rows.append(
                    {
                        "ticker": ticker,
                        "open": r.get("o"),
                        "high": r.get("h"),
                        "low": r.get("l"),
                        "close": r.get("c"),
                        "volume": r.get("v"),
                        "vwap": r.get("vw"),
                        "transactions": r.get("n"),
                        "date": date_val,
                        "extracted_at": extracted_at,
                    }
                )
            return rows

        results = self._fetch_batch(tickers, _fetch_one, label="price records")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: Technical Indicators (SMA / RSI)
    # --------------------------------------------------

    def fetch_indicator(
        self,
        tickers: list[str],
        run_date: str,
        indicator: str,
        window: int,
        timespan: str = "day",
        limit: int = 120,
    ) -> pd.DataFrame:
        """Fetch a technical indicator (sma or rsi) for a list of tickers."""
        date_obj = datetime.strptime(run_date, "%Y-%m-%d").date()
        timestamp_lte = int(
            datetime.combine(date_obj, datetime.max.time()).timestamp() * 1000
        )

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/v1/indicators/{indicator}/{ticker}"
                f"?timestamp.lte={timestamp_lte}"
                f"&timespan={timespan}"
                f"&adjusted=true"
                f"&window={window}"
                f"&series_type=close"
                f"&order=desc"
                f"&limit={limit}"
                f"&apiKey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            if data.get("status") != "OK" or not data.get("results"):
                return []
            rows = []
            for v in data["results"].get("values", []):
                ts = v.get("timestamp")
                rows.append(
                    {
                        "ticker": ticker,
                        "timestamp": (
                            datetime.fromtimestamp(ts / 1000) if ts else None
                        ),
                        f"{indicator}_value": v.get("value"),
                        "window_size": window,
                        "timespan": timespan,
                        "series_type": "close",
                        "date": run_date,
                    }
                )
            return rows

        results = self._fetch_batch(
            tickers, _fetch_one, label=f"{indicator.upper()} points"
        )
        return pd.DataFrame(results) if results else pd.DataFrame()

    # --------------------------------------------------
    # Endpoint: News
    # --------------------------------------------------

    def fetch_news(
        self, tickers: list[str], run_date: str, limit_per_ticker: int = 10
    ) -> pd.DataFrame:
        """Fetch news articles for a list of tickers."""

        def _fetch_one(ticker):
            url = (
                f"{BASE_URL}/v2/reference/news"
                f"?ticker={ticker}"
                f"&published_utc={run_date}"
                f"&limit={limit_per_ticker}"
                f"&sort=published_utc"
                f"&order=desc"
                f"&apiKey={self.api_key}"
            )
            response = self._get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            if data.get("status") != "OK":
                return []
            articles = []
            for a in data.get("results", []):
                published_utc = None
                if a.get("published_utc"):
                    published_utc = datetime.fromisoformat(
                        a["published_utc"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                articles.append(
                    {
                        "ticker": ticker,
                        "article_id": a.get("id"),
                        "publisher_name": a.get("publisher", {}).get("name"),
                        "publisher_homepage_url": a.get("publisher", {}).get(
                            "homepage_url"
                        ),
                        "publisher_logo_url": a.get("publisher", {}).get("logo_url"),
                        "title": a.get("title"),
                        "author": a.get("author"),
                        "published_utc": published_utc,
                        "article_url": a.get("article_url"),
                        "tickers": json.dumps(a.get("tickers")),
                        "image_url": a.get("image_url"),
                        "description": a.get("description"),
                        "keywords": json.dumps(a.get("keywords")),
                        "date": run_date,
                        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            return articles

        results = self._fetch_batch(tickers, _fetch_one, label="articles")
        return pd.DataFrame(results) if results else pd.DataFrame()
