"""Read-only Snowflake data access layer for the agent pipeline.

All functions query mart or staging tables and return pandas DataFrames
with lowercase column names. No writes, no DDL, no raw schema access.

Callers create a session via get_session() and pass it to reader functions.
The caller is responsible for closing the session.
"""

import logging
import os
import re
from typing import Optional

import pandas as pd
from snowflake.snowpark import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def get_session() -> Session:
    """Create a Snowflake session using existing loader configuration.

    Returns:
        Active Snowpark Session. Caller is responsible for closing.
    """
    from src.loaders.snowflake_loader import get_snowflake_session
    return get_snowflake_session()


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

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


def _get_dim_schema() -> str:
    """Return fully-qualified dimension schema: DATABASE.SCHEMA_DIM"""
    db = os.environ["SNOWFLAKE_DATABASE"]
    schema = os.environ["STUDENT_SCHEMA"]
    return f"{db}.{schema}_DIM"


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def _lowercase_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase all DataFrame column names for consistent access."""
    df.columns = [c.lower() for c in df.columns]
    return df


def _sanitize_tickers(tickers: list[str]) -> list[str]:
    """Sanitize ticker strings for safe SQL IN clause construction.

    Allows: A-Z, a-z, 0-9, dot (.), hyphen (-).
    Strips everything else. Drops empty results.
    """
    sanitized = []
    for t in tickers:
        clean = re.sub(r"[^A-Za-z0-9.\-]", "", t)
        if clean:
            sanitized.append(clean)
    return sanitized


def _ticker_filter_clause(tickers: Optional[list[str]], col: str = "TICKER") -> str:
    """Return a SQL AND fragment for ticker filtering, or empty string."""
    if not tickers:
        return ""
    safe = _sanitize_tickers(tickers)
    if not safe:
        return ""
    quoted = ", ".join(f"'{t}'" for t in safe)
    return f"AND {col} IN ({quoted})"


def _execute(session: Session, sql: str, table_name: str) -> pd.DataFrame:
    """Execute SQL, lowercase columns, log result count, return DataFrame."""
    logger.debug("SQL: %s", sql)
    df = session.sql(sql).to_pandas()
    df = _lowercase_columns(df)
    if df.empty:
        logger.warning("No data found in %s", table_name)
    else:
        logger.info("Read %d rows from %s", len(df), table_name)
    return df


# ---------------------------------------------------------------------------
# Reader functions
# ---------------------------------------------------------------------------

def read_technical_scores(
    session: Session,
    date: str,
    tickers: Optional[list[str]] = None,
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
    marts = _get_marts_schema()
    table = f"{marts}.MART_SP500_TECHNICAL_SCORES"
    logger.info(
        "Reading %s for date=%s, tickers=%s",
        table, date, len(tickers) if tickers else "all",
    )
    ticker_clause = _ticker_filter_clause(tickers)
    sql = f"""
        SELECT TICKER, DATE, TREND_SCORE, MOMENTUM_SCORE, MACD_SCORE,
               PRICE_ACTION_SCORE, TECHNICAL_SCORE
        FROM {table}
        WHERE DATE = '{date}'
        {ticker_clause}
    """
    return _execute(session, sql, table)


def read_fundamental_scores(
    session: Session,
    tickers: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Read fundamental scores (latest fiscal year per ticker).

    No date filter — fundamental scores are annual. Returns the most
    recent fiscal year for each ticker via QUALIFY ROW_NUMBER().

    Args:
        session: Active Snowpark session.
        tickers: Optional list of tickers to filter. None = all tickers.

    Returns:
        DataFrame with columns: ticker, date, fiscal_year, profitability_score,
        growth_score, financial_health_score, cash_quality_score,
        fundamentals_score, gross_margin, operating_margin, net_margin,
        return_on_equity, current_ratio, debt_to_equity, fcf_margin,
        revenue_growth_yoy, eps_growth_yoy, fcf_growth_yoy.
    """
    marts = _get_marts_schema()
    table = f"{marts}.MART_SP500_FUNDAMENTAL_SCORES"
    logger.info("Reading %s, tickers=%s", table, len(tickers) if tickers else "all")
    ticker_clause = _ticker_filter_clause(tickers)
    sql = f"""
        SELECT TICKER, DATE, FISCAL_YEAR,
               PROFITABILITY_SCORE, GROWTH_SCORE, FINANCIAL_HEALTH_SCORE,
               CASH_QUALITY_SCORE, FUNDAMENTALS_SCORE,
               GROSS_MARGIN, OPERATING_MARGIN, NET_MARGIN, RETURN_ON_EQUITY,
               CURRENT_RATIO, DEBT_TO_EQUITY, FCF_MARGIN,
               REVENUE_GROWTH_YOY, EPS_GROWTH_YOY, FCF_GROWTH_YOY
        FROM {table}
        WHERE 1=1
        {ticker_clause}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY TICKER ORDER BY FISCAL_YEAR DESC) = 1
    """
    return _execute(session, sql, table)


def read_composite_scores(
    session: Session,
    date: str,
    tickers: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Read composite scores for a given date.

    Args:
        session: Active Snowpark session.
        date: Date string (YYYY-MM-DD). Filters on technical_date.
        tickers: Optional list of tickers to filter. None = all tickers.

    Returns:
        DataFrame with columns: ticker, technical_date, technical_score,
        fiscal_year, fiscal_year_start_date, fiscal_year_end_date,
        fundamentals_score, trend_score, momentum_score, macd_score,
        price_action_score, profitability_score, growth_score,
        financial_health_score, cash_quality_score,
        composite_score_equal, composite_score_technical_bias,
        composite_score_fundamental_bias.
    """
    marts = _get_marts_schema()
    table = f"{marts}.MART_SP500_COMPOSITE_SCORES"
    logger.info(
        "Reading %s for date=%s, tickers=%s",
        table, date, len(tickers) if tickers else "all",
    )
    ticker_clause = _ticker_filter_clause(tickers)
    sql = f"""
        SELECT TICKER, TECHNICAL_DATE, TECHNICAL_SCORE,
               FISCAL_YEAR, FISCAL_YEAR_START_DATE, FISCAL_YEAR_END_DATE,
               FUNDAMENTALS_SCORE,
               TREND_SCORE, MOMENTUM_SCORE, MACD_SCORE, PRICE_ACTION_SCORE,
               PROFITABILITY_SCORE, GROWTH_SCORE, FINANCIAL_HEALTH_SCORE,
               CASH_QUALITY_SCORE,
               COMPOSITE_SCORE_EQUAL, COMPOSITE_SCORE_TECHNICAL_BIAS,
               COMPOSITE_SCORE_FUNDAMENTAL_BIAS
        FROM {table}
        WHERE TECHNICAL_DATE = '{date}'
        {ticker_clause}
    """
    return _execute(session, sql, table)


def read_industry_scores(
    session: Session,
    date: str,
    sector: Optional[str] = None,
) -> pd.DataFrame:
    """Read industry-enriched composite scores for a given date.

    Args:
        session: Active Snowpark session.
        date: Date string (YYYY-MM-DD). Filters on technical_date.
        sector: Optional sector name to filter (e.g., "Information Technology").
                None = all sectors.

    Returns:
        DataFrame with columns: ticker, company_name, sector, industry,
        composite_score_equal, composite_score_technical_bias,
        composite_score_fundamental_bias, technical_score, fundamentals_score,
        technical_date, fiscal_year, fiscal_year_start_date, fiscal_year_end_date.
    """
    marts = _get_marts_schema()
    table = f"{marts}.MART_SP500_INDUSTRY_SCORES"
    logger.info("Reading %s for date=%s, sector=%s", table, date, sector or "all")
    sector_clause = f"AND SECTOR = '{sector}'" if sector else ""
    sql = f"""
        SELECT TICKER, COMPANY_NAME, SECTOR, INDUSTRY,
               COMPOSITE_SCORE_EQUAL, COMPOSITE_SCORE_TECHNICAL_BIAS,
               COMPOSITE_SCORE_FUNDAMENTAL_BIAS,
               TECHNICAL_SCORE, FUNDAMENTALS_SCORE,
               TECHNICAL_DATE, FISCAL_YEAR,
               FISCAL_YEAR_START_DATE, FISCAL_YEAR_END_DATE
        FROM {table}
        WHERE TECHNICAL_DATE = '{date}'
        {sector_clause}
    """
    return _execute(session, sql, table)


def read_price_performance(
    session: Session,
    date: str,
    tickers: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Read price performance metrics for a given date.

    Args:
        session: Active Snowpark session.
        date: Date string (YYYY-MM-DD).
        tickers: Optional list of tickers to filter. None = all tickers.

    Returns:
        DataFrame with columns: ticker, date, close, daily_return,
        cumulative_return, rolling_30d_return, rolling_90d_return,
        rolling_1y_return, rolling_30d_volatility, running_max_price,
        drawdown_pct, company_name, sector, industry.
    """
    marts = _get_marts_schema()
    table = f"{marts}.MART_SP500_PRICE_PERFORMANCE"
    logger.info(
        "Reading %s for date=%s, tickers=%s",
        table, date, len(tickers) if tickers else "all",
    )
    ticker_clause = _ticker_filter_clause(tickers)
    sql = f"""
        SELECT TICKER, DATE, CLOSE, DAILY_RETURN, CUMULATIVE_RETURN,
               ROLLING_30D_RETURN, ROLLING_90D_RETURN, ROLLING_1Y_RETURN,
               ROLLING_30D_VOLATILITY, RUNNING_MAX_PRICE, DRAWDOWN_PCT,
               COMPANY_NAME, SECTOR, INDUSTRY
        FROM {table}
        WHERE DATE = '{date}'
        {ticker_clause}
    """
    return _execute(session, sql, table)


def read_recent_news(
    session: Session,
    tickers: list[str],
    lookback_days: int = 7,
) -> pd.DataFrame:
    """Read recent news articles from staging for specified tickers.

    Queries the STG schema (not marts) because news is not yet in a mart.
    VARIANT columns (tickers, keywords) are excluded.

    Args:
        session: Active Snowpark session.
        tickers: List of tickers to fetch news for (required).
        lookback_days: Number of days to look back (default: 7).

    Returns:
        DataFrame with columns: ticker, article_id, title, author,
        published_utc, article_url, description, date.
    """
    stg = _get_stg_schema()
    table = f"{stg}.STG_SP500_NEWS"
    logger.info(
        "Reading %s for %d tickers, lookback=%d days",
        table, len(tickers), lookback_days,
    )
    ticker_clause = _ticker_filter_clause(tickers)
    days = int(lookback_days)  # ensure safe integer
    sql = f"""
        SELECT TICKER, ARTICLE_ID, TITLE, AUTHOR,
               PUBLISHED_UTC, ARTICLE_URL, DESCRIPTION, DATE
        FROM {table}
        WHERE DATE >= DATEADD(day, -{days}, CURRENT_DATE())
        {ticker_clause}
        ORDER BY PUBLISHED_UTC DESC
    """
    return _execute(session, sql, table)


def read_sector_list(session: Session) -> list[str]:
    """Read the distinct list of GICS sectors from the dimension table.

    Args:
        session: Active Snowpark session.

    Returns:
        Sorted list of sector names (e.g., ["Communication Services",
        "Consumer Discretionary", ..., "Utilities"]).
    """
    dim = _get_dim_schema()
    table = f"{dim}.DIM_SP500_COMPANIES_CURRENT"
    logger.info("Reading distinct sectors from %s", table)
    sql = f"SELECT DISTINCT SECTOR FROM {table} WHERE SECTOR IS NOT NULL ORDER BY SECTOR"
    df = session.sql(sql).to_pandas()
    sectors = df["SECTOR"].dropna().tolist()
    logger.info("Found %d sectors", len(sectors))
    return sectors
