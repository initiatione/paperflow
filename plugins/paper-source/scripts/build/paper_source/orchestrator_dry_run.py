from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from paper_source.artifacts import file_sha256, json_sha256, utc_now, write_json_atomic
from paper_source.config import load_config
from paper_source.easyscholar import config_from_environment, enrich_candidates_with_easyscholar
from paper_source.filter_candidates import (
    default_discovery_exclusion_terms,
    exclusion_terms_from_query,
    filter_candidates_with_report,
)
from paper_source.grok_search_adapter import SEARCH_TIMEOUT_SECONDS as GROK_SEARCH_TIMEOUT_SECONDS
from paper_source.grok_search_adapter import discover_grok
from paper_source.grok_search_policy import (
    PARALLEL_FAN_IN_GRACE_SECONDS,
    EffectiveGrokMode,
    build_parallel_grok_queries,
    build_targeted_grok_queries,
    paper_search_good_enough,
    resolve_grok_mode,
)
from paper_source.normalize_candidates import normalize_candidates
from paper_source.orchestrator_common import (
    _auto_manage_run_lifecycle,
    _hash_existing_outputs,
    _new_run_dir,
    _normalize_selection_policy,
    _refresh_run_index,
    _tool_versions,
)
from paper_source.orchestrator_discovery import (
    filter_domains_from_profile as _filter_domains_from_profile,
    ranking_keywords_from_profile as _ranking_keywords_from_profile,
    ranking_priority_keywords_from_query_plan as _ranking_priority_keywords_from_query_plan,
    reason_counts as _reason_counts,
    run_query_plan_discovery as _run_query_plan_discovery,
    source_coverage_from_search_record as _source_coverage_from_search_record,
    venue_tiers_from_profile as _venue_tiers_from_profile,
)
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
from paper_source.rank_papers import rank_candidates
from paper_source.research_brief import ResearchBriefValidationError, load_research_brief
from paper_source.report_run import write_report
from paper_source.review_sessions import (
    build_review_signature,
    create_or_update_review_session,
    load_review_session_for_resume,
    mark_review_resumed,
    rehydrate_search_record_from_review,
    review_artifact_paths,
)

DOI_RECOVERY_MAX_CANDIDATES = 5
DOI_RECOVERY_DOMAINS = ["doi.org", "openalex.org", "crossref.org", "arxiv.org"]


def _with_paper_search_provider(records: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for record in records:
        item = dict(record)
        item.setdefault("provider", "paper_search")
        enriched.append(item)
    return enriched


def _evaluate_paper_search_good_enough(
    *,
    paper_search_record: dict,
    config,
    query: str,
    query_plan: dict | None,
    source_routing: dict | None,
    review_survey_policy: str,
    explicit_document_type_exclusions: bool,
    request_year_min: int | None,
    request_code_policy: str | None,
    selection_policy: str,
) -> tuple[bool, list[dict], dict]:
    query_exclude_terms = (
        default_discovery_exclusion_terms(query)
        if review_survey_policy == "legacy_default" or explicit_document_type_exclusions
        else []
    )
    normalized = normalize_candidates(_with_paper_search_provider(paper_search_record.get("records") or []))
    filter_report = filter_candidates_with_report(
        normalized,
        domains=_filter_domains_from_profile(config, query_plan),
        require_pdf=True,
        exclude_terms=query_exclude_terms,
        existing_library_index=load_existing_paper_index(config.vault_path),
        year_min=request_year_min,
        code_policy=request_code_policy,
    )
    ranked_pool = rank_candidates(
        filter_report["kept"],
        positive_keywords=_ranking_keywords_from_profile(config, query, query_plan),
        priority_keywords=_ranking_priority_keywords_from_query_plan(query_plan),
        negative_keywords=config.negative_keywords,
        venue_tiers=_venue_tiers_from_profile(config, query_plan),
        year_min=request_year_min,
        code_policy=request_code_policy,
        selection_policy=selection_policy,
    )
    evaluation = {
        "normalized_count": len(normalized),
        "recommendable_count": len(filter_report["kept"]),
        "staging_ready_count": len(filter_report.get("staging_ready", [])),
        "needs_pdf_count": len(filter_report.get("needs_pdf", [])),
        "ranked_count": len(ranked_pool),
    }
    return paper_search_good_enough(ranked_pool, source_routing=source_routing), ranked_pool, evaluation


def _merge_provider_search_records(
    paper_search_record: dict,
    grok_record: dict | None,
    *,
    grok_mode: str,
    grok_status: str,
    grok_reason: str | None = None,
) -> dict:
    paper_records = _with_paper_search_provider(paper_search_record.get("records") or [])
    grok_records = []
    if isinstance(grok_record, dict):
        grok_records = [dict(record) for record in grok_record.get("records") or [] if isinstance(record, dict)]
        if not paper_records:
            for record in grok_records:
                record["provenance_label"] = "grok_salvage_evidence"
    merged = dict(paper_search_record)
    merged["records"] = [*paper_records, *grok_records]
    merged["provider_records"] = {
        "paper_search": {
            "status": "ok" if not paper_search_record.get("error") else "error",
            "record_count": len(paper_records),
            "raw_response_path": paper_search_record.get("raw_response_path"),
        },
        "grok_search": {
            "mode": grok_mode,
            "status": grok_status,
            "reason": grok_reason,
            "record_count": len(grok_records),
            "raw_response_path": (grok_record or {}).get("raw_response_path") if isinstance(grok_record, dict) else None,
            "evidence_path": (grok_record or {}).get("evidence_path") if isinstance(grok_record, dict) else None,
            "warnings": (grok_record or {}).get("warnings", []) if isinstance(grok_record, dict) else [],
        },
    }
    merged["grok_search"] = merged["provider_records"]["grok_search"]
    merged["paper_search"] = merged["provider_records"]["paper_search"]
    if grok_record and isinstance(grok_record.get("evidence"), list):
        merged["grok_evidence_count"] = len(grok_record["evidence"])
    return merged


def _write_provider_records(run_dir: Path, paper_search_record: dict, grok_record: dict | None) -> None:
    write_json_atomic(run_dir / "paper-search-record.json", paper_search_record)
    if grok_record is not None:
        write_json_atomic(run_dir / "grok-search-record.json", grok_record)


def _run_grok_queries(
    *,
    queries: list[str],
    include_domains: list[str],
    run_dir: Path,
    timeout_seconds: int = GROK_SEARCH_TIMEOUT_SECONDS,
) -> dict:
    return discover_grok(
        queries=queries,
        include_domains=include_domains,
        raw_response_path=run_dir / "grok-search-raw.json",
        evidence_path=run_dir / "grok-search-evidence.json",
        timeout_seconds=timeout_seconds,
    )


def _has_doi(candidate: dict) -> bool:
    return bool(str(candidate.get("doi") or "").strip())


def _doi_recovery_candidates(candidates: list[dict], *, limit: int = DOI_RECOVERY_MAX_CANDIDATES) -> list[dict]:
    selected: list[dict] = []
    for candidate in candidates:
        title = str(candidate.get("title") or "").strip()
        if not title or _has_doi(candidate):
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def _doi_recovery_query(candidate: dict) -> str:
    title = str(candidate.get("title") or "").strip()
    arxiv_id = str(candidate.get("arxiv_id") or "").strip()
    if arxiv_id:
        return f'"{title}" "{arxiv_id}" DOI arXiv OpenAlex Crossref'
    return f'"{title}" DOI OpenAlex Crossref publisher'


def _title_key(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _apply_recovered_doi_to_original_records(search_record: dict, recovery_records: list[dict]) -> int:
    recovered_by_title = {
        _title_key(record.get("title")): record
        for record in recovery_records
        if _title_key(record.get("title")) and _has_doi(record)
    }
    applied = 0
    for record in search_record.get("records") or []:
        if not isinstance(record, dict) or _has_doi(record):
            continue
        recovered = recovered_by_title.get(_title_key(record.get("title")))
        if not recovered:
            continue
        record["doi"] = recovered.get("doi")
        record["doi_source"] = "grok_doi_recovery"
        if not record.get("landing_page_url") and recovered.get("landing_page_url"):
            record["landing_page_url"] = recovered.get("landing_page_url")
        if not record.get("url") and recovered.get("url"):
            record["url"] = recovered.get("url")
        applied += 1
    return applied


def _valid_grok_doi_recovery_record(grok_record: dict, recovery_records: list[dict]) -> tuple[bool, str | None]:
    if grok_record.get("status") != "ok":
        return False, "grok_status_not_ok"
    if not recovery_records:
        return False, "grok_no_records"
    warnings = [str(warning) for warning in grok_record.get("warnings") or [] if str(warning).strip()]
    if warnings:
        return False, "grok_warnings_present"
    return True, None


def _normalize_with_doi_recovery(
    search_record: dict,
    *,
    effective_grok: EffectiveGrokMode,
    run_dir: Path,
) -> tuple[list[dict], dict | None]:
    normalized = normalize_candidates(search_record.get("records", []))
    recovery_candidates = _doi_recovery_candidates(normalized)
    if not recovery_candidates:
        return normalized, {
            "status": "skipped",
            "reason": "no_missing_doi_candidates",
            "candidate_count": 0,
            "recovered_count": 0,
            "failed_count": 0,
        }

    before_missing = {str(candidate.get("slug") or candidate.get("title")) for candidate in recovery_candidates}
    queries = [_doi_recovery_query(candidate) for candidate in recovery_candidates]
    recovery_summary = {
        "status": "skipped",
        "reason": None,
        "candidate_count": len(recovery_candidates),
        "queries": queries,
        "recovered_count": 0,
        "failed_count": len(recovery_candidates),
        "candidates": [
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "year": candidate.get("year"),
                "venue": candidate.get("venue"),
                "arxiv_id": candidate.get("arxiv_id"),
                "primary_url": candidate.get("pdf_url")
                or candidate.get("landing_page_url")
                or candidate.get("publisher_url")
                or candidate.get("url"),
            }
            for candidate in recovery_candidates
        ],
    }
    if not effective_grok.configured:
        recovery_summary["reason"] = "grok_not_configured"
        return normalized, recovery_summary

    grok_record = discover_grok(
        queries=queries,
        include_domains=DOI_RECOVERY_DOMAINS,
        raw_response_path=run_dir / "doi-recovery-grok-raw.json",
        evidence_path=run_dir / "doi-recovery-grok-evidence.json",
        timeout_seconds=GROK_SEARCH_TIMEOUT_SECONDS,
    )
    write_json_atomic(run_dir / "doi-recovery-grok-record.json", grok_record)
    recovery_records = [dict(record) for record in grok_record.get("records") or [] if isinstance(record, dict)]
    provider_records = search_record.setdefault("provider_records", {})
    provider_records["grok_doi_recovery"] = {
        "mode": "targeted_doi_recovery",
        "status": grok_record.get("status"),
        "record_count": len(recovery_records),
        "raw_response_path": grok_record.get("raw_response_path"),
        "evidence_path": grok_record.get("evidence_path"),
        "warnings": grok_record.get("warnings", []),
    }
    valid_recovery, invalid_reason = _valid_grok_doi_recovery_record(grok_record, recovery_records)
    if not valid_recovery:
        recovery_summary.update(
            {
                "status": grok_record.get("status") or "unknown",
                "reason": invalid_reason,
                "record_count": len(recovery_records),
                "applied_count": 0,
                "recovered_count": 0,
                "failed_count": len(before_missing),
                "failed_slugs": sorted(before_missing),
                "record_path": str(run_dir / "doi-recovery-grok-record.json"),
                "raw_response_path": grok_record.get("raw_response_path"),
                "evidence_path": grok_record.get("evidence_path"),
                "warnings": grok_record.get("warnings", []),
            }
        )
        return normalized, recovery_summary

    applied_count = _apply_recovered_doi_to_original_records(search_record, recovery_records)
    search_record.setdefault("records", []).extend(recovery_records)
    normalized_after = normalize_candidates(search_record.get("records", []))
    after_missing = {
        str(candidate.get("slug") or candidate.get("title"))
        for candidate in normalized_after
        if str(candidate.get("slug") or candidate.get("title")) in before_missing and not _has_doi(candidate)
    }
    recovered = sorted(before_missing - after_missing)
    recovery_summary.update(
        {
            "status": grok_record.get("status") or "unknown",
            "reason": "targeted_grok_doi_recovery",
            "record_count": len(recovery_records),
            "applied_count": applied_count,
            "recovered_count": len(recovered),
            "failed_count": len(after_missing),
            "recovered_slugs": recovered,
            "failed_slugs": sorted(after_missing),
            "record_path": str(run_dir / "doi-recovery-grok-record.json"),
            "raw_response_path": grok_record.get("raw_response_path"),
            "evidence_path": grok_record.get("evidence_path"),
            "warnings": grok_record.get("warnings", []),
        }
    )
    return normalized_after, recovery_summary


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
    if review_survey_policy not in {"legacy_default", "include_by_default"}:
        raise ValueError(f"unknown review_survey_policy: {review_survey_policy}")
    explicit_document_type_exclusions = bool(exclusion_terms_from_query(query))
    query_plan = None
    if use_query_plan:
        force_non_review = False if review_survey_policy == "include_by_default" and not explicit_document_type_exclusions else None
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
                non_review=force_non_review,
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
            "grok_mode": grok_mode,
            "no_grok_search": bool(no_grok_search),
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
    effective_grok = resolve_grok_mode(
        config.grok_search,
        cli_mode=grok_mode,
        no_grok_search=no_grok_search,
    )

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
        "grok_search": {
            "mode": effective_grok.mode,
            "requested_mode": effective_grok.requested_mode,
            "configured": effective_grok.configured,
            "reason": effective_grok.reason,
        },
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
        paper_search_record = search_record
        grok_record = None
    else:
        grok_record = None
        if effective_grok.mode == "parallel":
            grok_queries = build_parallel_grok_queries(
                query=query,
                query_plan=query_plan,
                source_routing=source_routing,
                budget=config.grok_search.parallel_query_budget,
            )
            executor = ThreadPoolExecutor(max_workers=2)
            try:
                paper_future = executor.submit(
                    _run_query_plan_discovery,
                    query=query,
                    query_plan=query_plan,
                    max_results=config.max_results,
                    fixture_path=fixture_path,
                    command=effective_paper_search_command,
                    sources=effective_sources,
                    run_dir=run_dir,
                    source_routing=source_routing,
                )
                grok_future = executor.submit(
                    _run_grok_queries,
                    queries=grok_queries,
                    include_domains=config.grok_search.academic_domains.effective_domains,
                    run_dir=run_dir,
                )
                paper_search_record = paper_future.result()
                paper_records = paper_search_record.get("records") or []
                try:
                    grok_record = (
                        grok_future.result()
                        if paper_search_record.get("error") or not paper_records
                        else grok_future.result(timeout=PARALLEL_FAN_IN_GRACE_SECONDS)
                    )
                except TimeoutError:
                    grok_record = {
                        "provider": "grok_search",
                        "source_mode": "grok_search_mcp",
                        "status": "timeout_after_paper_search",
                        "queries": grok_queries,
                        "records": [],
                        "evidence": [],
                        "warnings": ["timeout_after_paper_search"],
                    }
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            search_record = _merge_provider_search_records(
                paper_search_record,
                grok_record,
                grok_mode="parallel",
                grok_status=str(grok_record.get("status") if isinstance(grok_record, dict) else "not_run"),
            )
        else:
            paper_search_record = _run_query_plan_discovery(
                query=query,
                query_plan=query_plan,
                max_results=config.max_results,
                fixture_path=fixture_path,
                command=effective_paper_search_command,
                sources=effective_sources,
                run_dir=run_dir,
                source_routing=source_routing,
            )
            if effective_grok.mode == "targeted":
                good_enough, targeted_ranked_pool, targeted_evaluation = _evaluate_paper_search_good_enough(
                    paper_search_record=paper_search_record,
                    config=config,
                    query=query,
                    query_plan=query_plan,
                    source_routing=source_routing,
                    review_survey_policy=review_survey_policy,
                    explicit_document_type_exclusions=explicit_document_type_exclusions,
                    request_year_min=request_year_min,
                    request_code_policy=request_code_policy,
                    selection_policy=selection_policy,
                )
                paper_search_record["targeted_grok_gate"] = {
                    "good_enough": good_enough,
                    **targeted_evaluation,
                }
                should_run_grok = not good_enough
                if should_run_grok:
                    grok_queries = build_targeted_grok_queries(
                        query=query,
                        query_plan=query_plan,
                        source_routing=source_routing,
                        ranked=targeted_ranked_pool,
                        budget=config.grok_search.targeted_query_budget,
                    )
                    grok_record = _run_grok_queries(
                        queries=grok_queries,
                        include_domains=config.grok_search.academic_domains.effective_domains,
                        run_dir=run_dir,
                    )
                    grok_status = str(grok_record.get("status"))
                    grok_reason = "paper_search_shortfall"
                else:
                    grok_status = "skipped_good_enough"
                    grok_reason = "paper_search_good_enough"
            else:
                grok_status = "off"
                grok_reason = effective_grok.reason
            search_record = _merge_provider_search_records(
                paper_search_record,
                grok_record,
                grok_mode=effective_grok.requested_mode,
                grok_status=grok_status,
                grok_reason=grok_reason,
            )
        _write_provider_records(run_dir, paper_search_record, grok_record)
    if brief_metadata:
        search_record["research_brief"] = brief_metadata
    write_json_atomic(run_dir / "search-record.json", search_record)
    state["state"] = "discovered"
    write_json_atomic(run_dir / "run-state.json", state)

    normalized, doi_recovery = _normalize_with_doi_recovery(
        search_record,
        effective_grok=effective_grok,
        run_dir=run_dir,
    )
    if doi_recovery:
        search_record["doi_recovery"] = doi_recovery
        state["doi_recovery"] = doi_recovery
        write_json_atomic(run_dir / "search-record.json", search_record)
    write_json_atomic(run_dir / "normalized.json", normalized)
    state["state"] = "normalized"
    write_json_atomic(run_dir / "run-state.json", state)

    query_exclude_terms = (
        default_discovery_exclusion_terms(query)
        if review_survey_policy == "legacy_default" or explicit_document_type_exclusions
        else []
    )
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
        "raw_scan_policy": existing_library_index.get("raw_scan_policy"),
        "policy": "dedupe from wiki _meta/reference-index.json when loaded; use _paper_source/raw metadata only as missing-index fallback",
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
        priority_keywords=_ranking_priority_keywords_from_query_plan(query_plan),
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
        "provider_records": search_record.get("provider_records", {}),
        "grok_search": search_record.get("grok_search", state.get("grok_search", {})),
        "doi_recovery": search_record.get("doi_recovery", {}),
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
        "doi_recovery": search_record.get("doi_recovery", {}),
        "provider_records": search_record.get("provider_records", {}),
        "grok_search": search_record.get("grok_search", state.get("grok_search", {})),
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
