from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-wiki-zotero-sync-report-v1"
ITEM_OUTCOMES = {"linked", "imported", "skipped", "conflict", "failed", "unavailable"}
GATE_CODES = {
    "zotero_plugin_missing",
    "zotero_helper_incompatible",
    "zotero_desktop_unavailable",
    "local_api_disabled",
    "connector_unavailable",
    "selected_target_mismatch",
    "invalid_frontmatter",
    "invalid_metadata",
    "validation_rejected",
    "conflict_multiple_zotero_items",
    "conflict_multiple_wiki_pages",
}
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|proxy)(=|:)[^\s\"']+"
)
PRIVATE_ENDPOINT_PATTERN = re.compile(r"https?://[^\s\"']*(?:token|key|secret|proxy)[^\s\"']*", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(value: str) -> str:
    text = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", value)
    return PRIVATE_ENDPOINT_PATTERN.sub("<redacted-url>", text)


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if re.search(r"(?i)(token|secret|password|api[_-]?key|authorization)", str(key)):
                sanitized[key] = "<redacted>"
            else:
                sanitized[key] = sanitize(item)
        return sanitized
    return value


def build_zotero_sync_report(
    *,
    run_id: str,
    mode: str,
    vault: Path | str,
    target_collection: str = "Paper Wiki",
    zotero_helper: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
    gates: list[dict[str, Any]] | None = None,
    metadata_provenance: list[dict[str, Any]] | None = None,
    snapshots: list[dict[str, Any]] | None = None,
    bibtex: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": mode,
        "vault": str(vault),
        "target_collection": target_collection,
        "created_at": created_at or utc_now(),
        "zotero_helper": zotero_helper or {"ok": False, "gate": "not_checked"},
        "summary": summary or {},
        "items": items or [],
        "gates": gates or [],
        "metadata_provenance": metadata_provenance or [],
        "snapshots": snapshots or [],
        "bibtex": bibtex or {"path": None, "entry_count": 0, "diagnostics": {}},
    }
    return sanitize(report)


def validate_zotero_sync_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required = {
        "schema_version",
        "run_id",
        "mode",
        "vault",
        "target_collection",
        "created_at",
        "zotero_helper",
        "summary",
        "items",
        "gates",
        "metadata_provenance",
        "snapshots",
        "bibtex",
    }
    missing = sorted(required - set(report))
    if missing:
        issues.append({"code": "missing_required_fields", "fields": missing})
    if report.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            {
                "code": "invalid_schema_version",
                "expected": SCHEMA_VERSION,
                "actual": report.get("schema_version"),
            }
        )
    for index, item in enumerate(report.get("items") or []):
        outcome = item.get("outcome")
        if outcome not in ITEM_OUTCOMES:
            issues.append(
                {
                    "code": "invalid_item_outcome",
                    "index": index,
                    "value": outcome,
                    "allowed": sorted(ITEM_OUTCOMES),
                }
            )
    for index, gate in enumerate(report.get("gates") or []):
        code = gate.get("gate") or gate.get("code")
        if code not in GATE_CODES:
            issues.append(
                {
                    "code": "invalid_gate_code",
                    "index": index,
                    "value": code,
                    "allowed": sorted(GATE_CODES),
                }
            )
    return issues
