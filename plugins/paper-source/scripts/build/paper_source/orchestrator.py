from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from paper_source import orchestrator_common as _common_workflows
from paper_source import orchestrator_dry_run as _dry_run_workflows
from paper_source.acquire_papers import _metadata_from_candidate, acquire_paper, acquire_paper_from_url
from paper_source.artifacts import (
    existing_run_dir,
    file_sha256,
    json_sha256,
    raw_paper_root,
    read_json,
    read_json_dict,
    runs_root,
    staging_paper_root,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)
from paper_source.feedback import record_feedback
from paper_source.evaluation_loop import build_improvement_brief, render_improvement_brief, write_improvement_brief
from paper_source.grok_search_adapter import discover_grok
from paper_source.orchestrator_discovery import (
    run_query_plan_discovery as _run_query_plan_discovery,
)
from paper_source.orchestrator_common import (
    _auto_manage_run_lifecycle,
    _cleanup_failed_prepare_raw_results,
    _hash_existing_outputs,
    _hash_paper_run_states,
    _manual_downloads_from_results,
    _normalize_selection_policy,
    _refresh_run_index,
    _tool_versions,
)
from paper_source.paper_gate import build_paper_gate, render_paper_gate
from paper_source.redo import redo_acquire, redo_parse, redo_read, redo_read_recritic, recritic
from paper_source.report_run import write_report
from paper_source.orchestrator_repair import write_repair_routed_report
from paper_source.run_index import (
    prune_run_lifecycle,
    query_research_queue,
    query_runs,
    render_research_queue_query,
    render_run_lifecycle,
    render_runs_query,
)
from paper_source.run_mineru_parse import materialize_mineru_fixture, run_mineru_command
from paper_source.skill_aware_evolve import activate_evolution, propose_evolution, query_evolution, render_evolution_query
from paper_source.source_artifacts import (
    resolve_mineru_markdown_path,
)
from paper_source.stage_wiki import (
    AUDITED_INGEST_MODE,
    FAST_INGEST_MODE,
    REVIEWED_INGEST_MODE,
    normalize_ingest_mode,
    stage_paper,
)
from paper_source.wiki_ingest_handoff import build_wiki_ingest_handoff, render_wiki_ingest_handoff
from paper_source.wiki_ingest_trigger import build_wiki_ingest_trigger, render_wiki_ingest_trigger
from paper_source.wiki_record_workflows import (
    _append_report_sections,
    _write_human_approval_report,
    _write_wiki_ingest_record_report,
    _zotero_record_only,
    record_human_approval,
    record_wiki_ingest,
)
from paper_source.wiki_query import ask_wiki, query_wiki, render_wiki_ask, render_wiki_query
from paper_source.wiki_init import initialize_paper_wiki


def _ensure_candidate_metadata(paper_root: Path, candidate: dict) -> None:
    metadata_path = paper_root / "metadata.json"
    if metadata_path.exists():
        return
    paper_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(metadata_path, _metadata_from_candidate(candidate))


def _new_run_dir(vault_path: Path, prefix: str | None = None) -> tuple[str, Path]:
    _common_workflows.datetime = datetime
    _common_workflows.timezone = timezone
    return _common_workflows._new_run_dir(vault_path, prefix)


_with_paper_search_provider = _dry_run_workflows._with_paper_search_provider
_evaluate_paper_search_good_enough = _dry_run_workflows._evaluate_paper_search_good_enough
_merge_provider_search_records = _dry_run_workflows._merge_provider_search_records
_write_provider_records = _dry_run_workflows._write_provider_records
_run_grok_queries = _dry_run_workflows._run_grok_queries
_has_doi = _dry_run_workflows._has_doi
_doi_recovery_candidates = _dry_run_workflows._doi_recovery_candidates
_doi_recovery_query = _dry_run_workflows._doi_recovery_query
_title_key = _dry_run_workflows._title_key
_apply_recovered_doi_to_original_records = _dry_run_workflows._apply_recovered_doi_to_original_records
_valid_grok_doi_recovery_record = _dry_run_workflows._valid_grok_doi_recovery_record
_normalize_with_doi_recovery = _dry_run_workflows._normalize_with_doi_recovery


def _sync_dry_run_hooks() -> None:
    _common_workflows.datetime = datetime
    _common_workflows.timezone = timezone
    _dry_run_workflows._new_run_dir = _new_run_dir
    _dry_run_workflows._run_query_plan_discovery = _run_query_plan_discovery
    _dry_run_workflows._run_grok_queries = _run_grok_queries
    _dry_run_workflows.discover_grok = discover_grok


def _write_repair_routed_report(
    vault_path: Path,
    slug: str,
    record: dict,
    *,
    started_at: str,
    input_artifact_hashes: dict[str, str],
) -> None:
    write_repair_routed_report(
        vault_path,
        slug,
        record,
        started_at=started_at,
        input_artifact_hashes=input_artifact_hashes,
        new_run_dir=_new_run_dir,
        paper_run_state=_paper_run_state,
        write_paper_run_state=_write_paper_run_state,
        refresh_run_index=_refresh_run_index,
    )


def run_dry_run(
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
    grok_mode: str | None = None,
    no_grok_search: bool = False,
    resume: bool = True,
    refresh: bool = False,
    from_brief: Path | None = None,
    allow_draft_brief: bool = False,
    review_survey_policy: str = "legacy_default",
) -> Path:
    _sync_dry_run_hooks()
    return _dry_run_workflows.run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault_path,
        query=query,
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
        grok_mode=grok_mode,
        no_grok_search=no_grok_search,
        resume=resume,
        refresh=refresh,
        from_brief=from_brief,
        allow_draft_brief=allow_draft_brief,
        review_survey_policy=review_survey_policy,
    )


def run_one_paper_ingest(
    vault_path: Path,
    candidate: dict,
    pdf_path: Path,
    mineru_markdown_path: Path,
    mineru_tex_path: Path | None = None,
    mineru_images_dir: Path | None = None,
    workflow_mode: str = FAST_INGEST_MODE,
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    initialize_paper_wiki(vault_path)
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)

    acquire_record = acquire_paper(candidate, pdf_path, paper_root)
    parse_record = materialize_mineru_fixture(
        paper_root,
        markdown_path=mineru_markdown_path,
        tex_path=mineru_tex_path,
        images_dir=mineru_images_dir,
    )
    reader_record = None
    critic_report = None
    if workflow_mode in {REVIEWED_INGEST_MODE, AUDITED_INGEST_MODE}:
        from paper_source.review.generate_reader import generate_reader_outputs

        reader_record = generate_reader_outputs(paper_root)
    if workflow_mode == AUDITED_INGEST_MODE:
        from paper_source.review.run_critic import run_critics

        critic_report = run_critics(paper_root)
    staging_root = stage_paper(vault_path, slug, paper_root, workflow_mode=workflow_mode)

    run_manifest = {
        "stage": "one-paper-ingest",
        "state": "staged",
        "paper_slug": slug,
        "workflow_mode": workflow_mode,
        "dry_run": False,
        "compiled_wiki_write": False,
        "acquire_record": acquire_record,
        "parse_record": parse_record,
        "reader_record": reader_record,
        "critic_outcome": critic_report["outcome"] if critic_report else "not-run",
        "paper_root": str(paper_root),
        "staging_root": str(staging_root),
    }
    write_json_atomic(paper_root / "run-manifest.json", run_manifest)
    return {
        "paper_root": paper_root,
        "staging_root": staging_root,
        "critic_report": critic_report,
        "run_manifest": run_manifest,
    }


def acquire_paper_from_candidate(vault_path: Path, candidate: dict) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    paper_root = raw_paper_root(vault_path, candidate["slug"])
    return acquire_paper_from_url(candidate, paper_root)


def parse_paper_with_mineru(
    vault_path: Path,
    slug: str,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
) -> dict:
    paper_root = raw_paper_root(vault_path.resolve(), slug)
    if not paper_root.exists():
        raise FileNotFoundError(f"missing raw paper root: {paper_root}")
    return run_mineru_command(paper_root, command=mineru_command, timeout_seconds=mineru_timeout)


def _write_paper_run_state(paper_root: Path, state: dict) -> dict:
    write_json_atomic(paper_root / "run-state.json", state)
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


def advance_paper_once(
    vault_path: Path,
    candidate: dict,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
    workflow_mode: str = FAST_INGEST_MODE,
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    initialize_paper_wiki(vault_path)
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)
    paper_pdf = paper_root / "paper.pdf"
    reader_md = paper_root / "reader" / "reader.md"
    critic_report_path = paper_root / "critic" / "critic-report.json"
    promotion_plan = staging_paper_root(vault_path, slug) / "promotion-plan.json"

    if not paper_pdf.exists():
        record = acquire_paper_from_candidate(vault_path, candidate)
        state = "acquired" if record["status"] == "success" else "acquire_failed"
        next_action = "parse" if record["status"] == "success" else None
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state=state,
                last_action="acquire",
                next_action=next_action,
                stage_record=record,
                workflow_mode=workflow_mode,
            ),
        )

    if not _has_complete_mineru_parse(paper_root):
        record = parse_paper_with_mineru(
            vault_path, slug, mineru_command=mineru_command, mineru_timeout=mineru_timeout
        )
        state = "parsed" if record["status"] == "success" else "parse_failed"
        next_action = (
            "staging"
            if record["status"] == "success" and workflow_mode == FAST_INGEST_MODE
            else "read" if record["status"] == "success" else None
        )
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state=state,
                last_action="parse",
                next_action=next_action,
                stage_record=record,
                workflow_mode=workflow_mode,
            ),
        )

    if workflow_mode in {REVIEWED_INGEST_MODE, AUDITED_INGEST_MODE} and not reader_md.exists():
        from paper_source.review.generate_reader import generate_reader_outputs

        record = generate_reader_outputs(paper_root)
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="read",
                last_action="read",
                next_action="critic" if workflow_mode == AUDITED_INGEST_MODE else "staging",
                stage_record=record,
                workflow_mode=workflow_mode,
            ),
        )

    if workflow_mode == AUDITED_INGEST_MODE and not critic_report_path.exists():
        from paper_source.review.run_critic import run_critics

        record = run_critics(paper_root)
        state = "critic_passed" if record["outcome"] == "pass" else "critic_failed"
        next_action = "staging" if record["outcome"] == "pass" else record.get("next_action")
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state=state,
                last_action="critic",
                next_action=next_action,
                stage_record=record,
                workflow_mode=workflow_mode,
            ),
        )

    critic_report = read_json(critic_report_path) if critic_report_path.exists() else {}
    if critic_report and critic_report.get("outcome") != "pass":
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="critic_failed",
                last_action="awaiting-critic-resolution",
                next_action=critic_report.get("next_action"),
                stage_record=critic_report,
                workflow_mode=workflow_mode,
            ),
        )

    if not promotion_plan.exists():
        staging_root = stage_paper(vault_path, slug, paper_root, workflow_mode=workflow_mode)
        record = {
            "stage": "staging",
            "status": "success",
            "workflow_mode": workflow_mode,
            "staging_root": str(staging_root),
            "promotion_plan": str(promotion_plan),
        }
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="staged",
                last_action="staging",
                next_action="run-wiki-ingest-agent",
                stage_record=record,
                human_gate_required=True,
                workflow_mode=workflow_mode,
            ),
        )

    return _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="staged",
            last_action="awaiting-wiki-ingest",
            next_action="run-wiki-ingest-agent",
            human_gate_required=True,
            workflow_mode=workflow_mode,
        ),
    )


def _research_decision_from_result(result: dict, *, title: str) -> dict | None:
    stage_record = result.get("stage_record")
    if not isinstance(stage_record, dict):
        return None
    decision = stage_record.get("research_decision")
    if not isinstance(decision, dict):
        return None
    payload = dict(decision)
    payload["slug"] = result["paper_slug"]
    payload["title"] = title
    if stage_record.get("research_decision_path"):
        payload["decision_path"] = stage_record["research_decision_path"]
    return payload


def _reader_revision_plan_from_result(result: dict, *, title: str) -> dict | None:
    stage_record = result.get("stage_record")
    if not isinstance(stage_record, dict):
        return None
    plan = stage_record.get("reader_revision_plan")
    if not isinstance(plan, dict):
        return None
    payload = {
        "slug": result["paper_slug"],
        "title": title,
        "recommendation": plan.get("recommendation"),
        "next_action": plan.get("next_action"),
        "blocking_count": len(plan.get("blocking_repairs") or []),
        "warning_count": len(plan.get("warning_followups") or []),
    }
    if stage_record.get("reader_revision_plan_path"):
        payload["plan_path"] = stage_record["reader_revision_plan_path"]
    return payload


def _reproduction_plan_from_result(result: dict, *, title: str) -> dict | None:
    stage_record = result.get("stage_record")
    if not isinstance(stage_record, dict):
        return None
    plan = stage_record.get("reproduction_plan")
    if not isinstance(plan, dict):
        return None
    if plan.get("next_action") == "none":
        return None
    checklist = plan.get("checklist") or []
    payload = {
        "slug": result["paper_slug"],
        "title": title,
        "next_action": plan.get("next_action"),
        "missing_count": len([item for item in checklist if item.get("status") == "missing"]),
        "human_gate_required": bool(plan.get("human_gate_required")),
    }
    if stage_record.get("reproduction_plan_path"):
        payload["plan_path"] = stage_record["reproduction_plan_path"]
    return payload


def advance_paper_batch(
    vault_path: Path,
    candidates: list[dict],
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = None,
    source_run_id: str | None = None,
    candidate_source: Path | None = None,
    workflow_type: str = "advance-batch",
    source_candidate_count: int | None = None,
    skipped_ranked_candidates: list[dict] | None = None,
    rank_decision_filter: list[str] | None = None,
    mineru_timeout: int | None = None,
    workflow_mode: str = FAST_INGEST_MODE,
    selection_policy: str = "balanced_high_quality",
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    selection_policy = _normalize_selection_policy(selection_policy)
    initialize_paper_wiki(vault_path)
    if max_papers is not None and max_papers < 0:
        raise ValueError("max_papers must be greater than or equal to 0")
    skipped_ranked_candidates = skipped_ranked_candidates or []
    source_candidate_count = source_candidate_count if source_candidate_count is not None else len(candidates)

    selected_candidates = candidates[:max_papers] if max_papers is not None else candidates
    run_id, run_dir = _new_run_dir(vault_path, "batch-advance")
    started_at = utc_now()
    results = [
        advance_paper_once(
            vault_path,
            candidate,
            mineru_command=mineru_command,
            mineru_timeout=mineru_timeout,
            workflow_mode=workflow_mode,
        )
        for candidate in selected_candidates
    ]
    failed = any(result["state"].endswith("_failed") for result in results)
    awaiting_promotion = any(
        result.get("human_gate_required")
        and result.get("next_action") in {"run-wiki-ingest-agent"}
        for result in results
    )
    if failed:
        batch_state = "batch_failed"
        status = "failed"
    elif awaiting_promotion:
        batch_state = "awaiting_promotion"
        status = "waiting_for_human_gate"
    else:
        batch_state = "batch_advanced"
        status = "success"

    titles_by_slug = {
        candidate["slug"]: candidate.get("title", candidate["slug"])
        for candidate in selected_candidates
        if candidate.get("slug")
    }
    paper_states = [
        {
            "paper_slug": result["paper_slug"],
            "state": result["state"],
            "next_action": result.get("next_action"),
        }
        for result in results
    ]
    report_paper_states = [
        {
            "slug": result["paper_slug"],
            "paper_slug": result["paper_slug"],
            "title": titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            "state": result["state"],
            "last_action": result.get("last_action"),
            "next_action": result.get("next_action"),
            "human_gate_required": result.get("human_gate_required", False),
        }
        for result in results
    ]
    research_decisions = [
        decision
        for result in results
        for decision in [
            _research_decision_from_result(
                result,
                title=titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            )
        ]
        if decision is not None
    ]
    reader_revision_plans = [
        plan
        for result in results
        for plan in [
            _reader_revision_plan_from_result(
                result,
                title=titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            )
        ]
        if plan is not None
    ]
    reproduction_plans = [
        plan
        for result in results
        for plan in [
            _reproduction_plan_from_result(
                result,
                title=titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            )
        ]
        if plan is not None
    ]
    failed_papers = [
        state
        for state in paper_states
        if state["state"].endswith("_failed")
    ]
    report_failed_papers = [
        state
        for state in report_paper_states
        if state["state"].endswith("_failed")
    ]
    critic_failures = [
        state
        for state in report_paper_states
        if state["state"] == "critic_failed"
    ]
    quarantined = [
        state
        for state in report_paper_states
        if state["state"] == "quarantined"
    ]
    accepted = [
        {
            "slug": state["slug"],
            "title": state["title"],
            "state": state["state"],
        }
        for state in report_paper_states
        if not state["state"].endswith("_failed")
    ]
    next_actions = list(
        dict.fromkeys(
            result["next_action"]
            for result in results
            if result.get("next_action")
        )
    )
    budget_usage = {
        "candidate_count": source_candidate_count,
        "processed_count": len(results),
        "skipped_count": source_candidate_count - len(results),
        "max_papers": max_papers,
        "selection_policy": selection_policy,
    }

    batch = {
        "stage": "batch-advance",
        "run_id": run_id,
        "workflow_type": workflow_type,
        "state": batch_state,
        "status": status,
        "workflow_mode": workflow_mode,
        "selection_policy": selection_policy,
        "vault_path": str(vault_path),
        "candidate_count": source_candidate_count,
        "processed_count": len(results),
        "skipped_count": source_candidate_count - len(results),
        "max_papers": max_papers,
        "skipped_ranked_candidates": skipped_ranked_candidates,
        "compiled_wiki_write": False,
        "human_gate_required": awaiting_promotion,
        "started_at": started_at,
        "tool_versions": _tool_versions("orchestrator", "advance_paper_batch", "advance_paper_once"),
        "results": results,
        "research_decisions": research_decisions,
        "reader_revision_plans": reader_revision_plans,
        "reproduction_plans": reproduction_plans,
    }
    if source_run_id is not None:
        batch["source_run_id"] = source_run_id
    if candidate_source is not None:
        batch["candidate_source"] = str(candidate_source)
    if rank_decision_filter is not None:
        batch["rank_decision_filter"] = rank_decision_filter
    batch["finished_at"] = utc_now()
    batch["exit_status"] = 1 if failed else 0
    input_hashes = {
        "candidates": json_sha256(selected_candidates),
    }
    if candidate_source is not None and candidate_source.exists():
        input_hashes["candidate_source"] = file_sha256(candidate_source)
    batch["input_artifact_hashes"] = input_hashes
    batch["output_artifact_hashes"] = {
        f"paper:{result['paper_slug']}:run-state.json": file_sha256(raw_paper_root(vault_path, result["paper_slug"]) / "run-state.json")
        for result in results
    }
    write_json_atomic(run_dir / "batch-advance-record.json", batch)
    write_json_atomic(run_dir / "run-state.json", batch)
    write_report(
        run_dir,
        accepted,
        [],
        workflow_type=workflow_type,
        run_id=run_id,
        quarantined=quarantined,
        critic_failures=critic_failures,
        paper_states=report_paper_states,
        failed_papers=report_failed_papers,
        budget_usage=budget_usage,
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        research_decisions=research_decisions,
        reader_revision_plans=reader_revision_plans,
        reproduction_plans=reproduction_plans,
    )
    report_json_path = run_dir / "report.json"
    report_payload = read_json(report_json_path)
    report_payload["processed_count"] = batch["processed_count"]
    report_payload["skipped_count"] = batch["skipped_count"]
    report_payload["selection_policy"] = selection_policy
    report_payload["skipped_ranked_candidates"] = skipped_ranked_candidates
    if rank_decision_filter is not None:
        report_payload["rank_decision_filter"] = rank_decision_filter
    report_payload["paper_states"] = paper_states
    report_payload["failed_papers"] = failed_papers
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    report_payload["reader_revision_plans"] = reader_revision_plans
    report_payload["reproduction_plans"] = reproduction_plans
    if source_run_id is not None:
        report_payload["source_run_id"] = source_run_id
    write_json_atomic(report_json_path, report_payload)
    lifecycle = _auto_manage_run_lifecycle(vault_path)
    if lifecycle.get("deleted_count"):
        batch["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        write_json_atomic(run_dir / "run-state.json", batch)
    _refresh_run_index(vault_path)
    return batch


def _rank_decision(candidate: dict) -> str | None:
    protocol = candidate.get("ranking_protocol")
    if not isinstance(protocol, dict):
        return None
    decision = protocol.get("decision")
    return str(decision) if decision else None


def _select_ranked_candidates(
    candidates: list[dict],
    *,
    include_review_candidates: bool,
    selection_policy: str = "balanced_high_quality",
) -> tuple[list[dict], list[dict], list[str]]:
    selection_policy = _normalize_selection_policy(selection_policy)
    allowed = ["advance-candidate"]
    if include_review_candidates or selection_policy in {"balanced_high_quality", "code_preferred", "recent_high_quality", "broad_map"}:
        allowed.append("review-candidate")
    selected: list[dict] = []
    skipped: list[dict] = []
    for candidate in candidates:
        decision = _rank_decision(candidate)
        if decision in allowed:
            if decision == "review-candidate" and not include_review_candidates and selection_policy != "broad_map":
                tier = candidate.get("quality_tier") or (candidate.get("quality_gate") or {}).get("tier")
                if tier not in {"Tier A", "Tier B"}:
                    skipped.append(
                        {
                            "slug": candidate.get("slug"),
                            "title": candidate.get("title"),
                            "decision": decision,
                            "quality_tier": tier,
                            "reason": "review_candidate_below_selection_policy",
                        }
                    )
                    continue
            selected.append(candidate)
            continue
        skipped.append(
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "decision": decision,
                "reason": "decision_not_selected",
            }
        )
    return selected, skipped, allowed


def advance_paper_batch_from_run(
    vault_path: Path,
    run_id: str,
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = None,
    include_review_candidates: bool = False,
    mineru_timeout: int | None = None,
    workflow_mode: str = FAST_INGEST_MODE,
    selection_policy: str = "balanced_high_quality",
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    rank_path = existing_run_dir(vault_path, run_id) / "rank.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    candidates = read_json(rank_path)
    selected_candidates, skipped_ranked_candidates, rank_decision_filter = _select_ranked_candidates(
        candidates,
        include_review_candidates=include_review_candidates,
        selection_policy=selection_policy,
    )
    return advance_paper_batch(
        vault_path,
        selected_candidates,
        mineru_command=mineru_command,
        max_papers=max_papers,
        source_run_id=run_id,
        candidate_source=rank_path,
        workflow_type="advance-ranked",
        source_candidate_count=len(candidates),
        skipped_ranked_candidates=skipped_ranked_candidates,
        rank_decision_filter=rank_decision_filter,
        mineru_timeout=mineru_timeout,
        workflow_mode=workflow_mode,
        selection_policy=selection_policy,
    )


def _prepare_candidate_until_parsed(
    vault_path: Path,
    candidate: dict,
    *,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
    workflow_mode: str = FAST_INGEST_MODE,
) -> dict:
    workflow_mode = normalize_ingest_mode(workflow_mode)
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)
    paper_pdf = paper_root / "paper.pdf"
    reader_md = paper_root / "reader" / "reader.md"
    critic_report_path = paper_root / "critic" / "critic-report.json"
    promotion_plan = staging_paper_root(vault_path, slug) / "promotion-plan.json"

    if not paper_pdf.exists():
        acquire_record = acquire_paper_from_candidate(vault_path, candidate)
        if acquire_record["status"] != "success":
            return _write_paper_run_state(
                paper_root,
                _paper_run_state(
                    paper_root=paper_root,
                    slug=slug,
                    state="acquire_failed",
                    last_action="acquire",
                    next_action=None,
                    stage_record=acquire_record,
                    workflow_mode=workflow_mode,
                ),
            )

    _ensure_candidate_metadata(paper_root, candidate)

    if not _has_complete_mineru_parse(paper_root):
        parse_record = parse_paper_with_mineru(
            vault_path, slug, mineru_command=mineru_command, mineru_timeout=mineru_timeout
        )
        if parse_record["status"] != "success":
            return _write_paper_run_state(
                paper_root,
                _paper_run_state(
                    paper_root=paper_root,
                    slug=slug,
                    state="parse_failed",
                    last_action="parse",
                    next_action=None,
                    stage_record=parse_record,
                    workflow_mode=workflow_mode,
                ),
            )

    if workflow_mode in {REVIEWED_INGEST_MODE, AUDITED_INGEST_MODE} and not reader_md.exists():
        from paper_source.review.generate_reader import generate_reader_outputs

        generate_reader_outputs(paper_root)

    if workflow_mode == AUDITED_INGEST_MODE and not critic_report_path.exists():
        from paper_source.review.run_critic import run_critics

        critic_record = run_critics(paper_root)
        if critic_record["outcome"] != "pass":
            return _write_paper_run_state(
                paper_root,
                _paper_run_state(
                    paper_root=paper_root,
                    slug=slug,
                    state="critic_failed",
                    last_action="critic",
                    next_action=critic_record.get("next_action"),
                    stage_record=critic_record,
                    workflow_mode=workflow_mode,
                ),
            )

    critic_report = read_json(critic_report_path) if critic_report_path.exists() else {}
    if critic_report and critic_report.get("outcome") != "pass":
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="critic_failed",
                last_action="awaiting-critic-resolution",
                next_action=critic_report.get("next_action"),
                stage_record=critic_report,
                workflow_mode=workflow_mode,
            ),
        )

    if not promotion_plan.exists():
        staging_root = stage_paper(vault_path, slug, paper_root, workflow_mode=workflow_mode)
        record = {
            "stage": "staging",
            "status": "success",
            "workflow_mode": workflow_mode,
            "staging_root": str(staging_root),
            "promotion_plan": str(promotion_plan),
        }
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="staged",
                last_action="staging",
                next_action="run-wiki-ingest-agent",
                stage_record=record,
                human_gate_required=True,
                workflow_mode=workflow_mode,
            ),
        )

    return _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="staged",
            last_action="already-staged",
            next_action="run-wiki-ingest-agent",
            human_gate_required=True,
            workflow_mode=workflow_mode,
        ),
    )


def _parse_record_status(paper_root: Path) -> str | None:
    record_path = paper_root / "parse-record.json"
    record = read_json_dict(record_path, default=None)
    if record is None:
        return None
    if isinstance(record, dict) and record.get("status") is not None:
        return str(record.get("status"))
    return None


def _has_complete_mineru_parse(paper_root: Path) -> bool:
    paper_pdf = paper_root / "paper.pdf"
    mineru_dir = paper_root / "mineru"
    mineru_md = resolve_mineru_markdown_path(paper_root)
    mineru_manifest = mineru_dir / "mineru-manifest.json"
    mineru_images = mineru_dir / "images"
    files_complete = (
        paper_pdf.exists()
        and mineru_md.exists()
        and mineru_md.stat().st_size > 0
        and mineru_manifest.exists()
        and mineru_images.is_dir()
    )
    if not files_complete:
        return False
    # A complete parse must also carry a success parse-record. This guards against
    # a crash/kill between writing mineru/ files and parse-record.json, and against
    # corrupted/leftover outputs being silently skipped by --skip-existing.
    return _parse_record_status(paper_root) == "success"


def _has_prepared_source_staging(vault_path: Path, slug: str, workflow_mode: str) -> bool:
    paper_root = raw_paper_root(vault_path, slug)
    if not _has_complete_mineru_parse(paper_root):
        return False
    plan_path = staging_paper_root(vault_path, slug) / "promotion-plan.json"
    plan = read_json_dict(plan_path, default=None)
    if plan is None:
        return False
    return isinstance(plan, dict) and plan.get("workflow_mode") == workflow_mode


def _prepare_candidate_failure_state(
    vault_path: Path,
    candidate: dict,
    exc: Exception,
    *,
    workflow_mode: str = FAST_INGEST_MODE,
) -> dict:
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)
    paper_root.mkdir(parents=True, exist_ok=True)
    workflow_mode = normalize_ingest_mode(workflow_mode)
    record = {
        "stage": "prepare",
        "status": "failed",
        "started_at": utc_now(),
        "finished_at": utc_now(),
        "exit_status": 1,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    return _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="prepare_failed",
            last_action="prepare",
            next_action=None,
            stage_record=record,
            workflow_mode=workflow_mode,
        ),
    )


def prepare_ranked_papers_from_run(
    vault_path: Path,
    run_id: str,
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = 1,
    include_review_candidates: bool = False,
    skip_existing: bool = False,
    mineru_timeout: int | None = None,
    workflow_mode: str = FAST_INGEST_MODE,
    selection_policy: str = "balanced_high_quality",
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    selection_policy = _normalize_selection_policy(selection_policy)
    initialize_paper_wiki(vault_path)
    rank_path = existing_run_dir(vault_path, run_id) / "rank.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    candidates = read_json(rank_path)
    selected_candidates, skipped_ranked_candidates, rank_decision_filter = _select_ranked_candidates(
        candidates,
        include_review_candidates=include_review_candidates,
        selection_policy=selection_policy,
    )
    source_candidate_count = len(candidates)
    skipped_existing_candidates: list[dict] = []
    if skip_existing:
        remaining_candidates = []
        for candidate in selected_candidates:
            slug = candidate.get("slug")
            if slug and _has_prepared_source_staging(vault_path, slug, workflow_mode):
                skipped_existing_candidates.append(
                    {
                        "slug": slug,
                        "title": candidate.get("title", slug),
                        "reason": "already_source_staged",
                    }
                )
                continue
            remaining_candidates.append(candidate)
        selected_candidates = remaining_candidates
    selected_candidates = selected_candidates[:max_papers] if max_papers is not None else selected_candidates
    batch_run_id, batch_run_dir = _new_run_dir(vault_path, "prepare-ranked")
    started_at = utc_now()
    results = []
    for candidate in selected_candidates:
        try:
            result = _prepare_candidate_until_parsed(
                vault_path,
                candidate,
                mineru_command=mineru_command,
                mineru_timeout=mineru_timeout,
                workflow_mode=workflow_mode,
            )
        except Exception as exc:
            result = _prepare_candidate_failure_state(vault_path, candidate, exc, workflow_mode=workflow_mode)
        results.append(result)
    raw_cleanup_records = _cleanup_failed_prepare_raw_results(vault_path, results)
    failed = any(result["state"].endswith("_failed") for result in results)
    awaiting_wiki_ingest = any(result.get("next_action") == "run-wiki-ingest-agent" for result in results)
    titles_by_slug = {
        candidate["slug"]: candidate.get("title", candidate["slug"])
        for candidate in selected_candidates
        if candidate.get("slug")
    }
    paper_states = [
        {
            "paper_slug": result["paper_slug"],
            "state": result["state"],
            "next_action": result.get("next_action"),
        }
        for result in results
    ]
    report_paper_states = [
        {
            "slug": result["paper_slug"],
            "paper_slug": result["paper_slug"],
            "title": titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            "state": result["state"],
            "last_action": result.get("last_action"),
            "next_action": result.get("next_action"),
            "human_gate_required": result.get("human_gate_required", False),
        }
        for result in results
    ]
    failed_papers = [state for state in paper_states if state["state"].endswith("_failed")]
    report_failed_papers = [state for state in report_paper_states if state["state"].endswith("_failed")]
    manual_downloads = _manual_downloads_from_results(results)
    accepted = [
        {
            "slug": state["slug"],
            "title": state["title"],
            "state": state["state"],
        }
        for state in report_paper_states
        if not state["state"].endswith("_failed")
    ]
    next_actions = list(dict.fromkeys(result["next_action"] for result in results if result.get("next_action")))
    batch = {
        "stage": "prepare-ranked",
        "run_id": batch_run_id,
        "workflow_type": "prepare-ranked",
        "state": "prepared" if not failed else "prepare_failed",
        "status": "waiting_for_human_gate" if awaiting_wiki_ingest and not failed else "success" if not failed else "failed",
        "workflow_mode": workflow_mode,
        "selection_policy": selection_policy,
        "vault_path": str(vault_path),
        "candidate_count": source_candidate_count,
        "processed_count": len(results),
        "skipped_count": source_candidate_count - len(results),
        "max_papers": max_papers,
        "source_run_id": run_id,
        "candidate_source": str(rank_path),
        "skipped_ranked_candidates": skipped_ranked_candidates,
        "skipped_existing_candidates": skipped_existing_candidates,
        "rank_decision_filter": rank_decision_filter,
        "skip_existing": skip_existing,
        "compiled_wiki_write": False,
        "human_gate_required": awaiting_wiki_ingest,
        "stops_after": "source-staging",
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 1 if failed else 0,
        "tool_versions": _tool_versions(
            "orchestrator",
            "prepare_ranked_papers_from_run",
            "run_mineru_parse",
            "stage_wiki",
        ),
        "results": results,
        "raw_cleanup": raw_cleanup_records,
        "next_actions": next_actions,
        "input_artifact_hashes": {
            "candidates": json_sha256(selected_candidates),
            "candidate_source": file_sha256(rank_path),
        },
        "output_artifact_hashes": _hash_paper_run_states(vault_path, results),
    }
    write_json_atomic(batch_run_dir / "batch-advance-record.json", batch)
    write_json_atomic(batch_run_dir / "run-state.json", batch)
    write_report(
        batch_run_dir,
        accepted,
        [],
        workflow_type="prepare-ranked",
        run_id=batch_run_id,
        paper_states=report_paper_states,
        failed_papers=report_failed_papers,
        budget_usage={
            "candidate_count": source_candidate_count,
            "processed_count": len(results),
            "skipped_count": source_candidate_count - len(results),
            "max_papers": max_papers,
            "skip_existing": skip_existing,
            "skipped_existing_count": len(skipped_existing_candidates),
            "stops_after": "source-staging",
            "workflow_mode": workflow_mode,
            "selection_policy": selection_policy,
        },
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        manual_downloads=manual_downloads,
    )
    report_json_path = batch_run_dir / "report.json"
    report_payload = read_json(report_json_path)
    report_payload["processed_count"] = batch["processed_count"]
    report_payload["skipped_count"] = batch["skipped_count"]
    report_payload["skipped_ranked_candidates"] = skipped_ranked_candidates
    report_payload["skipped_existing_candidates"] = skipped_existing_candidates
    report_payload["skip_existing"] = skip_existing
    report_payload["rank_decision_filter"] = rank_decision_filter
    report_payload["paper_states"] = paper_states
    report_payload["failed_papers"] = failed_papers
    report_payload["raw_cleanup"] = raw_cleanup_records
    report_payload["manual_downloads"] = manual_downloads
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    report_payload["source_run_id"] = run_id
    report_payload["workflow_mode"] = workflow_mode
    report_payload["stops_after"] = "source-staging"
    write_json_atomic(report_json_path, report_payload)
    lifecycle = _auto_manage_run_lifecycle(vault_path)
    if lifecycle.get("deleted_count"):
        batch["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        write_json_atomic(batch_run_dir / "run-state.json", batch)
    _refresh_run_index(vault_path)
    return batch


def _run_artifacts(run_dir: Path) -> dict:
    return {
        "query_plan": str(run_dir / "query-plan.json") if (run_dir / "query-plan.json").exists() else None,
        "search_record": str(run_dir / "search-record.json") if (run_dir / "search-record.json").exists() else None,
        "filter_report": str(run_dir / "filter-report.json") if (run_dir / "filter-report.json").exists() else None,
        "rank": str(run_dir / "rank.json") if (run_dir / "rank.json").exists() else None,
        "batch_record": str(run_dir / "batch-advance-record.json")
        if (run_dir / "batch-advance-record.json").exists()
        else None,
        "report": str(run_dir / "report.md") if (run_dir / "report.md").exists() else None,
        "report_json": str(run_dir / "report.json") if (run_dir / "report.json").exists() else None,
        "run_state": str(run_dir / "run-state.json") if (run_dir / "run-state.json").exists() else None,
        "progress_events": str(run_dir / "progress-events.jsonl")
        if (run_dir / "progress-events.jsonl").exists()
        else None,
        "progress_summary": str(run_dir / "progress-summary.json")
        if (run_dir / "progress-summary.json").exists()
        else None,
    }


def discover_to_handoff(
    *,
    plugin_root: Path,
    vault_path: Path,
    query: str | None,
    max_results: int | None,
    max_papers: int | None = 10,
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
    grok_mode: str | None = None,
    no_grok_search: bool = False,
    refresh: bool = False,
    from_brief: Path | None = None,
    allow_draft_brief: bool = False,
    include_review_candidates: bool = False,
    skip_existing: bool = True,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
    workflow_mode: str = FAST_INGEST_MODE,
) -> dict:
    vault_path = vault_path.resolve()
    selection_policy = _normalize_selection_policy(selection_policy)
    workflow_mode = normalize_ingest_mode(workflow_mode)
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
        grok_mode=grok_mode,
        no_grok_search=no_grok_search,
        resume=True,
        refresh=refresh,
    )
    prepare_batch = prepare_ranked_papers_from_run(
        vault_path,
        discovery_run_dir.name,
        mineru_command=mineru_command,
        max_papers=max_papers,
        include_review_candidates=include_review_candidates,
        skip_existing=skip_existing,
        mineru_timeout=mineru_timeout,
        workflow_mode=workflow_mode,
        selection_policy=selection_policy,
    )
    prepare_run_dir = runs_root(vault_path) / prepare_batch["run_id"]
    run_id, run_dir = _new_run_dir(vault_path, "discover-to-handoff")
    failed = prepare_batch.get("state") == "prepare_failed"
    next_actions = [
        "Review the source-staging approval report before recording human approval.",
        "Run wiki-ingest-handoff for each prepared slug, then record-human-approval when approved.",
        "Use Paper Wiki $paper-research-wiki after wiki-ingest-trigger; this command does not write final wiki pages.",
    ]
    record = {
        "stage": "discover-to-handoff",
        "run_id": run_id,
        "workflow_type": "discover-to-handoff",
        "state": "handoff_prepared" if not failed else "handoff_prepare_failed",
        "status": prepare_batch.get("status", "failed" if failed else "success"),
        "vault_path": str(vault_path),
        "query": query,
        "max_results": max_results,
        "max_papers": max_papers,
        "selection_policy": selection_policy,
        "workflow_mode": workflow_mode,
        "source_run_id": discovery_run_dir.name,
        "prepare_run_id": prepare_batch["run_id"],
        "processed_count": prepare_batch.get("processed_count", 0),
        "skipped_count": prepare_batch.get("skipped_count", 0),
        "skip_existing": skip_existing,
        "include_review_candidates": include_review_candidates,
        "compiled_wiki_write": False,
        "human_approval_written": False,
        "paper_wiki_invoked": False,
        "stops_after": "source-staging",
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 1 if failed else 0,
        "artifacts": {
            "discovery": _run_artifacts(discovery_run_dir),
            "prepare": _run_artifacts(prepare_run_dir),
        },
        "prepared_papers": [
            {
                "slug": result.get("paper_slug"),
                "state": result.get("state"),
                "next_action": result.get("next_action"),
                "staging_root": str(staging_paper_root(vault_path, result.get("paper_slug", "")))
                if result.get("paper_slug")
                else None,
                "wiki_ingest_brief": str(
                    staging_paper_root(vault_path, result.get("paper_slug", "")) / "wiki-ingest-brief.json"
                )
                if result.get("paper_slug")
                else None,
            }
            for result in prepare_batch.get("results", [])
        ],
        "manual_downloads": _manual_downloads_from_results(prepare_batch.get("results", [])),
        "next_actions": next_actions,
        "tool_versions": _tool_versions("orchestrator", "run_dry_run", "prepare_ranked_papers_from_run"),
        "input_artifact_hashes": {
            "discovery_run_state": file_sha256(discovery_run_dir / "run-state.json"),
            "prepare_run_state": file_sha256(prepare_run_dir / "run-state.json"),
        },
    }
    write_json_atomic(run_dir / "discover-to-handoff-record.json", record)
    write_json_atomic(run_dir / "run-state.json", record)
    report_lines = [
        "# Paper Source Discover To Handoff",
        "",
        f"Run ID: {run_id}",
        f"Discovery run: {discovery_run_dir.name}",
        f"Prepare run: {prepare_batch['run_id']}",
        f"Selection policy: {selection_policy}",
        f"Stops after: {record['stops_after']}",
        f"Final wiki write: {record['compiled_wiki_write']}",
        f"Human approval written: {record['human_approval_written']}",
        "",
        "## Prepared Papers",
    ]
    if record["prepared_papers"]:
        for index, paper in enumerate(record["prepared_papers"], start=1):
            report_lines.append(f"{index}. {paper['slug']} - {paper['state']}")
            if paper.get("wiki_ingest_brief"):
                report_lines.append(f"   - wiki_ingest_brief: {paper['wiki_ingest_brief']}")
            if paper.get("next_action"):
                report_lines.append(f"   - next_action: {paper['next_action']}")
    else:
        report_lines.append("- None.")
    if record["manual_downloads"]:
        report_lines.append("")
        report_lines.append("## Manual Downloads")
        for item in record["manual_downloads"]:
            report_lines.append(f"- {item.get('title') or item.get('slug')}: manual-download-required")
    report_lines.append("")
    report_lines.append("## Next Actions")
    report_lines.extend(f"- {action}" for action in next_actions)
    write_text_atomic(run_dir / "report.md", "\n".join(report_lines) + "\n")
    write_json_atomic(
        run_dir / "report.json",
        {
            "workflow_type": "discover-to-handoff",
            "run_id": run_id,
            "status": record["status"],
            "state": record["state"],
            "source_run_id": discovery_run_dir.name,
            "prepare_run_id": prepare_batch["run_id"],
            "selection_policy": selection_policy,
            "workflow_mode": workflow_mode,
            "stops_after": record["stops_after"],
            "compiled_wiki_write": False,
            "human_approval_written": False,
            "paper_wiki_invoked": False,
            "prepared_papers": record["prepared_papers"],
            "manual_downloads": record["manual_downloads"],
            "artifacts": record["artifacts"],
            "next_actions": next_actions,
            "errors": [] if not failed else ["prepare-ranked failed for at least one candidate"],
        },
    )
    record["output_artifact_hashes"] = _hash_existing_outputs(
        {
            "discover-to-handoff-record.json": run_dir / "discover-to-handoff-record.json",
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


def main() -> int:
    from paper_source.cli import main as cli_main

    return cli_main()

if __name__ == "__main__":
    raise SystemExit(main())
