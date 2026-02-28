# Infrastructure Readiness Report: AI Agent-Powered Stock Opportunity Discovery

> Generated: 2026-02-28
> Scope: Full audit of current data infrastructure vs. AI agent pipeline requirements

---

## Executive Summary

The current infrastructure is **70-75% ready** to support the AI agent pipeline. The foundational pillars — daily price data, technical indicators, 3-statement fundamentals, a full scoring/ranking mart layer, and a semantic layer — are production-grade and well-architected. However, several critical data gaps exist that would significantly limit the quality of AI-generated investment theses if left unaddressed. The most impactful gaps are: **no valuation data** (P/E, EV/EBITDA), **no earnings surprise/estimate data**, **no analyst consensus**, and **no sentiment scoring on existing news**. These gaps mean the AI agents would be generating "opportunity theses" without knowing if a stock is cheap or expensive, without knowing if it just beat or missed earnings, and without any forward-looking market expectations.

**Bottom line**: You can build the pipeline on the current infrastructure and get *functional* results. But to get the **best possible results**, 4-5 targeted data additions would transform the output quality from "interesting technical screen" to "actionable investment intelligence."

---

## Part 1: Current Infrastructure Audit

### What We Have (Strengths)

#### Data Sources (3 active)
| Source | Data Type | Frequency | Coverage | Quality |
|--------|-----------|-----------|----------|---------|
| Polygon.io | Prices, technicals, news | Daily | All S&P 500 | High — adjusted prices, 398-day history |
| FMP | 3-statement financials, news | Daily (annual data) | All S&P 500 | High — 45-60 fields per statement |
| Wikipedia | S&P 500 universe | Daily | Canonical membership | High — single source of truth |

#### Raw Tables (10 in Snowflake)
| Table | Grain | Volume | Refresh |
|-------|-------|--------|---------|
| `sp500_stock_prices` | (ticker, date) | ~500 rows/day | Daily |
| `sp500_rsi` | (ticker, date) | ~500 rows/day | Daily |
| `sp500_macd` | (ticker, date) | ~500 rows/day | Daily |
| `sp500_sma` | (ticker, date) | ~500 rows/day | Daily |
| `sp500_news` | (ticker, article_id, date) | ~2,000-5,000 rows/day | Daily |
| `sp500_income_statements` | (ticker, date, period) | ~2,500 total (500 × 5yr) | Daily (annual data) |
| `sp500_balance_sheets` | (ticker, date, period) | ~2,500 total | Daily (annual data) |
| `sp500_cash_flow_statements` | (ticker, date, period) | ~2,500 total | Daily (annual data) |
| `sp500_fmp_news` | (ticker, article_url, date) | Variable | Daily (experimental) |
| `sp500_tickers_lookup` | (ticker, date) | ~500 rows/day | Daily |

#### Mart Layer (5 analytics-ready tables)
| Mart | What It Provides | Score Range | Update Frequency |
|------|------------------|-------------|------------------|
| `mart_sp500_technical_scores` | Trend + Momentum + MACD + Price Action | 0-100 (4 components) | Daily |
| `mart_sp500_fundamental_scores` | Profitability + Growth + Health + Cash Quality | 0-100 (4 components) | Annual (full refresh) |
| `mart_sp500_composite_scores` | 3 blended variants (50/50, 60/40, 40/60) | 0-100 | Daily |
| `mart_sp500_industry_scores` | Composite + sector/industry metadata | 0-100 | Daily |
| `mart_sp500_price_performance` | Returns, volatility, drawdown, risk-adjusted | Raw metrics | Daily |

#### Operational Infrastructure
- **Airflow orchestration**: 9 daily DAGs + 4 backfill DAGs, dependency-gated via ExternalTaskSensors
- **dbt transformations**: 16 models (staging → intermediate → dimensions → marts), all tested
- **MCP semantic layer**: 5 models exposed with AI-friendly query patterns
- **Idempotent pipelines**: delete+insert everywhere, safe to re-run
- **Rate limiting**: Conservative (Polygon 0.8s/req, FMP 0.1s/req), no 429 risk

### What the AI Agent Pipeline Needs

Based on the project plan, here's what each agent requires:

| Agent | Primary Data Needed | Currently Available? |
|-------|--------------------|--------------------|
| **Market Context Agent** | Broad market returns, sector averages, volatility regime | YES — via `price_performance` + `industry_scores` |
| **Sector Scores Agent** | Per-sector composite scores, top/bottom stocks | YES — via `industry_scores` |
| **Stock Detail Agent** | Technical + fundamental + composite + returns per ticker | YES — via all 5 marts |
| **News Catalyst Agent** | Recent news articles for top ~50 candidates | PARTIAL — news exists but no sentiment scoring |
| **Opportunity Scorer** | 5-factor weighted score (technical, fundamental, price, catalyst, sector) | PARTIAL — 4 of 5 factors available; catalyst score requires LLM |
| **Thesis Writer Agent** | Full stock profile + market context + catalysts | PARTIAL — missing valuation context and earnings expectations |
| **Risk Assessor Agent** | Same as thesis writer + downside scenarios | PARTIAL — missing short interest, options-implied risk, analyst targets |

---

## Part 2: Critical Data Gaps

### Gap 1: No Valuation Data (CRITICAL)

**Impact: HIGH — This is the single biggest gap.**

The AI agents will generate "opportunity theses" for stocks without knowing whether they are cheap or expensive relative to earnings, cash flow, or book value. A stock can have a perfect technical score (100) and strong fundamentals (90) but be trading at 80x earnings — making it a terrible "opportunity" for a 30-day horizon.

**What's missing:**
- Price-to-Earnings ratio (P/E) — trailing and forward
- Price-to-Book ratio (P/B)
- Price-to-Sales ratio (P/S)
- EV/EBITDA
- PEG ratio (P/E divided by growth rate)
- Free Cash Flow Yield (FCF/Market Cap)
- Dividend Yield

**Why it matters for the pipeline:**
- The Thesis Writer cannot assess "is this stock attractively valued?" without P/E or EV/EBITDA
- The Risk Assessor cannot flag "this stock is priced for perfection" without valuation multiples
- The Opportunity Scorer has no "value" factor — it rewards momentum and quality but ignores price
- Sector comparisons are incomplete: "Technology has high scores" means nothing without knowing if Tech is trading at 30x or 50x earnings

**How to fix:**
- **Option A (Recommended)**: Add FMP `/v3/ratios/{ticker}` endpoint — returns P/E, P/B, P/S, EV/EBITDA, PEG, dividend yield, and 30+ other ratios in a single call. One new job, one new raw table, one new staging model.
- **Option B**: Compute P/E in dbt by joining `mart_sp500_technical_scores.close` (price) with `int_sp500_fundamentals.eps_diluted` (earnings) and `weighted_average_shares_out_diluted`. Works for trailing P/E but requires market cap for EV-based ratios, which we don't currently store.
- **Option C**: Add FMP `/v3/key-metrics/{ticker}` endpoint — returns market cap, enterprise value, and key ratios. Overlaps with Option A but is more focused.

**Recommendation**: Option A — FMP ratios endpoint. Single API call per ticker, returns everything needed. Estimated effort: 1 new API method + 1 job + 1 raw table + 1 staging view + 1 intermediate model + update to `mart_sp500_fundamental_scores` or a new `mart_sp500_valuation` table.

---

### Gap 2: No Earnings Surprise / Estimate Data (HIGH)

**Impact: HIGH — Earnings events are the #1 short-term catalyst for stock price moves.**

The pipeline plans to identify "30-day opportunities" but has no data on:
- When each company reports earnings next (earnings calendar)
- What analysts expect (consensus EPS estimate)
- Whether the company beat or missed last quarter (earnings surprise)
- How estimates have been revised recently (estimate revision momentum)

**Why it matters:**
- A stock reporting earnings in 5 days is a fundamentally different "opportunity" than one that reported 80 days ago
- Earnings surprises (beats/misses) are the strongest short-term catalysts — the News Catalyst Agent is trying to detect these from news articles, but structured data is far more reliable
- Estimate revision momentum (analysts raising/lowering estimates) is one of the most predictive signals for short-term returns
- The Thesis Writer needs to say "XYZ reports earnings on March 15, consensus expects $2.40 EPS" — without this data, the thesis is incomplete

**How to fix:**
- Add FMP `/v3/earnings-surprises/{ticker}` — returns actual vs estimated EPS, surprise %, for recent quarters
- Add FMP `/v3/analyst-estimates/{ticker}` — returns consensus EPS/revenue estimates by period
- Add FMP `/v4/earning-calendar` — returns upcoming earnings dates for all S&P 500 stocks

**Recommendation**: Add all three. The earnings calendar is especially critical — the pipeline should know which stocks are reporting within the 30-day opportunity window.

---

### Gap 3: No Analyst Consensus / Price Targets (MEDIUM-HIGH)

**Impact: MEDIUM-HIGH — Provides institutional signal and quantitative upside/downside framework.**

Wall Street analyst ratings and price targets provide:
- Consensus view (Buy/Hold/Sell distribution)
- Implied upside/downside (current price vs. median target)
- Rating momentum (upgrades vs. downgrades trend)

**Why it matters:**
- The Thesis Writer can reference "9 of 12 analysts rate this Buy with a median target of $180 (25% upside)"
- The Risk Assessor can flag "despite strong technicals, 4 analysts recently downgraded"
- Price targets provide a quantitative benchmark for the "30-day opportunity" claim
- Rating changes are strong catalysts that the News Catalyst Agent is trying to detect from articles — structured data is more reliable

**How to fix:**
- Add FMP `/v3/analyst-stock-recommendations/{ticker}` — returns analyst firm, rating, price target
- Add FMP `/v4/upgrades-downgrades-consensus` — returns aggregate consensus

**Recommendation**: Add the consensus endpoint. Individual analyst recommendations are nice-to-have but consensus is what matters for the scoring model.

---

### Gap 4: No Sentiment Scoring on Existing News (MEDIUM)

**Impact: MEDIUM — We already ingest news; we just don't analyze it pre-LLM.**

The pipeline ingests ~2,000-5,000 news articles per day from Polygon (10 per ticker). These articles have `title`, `description`, `keywords`, and `published_utc`. However:
- No pre-computed sentiment score exists
- No article categorization (earnings, product, M&A, regulatory, etc.)
- The News Catalyst Agent must process raw text for every candidate

**Current plan**: The News Catalyst Agent calls Claude to extract catalysts from raw news text. This works but is:
- **Expensive**: LLM calls for ~50 tickers × ~10 articles = 500 LLM calls per run just for catalyst extraction
- **Slow**: Each call takes 2-5 seconds, even with parallelism
- **Redundant**: Basic sentiment (positive/negative) could be pre-computed at ingestion time

**Why it matters:**
- Pre-computed sentiment scores would allow the Opportunity Scorer to include a "news sentiment" factor without LLM calls
- Article categorization (earnings, product launch, M&A, etc.) would let the catalyst agent focus on the most relevant articles
- Polygon provides `keywords` in their news response — these are already ingested but not used for scoring

**How to fix:**
- **Option A (Lightweight)**: Use the existing `keywords` VARIANT field from Polygon news to create a rule-based categorization in dbt (keywords containing "earnings", "revenue", "beat" → earnings category; "acquisition", "merger" → M&A category; etc.)
- **Option B (LLM-based)**: Add a pre-processing step in the pipeline that scores news sentiment via a cheap model (Haiku) at ingestion time and stores the score
- **Option C (No change)**: Accept the cost of real-time LLM analysis in the catalyst agent — the current plan already accounts for this

**Recommendation**: Option A as a quick win (keyword-based categorization in dbt), with Option C as the primary approach. The LLM-based catalyst extraction in the pipeline is actually the right approach for nuanced analysis — but pre-categorization reduces the number of articles the LLM needs to process.

---

### Gap 5: No Insider Trading Data (MEDIUM)

**Impact: MEDIUM — Strong contrarian signal, especially for short-term opportunities.**

Insider buying (executives purchasing their own stock with personal money) is one of the strongest bullish signals available. Insider selling is less informative (could be tax/diversification) but clustered selling is bearish.

**Why it matters:**
- "CEO bought $2M of stock last week" is a powerful catalyst for the thesis
- Insider buying patterns are predictive of 30-60 day returns (academic literature supports this)
- The Risk Assessor could flag "insiders have been net sellers for 6 months" as a risk

**How to fix:**
- Add FMP `/v4/insider-trading?symbol={ticker}` — returns transaction date, insider name, title, type (buy/sell), shares, price
- Aggregate into: net insider buying/selling over 30/90 days

**Recommendation**: Nice-to-have for V1, should-have for V2. Adds strong signal for thesis quality but can be deferred without breaking the pipeline.

---

### Gap 6: No Macroeconomic Context (LOW-MEDIUM)

**Impact: LOW-MEDIUM — The Market Context Agent can partially compensate via LLM knowledge.**

The pipeline has no data on:
- Federal Reserve interest rates / policy direction
- Treasury yield curve (2Y/10Y spread)
- Inflation metrics (CPI, PCE)
- Employment data
- GDP growth
- VIX (volatility index)

**Why it matters:**
- Market regime classification ("risk-on" vs "risk-off") is hard without macro data
- Sector rotation is driven by macro factors (rising rates → banks outperform, falling rates → tech outperforms)
- The LLM has training knowledge about macro relationships but not real-time macro data

**Mitigation:**
- The Market Context Agent can infer macro regime from broad market behavior (avg returns, volatility, sector rotation patterns) — this is what the current plan does
- Claude's training data includes macro-market relationships, so the LLM can reason about "if volatility is high and financials are outperforming, this suggests rising rate expectations"
- Real-time macro data (FRED API, Treasury.gov) could be added but is out of scope for the Polygon/FMP API tier

**Recommendation**: Defer to V2. The Market Context Agent's approach of inferring regime from market data + LLM reasoning is reasonable for V1. Macro data enrichment would be a Phase 9+ enhancement.

---

## Part 3: Gap Prioritization Matrix

| Gap | Impact on Output Quality | Implementation Effort | Data Source | Priority |
|-----|--------------------------|----------------------|-------------|----------|
| **Valuation ratios** (P/E, EV/EBITDA, etc.) | Critical — can't assess if stock is cheap/expensive | Medium (1 new API method + dbt model) | FMP `/v3/ratios/` or `/v3/key-metrics/` | **P0 — Must have** |
| **Earnings surprises & calendar** | High — #1 short-term catalyst | Medium (2-3 new endpoints + models) | FMP `/v3/earnings-surprises/`, `/v4/earning-calendar` | **P0 — Must have** |
| **Analyst consensus & targets** | Medium-High — institutional signal + upside quantification | Low (1 new endpoint + model) | FMP `/v4/upgrades-downgrades-consensus` | **P1 — Should have** |
| **News categorization** | Medium — reduces LLM cost, improves catalyst detection | Low (dbt model using existing keywords) | Already ingested (Polygon news keywords) | **P1 — Should have** |
| **Insider trading** | Medium — strong contrarian signal | Low-Medium (1 new endpoint + model) | FMP `/v4/insider-trading` | **P2 — Nice to have** |
| **Macro context** | Low-Medium — LLM can partially compensate | High (new API source, e.g., FRED) | New data source needed | **P3 — Future** |

---

## Part 4: Recommended Changes to the Implementation Plan

### Change 1: Add "Phase 0.5 — Data Enrichment" Before Agent Implementation

Insert a new phase between Phase 0 (Foundation) and Phase 1 (Agent Implementation) to add the critical missing data:

**Phase 0.5: Data Enrichment (NEW)**

| Feature | Description | Effort |
|---------|-------------|--------|
| 0.5.1 — FMP Valuation Ratios | New API method `fetch_key_metrics()`, new job `ingest_fmp_key_metrics.py`, new raw table `sp500_key_metrics`, new staging view, new intermediate model, new/updated mart | 2-3 hours |
| 0.5.2 — FMP Earnings Surprises | New API method `fetch_earnings_surprises()`, new job, new raw table `sp500_earnings_surprises`, staging, intermediate | 2-3 hours |
| 0.5.3 — FMP Earnings Calendar | New API method `fetch_earnings_calendar()`, new job, new raw table `sp500_earnings_calendar`, staging view | 1-2 hours |
| 0.5.4 — FMP Analyst Consensus | New API method `fetch_analyst_consensus()`, new job, new raw table `sp500_analyst_consensus`, staging view | 1-2 hours |
| 0.5.5 — News Categorization (dbt) | New intermediate model `int_sp500_news_categorized` using keyword extraction from existing Polygon news VARIANT fields | 1-2 hours |

**Deliverables:**
- 3-4 new raw tables in Snowflake
- 3-4 new staging views
- 1-2 new intermediate models
- Updated or new mart(s) for valuation and earnings data
- 3-4 new Airflow DAGs (daily, gated on sp500_lookup)

### Change 2: Update Opportunity Scoring Formula

The current plan's 5-factor scoring model should be updated to include valuation:

**Current Plan (5 factors):**
```
opportunity_score = (
    technical_momentum × 0.25 +
    fundamental_quality × 0.20 +
    price_trajectory × 0.20 +
    catalyst_strength × 0.20 +
    sector_favorability × 0.15
)
```

**Recommended (6 factors):**
```
opportunity_score = (
    technical_momentum × 0.20 +
    fundamental_quality × 0.15 +
    valuation_attractiveness × 0.15 +    # NEW: P/E relative to sector, FCF yield
    price_trajectory × 0.15 +
    catalyst_strength × 0.20 +
    sector_favorability × 0.15
)
```

**Why**: Valuation is a critical filter. A stock scoring 90 on technicals and 85 on fundamentals but trading at 60x P/E is not a "30-day opportunity" — it's a momentum trap. The valuation factor prevents this.

**Valuation attractiveness sub-score (0-100):**
- P/E relative to sector median (0-30 pts)
- FCF yield percentile within sector (0-25 pts)
- EV/EBITDA relative to 5-year average (0-25 pts)
- PEG ratio tier (0-20 pts)

### Change 3: Update Agent Data Access Layer

The `snowflake_reader.py` (Phase 0 Feature 03) needs additional reader functions:

| New Reader | Table | Purpose |
|-----------|-------|---------|
| `read_valuation_metrics(session, date, tickers=None)` | New valuation mart | P/E, P/B, P/S, EV/EBITDA, FCF yield per ticker |
| `read_earnings_calendar(session, start_date, end_date)` | New earnings calendar table | Upcoming earnings dates for all S&P 500 |
| `read_earnings_surprises(session, tickers=None)` | New earnings surprises table | Last 4 quarters of actual vs estimated EPS |
| `read_analyst_consensus(session, tickers=None)` | New analyst consensus table | Buy/Hold/Sell counts, median price target |

### Change 4: Update Thesis Writer Agent Context

The Thesis Writer (Phase 3) should receive additional context:

```python
# Current plan: thesis_context includes
{
    "stock_candidate": StockCandidate,     # scores + returns + catalysts
    "sector_context": SectorContext,        # sector averages
    "market_context": MarketContext,        # market regime
}

# Recommended: add valuation + earnings context
{
    "stock_candidate": StockCandidate,
    "sector_context": SectorContext,
    "market_context": MarketContext,
    "valuation": {                          # NEW
        "pe_ratio": 25.4,
        "sector_median_pe": 30.2,
        "pe_percentile_in_sector": 35,      # cheaper than 65% of sector peers
        "ev_ebitda": 18.2,
        "fcf_yield": 4.2,
        "peg_ratio": 1.8,
    },
    "earnings": {                           # NEW
        "next_earnings_date": "2026-03-15",
        "days_to_earnings": 15,
        "last_quarter_surprise_pct": 8.5,   # beat by 8.5%
        "surprise_streak": 4,               # beat 4 consecutive quarters
        "consensus_eps_estimate": 2.40,
    },
    "analyst_consensus": {                  # NEW
        "buy_count": 9,
        "hold_count": 3,
        "sell_count": 0,
        "median_target_price": 180.00,
        "implied_upside_pct": 25.0,
    },
}
```

This additional context enables thesis statements like:
> "AAPL is trading at 25x earnings, below its sector median of 30x, with 4 consecutive earnings beats averaging 8.5% surprise. With its next report on March 15, the stock offers an asymmetric setup: strong momentum (technical score: 82) and reasonable valuation (35th percentile P/E in Technology) into a potential catalyst."

vs. the current plan's output (without valuation/earnings data):
> "AAPL has a strong technical score of 82 with positive momentum and aligned moving averages. Recent news mentions strong iPhone demand."

The difference in thesis quality is substantial.

### Change 5: Update Risk Assessor Agent Context

Add valuation risk checks:

```python
# Risk assessment should now flag:
risk_checks = {
    "valuation_risk": pe_ratio > sector_median_pe * 1.5,          # "Priced for perfection"
    "earnings_event_risk": days_to_earnings < 14,                  # "Binary event approaching"
    "analyst_divergence": sell_count > buy_count * 0.5,            # "Significant sell-side skepticism"
    "surprise_dependency": last_surprise > 10 and pe > 40,        # "High expectations baked in"
    "insider_selling": net_insider_30d < -1_000_000,               # "Insiders reducing exposure"
}
```

### Change 6: Add Shortlist Filter for Earnings Timing

The Shortlist Selector (Phase 2) should optionally filter based on earnings calendar:

```yaml
# pipeline_config.yaml — new shortlist filter
shortlist:
  min_opportunity_score: 65.0
  max_drawdown_threshold: -0.20
  max_per_sector: 3
  max_total: 15
  exclude_earnings_within_days: 3    # NEW: exclude stocks reporting in <3 days (binary risk)
```

Stocks reporting earnings within 3 days are high-risk for a "30-day opportunity" thesis — the outcome is binary and unpredictable. The filter prevents the pipeline from recommending stocks right before an earnings event.

---

## Part 5: What Does NOT Need to Change

These aspects of the current infrastructure are solid and should remain as-is:

1. **Polygon API client** — Well-architected with rate limiting, retries, concurrent fetch. No changes needed.
2. **FMP API client** — Same quality. Just needs 3-4 new methods added to the existing class.
3. **Snowflake loader** — `overwrite_partition()` and `overwrite_date_range()` cover all new tables.
4. **dbt layer architecture** — staging → intermediate → marts pattern is correct. New data follows the same flow.
5. **Airflow DAG pattern** — New DAGs follow existing template (PythonOperator, ExternalTaskSensor gating).
6. **Scoring architecture** — Technical (0-100) and fundamental (0-100) scores are well-designed. Composite blending works.
7. **MCP semantic layer** — Will need new model entries for valuation/earnings but the architecture is sound.
8. **Security patterns** — `os.environ[]` for credentials, no `.env` reading, gitignore rules all correct.

---

## Part 6: Updated Implementation Roadmap

### Before (Current Plan)
```
Phase 0: Foundation (config, SDK, Snowflake reader, output dirs)
Phase 1: Core Agent Infrastructure (schemas, orchestrator, LLM client, manifest)
Phase 2: Data Collection Agents (market context, sector scores, stock detail, news catalyst)
Phase 3: Scoring & Ranking (opportunity scorer, sector ranker, shortlist selector)
Phase 4: Thesis & Risk (thesis writer, risk assessor)
Phase 5: PDF Report Generation
Phase 6: Pipeline Integration (CLI, caching, Airflow DAG)
Phase 7: Quality & Testing
Phase 8: Documentation
```

### After (Recommended)
```
Phase 0:   Foundation (config, SDK, Snowflake reader, output dirs) — NO CHANGE
Phase 0.5: Data Enrichment (NEW — valuation ratios, earnings data, analyst consensus)
Phase 1:   Core Agent Infrastructure — MINOR UPDATE (add new schemas for valuation/earnings)
Phase 2:   Data Collection Agents — UPDATE (add valuation + earnings context to stock detail)
Phase 3:   Scoring & Ranking — UPDATE (6-factor scoring with valuation, earnings timing filter)
Phase 4:   Thesis & Risk — UPDATE (richer context for thesis/risk, valuation-aware prompts)
Phase 5:   PDF Report Generation — MINOR UPDATE (add valuation section to stock detail pages)
Phase 6:   Pipeline Integration — NO CHANGE
Phase 7:   Quality & Testing — NO CHANGE
Phase 8:   Documentation — UPDATE (document new data sources and scoring changes)
```

---

## Part 7: Effort Estimate for Data Enrichment

| Task | New Files | Modified Files | Effort |
|------|-----------|---------------|--------|
| FMP `fetch_key_metrics()` method | 0 | `fmp_client.py` | 30 min |
| FMP `fetch_earnings_surprises()` method | 0 | `fmp_client.py` | 30 min |
| FMP `fetch_earnings_calendar()` method | 0 | `fmp_client.py` | 30 min |
| FMP `fetch_analyst_consensus()` method | 0 | `fmp_client.py` | 30 min |
| 4 ingestion jobs | 4 | 0 | 2 hours |
| 4 Airflow DAGs | 4 | `stock_screening_dbt_daily_dag.py` (add sensors) | 2 hours |
| 4 raw table CREATE statements | 0 | job files | included above |
| 4 staging views + sources YAML | 5 | `_sources.yml` | 1.5 hours |
| 1-2 intermediate models | 1-2 | 0 | 1.5 hours |
| 1 new mart (`mart_sp500_valuation`) or update existing | 1 | `mart.yml` | 2 hours |
| News categorization dbt model | 1 | `int.yml` | 1 hour |
| Semantic layer updates | 0 | `semantic_layer.yaml` | 1 hour |
| Update `requirements.txt` (if needed) | 0 | `requirements.txt` | 5 min |
| **Total** | **~15 new files** | **~8 modified files** | **~12 hours** |

---

## Part 8: Specific FMP Endpoints to Add

### 1. Key Metrics (Valuation)
```
GET /v3/key-metrics/{ticker}?period=annual
```
Returns: market_cap, enterprise_value, pe_ratio, price_to_book, price_to_sales, ev_to_ebitda, ev_to_operating_cash_flow, earnings_yield, fcf_yield, dividend_yield, payout_ratio, and 20+ more metrics.

**Integration path**: New raw table `sp500_key_metrics` → staging view `stg_fmp_key_metrics` → mart `mart_sp500_valuation` (or merge into `mart_sp500_fundamental_scores`).

### 2. Earnings Surprises
```
GET /v3/earnings-surprises/{ticker}
```
Returns: date, actual_eps, estimated_eps, surprise_pct for last 4+ quarters.

**Integration path**: New raw table `sp500_earnings_surprises` → staging view `stg_fmp_earnings_surprises` → accessible via `read_earnings_surprises()` in the agent data access layer.

### 3. Earnings Calendar
```
GET /v3/earning_calendar?from={start_date}&to={end_date}
```
Returns: date, ticker, eps_estimate, revenue_estimate, fiscal_date_ending for all companies reporting in the date range.

**Integration path**: New raw table `sp500_earnings_calendar` → staging view `stg_fmp_earnings_calendar` → accessible via `read_earnings_calendar()`.

### 4. Analyst Consensus (Upgrades/Downgrades)
```
GET /v4/upgrades-downgrades-consensus?symbol={ticker}
```
Returns: strong_buy, buy, hold, sell, strong_sell counts + consensus rating.

**Integration path**: New raw table `sp500_analyst_consensus` → staging view `stg_fmp_analyst_consensus` → accessible via `read_analyst_consensus()`.

---

## Part 9: Updated Feature Specs Required

The following Phase 0 feature specs need updates:

| Spec File | Required Update |
|-----------|----------------|
| `01-pipeline-configuration-system.md` | Add `valuation_weight` to `ScoringWeights` dataclass, add `exclude_earnings_within_days` to `ShortlistConfig` |
| `03-agent-data-access-layer.md` | Add 4 new reader functions for valuation, earnings surprises, earnings calendar, analyst consensus |
| `04-output-directory-conventions.md` | No changes needed |
| NEW: `implementation/phase_0.5/` specs | Create 5 new feature specs for the data enrichment phase |

---

## Part 10: Summary of Recommendations

### Must Do (Before Building Agents)
1. **Add FMP key metrics / valuation ratios** — Cannot write credible investment theses without P/E, EV/EBITDA
2. **Add FMP earnings surprises** — #1 short-term catalyst, far more reliable than news extraction
3. **Add FMP earnings calendar** — Must know when stocks report to manage binary event risk

### Should Do (High Value, Low Effort)
4. **Add FMP analyst consensus** — Provides institutional signal and price target for upside quantification
5. **Add news categorization dbt model** — Uses existing Polygon news keywords to pre-classify articles

### Can Defer (V2 Enhancements)
6. **Add FMP insider trading** — Strong signal but not essential for V1
7. **Add macro context (FRED API)** — LLM can compensate via training knowledge
8. **Add quarterly financials** — Annual is sufficient for V1; quarterly adds trend granularity
9. **Add options implied volatility** — Polygon options data; complex to integrate

### Update Implementation Plan
10. **Insert Phase 0.5** before agent development
11. **Update scoring formula** to 6 factors (add valuation)
12. **Update thesis/risk agent context** with valuation + earnings data
13. **Add earnings timing filter** to shortlist selector

---

## Conclusion

The current infrastructure provides a **strong technical and fundamental foundation**. The data pipeline, transformation layer, and scoring architecture are production-grade. However, building AI investment theses without valuation data and earnings context is like writing a restaurant review without tasting the food — you can describe the ambiance and the menu, but you're missing the most important dimension.

The recommended Phase 0.5 additions (~12 hours of effort) would elevate the pipeline output from "technically competent screen" to "actionable investment intelligence" — and all the required data is available through the FMP API that's already integrated into the project.
