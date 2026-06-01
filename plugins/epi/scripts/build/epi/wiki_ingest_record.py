from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from epi.artifacts import file_sha256, raw_paper_root, staging_paper_root, utc_now, write_json_atomic
from epi.paper_gate import build_paper_gate
from epi.wiki_ingest_approval import human_approval_record_path, validate_human_approval_record


_INTERNAL_VAULT_ROOTS = {"_raw", "_staging", "_runs", "_quarantine", ".git", ".obsidian"}
FINAL_SOURCE_REVIEW_SCHEMA_VERSION = "epi-final-source-review-v1"
REQUIRED_FINAL_SOURCE_ARTIFACTS = [
    "paper.pdf",
    "metadata.json",
    "mineru/paper.md",
    "mineru/paper.tex",
    "mineru/images/*",
    "mineru/mineru-manifest.json",
]


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


def _ensure_gate_allows_record(gate: dict[str, Any]) -> None:
    failure_checks = _gate_check_names(gate, "failure")
    if failure_checks:
        raise ValueError("paper gate has failure checks: " + ", ".join(failure_checks))

    next_action = gate.get("next_action")
    if next_action not in {"run-wiki-ingest-agent", "review-recorded-wiki-pages"}:
        raise ValueError(
            "record-wiki-ingest requires paper-gate next_action=run-wiki-ingest-agent; "
            f"got {next_action or 'unknown'}"
        )

    action_required = _gate_check_names(gate, "action_required")
    unresolved = [name for name in action_required if name != "human-approval"]
    if unresolved:
        raise ValueError("paper gate has unresolved action-required checks: " + ", ".join(unresolved))


def _is_agent_mediated_plan(plan: dict[str, Any]) -> bool:
    return (
        plan.get("handoff_type") == "agent-mediated-wiki-ingest"
        or plan.get("wiki_write_model") == "agent-mediated-vault-contract"
    )


def _resolve_page(vault_path: Path, page: str) -> dict[str, Any]:
    value = str(page or "").strip()
    if not value:
        raise ValueError("page path must not be empty")

    normalized = value.replace("\\", "/")
    parsed = PurePosixPath(normalized)
    if ".." in parsed.parts:
        raise ValueError(f"page path must not contain '..': {page}")

    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (vault_path / candidate).resolve()
    try:
        relative_path = resolved.relative_to(vault_path)
    except ValueError as exc:
        raise ValueError(f"page path must stay inside vault: {page}") from exc

    if not relative_path.parts:
        raise ValueError("page path must point to a file inside the vault")
    if relative_path.parts[0] in _INTERNAL_VAULT_ROOTS:
        raise ValueError(f"recorded final wiki page must not be under {relative_path.parts[0]}: {page}")
    if resolved.suffix.lower() != ".md":
        raise ValueError(f"recorded final wiki page must be a Markdown file: {page}")
    if not resolved.is_file():
        raise FileNotFoundError(f"recorded final wiki page does not exist: {resolved}")

    return {
        "path": str(resolved),
        "relative_path": relative_path.as_posix(),
        "sha256": file_sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _source_first_confirmed(brief: dict[str, Any]) -> bool:
    source_bundle = brief.get("source_bundle") if isinstance(brief.get("source_bundle"), dict) else {}
    raw_artifacts = "\n".join(str(item) for item in source_bundle.get("raw_artifacts") or [])
    formula_figure_review = (
        source_bundle.get("formula_figure_review")
        if isinstance(source_bundle.get("formula_figure_review"), dict)
        else {}
    )
    formula_figure_text = "\n".join(str(item) for item in formula_figure_review.values()).lower()
    return all(
        artifact in raw_artifacts
        for artifact in [
            "mineru/paper.md",
            "mineru/paper.tex",
            "mineru/images/*",
            "mineru/mineru-manifest.json",
        ]
    ) and all(token in formula_figure_text for token in ["formula", "figure", "image"])


def _resolve_review_candidate(value: str, *, vault_path: Path, staging_root: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] in {"_staging", "_raw"}:
        return vault_path / candidate
    staging_candidate = staging_root / candidate
    if staging_candidate.exists() or len(candidate.parts) == 1:
        return staging_candidate
    return vault_path / candidate


def _resolve_final_source_review_path(
    *,
    vault_path: Path,
    staging_root: Path,
    contract: dict[str, Any],
    source_review_path: str | Path | None,
) -> Path | None:
    if source_review_path:
        return _resolve_review_candidate(str(source_review_path), vault_path=vault_path, staging_root=staging_root)

    suggested = str(contract.get("suggested_output_path") or "").strip()
    candidates = []
    if suggested:
        candidates.append(_resolve_review_candidate(suggested, vault_path=vault_path, staging_root=staging_root))
    candidates.append(staging_root / "final-source-review.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _read_required_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"missing final source review: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"final source review is invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"final source review must be a JSON object: {path}")
    return payload


def _review_records_by_artifact(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records = payload.get("reviewed_artifacts")
    if not isinstance(records, list):
        return {}, ["final source review must include reviewed_artifacts[]"]
    by_artifact: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            failures.append(f"reviewed_artifacts[{index}] must be an object")
            continue
        artifact = str(record.get("artifact") or "").strip()
        if not artifact:
            failures.append(f"reviewed_artifacts[{index}] is missing artifact")
            continue
        if artifact in by_artifact:
            failures.append(f"duplicate final source review artifact: {artifact}")
            continue
        by_artifact[artifact] = record
    return by_artifact, failures


def _validate_review_status(record: dict[str, Any], artifact: str, failures: list[str]) -> None:
    if record.get("status") != "reviewed":
        failures.append(f"final source review artifact must be status=reviewed: {artifact}")


def _validate_file_artifact(
    *,
    paper_root: Path,
    artifact: str,
    record: dict[str, Any],
    failures: list[str],
) -> None:
    _validate_review_status(record, artifact, failures)
    artifact_path = paper_root / artifact
    if not artifact_path.is_file():
        failures.append(f"required source artifact is missing on disk: {artifact}")
        return
    actual_hash = file_sha256(artifact_path)
    if record.get("sha256") != actual_hash:
        failures.append(f"final source review sha256 mismatch: {artifact}")


def _validate_image_artifact(
    *,
    paper_root: Path,
    record: dict[str, Any],
    failures: list[str],
) -> None:
    artifact = "mineru/images/*"
    _validate_review_status(record, artifact, failures)
    image_dir = paper_root / "mineru" / "images"
    image_files = sorted(path for path in image_dir.rglob("*") if path.is_file()) if image_dir.exists() else []
    if record.get("file_count") != len(image_files):
        failures.append("final source review image file_count does not match mineru/images")
    reviewed_files = record.get("files") if isinstance(record.get("files"), list) else []
    reviewed_by_path = {
        str(item.get("relative_path") or item.get("path") or "").replace("\\", "/"): item
        for item in reviewed_files
        if isinstance(item, dict)
    }
    for image_path in image_files:
        relative = image_path.relative_to(paper_root).as_posix()
        reviewed = reviewed_by_path.get(relative)
        if not reviewed:
            failures.append(f"final source review missing image hash: {relative}")
            continue
        if reviewed.get("sha256") != file_sha256(image_path):
            failures.append(f"final source review image sha256 mismatch: {relative}")


def _validate_review_section(payload: dict[str, Any], key: str, failures: list[str]) -> None:
    section = payload.get(key) if isinstance(payload.get(key), dict) else {}
    if section.get("status") != "reviewed":
        failures.append(f"final source review {key} must be status=reviewed")
    if not str(section.get("summary") or "").strip():
        failures.append(f"final source review {key} must include a summary")


def _validate_pdf_fallback_section(payload: dict[str, Any], failures: list[str]) -> None:
    section = payload.get("pdf_fallback_review") if isinstance(payload.get("pdf_fallback_review"), dict) else {}
    if section.get("status") not in {"reviewed", "not-needed"}:
        failures.append("final source review pdf_fallback_review must be status=reviewed or not-needed")
    if not str(section.get("summary") or "").strip():
        failures.append("final source review pdf_fallback_review must include a summary")


def _validate_final_page_provenance(
    *,
    payload: dict[str, Any],
    page_records: list[dict[str, Any]],
    failures: list[str],
) -> None:
    provenance = payload.get("final_page_provenance")
    if not isinstance(provenance, list):
        failures.append("final source review must include final_page_provenance[]")
        return
    provenance_by_path = {
        str(item.get("relative_path") or "").replace("\\", "/"): item
        for item in provenance
        if isinstance(item, dict)
    }
    for page in page_records:
        relative_path = str(page.get("relative_path") or "").replace("\\", "/")
        item = provenance_by_path.get(relative_path)
        if not item:
            failures.append(f"final source review missing final page provenance: {relative_path}")
            continue
        if item.get("source_grounded") is not True:
            failures.append(f"final page provenance must be source_grounded=true: {relative_path}")
        if item.get("sha256") and item.get("sha256") != page.get("sha256"):
            failures.append(f"final page provenance sha256 mismatch: {relative_path}")


def _validate_final_source_review(
    *,
    source_review_path: Path,
    paper_root: Path,
    slug: str,
    page_records: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = _read_required_json(source_review_path)
    failures: list[str] = []
    if payload.get("schema_version") != FINAL_SOURCE_REVIEW_SCHEMA_VERSION:
        failures.append("final source review has unsupported schema_version")
    if payload.get("paper_slug") and payload.get("paper_slug") != slug:
        failures.append("final source review paper_slug does not match record slug")

    by_artifact, artifact_failures = _review_records_by_artifact(payload)
    failures.extend(artifact_failures)
    for artifact in REQUIRED_FINAL_SOURCE_ARTIFACTS:
        record = by_artifact.get(artifact)
        if not record:
            failures.append(f"final source review missing required artifact: {artifact}")
            continue
        if artifact == "mineru/images/*":
            _validate_image_artifact(paper_root=paper_root, record=record, failures=failures)
        else:
            _validate_file_artifact(
                paper_root=paper_root,
                artifact=artifact,
                record=record,
                failures=failures,
            )

    _validate_review_section(payload, "formula_review", failures)
    _validate_review_section(payload, "figure_table_image_review", failures)
    _validate_pdf_fallback_section(payload, failures)
    _validate_final_page_provenance(payload=payload, page_records=page_records, failures=failures)

    if failures:
        raise ValueError("final source review failed validation: " + "; ".join(failures))
    return payload


def create_wiki_ingest_record(
    vault_path: Path,
    slug: str,
    pages: list[str],
    *,
    approved_by: str,
    notes: str | None = None,
    source_review_path: str | Path | None = None,
) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    if not str(approved_by or "").strip():
        raise ValueError("human gate approval is required for record-wiki-ingest")
    if not pages:
        raise ValueError("at least one final wiki page must be recorded")

    paper_root = raw_paper_root(vault_path, slug)
    staging_root = staging_paper_root(vault_path, slug)
    plan_path = staging_root / "promotion-plan.json"
    plan = _read_json(plan_path)
    if not plan:
        raise FileNotFoundError(f"missing promotion plan: {plan_path}")
    if not _is_agent_mediated_plan(plan):
        raise ValueError("record-wiki-ingest only supports agent-mediated wiki ingest plans")

    brief_path = Path(plan.get("wiki_ingest_brief_path") or staging_root / "wiki-ingest-brief.json")
    brief = _read_json(brief_path)
    if not brief:
        raise FileNotFoundError(f"missing wiki ingest brief: {brief_path}")

    gate = build_paper_gate(vault_path, slug)
    _ensure_gate_allows_record(gate)
    approval_valid, approval_record, approval_issues = validate_human_approval_record(
        vault_path,
        slug,
        approved_by=approved_by,
        require_existing=True,
    )
    if not approval_valid:
        raise ValueError("; ".join(approval_issues))
    assert approval_record is not None

    page_records = [_resolve_page(vault_path, page) for page in pages]
    seen: set[str] = set()
    duplicates = []
    for record in page_records:
        relative = record["relative_path"]
        if relative in seen:
            duplicates.append(relative)
        seen.add(relative)
    if duplicates:
        raise ValueError("duplicate final wiki page records: " + ", ".join(duplicates))

    source_review_contract = (
        brief.get("final_source_review_contract")
        if isinstance(brief.get("final_source_review_contract"), dict)
        else {}
    )
    resolved_source_review_path = _resolve_final_source_review_path(
        vault_path=vault_path,
        staging_root=staging_root,
        contract=source_review_contract,
        source_review_path=source_review_path,
    )
    source_review_payload: dict[str, Any] | None = None
    if resolved_source_review_path and resolved_source_review_path.exists():
        source_review_payload = _validate_final_source_review(
            source_review_path=resolved_source_review_path,
            paper_root=paper_root,
            slug=slug,
            page_records=page_records,
        )
    elif source_review_contract.get("required"):
        raise ValueError(
            "final source review is required before record-wiki-ingest: "
            + str(resolved_source_review_path or staging_root / "final-source-review.json")
        )
    source_first_verified_by_source_review = source_review_payload is not None

    recorded_at = utc_now()
    failure_checks = _gate_check_names(gate, "failure")
    action_required_checks = _gate_check_names(gate, "action_required")
    human_gate_decision = {
        "status": "approved",
        "approved_by": str(approval_record.get("approved_by") or approved_by).strip(),
        "approved_at": approval_record.get("approved_at") or recorded_at,
        "approval_scope": approval_record.get("scope") or "run-wiki-ingest-agent",
        "prewrite_approval_record": str(human_approval_record_path(vault_path, slug)),
    }
    if notes:
        human_gate_decision["notes"] = notes
    elif approval_record.get("notes"):
        human_gate_decision["notes"] = approval_record.get("notes")

    record_payload = {
        "schema_version": "epi-wiki-ingest-record-v1",
        "stage": "record-wiki-ingest",
        "status": "recorded",
        "paper_slug": slug,
        "title": brief.get("title") or gate.get("title") or slug,
        "recorded_at": recorded_at,
        "vault_path": str(vault_path),
        "compiled_wiki_write": False,
        "record_only": True,
        "final_pages_modified_by_epi": False,
        "wiki_write_model": plan.get("wiki_write_model") or "agent-mediated-vault-contract",
        "handoff_type": plan.get("handoff_type") or brief.get("handoff_type"),
        "final_page_authority": plan.get("final_page_authority"),
        "source_first_confirmed": source_first_verified_by_source_review or _source_first_confirmed(brief),
        "source_first_verification_method": (
            "final-source-review-json"
            if source_first_verified_by_source_review
            else "brief-contract-only"
        ),
        "final_source_review": (
            {
                "status": "verified",
                "path": str(resolved_source_review_path),
                "schema_version": source_review_payload.get("schema_version"),
                "reviewed_artifacts": source_review_payload.get("reviewed_artifacts") or [],
                "formula_review": source_review_payload.get("formula_review") or {},
                "figure_table_image_review": source_review_payload.get("figure_table_image_review") or {},
                "pdf_fallback_review": source_review_payload.get("pdf_fallback_review") or {},
                "final_page_provenance": source_review_payload.get("final_page_provenance") or [],
            }
            if source_review_payload is not None
            else {
                "status": "missing",
                "required": bool(source_review_contract.get("required")),
            }
        ),
        "human_gate_decision": human_gate_decision,
        "paper_gate": {
            "status": gate.get("status"),
            "next_action": gate.get("next_action"),
            "conclusion": gate.get("check_suite", {}).get("conclusion"),
            "failure_checks": failure_checks,
            "action_required_checks": action_required_checks,
        },
        "paths": {
            "paper_root": str(paper_root),
            "staging_root": str(staging_root),
            "promotion_plan": str(plan_path),
            "wiki_ingest_brief": str(brief_path),
            "human_approval": str(human_approval_record_path(vault_path, slug)),
            "agent_handoff_paths": plan.get("agent_handoff_paths") or [],
        },
        "page_records": page_records,
        "page_paths": [record["path"] for record in page_records],
        "relative_page_paths": [record["relative_path"] for record in page_records],
        "ingest_policy": brief.get("ingest_policy") if isinstance(brief.get("ingest_policy"), dict) else {},
        "source_bundle": brief.get("source_bundle") if isinstance(brief.get("source_bundle"), dict) else {},
        "wiki_rule_source_model": (
            brief.get("wiki_rule_source_model")
            if isinstance(brief.get("wiki_rule_source_model"), dict)
            else {}
        ),
    }
    if source_review_payload is not None and resolved_source_review_path is not None:
        record_payload["paths"]["final_source_review"] = str(resolved_source_review_path)
    if notes:
        record_payload["notes"] = notes

    raw_record_path = paper_root / "wiki-ingest-record.json"
    staging_record_path = staging_root / "wiki-ingest-record.json"
    record_payload["record_paths"] = {
        "raw": str(raw_record_path),
        "staging": str(staging_record_path),
    }
    write_json_atomic(raw_record_path, record_payload)
    write_json_atomic(staging_record_path, record_payload)
    return record_payload
