from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_source.artifacts import read_json_dict, utc_now, write_json_atomic


def _metadata_snapshot(paper_root: Path) -> dict[str, Any]:
    metadata = read_json_dict(paper_root / "metadata.json", default={}) or {}
    keys = ["slug", "title", "doi", "arxiv_id", "venue", "year", "authors", "pdf_url"]
    return {key: metadata[key] for key in keys if key in metadata}


def _wiki_ingest_snapshot(paper_root: Path) -> dict[str, Any]:
    record_path = paper_root / "wiki-ingest-record.json"
    record = read_json_dict(record_path, default={}) or {}
    if not record:
        return {"status": "not_recorded", "record_path": str(record_path), "final_wiki_pages": []}
    return {
        "status": record.get("status"),
        "record_path": str(record_path),
        "wiki_write_model": record.get("wiki_write_model"),
        "source_first_confirmed": record.get("source_first_confirmed"),
        "final_wiki_pages": record.get("page_records") or [],
    }


def sync_zotero_record(
    paper_root: Path,
    *,
    enabled: bool,
    collection: str,
    item_key: str | None = None,
    mode: str = "record-only",
    reason: str | None = None,
) -> dict:
    paper_root = paper_root.resolve()
    synced_at = utc_now()
    base = {
        "schema_version": "paper-source-zotero-record-v1",
        "stage": "zotero",
        "paper_slug": paper_root.name,
        "collection": collection,
        "synced_at": synced_at,
        "record_only": True,
        "paper_metadata": _metadata_snapshot(paper_root),
        "wiki_ingest": _wiki_ingest_snapshot(paper_root),
        "evidence_paths": {
            "paper_root": str(paper_root),
            "metadata": str(paper_root / "metadata.json"),
            "pdf": str(paper_root / "paper.pdf"),
            "wiki_ingest_record": str(paper_root / "wiki-ingest-record.json"),
        },
    }
    if not enabled:
        record = {
            **base,
            "status": "skipped",
            "reason": reason or "zotero_disabled",
        }
    else:
        record = {
            **base,
            "status": "recorded",
            "mode": mode,
            "item_key": item_key,
            "note": "External Zotero writes are not performed by this offline record path.",
        }
    write_json_atomic(paper_root / "zotero-record.json", record)
    return record
