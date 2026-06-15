from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from paper_source.artifacts import raw_papers_root
from paper_source.schemas import slugify_title


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_doi(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = re.sub(r"^doi:\s*", "", text)
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = text.strip().rstrip(".,;)")
    return text or None


def _normalize_arxiv_base_id(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = re.sub(r"^arxiv:\s*", "", text)
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text)
    text = text.removesuffix(".pdf").strip().rstrip(".,;)")
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", text)
    if match:
        return match.group(1)
    match = re.search(r"([a-z-]+(?:\.[a-z-]+)?/\d{7})(?:v\d+)?", text)
    if match:
        return match.group(1)
    if text.endswith(tuple(f"v{number}" for number in range(1, 10))):
        return re.sub(r"v\d+$", "", text)
    return text or None


def _normalize_source_id(value: object) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _normalize_title(value: object) -> str | None:
    title = str(value or "").strip()
    if title:
        return slugify_title(title)
    return None


def _dedupe_key_from_text(value: object) -> str | None:
    text = str(value or "").strip()
    if ":" not in text:
        return None
    prefix, raw_value = text.split(":", 1)
    prefix = prefix.strip().lower()
    if prefix == "doi":
        normalized = _normalize_doi(raw_value)
        return f"doi:{normalized}" if normalized else None
    if prefix == "arxiv":
        normalized = _normalize_arxiv_base_id(raw_value)
        return f"arxiv:{normalized}" if normalized else None
    if prefix == "source_id":
        normalized = _normalize_source_id(raw_value)
        return f"source_id:{normalized}" if normalized else None
    if prefix == "title":
        normalized = _normalize_title(raw_value)
        return f"title:{normalized}" if normalized else None
    return None


def _index_keys(record: dict[str, Any], *, include_existing_dedupe_keys: bool = False) -> list[str]:
    keys: list[str] = []

    def add(key: str | None) -> None:
        if key and key not in keys:
            keys.append(key)

    doi = _normalize_doi(record.get("doi"))
    add(f"doi:{doi}" if doi else None)

    arxiv_base_id = _normalize_arxiv_base_id(record.get("arxiv_base_id") or record.get("arxiv_id") or record.get("url"))
    add(f"arxiv:{arxiv_base_id}" if arxiv_base_id else None)

    source_id = _normalize_source_id(record.get("source_id") or record.get("slug"))
    add(f"source_id:{source_id}" if source_id else None)

    title = _normalize_title(record.get("normalized_title") or record.get("title"))
    add(f"title:{title}" if title else None)

    if include_existing_dedupe_keys and isinstance(record.get("dedupe_keys"), list):
        for value in record.get("dedupe_keys") or []:
            add(_dedupe_key_from_text(value))

    return keys


def _load_reference_index_entries(vault_path: Path) -> tuple[Path, dict[str, Any] | None, list[dict[str, Any]]]:
    path = Path(vault_path).resolve() / "_meta" / "reference-index.json"
    payload = _load_json(path)
    raw_entries = payload.get("entries") if isinstance(payload, dict) else None
    entries = raw_entries if isinstance(raw_entries, list) else []
    normalized_entries: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id")
        entry = {
            "source_type": "wiki_reference_index",
            "slug": source_id or slugify_title(str(item.get("title") or "untitled-paper")),
            "source_id": source_id,
            "title": item.get("title") or item.get("normalized_title") or "Untitled paper",
            "doi": item.get("doi"),
            "arxiv_id": item.get("arxiv_id"),
            "arxiv_base_id": item.get("arxiv_base_id"),
            "page": item.get("page"),
            "canonical_pdf": item.get("canonical_pdf"),
            "path": item.get("page"),
            "status": item.get("status"),
            "dedupe_keys": item.get("dedupe_keys") if isinstance(item.get("dedupe_keys"), list) else [],
        }
        normalized_entries.append(entry)
    return path, payload, normalized_entries


def load_existing_paper_index(vault_path: Path) -> dict[str, Any]:
    vault_path = Path(vault_path)
    papers_root = raw_papers_root(Path(vault_path))
    by_key: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    reference_index_path, reference_payload, reference_entries = _load_reference_index_entries(vault_path)

    for entry in reference_entries:
        entries.append(entry)
        for key in _index_keys(entry, include_existing_dedupe_keys=True):
            by_key.setdefault(key, entry)

    raw_entries: list[dict[str, Any]] = []
    if papers_root.exists():
        for paper_root in sorted(path for path in papers_root.iterdir() if path.is_dir()):
            metadata = _load_json(paper_root / "metadata.json") or {}
            entry = {
                "source_type": "raw_library",
                "slug": metadata.get("slug") or paper_root.name,
                "source_id": metadata.get("source_id") or metadata.get("slug") or paper_root.name,
                "title": metadata.get("title") or paper_root.name,
                "doi": metadata.get("doi"),
                "arxiv_id": metadata.get("arxiv_id"),
                "path": str(paper_root),
            }
            raw_entries.append(entry)
            entries.append(entry)
            for key in _index_keys({**metadata, "title": entry["title"], "slug": entry["slug"]}):
                by_key.setdefault(key, entry)
    reference_status = "missing"
    if reference_payload is not None:
        reference_status = "loaded"
    return {
        "papers_root": str(papers_root),
        "reference_index_path": str(reference_index_path),
        "reference_index_status": reference_status,
        "reference_index_schema": (reference_payload or {}).get("schema_version") if reference_payload else None,
        "count": len(entries),
        "raw_count": len(raw_entries),
        "wiki_count": len(reference_entries),
        "by_key": by_key,
        "entries": entries,
    }


def existing_library_match(candidate: dict[str, Any], index: dict[str, Any] | None) -> dict[str, Any] | None:
    if not index:
        return None
    by_key = index.get("by_key")
    if not isinstance(by_key, dict):
        return None
    for key in _index_keys(candidate):
        match = by_key.get(key)
        if isinstance(match, dict):
            return {"key": key, **match}
    return None
