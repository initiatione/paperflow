from __future__ import annotations

import json
from pathlib import Path

from paper_source.artifacts import read_json_dict


def graph_search_filter(knowledge_dirs: list[str] | tuple[str, ...]) -> str:
    return "path:/^index\\.md$/ OR " + " OR ".join(
        f"path:/^{directory}\\\\//" for directory in knowledge_dirs
    )


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
