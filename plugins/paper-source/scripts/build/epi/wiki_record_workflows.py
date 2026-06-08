from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from epi.artifacts import (
    file_sha256,
    raw_paper_root,
    runs_root,
    staging_paper_root,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)
from epi.config import load_wiki_config
from epi.epi_repository import ensure_epi_repository
from epi.paper_gate import build_paper_gate
from epi.promote_to_wiki import promote_paper, rollback_promotion
from epi.report_run import write_report
from epi.run_index import refresh_run_index
from epi.wiki_ingest_approval import create_human_approval_record, human_approval_record_path
from epi.wiki_ingest_record import create_wiki_ingest_record, create_wiki_ingest_record_from_prw_request
from epi.zotero_sync import sync_zotero_record

_LOCAL_TOOL_VERSION = "epi-local"


def _write_json(path: Path, payload: object) -> None:
    write_json_atomic(path, payload)


def _refresh_run_index(vault_path: Path) -> None:
    refresh_run_index(vault_path.resolve())


def _hash_existing_outputs(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in paths.items():
        if path.exists():
            hashes[name] = file_sha256(path)
    return hashes


def _tool_versions(*tool_names: str) -> dict[str, str]:
    return {tool_name: _LOCAL_TOOL_VERSION for tool_name in tool_names}


def _new_run_dir(vault_path: Path, prefix: str | None = None) -> tuple[str, Path]:
    ensure_epi_repository(vault_path)
    runs_dir = runs_root(vault_path)
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{prefix}-{timestamp}" if prefix else timestamp
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _zotero_record_only(vault_path: Path, paper_root: Path) -> dict:
    config = load_wiki_config(vault_path) or {}
    zotero_config = config.get("zotero") if isinstance(config.get("zotero"), dict) else {}
    enabled = bool(zotero_config.get("enabled", False))
    collection = str(zotero_config.get("collection") or "EPI")
    reason = "zotero_not_configured" if not config else "zotero_disabled"
    return sync_zotero_record(
        paper_root,
        enabled=enabled,
        collection=collection,
        mode="record-only",
        reason=reason,
    )


def _append_report_sections(
    report_md_path: Path,
    *,
    human_gate: dict | None = None,
    wiki_pages_written: list[str] | None = None,
    restored_paths: list[str] | None = None,
    removed_paths: list[str] | None = None,
) -> None:
    existing = report_md_path.read_text(encoding="utf-8").rstrip()
    sections: list[str] = []
    if human_gate is not None:
        sections.extend(
            [
                "## Human Gate",
                f"- status: {human_gate.get('status')}",
                f"- approved_by: {human_gate.get('approved_by')}",
                f"- approved_at: {human_gate.get('approved_at')}",
            ]
        )
    if wiki_pages_written is not None:
        sections.append("## Wiki Pages Written")
        if wiki_pages_written:
            sections.extend(f"- {path}" for path in wiki_pages_written)
        else:
            sections.append("- None.")
    if restored_paths is not None:
        sections.append("## Restored Paths")
        if restored_paths:
            sections.extend(f"- {path}" for path in restored_paths)
        else:
            sections.append("- None.")
    if removed_paths is not None:
        sections.append("## Removed Paths")
        if removed_paths:
            sections.extend(f"- {path}" for path in removed_paths)
        else:
            sections.append("- None.")
    if sections:
        write_text_atomic(report_md_path, existing + "\n\n" + "\n".join(sections) + "\n")


def _write_paper_run_state(paper_root: Path, state: dict) -> dict:
    _write_json(paper_root / "run-state.json", state)
    return state


def _paper_run_state(
    *,
    paper_root: Path,
    slug: str,
    state: str,
    last_action: str,
    next_action: str | None,
    stage_record: dict | None = None,
    human_gate_required: bool = False,
    workflow_mode: str | None = None,
) -> dict:
    payload = {
        "paper_slug": slug,
        "state": state,
        "last_action": last_action,
        "next_action": next_action,
        "paper_root": str(paper_root),
        "compiled_wiki_write": False,
        "human_gate_required": human_gate_required,
    }
    if workflow_mode is not None:
        payload["workflow_mode"] = workflow_mode
    if stage_record is not None:
        payload["stage_record"] = stage_record
    return payload


def _write_promotion_or_rollback_run_state(
    run_dir: Path,
    *,
    run_id: str,
    workflow_type: str,
    vault_path: Path,
    slug: str,
    started_at: str,
    finished_at: str,
    input_artifact_hashes: dict[str, str],
    output_artifact_hashes: dict[str, str],
    zotero_results: dict | None = None,
) -> None:
    state = {
        "stage": workflow_type,
        "run_id": run_id,
        "workflow_type": workflow_type,
        "state": "reported",
        "status": "success",
        "paper_slug": slug,
        "vault_path": str(vault_path),
        "compiled_wiki_write": True,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_status": 0,
        "tool_versions": _tool_versions("orchestrator", "report_run", "promote_to_wiki"),
        "input_artifact_hashes": input_artifact_hashes,
        "output_artifact_hashes": output_artifact_hashes,
    }
    if zotero_results is not None:
        state["zotero_results"] = zotero_results
    _write_json(run_dir / "run-state.json", state)


def _write_wiki_ingest_record_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    record: dict,
    zotero_results: dict,
) -> None:
    next_actions = ["review-recorded-wiki-pages"]
    page_paths = record.get("relative_page_paths") or record.get("page_paths") or []
    human_gate = record.get("human_gate_decision") or {}
    changed_artifacts = [
        f"_epi/raw/{slug}/wiki-ingest-record.json",
        f"_epi/staging/papers/{slug}/wiki-ingest-record.json",
    ]
    report_paper_states = [
        {
            "slug": slug,
            "paper_slug": slug,
            "title": record.get("title") or slug,
            "state": "wiki_ingest_recorded",
            "last_action": "record-wiki-ingest",
            "next_action": next_actions[0],
            "human_gate_required": False,
        }
    ]
    write_report(
        run_dir,
        [{"slug": slug, "title": record.get("title") or slug, "state": "wiki_ingest_recorded"}],
        [],
        workflow_type="record-wiki-ingest",
        run_id=run_id,
        paper_states=report_paper_states,
        failed_papers=[],
        budget_usage={"paper_count": 1, "recorded_page_count": len(page_paths)},
        wiki_pages_written=page_paths,
        zotero_results=zotero_results,
        next_actions=next_actions,
        human_gate=human_gate,
        changed_artifacts=changed_artifacts,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {"paper_slug": slug, "state": "wiki_ingest_recorded", "next_action": next_actions[0]}
    ]
    report_payload["failed_papers"] = []
    report_payload["wiki_pages_written"] = page_paths
    report_payload["changed_artifacts"] = changed_artifacts
    report_payload["human_gate"] = human_gate
    report_payload["next_actions"] = next_actions
    report_payload["wiki_ingest_record"] = record
    report_payload["page_records"] = record.get("page_records") or []
    report_payload["zotero_results"] = zotero_results
    _write_json(report_json_path, report_payload)


def _write_human_approval_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    record: dict,
) -> None:
    report_md_path = run_dir / "report.md"
    report_json_path = run_dir / "report.json"
    lines = [
        f"# EPI Human Approval - {slug}",
        "",
        f"- run_id: {run_id}",
        "- workflow_type: record-human-approval",
        f"- status: {record.get('status')}",
        f"- approved_by: {record.get('approved_by')}",
        f"- scope: {record.get('scope')}",
        f"- approval_path: {record.get('record_path')}",
        "- next_action: wiki-ingest-trigger",
        "",
    ]
    write_text_atomic(report_md_path, "\n".join(lines))
    _write_json(
        report_json_path,
        {
            "schema_version": "epi-human-approval-report-v1",
            "run_id": run_id,
            "workflow_type": "record-human-approval",
            "paper_slug": slug,
            "status": record.get("status"),
            "human_approval_record": record,
            "next_actions": ["run-wiki-ingest-agent"],
            "recommended_next_command": f"wiki-ingest-trigger --slug {slug}",
        },
    )


def record_human_approval(
    vault_path: Path,
    slug: str,
    *,
    approved_by: str,
    scope: str,
    notes: str | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    gate = build_paper_gate(vault_path, slug)
    record = create_human_approval_record(
        vault_path,
        slug,
        approved_by=approved_by,
        scope=scope,
        notes=notes,
        gate=gate,
    )
    record_path = human_approval_record_path(vault_path, slug)
    record["record_path"] = str(record_path)
    run_id, run_dir = _new_run_dir(vault_path, "record-human-approval")
    _write_human_approval_report(run_dir, run_id=run_id, slug=slug, record=record)
    _write_json(
        run_dir / "run-state.json",
        {
            "stage": "record-human-approval",
            "run_id": run_id,
            "workflow_type": "record-human-approval",
            "state": "human_approved_for_wiki_ingest",
            "status": "success",
            "paper_slug": slug,
            "vault_path": str(vault_path),
            "compiled_wiki_write": False,
            "record_only": True,
            "finished_at": utc_now(),
            "tool_versions": _tool_versions("orchestrator", "wiki_ingest_approval"),
            "output_artifact_hashes": _hash_existing_outputs(
                {
                    "human-approval.json": record_path,
                    "report.md": run_dir / "report.md",
                    "report.json": run_dir / "report.json",
                }
            ),
        },
    )
    paper_root = raw_paper_root(vault_path, slug)
    _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="human_approved_for_wiki_ingest",
            last_action="record-human-approval",
            next_action="run-wiki-ingest-agent",
            stage_record=record,
            human_gate_required=False,
        ),
    )
    _refresh_run_index(vault_path)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "record": record,
        "record_path": str(record_path),
    }


def record_wiki_ingest(
    vault_path: Path,
    slug: str | None,
    pages: list[str] | None,
    *,
    approved_by: str | None,
    notes: str | None = None,
    source_review_path: str | Path | None = None,
    from_prw_request: str | Path | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    started_at = utc_now()
    if from_prw_request is not None:
        record = create_wiki_ingest_record_from_prw_request(
            vault_path,
            from_prw_request,
            notes=notes,
        )
        slug = str(record.get("paper_slug") or "").strip()
    else:
        if not str(slug or "").strip():
            raise ValueError("record-wiki-ingest requires --slug unless --from-prw-request is used")
        if not pages:
            raise ValueError("record-wiki-ingest requires --page unless --from-prw-request is used")
        if not str(approved_by or "").strip():
            raise ValueError("record-wiki-ingest requires --approved-by unless --from-prw-request is used")
        record = create_wiki_ingest_record(
            vault_path,
            str(slug),
            pages,
            approved_by=str(approved_by),
            notes=notes,
            source_review_path=source_review_path,
        )
    if not slug:
        raise ValueError("record-wiki-ingest could not resolve paper slug")
    run_id, run_dir = _new_run_dir(vault_path, "record-wiki-ingest")
    paper_root = raw_paper_root(vault_path, slug)
    staging_root = staging_paper_root(vault_path, slug)
    raw_record_path = paper_root / "wiki-ingest-record.json"
    staging_record_path = staging_root / "wiki-ingest-record.json"
    plan_path = staging_root / "promotion-plan.json"
    brief_path = Path(record.get("paths", {}).get("wiki_ingest_brief") or staging_root / "wiki-ingest-brief.json")
    final_source_review_value = record.get("paths", {}).get("final_source_review")
    final_source_review_path = Path(final_source_review_value) if final_source_review_value else None
    final_page_hashes = {
        f"final_page:{page['relative_path']}": page["sha256"]
        for page in record.get("page_records") or []
    }
    input_artifacts = {
        "promotion-plan.json": plan_path,
        "wiki-ingest-brief.json": brief_path,
        **{
            f"final_page:{page['relative_path']}": Path(page["path"])
            for page in record.get("page_records") or []
        },
    }
    if final_source_review_path is not None:
        input_artifacts["final-source-review.json"] = final_source_review_path
    source_request = record.get("source_request") if isinstance(record.get("source_request"), dict) else {}
    if source_request.get("path"):
        input_artifacts["prw-record-request.json"] = Path(str(source_request["path"]))
    zotero_results = _zotero_record_only(vault_path, paper_root)
    _write_wiki_ingest_record_report(
        run_dir,
        run_id=run_id,
        slug=slug,
        record=record,
        zotero_results=zotero_results,
    )
    _write_json(
        run_dir / "run-state.json",
        {
            "stage": "record-wiki-ingest",
            "run_id": run_id,
            "workflow_type": "record-wiki-ingest",
            "state": "wiki_ingest_recorded",
            "status": "success",
            "paper_slug": slug,
            "vault_path": str(vault_path),
            "compiled_wiki_write": False,
            "record_only": True,
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_status": 0,
            "tool_versions": _tool_versions("orchestrator", "wiki_ingest_record", "report_run"),
            "input_artifact_hashes": _hash_existing_outputs(input_artifacts),
            "final_page_hashes": final_page_hashes,
            "output_artifact_hashes": _hash_existing_outputs(
                {
                    "wiki-ingest-record.raw.json": raw_record_path,
                    "wiki-ingest-record.staging.json": staging_record_path,
                    "zotero-record.json": paper_root / "zotero-record.json",
                    "report.md": run_dir / "report.md",
                    "report.json": run_dir / "report.json",
                }
            ),
            "zotero_results": zotero_results,
        },
    )
    _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="wiki_ingest_recorded",
            last_action="record-wiki-ingest",
            next_action="review-recorded-wiki-pages",
            stage_record=record,
            human_gate_required=False,
        ),
    )
    _refresh_run_index(vault_path)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "record": record,
        "record_path": str(raw_record_path),
        "staging_record_path": str(staging_record_path),
        "zotero_results": zotero_results,
        "zotero_record_path": str(paper_root / "zotero-record.json"),
    }


def _write_promotion_routed_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    promoted_page_paths: list[str],
    human_gate: dict,
    zotero_results: dict,
) -> None:
    next_actions = ["review-promoted-pages"]
    report_paper_states = [
        {
            "slug": slug,
            "paper_slug": slug,
            "title": slug,
            "state": "promoted",
            "last_action": "promote-to-wiki",
            "next_action": next_actions[0],
            "human_gate_required": False,
        }
    ]
    write_report(
        run_dir,
        [{"slug": slug, "title": slug, "state": "promoted"}],
        [],
        workflow_type="promote-to-wiki",
        run_id=run_id,
        paper_states=report_paper_states,
        failed_papers=[],
        budget_usage={},
        wiki_pages_written=promoted_page_paths,
        zotero_results=zotero_results,
        next_actions=next_actions,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {"paper_slug": slug, "state": "promoted", "next_action": next_actions[0]}
    ]
    report_payload["failed_papers"] = []
    report_payload["wiki_pages_written"] = promoted_page_paths
    report_payload["human_gate"] = human_gate
    report_payload["next_actions"] = next_actions
    report_payload["zotero_results"] = zotero_results
    _write_json(report_json_path, report_payload)
    _append_report_sections(
        run_dir / "report.md",
        human_gate=human_gate,
        wiki_pages_written=promoted_page_paths,
    )


def _write_rollback_routed_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    human_gate: dict | None,
    restored_paths: list[str],
    removed_paths: list[str],
) -> None:
    next_actions = ["re-review-before-repromote"]
    report_paper_states = [
        {
            "slug": slug,
            "paper_slug": slug,
            "title": slug,
            "state": "rolled_back",
            "last_action": "rollback-promotion",
            "next_action": next_actions[0],
            "human_gate_required": False,
        }
    ]
    write_report(
        run_dir,
        [],
        [],
        workflow_type="rollback-promotion",
        run_id=run_id,
        paper_states=report_paper_states,
        failed_papers=[],
        budget_usage={},
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {"paper_slug": slug, "state": "rolled_back", "next_action": next_actions[0]}
    ]
    report_payload["failed_papers"] = []
    report_payload["wiki_pages_written"] = []
    report_payload["restored_paths"] = restored_paths
    report_payload["removed_paths"] = removed_paths
    report_payload["next_actions"] = next_actions
    if human_gate is not None:
        report_payload["human_gate"] = human_gate
    _write_json(report_json_path, report_payload)
    _append_report_sections(
        run_dir / "report.md",
        human_gate=human_gate,
        wiki_pages_written=[],
        restored_paths=restored_paths,
        removed_paths=removed_paths,
    )


__all__ = [
    "promote_paper",
    "record_human_approval",
    "record_wiki_ingest",
    "rollback_promotion",
    "_append_report_sections",
    "_hash_existing_outputs",
    "_new_run_dir",
    "_refresh_run_index",
    "_write_human_approval_report",
    "_write_promotion_or_rollback_run_state",
    "_write_promotion_routed_report",
    "_write_rollback_routed_report",
    "_write_wiki_ingest_record_report",
    "_zotero_record_only",
]
