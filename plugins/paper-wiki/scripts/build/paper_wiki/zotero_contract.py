from __future__ import annotations

from typing import Any


ALLOWED_SYNC_STATUSES = (
    "unlinked",
    "linked",
    "imported",
    "skipped",
    "conflict",
    "zotero_unavailable",
)
REFERENCE_INDEX_ZOTERO_FIELDS = (
    "sync_status",
    "item_key",
    "bibtex_key",
    "collection",
    "identity_basis",
    "synced_at",
    "last_checked_at",
)
BIBTEX_ELIGIBLE_STATUSES = {"linked", "imported"}


def normalize_zotero_metadata(value: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if value is None or value == "":
        return None, issues
    if not isinstance(value, dict):
        return None, [
            {
                "code": "zotero_metadata_not_mapping",
                "message": "frontmatter zotero metadata must be a mapping.",
            }
        ]
    status = str(value.get("sync_status") or "").strip()
    if not status:
        return None, [
            {
                "code": "zotero_sync_status_missing",
                "message": "frontmatter zotero.sync_status is required when zotero metadata is present.",
            }
        ]
    if status not in ALLOWED_SYNC_STATUSES:
        return None, [
            {
                "code": "zotero_sync_status_invalid",
                "field": "zotero.sync_status",
                "value": status,
                "allowed": list(ALLOWED_SYNC_STATUSES),
            }
        ]
    normalized: dict[str, Any] = {"sync_status": status}
    for field in REFERENCE_INDEX_ZOTERO_FIELDS[1:]:
        raw = value.get(field)
        if raw is None or raw == "":
            continue
        normalized[field] = str(raw).strip()
    return normalized, issues


def validate_zotero_metadata(value: Any) -> list[dict[str, Any]]:
    _metadata, issues = normalize_zotero_metadata(value)
    return issues


def is_bibtex_eligible(value: Any) -> bool:
    metadata, _issues = normalize_zotero_metadata(value)
    if not metadata:
        return False
    return (
        metadata.get("sync_status") in BIBTEX_ELIGIBLE_STATUSES
        and bool(str(metadata.get("item_key") or "").strip())
    )
