# Rule: Security & Privacy Guardrails

Strict rules for credential handling, access control, and safe development practices.

---

## Credential Management

### Environment Variables (MANDATORY)

All credentials are accessed via environment variables. Never hardcode secrets.

| Variable | Used By | Purpose |
|----------|---------|---------|
| `SNOWFLAKE_USER` | profiles.yml, snowflake_loader.py, mcp_server.py | Snowflake authentication |
| `SNOWFLAKE_PASSWORD` | profiles.yml, snowflake_loader.py, mcp_server.py | Snowflake authentication |
| `SNOWFLAKE_ACCOUNT` | profiles.yml, snowflake_loader.py, mcp_server.py | Snowflake account identifier |
| `SNOWFLAKE_DATABASE` | profiles.yml, snowflake_loader.py, mcp_server.py | Target database |
| `SNOWFLAKE_WAREHOUSE` | profiles.yml, snowflake_loader.py, mcp_server.py | Compute warehouse |
| `STUDENT_SCHEMA` | snowflake_loader.py, mcp_server.py | Schema prefix for all tables |
| `POLYGON_API_KEY` | polygon_client.py | Polygon.io API authentication |
| `FMP_API_KEY` | fmp_client.py | Financial Modeling Prep API authentication |

### dbt Profiles
```yaml
user: "{{ env_var('SNOWFLAKE_USER') }}"
password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
```
Jinja env_var() is the ONLY acceptable way to reference credentials in profiles.yml.

### Python Code
```python
os.environ["SNOWFLAKE_USER"]  # or os.getenv() with explicit KeyError on missing
```

## Forbidden Files — NEVER Read, Index, or Commit

| Pattern | Reason |
|---------|--------|
| `.env` / `.env.*` / `dbt.env` | Contains API keys and Snowflake credentials |
| `profiles.yml` with hardcoded passwords | Should only contain `env_var()` references |
| `target/` | dbt compiled SQL may contain interpolated secrets |
| `logs/` | dbt and Airflow logs may contain connection strings |
| `dbt_packages/` | Third-party code, not project source |
| `venv/` / `.venv/` | Python virtual environments |
| `node_modules/` | Node dependencies |
| `*.db` (SQLite files) | Superset metadata, Airflow state |
| `__pycache__/` | Compiled Python bytecode |

## MCP Access Isolation

The MCP server enforces strict read-only access to marts only:

```python
# mcp_server.py — hardcoded whitelist
ALLOWED_TABLES = [
    "mart_sp500_composite_scores",
    "mart_sp500_industry_scores",
    "mart_sp500_fundamental_scores",
    "mart_sp500_technical_scores",
    "mart_sp500_price_performance",
]
```

**Rules:**
- MCP connects to `{STUDENT_SCHEMA}_marts` schema ONLY
- RAW, STG, INT, DIM schemas are NEVER exposed via MCP
- Adding a new table to MCP requires explicit addition to the whitelist
- MCP operations are READ-ONLY (no INSERT, UPDATE, DELETE, DDL)

## Snowflake Role-Based Access

| Setting | Value | Purpose |
|---------|-------|---------|
| Role | `ALL_USERS_ROLE` | Shared student environment role |
| Database | `DATAEXPERT_STUDENT` | Shared database |
| Warehouse | `COMPUTE_WH` | Shared compute resource |

**In a production environment, enforce:**
- Separate roles for ETL write (LOADER_ROLE) and dbt transform (TRANSFORMER_ROLE)
- Read-only role for MCP/Superset (READER_ROLE)
- Dedicated warehouse per workload tier

## PII Assessment

**Current state: NO PII exists in the data.**

All data is public market information:
- Ticker symbols (public)
- Stock prices (public market data)
- Financial statements (SEC filings, public)
- Company metadata (Wikipedia, public)
- News articles (public)

If PII is introduced in the future (e.g., user portfolios, personal watchlists):
1. Apply column-level masking in Snowflake
2. Never expose PII through MCP or Superset
3. Add row-level security for multi-tenant scenarios
4. Document PII columns in YAML schema definitions

## Safe Logging Practices

- Python ETL logs use `logging` module — log row counts and status, NEVER log credentials or full SQL with interpolated secrets
- dbt logging is handled by dbt core — `target/` directory is gitignored
- Airflow task logs may contain connection metadata — XCom should never store credentials
- MCP server logs query requests — log the query text but NEVER log connection strings

## Docker Security

| Concern | Current State | Production Recommendation |
|---------|--------------|--------------------------|
| Superset secret key | Default placeholder in docker-compose | Override via environment variable |
| Superset admin password | Hardcoded "admin" in docker-compose command | Override or use external auth |
| Base image | `astrocrpublic.azurecr.io/runtime:3.1-9` | Pin to specific digest in production |
| .env mounting | Not mounted (secrets via env vars) | Continue this pattern |
