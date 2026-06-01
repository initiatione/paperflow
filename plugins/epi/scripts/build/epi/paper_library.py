from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from epi.artifacts import raw_papers_root
from epi.schemas import canonical_key, slugify_title


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _index_key(record: dict[str, Any]) -> list[str]:
    keys = {canonical_key(record)}
    title = str(record.get("title") or "").strip()
    if title:
        keys.add(f"title:{slugify_title(title)}")
    doi = str(record.get("doi") or "").strip().lower()
    if doi:
        keys.add(f"doi:{doi}")
    arxiv_id = str(record.get("arxiv_id") or "").strip().lower()
    if arxiv_id:
        keys.add(f"arxiv:{arxiv_id}")
    return sorted(keys)


def load_existing_paper_index(vault_path: Path) -> dict[str, Any]:
    papers_root = raw_papers_root(Path(vault_path))
    by_key: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    if not papers_root.exists():
        return {"papers_root": str(papers_root), "count": 0, "by_key": by_key, "entries": entries}

    for paper_root in sorted(path for path in papers_root.iterdir() if path.is_dir()):
        metadata = _load_json(paper_root / "metadata.json") or {}
        entry = {
            "slug": metadata.get("slug") or paper_root.name,
            "title": metadata.get("title") or paper_root.name,
            "doi": metadata.get("doi"),
            "arxiv_id": metadata.get("arxiv_id"),
            "path": str(paper_root),
        }
        entries.append(entry)
        for key in _index_key({**metadata, "title": entry["title"]}):
            by_key.setdefault(key, entry)
    return {"papers_root": str(papers_root), "count": len(entries), "by_key": by_key, "entries": entries}


def existing_library_match(candidate: dict[str, Any], index: dict[str, Any] | None) -> dict[str, Any] | None:
    if not index:
        return None
    by_key = index.get("by_key")
    if not isinstance(by_key, dict):
        return None
    for key in _index_key(candidate):
        match = by_key.get(key)
        if isinstance(match, dict):
            return {"key": key, **match}
    return None
