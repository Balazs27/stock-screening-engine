# Build Agent Data Access Layer (Snowflake Reader)

## Goal

Create a read-only data access layer that provides clean, typed DataFrame access to all 5 mart tables and the staging news table. This layer is the single interface between the agent pipeline and Snowflake — no agent should ever construct raw SQL or manage Snowflake sessions directly.

## Why this matters

The agent pipeline needs to read scored, enriched data from Snowflake marts to feed into context agents, scorers, rankers, and report builders. A centralized reader module:
- Enforces read-only access (agents never write to Snowflake)
- Encapsulates schema/table naming conventions (uppercase Snowflake identifiers, `STUDENT_SCHEMA` prefix)
- Provides consistent DataFrame column naming (lowercase pandas columns)
- Enables easy mocking in tests (swap the reader, not Snowflake)
- Reuses the existing `get_snowflake_session()` from `src/loaders/snowflake_loader.py`

## Scope

- Create `src/agents/data/__init__.py` (package marker)
- Create `src/agents/data/snowflake_reader.py` with 7 reader functions + 1 session helper
- Each function queries a specific mart/staging table and returns a pandas DataFrame
- All queries use the `{STUDENT_SCHEMA}_MARTS` or `{STUDENT_SCHEMA}_STG` schema (uppercase)
- Column names are returned as lowercase in the resulting DataFrame

## Out of scope

- Writing to Snowflake (existing `src/loaders/snowflake_loader.py` handles all writes)
- Creating new Snowflake tables or views
- Caching query results (Phase 6 feature: `src/agents/core/cache.py`)
- Any data transformation or scoring logic
- Direct access to RAW or INT schemas

## Required context to read first

| File | Why |
|------|-----|
| `project_checklist.md` | Exact acceptance criteria and function signatures |
| `src/loaders/snowflake_loader.py` | `get_snowflake_session()` pattern — reuse for session creation |
| `CLAUDE.md` | "Snowflake identifiers are UPPERCASE", "NEVER expose RAW/STG/INT schemas to MCP or Superset" |
| `.claude/rules/analytics-architecture.md` | Layer boundaries, exposure rules |
| `.claude/rules/security-and-privacy-guardrails.md` | Credential patterns, env var conventions |
| `dbt_project/models/marts/mart_sp500_technical_scores.sql` | Output columns: ticker, date, trend_score, momentum_score, macd_score, price_action_score, technical_score |
| `dbt_project/models/marts/mart_sp500_fundamental_scores.sql` | Output columns: ticker, date, fiscal_year, profitability_score, growth_score, financial_health_score, cash_quality_score, fundamentals_score, + raw metrics |
| `dbt_project/models/marts/mart_sp500_composite_scores.sql` | Output columns: ticker, technical_date, technical_score, fiscal_year, fundamentals_score, component scores, 3 composite variants |
| `dbt_project/models/marts/mart_sp500_industry_scores.sql` | Output columns: ticker, company_name, sector, industry, composite scores, technical_date, fiscal_year |
| `dbt_project/models/marts/mart_sp500_price_performance.sql` | Output columns: ticker, date, close, daily_return, cumulative_return, rolling returns, volatility, drawdown, company_name, sector, industry |
| `dbt_project/models/staging/polygon/stg_sp500_news.sql` | Output columns: ticker, article_id, publisher_name, title, author, published_utc, article_url, tickers, image_url, description, keywords, date |
| `PROJECT_STRUCTURE.md` | Snowflake schema topology — schema naming: `BALAZSILLOVAI30823_MARTS`, `BALAZSILLOVAI30823_STG` |

## Dependencies

### Upstream features
- Feature 01 (pipeline configuration system) — `src/agents/__init__.py` must exist. If not yet implemented, this feature must create it.

### Libraries/packages
- `snowflake-snowpark-python` — already in `requirements.txt`. Provides `Session` class and `.sql().to_pandas()` for queries.
- `pandas` — already in `requirements.txt`. All reader functions return `pd.DataFrame`.
- `os` — standard library, for `os.environ["STUDENT_SCHEMA"]`.

### Environment variables
- `SNOWFLAKE_ACCOUNT` — Snowflake account identifier
- `SNOWFLAKE_USER` — Snowflake username
- `SNOWFLAKE_PASSWORD` — Snowflake password
- `SNOWFLAKE_ROLE` — Snowflake role (ALL_USERS_ROLE)
- `SNOWFLAKE_WAREHOUSE` — Snowflake warehouse (COMPUTE_WH)
- `SNOWFLAKE_DATABASE` — Snowflake database (DATAEXPERT_STUDENT)
- `STUDENT_SCHEMA` — Schema prefix (e.g., BALAZSILLOVAI30823)

All are required for Snowflake connectivity. Already used by existing ETL loaders.

### APIs/data sources
- Snowflake warehouse — read-only access to `{STUDENT_SCHEMA}_MARTS` and `{STUDENT_SCHEMA}_STG` schemas

## Data contracts and schemas

### Snowflake table → pandas DataFrame column mapping

All Snowflake columns are UPPERCASE. Reader functions return DataFrames with **lowercase** column names (done via `df.columns = [c.lower() for c in df.columns]`).

#### `mart_sp500_technical_scores`
| Snowflake Column | pandas Column | Type |
|-----------------|---------------|------|
| TICKER | ticker | str |
| DATE | date | date |
| TREND_SCORE | trend_score | int |
| MOMENTUM_SCORE | momentum_score | int |
| MACD_SCORE | macd_score | int |
| PRICE_ACTION_SCORE | price_action_score | int |
| TECHNICAL_SCORE | technical_score | int |

#### `mart_sp500_fundamental_scores`
| Snowflake Column | pandas Column | Type |
|-----------------|---------------|------|
| TICKER | ticker | str |
| DATE | date | date |
| FISCAL_YEAR | fiscal_year | int |
| PROFITABILITY_SCORE | profitability_score | int |
| GROWTH_SCORE | growth_score | int |
| FINANCIAL_HEALTH_SCORE | financial_health_score | int |
| CASH_QUALITY_SCORE | cash_quality_score | int |
| FUNDAMENTALS_SCORE | fundamentals_score | int |
| GROSS_MARGIN | gross_margin | float |
| OPERATING_MARGIN | operating_margin | float |
| NET_MARGIN | net_margin | float |
| RETURN_ON_EQUITY | return_on_equity | float |
| CURRENT_RATIO | current_ratio | float |
| DEBT_TO_EQUITY | debt_to_equity | float |
| FCF_MARGIN | fcf_margin | float |
| REVENUE_GROWTH_YOY | revenue_growth_yoy | float |
| EPS_GROWTH_YOY | eps_growth_yoy | float |
| FCF_GROWTH_YOY | fcf_growth_yoy | float |

#### `mart_sp500_composite_scores`
| Snowflake Column | pandas Column | Type |
|-----------------|---------------|------|
| TICKER | ticker | str |
| TECHNICAL_DATE | technical_date | date |
| TECHNICAL_SCORE | technical_score | float |
| FISCAL_YEAR | fiscal_year | int/null |
| FUNDAMENTALS_SCORE | fundamentals_score | float/null |
| TREND_SCORE | trend_score | int |
| MOMENTUM_SCORE | momentum_score | int |
| MACD_SCORE | macd_score | int |
| PRICE_ACTION_SCORE | price_action_score | int |
| PROFITABILITY_SCORE | profitability_score | int/null |
| GROWTH_SCORE | growth_score | int/null |
| FINANCIAL_HEALTH_SCORE | financial_health_score | int/null |
| CASH_QUALITY_SCORE | cash_quality_score | int/null |
| COMPOSITE_SCORE_EQUAL | composite_score_equal | float/null |
| COMPOSITE_SCORE_TECHNICAL_BIAS | composite_score_technical_bias | float/null |
| COMPOSITE_SCORE_FUNDAMENTAL_BIAS | composite_score_fundamental_bias | float/null |

#### `mart_sp500_industry_scores`
Same as composite scores plus: COMPANY_NAME, SECTOR, INDUSTRY, FISCAL_YEAR_START_DATE, FISCAL_YEAR_END_DATE

#### `mart_sp500_price_performance`
| Snowflake Column | pandas Column | Type |
|-----------------|---------------|------|
| TICKER | ticker | str |
| DATE | date | date |
| CLOSE | close | float |
| DAILY_RETURN | daily_return | float |
| CUMULATIVE_RETURN | cumulative_return | float |
| ROLLING_30D_RETURN | rolling_30d_return | float |
| ROLLING_90D_RETURN | rolling_90d_return | float |
| ROLLING_1Y_RETURN | rolling_1y_return | float |
| ROLLING_30D_VOLATILITY | rolling_30d_volatility | float |
| RUNNING_MAX_PRICE | running_max_price | float |
| DRAWDOWN_PCT | drawdown_pct | float |
| COMPANY_NAME | company_name | str |
| SECTOR | sector | str |
| INDUSTRY | industry | str |

#### `stg_sp500_news` (from `_STG` schema)
| Snowflake Column | pandas Column | Type |
|-----------------|---------------|------|
| TICKER | ticker | str |
| ARTICLE_ID | article_id | str |
| TITLE | title | str |
| AUTHOR | author | str/null |
| PUBLISHED_UTC | published_utc | timestamp |
| ARTICLE_URL | article_url | str |
| DESCRIPTION | description | str/null |
| DATE | date | date |

Note: `tickers` and `keywords` columns are VARIANT type in Snowflake. For the news reader, we only need the text fields (title, description) for catalyst extraction. Skip VARIANT columns.

## Implementation plan

### Step 1: Create package scaffolding

Create `src/agents/data/__init__.py` as an empty file.

If `src/agents/__init__.py` does not yet exist (Feature 01 not implemented), create it too.

### Step 2: Create `snowflake_reader.py`

Write `src/agents/data/snowflake_reader.py` with the structure below.

**Key implementation details:**

1. **Session reuse**: Import `get_snowflake_session` from `src.loaders.snowflake_loader`. Caller creates the session and passes it to reader functions. The reader NEVER creates or closes sessions.

2. **Schema resolution**: Use `os.environ["STUDENT_SCHEMA"]` to build fully-qualified table names:
   - Marts: `{STUDENT_SCHEMA}_MARTS.{table_name}` (e.g., `BALAZSILLOVAI30823_MARTS.MART_SP500_TECHNICAL_SCORES`)
   - Staging: `{STUDENT_SCHEMA}_STG.{table_name}` (e.g., `BALAZSILLOVAI30823_STG.STG_SP500_NEWS`)

3. **Fully-qualified names**: All queries must use database.schema.table format because the Snowpark session is connected to the base schema, not the marts schema:
   - `{database}.{STUDENT_SCHEMA}_MARTS.MART_SP500_TECHNICAL_SCORES`
   - Use `os.environ["SNOWFLAKE_DATABASE"]` for the database part.

4. **Column lowercasing**: Every function does `df.columns = [c.lower() for c in df.columns]` before returning.

5. **Date filtering**: Functions that accept a `date` parameter filter by `WHERE DATE = '{date}'` or `WHERE TECHNICAL_DATE = '{date}'` as appropriate for the mart.

6. **Ticker filtering**: Functions that accept `tickers: list[str] | None` add `WHERE TICKER IN (...)` when tickers is not None.

7. **SQL parameterization**: Use f-strings for table/schema names (not user input). Ticker values should be sanitized — strip non-alphanumeric characters except dots and hyphens (e.g., `BRK.B`, `BF-B`).

### Step 3: Implement each reader function

See the Functions and interfaces section below for exact signatures.

### Step 4: Add a `get_session()` convenience wrapper

Create a thin wrapper that imports and calls `get_snowflake_session()`:

```python
def get_session() -> Session:
    """Create a Snowflake session using existing loader configuration."""
    from src.loaders.snowflake_loader import get_snowflake_session
    return get_snowflake_session()
```

This avoids agents needing to know about `src.loaders.snowflake_loader`.

### Step 5: Validate locally

```bash
cd /Users/balazsillovai/stock-screening-engine
python -c "
from src.agents.data.snowflake_reader import get_session, read_technical_scores
session = get_session()
df = read_technical_scores(session, '2025-06-13')
print(df.shape, df.columns.tolist())
session.close()
"
```

Replace the date with a date known to have data in the marts.

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `src/agents/data/__init__.py` | CREATE | Empty file (package marker) |
| `src/agents/data/snowflake_reader.py` | CREATE | Read-only Snowflake access layer with 7 reader functions |
| `src/agents/__init__.py` | CREATE (if not exists) | Empty file — may already exist from Feature 01 |

## Functions and interfaces

### `snowflake_reader.py`

```python
import os
import logging
from typing import Optional

import pandas as pd
from snowflake.snowpark import Session

logger = logging.getLogger(__name__)


def get_session() -> Session:
    """Create a Snowflake session using existing loader configuration.

    Returns:
        Active Snowpark Session. Caller is responsible for closing.
    """
    ...


def _get_marts_schema() -> str:
    """Return fully-qualified marts schema: DATABASE.SCHEMA_MARTS"""
    db = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["STUDENT_SCHEMA"]
    return f"{db}.{schema}_MARTS"


def _get_stg_schema() -> str:
    """Return fully-qualified staging schema: DATABASE.SCHEMA_STG"""
    db = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["STUDENT_SCHEMA"]
    return f"{db}.{schema}_STG"


def _lowercase_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase all DataFrame column names for consistent access."""
    df.columns = [c.lower() for c in df.columns]
    return df


def _sanitize_tickers(tickers: list[str]) -> list[str]:
    """Sanitize ticker strings for safe SQL IN clause construction.

    Allows: A-Z, a-z, 0-9, dot (.), hyphen (-).
    Strips everything else.
    """
    ...


def read_technical_scores(
    session: Session,
    date: str,
    tickers: Optional[list[str]] = None
) -> pd.DataFrame:
    """Read technical scores for a given date.

    Args:
        session: Active Snowpark session.
        date: Date string (YYYY-MM-DD).
        tickers: Optional list of tickers to filter. None = all tickers.

    Returns:
        DataFrame with columns: ticker, date, trend_score, momentum_score,
        macd_score, price_action_score, technical_score.
    """
    ...


def read_fundamental_scores(
    session: Session,
    tickers: Optional[list[str]] = None
) -> pd.DataFrame:
    """Read fundamental scores (latest fiscal year per ticker).

    No date filter — fundamental scores are annual. Returns the most
    recent fiscal year for each ticker.

    Args:
        session: Active Snowpark session.
        tickers: Optional list of tickers to filter. None = all tickers.

    Returns:
        DataFrame with columns: ticker, date, fiscal_year, profitability_score,
        growth_score, financial_health_score, cash_quality_score,
        fundamentals_score, + raw margin/ratio metrics.
    """
    ...


def read_composite_scores(
    session: Session,
    date: str,
    tickers: Optional[list[str]] = None
) -> pd.DataFrame:
    """Read composite scores for a given date.

    Args:
        session: Active Snowpark session.
        date: Date string (YYYY-MM-DD). Filters on technical_date.
        tickers: Optional list of tickers to filter. None = all tickers.

    Returns:
        DataFrame with columns: ticker, technical_date, technical_score,
        fiscal_year, fundamentals_score, component scores,
        composite_score_equal, composite_score_technical_bias,
        composite_score_fundamental_bias.
    """
    ...


def read_industry_scores(
    session: Session,
    date: str,
    sector: Optional[str] = None
) -> pd.DataFrame:
    """Read industry-enriched composite scores for a given date.

    Args:
        session: Active Snowpark session.
        date: Date string (YYYY-MM-DD). Filters on technical_date.
        sector: Optional sector name to filter (e.g., "Information Technology").
                None = all sectors.

    Returns:
        DataFrame with columns: ticker, company_name, sector, industry,
        composite scores, technical_date, fiscal_year.
    """
    ...


def read_price_performance(
    session: Session,
    date: str,
    tickers: Optional[list[str]] = None
) -> pd.DataFrame:
    """Read price performance metrics for a given date.

    Args:
        session: Active Snowpark session.
        date: Date string (YYYY-MM-DD).
        tickers: Optional list of tickers to filter. None = all tickers.

    Returns:
        DataFrame with columns: ticker, date, close, daily_return,
        cumulative_return, rolling returns, volatility, drawdown,
        company_name, sector, industry.
    """
    ...


def read_recent_news(
    session: Session,
    tickers: list[str],
    lookback_days: int = 7
) -> pd.DataFrame:
    """Read recent news articles from staging for specified tickers.

    Queries the STG schema (not marts) because news is not yet in marts.

    Args:
        session: Active Snowpark session.
        tickers: List of tickers to fetch news for (required).
        lookback_days: Number of days to look back (default: 7).

    Returns:
        DataFrame with columns: ticker, article_id, title, author,
        published_utc, article_url, description, date.
        VARIANT columns (tickers, keywords) are excluded.
    """
    ...


def read_sector_list(session: Session) -> list[str]:
    """Read the distinct list of GICS sectors from the dimension table.

    Args:
        session: Active Snowpark session.

    Returns:
        Sorted list of sector names (e.g., ["Communication Services",
        "Consumer Discretionary", ..., "Utilities"]).
    """
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `src/loaders/snowflake_loader.py` | `get_session()` imports `get_snowflake_session()` from here. No modifications to the loader. |
| `src/agents/data/` package | Creates a new sub-package under `src/agents/`. All future agent code that needs Snowflake data should import from here. |
| Snowflake schemas | Reads from `_MARTS` and `_STG` schemas only. No writes. No DDL. |
| Existing ETL pipeline | Zero impact — this module reads from tables that are populated by the existing ETL/dbt pipeline. |
| `read_recent_news` accesses STG | This is the only function that reads outside `_MARTS`. Justified because news articles are in staging, not in any mart. If a news mart is added in the future, this function should be updated to read from marts instead. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| No data for the requested date | Return an empty DataFrame with correct column names. Do not raise an exception — the caller (agent) decides how to handle empty data. |
| Session not connected / expired | Let the Snowpark `SnowparkSessionException` propagate. The orchestrator catches it as a critical failure. |
| Missing env var (`STUDENT_SCHEMA`) | `os.environ["STUDENT_SCHEMA"]` raises `KeyError`. Let it propagate — startup validation should catch this. |
| Ticker contains SQL injection characters | `_sanitize_tickers()` strips non-alphanumeric characters (keeping `.` and `-` for tickers like `BRK.B`). Additionally, tickers are quoted in the SQL IN clause: `TICKER IN ('AAPL', 'MSFT')`. |
| Sector name with special characters | Sector names from GICS are safe ASCII strings (e.g., "Information Technology"). Quote in SQL: `SECTOR = '{sector}'`. |
| Very large result set | Unlikely — each mart has ~500 rows per date (one per S&P 500 ticker). No pagination needed. |
| NULL values in score columns | Preserve NULLs as `NaN` in pandas. Downstream agents handle missing scores (e.g., `fundamental_score=None` for stocks without fiscal year data). |
| `read_fundamental_scores` latest fiscal year | Use `QUALIFY ROW_NUMBER() OVER (PARTITION BY TICKER ORDER BY FISCAL_YEAR DESC) = 1` to get the most recent fiscal year per ticker. |

## Observability (logging/metrics)

- `logger = logging.getLogger(__name__)` at module level
- Log at `INFO` level: "Reading {table_name} for date={date}, tickers={len(tickers) or 'all'}" before each query
- Log at `INFO` level: "Read {len(df)} rows from {table_name}" after each query
- Log at `WARNING` level: "No data found in {table_name} for date={date}" when result is empty
- Log at `DEBUG` level: the full SQL query string (useful for debugging, disabled in production)
- No timing metrics in the reader itself — timing is captured by the `BaseAgent.execute()` wrapper in Phase 1

## Acceptance criteria

- [ ] `src/agents/data/__init__.py` exists
- [ ] `src/agents/data/snowflake_reader.py` exists with all 7 reader functions + `get_session()`
- [ ] `from src.agents.data.snowflake_reader import get_session, read_technical_scores` succeeds
- [ ] `read_technical_scores(session, date)` returns a non-empty DataFrame with lowercase column names when called with a valid date
- [ ] `read_fundamental_scores(session)` returns one row per ticker (latest fiscal year)
- [ ] `read_composite_scores(session, date)` returns DataFrame with all 3 composite score variants
- [ ] `read_industry_scores(session, date, sector="Information Technology")` returns only IT sector stocks
- [ ] `read_price_performance(session, date)` returns DataFrame with return and risk metrics
- [ ] `read_recent_news(session, ["AAPL", "MSFT"], lookback_days=7)` returns news articles
- [ ] `read_sector_list(session)` returns a sorted list of 11 GICS sector names
- [ ] Column names in all returned DataFrames are lowercase
- [ ] Empty date ranges return empty DataFrames (not errors)
- [ ] Integration test confirms all 7 reader functions work against a live Snowflake connection

## Follow-ups (optional)

- Phase 6 will add caching (`RunCache`) to avoid redundant Snowflake queries on pipeline re-runs
- If a news mart model is added to dbt, update `read_recent_news()` to query `_MARTS` instead of `_STG`
- Consider adding a `read_dimension_companies(session)` function if agents need the full dimension table directly
