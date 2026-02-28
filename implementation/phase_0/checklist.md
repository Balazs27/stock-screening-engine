# Phase 0 — Implementation Checklist

Analysis performed: 2026-02-28
Verification method: live code reading + automated acceptance criteria tests

---

## Overall Status: IMPLEMENTED WITH ISSUES

All 4 features are structurally complete. All primary acceptance criteria pass. Three code-quality issues were found in Feature 01 and one behavioral edge case in Feature 03. No unit test files exist yet (deferred to Phase 7 per project plan).

---

## Feature 01 — Pipeline Configuration System

**Files:**
- [x] `src/agents/__init__.py` — exists, importable
- [x] `src/agents/config/__init__.py` — exists, importable
- [x] `src/agents/config/pipeline_config.yaml` — all 5 sections, correct defaults, inline comments
- [x] `src/agents/config/config_loader.py` — typed loader with validation

**Acceptance criteria:**
- [x] `load_config()` returns `PipelineConfig` with all correct defaults
- [x] `load_config()` with missing file raises `ConfigValidationError`
- [x] `load_config()` with invalid YAML syntax raises `ConfigValidationError`
- [x] `load_config()` with weight sum ≠ 1.0 raises `ConfigValidationError`
- [x] Partial YAML (only one section) applies defaults for all omitted fields
- [x] Empty YAML file loads with all defaults
- [x] `PIPELINE_SCORING_TECHNICAL_MOMENTUM` env var override works
- [x] All 5 scoring weights match spec: 0.25 / 0.20 / 0.20 / 0.20 / 0.15
- [x] `PyYAML` in `requirements.txt`
- [ ] Unit test file (`tests/agents/test_config_loader.py`) — **not created** (deferred to Phase 7)

**Issues found:**

| Severity | Location | Issue |
|----------|----------|-------|
| Minor | `config_loader.py:90` | `_coerce_value()` is **defined but never called** — dead code. Coercion is performed inline in `_build_dataclass()` instead. Should be removed or wired in. |
| Minor | `config_loader.py:149` | `field_types` variable assigned (`{f.name: f.type for f in fields(cls)}`) but **never read** — the loop uses `f.type` directly. Dead assignment. |
| Minor | `config_loader.py:151` | `import sys` is **inside `_build_dataclass()`** rather than at module top-level. Not a bug but violates PEP 8 and adds per-call import overhead. |

---

## Feature 02 — Anthropic SDK & Secret Management

**Files:**
- [x] `requirements.txt` — `anthropic` and `pydantic` added under `# Agent pipeline dependencies`
- [x] `.env.example` — `ANTHROPIC_API_KEY=your_anthropic_api_key` present
- [x] `.env.example` — `SNOWFLAKE_*` variables documented
- [x] `.gitignore` — `!.env.example` exception added; file is NOT gitignored

**Acceptance criteria:**
- [x] `anthropic 0.84.0` installs and imports cleanly
- [x] `pydantic 2.12.5` installs and imports cleanly (v2.x confirmed)
- [x] `ANTHROPIC_API_KEY` documented in `.env.example`
- [x] `.env.example` not gitignored (`git check-ignore` returns nothing)
- [x] No `.env` files read, modified, or committed
- [x] `pip check` — only pre-existing `fastapi/starlette` conflict; neither `anthropic` nor `pydantic` introduce new conflicts

**Issues found:** None.

---

## Feature 03 — Agent Data Access Layer (Snowflake Reader)

**Files:**
- [x] `src/agents/data/__init__.py` — exists, importable
- [x] `src/agents/data/snowflake_reader.py` — 7 reader functions + `get_session()`

**Acceptance criteria:**
- [x] All 7 reader functions + `get_session()` importable
- [x] `get_session()` wraps `get_snowflake_session()` from `src.loaders.snowflake_loader`
- [x] `_sanitize_tickers()` strips SQL injection chars (quotes, semicolons) while preserving `.` and `-` for tickers like `BRK.B`, `BF-B`
- [x] `_ticker_filter_clause(None)` and `_ticker_filter_clause([])` return empty string
- [x] All column names lowercased via `_lowercase_columns()`
- [x] `read_fundamental_scores` uses `QUALIFY ROW_NUMBER() OVER (PARTITION BY TICKER ORDER BY FISCAL_YEAR DESC) = 1` for latest year
- [x] `read_recent_news` selects only text columns, excludes VARIANT columns (`tickers`, `keywords`)
- [x] `read_recent_news` casts `lookback_days` to `int()` before SQL interpolation
- [x] `read_sector_list` queries `_DIM` schema, returns sorted distinct sector list
- [x] Fully-qualified 3-part table names (`DATABASE.SCHEMA.TABLE`) used throughout
- [ ] Integration test file (`tests/agents/test_snowflake_reader.py`) — **not created** (deferred to Phase 7)
- [ ] Live Snowflake integration verified — **cannot run without credentials in CI**

**Issues found:**

| Severity | Location | Issue |
|----------|----------|-------|
| Medium | `snowflake_reader.py:84` | `_ticker_filter_clause([])` returns `""` (no filter). If `read_recent_news(session, [])` is called with an empty list, the query returns **all news for the lookback window** across every ticker — potentially thousands of rows. The function should either guard against empty `tickers` with an early `return pd.DataFrame(columns=[...])` or raise `ValueError("tickers must be non-empty")`. The `tickers` parameter has no default (correctly required), but a caller passing `[]` gets unexpected behavior silently. |

---

## Feature 04 — Output Directory Conventions

**Files:**
- [x] `output/.gitkeep` — exists, tracked by git
- [x] `src/agents/core/__init__.py` — exists, importable
- [x] `src/agents/core/output_manager.py` — all 7 functions

**Acceptance criteria:**
- [x] `output/.gitkeep` tracked by git; `git check-ignore output/.gitkeep` returns nothing
- [x] `output/*` in `.gitignore`; `git check-ignore output/2026-02-28/test.pdf` returns match
- [x] `ensure_run_directory("2026-02-28")` creates `run/`, `sectors/`, `aggregate/`, `.cache/`
- [x] `ensure_run_directory()` is idempotent (second call does not error)
- [x] `get_sector_pdf_path("2026-02-28", "Information Technology")` → `.../sectors/information-technology.pdf`
- [x] `get_aggregate_pdf_path("2026-02-28")` → `.../aggregate/daily_opportunities_2026-02-28.pdf`
- [x] `get_manifest_path("2026-02-28")` → `.../manifest.json`
- [x] `get_log_path("2026-02-28")` → `.../pipeline.log`
- [x] `get_cache_dir("2026-02-28")` → `.../.cache/`
- [x] `slugify()` correct for all 11 GICS sectors
- [x] `ensure_run_directory("bad-date")` raises `ValueError`
- [x] `ensure_run_directory("2026-13-01")` raises `ValueError` (invalid calendar date)
- [x] `slugify("")` raises `ValueError`
- [x] `slugify("!!!")` raises `ValueError` (all-special-char input)
- [x] Agent `__pycache__/` entries in `.gitignore` (all 4: `agents/`, `config/`, `core/`, `data/`)
- [ ] Unit test file (`tests/agents/test_output_manager.py`) — **not created** (deferred to Phase 7)

**Issues found:** None.

---

## Issues Summary

| # | Severity | Feature | File | Description | Action Required |
|---|----------|---------|------|-------------|-----------------|
| 1 | Minor | 01 | `config_loader.py:90` | `_coerce_value()` defined but never called — dead code | Remove function or wire it into `_build_dataclass` |
| 2 | Minor | 01 | `config_loader.py:149` | `field_types` variable assigned but never read | Remove the dead assignment |
| 3 | Minor | 01 | `config_loader.py:151` | `import sys` inside a function body | Move to module-level imports |
| 4 | Medium | 03 | `snowflake_reader.py:84` | `read_recent_news(session, [])` silently returns all news (no ticker filter applied when list is empty) | Add guard: return empty DataFrame or raise ValueError if tickers list is empty |

---

## Missing Items (Not Blocking Phase 1)

These items appear in individual spec acceptance criteria but are explicitly out of scope for Phase 0 — they belong to Phase 7 (Testing & QA):

| Item | Spec Reference | Phase |
|------|---------------|-------|
| `tests/agents/test_config_loader.py` | Feature 01 acceptance criteria | Phase 7 |
| `tests/agents/test_snowflake_reader.py` | Feature 03 acceptance criteria | Phase 7 |
| `tests/agents/test_output_manager.py` | Feature 04 acceptance criteria | Phase 7 |

---

## Dependency Readiness for Phase 1

| Phase 1 Dependency | Status | Notes |
|--------------------|--------|-------|
| `src/agents/__init__.py` exists | ✅ | Required by base_agent, schemas, orchestrator |
| `src/agents/core/__init__.py` exists | ✅ | Required by all core modules |
| `PipelineConfig` loadable | ✅ | Required by orchestrator, base_agent |
| `anthropic` SDK installed | ✅ | Required by llm_client.py |
| `pydantic` v2 installed | ✅ | Required by schemas.py |
| `output_manager.py` path helpers | ✅ | Required by manifest.py, report_builder.py |
| Snowflake reader functions | ✅ | Required by all collector agents |
