# Feature Checklist — Daily Agentic Stock Opportunity Pipeline

Chronological, standalone features. Each item is independently implementable, testable, and mergeable.

---

## Phase 0 — Foundation & Configuration

- [ ] **Create pipeline configuration system**
  - Scope: Add `src/agents/__init__.py`, `src/agents/config/__init__.py`, `src/agents/config/pipeline_config.yaml` (master config with universe, sector mappings, scoring weights, shortlist thresholds, agent parameters, model selection, output paths), and `src/agents/config/config_loader.py` (typed config loader using PyYAML + dataclasses, validates required fields, applies defaults, supports env var overrides for CI/CD).
  - Key files: `src/agents/config/pipeline_config.yaml`, `src/agents/config/config_loader.py`
  - Acceptance criteria: `config_loader.load_config()` returns a validated `PipelineConfig` dataclass from YAML. Invalid YAML raises `ConfigValidationError`. Default values apply for omitted fields. Unit test covers valid load, missing field, and invalid type scenarios.

- [ ] **Add Anthropic SDK dependency and secret management**
  - Scope: Add `anthropic` and `pydantic` to `requirements.txt`. Document `ANTHROPIC_API_KEY` in the existing `.env` pattern. The key is accessed via `os.environ["ANTHROPIC_API_KEY"]` following the project's existing credential pattern (see `src/api_clients/polygon_client.py` for reference). Do NOT read or modify `.env` — only update documentation and requirements.
  - Key files: `requirements.txt`
  - Acceptance criteria: `pip install -r requirements.txt` installs anthropic SDK. `import anthropic` succeeds. No `.env` files are read or committed.

- [ ] **Build agent data access layer (Snowflake reader)**
  - Scope: Create `src/agents/data/__init__.py` and `src/agents/data/snowflake_reader.py`. Provides a read-only interface to all 5 mart tables plus `stg_sp500_news` for catalyst extraction. Reuses `src/loaders/snowflake_loader.get_snowflake_session()` for session creation. Functions: `read_technical_scores(session, date, tickers=None)`, `read_fundamental_scores(session, tickers=None)`, `read_composite_scores(session, date, tickers=None)`, `read_industry_scores(session, date, sector=None)`, `read_price_performance(session, date, tickers=None)`, `read_recent_news(session, tickers, lookback_days=7)`, `read_sector_list(session)`. All return pandas DataFrames. Query the `{STUDENT_SCHEMA}_MARTS` schema (uppercase Snowflake identifiers) for marts and `{STUDENT_SCHEMA}_STG` for news staging.
  - Key files: `src/agents/data/snowflake_reader.py`
  - Acceptance criteria: Each reader function returns a non-empty DataFrame when called with a valid Snowflake session and a date that has data. Column names match the dbt model outputs (lowercase in pandas). An integration test confirms all 6 reader functions work against Snowflake.

- [ ] **Establish output directory conventions and .gitignore**
  - Scope: Create `output/.gitkeep` to establish the directory. Add `output/*` and `!output/.gitkeep` to `.gitignore`. Create a utility `src/agents/core/__init__.py` and `src/agents/core/output_manager.py` with functions: `ensure_run_directory(run_date: str) -> Path` (creates `output/{date}/`, `output/{date}/sectors/`, `output/{date}/aggregate/`, `output/{date}/.cache/`), `get_sector_pdf_path(run_date, sector_name) -> Path`, `get_aggregate_pdf_path(run_date) -> Path`, `get_manifest_path(run_date) -> Path`. Sector names are slugified for filesystem safety (e.g., "Information Technology" → "information-technology").
  - Key files: `src/agents/core/output_manager.py`, `.gitignore`
  - Acceptance criteria: `ensure_run_directory("2026-02-28")` creates all expected subdirectories. Path helpers return correct paths. Directory is gitignored except for `.gitkeep`. Unit test verifies directory creation and path generation.

---

## Phase 1 — Agent Infrastructure

- [ ] **Define core schemas (Pydantic models)**
  - Scope: Create `src/agents/core/schemas.py` with Pydantic v2 models: `StockCandidate` (ticker, company_name, sector, industry, technical_score, fundamental_score, composite_score, opportunity_score, trend_score, momentum_score, macd_score, price_action_score, profitability_score, growth_score, health_score, cash_score, daily_return, rolling_30d_return, rolling_30d_volatility, drawdown_pct, catalysts: list[str], catalyst_sentiment: str), `SectorContext` (sector, avg_composite_score, median_composite_score, std_composite_score, top_performers: list[str], bottom_performers: list[str], sector_summary: str), `MarketContext` (date, avg_daily_return, breadth_pct_positive, avg_volatility, avg_drawdown, sector_scores: dict[str, float], market_summary: str), `OpportunityThesis` (ticker, company_name, sector, opportunity_summary, thirty_day_thesis, key_catalysts: list[str], supporting_signals: list[str], entry_considerations: str, key_risks: list[str], assumptions: list[str], downside_scenario: str, risk_rating: Literal["Low", "Medium", "High"], opportunity_score: float, technical_score: float, fundamental_score: float). All models have `.model_dump()` for serialization.
  - Key files: `src/agents/core/schemas.py`
  - Acceptance criteria: All schemas instantiate with valid sample data. Invalid data (e.g., score > 100) raises `ValidationError`. Schemas serialize to dict and deserialize back. Unit test covers instantiation, validation, and round-trip serialization for each schema.

- [ ] **Build base agent abstraction**
  - Scope: Create `src/agents/core/base_agent.py`. Define `RunContext` dataclass (run_date: str, universe: list[str], sector: Optional[str], config: PipelineConfig, shared_data: dict, snowflake_session: Session). Define `AgentOutput` dataclass (agent_name: str, status: Literal["success", "partial", "failed"], data: dict, errors: list[str], duration_ms: int). Define `BaseAgent` abstract class with: abstract method `run(context: RunContext) -> AgentOutput`, concrete `execute(context: RunContext) -> AgentOutput` that wraps `run()` with timing, error handling, and logging. Agents log start/end/errors via Python `logging` module.
  - Key files: `src/agents/core/base_agent.py`
  - Acceptance criteria: A `MockAgent(BaseAgent)` subclass can be created, executed, and returns a valid `AgentOutput`. Execution timing is captured. Exceptions in `run()` are caught and returned as `AgentOutput` with status="failed". Unit test covers success, failure, and timing scenarios.

- [ ] **Build LLM client wrapper**
  - Scope: Create `src/agents/core/llm_client.py`. Class `LLMClient` wraps `anthropic.Anthropic()`. Methods: `generate(prompt: str, system: str, model: str = "claude-sonnet-4-6", max_tokens: int = 4096) -> str` (plain text response), `generate_structured(prompt: str, system: str, response_schema: type[BaseModel], model: str = "claude-sonnet-4-6") -> BaseModel` (parses JSON from LLM into Pydantic model, retries up to 2x on parse failure). Includes token usage tracking: `total_input_tokens`, `total_output_tokens` properties. Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s) on transient API errors (rate limit, overloaded). Uses `ANTHROPIC_API_KEY` env var.
  - Key files: `src/agents/core/llm_client.py`
  - Acceptance criteria: `LLMClient.generate()` returns a non-empty string. `generate_structured()` returns a valid Pydantic model instance. Token usage increments after calls. Retry logic handles simulated failures. Unit test mocks the anthropic client; integration test makes a real API call.

- [ ] **Build run manifest and structured logging**
  - Scope: Create `src/agents/core/manifest.py`. Class `RunManifest` (run_id: UUID, run_date: str, start_time: datetime, end_time: Optional[datetime], config_snapshot: dict, agent_results: list[AgentOutput], total_llm_input_tokens: int, total_llm_output_tokens: int, status: str, errors: list[str]). Methods: `add_agent_result(output: AgentOutput)`, `finalize()` (sets end_time, computes status), `write(output_dir: Path)` (writes manifest.json). Configure Python logging to write structured JSON lines to `output/{date}/pipeline.log` and to stderr for console output.
  - Key files: `src/agents/core/manifest.py`
  - Acceptance criteria: Manifest writes valid JSON to `manifest.json`. All agent results are captured with timing. `finalize()` sets overall status based on agent statuses. Unit test creates a manifest, adds mock results, finalizes, and verifies JSON output.

- [ ] **Build pipeline orchestrator**
  - Scope: Create `src/agents/core/orchestrator.py`. Class `DailyPipeline` initialized with `PipelineConfig`. Method `run(run_date: str, sector: Optional[str] = None) -> RunManifest`. Pipeline stages: (1) initialize RunContext + Snowflake session, (2) run market context agent, (3) run sector scores agent (parallel across sectors via ThreadPoolExecutor), (4) run stock detail agent, (5) run news catalyst agent, (6) run opportunity scorer, (7) run sector ranker agent per sector, (8) run shortlist selector, (9) run thesis writer for shortlisted stocks, (10) run risk assessor for shortlisted stocks, (11) run report builder, (12) write manifest. If `sector` is specified, only stages relevant to that sector execute. Non-critical agent failures (thesis, risk, report) produce warnings but don't halt the pipeline. Critical agent failures (data collection, scoring) halt the pipeline.
  - Key files: `src/agents/core/orchestrator.py`
  - Acceptance criteria: Pipeline runs end-to-end with mock agents (no real LLM/Snowflake). Pipeline halts on critical agent failure. Pipeline continues on non-critical agent failure. Manifest captures all results. Sector-only mode skips irrelevant stages. Unit test uses mock agents to verify orchestration logic.

---

## Phase 2 — Data Collection & Context Agents

- [ ] **Build market context agent**
  - Scope: Create `src/agents/collectors/__init__.py` and `src/agents/collectors/market_context_agent.py`. Class `MarketContextAgent(BaseAgent)`. In `run()`: (1) query `read_price_performance(date)` for all tickers, compute avg_daily_return, breadth (% positive rolling_30d_return), avg_volatility, avg_drawdown; (2) query `read_industry_scores(date)` grouped by sector, compute per-sector avg composite_score_equal; (3) call LLM with computed stats to generate a 3-5 sentence `market_summary` describing market regime (bullish/bearish/neutral, high/low volatility, sector rotation themes). Store result in `context.shared_data["market_context"]` as `MarketContext` schema.
  - Key files: `src/agents/collectors/market_context_agent.py`
  - Acceptance criteria: Agent returns `MarketContext` with all numeric fields populated and a non-empty market_summary. Sector scores dict has 11 GICS sectors. Integration test with Snowflake confirms real data flows through.

- [ ] **Build sector scores agent**
  - Scope: Create `src/agents/collectors/sector_scores_agent.py`. Class `SectorScoresAgent(BaseAgent)`. In `run()`: for each sector in the universe (from `read_sector_list()`), query `read_industry_scores(date, sector)`, compute avg/median/std composite_score_equal, identify top 5 and bottom 5 tickers by score. Optionally call LLM for a 2-sentence sector summary. Store results in `context.shared_data["sector_contexts"]` as `dict[str, SectorContext]`. Runs in parallel across sectors via the orchestrator's thread pool.
  - Key files: `src/agents/collectors/sector_scores_agent.py`
  - Acceptance criteria: Agent returns `SectorContext` for every sector present in the data. Top/bottom performers are correctly ordered. Integration test verifies at least 8 sectors return data.

- [ ] **Build stock detail agent**
  - Scope: Create `src/agents/collectors/stock_detail_agent.py`. Class `StockDetailAgent(BaseAgent)`. In `run()`: reads the full universe of tickers from `dim_sp500_companies_current` (via `read_industry_scores`). For each ticker, reads all 5 marts and assembles a `StockCandidate` Pydantic object with all score components + price performance metrics. Handles NULL fundamentals gracefully (scores may be None for stocks without fiscal year data). Store results in `context.shared_data["candidates"]` as `list[StockCandidate]`.
  - Key files: `src/agents/collectors/stock_detail_agent.py`
  - Acceptance criteria: Agent returns 400+ `StockCandidate` objects (some tickers may lack data). Each candidate has non-null technical_score and sector. Candidates with NULL fundamentals have `fundamental_score=None`. Integration test confirms assembly for 3 known tickers (AAPL, MSFT, NVDA).

- [ ] **Build news catalyst agent**
  - Scope: Create `src/agents/collectors/news_catalyst_agent.py`. Class `NewsCatalystAgent(BaseAgent)`. In `run()`: for shortlisted candidates only (or top N by pre-score, configurable, default: top 50), read recent news via `read_recent_news(session, tickers, lookback_days=7)`. Group articles by ticker. For each ticker with articles, call LLM with article titles+descriptions to extract: (a) list of catalysts (earnings, product launch, M&A, management, regulatory, macro), (b) sentiment classification (positive/negative/neutral), (c) confidence (high/medium/low). Store in `context.shared_data["catalysts"]` as `dict[str, dict]`. Tickers without news get empty catalyst lists.
  - Key files: `src/agents/collectors/news_catalyst_agent.py`
  - Acceptance criteria: Agent returns catalyst data for tickers with recent news. LLM output parses into expected structure. Tickers without news return empty lists (not errors). Integration test with mock LLM confirms extraction logic.

---

## Phase 3 — Scoring, Ranking & Shortlisting

- [ ] **Build opportunity scorer**
  - Scope: Create `src/agents/analysts/__init__.py` and `src/agents/analysts/opportunity_scorer.py`. Class `OpportunityScorer(BaseAgent)`. In `run()`: reads `candidates` and `catalysts` from shared_data. Computes `opportunity_score` (0-100) for each candidate using configurable weights from `pipeline_config.yaml` (defaults: technical_momentum=25, fundamental_quality=20, price_trajectory=20, catalyst_strength=20, sector_favorability=15). Technical momentum: maps technical_score (0-100) directly. Fundamental quality: maps fundamental_score (0-100), default 50 if None. Price trajectory: composite of rolling_30d_return (positive = higher) + low volatility bonus + low drawdown bonus, normalized to 0-100. Catalyst strength: 0 if no catalysts, scaled by count × sentiment (positive=1, neutral=0.5, negative=-0.5), capped 0-100. Sector favorability: sector's avg_composite_score relative to overall mean, normalized 0-100. Final score = weighted sum. Updates `opportunity_score` on each `StockCandidate`. Deterministic given same inputs.
  - Key files: `src/agents/analysts/opportunity_scorer.py`
  - Acceptance criteria: All candidates receive an `opportunity_score` between 0-100. Score is reproducible (same inputs → same output). Factor decomposition is available per candidate. Unit test with fixed inputs produces expected scores. Edge cases: all-null fundamentals, no catalysts, extreme returns.

- [ ] **Build sector ranker agent**
  - Scope: Create `src/agents/analysts/sector_ranker_agent.py`. Class `SectorRankerAgent(BaseAgent)`. In `run()`: groups candidates by sector, sorts by opportunity_score descending. For top 5 per sector, calls LLM with the stock's full profile + sector context to generate a 2-3 sentence rationale explaining why this stock ranks where it does. Flags anomalies: stocks with high opportunity_score but deteriorating momentum (negative rolling_30d_return), or low score but strong positive catalyst. Stores ranked lists + rationale in `context.shared_data["sector_rankings"]` as `dict[str, list[dict]]`.
  - Key files: `src/agents/analysts/sector_ranker_agent.py`
  - Acceptance criteria: Every sector has a ranked list. Top 5 per sector have LLM-generated rationales. Anomalies are flagged when present. Integration test with mock LLM verifies ranking and rationale generation.

- [ ] **Build shortlist selector**
  - Scope: Create `src/agents/analysts/shortlist_selector.py`. Class `ShortlistSelector(BaseAgent)`. In `run()`: applies configurable filters from `pipeline_config.yaml`: (1) minimum opportunity_score (default: 65), (2) maximum drawdown threshold (default: -20%, exclude deeper drawdowns), (3) maximum per-sector count (default: 3), (4) maximum total shortlist size (default: 15). Selection algorithm: sort all passing candidates by opportunity_score descending, take top N per sector, then take overall top N. Deterministic. Stores result in `context.shared_data["shortlist"]` as `list[StockCandidate]`.
  - Key files: `src/agents/analysts/shortlist_selector.py`
  - Acceptance criteria: Shortlist size is between 0 and max_shortlist_size. No sector exceeds max_per_sector. All stocks in shortlist pass minimum score and drawdown thresholds. Deterministic: same inputs → same shortlist. Unit test with 20 mock candidates verifies correct filtering and ordering.

---

## Phase 4 — Thesis Generation & Risk Assessment

- [ ] **Create disclaimers configuration**
  - Scope: Create `src/agents/config/disclaimers.yaml` with: `report_disclaimer` (2-3 sentences: research/educational purposes only, not financial advice, past performance not indicative), `scope_statement` ("30-day opportunity discovery based on quantitative and qualitative signals"), `methodology_note` (brief description of scoring approach). Create loader function in `config_loader.py`: `load_disclaimers() -> dict[str, str]`.
  - Key files: `src/agents/config/disclaimers.yaml`, `src/agents/config/config_loader.py`
  - Acceptance criteria: Disclaimers load from YAML. All 3 fields are present and non-empty. Unit test verifies loading.

- [ ] **Build thesis writer agent**
  - Scope: Create `src/agents/analysts/thesis_writer_agent.py`. Class `ThesisWriterAgent(BaseAgent)`. In `run()`: for each stock in `shared_data["shortlist"]`, calls LLM (claude-opus-4-6 by default, configurable) with a structured prompt including: full StockCandidate data, SectorContext for that stock's sector, MarketContext, catalyst data, sector ranking rationale. Prompt template requests JSON output matching `OpportunityThesis` schema: opportunity_summary (2-3 sentences), thirty_day_thesis (1 paragraph), key_catalysts (3-5 bullets), supporting_signals (3-5 bullets), entry_considerations (1-2 sentences). Uses `llm_client.generate_structured()` for Pydantic parsing. Stores in `context.shared_data["theses"]` as `dict[str, OpportunityThesis]` keyed by ticker.
  - Key files: `src/agents/analysts/thesis_writer_agent.py`
  - Acceptance criteria: Each shortlisted stock gets a complete `OpportunityThesis`. All fields are non-empty strings or non-empty lists. LLM is called with full context (no missing data in prompt). Integration test with real LLM generates thesis for 1 stock. Unit test with mock LLM verifies prompt construction and response parsing.

- [ ] **Build risk assessor agent**
  - Scope: Create `src/agents/analysts/risk_assessor_agent.py`. Class `RiskAssessorAgent(BaseAgent)`. In `run()`: for each stock in shortlist, calls LLM with the stock's thesis + full profile data. Uses contrarian prompting: system prompt explicitly instructs LLM to "argue against the investment thesis" and "identify what could go wrong." Extracts: key_risks (3-5 bullets), assumptions (3-5 bullets), downside_scenario (1-2 sentences), risk_rating (Low/Medium/High). Merges risk data into the existing `OpportunityThesis` objects in `shared_data["theses"]`. Uses claude-sonnet-4-6 (cheaper, risk assessment doesn't need opus quality).
  - Key files: `src/agents/analysts/risk_assessor_agent.py`
  - Acceptance criteria: Each shortlisted stock's thesis has populated risk fields. Risk ratings are valid (Low/Medium/High). Contrarian perspective is evident (risks challenge the thesis, not repeat it). Unit test with mock LLM verifies contrarian prompting approach.

---

## Phase 5 — PDF Report Generation

- [ ] **Add PDF generation dependencies**
  - Scope: Add `fpdf2` and `matplotlib` to `requirements.txt`. These are needed for PDF rendering and chart generation respectively. `fpdf2` is a pure-Python PDF library with no system dependencies. `matplotlib` enables static chart images (sector heatmaps, score distributions) embedded as PNGs in the PDF.
  - Key files: `requirements.txt`
  - Acceptance criteria: `pip install -r requirements.txt` installs both. `from fpdf import FPDF` and `import matplotlib` succeed.

- [ ] **Build PDF engine (base layout and components)**
  - Scope: Create `src/agents/reports/__init__.py` and `src/agents/reports/pdf_engine.py`. Class `PDFEngine` extending `fpdf.FPDF`. Configures: A4 landscape (for wide tables) or portrait (configurable), 10pt body font, consistent margins. Reusable methods: `add_title_page(title, subtitle, date)`, `add_section_header(text)`, `add_paragraph(text)`, `add_bullet_list(items: list[str])`, `add_score_table(headers, rows)` (colored cells: green >70, yellow 40-70, red <40), `add_image(path, width)`, `add_page_footer(disclaimer_text)` (page number + short disclaimer on every page), `add_disclaimer_page(full_disclaimer)`. Define color palette constants for consistent branding.
  - Key files: `src/agents/reports/pdf_engine.py`
  - Acceptance criteria: `PDFEngine` can create a multi-page PDF with title, sections, tables, bullets, and footer. PDF opens correctly in standard readers. Score table colors render correctly. Unit test generates a sample PDF and verifies file size > 1KB and page count >= 2.

- [ ] **Build chart generation utilities**
  - Scope: Create `src/agents/reports/charts.py`. Functions: `generate_sector_heatmap(sector_scores: dict[str, float], output_path: Path)` (horizontal bar chart, sectors sorted by score, colored green→yellow→red), `generate_score_distribution(scores: list[float], output_path: Path)` (histogram of opportunity scores, vertical line at shortlist threshold), `generate_factor_breakdown(candidate: StockCandidate, output_path: Path)` (stacked horizontal bar showing technical/fundamental/catalyst/price/sector factor contributions). All functions save PNG to specified path. Uses matplotlib with non-interactive backend (`Agg`). Charts are clean, minimal, with data labels.
  - Key files: `src/agents/reports/charts.py`
  - Acceptance criteria: Each chart function produces a valid PNG file > 5KB. Charts display correct data labels. Non-interactive backend works without display server. Unit test generates all 3 chart types from mock data.

- [ ] **Build sector report template**
  - Scope: Create `src/agents/reports/sector_report.py`. Function `generate_sector_pdf(sector: str, sector_context: SectorContext, candidates: list[StockCandidate], theses: dict[str, OpportunityThesis], market_context: MarketContext, disclaimers: dict, run_date: str, output_path: Path)`. PDF structure: (1) title page with sector name + date, (2) sector overview (avg scores, market context), (3) ranked stock table (top 10 by opportunity_score with score components), (4) for each shortlisted stock in this sector: 1-page detail with thesis, supporting signals, risks, factor breakdown chart, (5) disclaimer page. Writes PDF to `output/{date}/sectors/{sector-slug}.pdf`.
  - Key files: `src/agents/reports/sector_report.py`
  - Acceptance criteria: Generates a multi-page PDF for a sector with at least 1 shortlisted stock. PDF contains correct stock data, thesis text, and risk assessment. Charts are embedded. Disclaimer is present. Smoke test generates PDF from mock data.

- [ ] **Build aggregate report template**
  - Scope: Create `src/agents/reports/aggregate_report.py`. Function `generate_aggregate_pdf(market_context: MarketContext, sector_contexts: dict[str, SectorContext], shortlist: list[StockCandidate], theses: dict[str, OpportunityThesis], disclaimers: dict, config: PipelineConfig, run_date: str, output_path: Path)`. PDF structure: (1) title page "Daily Stock Opportunities — {date}", (2) executive summary (market context + key themes from LLM, 1 page), (3) sector heatmap chart, (4) opportunities summary table (all shortlisted stocks, ranked, with scores), (5) for each shortlisted stock: 1-page detail (thesis, catalysts, risks, factor breakdown chart), (6) methodology appendix (scoring weights, data sources, universe definition), (7) disclaimer page. Writes to `output/{date}/aggregate/daily_opportunities_{date}.pdf`.
  - Key files: `src/agents/reports/aggregate_report.py`
  - Acceptance criteria: Generates a complete PDF with all sections. Table of shortlisted stocks is sorted by opportunity_score. Each stock page has thesis + risks. Methodology appendix reflects actual config weights. PDF is > 10 pages for a 10-stock shortlist. Smoke test generates PDF from mock data.

- [ ] **Build report orchestration layer**
  - Scope: Create `src/agents/reports/report_builder.py`. Class `ReportBuilder(BaseAgent)`. In `run()`: (1) generate sector PDFs in parallel (ThreadPoolExecutor) for each sector that has shortlisted stocks, (2) generate aggregate PDF, (3) validate all PDFs exist and are > 0 bytes, (4) log file paths and sizes. Returns list of generated PDF paths in `AgentOutput.data["pdf_paths"]`. Handles chart cleanup (deletes temporary PNG files after embedding).
  - Key files: `src/agents/reports/report_builder.py`
  - Acceptance criteria: All expected PDFs are generated. No temporary PNG files remain after run. Agent output contains correct PDF paths. Failed PDF generation for one sector doesn't block others. Integration test generates full report set from mock data.

---

## Phase 6 — Pipeline Orchestration & Daily Execution

- [ ] **Build CLI entry point**
  - Scope: Create `src/agents/cli.py` with `argparse`-based CLI. Commands: `python -m src.agents.cli run --date YYYY-MM-DD` (specific date), `python -m src.agents.cli run` (defaults to today), `python -m src.agents.cli run --sector "Information Technology"` (single sector), `python -m src.agents.cli run --dry-run` (data collection only, no LLM calls, no PDF — validates data availability). Exit codes: 0=success, 1=partial failure, 2=fatal failure. Initializes logging, loads config, creates `DailyPipeline`, calls `run()`, prints summary to stdout (shortlist tickers, PDF paths, run duration).
  - Key files: `src/agents/cli.py`
  - Acceptance criteria: `python -m src.agents.cli run --dry-run` completes without LLM calls and reports data availability. Full run produces PDFs in `output/{date}/`. `--sector` flag limits execution to one sector. `--date` accepts valid date strings. Invalid arguments produce helpful error messages.

- [ ] **Build file-based caching layer**
  - Scope: Create `src/agents/core/cache.py`. Class `RunCache` initialized with `output/{date}/.cache/`. Methods: `get(key: str) -> Optional[dict]` (reads JSON from `.cache/{key}.json`), `set(key: str, data: dict)` (writes JSON), `has(key: str) -> bool`. Used by agents to cache: Snowflake query results (key = query hash), LLM responses (key = prompt hash). Cache is date-scoped: only valid for the current run date. `DailyPipeline` passes `RunCache` instance via `RunContext`. Agents check cache before making expensive calls. `--no-cache` CLI flag disables caching.
  - Key files: `src/agents/core/cache.py`
  - Acceptance criteria: Cache writes and reads JSON files correctly. Re-running pipeline with cache hits skips Snowflake queries and LLM calls. `--no-cache` forces fresh execution. Cache files are isolated per date. Unit test verifies read/write/miss behavior.

- [ ] **Build Airflow DAG for agent pipeline**
  - Scope: Create `dags/agents/__init__.py` and `dags/agents/stock_opportunity_agent_dag.py`. Daily-scheduled DAG (`@daily`) that runs after `stock_screening_dbt_daily_dag` completes. Uses `ExternalTaskSensor` on `stock_screening_dbt_daily_dag` (following the pattern in `dags/dbt/stock_screening_dbt_daily_dag.py`). Single `PythonOperator` calling the pipeline entry point with `run_date={{ ds }}`. Imports from `airflow.providers.standard.*` (NEVER `airflow.operators.*`). DAG ID: `stock_opportunity_agent_daily`. Tags: `["agents", "reporting"]`. Timeout: 30 minutes. Retries: 1 with 5-minute delay.
  - Key files: `dags/agents/stock_opportunity_agent_dag.py`
  - Acceptance criteria: DAG parses without errors (`astro dev parse`). ExternalTaskSensor correctly references dbt DAG. PythonOperator calls pipeline with Airflow execution date. DAG uses correct import paths. Integration with existing DAG dependency graph is correct.

- [ ] **Add pipeline error handling and agent-level retries**
  - Scope: Update `src/agents/core/base_agent.py` to add retry support: `max_retries` class attribute (default: 2), `execute()` retries `run()` on transient failures (connection errors, API rate limits) with exponential backoff. Update `src/agents/core/orchestrator.py` to categorize agents as critical vs non-critical: critical agents (market_context, sector_scores, stock_detail, opportunity_scorer, shortlist_selector) halt pipeline on failure; non-critical agents (news_catalyst, sector_ranker, thesis_writer, risk_assessor, report_builder) log warnings and continue with degraded output. Failed thesis → PDF shows "Analysis unavailable for this stock." Failed risk → PDF shows "Risk assessment pending."
  - Key files: `src/agents/core/base_agent.py`, `src/agents/core/orchestrator.py`
  - Acceptance criteria: Transient failures in agents trigger retries (verified via mock). Critical agent failure halts pipeline (exit code 2). Non-critical agent failure produces degraded output (exit code 1). PDF handles missing thesis/risk gracefully. Unit test simulates failures at each tier.

---

## Phase 7 — Testing & Quality Assurance

- [ ] **Add unit tests for scoring and selection logic**
  - Scope: Create `tests/agents/__init__.py`, `tests/agents/test_opportunity_scorer.py` (test score calculation with known inputs: perfect scores, zero scores, missing fundamentals, no catalysts, extreme returns; verify weighted sum correctness and 0-100 bounds), `tests/agents/test_shortlist_selector.py` (test filtering: below threshold excluded, per-sector cap enforced, total cap enforced, empty universe returns empty list, all below threshold returns empty list), `tests/agents/test_config_loader.py` (valid YAML loads, missing required fields raise error, defaults applied for optional fields), `tests/agents/test_schemas.py` (all Pydantic models validate with good data, reject bad data).
  - Key files: `tests/agents/test_opportunity_scorer.py`, `tests/agents/test_shortlist_selector.py`, `tests/agents/test_config_loader.py`, `tests/agents/test_schemas.py`
  - Acceptance criteria: All unit tests pass. Scoring tests verify exact numeric outputs for deterministic inputs. Selection tests verify all filtering rules. Config tests cover edge cases. `pytest tests/agents/ -v` runs clean.

- [ ] **Add integration tests for data access and LLM client**
  - Scope: Create `tests/agents/test_snowflake_reader.py` (each reader function returns expected columns from Snowflake; requires `SNOWFLAKE_*` env vars), `tests/agents/test_llm_client.py` (generate() returns non-empty string; generate_structured() returns valid Pydantic model; requires `ANTHROPIC_API_KEY`). Mark integration tests with `@pytest.mark.integration` so they can be skipped in CI without credentials.
  - Key files: `tests/agents/test_snowflake_reader.py`, `tests/agents/test_llm_client.py`
  - Acceptance criteria: Integration tests pass when env vars are set. Tests are skipped (not failed) when env vars are missing. Data reader tests verify column names match dbt model outputs.

- [ ] **Add PDF smoke test and end-to-end pipeline test**
  - Scope: Create `tests/agents/test_pdf_generation.py` (generates sector PDF and aggregate PDF from mock data, verifies: file exists, size > 1KB, no non-PDF files created), `tests/agents/test_pipeline_smoke.py` (runs full pipeline with mock LLM client on a 5-ticker mini universe, verifies: manifest.json created, at least 1 sector PDF created, aggregate PDF created, exit code 0). Mock LLM returns canned JSON responses matching schema.
  - Key files: `tests/agents/test_pdf_generation.py`, `tests/agents/test_pipeline_smoke.py`
  - Acceptance criteria: PDF smoke test produces valid PDF files. Pipeline smoke test completes end-to-end without real LLM calls. All output artifacts are present. Tests run in < 30 seconds.

---

## Phase 8 — Documentation & Index Updates

- [ ] **Update README.md with agent pipeline documentation**
  - Scope: Add a new section to `README.md` covering: (1) Agent pipeline overview (what it does, daily schedule), (2) How to run (`python -m src.agents.cli run`), (3) Configuration (`pipeline_config.yaml` parameters), (4) Output structure (`output/{date}/` layout), (5) How to add a new agent or scoring factor (extend BaseAgent, register in orchestrator), (6) Environment variables (ANTHROPIC_API_KEY), (7) Testing (`pytest tests/agents/`).
  - Key files: `README.md`
  - Acceptance criteria: A new developer can run the pipeline by following README instructions. All new env vars are documented. Output examples are described.

- [ ] **Update project indexes and CLAUDE.md**
  - Scope: Update `general_index.md` to include all new files under `src/agents/`, `dags/agents/`, `tests/agents/`. Update `PROJECT_STRUCTURE.md` to include the agent layer directory tree and updated architecture diagram. Update `CLAUDE.md` to reference the agent layer (add agent-related rules). Update `detailed_index.md` if new data contracts are introduced.
  - Key files: `general_index.md`, `PROJECT_STRUCTURE.md`, `CLAUDE.md`, `detailed_index.md`
  - Acceptance criteria: Every new file appears in `general_index.md`. Architecture diagram in `PROJECT_STRUCTURE.md` includes the agent layer. `CLAUDE.md` routes to agent rules. All indexes are accurate and complete.
