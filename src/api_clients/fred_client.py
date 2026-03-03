# --------------------
# FRED API Client
# --------------------
# Handles: auth, retries, response parsing.
# Returns: pandas DataFrames. Never touches Snowflake.

import os
import time
from datetime import datetime
from threading import Lock

import pandas as pd
import requests

BASE_URL = "https://api.stlouisfed.org/fred"
MAX_RETRIES = 3
MIN_REQUEST_INTERVAL = 0.5  # Conservative; FRED allows 120 req/min

# Standard macro rate series used in Phase 0.5
MACRO_SERIES = ["DFF", "DGS10", "DGS2", "BAMLH0A0HYM2"]


class FREDClient:

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ["FRED_API_KEY"]
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
    # Endpoint: Series Observations
    # --------------------------------------------------

    def fetch_series(
        self,
        series_ids: list[str],
        observation_start: str,
        observation_end: str,
    ) -> pd.DataFrame:
        """Fetch FRED time series observations for multiple series.

        Args:
            series_ids: List of FRED series IDs (e.g., ["DFF", "DGS10"]).
            observation_start: Start date (YYYY-MM-DD).
            observation_end: End date (YYYY-MM-DD).

        Returns:
            DataFrame with columns: series_id, date, value, extracted_at.
            FRED's "." (missing data for weekends/holidays) is parsed to None.
        """
        all_rows = []
        extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for series_id in series_ids:
            print(f"Fetching FRED series {series_id}: {observation_start} to {observation_end}...")
            url = (
                f"{BASE_URL}/series/observations"
                f"?series_id={series_id}"
                f"&api_key={self.api_key}"
                f"&file_type=json"
                f"&observation_start={observation_start}"
                f"&observation_end={observation_end}"
            )
            response = self._get(url)
            if response.status_code != 200:
                print(f"  {series_id}: HTTP {response.status_code}, skipping.")
                continue

            data = response.json()
            observations = data.get("observations", [])

            count = 0
            for obs in observations:
                raw_value = obs.get("value", ".")
                # FRED returns "." for missing data (weekends, holidays, not yet released)
                value = None
                if raw_value != ".":
                    try:
                        value = float(raw_value)
                    except (ValueError, TypeError):
                        value = None

                all_rows.append({
                    "series_id": series_id,
                    "date": obs.get("date"),
                    "value": value,
                    "extracted_at": extracted_at,
                })
                count += 1

            print(f"  {series_id}: {count} observations")

        print(f"\nTotal: {len(all_rows)} observations across {len(series_ids)} series")
        return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()

    def fetch_macro_rates(
        self, observation_start: str, observation_end: str
    ) -> pd.DataFrame:
        """Convenience method: fetch all standard macro rate series.

        Series: DFF (Fed Funds), DGS10 (10Y Treasury), DGS2 (2Y Treasury),
        BAMLH0A0HYM2 (High Yield OAS).
        """
        return self.fetch_series(MACRO_SERIES, observation_start, observation_end)
