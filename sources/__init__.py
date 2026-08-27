"""
Auto-added source registry.

Each entry in `_registry.json` points to a Python module in this package that
exports:
- `SOURCE`  : dict with {name, url, base_url, color, org_type}
- `scrape(source)` : callable returning a list of post dicts, same shape as
  the hand-written scrapers in app.py.

This split keeps hand-tuned scrapers in app.py untouched. Auto-generated
scrapers live here in quarantine where they can be reviewed or deleted
without risk to the core file.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).parent
_REGISTRY_PATH = _PACKAGE_DIR / "_registry.json"

# Module names must be safe Python identifiers to prevent import-path shenanigans
# (e.g. "../etc/passwd") from arriving via the registry file.
_MODULE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _load_registry() -> list[dict[str, Any]]:
    if not _REGISTRY_PATH.exists():
        return []
    try:
        with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.error("sources/_registry.json is not a list; ignoring")
            return []
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"sources/_registry.json unreadable: {e}")
        return []


def _save_registry(entries: list[dict[str, Any]]) -> None:
    tmp = _REGISTRY_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    tmp.replace(_REGISTRY_PATH)


def load_all() -> tuple[list[dict[str, Any]], dict[str, Callable]]:
    """Import every auto-added source module and return (sources, scrapers).

    Modules that fail to import or don't expose the expected symbols are
    logged and skipped - one bad file must not brick the whole app.
    """
    sources: list[dict[str, Any]] = []
    scrapers: dict[str, Callable] = {}

    for entry in _load_registry():
        module_name = entry.get("module")
        if not module_name or not _MODULE_NAME_RE.match(module_name):
            logger.warning(f"[sources] Skipping bad module name: {module_name!r}")
            continue

        module_path = _PACKAGE_DIR / f"{module_name}.py"
        if not module_path.is_file():
            logger.warning(f"[sources] Registry references missing file: {module_path.name}")
            continue

        full_name = f"sources.{module_name}"
        try:
            if full_name in sys.modules:
                mod = importlib.reload(sys.modules[full_name])
            else:
                mod = importlib.import_module(full_name)
        except Exception as e:
            logger.error(f"[sources] Import failed for {module_name}: {type(e).__name__}: {e}")
            continue

        source = getattr(mod, "SOURCE", None)
        scrape_fn = getattr(mod, "scrape", None)
        if not isinstance(source, dict) or not callable(scrape_fn):
            logger.warning(f"[sources] {module_name} missing SOURCE dict or scrape() fn")
            continue

        required = {"name", "url", "base_url", "color"}
        if not required.issubset(source.keys()):
            logger.warning(f"[sources] {module_name} SOURCE missing keys: {required - source.keys()}")
            continue

        source.setdefault("org_type", "company")
        sources.append(source)
        scrapers[source["name"]] = scrape_fn
        logger.info(f"[sources] Loaded auto-added source: {source['name']} ({module_name})")

    return sources, scrapers


def register(module_name: str, source: dict[str, Any]) -> None:
    """Append a new source to the registry file. Overwrites if module_name already exists."""
    if not _MODULE_NAME_RE.match(module_name):
        raise ValueError(f"Invalid module name: {module_name!r}")

    entries = _load_registry()
    entries = [e for e in entries if e.get("module") != module_name]
    entries.append({
        "module": module_name,
        "name": source["name"],
        "url": source["url"],
        "base_url": source["base_url"],
        "color": source["color"],
        "org_type": source.get("org_type", "company"),
    })
    _save_registry(entries)


def slugify_module_name(name: str) -> str:
    """Convert a display name into a safe python module identifier.

    "Perceptron Labs!" -> "perceptron_labs"
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not slug or not slug[0].isalpha():
        slug = "src_" + slug
    return slug[:64]
