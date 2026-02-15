#!/usr/bin/env python3
"""
MCP Server for Stock Screening Engine.

Exposes S&P 500 scoring marts to Claude Desktop via the Model Context Protocol.
Uses boring-semantic-layer with Snowflake via ibis.

Required environment variables:
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
    SNOWFLAKE_DATABASE, SNOWFLAKE_WAREHOUSE, STUDENT_SCHEMA

Usage:
    # Run directly (for testing)
    python -m src.mcp.mcp_server

    # Add to Claude Desktop config (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "stock-screening": {
          "command": "uv",
          "args": ["run", "python", "-m", "src.mcp.mcp_server"],
          "env": {
            "SNOWFLAKE_ACCOUNT": "aab46027.us-west-2",
            "SNOWFLAKE_USER": "your_user",
            "SNOWFLAKE_PASSWORD": "your_password",
            "SNOWFLAKE_DATABASE": "DATAEXPERT_STUDENT",
            "SNOWFLAKE_WAREHOUSE": "COMPUTE_WH",
            "STUDENT_SCHEMA": "your_schema"
          }
        }
      }
    }
"""

import os
import sys
from pathlib import Path

import ibis

from boring_semantic_layer import from_yaml, to_semantic_table
from boring_semantic_layer.agents.backends.mcp import create_mcp_server


# Whitelisted mart tables — ONLY these are exposed. No discovery.
ALLOWED_TABLES = [
    "mart_sp500_composite_scores",
    "mart_sp500_industry_scores",
    "mart_sp500_fundamental_scores",
    "mart_sp500_technical_scores",
    "mart_sp500_price_performance",
]

REQUIRED_ENV_VARS = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_WAREHOUSE",
    "STUDENT_SCHEMA",
]


def get_snowflake_connection() -> ibis.BaseBackend:
    """Connect to the Snowflake marts schema (read-only) via ibis."""
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # dbt creates schemas as {target_schema}_{custom_schema}
    # e.g., balazsillovai30823_marts
    student_schema = os.environ["STUDENT_SCHEMA"]
    marts_schema = f"{student_schema}_marts".upper()

    conn = ibis.snowflake.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        schema=marts_schema,
    )

    return conn


def load_tables(conn: ibis.BaseBackend) -> dict:
    """Load only the whitelisted mart tables. No schema discovery."""
    tables = {}
    for table_name in ALLOWED_TABLES:
        try:
            tables[table_name] = conn.table(table_name.upper())
            # Normalize column names to lowercase
            table = table.rename({col: col.lower() for col in table.columns})
            tables[table_name] = table
        except Exception as e:
            print(f"Warning: Could not load table {table_name}: {e}", file=sys.stderr)
    return tables


def get_semantic_layer_path() -> Path:
    """Get the path to the semantic layer YAML."""
    return Path(__file__).parent / "semantic_layer.yaml"


def main():
    """Run the MCP server."""
    conn = get_snowflake_connection()

    tables = load_tables(conn)
    print(f"Loaded {len(tables)}/{len(ALLOWED_TABLES)} whitelisted tables from Snowflake")

    if not tables:
        print("ERROR: No tables could be loaded. Check Snowflake credentials and schema.", file=sys.stderr)
        sys.exit(1)

    # Load semantic models from YAML
    yaml_path = get_semantic_layer_path()
    models = {}

    if yaml_path.exists():
        try:
            models = from_yaml(str(yaml_path), tables=tables)
            print(f"Loaded {len(models)} semantic models from YAML")
        except Exception as e:
            print(f"Warning: Could not load YAML models: {e}", file=sys.stderr)

    # Fallback: wrap raw tables as semantic tables
    if not models:
        print("Using raw tables as semantic models (no YAML)")
        for name, table in tables.items():
            models[name] = to_semantic_table(table, name=name)

    server = create_mcp_server(
        models=models,
        name="Stock Screening Engine",
    )

    print("Starting Stock Screening Engine MCP Server...")
    print("Available models:", list(models.keys()))

    server.run()


if __name__ == "__main__":
    main()
