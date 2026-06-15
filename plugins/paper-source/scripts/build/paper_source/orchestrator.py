from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

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
from paper_source.config import load_config
from paper_source.easyscholar import config_from_environment, enrich_candidates_with_easyscholar
from paper_source.paper_source_repository import (
    cleanup_paper_source_repository,
    ensure_paper_source_repository,
    refresh_paper_source_manifest,
)
from paper_source.feedback import record_feedback
from paper_source.evaluation_loop import build_improvement_brief, render_improvement_brief, write_improvement_brief
from paper_source.filter_candidates import default_discovery_exclusion_terms, filter_candidates, filter_candidates_with_report
from paper_source.orchestrator_discovery import (
    filter_domains_from_profile as _filter_domains_from_profile,
    ranking_keywords_from_profile as _ranking_keywords_from_profile,
    reason_counts as _reason_counts,
    run_query_plan_discovery as _run_query_plan_discovery,
    source_coverage_from_search_record as _source_coverage_from_search_record,
    venue_tiers_from_profile as _venue_tiers_from_profile,
)
from paper_source.normalize_candidates import normalize_candidates
from paper_source.paper_gate import build_paper_gate, render_paper_gate
from paper_source.paper_library import load_existing_paper_index
from paper_source.paper_search_adapter import plan_source_routing
from paper_source.query_plan_build import (
    agent_plan_constraint as _agent_plan_constraint,
    agent_plan_hard_domain_anchors as _agent_plan_hard_domain_anchors,
    agent_plan_soft_recall_terms as _agent_plan_soft_recall_terms,
    agent_plan_strings as _agent_plan_strings,
    apply_agent_supplied_query_inputs as _apply_agent_supplied_query_inputs,
    apply_exact_lookup_query_plan as _apply_exact_lookup_query_plan,
    build_dry_run_query_plan as _build_dry_run_query_plan,
    load_agent_query_plan_json as _load_agent_query_plan_json,
    normalize_code_policy as _normalize_code_policy,
    normalize_year_min as _normalize_year_min,
    query_strategy_for_dry_run as _query_strategy_for_dry_run,
    request_constraints_payload as _request_constraints_payload,
    unique_nonempty_strings as _unique_nonempty_strings,
)
from paper_source.query_planner import build_query_plan_from_research_brief, infer_research_mode
from paper_source.raw_cleanup import cleanup_failed_raw_paper
from paper_source.rank_papers import SELECTION_POLICIES, rank_candidates
from paper_source.redo import redo_acquire, redo_parse, redo_read, redo_read_recritic, recritic
from paper_source.research_brief import ResearchBriefValidationError, load_research_brief
from paper_source.report_run import write_report
from paper_source.orchestrator_repair import write_repair_routed_report
from paper_source.review_sessions import (
    build_review_signature,
    create_or_update_review_session,
    load_review_session_for_resume,
    mark_review_resumed,
    rehydrate_search_record_from_review,
    review_artifact_paths,
)
from paper_source.run_index import (
    auto_prune_run_lifecycle,
    prune_run_lifecycle,
    query_research_queue,
    query_runs,
    refresh_run_index,
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

_LOCAL_TOOL_VERSION = "paper-source-local"


def _ensure_candidate_metadata(paper_root: Path, candidate: dict) -> None:
    metadata_path = paper_root / "metadata.json"
    if metadata_path.exists():
        return
    paper_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(metadata_path, _metadata_from_candidate(candidate))


def _refresh_run_index(vault_path: Path) -> None:
    refresh_run_index(vault_path.resolve())


def _auto_manage_run_lifecycle(vault_path: Path) -> dict:
    result = auto_prune_run_lifecycle(
        vault_path.resolve(),
        keep_latest=15,
        keep_per_workflow=2,
    )
    repository_cleanup = cleanup_paper_source_repository(vault_path)
    if repository_cleanup.get("deleted_count"):
        result["repository_cleanup"] = repository_cleanup
        result["deleted_count"] = int(result.get("deleted_count", 0)) + int(repository_cleanup.get("deleted_count", 0))
    else:
        refresh_paper_source_manifest(vault_path)
    return result


def _hash_paper_run_states(vault_path: Path, results: list[dict]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for result in results:
        slug = result.get("paper_slug")
        if not slug:
            continue
        run_state_path = raw_paper_root(vault_path, slug) / "run-state.json"
        if run_state_path.exists():
            hashes[f"paper:{slug}:run-state.json"] = file_sha256(run_state_path)
        raw_cleanup = result.get("raw_cleanup") if isinstance(result.get("raw_cleanup"), dict) else {}
        manifest_path = raw_cleanup.get("manifest_path")
        if manifest_path and Path(manifest_path).exists():
            hashes[f"paper:{slug}:raw-cleanup.json"] = file_sha256(Path(manifest_path))
    return hashes


def _cleanup_failed_prepare_raw_results(vault_path: Path, results: list[dict]) -> list[dict]:
    cleanup_records: list[dict] = []
    for result in results:
        state = str(result.get("state") or "")
        last_action = str(result.get("last_action") or "")
        slug = str(result.get("paper_slug") or "")
        if not slug or not state.endswith("_failed") or last_action not in {"acquire", "parse", "prepare"}:
            continue
        cleanup = cleanup_failed_raw_paper(
            vault_path,
            slug,
            reason="failed_before_complete_parse",
            stage_record=result.get("stage_record") if isinstance(result.get("stage_record"), dict) else None,
        )
        result["raw_cleanup"] = cleanup
        cleanup_records.append(cleanup)
    return cleanup_records


def _manual_downloads_from_results(results: list[dict]) -> list[dict]:
    cards: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        stage_record = result.get("stage_record")
        if not isinstance(stage_record, dict):
            continue
        manual_download = stage_record.get("manual_download")
        if not isinstance(manual_download, dict):
            continue
        card = dict(manual_download)
        card.setdefault("slug", result.get("paper_slug"))
        card.setdefault("paper_slug", result.get("paper_slug"))
        key = (
            str(card.get("slug") or ""),
            str(card.get("doi") or ""),
            str(card.get("doi_url") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        cards.append(card)
    return cards


def _hash_existing_outputs(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in paths.items():
        if path.exists():
            hashes[name] = file_sha256(path)
    return hashes


def _tool_versions(*tool_names: str) -> dict[str, str]:
    return {tool_name: _LOCAL_TOOL_VERSION for tool_name in tool_names}


def _new_run_dir(vault_path: Path, prefix: str | None = None) -> tuple[str, Path]:
    ensure_paper_source_repository(vault_path)
    runs_dir = runs_root(vault_path)
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{prefix}-{timestamp}" if prefix else timestamp
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _normalize_selection_policy(value: object) -> str:
    policy = str(value or "balanced_high_quality").strip().lower()
    if policy not in SELECTION_POLICIES:
        raise ValueError(f"unknown selection_policy: {value}")
    return policy



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
    resume: bool = True,
    refresh: bool = False,
    from_brief: Path | None = None,
    allow_draft_brief: bool = False,
) -> Path:
    config = load_config(plugin_root=plugin_root, vault_path=vault_path, max_results=max_results)
    selection_policy = _normalize_selection_policy(selection_policy)
    brief_payload: dict | None = None
    brief_metadata: dict | None = None
    if from_brief is not None:
        try:
            loaded_brief = load_research_brief(from_brief, allow_draft=allow_draft_brief)
        except ResearchBriefValidationError as exc:
            raise ValueError(str(exc)) from exc
        brief_payload = loaded_brief["payload"]
        brief_metadata = {
            "path": loaded_brief["json_path"],
            "slug": loaded_brief["slug"],
            "hash": loaded_brief["hash"],
            "status": loaded_brief["status"],
            "revision_number": loaded_brief["revision_number"],
            "formal_use_eligible": loaded_brief["formal_use_eligible"],
            "allow_draft": allow_draft_brief,
        }
        query = brief_payload["task"]
    if not query:
        raise ValueError("query or from_brief is required")
    configured_paper_search_command = (
        config.paper_search_command if config.paper_search_command not in {None, "", "paper-search"} else None
    )
    effective_paper_search_command = paper_search_command or configured_paper_search_command
    requested_sources = sources or config.paper_search_sources
    source_routing = plan_source_routing(requested_sources, query=query)
    effective_sources = source_routing.get("selected_sources") or requested_sources
    run_id, run_dir = _new_run_dir(config.vault_path)
    started_at = utc_now()
    agent_query_plan_payload = _load_agent_query_plan_json(agent_query_plan_json)
    supplied_query_variants = _unique_nonempty_strings(
        _agent_plan_strings(agent_query_plan_payload, "query_variants") + _unique_nonempty_strings(query_variants)
    )
    supplied_domain_focus_terms = _unique_nonempty_strings(domain_focus_terms, split_commas=True)
    agent_soft_recall_terms = _agent_plan_soft_recall_terms(agent_query_plan_payload)
    agent_hard_domain_anchors = _agent_plan_hard_domain_anchors(agent_query_plan_payload)
    request_year_min = _normalize_year_min(
        year_min if year_min is not None else _agent_plan_constraint(agent_query_plan_payload, "year_min")
    )
    request_code_policy = _normalize_code_policy(
        code_policy
        if code_policy is not None
        else _agent_plan_constraint(agent_query_plan_payload, "code_policy")
    )
    request_constraints = _request_constraints_payload(request_year_min, request_code_policy)
    query_plan = None
    if use_query_plan:
        query_plan = (
            build_query_plan_from_research_brief(
                brief_payload,
                max_queries=max(1, query_plan_max_queries),
                profile=config.profile,
                domains=config.domains,
                positive_keywords=config.positive_keywords,
                negative_keywords=config.negative_keywords,
                venue_prior=config.venue_prior,
            )
            if brief_payload is not None
            else _build_dry_run_query_plan(
                query,
                domain=query_plan_domain,
                max_queries=query_plan_max_queries,
                config=config,
            )
        )
    if supplied_query_variants or supplied_domain_focus_terms or agent_query_plan_payload:
        query_plan = _apply_agent_supplied_query_inputs(
            query_plan,
            query=query,
            config=config,
            query_variants=supplied_query_variants,
            domain_focus_terms=supplied_domain_focus_terms,
            agent_query_plan=agent_query_plan_payload,
            agent_query_plan_path=agent_query_plan_json,
            year_min=request_year_min,
            code_policy=request_code_policy,
        )
    if query_plan:
        _apply_exact_lookup_query_plan(query_plan, source_routing)
    research_mode = (query_plan or {}).get("research_mode") or infer_research_mode(query)
    query_strategy = _query_strategy_for_dry_run(query_plan, fixture_path, source_routing)
    review_signature = build_review_signature(
        {
            "query": query,
            "query_plan": query_plan or {},
            "requested_sources": requested_sources,
            "effective_sources": effective_sources,
            "source_routing": source_routing,
            "max_results": config.max_results,
            "profile": config.profile,
            "domains": config.domains,
            "positive_keywords": config.positive_keywords,
            "negative_keywords": config.negative_keywords,
            "venue_prior": config.venue_prior,
            "use_query_plan": use_query_plan,
            "agent_query_variants": supplied_query_variants,
            "agent_domain_focus_terms": supplied_domain_focus_terms,
            "agent_hard_domain_anchors": agent_hard_domain_anchors,
            "agent_soft_recall_terms": agent_soft_recall_terms,
            "agent_query_plan_json": str(agent_query_plan_json) if agent_query_plan_json else None,
            "request_constraints": request_constraints,
            "query_plan_domain": query_plan_domain,
            "query_plan_max_queries": query_plan_max_queries,
            "enable_easyscholar": bool(enable_easyscholar and config.easyscholar_enabled),
            "selection_policy": selection_policy,
            "research_brief": brief_metadata or {},
        }
    )
    resumed_session = None
    if resume and not refresh:
        try:
            resumed_session = load_review_session_for_resume(config.vault_path, review_signature["signature"])
        except FileNotFoundError:
            resumed_session = None
    if query_plan:
        query_plan["source_routing"] = source_routing
        write_json_atomic(run_dir / "query-plan.json", query_plan)

    state = {
        "stage": "paper-discovery-dry-run",
        "run_id": run_id,
        "workflow_type": "paper-discovery-dry-run",
        "state": "configured",
        "status": "running",
        "dry_run": True,
        "query": query,
        "research_mode": research_mode,
        "query_strategy": query_strategy,
        "profile": config.profile,
        "requested_sources": requested_sources,
        "sources": effective_sources,
        "source_routing": source_routing,
        "vault_path": str(config.vault_path),
        "started_at": started_at,
        "tool_versions": _tool_versions(
            "orchestrator",
            "paper_search_adapter",
            "normalize_candidates",
            "filter_candidates",
            "easyscholar",
            "rank_candidates",
            "report_run",
        ),
    }
    if request_constraints:
        state["request_constraints"] = request_constraints
    state["selection_policy"] = selection_policy
    if brief_metadata:
        state["research_brief"] = brief_metadata
    if query_plan:
        state["query_plan"] = {
            "domain": query_plan.get("domain"),
            "query_variant_count": len(query_plan.get("query_variants") or []),
            "path": str(run_dir / "query-plan.json"),
        }
    write_json_atomic(run_dir / "run-state.json", state)

    if resumed_session:
        search_record = rehydrate_search_record_from_review(resumed_session)
    else:
        search_record = _run_query_plan_discovery(
            query=query,
            query_plan=query_plan,
            max_results=config.max_results,
            fixture_path=fixture_path,
            command=effective_paper_search_command,
            sources=effective_sources,
            run_dir=run_dir,
            source_routing=source_routing,
        )
    if brief_metadata:
        search_record["research_brief"] = brief_metadata
    write_json_atomic(run_dir / "search-record.json", search_record)
    state["state"] = "discovered"
    write_json_atomic(run_dir / "run-state.json", state)

    normalized = normalize_candidates(search_record.get("records", []))
    write_json_atomic(run_dir / "normalized.json", normalized)
    state["state"] = "normalized"
    write_json_atomic(run_dir / "run-state.json", state)

    query_exclude_terms = default_discovery_exclusion_terms(query)
    existing_library_index = load_existing_paper_index(config.vault_path)
    filter_report = filter_candidates_with_report(
        normalized,
        domains=_filter_domains_from_profile(config, query_plan),
        require_pdf=True,
        exclude_terms=query_exclude_terms,
        existing_library_index=existing_library_index,
        year_min=request_year_min,
        code_policy=request_code_policy,
    )
    if request_constraints:
        filter_report["request_constraints"] = request_constraints
    filter_report["existing_library"] = {
        "papers_root": existing_library_index.get("papers_root"),
        "count": existing_library_index.get("count", 0),
        "raw_count": existing_library_index.get("raw_count", 0),
        "wiki_count": existing_library_index.get("wiki_count", 0),
        "reference_index_path": existing_library_index.get("reference_index_path"),
        "reference_index_status": existing_library_index.get("reference_index_status"),
        "reference_index_schema": existing_library_index.get("reference_index_schema"),
        "policy": "dedupe wiki _meta/reference-index.json first, then _paper_source/raw metadata fallback",
    }
    filtered = filter_report["kept"]
    staging_ready = filter_report.get("staging_ready", [])
    needs_pdf = filter_report.get("needs_pdf", [])
    rejected = filter_report["rejected"]
    write_json_atomic(run_dir / "filter-report.json", filter_report)
    state["state"] = "filtered"
    write_json_atomic(run_dir / "run-state.json", state)

    easyscholar_config = config_from_environment(
        config.vault_path,
        enabled=bool(enable_easyscholar and config.easyscholar_enabled),
        timeout_seconds=config.easyscholar_timeout_seconds,
        cache_ttl_days=config.easyscholar_cache_ttl_days,
        max_candidates_per_run=config.easyscholar_max_candidates_per_run,
    )
    enriched_filtered, easyscholar_record = enrich_candidates_with_easyscholar(filtered, easyscholar_config)
    easyscholar_record_path = run_dir / "easyscholar-record.json"
    write_json_atomic(easyscholar_record_path, easyscholar_record)
    state["state"] = "quality_enriched"
    state["easyscholar"] = {
        "enabled": easyscholar_record.get("enabled"),
        "summary": easyscholar_record.get("summary", {}),
        "record_path": str(easyscholar_record_path),
    }
    write_json_atomic(run_dir / "run-state.json", state)

    ranked_pool = rank_candidates(
        enriched_filtered,
        positive_keywords=_ranking_keywords_from_profile(config, query, query_plan),
        negative_keywords=config.negative_keywords,
        venue_tiers=_venue_tiers_from_profile(config, query_plan),
        year_min=request_year_min,
        code_policy=request_code_policy,
        selection_policy=selection_policy,
    )
    ranked = ranked_pool[: config.max_results]
    write_json_atomic(run_dir / "rank.json", ranked)
    state["state"] = "ranked"
    write_json_atomic(run_dir / "run-state.json", state)

    errors = [search_record["error"]] if search_record.get("error") else []
    budget_usage = {
        "max_results": config.max_results,
        "raw_candidate_pool_count": len(search_record.get("records", [])),
        "discovered_count": len(normalized),
        "filtered_candidate_pool_count": len(filtered),
        "ranked_candidate_pool_count": len(ranked_pool),
        "accepted_count": len(ranked),
        "staging_ready_count": len(staging_ready),
        "needs_pdf_count": len(needs_pdf),
        "rejected_count": len(rejected),
        "selection_policy": selection_policy,
    }
    if query_plan:
        budget_usage["query_variant_count"] = len(query_plan.get("query_variants") or [])
    if request_constraints:
        budget_usage.update(request_constraints)
    source_coverage = _source_coverage_from_search_record(search_record, deduped_total=len(normalized))
    review_session_payload = None
    if resumed_session:
        mark_review_resumed(resumed_session, run_id)
        review_session_payload = {
            "review_id": resumed_session["review_id"],
            "review_dir": str(resumed_session["review_dir"]),
            "resumed": True,
            "refreshed": False,
            "provider_call_skipped": True,
            "resume_reason": "matching_signature",
            "artifacts": review_artifact_paths(resumed_session),
        }
    else:
        session = create_or_update_review_session(
            config.vault_path,
            topic=query,
            signature=review_signature,
            query_plan=query_plan,
            search_record=search_record,
            normalized=normalized,
            filter_report=filter_report,
            easyscholar_record=easyscholar_record,
            ranked_pool=ranked_pool,
            accepted=ranked,
            coverage=source_coverage,
            run_id=run_id,
            refreshed=refresh,
        )
        review_session_payload = {
            "review_id": session["review_id"],
            "review_dir": session["review_dir"],
            "resumed": False,
            "refreshed": bool(refresh),
            "provider_call_skipped": False,
            "resume_reason": "refresh" if refresh else "created",
            "artifacts": review_artifact_paths(session),
        }
    discovery_context = {
        "research_mode": research_mode,
        "query_strategy": search_record.get("query_strategy", state.get("query_strategy")),
        "query_plan": query_plan or {},
        "candidate_pool": {
            "raw": len(search_record.get("records", [])),
            "normalized": len(normalized),
            "filtered": len(filtered),
            "ranked": len(ranked_pool),
            "accepted": len(ranked),
            "staging_ready": len(staging_ready),
            "needs_pdf": len(needs_pdf),
            "rejected": len(rejected),
        },
        "recommendation_filter": {
            "hard_filter_count": len(rejected),
            "recommendable_count": len(filtered),
            "staging_ready_count": len(staging_ready),
            "needs_pdf_count": len(needs_pdf),
            "policy": "missing PDF affects staging readiness, not recommendation eligibility when identity is stable",
        },
        "existing_library": filter_report.get("existing_library", {}),
        "query_records": search_record.get("query_records", []),
        "source_coverage": source_coverage,
        "request_constraints": request_constraints,
        "warnings": search_record.get("warnings", []),
        "easyscholar": {
            "enabled": easyscholar_record.get("enabled"),
            "summary": easyscholar_record.get("summary", {}),
            "record_path": str(easyscholar_record_path),
        },
        "review_session": review_session_payload,
    }
    discovery_diagnostics = {
        "schema_version": "paper-source-discovery-diagnostics-v1",
        "run_id": run_id,
        "selection_policy": selection_policy,
        "query_plan_contract": {
            "hard_domain_anchors": (query_plan or {}).get("concept_blocks", {}).get("hard_domain_anchors", []),
            "soft_recall_terms": (query_plan or {}).get("soft_recall_terms")
            or (query_plan or {}).get("concept_blocks", {}).get("soft_recall_terms", []),
            "term_provenance": (query_plan or {}).get("term_provenance", {}),
            "policy": "hard filters come only from explicit/config/Research Brief anchors; inferred terms are recall evidence",
        },
        "candidate_pool": discovery_context["candidate_pool"],
        "recommendation_filter": discovery_context["recommendation_filter"],
        "existing_library": filter_report.get("existing_library", {}),
        "rejection_reason_counts": _reason_counts(rejected, "filter_reasons"),
        "readiness_reason_counts": _reason_counts(needs_pdf, "readiness_reasons"),
        "needs_pdf": [
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "doi": candidate.get("doi"),
                "arxiv_id": candidate.get("arxiv_id"),
                "url": candidate.get("url") or candidate.get("publisher_url") or candidate.get("landing_page_url"),
                "readiness_reasons": candidate.get("readiness_reasons", []),
            }
            for candidate in needs_pdf
        ],
        "source_coverage": source_coverage,
    }
    diagnostics_path = run_dir / "discovery-diagnostics.json"
    write_json_atomic(diagnostics_path, discovery_diagnostics)
    discovery_context["diagnostics_path"] = str(diagnostics_path)
    if brief_metadata:
        discovery_context["research_brief"] = brief_metadata
    next_actions = ["Review accepted dry-run candidates before advancing ranked papers."]
    if rejected:
        next_actions.append("Refine the query or domain profile if too many candidates were rejected.")
    else:
        next_actions.append("Run the paper advance workflow on the top dry-run candidates when ready.")
    write_report(
        run_dir,
        ranked,
        errors,
        workflow_type=state["workflow_type"],
        run_id=run_id,
        rejected=rejected,
        quarantined=[],
        critic_failures=[],
        budget_usage=budget_usage,
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        discovery_context=discovery_context,
    )
    state["state"] = "reported"
    state["status"] = "failed" if errors else "success"
    state["finished_at"] = utc_now()
    state["exit_status"] = 1 if errors else 0
    state["review_session"] = review_session_payload
    input_hashes = {
        "request": json_sha256(
            {
                "query": query,
                "max_results": config.max_results,
                "sources": effective_sources,
                "requested_sources": requested_sources,
                "profile": config.profile,
                "query_plan": query_plan,
                "source_routing": source_routing,
                "agent_query_plan_json": str(agent_query_plan_json) if agent_query_plan_json else None,
                "agent_hard_domain_anchors": agent_hard_domain_anchors,
                "agent_soft_recall_terms": agent_soft_recall_terms,
                "request_constraints": request_constraints,
                "selection_policy": selection_policy,
                "research_brief": brief_metadata,
            }
        )
    }
    if agent_query_plan_json is not None and agent_query_plan_json.exists():
        input_hashes["agent-query-plan.json"] = file_sha256(agent_query_plan_json)
    if brief_metadata:
        input_hashes["research-brief.json"] = brief_metadata["hash"]
    if fixture_path is not None and fixture_path.exists():
        input_hashes["fixture.json"] = file_sha256(fixture_path)
    state["input_artifact_hashes"] = input_hashes
    state["output_artifact_hashes"] = _hash_existing_outputs(
        {
            "search-record.json": run_dir / "search-record.json",
            "normalized.json": run_dir / "normalized.json",
            "filter-report.json": run_dir / "filter-report.json",
            "easyscholar-record.json": run_dir / "easyscholar-record.json",
            "discovery-diagnostics.json": run_dir / "discovery-diagnostics.json",
            "rank.json": run_dir / "rank.json",
            "report.md": run_dir / "report.md",
            "paper-search-raw.json": run_dir / "paper-search-raw.json",
            "query-plan.json": run_dir / "query-plan.json",
        }
    )
    write_json_atomic(run_dir / "run-state.json", state)
    lifecycle = _auto_manage_run_lifecycle(config.vault_path)
    if lifecycle.get("deleted_count"):
        state["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        write_json_atomic(run_dir / "run-state.json", state)
    _refresh_run_index(config.vault_path)
    return run_dir


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
        and result.get("next_action") in {"promote-to-wiki", "run-wiki-ingest-agent"}
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
