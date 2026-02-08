import os
from snowflake.snowpark import Session

def get_snowflake_session() -> Session:
    return Session.builder.configs({
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": os.environ["STUDENT_SCHEMA"],
    }).create()


def get_sp500_tickers(session: Session, table_name: str, run_date: str) -> list[str]:
    """Query the lookup table for S&P 500 tickers on a given date."""
    query = f"SELECT DISTINCT ticker FROM {table_name} WHERE date = '{run_date}'"
    df = session.sql(query).to_pandas()
    return df["TICKER"].dropna().unique().tolist()


def overwrite_partition(
    session: Session,
    df,
    table_name: str,
    partition_col: str,
    partition_value: str,
    create_table_sql: str,
):
    session.sql(create_table_sql).collect()
    session.sql(
        f"DELETE FROM {table_name} WHERE {partition_col} = '{partition_value}'"
    ).collect()

    session.create_dataframe(df)\
        .write.mode("append")\
        .save_as_table(table_name)


def overwrite_date_range(
    session: Session,
    df,
    table_name: str,
    start_date: str,
    end_date: str,
    create_table_sql: str,
):
    """Like overwrite_partition but deletes a date range (for backfills)."""
    session.sql(create_table_sql).collect()
    session.sql(
        f"DELETE FROM {table_name} WHERE date BETWEEN '{start_date}' AND '{end_date}'"
    ).collect()

    session.create_dataframe(df)\
        .write.mode("append")\
        .save_as_table(table_name)


def overwrite_partition_with_variants(
    session: Session,
    df,
    table_name: str,
    partition_col: str,
    partition_value: str,
    create_table_sql: str,
    variant_columns: list[str],
):
    """Like overwrite_partition but applies parse_json() to VARIANT columns."""
    from snowflake.snowpark.functions import parse_json, col

    session.sql(create_table_sql).collect()
    session.sql(
        f"DELETE FROM {table_name} WHERE {partition_col} = '{partition_value}'"
    ).collect()

    df.columns = [c.upper() for c in df.columns]
    snowpark_df = session.create_dataframe(df)

    variant_upper = {v.upper() for v in variant_columns}
    select_cols = [
        parse_json(col(c)).alias(c) if c in variant_upper else col(c)
        for c in snowpark_df.columns
    ]

    snowpark_df.select(*select_cols)\
        .write.mode("append")\
        .save_as_table(table_name)


def overwrite_date_range_with_variants(
    session: Session,
    df,
    table_name: str,
    start_date: str,
    end_date: str,
    create_table_sql: str,
    variant_columns: list[str],
):
    """Like overwrite_date_range but applies parse_json() to VARIANT columns."""
    from snowflake.snowpark.functions import parse_json, col

    session.sql(create_table_sql).collect()
    session.sql(
        f"DELETE FROM {table_name} WHERE date BETWEEN '{start_date}' AND '{end_date}'"
    ).collect()

    df.columns = [c.upper() for c in df.columns]
    snowpark_df = session.create_dataframe(df)

    variant_upper = {v.upper() for v in variant_columns}
    select_cols = [
        parse_json(col(c)).alias(c) if c in variant_upper else col(c)
        for c in snowpark_df.columns
    ]

    snowpark_df.select(*select_cols)\
        .write.mode("append")\
        .save_as_table(table_name)
