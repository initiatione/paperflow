from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_source.artifacts import file_sha256, read_json, runs_root, utc_now, write_json_atomic, write_text_atomic
from paper_source.auto_staging import auto_stage_recommendations_from_run
from paper_source.orchestrator import (
    _auto_manage_run_lifecycle,
    _hash_existing_outputs,
    _new_run_dir,
    _refresh_run_index,
    _run_artifacts,
    _tool_versions,
    run_dry_run,
)


def _empty_artifacts() -> dict[str, Any]:
    return {
        "query_plan": None,
        "search_record": None,
        "filter_report": None,
        "rank": None,
        "batch_record": None,
        "report": None,
        "report_json": None,
        "run_state": None,
    }


def _summary_from_session(session_recommendations: dict[str, Any]) -> dict[str, Any]:
    primary = session_recommendations.get("primary_recommendations")
    primary = primary if isinstance(primary, list) else []
    statuses: dict[str, int] = {}
    for item in primary:
        if not isinstance(item, dict):
            continue
        status = str(item.get("auto_staging_status") or "not_selected")
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "primary_count": len(primary),
        "auto_staging_status_counts": statuses,
        "overflow_hidden_count": (session_recommendations.get("overflow") or {}).get("hidden_count", 0)
        if isinstance(session_recommendations.get("overflow"), dict)
        else 0,
    }


def _render_report(record: dict[str, Any]) -> str:
    lines = [
        "# Paper Source Discover Papers",
        "",
        f"Run ID: {record['run_id']}",
        f"Discovery run: {record['discovery_run_id']}",
        f"Auto-staging run: {record.get('auto_staging_run_id') or 'not_run'}",
        f"Selection policy: {record['selection_policy']}",
        f"Workflow mode: {record['workflow_mode']}",
        f"Auto-stage: {str(record['auto_stage']).lower()}",
        f"Stops after: {record['stops_after']}",
        f"Final wiki write: {str(record['compiled_wiki_write']).lower()}",
        f"Human approval written: {str(record['human_approval_written']).lower()}",
        "",
        "## Recommendation Summary",
        f"- primary_count: {record['recommendation_summary']['primary_count']}",
        f"- overflow_hidden_count: {record['recommendation_summary']['overflow_hidden_count']}",
    ]
    for status, count in sorted(record["recommendation_summary"]["auto_staging_status_counts"].items()):
        lines.append(f"- {status}: {count}")
    plan = record.get("auto_staging_plan") or {}
    if plan:
        lines.extend(
            [
                "",
                "## Auto Staging Plan",
                f"- selected: {len(plan.get('selected') or [])}",
                f"- skipped: {len(plan.get('skipped') or [])}",
            ]
        )
        skipped_by_reason = (plan.get("counts") or {}).get("skipped_by_reason") or {}
        for reason, count in sorted(skipped_by_reason.items()):
            lines.append(f"- skipped_{reason}: {count}")
    if record.get("manual_downloads"):
        lines.append("")
        lines.append("## Manual Downloads")
        for item in record["manual_downloads"]:
            lines.append(f"- {item.get('title') or item.get('slug')}: manual-download-required")
    lines.append("")
    lines.append("## Next Actions")
    lines.extend(f"- {action}" for action in record["next_actions"])
    return "\n".join(lines) + "\n"


def discover_papers(
    *,
    plugin_root: Path,
    vault_path: Path,
    query: str | None,
    max_results: int | None,
    fixture_path: Path | None = None,
    paper_search_command: str | None = None,
    sources: list[str] | None = None,
    use_query_plan: bool = True,
    query_variants: list[str] | None = None,
    domain_focus_terms: list[str] | None = None,
    agent_query_plan_json: Path | None = None,
    year_min: int | None = None,
    code_policy: str | None = None,
    query_plan_domain: str = "auto",
    query_plan_max_queries: int = 6,
    enable_easyscholar: bool = True,
    selection_policy: str = "balanced_high_quality",
    refresh: bool = False,
    from_brief: Path | None = None,
    allow_draft_brief: bool = False,
    auto_stage: bool = True,
    max_auto_stage: int = 3,
    review_survey_requested: bool = False,
    skip_existing: bool = True,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
    workflow_mode: str = "fast-ingest",
) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    started_at = utc_now()
    discovery_run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault_path,
        query=query,
        from_brief=from_brief,
        allow_draft_brief=allow_draft_brief,
        max_results=max_results,
        fixture_path=fixture_path,
        paper_search_command=paper_search_command,
        sources=sources,
        use_query_plan=use_query_plan,
        query_variants=query_variants,
        domain_focus_terms=domain_focus_terms,
        agent_query_plan_json=agent_query_plan_json,
        year_min=year_min,
        code_policy=code_policy,
        query_plan_domain=query_plan_domain,
        query_plan_max_queries=query_plan_max_queries,
        enable_easyscholar=enable_easyscholar,
        selection_policy=selection_policy,
        resume=True,
        refresh=refresh,
        review_survey_policy="include_by_default",
    )
    discovery_report = read_json(discovery_run_dir / "report.json")
    session_recommendations = discovery_report.get("session_recommendations") or {}
    auto_batch: dict[str, Any] | None = None
    auto_report: dict[str, Any] = {}
    if auto_stage:
        auto_batch = auto_stage_recommendations_from_run(
            vault_path,
            discovery_run_dir.name,
            mineru_command=mineru_command,
            auto_limit=max_auto_stage,
            review_survey_requested=review_survey_requested,
            skip_existing=skip_existing,
            mineru_timeout=mineru_timeout,
            workflow_mode=workflow_mode,
            selection_policy=selection_policy,
        )
        auto_report = read_json(runs_root(vault_path) / auto_batch["run_id"] / "report.json", default={}) or {}
        session_recommendations = auto_batch.get("session_recommendations") or auto_report.get(
            "session_recommendations", session_recommendations
        )

    run_id, run_dir = _new_run_dir(vault_path, "discover-papers")
    auto_run_id = auto_batch.get("run_id") if auto_batch else None
    auto_run_dir = runs_root(vault_path) / auto_run_id if auto_run_id else None
    failed = bool(auto_batch and auto_batch.get("state") == "prepare_failed")
    status = auto_batch.get("status", "success") if auto_batch else "success"
    state = "source_staging_prepared" if auto_batch and not failed else "recommendations_reported"
    if failed:
        state = "source_staging_failed"
    next_actions = [
        "Review session_recommendations before reading decisions.",
        "Use manual_download links for needs_pdf recommendations.",
    ]
    if auto_stage:
        next_actions.append("Review source-staging artifacts before approval or Paper Wiki handoff.")
    else:
        next_actions.append("Rerun discover-papers without --no-auto-stage to prepare source-staging artifacts.")

    record = {
        "stage": "discover-papers",
        "run_id": run_id,
        "workflow_type": "discover-papers",
        "state": state,
        "status": status,
        "vault_path": str(vault_path),
        "query": query,
        "max_results": max_results,
        "selection_policy": selection_policy,
        "workflow_mode": workflow_mode,
        "source_run_id": discovery_run_dir.name,
        "discovery_run_id": discovery_run_dir.name,
        "auto_staging_run_id": auto_run_id,
        "auto_stage": auto_stage,
        "max_auto_stage": max_auto_stage,
        "review_survey_requested": review_survey_requested,
        "skip_existing": skip_existing,
        "processed_count": auto_batch.get("processed_count", 0) if auto_batch else 0,
        "skipped_count": auto_batch.get("skipped_count", 0) if auto_batch else 0,
        "compiled_wiki_write": False,
        "human_approval_written": False,
        "paper_wiki_invoked": False,
        "stops_after": "source-staging" if auto_stage else "recommendation-output",
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 1 if failed else 0,
        "auto_staging_plan": (auto_batch or {}).get("auto_staging_plan") or auto_report.get("auto_staging_plan"),
        "session_recommendations": session_recommendations,
        "recommendation_summary": _summary_from_session(session_recommendations),
        "manual_downloads": auto_report.get("manual_downloads", []),
        "artifacts": {
            "discovery": _run_artifacts(discovery_run_dir),
            "auto_staging": _run_artifacts(auto_run_dir) if auto_run_dir else _empty_artifacts(),
        },
        "next_actions": next_actions,
        "tool_versions": _tool_versions("discover_papers", "run_dry_run", "auto_stage_recommendations_from_run"),
        "input_artifact_hashes": {
            "discovery_run_state": file_sha256(discovery_run_dir / "run-state.json"),
        },
    }
    if auto_run_dir is not None and (auto_run_dir / "run-state.json").exists():
        record["input_artifact_hashes"]["auto_staging_run_state"] = file_sha256(auto_run_dir / "run-state.json")

    write_json_atomic(run_dir / "discover-papers-record.json", record)
    write_text_atomic(run_dir / "report.md", _render_report(record))
    write_json_atomic(
        run_dir / "report.json",
        {
            "workflow_type": "discover-papers",
            "run_id": run_id,
            "status": record["status"],
            "state": record["state"],
            "discovery_run_id": discovery_run_dir.name,
            "auto_staging_run_id": auto_run_id,
            "selection_policy": selection_policy,
            "workflow_mode": workflow_mode,
            "stops_after": record["stops_after"],
            "compiled_wiki_write": False,
            "human_approval_written": False,
            "paper_wiki_invoked": False,
            "auto_stage": auto_stage,
            "auto_staging_plan": record["auto_staging_plan"],
            "session_recommendations": session_recommendations,
            "recommendation_summary": record["recommendation_summary"],
            "manual_downloads": record["manual_downloads"],
            "artifacts": record["artifacts"],
            "next_actions": next_actions,
            "errors": [] if not failed else ["auto-staging failed for at least one candidate"],
        },
    )
    record["output_artifact_hashes"] = _hash_existing_outputs(
        {
            "discover-papers-record.json": run_dir / "discover-papers-record.json",
            "report.md": run_dir / "report.md",
            "report.json": run_dir / "report.json",
        }
    )
    write_json_atomic(run_dir / "run-state.json", record)

    lifecycle = _auto_manage_run_lifecycle(vault_path)
    if lifecycle.get("deleted_count"):
        record["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        write_json_atomic(run_dir / "run-state.json", record)
    _refresh_run_index(vault_path)
    return record
