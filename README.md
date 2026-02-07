# Stock Screening & Scoring Engine

A data platform that ingests market and fundamentals data for S&P500 stocks,
computes quantitative signals, and produces a daily 0–100 score to rank investment opportunities.

## What this project does
- Ingests stock prices and financial data from external APIs
- Stores raw and processed data in Snowflake
- Transforms data using dbt (staging → marts)
- Orchestrates pipelines with Airflow
- Produces ranked stock scores based on momentum, fundamentals, and risk signals

## Tech stack
- Python
- Airflow
- dbt
- Snowflake
- Docker

## Architecture (high level)
APIs → Python ETL → Snowflake (raw) → dbt models → analytics-ready marts → rankings

## Project status
Actively under development as a Analytics/Data Engineering capstone project.
