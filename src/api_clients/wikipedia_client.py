# --------------------
# Fetch S&P 500 constituents from Wikipedia
# --------------------

import time
import pandas as pd
import requests
from datetime import datetime
from io import StringIO

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
MAX_RETRIES = 3
INITIAL_BACKOFF = 5  # seconds


def fetch_sp500_constituents(run_date: str) -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(WIKI_URL, headers=headers, timeout=10)
        if response.status_code == 403 and attempt < MAX_RETRIES:
            wait = INITIAL_BACKOFF * attempt
            print(f"Rate limited by Wikipedia (403). Retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        break

    df = pd.read_html(StringIO(response.text))[0]

    column_mapping = {
        "Symbol": "ticker",
        "Security": "security_name",
        "GICS Sector": "gics_sector",
        "GICS Sub-Industry": "gics_sub_industry",
        "Headquarters Location": "headquarters_location",
        "Date added": "date_added",
        "CIK": "cik",
        "Founded": "founded_year",
    }

    df = df.rename(columns=column_mapping)
    df["date"] = run_date
    df["extracted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return df
