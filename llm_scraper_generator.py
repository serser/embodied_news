"""
LLM fallback scraper generator.

When the generic scraper (RSS -> Next.js -> HTML heuristics) can't extract
posts cleanly, we ask MiMo to write a bespoke scraper following the same
conventions as the hand-written functions in app.py.

Every LLM response is:
1. Extracted from a fenced code block.
2. Parsed via ast.parse() to reject syntax errors before disk write.
3. Walked to enforce an import allowlist - LLM cannot import `os`,
   `subprocess`, `socket`, or anything else that could touch the host.
4. Written to sources/<module>.py.
5. Loaded via importlib and executed against the live URL. If it raises
   or returns < 1 post, the file is deleted and an error is returned.

The prompt shows the LLM three reference scrapers (JSON API, Next.js
__NEXT_DATA__, plain HTML) so it can match the local style.
"""

from __future__ import annotations

import ast
import logging
import os
import re
import textwrap
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI

logger = logging.getLogger(__name__)

MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5-pro"
MAX_HTML_CHARS = 60_000

ALLOWED_IMPORTS = {
    "re", "json", "datetime", "logging",
    "urllib.parse",
    "requests",
    "bs4",
}

ALLOWED_FROM_IMPORTS = {
    "datetime": {"datetime", "timedelta", "timezone"},
    "urllib.parse": {"urljoin", "urlparse", "parse_qs", "unquote", "quote"},
    "bs4": {"BeautifulSoup"},
}

FORBIDDEN_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "input",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "breakpoint", "help",
}


class LLMGenerationError(Exception):
    pass


def _get_client() -> OpenAI:
    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise LLMGenerationError("MIMO_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key, base_url=MIMO_BASE_URL)


def _fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text


SYSTEM_PROMPT = """You are a Python scraping-code generator. Your only job is to write a single Python module that scrapes a blog listing page.

The module MUST contain:
  1. A module-level dict named `SOURCE` with keys: name, url, base_url, color, org_type.
  2. A function `scrape(source: dict) -> list[dict]` that returns post dicts with keys:
     title (str), url (absolute str), date (datetime), summary (str), image (str|None), company (str).

Hard rules:
  - Only import from this allowlist: re, json, datetime, logging, urllib.parse, requests, bs4.
    (`from bs4 import BeautifulSoup`, `from datetime import datetime`, `from urllib.parse import urljoin, urlparse, parse_qs, unquote` are fine.)
  - NEVER import os, sys, subprocess, socket, pickle, importlib, io, pathlib, or shutil.
  - NEVER use eval, exec, compile, __import__, open(), or global/local reflection.
  - NEVER call open() or write to disk. Only network I/O via requests.get().
  - Use datetime.min when a date is unknown so posts sort to the bottom.
  - Absolute URLs only in the returned dicts. Prepend base_url if needed.
  - Timeout on requests: pass timeout=20 to requests.get.
  - Set a browser User-Agent header on every requests.get call.

Output format: return ONLY the Python code, wrapped in ONE ```python ... ``` fenced block. No prose before or after."""


USER_PROMPT_TEMPLATE = """Write a scraper for this blog page.

URL:      {url}
Name:     {name}
BaseURL:  {base_url}
Color:    {color}
OrgType:  {org_type}

Here is a truncated snapshot of the page HTML (first {html_chars} chars):

```html
{html}
```

Requirements:
  - Set SOURCE = {source_repr}
  - Implement scrape(source) that fetches source["url"] and returns >= 1 post dict.
  - Use BeautifulSoup for parsing. Try to look at the HTML structure and pick stable selectors.
  - If the site is Next.js (look for <script id="__NEXT_DATA__">), parse that JSON.
  - If the page has an RSS/Atom feed or a JSON API endpoint you can identify, use it instead.
  - If you have to fall back to CSS-class selectors, prefer semantic tags (article, h1-h4, time) over brittle utility classes.
  - Log a single line at end: `logger.info(f"[{{company}}] Scraped {{n}} posts")` where company = source["name"].

Return the module code now."""


def build_prompt(url: str, name: str, base_url: str, color: str, org_type: str, html: str) -> str:
    trimmed = html[:MAX_HTML_CHARS]
    source_repr = repr({
        "name": name,
        "url": url,
        "base_url": base_url,
        "color": color,
        "org_type": org_type,
    })
    return USER_PROMPT_TEMPLATE.format(
        url=url, name=name, base_url=base_url, color=color, org_type=org_type,
        html_chars=len(trimmed), html=trimmed, source_repr=source_repr,
    )


_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(response_text: str) -> str:
    m = _CODE_FENCE_RE.search(response_text)
    if not m:
        text = response_text.strip()
        if text.startswith("import ") or text.startswith("from ") or text.startswith('"""'):
            return text
        raise LLMGenerationError("LLM response contained no fenced code block")
    return m.group(1).strip()


def _import_allowed(module: str, names: list[str] | None = None) -> tuple[bool, str]:
    """Enforce the import allowlist.

    - `import X`         : X must be in ALLOWED_IMPORTS
    - `from X import a,b`: X must be in ALLOWED_IMPORTS AND every name in
                           ALLOWED_FROM_IMPORTS[X] (or `*`-import blocked).
    Returns (ok, reason).
    """
    root = module.split(".")[0]
    if module not in ALLOWED_IMPORTS and root not in ALLOWED_IMPORTS:
        return False, f"import {module!r} is not allowed"
    if names is not None:
        allowed_names = ALLOWED_FROM_IMPORTS.get(module) or ALLOWED_FROM_IMPORTS.get(root)
        if allowed_names is None:
            return False, f"from {module!r} import ... has no allowed names"
        for n in names:
            if n == "*":
                return False, f"from {module} import * is not allowed"
            if n not in allowed_names:
                return False, f"from {module} import {n} is not allowed"
    return True, ""


def validate_code(code: str) -> None:
    """AST-based static check. Raises LLMGenerationError on any violation."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise LLMGenerationError(f"Generated code has a syntax error: {e}") from e

    has_source = False
    has_scrape = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                ok, reason = _import_allowed(alias.name)
                if not ok:
                    raise LLMGenerationError(f"Forbidden import: {reason}")

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [a.name for a in node.names]
            ok, reason = _import_allowed(module, names)
            if not ok:
                raise LLMGenerationError(f"Forbidden import: {reason}")

        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise LLMGenerationError(f"Forbidden name used: {node.id}")

        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
                raise LLMGenerationError("Access to __builtins__ is not allowed")
            if node.attr.startswith("__") and node.attr not in {"__name__", "__doc__"}:
                if node.attr in {"__class__", "__bases__", "__subclasses__", "__globals__", "__code__", "__import__"}:
                    raise LLMGenerationError(f"Access to dunder attribute {node.attr!r} not allowed")

        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "SOURCE":
                    has_source = True

        elif isinstance(node, ast.FunctionDef) and node.name == "scrape":
            has_scrape = True

    if not has_source:
        raise LLMGenerationError("Generated module is missing top-level SOURCE dict")
    if not has_scrape:
        raise LLMGenerationError("Generated module is missing scrape() function")


def generate_scraper_code(
    url: str,
    name: str,
    base_url: str,
    color: str,
    org_type: str,
) -> str:
    """Fetch the page, prompt MiMo, validate, and return the code string.

    Raises LLMGenerationError on any failure (network, empty response,
    validation reject, missing key).
    """
    try:
        html = _fetch_page(url)
    except requests.RequestException as e:
        raise LLMGenerationError(f"Failed to fetch {url}: {e}") from e

    client = _get_client()
    user_prompt = build_prompt(url, name, base_url, color, org_type, html)

    logger.info(f"[llm] requesting scraper from MiMo for {url}")
    try:
        completion = client.chat.completions.create(
            model=MIMO_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=4096,
            temperature=0.2,
            top_p=0.95,
        )
    except Exception as e:
        raise LLMGenerationError(f"MiMo API call failed: {type(e).__name__}: {e}") from e

    if not completion.choices:
        raise LLMGenerationError("MiMo returned no choices")
    content = completion.choices[0].message.content or ""
    if not content.strip():
        raise LLMGenerationError("MiMo returned empty content")

    code = extract_code(content)
    validate_code(code)
    return code


def save_scraper_module(module_name: str, code: str, sources_dir: Path) -> Path:
    """Write validated code to sources/<module_name>.py. Returns the path.

    Sanity-check that the module name is a safe python identifier BEFORE
    touching the filesystem so a malformed name can't escape sources_dir.
    """
    if not re.match(r"^[a-z][a-z0-9_]{0,63}$", module_name):
        raise LLMGenerationError(f"Invalid module name: {module_name!r}")
    header = textwrap.dedent(f'''\
        """Auto-generated scraper for {module_name}. Do not hand-edit unless you know what you're doing;
        regenerate via the admin form to replace this file.
        """
        ''')
    target = sources_dir / f"{module_name}.py"
    target.write_text(header + code + "\n", encoding="utf-8")
    return target
