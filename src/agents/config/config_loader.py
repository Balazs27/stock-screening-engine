"""Pipeline configuration loader.

Reads pipeline_config.yaml, applies PIPELINE_* environment variable overrides,
validates all fields, and returns a typed PipelineConfig dataclass.
"""

import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "pipeline_config.yaml"

# Maps PIPELINE_{PREFIX}_* env vars to the corresponding raw dict section key.
_ENV_SECTION_MAP = {
    "UNIVERSE": "universe",
    "SCORING": "scoring_weights",
    "SHORTLIST": "shortlist",
    "AGENTS": "agents",
    "OUTPUT": "output",
}


class ConfigValidationError(Exception):
    """Raised when pipeline configuration is missing, malformed, or invalid."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

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
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    shortlist: ShortlistConfig = field(default_factory=ShortlistConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _coerce_value(value: str, target_type: type) -> Any:
    """Coerce a string env var value to the target Python type."""
    try:
        if target_type == float:
            return float(value)
        if target_type == int:
            return int(value)
        return value  # str — no coercion needed
    except (ValueError, TypeError) as exc:
        raise ConfigValidationError(
            f"Cannot convert env var value {value!r} to {target_type.__name__}: {exc}"
        ) from exc


def _apply_env_overrides(raw: dict) -> dict:
    """Apply PIPELINE_<SECTION>_<KEY> environment variable overrides to raw config dict.

    Examples:
        PIPELINE_SCORING_TECHNICAL_MOMENTUM=0.30  → scoring_weights.technical_momentum = 0.30
        PIPELINE_SHORTLIST_MAX_TOTAL=10           → shortlist.max_total = 10
        PIPELINE_AGENTS_THESIS_MODEL=claude-opus-4-6 → agents.thesis_model = "claude-opus-4-6"
    """
    for env_key, env_value in os.environ.items():
        if not env_key.startswith("PIPELINE_"):
            continue

        # Strip the PIPELINE_ prefix and split into section + field parts
        remainder = env_key[len("PIPELINE_"):]
        parts = remainder.split("_", 1)
        if len(parts) < 2:
            continue  # e.g. PIPELINE_ alone — skip

        section_prefix, field_suffix = parts[0], parts[1].lower()

        section_key = _ENV_SECTION_MAP.get(section_prefix)
        if section_key is None:
            continue  # Unknown section prefix — silently ignore

        # Ensure the section dict exists in raw
        if section_key not in raw or raw[section_key] is None:
            raw[section_key] = {}

        raw[section_key][field_suffix] = env_value
        logger.debug(
            "Override: %s.%s = %r (from %s)", section_key, field_suffix, env_value, env_key
        )

    return raw


def _build_dataclass(cls: type, raw_section: dict | None) -> Any:
    """Construct a dataclass from a raw dict section, applying field-level defaults for missing keys.

    Coerces string values (from env var overrides) to the declared field type.
    Silently ignores unknown keys (forward-compatible).
    """
    if raw_section is None:
        return cls()  # All defaults

    field_types = {f.name: f.type for f in fields(cls)}
    # Resolve string annotations to actual types for simple scalars
    import sys
    module_globals = sys.modules[cls.__module__].__dict__

    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in raw_section:
            continue  # Let dataclass default apply

        raw_value = raw_section[f.name]

        # Resolve type annotation if it's a string (e.g., from __future__ annotations)
        declared_type = f.type
        if isinstance(declared_type, str):
            declared_type = eval(declared_type, module_globals)  # noqa: S307

        # Coerce string env-var overrides to the declared type
        if isinstance(raw_value, str) and declared_type in (int, float):
            try:
                raw_value = declared_type(raw_value)
            except (ValueError, TypeError) as exc:
                raise ConfigValidationError(
                    f"Invalid value for {cls.__name__}.{f.name}: "
                    f"cannot convert {raw_value!r} to {declared_type.__name__}: {exc}"
                ) from exc
        elif not isinstance(raw_value, str) and declared_type == str:
            raw_value = str(raw_value)

        kwargs[f.name] = raw_value

    try:
        return cls(**kwargs)
    except TypeError as exc:
        raise ConfigValidationError(
            f"Failed to construct {cls.__name__}: {exc}"
        ) from exc


def _validate_weights(weights: ScoringWeights) -> None:
    """Validate that all scoring weights are in [0, 1] and sum to 1.0."""
    weight_values = {
        "technical_momentum": weights.technical_momentum,
        "fundamental_quality": weights.fundamental_quality,
        "price_trajectory": weights.price_trajectory,
        "catalyst_strength": weights.catalyst_strength,
        "sector_favorability": weights.sector_favorability,
    }

    for name, value in weight_values.items():
        if not isinstance(value, (int, float)):
            raise ConfigValidationError(
                f"scoring_weights.{name} must be a number, got {type(value).__name__}"
            )
        if value < 0 or value > 1:
            raise ConfigValidationError(
                f"scoring_weights.{name} must be in [0, 1], got {value}"
            )

    total = sum(weight_values.values())
    deviation = abs(total - 1.0)

    if deviation >= 0.001:
        raise ConfigValidationError(
            f"Scoring weights sum to {total:.6f}, must sum to 1.0 "
            f"(allowed tolerance: 0.001). Weights: {weight_values}"
        )

    if deviation > 0.0001:
        logger.warning(
            "Scoring weights sum is close to boundary: %.6f (ideal: 1.0). "
            "Consider rounding weights for clarity.",
            total,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(config_path: "Path | str | None" = None) -> PipelineConfig:
    """Load and validate pipeline configuration from YAML.

    Args:
        config_path: Path to the YAML config file. Defaults to
                     pipeline_config.yaml in the same directory as this module.

    Returns:
        Validated PipelineConfig dataclass with all sections populated.

    Raises:
        ConfigValidationError: If the config file is missing, has invalid YAML
                               syntax, contains invalid values, or scoring weights
                               do not sum to 1.0.
    """
    if config_path is None:
        path = _DEFAULT_CONFIG_PATH
    else:
        path = Path(config_path)

    if not path.exists():
        raise ConfigValidationError(f"Config file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"Invalid YAML in {path}: {exc}") from exc

    # An empty YAML file yields None — treat as empty dict (all defaults)
    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        raise ConfigValidationError(
            f"Config file {path} must be a YAML mapping at the top level, "
            f"got {type(raw).__name__}"
        )

    # Apply environment variable overrides before constructing dataclasses
    raw = _apply_env_overrides(raw)

    try:
        universe = _build_dataclass(UniverseConfig, raw.get("universe"))
        scoring_weights = _build_dataclass(ScoringWeights, raw.get("scoring_weights"))
        shortlist = _build_dataclass(ShortlistConfig, raw.get("shortlist"))
        agents = _build_dataclass(AgentConfig, raw.get("agents"))
        output = _build_dataclass(OutputConfig, raw.get("output"))
    except ConfigValidationError:
        raise
    except Exception as exc:
        raise ConfigValidationError(f"Failed to parse config from {path}: {exc}") from exc

    _validate_weights(scoring_weights)

    config = PipelineConfig(
        universe=universe,
        scoring_weights=scoring_weights,
        shortlist=shortlist,
        agents=agents,
        output=output,
    )

    logger.info("Loaded pipeline config from %s", path)
    return config
