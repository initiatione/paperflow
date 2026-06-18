#!/usr/bin/env python3
"""Report selected environment variables without exposing secret values."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


DEFAULT_VARS = [
    "MINERU_TOKEN",
    "EASYSCHOLAR_SECRET_KEY",
    "OPENAI_COMPATIBLE_API_URL",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_COMPATIBLE_MODEL",
    "PAPER_SOURCE_GROK_MODEL_FALLBACKS",
    "PAPER_SOURCE_GROK_PARALLEL_GRACE_SECONDS",
    "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL",
    "PAPER_SEARCH_MCP_CORE_API_KEY",
    "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY",
    "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL",
    "PAPER_SEARCH_MCP_DOAJ_API_KEY",
    "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN",
]

SECRET_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASS|AUTH|COOKIE|BEARER)", re.I)


def is_secret(name: str) -> bool:
    return bool(SECRET_RE.search(name))


def parse_env_line(line: str) -> Tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.lower().startswith("export "):
        stripped = stripped[7:].strip()
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_env_file(path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    values: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors[str(path)] = f"{type(exc).__name__}: {exc}"
        return values, errors

    for line in text.splitlines():
        parsed = parse_env_line(line)
        if parsed:
            key, value = parsed
            values[key] = value
    return values, errors


def classify_value(name: str, value: str | None, include_values: bool) -> Dict[str, object]:
    status = "set" if value else "missing"
    item: Dict[str, object] = {"status": status, "secret": is_secret(name)}
    if status == "set":
        item["length"] = len(value or "")
        if item["secret"]:
            item["value"] = "<redacted>"
        elif include_values:
            item["value"] = value
    return item


def collect_sources(env_files: Iterable[Path]) -> Tuple[Dict[str, str], Dict[str, List[str]], Dict[str, str]]:
    merged: Dict[str, str] = {}
    sources: Dict[str, List[str]] = {}
    errors: Dict[str, str] = {}

    for key, value in os.environ.items():
        merged[key] = value
        sources.setdefault(key, []).append("process")

    for path in env_files:
        values, file_errors = load_env_file(path)
        errors.update(file_errors)
        for key, value in values.items():
            merged[key] = value
            sources.setdefault(key, []).append(str(path))

    return merged, sources, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", action="append", default=[], help="Optional dotenv-style env file")
    parser.add_argument("--var", action="append", default=[], help="Variable to include in addition to defaults")
    parser.add_argument("--only-var", action="append", default=[], help="Use only these variable names")
    parser.add_argument("--include-values", action="store_true", help="Show non-secret values")
    args = parser.parse_args()

    names = args.only_var or [*DEFAULT_VARS, *args.var]
    names = list(dict.fromkeys(names))
    env_files = [Path(value).expanduser() for value in args.env_file]
    merged, sources, errors = collect_sources(env_files)

    variables = {}
    for name in names:
        item = classify_value(name, merged.get(name), args.include_values)
        if name in sources:
            item["sources"] = sources[name]
        variables[name] = item

    print(
        json.dumps(
            {
                "schema": "paperflow-redacted-env-status-v1",
                "env_files": [str(path) for path in env_files],
                "env_file_errors": errors,
                "variables": variables,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
