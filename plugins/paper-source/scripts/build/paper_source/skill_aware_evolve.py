from __future__ import annotations

import json
import shutil
import uuid
from collections import Counter
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from paper_source.artifacts import evolution_root, read_json, read_json_dict, utc_now, write_json_atomic, write_text_atomic


WHITELISTED_TEMPLATE_ASSETS = {
    "templates/ranking.example.yaml",
    "templates/critic-checklist.example.yaml",
}
EXECUTION_LAPSE_TYPES = {
    "execution_lapse",
    "missed_instruction",
    "missed_existing_instruction",
    "operator_error",
    "bad_execution",
}
CONFIG_CHANGE_TYPES = {
    "configuration",
    "configuration_change",
    "config_need",
    "user_config",
}


def _normalize_asset_key(target_asset: str) -> str:
    return target_asset.replace("\\", "/")


def _validate_target_asset(target_asset: str) -> str:
    normalized = _normalize_asset_key(target_asset).strip()
    path = PurePosixPath(normalized)
    if (
        not normalized
        or Path(target_asset).is_absolute()
        or normalized.startswith("/")
        or ".." in path.parts
        or any(char in normalized for char in "*?;|")
    ):
        raise ValueError("evolution proposals require a bounded relative target_asset")
    return normalized


def _normalize_signal(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _reflection_classification(reflection_type: str, evidence_type: str | None) -> str:
    signals = {_normalize_signal(reflection_type), _normalize_signal(evidence_type)}
    if signals & EXECUTION_LAPSE_TYPES:
        return "execution_lapse"
    if signals & CONFIG_CHANGE_TYPES:
        return "configuration_change"
    return "skill_change"


def _infer_risk_level(target_asset: str, classification: str) -> str:
    if classification in {"execution_lapse", "configuration_change"}:
        return "low"
    normalized = _normalize_asset_key(target_asset)
    if normalized in WHITELISTED_TEMPLATE_ASSETS:
        return "low"
    if normalized.startswith("docs/") or normalized.startswith("skills/"):
        return "medium"
    return "high"


def _default_acceptance_gates() -> list[dict[str, Any]]:
    return [
        {
            "id": "human_approval",
            "required": True,
            "description": "Activation requires explicit human approval.",
        },
        {
            "id": "validation_non_regression",
            "required": False,
            "description": "Attach Plugin Eval, tests, benchmark, or metric evidence when available.",
        },
    ]


def _bounded_change(target_asset: str, proposed_change: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_asset": target_asset,
        "single_target_asset": True,
        "allowed_operations": ["add", "replace", "delete"],
        "proposed_change_keys": sorted(str(key) for key in proposed_change.keys()),
        "code_write_allowed": False,
    }


def _optimizer_protocol() -> dict[str, Any]:
    return {
        "inspired_by": ["SkillOpt", "EmbodiSkill"],
        "skillopt": {
            "bounded_text_edit": True,
            "validation_improvement_required": True,
            "metric_gate_evaluation": True,
            "metric_gate_missing_value_rejects": True,
            "rejected_edit_buffer": "_evolution/rejected",
            "zero_runtime_model_calls": True,
        },
        "embodiskill": {
            "skill_aware_reflection": True,
            "distinguish_execution_lapse_from_skill_defect": True,
            "preserve_valid_guidance_on_execution_lapse": True,
        },
    }


def _metric_from_validation_result(validation_result: dict[str, Any], metric: str) -> Any:
    if metric in validation_result:
        return validation_result[metric]
    metrics = validation_result.get("metrics")
    if isinstance(metrics, dict):
        return metrics.get(metric)
    return None


def _coerce_metric_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _compare_metric(actual: Any, operator: str, expected: Any) -> bool | None:
    actual_number = _coerce_metric_number(actual)
    expected_number = _coerce_metric_number(expected)
    if actual_number is None or expected_number is None:
        return None
    if operator == ">=":
        return actual_number >= expected_number
    if operator == ">":
        return actual_number > expected_number
    if operator == "<=":
        return actual_number <= expected_number
    if operator == "<":
        return actual_number < expected_number
    if operator in {"==", "="}:
        return actual_number == expected_number
    if operator == "!=":
        return actual_number != expected_number
    return None


def _gate_results(approved: bool, validation_result: dict[str, Any] | None) -> dict[str, Any]:
    validation_passed = None if validation_result is None else bool(validation_result.get("passed"))
    return {
        "human_approval": "passed" if approved else "failed",
        "validation": "not_provided" if validation_passed is None else ("passed" if validation_passed else "failed"),
    }


def _requires_validation_before_application(proposal: dict[str, Any], normalized_target_asset: str) -> bool:
    return (
        proposal.get("reflection_classification") == "skill_change"
        and normalized_target_asset in WHITELISTED_TEMPLATE_ASSETS
    )


def _check_run_for_gate(
    gate: dict[str, Any],
    *,
    approved: bool,
    validation_result: dict[str, Any] | None,
) -> dict[str, Any]:
    name = str(gate.get("id") or gate.get("metric") or gate.get("command") or "validation_gate")
    if name == "human_approval":
        conclusion = "success" if approved else "failure"
        summary = "Human approval recorded." if approved else "Human approval is required."
    elif name == "quality_loop_sources_complete":
        missing_sources = [str(item) for item in gate.get("missing_sources") or []]
        invalid_sources = [str(item) for item in gate.get("invalid_sources") or []]
        if missing_sources or invalid_sources:
            conclusion = "failure"
            parts = []
            if missing_sources:
                parts.append("missing sources: " + ", ".join(missing_sources))
            if invalid_sources:
                parts.append("invalid sources: " + ", ".join(invalid_sources))
            summary = "Quality-loop evidence sources are incomplete; " + "; ".join(parts) + "."
        else:
            conclusion = "success"
            summary = "Quality-loop evidence sources are complete."
    elif validation_result is None:
        conclusion = "action_required"
        summary = gate.get("description") or "Validation result is required before applying this skill change."
    elif validation_result.get("passed") is False:
        conclusion = "failure"
        summary = validation_result.get("reason") or validation_result.get("summary") or "Validation failed."
    elif gate.get("metric") and gate.get("operator") and "value" in gate:
        metric = str(gate["metric"])
        operator = str(gate["operator"])
        expected = gate["value"]
        actual = _metric_from_validation_result(validation_result, metric)
        comparison = _compare_metric(actual, operator, expected)
        if comparison is True:
            conclusion = "success"
            summary = f"{metric}={actual} satisfies {operator} {expected}."
        elif comparison is False:
            conclusion = "failure"
            summary = f"{metric}={actual} does not satisfy {operator} {expected}."
        else:
            conclusion = "failure"
            summary = f"{metric} is missing or cannot be compared against {operator} {expected}."
    elif validation_result.get("passed"):
        conclusion = "success"
        summary = validation_result.get("summary") or "Validation passed."
    else:
        conclusion = "failure"
        summary = validation_result.get("reason") or validation_result.get("summary") or "Validation failed."
    return {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": name,
            "summary": summary,
        },
    }


def _is_non_human_gate(gate: dict[str, Any]) -> bool:
    name = str(gate.get("id") or gate.get("metric") or gate.get("command") or "")
    return name != "human_approval"


def _build_check_suite(
    proposal: dict[str, Any],
    *,
    approved: bool,
    validation_result: dict[str, Any] | None,
) -> dict[str, Any]:
    gates = list(proposal.get("acceptance_gates") or [])
    if not any((gate.get("id") if isinstance(gate, dict) else None) == "human_approval" for gate in gates):
        gates.insert(0, _default_acceptance_gates()[0])
    target_asset = _validate_target_asset(str(proposal.get("target_asset") or ""))
    if _requires_validation_before_application(proposal, _normalize_asset_key(target_asset)) and not any(
        isinstance(gate, dict) and _is_non_human_gate(gate)
        for gate in gates
    ):
        gates.append(
            {
                "id": "validation_required",
                "required": True,
                "description": "Validation result is required before applying this whitelisted skill change.",
            }
        )
    check_runs = [
        _check_run_for_gate(gate, approved=approved, validation_result=validation_result)
        for gate in gates
        if isinstance(gate, dict)
    ]
    conclusions = {run["conclusion"] for run in check_runs}
    if "failure" in conclusions:
        conclusion = "failure"
    elif "action_required" in conclusions:
        conclusion = "action_required"
    else:
        conclusion = "success"
    return {
        "schema_version": "paper-source-evolution-check-suite-v1",
        "status": "completed",
        "conclusion": conclusion,
        "check_runs": check_runs,
    }


def _parse_yaml_scalar(raw: str) -> Any:
    if raw.startswith('"') and raw.endswith('"'):
        return json.loads(raw)
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _parse_simple_yaml_mapping(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        key, separator, value = stripped.partition(":")
        if not separator:
            raise ValueError(f"unsupported yaml line: {raw_line}")
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value.strip():
            parent[key] = _parse_yaml_scalar(value.strip())
            continue
        node: dict[str, Any] = {}
        parent[key] = node
        stack.append((indent, node))
    return root


def _dump_yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False) if any(ch.isspace() for ch in str(value)) or ":" in str(value) else str(value)


def _dump_simple_yaml_mapping(payload: dict[str, Any], *, indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_dump_simple_yaml_mapping(value, indent=indent + 2))
        else:
            lines.append(f"{prefix}{key}: {_dump_yaml_scalar(value)}")
    return lines


def _deep_merge_mapping(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge_mapping(base[key], value)
            continue
        base[key] = value
    return base


def _apply_template_change(asset_path: Path, proposed_change: dict[str, Any]) -> None:
    current = _parse_simple_yaml_mapping(asset_path.read_text(encoding="utf-8"))
    merged = _deep_merge_mapping(current, proposed_change)
    content = "\n".join(_dump_simple_yaml_mapping(merged)) + "\n"
    write_text_atomic(asset_path, content)


def propose_evolution(
    vault_path: Path,
    *,
    reflection_type: str,
    target_asset: str,
    rationale: str,
    proposed_change: dict[str, Any],
    evidence: list[str],
    evidence_type: str | None = None,
    before_metrics: dict[str, Any] | None = None,
    acceptance_gates: list[dict[str, Any]] | None = None,
    risk_level: str | None = None,
) -> dict:
    target_asset = _validate_target_asset(target_asset)
    if not isinstance(proposed_change, dict) or not proposed_change:
        raise ValueError("proposed_change must be a non-empty object")
    classification = _reflection_classification(reflection_type, evidence_type)
    skill_change_allowed = classification == "skill_change"
    proposal_id = f"evo-{uuid.uuid4().hex[:12]}"
    proposal = {
        "id": proposal_id,
        "status": "proposed",
        "created_at": utc_now(),
        "reflection_type": reflection_type,
        "evidence_type": evidence_type or reflection_type,
        "reflection_classification": classification,
        "skill_change_allowed": skill_change_allowed,
        "target_asset": target_asset,
        "rationale": rationale,
        "proposed_change": proposed_change,
        "evidence": evidence,
        "before_metrics": before_metrics or {},
        "acceptance_gates": acceptance_gates or _default_acceptance_gates(),
        "bounded_change": _bounded_change(target_asset, proposed_change),
        "optimizer_protocol": _optimizer_protocol(),
        "risk_level": risk_level or _infer_risk_level(target_asset, classification),
        "activation_status": "pending_human_approval",
        "activation_requires_human_approval": True,
        "rollback_instructions": "Move active record to archive and restore the previous controlled asset version.",
    }
    path = evolution_root(vault_path) / "proposals" / f"{proposal_id}.json"
    write_json_atomic(path, proposal)
    return proposal


def activate_evolution(
    vault_path: Path,
    proposal_id: str,
    *,
    approved: bool,
    validation_result: dict[str, Any] | None = None,
) -> dict:
    if not approved:
        raise PermissionError("human approval is required before activating evolution proposals")
    vault_path = vault_path.resolve()
    proposal_path = evolution_root(vault_path) / "proposals" / f"{proposal_id}.json"
    proposal = read_json(proposal_path)
    target_asset = _validate_target_asset(proposal["target_asset"])
    normalized_target_asset = _normalize_asset_key(target_asset)
    activated = {
        **proposal,
        "status": "active",
        "activated_at": utc_now(),
        "activation_status": "active",
        "gate_results": _gate_results(approved, validation_result),
        "validation_result": validation_result,
        "check_suite": _build_check_suite(proposal, approved=approved, validation_result=validation_result),
        "code_modified": False,
    }
    check_suite_conclusion = activated["check_suite"]["conclusion"]

    if _requires_validation_before_application(proposal, normalized_target_asset) and validation_result is None:
        activated["status"] = "pending_validation"
        activated["activation_status"] = "action_required"
        activated["asset_application"] = {
            "status": "record_only",
            "target_asset": target_asset,
            "reason": "validation_required_before_skill_change",
            "backup_created": False,
        }
        pending_path = evolution_root(vault_path) / "pending" / f"{proposal_id}.json"
        write_json_atomic(pending_path, activated)
        return activated

    if validation_result is not None and check_suite_conclusion == "failure":
        activated["status"] = "rejected"
        activated["activation_status"] = "rejected_by_validation"
        activated["asset_application"] = {
            "status": "record_only",
            "target_asset": target_asset,
            "reason": "validation_gate_failed",
            "backup_created": False,
        }
        rejected_path = evolution_root(vault_path) / "rejected" / f"{proposal_id}.json"
        write_json_atomic(rejected_path, activated)
        archive_dir = evolution_root(vault_path) / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(proposal_path, archive_dir / f"{proposal_id}.proposed.json")
        return activated

    if proposal.get("reflection_classification") == "execution_lapse":
        activated["asset_application"] = {
            "status": "record_only",
            "target_asset": target_asset,
            "reason": "execution_lapse_preserves_existing_skill",
            "backup_created": False,
        }
    elif proposal.get("reflection_classification") == "configuration_change":
        activated["asset_application"] = {
            "status": "record_only",
            "target_asset": target_asset,
            "reason": "configuration_change_uses_config_proposal_flow",
            "backup_created": False,
        }
    elif normalized_target_asset not in WHITELISTED_TEMPLATE_ASSETS:
        activated["asset_application"] = {
            "status": "record_only",
            "target_asset": target_asset,
            "reason": "target_asset_not_whitelisted",
            "backup_created": False,
        }
    else:
        asset_path = vault_path / Path(target_asset)
        backup_dir = evolution_root(vault_path) / "backups" / proposal_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / asset_path.name
        shutil.copyfile(asset_path, backup_path)
        _apply_template_change(asset_path, proposal["proposed_change"])
        activated["asset_application"] = {
            "status": "applied",
            "target_asset": target_asset,
            "asset_path": str(asset_path),
            "backup_created": True,
            "backup_path": str(backup_path),
        }
        activated["rollback"] = {
            "target_asset": target_asset,
            "backup_path": str(backup_path),
            "restore_action": "restore_file_copy",
        }
    active_path = evolution_root(vault_path) / "active" / f"{proposal_id}.json"
    write_json_atomic(active_path, activated)
    archive_dir = evolution_root(vault_path) / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(proposal_path, archive_dir / f"{proposal_id}.proposed.json")
    return activated


def _load_evolution_records(vault_path: Path) -> list[dict[str, Any]]:
    evolution_root_path = evolution_root(vault_path)
    records_by_id: dict[str, dict[str, Any]] = {}
    precedence = {"proposals": 0, "pending": 1, "rejected": 2, "active": 3}
    for bucket in ["proposals", "pending", "rejected", "active"]:
        bucket_root = evolution_root_path / bucket
        if not bucket_root.exists():
            continue
        for path in sorted(bucket_root.glob("*.json")):
            try:
                record = read_json_dict(path, default=None)
            except OSError:
                continue
            if record is None:
                continue
            proposal_id = record.get("id")
            if not proposal_id:
                continue
            current = records_by_id.get(proposal_id)
            if current and current.get("_bucket_precedence", -1) > precedence[bucket]:
                continue
            records_by_id[proposal_id] = {
                **record,
                "_bucket": bucket,
                "_bucket_precedence": precedence[bucket],
                "_record_path": str(path),
            }
    return list(records_by_id.values())


def _record_sort_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("activated_at") or record.get("created_at") or ""),
        str(record.get("id") or ""),
        str(record.get("_bucket") or ""),
    )


def _validation_reason(record: dict[str, Any]) -> str:
    validation_result = record.get("validation_result")
    if isinstance(validation_result, dict):
        return str(validation_result.get("reason") or validation_result.get("summary") or "")
    asset_application = record.get("asset_application")
    if isinstance(asset_application, dict):
        return str(asset_application.get("reason") or "")
    return ""


def _check_run_summaries(record: dict[str, Any], conclusions: set[str]) -> list[dict[str, str]]:
    check_suite = record.get("check_suite") if isinstance(record.get("check_suite"), dict) else {}
    check_runs = check_suite.get("check_runs") if isinstance(check_suite.get("check_runs"), list) else []
    summaries: list[dict[str, str]] = []
    for run in check_runs:
        if not isinstance(run, dict) or run.get("conclusion") not in conclusions:
            continue
        output = run.get("output") if isinstance(run.get("output"), dict) else {}
        summaries.append(
            {
                "name": str(run.get("name") or ""),
                "conclusion": str(run.get("conclusion") or ""),
                "summary": str(output.get("summary") or ""),
            }
        )
    return summaries


def _evolution_next_action(record: dict[str, Any]) -> str:
    status = record.get("status")
    check_suite = record.get("check_suite") if isinstance(record.get("check_suite"), dict) else {}
    conclusion = check_suite.get("conclusion")
    if record.get("reflection_classification") == "configuration_change":
        return "propose-config-update"
    if status == "pending_validation" or conclusion == "action_required":
        return "provide-validation-result"
    if status == "rejected" or conclusion == "failure":
        return "review-rejected-edit-buffer"
    if status == "active":
        return "monitor-non-regression"
    return "review-proposal"


def _summarize_evolution_record(record: dict[str, Any]) -> dict[str, Any]:
    check_suite = record.get("check_suite") if isinstance(record.get("check_suite"), dict) else {}
    item = {
        "id": record.get("id"),
        "status": record.get("status", "unknown"),
        "activation_status": record.get("activation_status"),
        "target_asset": record.get("target_asset"),
        "reflection_classification": record.get("reflection_classification"),
        "evidence_type": record.get("evidence_type"),
        "risk_level": record.get("risk_level"),
        "check_suite_conclusion": check_suite.get("conclusion", "not_started"),
        "asset_application_status": (
            record.get("asset_application", {}).get("status")
            if isinstance(record.get("asset_application"), dict)
            else None
        ),
        "created_at": record.get("created_at"),
        "activated_at": record.get("activated_at"),
        "next_action": _evolution_next_action(record),
        "reason": _validation_reason(record),
        "record_path": record.get("_record_path"),
    }
    failed_checks = _check_run_summaries(record, {"failure"})
    action_required_checks = _check_run_summaries(record, {"action_required"})
    if failed_checks:
        item["failed_checks"] = failed_checks
    if action_required_checks:
        item["action_required_checks"] = action_required_checks
    return {key: value for key, value in item.items() if value is not None and value != ""}


def query_evolution(
    vault_path: Path,
    *,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    records = _load_evolution_records(vault_path)
    records.sort(key=_record_sort_key, reverse=True)
    if status:
        records = [record for record in records if record.get("status") == status]
    items = [_summarize_evolution_record(record) for record in records[:limit]]
    status_counts = Counter(str(record.get("status", "unknown")) for record in records)
    check_suite_counts = Counter(
        str(
            record.get("check_suite", {}).get("conclusion", "not_started")
            if isinstance(record.get("check_suite"), dict)
            else "not_started"
        )
        for record in records
    )
    return {
        "title": "Paper Source Evolution Status" if status is None else f"Paper Source Evolution Status - {status}",
        "status": status,
        "summary": {
            "total_records": len(records),
            "status_counts": dict(sorted(status_counts.items())),
            "check_suite_counts": dict(sorted(check_suite_counts.items())),
        },
        "items": items,
    }


def render_evolution_query(result: dict[str, Any]) -> str:
    lines = [f"# {result['title']}", ""]
    summary = result.get("summary") or {}
    lines.extend(
        [
            "## Summary",
            "",
            f"- total records: {summary.get('total_records', 0)}",
        ]
    )
    for status, count in (summary.get("status_counts") or {}).items():
        lines.append(f"- {status}: {count}")
    for conclusion, count in (summary.get("check_suite_counts") or {}).items():
        lines.append(f"- check {conclusion}: {count}")
    lines.extend(["", "## Records", ""])
    items = result.get("items") or []
    if not items:
        lines.extend(["No evolution records found.", ""])
        return "\n".join(lines)
    for item in items:
        lines.append(
            "- {id} | {status} | {target_asset}".format(
                id=item.get("id", "-"),
                status=item.get("status", "unknown"),
                target_asset=item.get("target_asset", "-"),
            )
        )
        lines.append(f"  check: {item.get('check_suite_conclusion', 'not_started')}")
        lines.append(f"  next: {item.get('next_action', 'review-proposal')}")
        if item.get("reason"):
            lines.append(f"  reason: {item['reason']}")
        for check in item.get("failed_checks") or []:
            lines.append(f"  failed-check: {check.get('name', '-')}: {check.get('summary', '')}")
        for check in item.get("action_required_checks") or []:
            lines.append(f"  action-required-check: {check.get('name', '-')}: {check.get('summary', '')}")
        if item.get("risk_level"):
            lines.append(f"  risk: {item['risk_level']}")
    lines.append("")
    return "\n".join(lines)
