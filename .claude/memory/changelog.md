# Changelog

Chronological ledger of autonomous actions. Document BEFORE committing to Git.

---

## Template

```
### YYYY-MM-DD — {Short Title}

**What changed:**
- {File path}: {Description of change}

**Why:**
- {Motivation / user request / bug discovered}

**Expected downstream impacts:**
- {List affected consumers: MCP, Superset, downstream models, or "None"}

**Validation evidence:**
- {Tests run and results}
- {Row count comparison if applicable}
- {Score distribution check if applicable}

**Git commit:** {commit hash after committing}
```

---

## Entries

### 2026-03-03 — Phase 0.5 Pipeline Correction & Expansion

**What changed:**
- `src/api_clients/fmp_client.py`: Renamed duplicate `fetch_news` methods to `fetch_fmp_articles` and `fetch_general_news`; added 4 new methods (fetch_press_releases, fetch_stock_news, fetch_insider_trades_latest, fetch_insider_trades_search); removed hardcoded API key from comment; removed non-existent endpoints (insider-trading per-ticker, institutional-holder per-ticker)
- `src/api_clients/polygon_client.py`: Added `fetch_stock_snapshot` method
- `src/jobs/ingest_fmp_news.py`: Renamed to `ingest_fmp_articles.py`, calls `fetch_fmp_articles`
- `src/jobs/ingest_fmp_global_news.py`: Renamed to `ingest_fmp_general_news.py`, calls `fetch_general_news`
- `src/jobs/ingest_fmp_insider_trades.py`: Complete rewrite for paginated global feed (`/stable/insider-trading/latest`)
- `src/jobs/ingest_fmp_dividends.py`: Removed 2 debug print statements
- `dags/etl/fmp_news_daily_dag.py`: Renamed to `fmp_articles_daily_dag.py`
- Created 4 new daily job files: press releases, stock news, insider trades search, stock snapshot
- Created 8 new backfill job files: articles, general news, press releases, stock news, dividends, key metrics, insider trades, insider trades search
- Created 8 new daily DAGs and 8 new backfill DAGs

**Why:**
- Phase 0.5 original implementation contained incorrect API endpoints (2 non-existent), duplicate method names (1 shadowed), broken ticker parsing logic, hardcoded API key in comment, debug prints in production code

**Expected downstream impacts:**
- `sp500_fmp_news` table now ingests FMP articles (was incorrectly ingesting general news due to method shadowing)
- `sp500_insider_trades` now populated from paginated feed (was always empty due to non-existent endpoint)
- 4 new Snowflake tables on first job run: sp500_fmp_press_releases, sp500_fmp_stock_news, sp500_insider_trades_search, sp500_stock_snapshot

**Validation evidence:**
- `astro dev parse`: all ETL DAGs parse without import errors

**Git commit:** pending

---

### 2026-03-03 — FMP News Pipeline Fixes & Unfiltering

**What changed:**
- `src/api_clients/fmp_client.py`: Fixed NoneType crash in `fetch_general_news`, `fetch_press_releases`, `fetch_stock_news` — `(article.get("symbol") or "").strip()` instead of `article.get("symbol", "").strip()` (JSON null returns None, not default); fixed `fetch_general_news` endpoint URL from `/stable/general-latest` to `/stable/news/general-latest`; added `start_date` parameter to all 4 news methods for backfill support; fixed `fetch_press_releases` to use `publishedDate` field for dates; removed S&P 500 ticker filtering from `fetch_general_news` and `fetch_press_releases` (now unfiltered global feeds)
- `src/api_clients/fmp_client.py`: Fixed `fetch_earnings_calendar` endpoint from `/stable/earning-calendar` to `/stable/earnings-calendar`
- `src/jobs/ingest_fmp_general_news.py` + `_backfill.py`: Removed S&P 500 dependency (no get_sp500_tickers, no LOOKUP_TABLE); changed DDL column from `ticker` to `symbol`; changed PK from `(article_url, ticker)` to `(article_url)`
- `src/jobs/ingest_fmp_press_releases.py` + `_backfill.py`: Same unfiltering changes as general news
- All 4 backfill news jobs now pass `start_date` to API client for proper date-range pagination
- `dags/etl/fmp_global_news_dag.py`: Removed ExternalTaskSensor on sp500_lookup
- `dags/etl/fmp_press_releases_dag.py`: Removed ExternalTaskSensor on sp500_lookup

**Why:**
- FMP news methods crashed on articles with `null` symbol (NoneType.strip() error)
- General news endpoint URL was wrong (missing `/news/` segment)
- Backfill jobs only fetched 1 day of data instead of 5 years (date filtering logic was wrong)
- General news and press releases are not stock-specific, so S&P 500 filtering removed most results
- Earnings calendar returned 404 due to endpoint URL typo

**Expected downstream impacts:**
- `sp500_fmp_general_news` and `sp500_fmp_press_releases` tables now use `symbol` column (not `ticker`) and `(article_url)` PK — tables must be recreated if previously populated
- General news and press releases DAGs now run independently of sp500_lookup
- Earnings calendar now fetches data successfully

**Git commit:** pending

---

### 2026-02-28 — Agentic Workspace Initialization

**What changed:**
- Created `PROJECT_STRUCTURE.md` — high-level architecture map
- Created `general_index.md` — exhaustive file-by-file index
- Created `detailed_index.md` — deep structural index with grains, dependencies, scoring logic
- Created `.claude/rules/` — 7 rule files (architecture, contracts, performance, incremental, quality, security, testing)
- Created `.claude/memory/` — MEMORY.md (operational learnings), active_plan.md (template), changelog.md (this file)
- Created `CLAUDE.md` — master routing file with progressive disclosure
- Created `AGENTS.md` — cross-tool mirror of CLAUDE.md
- Updated `.gitignore` — added agentic workspace context file exclusions

**Why:**
- Initialize comprehensive agentic workspace context for autonomous analytics development
- Eliminate future search latency via spatial indexing
- Prevent hallucination via grounded architectural rules
- Enable persistent state tracking across sessions

**Expected downstream impacts:**
- None (context files only, no code changes)

**Validation evidence:**
- All files created successfully
- No existing files were modified except .gitignore (append only)
- CLAUDE.md stays under 200-line target

**Git commit:** pending

---

*Add new entries above this line.*
