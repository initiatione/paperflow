from __future__ import annotations

import json
from pathlib import Path

from paper_source.artifacts import read_json_dict


GRAPH_IGNORE_FILTERS: tuple[str, ...] = (
    "_epi/",
    "_paper_source/",
    "_meta/",
    ".claude/",
    "AGENTS.md",
    "hot.md",
    "log.md",
)


def graph_search_filter(knowledge_dirs: list[str] | tuple[str, ...]) -> str:
    """Keep graph scope out of Obsidian search; app ignore filters carry it."""
    _ = knowledge_dirs
    return ""


def _merged_ignore_filters(existing: object) -> list[str]:
    filters = [item for item in existing if isinstance(item, str)] if isinstance(existing, list) else []
    for required in GRAPH_IGNORE_FILTERS:
        if required not in filters:
            filters.append(required)
    return filters


def sync_graph_json(path: Path, knowledge_dirs: list[str] | tuple[str, ...], created: list[str]) -> None:
    if path.exists():
        payload = read_json_dict(path, default={}) or {}
    else:
        payload = {}
    expected_search = graph_search_filter(knowledge_dirs)
    previous_search = str(payload.get("search") or "")
    previous_collapse_filter = payload.get("collapse-filter")
    payload["collapse-filter"] = True
    payload["search"] = expected_search
    if not path.exists() or previous_search != expected_search or previous_collapse_filter is not True:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(".obsidian/graph.json")


def sync_app_json(path: Path, created: list[str]) -> None:
    if path.exists():
        payload = read_json_dict(path, default={}) or {}
    else:
        payload = {}
    previous = payload.get("userIgnoreFilters")
    merged = _merged_ignore_filters(previous)
    payload["userIgnoreFilters"] = merged
    if not path.exists() or previous != merged:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(".obsidian/app.json")
