"""Output directory utilities for the agent pipeline.

Every pipeline run writes artifacts under output/{YYYY-MM-DD}/.
This module creates that structure and resolves canonical paths for
PDFs, manifests, logs, and cache files.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Default output root: navigate from src/agents/core/ up to project root
_DEFAULT_BASE_DIR: Path = Path(__file__).resolve().parents[3] / "output"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLUG_MAX_LEN = 50


def slugify(name: str) -> str:
    """Convert a human-readable name to a filesystem-safe slug.

    Rules applied in order:
    1. Raise ValueError for empty input.
    2. Lowercase.
    3. Replace spaces and underscores with hyphens.
    4. Remove any character that is not alphanumeric or hyphen.
    5. Collapse multiple consecutive hyphens into one.
    6. Strip leading/trailing hyphens.
    7. Truncate to 50 characters.

    Examples:
        "Information Technology" -> "information-technology"
        "Health Care"            -> "health-care"
        "S&P 500"                -> "sp-500"
        "Real Estate"            -> "real-estate"

    Args:
        name: Human-readable name to slugify.

    Returns:
        Lowercase, hyphen-separated slug safe for filenames.

    Raises:
        ValueError: If name is empty or results in an empty slug.
    """
    if not name or not name.strip():
        raise ValueError("Cannot slugify empty string")

    slug = name.lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    slug = slug[:_SLUG_MAX_LEN]

    if not slug:
        raise ValueError(f"Cannot slugify {name!r}: result is empty after sanitization")

    return slug


def _resolve_base(base_dir: "Path | str | None") -> Path:
    """Return the resolved base directory, falling back to the default."""
    if base_dir is None:
        return _DEFAULT_BASE_DIR
    return Path(base_dir)


def _validate_date(run_date: str) -> None:
    """Validate run_date is YYYY-MM-DD format and a real calendar date."""
    if not _DATE_RE.match(run_date):
        raise ValueError(
            f"Invalid date format: {run_date!r}. Expected YYYY-MM-DD."
        )
    try:
        datetime.strptime(run_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date value: {run_date!r}. Not a real calendar date."
        )


def ensure_run_directory(
    run_date: str,
    base_dir: "Path | str | None" = None,
) -> Path:
    """Create the complete output directory tree for a pipeline run.

    Creates (idempotent):
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
        ValueError: If run_date is not a valid YYYY-MM-DD date string.
        OSError: If directory creation fails (e.g., permission denied).
    """
    _validate_date(run_date)
    base = _resolve_base(base_dir)
    run_dir = base / run_date

    if run_dir.exists():
        logger.debug("Run directory already exists: %s", run_dir)
    else:
        run_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created run directory: %s", run_dir)

    for subdir in ("sectors", "aggregate", ".cache"):
        path = run_dir / subdir
        path.mkdir(exist_ok=True)
        logger.debug("Ensured subdirectory: %s", path)

    return run_dir


def get_sector_pdf_path(
    run_date: str,
    sector_name: str,
    base_dir: "Path | str | None" = None,
) -> Path:
    """Return the expected path for a sector PDF report.

    The directory is not created by this function — call
    ensure_run_directory() first.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        sector_name: Human-readable sector name (will be slugified).
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/sectors/information-technology.pdf
    """
    _validate_date(run_date)
    base = _resolve_base(base_dir)
    slug = slugify(sector_name)
    return base / run_date / "sectors" / f"{slug}.pdf"


def get_aggregate_pdf_path(
    run_date: str,
    base_dir: "Path | str | None" = None,
) -> Path:
    """Return the expected path for the aggregate daily PDF report.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/aggregate/daily_opportunities_2026-02-28.pdf
    """
    _validate_date(run_date)
    base = _resolve_base(base_dir)
    return base / run_date / "aggregate" / f"daily_opportunities_{run_date}.pdf"


def get_manifest_path(
    run_date: str,
    base_dir: "Path | str | None" = None,
) -> Path:
    """Return the expected path for the run manifest JSON file.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/manifest.json
    """
    _validate_date(run_date)
    base = _resolve_base(base_dir)
    return base / run_date / "manifest.json"


def get_log_path(
    run_date: str,
    base_dir: "Path | str | None" = None,
) -> Path:
    """Return the expected path for the pipeline log file.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/pipeline.log
    """
    _validate_date(run_date)
    base = _resolve_base(base_dir)
    return base / run_date / "pipeline.log"


def get_cache_dir(
    run_date: str,
    base_dir: "Path | str | None" = None,
) -> Path:
    """Return the path to the cache directory for a run.

    Args:
        run_date: Date string in YYYY-MM-DD format.
        base_dir: Override the default output base directory.

    Returns:
        Path like: output/2026-02-28/.cache/
    """
    _validate_date(run_date)
    base = _resolve_base(base_dir)
    return base / run_date / ".cache"
