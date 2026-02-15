FROM apache/superset:latest

# Switch to root to install Snowflake driver
USER root

RUN pip install --target=/app/.venv/lib/python3.10/site-packages \
    snowflake-connector-python \
    snowflake-sqlalchemy \
    fastmcp

# Switch back to superset user for security
USER superset
