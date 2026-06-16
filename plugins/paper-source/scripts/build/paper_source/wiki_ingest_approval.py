from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_source.artifacts import read_json_dict, staging_paper_root, utc_now, write_json_atomic


HUMAN_APPROVAL_SCHEMA_VERSION = "paper-source-human-approval-v1"
ACCEPTED_HUMAN_APPROVAL_SCHEMA_VERSIONS = {
    HUMAN_APPROVAL_SCHEMA_VERSION,
}
HUMAN_APPROVAL_SCOPE = "run-wiki-ingest-agent"
CODEX_AUTOMATION_ACTOR_PREFIX = "codex-automation:"


def human_approval_record_path(vault_path: Path, slug: str) -> Path:
    return staging_paper_root(vault_path.resolve(), slug) / "human-approval.json"


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
    automation_mode: str | None = None,
    automation_task_id: str | None = None,
    automation_task_source: str | None = None,
    automation_authorization: str | None = None,
) -> dict[str, Any]:
    approved_by_value = str(approved_by or "").strip()
    if not approved_by_value:
        raise ValueError("approved-by is required for record-human-approval")
    ensure_gate_allows_human_approval(gate, scope=scope)
    automation = _automation_payload(
        approved_by=approved_by_value,
        mode=automation_mode,
        task_id=automation_task_id,
        task_source=automation_task_source,
        authorization=automation_authorization,
        slug=slug,
        scope=scope,
        gate=gate,
    )
    record = {
        "schema_version": HUMAN_APPROVAL_SCHEMA_VERSION,
        "stage": "record-human-approval",
        "status": "approved",
        "paper_slug": slug,
        "scope": scope,
        "approved_by": approved_by_value,
        "approval_actor_type": "codex-automation" if automation else "human",
        "approved_at": utc_now(),
        "paper_gate_snapshot": paper_gate_snapshot(gate),
    }
    if automation:
        record["automation"] = automation
    if notes:
        record["notes"] = notes
    path = human_approval_record_path(vault_path, slug)
    write_json_atomic(path, record)
    return record


def _automation_payload(
    *,
    approved_by: str,
    mode: str | None,
    task_id: str | None,
    task_source: str | None,
    authorization: str | None,
    slug: str,
    scope: str,
    gate: dict[str, Any],
) -> dict[str, Any] | None:
    values = [mode, task_id, task_source, authorization]
    if not any(str(value or "").strip() for value in values):
        return None
    mode_value = str(mode or "").strip()
    task_id_value = str(task_id or "").strip()
    task_source_value = str(task_source or "").strip()
    authorization_value = str(authorization or "").strip()
    missing = [
        name
        for name, value in {
            "automation-mode": mode_value,
            "automation-task-id": task_id_value,
            "automation-task-source": task_source_value,
            "automation-authorization": authorization_value,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError("automation approval requires " + ", ".join(missing))
    expected_actor = f"{CODEX_AUTOMATION_ACTOR_PREFIX}{task_id_value}"
    if approved_by != expected_actor:
        raise ValueError(f"automation approved-by must be {expected_actor}")
    return {
        "mode": mode_value,
        "task_id": task_id_value,
        "task_source": task_source_value,
        "original_authorization": authorization_value,
        "authorized_at": utc_now(),
        "handoff_context": {
            "paper_slug": slug,
            "approval_scope": scope,
            "paper_gate_snapshot": paper_gate_snapshot(gate),
        },
    }


def load_human_approval_record(vault_path: Path, slug: str) -> dict[str, Any] | None:
    path = human_approval_record_path(vault_path, slug)
    if not path.exists():
        return None
    return read_json_dict(path, default={}) or {}


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
    if record.get("schema_version") not in ACCEPTED_HUMAN_APPROVAL_SCHEMA_VERSIONS:
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
    automation = record.get("automation") if isinstance(record.get("automation"), dict) else None
    if automation:
        task_id = str(automation.get("task_id") or "").strip()
        expected_actor = f"{CODEX_AUTOMATION_ACTOR_PREFIX}{task_id}" if task_id else ""
        if record.get("approval_actor_type") != "codex-automation":
            issues.append("automation approval record actor type must be codex-automation")
        if not task_id:
            issues.append("automation approval task_id is missing")
        if expected_actor and record_approved_by != expected_actor:
            issues.append("automation approval approved_by does not match task_id")
        for field in ["mode", "task_source", "original_authorization", "authorized_at", "handoff_context"]:
            if not automation.get(field):
                issues.append(f"automation approval {field} is missing")
    expected_approved_by = str(approved_by or "").strip()
    if expected_approved_by and record_approved_by != expected_approved_by:
        issues.append(
            "record-wiki-ingest approved-by does not match pre-write human approval: "
            f"{expected_approved_by} != {record_approved_by}"
        )
    if not str(record.get("approved_at") or "").strip():
        issues.append("human approval record approved_at is missing")
    return not issues, record, issues
