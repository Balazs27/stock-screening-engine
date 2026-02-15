# CLAUDE.md

# Stock Screening & Scoring Engine

## Project Purpose

This project is a production-style analytics platform that:

• Ingests financial data for S&P 500 companies  
• Transforms and models the data using dbt  
• Computes technical, fundamental, and composite stock scores  
• Ranks stocks daily  
• Enables AI-driven analysis via MCP + semantic layer  
• Enables BI dashboards via Superset  

In plain terms:

This system continuously evaluates the S&P 500 and surfaces the strongest stocks based on quantified signals across momentum, profitability, risk, and price behavior.

This repository demonstrates real-world:

• Data Engineering  
• Analytics Engineering  
• Incremental modeling  
• Orchestration  
• AI integration  
• BI enablement  

---

# High-Level Architecture

External Sources  
(Wikipedia, Polygon, FMP)  
        ↓  
Python ETL Jobs (Airflow orchestrated)  
        ↓  
Snowflake (RAW layer)  
        ↓  
dbt (staging → intermediate → marts)  
        ↓  
Analytics Layer  
    • Scoring models  
    • Ranking models  
    • Industry aggregation  
    • Price performance models  
        ↓  
Access Layer  
    • Superset dashboards  
    • MCP Semantic Layer (Claude Desktop AI interface)

---

# Core Architectural Principles

1. Canonical universe definition  
   Wikipedia defines which stocks exist.

2. Strict separation of concerns  
   API access ≠ warehouse writes ≠ orchestration ≠ transformation.

3. Snowflake is the source of truth.

4. dbt defines analytical meaning.

5. Airflow controls time.

6. All daily-grain models are incremental and optimized for multi-year scale.

---

# Snowflake Layout

Single shared database:

DATAEXPERT_STUDENT

Schema naming convention (dbt default behavior):

{student_schema}  
{student_schema}_stg  
{student_schema}_int  
{student_schema}_dims  
{student_schema}_marts  

Example:
BALAZSILLOVAI30823_MARTS

All analytical exposure (Superset + MCP) happens strictly from the MARTS schema.

---

# dbt Modeling Layers

## Staging (Views)

• Clean raw API data  
• Standardize column names  
• Enforce types  
• No business logic  

## Intermediate (Tables, incremental where needed)

• Price returns
• Technical indicators (SMA, RSI, MACD)
• Daily price changes
• Annual fundamentals with YoY growth
• Rolling metrics (volatility, drawdown)

Optimized with lookback-window incremental filters for:

• SMA-200
• LAG functions
• Rolling volatility

## Dimensions

dim_sp500_companies_current  
Current snapshot of S&P 500 universe.

## Marts

### mart_sp500_technical_scores
Daily technical scoring (0–100)

### mart_sp500_fundamental_scores
Annual fundamental scoring (0–100)

### mart_sp500_composite_scores
Daily combined technical + fundamental scoring

### mart_sp500_industry_scores
Composite scores enriched with:
• Company
• Sector
• Industry

Used for sector-level analytics.

### mart_sp500_price_performance
Daily:
• Returns
• Rolling returns
• Volatility
• Drawdown
• YTD performance

Enriched with company metadata.

---

# Orchestration

Airflow handles:

• Daily ETL pipelines
• Backfill pipelines
• dbt DAG (Cosmos-based)
• ETL dependency gating via ExternalTaskSensor

No business logic inside DAGs.

---

# MCP + Semantic Layer

The project exposes selected mart tables via:

src/mcp/mcp_server.py

Whitelisted tables only.

Semantic layer:
semantic_layer.yaml

Defines:
• Dimensions
• Measures
• Time grains
• Business descriptions
• Derived metrics (YTD return, drawdown, etc.)

This enables Claude Desktop to:

• Answer analytical questions
• Compare sectors
• Identify leaders/laggards
• Detect drawdown periods
• Analyze cycles

AI queries operate strictly on marts schema.

---

# Superset

Superset is connected directly to Snowflake.

Used for:

• Exploratory analysis
• Dashboards
• Performance charts
• Sector heatmaps
• Risk analysis

Connection uses:
snowflake-sqlalchemy driver.

---

# Current System Capabilities

The system can:

• Backfill 3–5 years of daily stock data
• Compute rolling technical indicators
• Align fiscal-year fundamentals to daily prices
• Compute composite weighted scores
• Rank stocks daily
• Analyze sector performance
• Calculate volatility and drawdowns
• Support AI narrative analytics via MCP
• Visualize data in Superset

---

# Design Rules

Claude should:

• Respect incremental modeling logic
• Avoid rewriting working pipelines
• Keep API logic separate from warehouse logic
• Keep DAGs thin
• Keep marts analytics-ready
• Assume Snowflake uppercase identifiers
• Avoid cross-schema exposure

Claude should NOT:

• Introduce unnecessary tools
• Mix orchestration and business logic
• Bypass semantic layer for AI queries
• Expose RAW/STG schemas to MCP

---

# Future Product Vision

Potential evolution:

• Backtesting engine
• Strategy simulation
• Factor-based ranking
• Regime detection (bull/bear cycle)
• Risk-adjusted scoring
• Portfolio optimizer
• ML signal enhancement
• Alternative data signals
• Web UI for stock screening

---

# Mental Model

Wikipedia defines WHAT exists.  
APIs define WHAT happens.  
Snowflake stores TRUTH.  
dbt defines MEANING.  
Airflow controls TIME.  
Superset shows INSIGHT.  
MCP enables INTELLIGENCE.

---

This document must evolve with the platform.