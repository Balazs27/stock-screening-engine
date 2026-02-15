# Stock Screening & Scoring Engine

A production-style analytics platform that ingests market and fundamentals data for S&P 500 stocks, computes quantitative signals, and generates daily 0–100 scores to rank investment opportunities.

This project demonstrates modern Data Engineering and Analytics Engineering practices, including orchestration, incremental modeling, AI integration, and BI visualization.

---

## What this project does

• Ingests stock prices, technical indicators, and financial statement data from external APIs  
• Maintains a canonical S&P 500 universe definition  
• Stores raw and processed data in Snowflake  
• Transforms data using dbt (staging → intermediate → marts)  
• Computes:
  - Technical scores (trend, momentum, MACD, price action)
  - Fundamental scores (profitability, growth, financial health, cash quality)
  - Composite weighted scores
  - Industry-enriched rankings
  - Rolling returns, volatility, and drawdowns  
• Orchestrates pipelines with Airflow (daily + backfill DAGs)  
• Exposes analytics via:
  - Superset dashboards
  - MCP Semantic Layer for AI-powered analysis in Claude Desktop  

---

## Tech Stack

- Python (ETL)
- Airflow (orchestration)
- dbt (transformations & modeling)
- Snowflake (warehouse)
- Superset (BI visualization)
- MCP + Semantic Layer (AI interface)
- Docker (containerization)

---

## High-Level Architecture

External APIs  
→ Python ETL  
→ Snowflake (RAW)  
→ dbt (staging → intermediate → marts)  
→ Scoring & Ranking Models  
→ Superset Dashboards + AI via MCP  

---

## Current Capabilities

• Multi-year backfills (3+ years daily data)  
• Incremental daily updates  
• Rolling technical indicators (SMA, RSI, MACD)  
• Annual fundamental alignment to daily prices  
• Composite scoring with multiple weighting schemes  
• Sector & industry-level analytics  
• Volatility and drawdown analysis  
• AI-driven natural language analytics through Claude Desktop  

---

## Project Status

Actively evolving from capstone project into a full-featured stock analytics platform.

Next phase:  
• Strategy backtesting  
• Portfolio simulation  
• Factor modeling  
• Risk-adjusted ranking  
• ML-enhanced signals  