from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from epi.artifacts import staging_paper_root, utc_now, write_json_atomic


HUMAN_APPROVAL_SCHEMA_VERSION = "epi-human-approval-v1"
HUMAN_APPROVAL_SCOPE = "run-wiki-ingest-agent"


def human_approval_record_path(vault_path: Path, slug: str) -> Path:
    return staging_paper_root(vault_path.resolve(), slug) / "human-approval.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _gate_check_names(gate: dict[str, Any], conclusion: str) -> list[str]:
    return [
        str(run.get("name"))
        for run in gate.get("check_suite", {}).get("check_runs", [])
        if run.get("conclusion") == conclusion
    ]


def paper_gate_snapshot(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": gate.get("status"),
        "next_action": gate.get("next_action"),
        "conclusion": gate.get("check_suite", {}).get("conclusion"),
        "failure_checks": _gate_check_names(gate, "failure"),
        "action_required_checks": _gate_check_names(gate, "action_required"),
    }


def ensure_gate_allows_human_approval(gate: dict[str, Any], *, scope: str) -> None:
    snapshot = paper_gate_snapshot(gate)
    if scope != HUMAN_APPROVAL_SCOPE:
        raise ValueError(f"unsupported human approval scope: {scope}")
    if snapshot["next_action"] != HUMAN_APPROVAL_SCOPE:
        raise ValueError(
            "record-human-approval requires paper-gate next_action=run-wiki-ingest-agent; "
            f"got {snapshot['next_action'] or 'unknown'}"
        )
    if snapshot["failure_checks"]:
        raise ValueError("paper gate has failure checks: " + ", ".join(snapshot["failure_checks"]))
    if snapshot["action_required_checks"] != ["human-approval"]:
        raise ValueError(
            "record-human-approval requires the only action-required check to be human-approval; got "
            + ", ".join(snapshot["action_required_checks"])
        )


def create_human_approval_record(
    vault_path: Path,
    slug: str,
    *,
    approved_by: str,
    scope: str,
    gate: dict[str, Any],
    notes: str | None = None,
) -> dict[str, Any]:
    approved_by_value = str(approved_by or "").strip()
    if not approved_by_value:
        raise ValueError("approved-by is required for record-human-approval")
    ensure_gate_allows_human_approval(gate, scope=scope)
    record = {
        "schema_version": HUMAN_APPROVAL_SCHEMA_VERSION,
        "stage": "record-human-approval",
        "status": "approved",
        "paper_slug": slug,
        "scope": scope,
        "approved_by": approved_by_value,
        "approved_at": utc_now(),
        "paper_gate_snapshot": paper_gate_snapshot(gate),
    }
    if notes:
        record["notes"] = notes
    path = human_approval_record_path(vault_path, slug)
    write_json_atomic(path, record)
    return record


def load_human_approval_record(vault_path: Path, slug: str) -> dict[str, Any] | None:
    path = human_approval_record_path(vault_path, slug)
    if not path.exists():
        return None
    return _read_json(path)


def validate_human_approval_record(
    vault_path: Path,
    slug: str,
    *,
    approved_by: str | None = None,
    require_existing: bool = False,
) -> tuple[bool, dict[str, Any] | None, list[str]]:
    path = human_approval_record_path(vault_path, slug)
    record = load_human_approval_record(vault_path, slug)
    if record is None:
        if require_existing:
            return False, None, [f"pre-write human approval artifact is required: {path}"]
        return False, None, []

    issues: list[str] = []
    if record.get("schema_version") != HUMAN_APPROVAL_SCHEMA_VERSION:
        issues.append("human approval record has unsupported schema_version")
    if record.get("status") != "approved":
        issues.append("human approval record status must be approved")
    if record.get("paper_slug") != slug:
        issues.append("human approval record paper_slug does not match")
    if record.get("scope") != HUMAN_APPROVAL_SCOPE:
        issues.append("human approval record scope must be run-wiki-ingest-agent")
    record_approved_by = str(record.get("approved_by") or "").strip()
    if not record_approved_by:
        issues.append("human approval record approved_by is missing")
    expected_approved_by = str(approved_by or "").strip()
    if expected_approved_by and record_approved_by != expected_approved_by:
        issues.append(
            "record-wiki-ingest approved-by does not match pre-write human approval: "
            f"{expected_approved_by} != {record_approved_by}"
        )
    if not str(record.get("approved_at") or "").strip():
        issues.append("human approval record approved_at is missing")
    return not issues, record, issues
