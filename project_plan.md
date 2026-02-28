# Implementation Plan — Daily Agentic Stock Opportunity Pipeline

## Overview

Build an AI agent-powered stock opportunity discovery system on top of the existing data infrastructure. The system runs daily, identifies short-horizon (~30-day) investment opportunities within the S&P 500, and produces dated PDF reports with transparent, explainable theses.

**Key leverage**: All data ingestion (Polygon, FMP, Wikipedia), warehouse (Snowflake RAW→STG→INT→MARTS), and scoring (technical/fundamental/composite 0-100) already exist. This plan builds the intelligence and reporting layers on top.

---

## Phase 0 — Foundation & Configuration

### Objective
Establish project scaffolding, configuration system, secret management, and data access patterns for the agent layer.

### Deliverables

1. **Pipeline configuration system** (`src/agents/config/`)
   - `pipeline_config.yaml` — master config: universe, sector mappings, scoring weights, thresholds, shortlist size, agent parameters, output paths
   - `config_loader.py` — typed config loader with validation and defaults
   - Supports overrides via environment variables for CI/CD

2. **Secret management for LLM API**
   - Add `ANTHROPIC_API_KEY` to `.env` template and documentation
   - Follow existing pattern: `os.environ["ANTHROPIC_API_KEY"]`
   - Add `anthropic` Python SDK to `requirements.txt`

3. **Agent data access layer** (`src/agents/data/`)
   - `snowflake_reader.py` — read-only Snowflake session factory using existing `snowflake_loader.get_snowflake_session()` pattern
   - Pre-built query functions for each mart table (returns DataFrames)
   - Sector-filtered queries, date-filtered queries, top-N queries

4. **Output directory conventions**
   - `output/{YYYY-MM-DD}/` — dated run folders
   - `output/{YYYY-MM-DD}/sectors/` — per-sector PDFs
   - `output/{YYYY-MM-DD}/aggregate/` — cross-sector summary PDF
   - `output/{YYYY-MM-DD}/manifest.json` — run metadata
   - Add `output/` to `.gitignore`

### Acceptance Criteria
- `pipeline_config.yaml` loads and validates without errors
- `snowflake_reader.py` returns DataFrames from all 5 mart tables
- `output/` directory structure created by a test helper
- `ANTHROPIC_API_KEY` documented in `.env.example`

---

## Phase 1 — Agent Infrastructure

### Objective
Build a minimal, extensible agent abstraction with shared context, orchestration, and structured logging.

### Deliverables

1. **Base agent protocol** (`src/agents/core/base_agent.py`)
   - Abstract base class: `BaseAgent` with `run(context: RunContext) -> AgentOutput`
   - `RunContext` dataclass: run_date, universe (list of tickers), sector (optional), config, shared data store
   - `AgentOutput` dataclass: agent_name, status, data (dict), errors, duration_ms
   - Standardized error handling and timeout enforcement

2. **LLM client wrapper** (`src/agents/core/llm_client.py`)
   - Thin wrapper around `anthropic.Anthropic()` with retry logic (3x exponential backoff)
   - Configurable model selection (default: claude-sonnet-4-6 for cost efficiency, claude-opus-4-6 for thesis writing)
   - Structured output parsing (JSON mode) for agent responses
   - Token usage tracking per agent per run

3. **Context schema** (`src/agents/core/schemas.py`)
   - Pydantic models for shared data passed between agents:
     - `StockCandidate` — ticker, company_name, sector, industry, scores, signals
     - `SectorContext` — sector name, avg scores, top/bottom performers, sector thesis
     - `MarketContext` — date, broad market signals, sector rotation indicators
     - `OpportunityThesis` — ticker, entry rationale, catalysts, risks, assumptions, 30-day target thesis
   - All schemas serializable to dict for logging

4. **Pipeline orchestrator** (`src/agents/core/orchestrator.py`)
   - `DailyPipeline` class: loads config, initializes agents, executes in defined order
   - Sequential execution with dependency resolution (market context → sector analysis → ranking → thesis → report)
   - Per-sector parallelism via `concurrent.futures.ThreadPoolExecutor`
   - Captures timing, errors, and outputs per stage

5. **Run manifest and logging** (`src/agents/core/manifest.py`)
   - `RunManifest` dataclass: run_id (UUID), run_date, start_time, end_time, config_snapshot, agent_results, errors
   - Writes `manifest.json` to `output/{date}/`
   - Python `logging` integration with structured JSON log lines

### Acceptance Criteria
- `BaseAgent` subclass can be instantiated and run with mock context
- `llm_client.py` makes a successful API call (integration test with real key)
- `DailyPipeline` executes a no-op pipeline and writes `manifest.json`
- All schemas validate with sample data

---

## Phase 2 — Data Collection & Context Agents

### Objective
Build agents that read from existing Snowflake marts and external signals to assemble the analytical context for each run.

### Deliverables

1. **Market context agent** (`src/agents/collectors/market_context_agent.py`)
   - Reads `mart_sp500_price_performance` for broad market signals:
     - Avg daily return across S&P 500 (market direction)
     - % of stocks with positive rolling_30d_return (breadth)
     - Avg rolling_30d_volatility (risk regime)
     - Avg drawdown_pct (market stress level)
   - Reads `mart_sp500_industry_scores` aggregated by sector:
     - Per-sector avg composite_score_equal (sector rotation signal)
   - Uses LLM to synthesize a 3-5 sentence market context summary
   - Output: `MarketContext` schema

2. **Sector scores agent** (`src/agents/collectors/sector_scores_agent.py`)
   - For a given sector, reads `mart_sp500_industry_scores` filtered by sector
   - Computes: sector avg/median/std composite score, top 10 and bottom 10 by score
   - Reads `mart_sp500_price_performance` for sector-level return distribution
   - Output: `SectorContext` schema per sector

3. **Stock detail agent** (`src/agents/collectors/stock_detail_agent.py`)
   - For a given list of candidate tickers, reads all 5 marts and assembles a full profile:
     - Technical score + component breakdown (trend, momentum, MACD, price action)
     - Fundamental score + component breakdown (profitability, growth, health, cash)
     - Price performance (returns, volatility, drawdown)
     - Composite scores (all 3 variants)
   - Output: list of `StockCandidate` schemas

4. **News catalyst agent** (`src/agents/collectors/news_catalyst_agent.py`)
   - Reads `stg_sp500_news` (Polygon) for recent articles per ticker (last 7 days)
   - Uses LLM to extract catalysts: earnings surprises, product launches, M&A, management changes, regulatory events
   - Classifies catalysts as positive/negative/neutral with confidence
   - Output: per-ticker catalyst summary dict

### Acceptance Criteria
- Market context agent returns a valid `MarketContext` with real Snowflake data
- Sector scores agent returns `SectorContext` for "Information Technology" sector
- Stock detail agent returns `StockCandidate` for AAPL, MSFT, NVDA
- News catalyst agent extracts at least 1 catalyst from recent news data

---

## Phase 3 — Scoring, Ranking & Shortlisting

### Objective
Build the scoring overlay that combines existing dbt scores with agent-derived signals to rank and shortlist opportunities.

### Deliverables

1. **Opportunity scorer** (`src/agents/analysts/opportunity_scorer.py`)
   - Combines multiple signal dimensions into a single opportunity score (0-100):
     - Technical momentum (from `mart_sp500_technical_scores`): 25% weight
     - Fundamental quality (from `mart_sp500_fundamental_scores`): 20% weight
     - Price performance trajectory (from `mart_sp500_price_performance`): 20% weight
     - Catalyst strength (from news catalyst agent): 20% weight
     - Sector favorability (from sector scores agent): 15% weight
   - All weights configurable via `pipeline_config.yaml`
   - Transparent: every score decomposable into its factors
   - Output: list of `StockCandidate` with `opportunity_score` field populated

2. **Sector ranker agent** (`src/agents/analysts/sector_ranker_agent.py`)
   - For each sector: ranks stocks by opportunity_score
   - Uses LLM to evaluate relative positioning: "Is this stock's score justified given its sector context?"
   - Flags anomalies: high score but deteriorating fundamentals, low score but strong catalyst
   - Output: per-sector ranked list with LLM-annotated rationale

3. **Shortlist selector** (`src/agents/analysts/shortlist_selector.py`)
   - Applies configurable selection criteria:
     - Minimum opportunity_score threshold (default: 65)
     - Maximum per-sector concentration (default: 3 stocks per sector)
     - Maximum total shortlist size (default: 10-15)
     - Exclude stocks with drawdown_pct > threshold (default: -20%)
   - Deterministic: same inputs → same shortlist
   - Output: final shortlist of `StockCandidate` objects

### Acceptance Criteria
- Opportunity scorer produces scores for all ~500 S&P 500 stocks
- Sector ranker annotates top 5 per sector with LLM rationale
- Shortlist selector returns 10-15 stocks meeting all criteria
- All scores are traceable to their factor components

---

## Phase 4 — Thesis Generation & Risk Assessment

### Objective
For each shortlisted stock, generate a structured 30-day investment thesis with explicit risks and assumptions.

### Deliverables

1. **Thesis writer agent** (`src/agents/analysts/thesis_writer_agent.py`)
   - For each shortlisted stock, uses LLM (claude-opus-4-6 for quality) to generate:
     - **Opportunity summary** (2-3 sentences): what the opportunity is
     - **30-day thesis** (1 paragraph): why this stock should outperform over ~1 month
     - **Key catalysts** (bulleted): specific near-term events driving the thesis
     - **Supporting signals** (bulleted): score breakdown, technical/fundamental factors
     - **Entry considerations**: current price context, recent momentum direction
   - Structured output via Pydantic `OpportunityThesis` schema
   - LLM prompt includes full `StockCandidate` data + `SectorContext` + `MarketContext`

2. **Risk assessor agent** (`src/agents/analysts/risk_assessor_agent.py`)
   - For each shortlisted stock, generates:
     - **Key risks** (3-5 bullets): what could go wrong in the next 30 days
     - **Assumptions** (3-5 bullets): what must hold true for the thesis to play out
     - **Downside scenario** (1-2 sentences): what happens if the thesis fails
     - **Risk rating** (Low/Medium/High): overall risk assessment
   - Uses contrarian prompting: explicitly asks LLM to argue against the thesis
   - Output: per-ticker risk assessment dict

3. **Disclaimer and scope framing** (`src/agents/config/disclaimers.yaml`)
   - Standard disclaimers for research/educational use
   - Scope statement: "30-day opportunity discovery, not financial advice"
   - Included in every PDF report

### Acceptance Criteria
- Thesis writer generates structured thesis for 3 test tickers
- Risk assessor generates contrarian risk assessment for same tickers
- All outputs conform to Pydantic schemas
- Disclaimers load from YAML config

---

## Phase 5 — PDF Report Generation

### Objective
Build a PDF rendering pipeline that compiles agent outputs into professional, dated reports.

### Deliverables

1. **PDF engine setup** (`src/agents/reports/pdf_engine.py`)
   - Uses `fpdf2` (pure Python, no system dependencies) or `reportlab`
   - Defines page layout: header with date/branding, footer with page numbers and disclaimer
   - Reusable components: section headers, score tables, bullet lists, mini charts
   - Consistent styling: fonts, colors, spacing

2. **Chart generation** (`src/agents/reports/charts.py`)
   - Uses `matplotlib` for static chart images embedded in PDF:
     - Sector heatmap (avg composite score by sector)
     - Score distribution histogram (opportunity scores)
     - Per-stock score breakdown bar chart (factor decomposition)
   - Charts saved as temporary PNGs, embedded in PDF, cleaned up after

3. **Sector report template** (`src/agents/reports/sector_report.py`)
   - Per-sector PDF:
     - Sector summary (avg scores, market context)
     - Ranked stock table (top 10 by opportunity score)
     - Detailed thesis for each shortlisted stock in this sector
     - Risk assessment per stock
   - Written to `output/{date}/sectors/{sector_name}.pdf`

4. **Aggregate report template** (`src/agents/reports/aggregate_report.py`)
   - Cross-sector "Today's Opportunities" PDF:
     - Executive summary (market context, key themes)
     - Sector heatmap
     - Top opportunities table (shortlisted stocks across all sectors)
     - Per-stock thesis + risk (1 page per stock)
     - Appendix: methodology, scoring weights, disclaimers
   - Written to `output/{date}/aggregate/daily_opportunities_{date}.pdf`

5. **Report orchestration** (`src/agents/reports/report_builder.py`)
   - Coordinates PDF generation:
     - Generates all sector PDFs (parallel)
     - Generates aggregate PDF
     - Validates all PDFs are non-empty and readable
   - Output: list of generated file paths

### Acceptance Criteria
- Sector PDF generates with real data for "Information Technology"
- Aggregate PDF generates with 10+ stock theses
- All PDFs open correctly in standard PDF readers
- Charts render with correct data labels
- No HTML, Markdown, or non-PDF artifacts in `output/`

---

## Phase 6 — Pipeline Orchestration & Daily Execution

### Objective
Wire everything into a repeatable daily pipeline with CLI entry point and optional Airflow integration.

### Deliverables

1. **CLI entry point** (`src/agents/cli.py`)
   - `python -m src.agents.cli run --date 2026-02-28` — full pipeline for a specific date
   - `python -m src.agents.cli run` — defaults to today
   - `python -m src.agents.cli run --sector "Information Technology"` — single sector mode
   - `python -m src.agents.cli run --dry-run` — executes data collection only, no LLM calls
   - Exit codes: 0 = success, 1 = partial failure (some agents failed), 2 = total failure

2. **Airflow DAG** (`dags/agents/stock_opportunity_agent_dag.py`)
   - Schedule: `@daily`, runs after `stock_screening_dbt_daily_dag` completes
   - ExternalTaskSensor on `stock_screening_dbt_daily_dag`
   - Single PythonOperator calling the pipeline entry point
   - Follows existing DAG patterns (imports from `airflow.providers.standard.*`)

3. **Caching layer** (`src/agents/core/cache.py`)
   - File-based cache in `output/{date}/.cache/`
   - Caches Snowflake query results and LLM responses per run date
   - Enables re-running failed stages without re-fetching data
   - TTL: same-day only (cache invalidated on next run date)

4. **Error handling and retries**
   - Agent-level retry: each agent retries up to 2x on transient failures
   - Pipeline-level: if a non-critical agent fails, pipeline continues with degraded output
   - Critical agents (data collection, scoring): failure halts pipeline
   - Non-critical agents (thesis writing, risk assessment): failure produces "analysis unavailable" in PDF

### Acceptance Criteria
- CLI runs end-to-end and produces PDFs in `output/{date}/`
- Pipeline completes in under 15 minutes for full S&P 500
- `manifest.json` captures all timing, errors, and config
- Re-running same date uses cached data (no duplicate API/LLM calls)
- Airflow DAG parses without errors (`astro dev parse`)

---

## Phase 7 — Testing & Quality Assurance

### Objective
Establish test coverage for scoring logic, PDF generation, and end-to-end pipeline integrity.

### Deliverables

1. **Unit tests** (`tests/agents/`)
   - `test_opportunity_scorer.py` — score calculation with known inputs produces expected outputs
   - `test_shortlist_selector.py` — selection criteria correctly filter/limit candidates
   - `test_config_loader.py` — config validation catches invalid YAML
   - `test_schemas.py` — Pydantic schemas validate and reject bad data

2. **Integration tests** (`tests/agents/`)
   - `test_snowflake_reader.py` — reads from Snowflake and returns expected columns
   - `test_llm_client.py` — makes API call and parses structured response
   - `test_pipeline_smoke.py` — runs full pipeline on 5 tickers (mini universe) and produces PDF

3. **PDF smoke tests** (`tests/agents/`)
   - `test_pdf_generation.py` — generates PDF from mock data, verifies file size > 0, page count > 0
   - Verifies no non-PDF files created in output/

4. **Scoring determinism test**
   - Run scorer twice with identical inputs, assert identical outputs
   - Ensures no randomness in scoring (LLM outputs may vary, but scores are deterministic)

### Acceptance Criteria
- All unit tests pass
- Integration tests pass with real Snowflake connection
- PDF smoke test generates valid PDF from mock data
- Test suite runs in under 2 minutes (excluding integration tests)

---

## Phase 8 — Documentation & Operational Readiness

### Objective
Document how to run, configure, extend, and monitor the pipeline.

### Deliverables

1. **Pipeline operations guide** (update `README.md`)
   - How to run daily pipeline (CLI)
   - How to configure weights, thresholds, universe
   - How to add a new agent or scoring factor
   - How to add a new sector-specific workflow
   - Environment variables required

2. **Update CLAUDE.md** — add agent layer references
3. **Update general_index.md** — add all new files
4. **Update PROJECT_STRUCTURE.md** — add agent architecture diagram
5. **Update semantic_layer.yaml** — if any new mart models are added

### Acceptance Criteria
- New team member can run the pipeline by following README
- All new files indexed in general_index.md
- CLAUDE.md routes to agent layer rules

---

## Architecture Diagram

```
                    EXISTING INFRASTRUCTURE
                    ─────────────────────────
    Polygon/FMP/Wikipedia → Airflow ETL → Snowflake RAW
                                              │
                                         dbt (Cosmos)
                                              │
                                    STG → INT → MARTS
                                              │
                    ─────────────────────────────────────
                    NEW AGENT LAYER
                    ─────────────────────────────────────
                                              │
                              ┌────────────────┼────────────────┐
                              ▼                ▼                ▼
                    Market Context     Sector Scores      Stock Detail
                        Agent              Agent              Agent
                              │                │                │
                              └────────────────┼────────────────┘
                                              │
                                    News Catalyst Agent
                                              │
                                    Opportunity Scorer
                                              │
                                ┌─────────────┼─────────────┐
                                ▼             ▼             ▼
                          Sector Ranker  Shortlist    (per sector)
                              Agent      Selector
                                              │
                                ┌─────────────┼─────────────┐
                                ▼                           ▼
                          Thesis Writer              Risk Assessor
                              Agent                     Agent
                                              │
                                       Report Builder
                                              │
                              ┌────────────────┼────────────────┐
                              ▼                                ▼
                    Sector PDFs                    Aggregate PDF
                    output/{date}/sectors/          output/{date}/aggregate/
```

## Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| LLM | Claude API (anthropic SDK) | Project is Claude-native (MCP, semantic layer) |
| Agent framework | Custom (BaseAgent + orchestrator) | Minimal dependencies, full control |
| PDF generation | fpdf2 | Pure Python, no system deps, good table support |
| Charts | matplotlib | Already common in Python data stacks |
| Config | YAML | Consistent with existing dbt/semantic layer patterns |
| Data access | Snowpark (existing) | Reuses existing session management |
| Schema validation | Pydantic | Standard for structured data in Python |
| Testing | pytest | Standard Python test framework |

## Cost Considerations

| Resource | Estimated Daily Cost | Notes |
|----------|---------------------|-------|
| Claude API (Sonnet for analysis) | ~$2-5/run | ~50 agent calls × ~2K tokens avg |
| Claude API (Opus for thesis) | ~$3-8/run | ~15 thesis calls × ~4K tokens avg |
| Snowflake queries | Negligible | Shared warehouse, small scans on marts |
| Total | ~$5-13/day | Configurable by adjusting model selection |
