from __future__ import annotations

from pathlib import Path

from epi.artifacts import utc_now, write_json_atomic


def sync_zotero_record(
    paper_root: Path,
    *,
    enabled: bool,
    collection: str,
    item_key: str | None = None,
    mode: str = "record-only",
) -> dict:
    if not enabled:
        record = {
            "stage": "zotero",
            "status": "skipped",
            "reason": "zotero_disabled",
            "collection": collection,
            "synced_at": utc_now(),
        }
    else:
        record = {
            "stage": "zotero",
            "status": "recorded",
            "mode": mode,
            "collection": collection,
            "item_key": item_key,
            "synced_at": utc_now(),
            "note": "External Zotero writes are not performed by this offline record path.",
        }
    write_json_atomic(paper_root / "zotero-record.json", record)
    return record
