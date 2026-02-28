# Establish Output Directory Conventions and .gitignore

## Goal

Create a standardized output directory structure for daily pipeline runs and a utility module that manages directory creation, path resolution, and filesystem safety. Every pipeline run produces artifacts in `output/{YYYY-MM-DD}/` — this feature defines and enforces that structure.

## Why this matters

The pipeline generates multiple PDF reports (per-sector + aggregate), a run manifest, cache files, log files, and temporary chart images. Without a consistent directory convention:
- Files would scatter across the project root
- Concurrent or sequential runs could overwrite each other
- Git would track generated artifacts, bloating the repository
- Agents would need to hardcode paths instead of asking a utility for the correct location

## Scope

- Create `output/.gitkeep` to establish the output directory in the repo
- Update `.gitignore` to exclude `output/*` except `.gitkeep`
- Create `src/agents/core/__init__.py` (package marker for the `core` sub-package)
- Create `src/agents/core/output_manager.py` with directory creation and path resolution utilities

## Out of scope

- Actually generating PDF files or manifests (Phase 5 and Phase 1 features)
- Cache implementation (`src/agents/core/cache.py` — Phase 6 feature)
- Logging configuration (`src/agents/core/manifest.py` — Phase 1 feature)
- CLI integration (Phase 6 feature)
- Cleaning up old output directories

## Required context to read first

| File | Why |
|------|-----|
| `project_checklist.md` | Exact acceptance criteria, function signatures, directory structure |
| `project_plan.md` | Phase 0 deliverable #4: output directory conventions |
| `.gitignore` | Current gitignore rules — must add output exclusion without breaking existing rules |
| `CLAUDE.md` | "NEVER read .env" — output directory must not contain or reference credentials |
| `.claude/rules/security-and-privacy-guardrails.md` | Forbidden files list — generated PDFs and manifests should be gitignored |

## Dependencies

### Upstream features
- Feature 01 (pipeline configuration system) — `src/agents/__init__.py` must exist. If not yet implemented, this feature must create it. Also, `OutputConfig.base_dir` from `PipelineConfig` defines the output root (default: `"output"`).

### Libraries/packages
- Python `pathlib` — standard library, for `Path` operations.
- Python `re` — standard library, for slugification.
- No additional pip packages needed.

### Environment variables
- None required for this feature.

### APIs/data sources
- None — this is a pure filesystem utility.

## Data contracts and schemas

### Output directory structure

For a pipeline run on `2026-02-28`:

```
output/
├── .gitkeep
└── 2026-02-28/
    ├── sectors/
    │   ├── information-technology.pdf
    │   ├── health-care.pdf
    │   ├── financials.pdf
    │   └── ... (one PDF per sector with shortlisted stocks)
    ├── aggregate/
    │   └── daily_opportunities_2026-02-28.pdf
    ├── .cache/
    │   ├── market_context.json
    │   ├── sector_scores_information-technology.json
    │   └── ... (per-agent cache files)
    ├── manifest.json
    └── pipeline.log
```

### Sector name slugification

GICS sector names → filesystem-safe slugs:

| GICS Sector | Slug |
|-------------|------|
| Communication Services | communication-services |
| Consumer Discretionary | consumer-discretionary |
| Consumer Staples | consumer-staples |
| Energy | energy |
| Financials | financials |
| Health Care | health-care |
| Industrials | industrials |
| Information Technology | information-technology |
| Materials | materials |
| Real Estate | real-estate |
| Utilities | utilities |

Slugification rules:
1. Convert to lowercase
2. Replace spaces with hyphens
3. Remove any character that is not alphanumeric or hyphen
4. Collapse multiple consecutive hyphens into one
5. Strip leading/trailing hyphens

## Implementation plan

### Step 1: Create `output/.gitkeep`

```bash
mkdir -p output
touch output/.gitkeep
```

This ensures the `output/` directory exists in the repository as an empty tracked directory.

### Step 2: Update `.gitignore`

Add the following lines to `.gitignore`:

```
## Pipeline output (generated artifacts)
output/*
!output/.gitkeep
```

Place these lines after the existing `## Superset metadata` section. The `output/*` rule excludes all generated content, while `!output/.gitkeep` preserves the directory marker.

Also add `__pycache__` exclusions for the new packages:

```
src/agents/__pycache__/
src/agents/config/__pycache__/
src/agents/core/__pycache__/
src/agents/data/__pycache__/
```

### Step 3: Create package scaffolding

Create the following files if they don't already exist:
- `src/agents/__init__.py` (empty — may exist from Feature 01)
- `src/agents/core/__init__.py` (empty)

### Step 4: Create `output_manager.py`

Write `src/agents/core/output_manager.py` with the functions specified in the interfaces section below.

**Key implementation details:**

1. **Date validation**: `ensure_run_directory()` validates the date string format (`YYYY-MM-DD`) using regex. Raise `ValueError` for invalid dates.

2. **Idempotent directory creation**: Use `Path.mkdir(parents=True, exist_ok=True)` so the function can be called multiple times without error.

3. **Slugification**: Implement as a pure function — no I/O, no side effects. Used by path helpers to convert sector names to filesystem-safe strings.

4. **Base directory**: Default to `output/` relative to the project root. In production, this may be overridden via `PipelineConfig.output.base_dir`.

5. **Project root detection**: Use `Path(__file__).resolve().parents[3]` to navigate from `src/agents/core/output_manager.py` up to the project root. Alternatively, accept `base_dir` as a parameter with a sensible default.

### Step 5: Validate locally

```bash
cd /Users/balazsillovai/stock-screening-engine
python -c "
from src.agents.core.output_manager import ensure_run_directory, get_sector_pdf_path, get_aggregate_pdf_path
run_dir = ensure_run_directory('2026-02-28')
print(f'Run directory: {run_dir}')
print(f'Sectors dir exists: {(run_dir / \"sectors\").exists()}')
print(f'Aggregate dir exists: {(run_dir / \"aggregate\").exists()}')
print(f'Cache dir exists: {(run_dir / \".cache\").exists()}')
print(f'Sector PDF path: {get_sector_pdf_path(\"2026-02-28\", \"Information Technology\")}')
print(f'Aggregate PDF path: {get_aggregate_pdf_path(\"2026-02-28\")}')
"
```

Then clean up:
```bash
rm -rf output/2026-02-28
```

### Step 6: Verify gitignore

```bash
git check-ignore output/2026-02-28/sectors/information-technology.pdf
# Should output: output/2026-02-28/sectors/information-technology.pdf

git check-ignore output/.gitkeep
# Should output nothing (NOT ignored)
```

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `output/.gitkeep` | CREATE | Empty file to preserve output directory in git |
| `.gitignore` | EDIT | Add `output/*`, `!output/.gitkeep`, and agent `__pycache__` exclusions |
| `src/agents/__init__.py` | CREATE (if not exists) | Empty file (package marker) |
| `src/agents/core/__init__.py` | CREATE | Empty file (package marker) |
| `src/agents/core/output_manager.py` | CREATE | Output directory utilities |

## Functions and interfaces

### `output_manager.py`

```python
import re
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Default output base directory (relative to project root)
_DEFAULT_BASE_DIR = Path(__file__).resolve().parents[3] / "output"


def slugify(name: str) -> str:
    """Convert a sector name to a filesystem-safe slug.

    Examples:
        "Information Technology" -> "information-technology"
        "Health Care" -> "health-care"
        "Consumer Discretionary" -> "consumer-discretionary"
        "Energy" -> "energy"

    Args:
        name: Human-readable name (e.g., GICS sector name).

    Returns:
        Lowercase, hyphen-separated slug safe for filenames.
    """
    ...


def ensure_run_directory(
    run_date: str,
    base_dir: Path | str | None = None
) -> Path:
    """Create the complete output directory tree for a pipeline run.

    Creates:
        {base_dir}/{run_date}/
        {base_dir}/{run_date}/sectors/
        {base_dir}/{run_date}/aggregate/
        {base_dir}/{run_date}/.cache/

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.
                  Defaults to {project_root}/output/.

    Returns:
        Path to the run directory ({base_dir}/{run_date}/).

    Raises:
        ValueError: If run_date is not in YYYY-MM-DD format.
    """
    ...


def get_sector_pdf_path(
    run_date: str,
    sector_name: str,
    base_dir: Path | str | None = None
) -> Path:
    """Return the expected path for a sector PDF report.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        sector_name: Human-readable sector name (will be slugified).
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/sectors/information-technology.pdf
    """
    ...


def get_aggregate_pdf_path(
    run_date: str,
    base_dir: Path | str | None = None
) -> Path:
    """Return the expected path for the aggregate PDF report.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/aggregate/daily_opportunities_2026-02-28.pdf
    """
    ...


def get_manifest_path(
    run_date: str,
    base_dir: Path | str | None = None
) -> Path:
    """Return the expected path for the run manifest.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/manifest.json
    """
    ...


def get_log_path(
    run_date: str,
    base_dir: Path | str | None = None
) -> Path:
    """Return the expected path for the pipeline log file.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/pipeline.log
    """
    ...


def get_cache_dir(
    run_date: str,
    base_dir: Path | str | None = None
) -> Path:
    """Return the path to the cache directory for a run.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/.cache/
    """
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `.gitignore` | Modified to exclude `output/*`. If someone has unstaged files in `output/`, they will be hidden after this change. Verify with `git status` before and after. |
| `src/agents/core/` package | New sub-package. All future core agent infrastructure (base_agent, llm_client, manifest, orchestrator, cache, schemas) lives here. |
| `PipelineConfig.output.base_dir` | Feature 01's config references `output` as default `base_dir`. This feature implements the corresponding filesystem structure. If Feature 01 changes the default, this module must match. |
| Filesystem | `ensure_run_directory()` creates directories. On CI/CD or read-only filesystems, this will fail. The orchestrator should catch `OSError` and report it. |
| `output/.gitkeep` | Adding this file to git tracking. If someone deletes it, `git checkout -- output/.gitkeep` restores it. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| Invalid date format | `ensure_run_directory("not-a-date")` raises `ValueError("Invalid date format: 'not-a-date'. Expected YYYY-MM-DD.")`. Validate with regex `^\d{4}-\d{2}-\d{2}$` and `datetime.strptime(date, "%Y-%m-%d")`. |
| Directory already exists | `Path.mkdir(exist_ok=True)` — no error. Idempotent. |
| Permission denied on mkdir | Let `OSError` propagate. The orchestrator catches and reports as a fatal startup error. |
| Sector name with unusual characters | `slugify()` handles edge cases: `"Real Estate"` → `"real-estate"`, `"S&P 500"` → `"sp-500"`, `""` → raises `ValueError`. |
| Empty sector name | `slugify("")` should raise `ValueError("Cannot slugify empty string")`. |
| Very long sector name | Truncate slug to 50 characters. GICS sector names are all under 30 chars, so this is a defensive guard. |
| `base_dir` does not exist | `Path.mkdir(parents=True)` creates all intermediate directories. |
| Path traversal attack (`../` in run_date) | Date validation regex (`^\d{4}-\d{2}-\d{2}$`) prevents path traversal. Only digits and hyphens are allowed. |

## Observability (logging/metrics)

- `logger = logging.getLogger(__name__)` at module level
- Log at `INFO` level: "Created run directory: {run_dir}" when `ensure_run_directory()` creates a new directory
- Log at `DEBUG` level: "Run directory already exists: {run_dir}" when directory already exists
- Log at `DEBUG` level: each subdirectory created (sectors, aggregate, .cache)
- No metrics at this stage — directory creation is a one-time operation per run

## Acceptance criteria

- [ ] `output/.gitkeep` exists and is tracked by git
- [ ] `output/*` is in `.gitignore` (generated files are excluded)
- [ ] `output/.gitkeep` is NOT excluded by `.gitignore` (verified via `git check-ignore`)
- [ ] `src/agents/core/__init__.py` exists
- [ ] `src/agents/core/output_manager.py` exists with all documented functions
- [ ] `ensure_run_directory("2026-02-28")` creates: `output/2026-02-28/`, `output/2026-02-28/sectors/`, `output/2026-02-28/aggregate/`, `output/2026-02-28/.cache/`
- [ ] `get_sector_pdf_path("2026-02-28", "Information Technology")` returns `Path(".../output/2026-02-28/sectors/information-technology.pdf")`
- [ ] `get_aggregate_pdf_path("2026-02-28")` returns `Path(".../output/2026-02-28/aggregate/daily_opportunities_2026-02-28.pdf")`
- [ ] `get_manifest_path("2026-02-28")` returns `Path(".../output/2026-02-28/manifest.json")`
- [ ] `slugify("Information Technology")` returns `"information-technology"`
- [ ] `slugify("Health Care")` returns `"health-care"`
- [ ] `ensure_run_directory("bad-date")` raises `ValueError`
- [ ] `slugify("")` raises `ValueError`
- [ ] Calling `ensure_run_directory()` twice with the same date does not error (idempotent)
- [ ] Agent `__pycache__/` directories are in `.gitignore`
- [ ] Unit test covers: directory creation, path generation, slugification, invalid date, empty name, idempotency

## Follow-ups (optional)

- Phase 1 will use `get_manifest_path()` and `get_log_path()` in the manifest and logging setup
- Phase 5 will use `get_sector_pdf_path()` and `get_aggregate_pdf_path()` in report generation
- Phase 6 will use `get_cache_dir()` in the caching layer
- Consider adding a `cleanup_old_runs(keep_days=30)` function in a future iteration to manage disk space
