# Create Pipeline Configuration System

## Goal

Create a typed, validated YAML-based configuration system that governs every tunable parameter of the daily agentic stock opportunity pipeline. This is the foundational feature — every subsequent agent, scorer, selector, and report builder reads its parameters from this config.

## Why this matters

Without a centralized config, scoring weights, shortlist thresholds, model selection, and output paths would be hardcoded across dozens of files. A single YAML + typed loader ensures:
- All tunable parameters are documented in one place
- Changes to weights or thresholds require editing one file, not hunting through code
- CI/CD can override parameters via environment variables without modifying YAML
- Invalid configurations are caught at startup (fail fast), not mid-pipeline

## Scope

- Create package scaffolding: `src/agents/__init__.py`, `src/agents/config/__init__.py`
- Create `src/agents/config/pipeline_config.yaml` — master config with all pipeline parameters
- Create `src/agents/config/config_loader.py` — typed config loader that reads YAML, validates required fields, applies defaults, and supports env var overrides

## Out of scope

- Disclaimers YAML (separate feature in Phase 4: `src/agents/config/disclaimers.yaml`)
- LLM client setup (Phase 1 feature)
- Snowflake reader setup (Phase 0 Feature 3)
- Any agent implementation
- Runtime parameter overrides via CLI flags (Phase 6 feature)

## Required context to read first

| File | Why |
|------|-----|
| `project_plan.md` | Phase 0 deliverables and Phase 3 scoring weight defaults |
| `project_checklist.md` | Exact acceptance criteria for this feature |
| `CLAUDE.md` | Forbidden actions, core design rules |
| `.claude/rules/analytics-architecture.md` | Separation of concerns — config belongs in `src/agents/config/` |
| `.claude/rules/security-and-privacy-guardrails.md` | Credential patterns — env var access via `os.environ[]` |
| `dbt_project/models/marts/mart_sp500_technical_scores.sql` | Existing scoring component names (trend, momentum, price_action, macd) |
| `dbt_project/models/marts/mart_sp500_fundamental_scores.sql` | Existing scoring component names (profitability, growth, health, cash) |
| `dbt_project/models/marts/mart_sp500_composite_scores.sql` | Existing composite weighting variants (50/50, 60/40, 40/60) |

## Dependencies

### Upstream features
- None — this is the first feature in the implementation order.

### Libraries/packages
- `PyYAML` — must be added to `requirements.txt` (not currently present). Used by `config_loader.py` to parse YAML.
- Python `dataclasses` module — standard library, no install needed.
- Python `os` module — standard library, for env var overrides.

### Environment variables
- None required for this feature specifically. The config system *supports* env var overrides but does not mandate any particular env var at this stage.

### APIs/data sources
- None — this is a pure configuration feature.

## Data contracts and schemas

### `PipelineConfig` dataclass

```python
@dataclass
class UniverseConfig:
    source_table: str  # default: "dim_sp500_companies_current"
    schema_suffix: str  # default: "_MARTS"

@dataclass
class ScoringWeights:
    technical_momentum: float  # default: 0.25
    fundamental_quality: float  # default: 0.20
    price_trajectory: float    # default: 0.20
    catalyst_strength: float   # default: 0.20
    sector_favorability: float # default: 0.15
    # Weights MUST sum to 1.0 — validated at load time

@dataclass
class ShortlistConfig:
    min_opportunity_score: float   # default: 65.0
    max_drawdown_threshold: float  # default: -0.20
    max_per_sector: int            # default: 3
    max_total: int                 # default: 15

@dataclass
class AgentConfig:
    news_lookback_days: int       # default: 7
    catalyst_top_n: int           # default: 50
    thesis_model: str             # default: "claude-opus-4-6"
    analysis_model: str           # default: "claude-sonnet-4-6"
    risk_model: str               # default: "claude-sonnet-4-6"
    max_retries: int              # default: 2
    retry_base_delay_seconds: float  # default: 1.0

@dataclass
class OutputConfig:
    base_dir: str          # default: "output"
    pdf_orientation: str   # default: "portrait"  (portrait or landscape)

@dataclass
class PipelineConfig:
    universe: UniverseConfig
    scoring_weights: ScoringWeights
    shortlist: ShortlistConfig
    agents: AgentConfig
    output: OutputConfig
```

### `pipeline_config.yaml` structure

```yaml
universe:
  source_table: dim_sp500_companies_current
  schema_suffix: _MARTS

scoring_weights:
  technical_momentum: 0.25
  fundamental_quality: 0.20
  price_trajectory: 0.20
  catalyst_strength: 0.20
  sector_favorability: 0.15

shortlist:
  min_opportunity_score: 65.0
  max_drawdown_threshold: -0.20
  max_per_sector: 3
  max_total: 15

agents:
  news_lookback_days: 7
  catalyst_top_n: 50
  thesis_model: claude-opus-4-6
  analysis_model: claude-sonnet-4-6
  risk_model: claude-sonnet-4-6
  max_retries: 2
  retry_base_delay_seconds: 1.0

output:
  base_dir: output
  pdf_orientation: portrait
```

## Implementation plan

### Step 1: Add PyYAML to requirements.txt

Append `PyYAML` to `/Users/balazsillovai/stock-screening-engine/requirements.txt`. Place it alphabetically or at the end. Do not remove existing entries.

### Step 2: Create package scaffolding

Create the following empty `__init__.py` files:
- `src/agents/__init__.py`
- `src/agents/config/__init__.py`

Both files should be empty (zero bytes). They exist only to make `src.agents` and `src.agents.config` importable as Python packages.

### Step 3: Create `pipeline_config.yaml`

Write the YAML file at `src/agents/config/pipeline_config.yaml` with the exact structure shown in the Data contracts section above. Include inline YAML comments explaining each section. All values must be the documented defaults.

### Step 4: Create `config_loader.py`

Write `src/agents/config/config_loader.py` with the following contents:

1. Import `yaml`, `os`, `dataclasses`, `pathlib.Path`
2. Define a custom `ConfigValidationError(Exception)` class
3. Define all dataclass types: `UniverseConfig`, `ScoringWeights`, `ShortlistConfig`, `AgentConfig`, `OutputConfig`, `PipelineConfig`
4. Define `_apply_env_overrides(raw: dict) -> dict`:
   - Checks for env vars prefixed with `PIPELINE_` that map to config keys
   - Pattern: `PIPELINE_SCORING_TECHNICAL_MOMENTUM=0.30` overrides `scoring_weights.technical_momentum`
   - Only override if the env var exists; do not error on missing env vars
5. Define `_validate_weights(weights: ScoringWeights) -> None`:
   - Assert all weights are >= 0 and <= 1
   - Assert weights sum to 1.0 (with float tolerance: `abs(total - 1.0) < 0.001`)
   - Raise `ConfigValidationError` on failure
6. Define `load_config(config_path: Path | str | None = None) -> PipelineConfig`:
   - Default path: `Path(__file__).parent / "pipeline_config.yaml"`
   - Read YAML, apply env overrides, validate, construct dataclass tree
   - Raise `ConfigValidationError` for: missing file, invalid YAML syntax, missing required section, invalid types, invalid weight sum
   - Return fully constructed `PipelineConfig`

### Step 5: Validate locally

```bash
cd /Users/balazsillovai/stock-screening-engine
python -c "from src.agents.config.config_loader import load_config; c = load_config(); print(c)"
```

This should print the `PipelineConfig` dataclass without errors.

## File-level change list

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | EDIT | Append `PyYAML` |
| `src/agents/__init__.py` | CREATE | Empty file (package marker) |
| `src/agents/config/__init__.py` | CREATE | Empty file (package marker) |
| `src/agents/config/pipeline_config.yaml` | CREATE | Master configuration YAML |
| `src/agents/config/config_loader.py` | CREATE | Typed config loader with validation |

## Functions and interfaces

### `config_loader.py`

```python
class ConfigValidationError(Exception):
    """Raised when pipeline configuration is invalid."""
    pass

@dataclass
class UniverseConfig:
    source_table: str = "dim_sp500_companies_current"
    schema_suffix: str = "_MARTS"

@dataclass
class ScoringWeights:
    technical_momentum: float = 0.25
    fundamental_quality: float = 0.20
    price_trajectory: float = 0.20
    catalyst_strength: float = 0.20
    sector_favorability: float = 0.15

@dataclass
class ShortlistConfig:
    min_opportunity_score: float = 65.0
    max_drawdown_threshold: float = -0.20
    max_per_sector: int = 3
    max_total: int = 15

@dataclass
class AgentConfig:
    news_lookback_days: int = 7
    catalyst_top_n: int = 50
    thesis_model: str = "claude-opus-4-6"
    analysis_model: str = "claude-sonnet-4-6"
    risk_model: str = "claude-sonnet-4-6"
    max_retries: int = 2
    retry_base_delay_seconds: float = 1.0

@dataclass
class OutputConfig:
    base_dir: str = "output"
    pdf_orientation: str = "portrait"

@dataclass
class PipelineConfig:
    universe: UniverseConfig
    scoring_weights: ScoringWeights
    shortlist: ShortlistConfig
    agents: AgentConfig
    output: OutputConfig

def load_config(config_path: Path | str | None = None) -> PipelineConfig:
    """Load and validate pipeline configuration from YAML.

    Args:
        config_path: Path to YAML file. Defaults to pipeline_config.yaml
                     in the same directory as this module.

    Returns:
        Validated PipelineConfig dataclass.

    Raises:
        ConfigValidationError: If config is missing, malformed, or invalid.
    """
    ...

def _apply_env_overrides(raw: dict) -> dict:
    """Apply PIPELINE_* environment variable overrides to raw config dict."""
    ...

def _validate_weights(weights: ScoringWeights) -> None:
    """Validate scoring weights sum to 1.0 and are each in [0, 1]."""
    ...
```

## Couplings and side effects

| Module/File | Impact |
|-------------|--------|
| `requirements.txt` | Adding `PyYAML` — all downstream `pip install -r requirements.txt` will install it. Verify no conflicts with existing deps. |
| `src/agents/` package | Creating this package establishes the namespace for all future agent code. All subsequent Phase 0-8 features depend on this package existing. |
| Airflow Docker image (`Dockerfile`) | The Astro Runtime image installs from `requirements.txt`, so `PyYAML` will be available in the Airflow container after next build. |
| No existing code is modified | Config loader is standalone — no existing files import from it yet. |

## Error handling and edge cases

| Scenario | Handling |
|----------|----------|
| YAML file not found | Raise `ConfigValidationError(f"Config file not found: {path}")` |
| YAML syntax error | Catch `yaml.YAMLError`, raise `ConfigValidationError` with original message |
| Missing top-level section (e.g., no `scoring_weights` key) | Apply defaults for the entire section — all dataclass fields have defaults |
| Missing individual field (e.g., `scoring_weights` exists but no `technical_momentum`) | Apply field-level default from the dataclass |
| Scoring weights don't sum to 1.0 | Raise `ConfigValidationError(f"Scoring weights sum to {total}, must sum to 1.0")` |
| Invalid type (e.g., `max_per_sector: "three"`) | Catch `TypeError`/`ValueError` during dataclass construction, raise `ConfigValidationError` |
| Env var override with invalid value | Raise `ConfigValidationError` with the env var name and invalid value |
| Empty YAML file | Treat as all-defaults config (every section uses dataclass defaults) |
| Extra unknown keys in YAML | Silently ignore — forward-compatible for future config additions |

## Observability (logging/metrics)

- `config_loader.py` uses Python `logging` module: `logger = logging.getLogger(__name__)`
- Log at `INFO` level: "Loaded pipeline config from {path}"
- Log at `DEBUG` level: each env var override applied ("Override: scoring_weights.technical_momentum = 0.30 (from PIPELINE_SCORING_TECHNICAL_MOMENTUM)")
- Log at `WARNING` level: if scoring weights are close to boundary (`abs(total - 1.0) < 0.001` but `> 0.0001`)
- No metrics collection at this stage (future: track config versions per run in manifest)

## Acceptance criteria

- [ ] `src/agents/__init__.py` exists and is importable (`from src.agents import ...` does not error)
- [ ] `src/agents/config/__init__.py` exists and is importable
- [ ] `src/agents/config/pipeline_config.yaml` exists with all documented sections and defaults
- [ ] `from src.agents.config.config_loader import load_config` succeeds
- [ ] `load_config()` returns a `PipelineConfig` dataclass with correct default values
- [ ] `load_config()` with a missing YAML file raises `ConfigValidationError`
- [ ] `load_config()` with invalid YAML syntax raises `ConfigValidationError`
- [ ] `load_config()` with scoring weights summing to != 1.0 raises `ConfigValidationError`
- [ ] Default values apply for omitted fields (partial YAML with only `shortlist:` section still loads)
- [ ] Environment variable `PIPELINE_SCORING_TECHNICAL_MOMENTUM=0.30` overrides the YAML value
- [ ] `PyYAML` is in `requirements.txt` and `pip install -r requirements.txt` installs it
- [ ] Unit test covers: valid load, missing file, invalid YAML, invalid weight sum, env var override, partial YAML

## Follow-ups (optional)

- Phase 6 will add `--config` CLI flag to specify alternative YAML path
- Phase 8 should document all config parameters in `README.md`
- Consider adding JSON Schema validation for the YAML in a future iteration
