# Add Anthropic SDK Dependency and Secret Management

## Goal

Add the `anthropic` and `pydantic` Python packages to the project's dependency list and document the `ANTHROPIC_API_KEY` environment variable pattern. This establishes the LLM integration foundation that all Claude API-calling agents depend on.

## Why this matters

The entire agent layer relies on the Anthropic Python SDK to call Claude models for market analysis, thesis generation, and risk assessment. Pydantic is required for structured schema validation across all agent data contracts. Without these dependencies installed, no agent code can function. The secret management documentation ensures the API key follows the project's established credential pattern — `os.environ["KEY"]` with no `.env` file reading in code.

## Scope

- Add `anthropic` to `requirements.txt`
- Add `pydantic` to `requirements.txt`
- Document `ANTHROPIC_API_KEY` in a visible location (comment in `requirements.txt` or a new `.env.example` file)
- Verify both packages install and import correctly

## Out of scope

- Building the LLM client wrapper (`src/agents/core/llm_client.py`) — that is Phase 1 Feature 3
- Reading or modifying any `.env` file — strictly forbidden per project rules
- Creating Anthropic client instances or making API calls
- Any agent implementation

## Required context to read first

| File | Why |
|------|-----|
| `project_checklist.md` | Exact acceptance criteria for this feature |
| `CLAUDE.md` | Forbidden actions: "NEVER read .env, dbt.env, or files containing credentials" |
| `.claude/rules/security-and-privacy-guardrails.md` | Credential management patterns, env var table, forbidden files list |
| `requirements.txt` | Current dependency list — must not break existing installs |
| `src/api_clients/polygon_client.py` (lines 25-26) | Reference pattern for env var access: `self.api_key = api_key or os.environ["POLYGON_API_KEY"]` |
| `src/api_clients/fmp_client.py` (first 30 lines) | Same pattern for `FMP_API_KEY` |
| `src/loaders/snowflake_loader.py` (lines 4-13) | Same pattern for Snowflake credentials |

## Dependencies

### Upstream features
- Feature 01 (pipeline configuration system) should be implemented first since it creates `src/agents/__init__.py`, but this feature does not strictly depend on it. If implemented standalone, `src/agents/` package must already exist.

### Libraries/packages
- `anthropic` — Anthropic Python SDK. Current latest version should be installed without pinning (let pip resolve).
- `pydantic` — Data validation library. Version 2.x (Pydantic v2). Do not pin to v1.

### Environment variables
- `ANTHROPIC_API_KEY` — Required for all LLM calls. Must be set in the shell environment before running the pipeline. Not read from `.env` files.

### APIs/data sources
- Anthropic API (https://api.anthropic.com) — will be used in later phases. This feature only installs the SDK, does not call the API.

## Data contracts and schemas

No new data contracts introduced by this feature. The `anthropic` SDK's `Message` response type and Pydantic `BaseModel` will be used extensively starting in Phase 1.

## Implementation plan

### Step 1: Add dependencies to requirements.txt

Edit `/Users/balazsillovai/stock-screening-engine/requirements.txt` to add two new lines:

```
anthropic
pydantic
```

Place them in a logical position — either alphabetically or grouped at the end with a comment `# Agent pipeline dependencies`. Do not remove or modify any existing lines.

**Important**: Do not pin versions. The project's existing deps (e.g., `apache-airflow-providers-snowflake`, `snowflake-snowpark-python`) are also unpinned, so follow the same convention.

### Step 2: Verify installation

Run from project root:
```bash
pip install -r requirements.txt
```

Verify:
```bash
python -c "import anthropic; print(anthropic.__version__)"
python -c "import pydantic; print(pydantic.__version__)"
```

Both should print version numbers without errors.

### Step 3: Verify no dependency conflicts

```bash
pip check
```

This should report no broken dependencies. Known potential conflicts:
- `pydantic` v2 vs v1: some packages may depend on pydantic v1. If `pip check` reports issues, add `pydantic>=2.0` to force v2.
- `anthropic` depends on `httpx` which should not conflict with `requests` (used by Polygon/FMP clients).

### Step 4: Document the API key

Create `.env.example` at the project root (if it doesn't already exist) with:

```bash
# Stock Screening Engine — Environment Variables
# Copy this file to .env and fill in values. NEVER commit .env.

# Existing credentials (already required)
POLYGON_API_KEY=your_polygon_api_key
FMP_API_KEY=your_fmp_api_key
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ROLE=ALL_USERS_ROLE
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=DATAEXPERT_STUDENT
STUDENT_SCHEMA=your_schema_prefix

# Agent pipeline (new)
ANTHROPIC_API_KEY=your_anthropic_api_key
```

Verify `.env.example` is NOT in `.gitignore` (it should be committed as documentation). The existing `.gitignore` excludes `.env` and `.env.*` — `.env.example` does NOT match the `.env.*` glob pattern because it has a dot before `example` (`.env.example` matches `.env.*`).

**Wait** — `.env.example` DOES match `.env.*`. So instead, name the file `env.example` (no leading dot) or add `!.env.example` to `.gitignore` to explicitly include it.

**Decision**: Add `!.env.example` to `.gitignore` to keep the conventional name `.env.example`. This is the clearest signal to developers.

### Step 5: Update .gitignore

Add an explicit include rule for `.env.example`:

```
## Ignore environment variable files
.env
.env.*
!.env.example
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | EDIT | Add `anthropic` and `pydantic` |
| `.env.example` | CREATE | Document all required environment variables including `ANTHROPIC_API_KEY` |
| `.gitignore` | EDIT | Add `!.env.example` to prevent gitignoring the example file |

## Functions and interfaces

No functions or classes are created by this feature. This is a dependency and documentation-only change.

The `anthropic` SDK provides:
```python
# Will be used in Phase 1 Feature 3 (llm_client.py)
import anthropic
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system="...",
    messages=[{"role": "user", "content": "..."}]
)
```

The `pydantic` library provides:
```python
# Will be used in Phase 1 Feature 1 (schemas.py)
from pydantic import BaseModel, Field, field_validator

class StockCandidate(BaseModel):
    ticker: str
    technical_score: float = Field(ge=0, le=100)
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `requirements.txt` | All environments (local venv, Astro Docker image) will install `anthropic` + `pydantic` on next `pip install`. Verify the Astro Docker build still succeeds. |
| `.gitignore` | Adding `!.env.example` changes gitignore behavior. Verify no existing `.env.example` file with secrets is accidentally tracked. |
| Existing code | No existing code imports `anthropic` or `pydantic` yet. Zero runtime impact on current pipeline. |
| Airflow Docker image (`Dockerfile`) | The `Dockerfile` runs `pip install -r requirements.txt`, so these packages will be available in the Airflow container. Verify image builds without errors. |
| `snowflake-snowpark-python` | This package has its own dependency tree. Verify `pydantic` v2 does not conflict with any Snowpark internal pydantic usage. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| `pip install` fails due to version conflict | Run `pip install --dry-run -r requirements.txt` first to check. If conflict exists, pin minimum version: `anthropic>=0.40.0`, `pydantic>=2.0`. |
| `ANTHROPIC_API_KEY` not set at runtime | This feature does not consume the key. Phase 1 Feature 3 (`llm_client.py`) will raise `KeyError` if missing. CLI `--dry-run` mode (Phase 6) will skip LLM calls. |
| Pydantic v1 vs v2 | If any existing dep requires pydantic v1, the install will fail. Resolution: check `pip show pydantic` for currently installed version. If v1 is locked in by another dep, use `pydantic>=2.0` and investigate the conflict. The `boring-semantic-layer` package may have a pydantic dependency — verify compatibility. |
| `.env.example` accidentally contains real secrets | The `.env.example` file must contain only placeholder values (`your_xxx`). Never copy actual credentials into it. |

## Observability (logging/metrics)

No logging or metrics added by this feature. The `anthropic` SDK has its own internal logging (configurable via `ANTHROPIC_LOG` env var) which will be leveraged in Phase 1.

## Acceptance criteria

- [ ] `requirements.txt` contains `anthropic` and `pydantic` as new entries
- [ ] `pip install -r requirements.txt` completes without errors
- [ ] `python -c "import anthropic; print(anthropic.__version__)"` succeeds
- [ ] `python -c "import pydantic; print(pydantic.__version__)"` succeeds and shows v2.x
- [ ] `pip check` reports no broken dependencies
- [ ] `.env.example` exists at project root with `ANTHROPIC_API_KEY=your_anthropic_api_key`
- [ ] `.env.example` is NOT gitignored (verify with `git check-ignore .env.example` — should return nothing)
- [ ] No `.env` files are read, modified, or committed
- [ ] Existing `astro dev parse` still passes (DAG import integrity)

## Follow-ups (optional)

- Phase 1 Feature 3 will build the `LLMClient` wrapper that actually calls the Anthropic API
- Phase 8 should document `ANTHROPIC_API_KEY` in `README.md` under "Environment Variables"
- Consider adding `anthropic[bedrock]` if AWS Bedrock fallback is desired in the future
