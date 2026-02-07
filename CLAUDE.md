# CLAUDE.md

## Project Overview

**Project name:** Stock Screening & Scoring Engine
**Purpose:** Build a production-style data platform that ingests financial data for S&P 500 companies, computes quantitative signals, scores each stock (0–100), and ranks them daily to surface top investment opportunities.

In plain terms: this system continuously watches hundreds of stocks, processes price and fundamentals data, and outputs a ranked list of stocks based on health, momentum, and risk signals.

This repository is a **Data Engineering capstone project**, designed to demonstrate real-world practices: modular ETL design, orchestration with Airflow, transformations with dbt, and analytics-ready data models in Snowflake.

---

## High-Level Architecture

```
External Sources
(Wikipedia, Polygon, FMP)
        ↓
Python ETL Jobs (src/jobs)
        ↓
Snowflake RAW / LOOKUP / SOURCE tables
        ↓
dbt (staging → intermediate → marts)
        ↓
Scoring & Ranking Tables
```

Key architectural principle:

> One canonical universe definition (S&P 500) → all downstream pipelines depend on it.

---

## Data Sources

### 1. Wikipedia (Universe Definition)

* Scrapes the official S&P 500 constituents list
* Produces a **snapshot lookup table** in Snowflake
* Contains ticker, company name, GICS sector/sub-industry, headquarters, CIK, founded year, etc.
* This table is the **base dependency** for all other ETLs

### 2. Polygon API

* Market data (prices, volumes, indicators)
* Filtered strictly to S&P 500 tickers from the lookup table

### 3. FMP API

* Fundamentals and financial statement data
* Also filtered to S&P 500 tickers

---

## Repository Structure (Important for Claude)

```
stock-screening-engine/
│
├── dags/                  # Airflow DAGs (orchestration only)
│   ├── etl/
│   ├── dbt/
│   └── stock_screening_dag.py
│
├── src/                   # Core Python code (business logic)
│   ├── api_clients/       # External data access (NO Snowflake here)
│   │   ├── wikipedia_client.py
│   │   ├── polygon_client.py
│   │   └── fmp_client.py
│   │
│   ├── loaders/           # Persistence layer (Snowflake writes only)
│   │   └── snowflake_loader.py
│   │
│   ├── jobs/              # Executable ETL jobs (Airflow entrypoints)
│   │   ├── ingest_sp500_universe.py
│   │   ├── ingest_polygon_prices.py
│   │   └── ingest_fmp_financials.py
│   │
│   ├── utils/             # Shared helpers (logging, dates, retries)
│   │   ├── logging.py
│   │   └── dates.py
│   │
│   └── __init__.py
│
├── dbt_project/           # dbt transformations
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   ├── macros/
│   ├── seeds/
│   ├── snapshots/
│   ├── dbt_project.yml
│   ├── packages.yml
│   └── profiles.yml
│
├── capstone_project/      # Legacy / original scripts (for refactoring)
│   └── (original monolithic ETL scripts)
│
├── docker/
├── tests/
├── requirements.txt
├── .env.example
├── README.md
└── CLAUDE.md
```

---

## Design Rules (Very Important)

### Separation of Concerns

**api_clients/**

* Fetch data from external APIs or scrape websites
* Handle auth, pagination, rate limits
* Return pandas DataFrames or Python objects
* ❌ Never connect to Snowflake

**loaders/**

* Own Snowflake connections and write logic
* Create tables, delete partitions, insert data
* ❌ Never call external APIs

**jobs/**

* Glue layer
* Orchestrates: fetch → load
* This is what Airflow calls
* Very thin, readable scripts

**utils/**

* Stateless helper functions
* Logging, date handling, small utilities

---

## Current State of the Project

* dbt project successfully migrated and validated (`dbt debug` passes)
* Environment variables managed via `.env` / `.env.example`
* Core dependencies installed via `requirements.txt`
* Wikipedia S&P 500 scraper has been **successfully refactored** into the new modular structure
* Original bootcamp scripts are copied into `capstone_project/` for:

  * Safe experimentation
  * Easier slicing/refactoring
  * Allowing Claude to help refactor logic incrementally

---

## Canonical Tables

### sp500_tickers_lookup

* Source: Wikipedia
* Grain: one row per ticker per snapshot date
* Used as a lookup table for all downstream ETLs

---

## How Claude Should Help on This Project

Claude should:

* Follow the separation of concerns strictly
* Prefer incremental refactors over rewrites
* Keep Airflow DAGs thin (no business logic)
* Reuse existing loaders and clients when possible
* Assume Snowflake is the primary warehouse
* Treat dbt as the transformation and modeling layer
* Help migrate scripts from `capstone_project/` into `src/` modules

Claude should NOT:

* Introduce new tools unless clearly justified
* Mix API logic with Snowflake logic
* Add unnecessary abstractions
* Break working pipelines for “cleanliness” alone

---

## Future Extensions (Planned)

* Daily scoring models (momentum, volatility, fundamentals)
* Stock ranking marts in dbt
* Backtesting logic
* Feature-level documentation
* Visualization layer

---

## Mental Model Summary

> Wikipedia defines *what* stocks exist.
> APIs define *what happens* to them.
> Snowflake stores truth.
> dbt defines meaning.
> Airflow controls time.

This document should be kept up to date as the system evolves.
