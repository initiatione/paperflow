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
from paper_source.generate_reader import generate_reader_outputs
from paper_source.normalize_candidates import normalize_candidates
from paper_source.paper_gate import build_paper_gate, render_paper_gate
from paper_source.paper_library import load_existing_paper_index
from paper_source.paper_search_adapter import (
    discover,
    paper_search_provider_readiness,
    paper_search_source_capabilities,
    plan_source_routing,
)
from paper_source.query_planner import build_query_plan, build_query_plan_from_research_brief, infer_research_mode, topic_focus_terms
from paper_source.raw_cleanup import cleanup_failed_raw_paper
from paper_source.rank_papers import rank_candidates
from paper_source.redo import redo_acquire, redo_parse, redo_read, redo_read_recritic, recritic
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
from paper_source.run_critic import run_critics
from paper_source.run_mineru_parse import materialize_mineru_fixture, run_mineru_command
from paper_source.skill_aware_evolve import activate_evolution, propose_evolution, query_evolution, render_evolution_query
from paper_source.source_artifacts import (
    canonical_mineru_markdown_relative_path,
    has_nonempty_mineru_tex,
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
    _write_promotion_or_rollback_run_state,
    _write_promotion_routed_report,
    _write_rollback_routed_report,
    _write_wiki_ingest_record_report,
    _zotero_record_only,
    promote_paper,
    record_human_approval,
    record_wiki_ingest,
    rollback_promotion,
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


def _build_dry_run_query_plan(query: str, *, domain: str, max_queries: int, config) -> dict:
    return build_query_plan(
        topic=query,
        domain=domain,
        max_queries=max(1, max_queries),
        profile=config.profile,
        domains=config.domains,
        positive_keywords=config.positive_keywords,
        negative_keywords=config.negative_keywords,
        venue_prior=config.venue_prior,
    )


def _exact_lookup_query(source_routing: dict | None, fallback_query: str) -> str:
    exact_lookup = source_routing.get("exact_lookup") if isinstance(source_routing, dict) else None
    if isinstance(exact_lookup, dict) and exact_lookup.get("value"):
        return str(exact_lookup["value"])
    return fallback_query


def _apply_exact_lookup_query_plan(query_plan: dict, source_routing: dict | None) -> None:
    exact_lookup = source_routing.get("exact_lookup") if isinstance(source_routing, dict) else None
    if not isinstance(exact_lookup, dict):
        return
    query_plan["research_mode"] = {
        "schema_version": "paper-source-research-mode-v1",
        "mode": "exact-lookup",
        "spectrum": "fidelity",
        "oversight": "low",
        "signals": [exact_lookup.get("kind")],
        "reason": "The user supplied a DOI, arXiv ID, or explicit title lookup; preserve the identifier instead of expanding the query.",
    }
    query_plan["query_variants"] = [_exact_lookup_query(source_routing, str(query_plan.get("topic") or ""))]


def _query_strategy_for_dry_run(query_plan: dict | None, fixture_path: Path | None, source_routing: dict | None) -> str:
    if fixture_path is not None or not query_plan:
        return "single_query"
    if isinstance(source_routing, dict) and isinstance(source_routing.get("exact_lookup"), dict):
        return "exact_lookup_single_query"
    return "query_plan_multi_query"


def _ranking_keywords_from_profile(config, query: str, query_plan: dict | None) -> list[str]:
    keywords: list[str] = []
    keywords.extend(config.positive_keywords)
    keywords.extend(config.domains)
    keywords.extend(topic_focus_terms(query))
    if not keywords:
        keywords.extend(
            word
            for word in query.replace("-", " ").replace("/", " ").split()
            if len(word) > 2 and word.lower() not in {"latest", "recent", "paper", "papers", "quality"}
        )

    seen: set[str] = set()
    unique_keywords: list[str] = []
    for keyword in keywords:
        normalized = " ".join(str(keyword).lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_keywords.append(str(keyword))
    return unique_keywords


def _venue_tiers_from_profile(config, query_plan: dict | None) -> dict[str, float]:
    venues: list[str] = []
    venues.extend(config.venue_prior)
    if query_plan:
        recall = query_plan.get("recall_gap_checks") or {}
        venue_families = recall.get("venue_families") or []
        if isinstance(venue_families, list):
            venues.extend(
                str(venue)
                for venue in venue_families
                if "configured" not in str(venue).lower() and "field-specific" not in str(venue).lower()
            )

    tiers: dict[str, float] = {}
    for index, venue in enumerate(venues):
        normalized = str(venue).lower()
        if not normalized or normalized in tiers:
            continue
        tiers[normalized] = max(0.75, 1.0 - index * 0.02)
    return tiers


def _filter_domains_from_profile(config, query_plan: dict | None) -> list[str]:
    if query_plan:
        blocks = query_plan.get("concept_blocks") or {}
        domain_focus_terms = blocks.get("domain_focus_terms") or []
        if isinstance(domain_focus_terms, list) and domain_focus_terms:
            return [str(term) for term in domain_focus_terms]
        domain_terms = blocks.get("domain_terms") or []
        if isinstance(domain_terms, list):
            return [str(term) for term in domain_terms]
    if config.domains:
        return config.domains
    return []


def _annotate_query_records(records: list[dict], *, query_variant: str, query_variant_index: int) -> list[dict]:
    annotated: list[dict] = []
    for record in records:
        enriched = dict(record)
        enriched["query_variant"] = query_variant
        enriched["query_variant_index"] = query_variant_index
        annotated.append(enriched)
    return annotated


def _merged_source_mode(query_records: list[dict]) -> str:
    modes = sorted({str(record.get("source_mode") or "unknown") for record in query_records})
    if not modes:
        return "query_plan_multi_query"
    if len(modes) == 1:
        return modes[0]
    return "query_plan_mixed"


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _ordered_sources_from_upstream(upstream: dict) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    source_candidates: list[object] = []
    sources_used = upstream.get("sources_used")
    if isinstance(sources_used, list):
        source_candidates.extend(sources_used)
    source_results = upstream.get("source_results")
    if isinstance(source_results, dict):
        source_candidates.extend(source_results)
    errors = upstream.get("errors")
    if isinstance(errors, dict):
        source_candidates.extend(errors)
    for source in source_candidates:
        source_name = str(source)
        if not source_name or source_name in seen:
            continue
        seen.add(source_name)
        ordered.append(source_name)
    return ordered


def _source_coverage_from_single_record(search_record: dict, deduped_total: int | None = None) -> dict:
    upstream = search_record.get("upstream")
    if not isinstance(upstream, dict) or not upstream:
        return {}

    source_results: dict[str, int] = {}
    upstream_results = upstream.get("source_results")
    if isinstance(upstream_results, dict):
        for source, count in upstream_results.items():
            source_results[str(source)] = _int_or_none(count) or 0

    errors: dict[str, str] = {}
    upstream_errors = upstream.get("errors")
    if isinstance(upstream_errors, dict):
        errors = {str(source): str(error) for source, error in upstream_errors.items() if str(error)}

    raw_total = (
        _int_or_none(upstream.get("raw_total"))
        if upstream.get("raw_total") is not None
        else _int_or_none(upstream.get("total"))
    )
    if raw_total is None:
        raw_total = len(search_record.get("records") or [])
    if deduped_total is None:
        deduped_total = _int_or_none(upstream.get("total"))
    if deduped_total is None:
        deduped_total = len(search_record.get("records") or [])

    sources_used = _ordered_sources_from_upstream(upstream)

    coverage = {
        "sources_used": sources_used,
        "source_results": source_results,
        "errors": errors,
        "raw_total": raw_total,
        "deduped_total": deduped_total,
        "query_count": 1,
        "capabilities": paper_search_source_capabilities(sources_used),
        "provider_readiness": paper_search_provider_readiness(sources_used),
    }
    if isinstance(upstream.get("source_health"), dict):
        coverage["source_health"] = upstream["source_health"]
    if upstream.get("timeout_budget_seconds") is not None:
        coverage["timeout_budget_seconds"] = upstream.get("timeout_budget_seconds")
    if upstream.get("search_duration_ms") is not None:
        coverage["search_duration_ms"] = upstream.get("search_duration_ms")
    if isinstance(search_record.get("source_routing"), dict):
        coverage["source_routing"] = search_record["source_routing"]
        coverage["provider_readiness"] = search_record["source_routing"].get(
            "provider_readiness", coverage["provider_readiness"]
        )
    return coverage


def _merge_source_error(errors: dict[str, str], source: str, error: object) -> None:
    error_text = str(error)
    if not error_text:
        return
    existing = errors.get(source)
    if not existing:
        errors[source] = error_text
    elif error_text not in existing.split("; "):
        errors[source] = f"{existing}; {error_text}"


def _source_coverage_from_search_record(search_record: dict, deduped_total: int | None = None) -> dict:
    query_records = search_record.get("query_records")
    if not isinstance(query_records, list) or not query_records:
        return _source_coverage_from_single_record(search_record, deduped_total=deduped_total)

    sources_used: list[str] = []
    seen_sources: set[str] = set()
    source_results: dict[str, int] = {}
    source_health: dict[str, dict] = {}
    errors: dict[str, str] = {}
    raw_total = 0
    timeout_budget_seconds: int | None = None
    search_duration_ms = 0

    for query_record in query_records:
        if not isinstance(query_record, dict):
            continue
        upstream = query_record.get("upstream")
        upstream = upstream if isinstance(upstream, dict) else {}
        for source in _ordered_sources_from_upstream(upstream):
            if source not in seen_sources:
                seen_sources.add(source)
                sources_used.append(source)

        upstream_results = upstream.get("source_results")
        if isinstance(upstream_results, dict):
            for source, count in upstream_results.items():
                source_name = str(source)
                source_results[source_name] = source_results.get(source_name, 0) + (_int_or_none(count) or 0)
                if source_name not in seen_sources:
                    seen_sources.add(source_name)
                    sources_used.append(source_name)

        upstream_health = upstream.get("source_health")
        if isinstance(upstream_health, dict):
            for source, state in upstream_health.items():
                source_name = str(source)
                if isinstance(state, dict):
                    source_health[source_name] = dict(state)
                if source_name not in seen_sources:
                    seen_sources.add(source_name)
                    sources_used.append(source_name)

        upstream_errors = upstream.get("errors")
        if isinstance(upstream_errors, dict):
            for source, error in upstream_errors.items():
                source_name = str(source)
                _merge_source_error(errors, source_name, error)
                if source_name not in seen_sources:
                    seen_sources.add(source_name)
                    sources_used.append(source_name)

        record_raw_total = (
            _int_or_none(upstream.get("raw_total"))
            if upstream.get("raw_total") is not None
            else _int_or_none(upstream.get("total"))
        )
        if record_raw_total is None:
            record_raw_total = _int_or_none(query_record.get("record_count")) or 0
        raw_total += record_raw_total
        if upstream.get("timeout_budget_seconds") is not None:
            timeout_budget_seconds = _int_or_none(upstream.get("timeout_budget_seconds"))
        search_duration_ms += _int_or_none(upstream.get("search_duration_ms")) or 0

    if not sources_used and not source_results and not errors and raw_total == 0:
        return {}

    coverage = {
        "sources_used": sources_used,
        "source_results": source_results,
        "errors": errors,
        "raw_total": raw_total,
        "deduped_total": deduped_total if deduped_total is not None else len(search_record.get("records") or []),
        "query_count": len(query_records),
        "capabilities": paper_search_source_capabilities(sources_used),
        "provider_readiness": paper_search_provider_readiness(sources_used),
    }
    if source_health:
        coverage["source_health"] = source_health
    if timeout_budget_seconds is not None:
        coverage["timeout_budget_seconds"] = timeout_budget_seconds
    if search_duration_ms:
        coverage["search_duration_ms"] = search_duration_ms
    if isinstance(search_record.get("source_routing"), dict):
        coverage["source_routing"] = search_record["source_routing"]
        coverage["provider_readiness"] = search_record["source_routing"].get(
            "provider_readiness", coverage["provider_readiness"]
        )
    return coverage


def _run_query_plan_discovery(
    *,
    query: str,
    query_plan: dict | None,
    max_results: int,
    fixture_path: Path | None,
    command: str | None,
    sources: list[str],
    run_dir: Path,
    source_routing: dict | None = None,
) -> dict:
    effective_sources = (
        source_routing.get("selected_sources")
        if isinstance(source_routing, dict) and source_routing.get("selected_sources")
        else sources
    )
    exact_lookup = source_routing.get("exact_lookup") if isinstance(source_routing, dict) else None
    if fixture_path is not None or not query_plan or isinstance(exact_lookup, dict):
        discovery_query = _exact_lookup_query(source_routing, query) if isinstance(exact_lookup, dict) else query
        search_record = discover(
            query=discovery_query,
            max_results=max_results,
            fixture_path=fixture_path,
            command=command,
            sources=effective_sources,
            raw_response_path=run_dir / "paper-search-raw.json",
        )
        if query_plan:
            search_record["query_plan"] = query_plan
            search_record["query_strategy"] = (
                "fixture_single_query"
                if fixture_path is not None
                else "exact_lookup_single_query"
                if isinstance(exact_lookup, dict)
                else "single_query"
            )
            if isinstance(exact_lookup, dict):
                search_record["query_records"] = []
        if source_routing:
            search_record["source_routing"] = source_routing
        return search_record

    query_variants = query_plan.get("query_variants") or [query]
    query_records: list[dict] = []
    combined_records: list[dict] = []
    query_errors: list[str] = []
    for index, query_variant in enumerate(query_variants, start=1):
        raw_path = run_dir / f"paper-search-raw-{index:02d}.json"
        search_record = discover(
            query=query_variant,
            max_results=max_results,
            fixture_path=None,
            command=command,
            sources=effective_sources,
            raw_response_path=raw_path,
        )
        if search_record.get("error"):
            query_errors.append(f"{query_variant}: {search_record['error']}")
        query_records.append(
            {
                "index": index,
                "query": query_variant,
                "source_mode": search_record.get("source_mode"),
                "record_count": len(search_record.get("records") or []),
                "raw_response_path": search_record.get("raw_response_path"),
                "error": search_record.get("error"),
                "upstream": search_record.get("upstream", {}),
            }
        )
        combined_records.extend(
            _annotate_query_records(
                search_record.get("records") or [],
                query_variant=query_variant,
                query_variant_index=index,
            )
        )

    aggregate_raw_path = run_dir / "paper-search-raw.json"
    write_json_atomic(
        aggregate_raw_path,
        {
            "query": query,
            "query_strategy": "query_plan_multi_query",
            "query_plan": query_plan,
            "query_records": query_records,
            "raw_candidate_count": len(combined_records),
        },
    )
    combined = {
        "query": query,
        "max_results": max_results,
        "source_mode": _merged_source_mode(query_records),
        "query_strategy": "query_plan_multi_query",
        "query_plan": query_plan,
        "query_records": query_records,
        "raw_response_path": str(aggregate_raw_path),
        "records": combined_records,
    }
    if source_routing:
        combined["source_routing"] = source_routing
    if query_errors and not combined_records:
        combined["error"] = "; ".join(query_errors)
    elif query_errors:
        combined["warnings"] = query_errors
    return combined


def _append_revision_delta_section(report_md_path: Path, revision_delta: dict | None) -> None:
    if not revision_delta:
        return
    existing = report_md_path.read_text(encoding="utf-8").rstrip()
    before = revision_delta.get("before") or {}
    after = revision_delta.get("after") or {}
    lines = [
        "## Revision Delta",
        f"- before blocking repairs: {before.get('blocking_count', 0)}",
        f"- before warning follow-ups: {before.get('warning_count', 0)}",
        f"- after blocking repairs: {after.get('blocking_count', 0)}",
        f"- after warning follow-ups: {after.get('warning_count', 0)}",
        "- resolved blocking checks: "
        + (", ".join(revision_delta.get("resolved_blocking_checks") or []) or "None"),
        "- remaining blocking checks: "
        + (", ".join(revision_delta.get("remaining_blocking_checks") or []) or "None"),
        "- remaining warning checks: "
        + (", ".join(revision_delta.get("remaining_warning_checks") or []) or "None"),
    ]
    write_text_atomic(report_md_path, existing + "\n\n" + "\n".join(lines) + "\n")


def _paper_title(vault_path: Path, slug: str) -> str:
    metadata_path = raw_paper_root(vault_path, slug) / "metadata.json"
    if not metadata_path.exists():
        return slug
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return slug
    return metadata.get("title") or slug


def _repair_report_contract(vault_path: Path, slug: str, record: dict) -> tuple[dict, list[str], list[str]]:
    stage = record["stage"]
    if stage == "redo-acquire":
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reacquired",
                "last_action": "redo-acquire",
                "next_action": "redo-parse",
                "human_gate_required": False,
            },
            ["paper.pdf"],
            ["redo-parse the reacquired PDF"],
        )
    if stage == "redo-parse":
        changed_artifacts = [canonical_mineru_markdown_relative_path(slug)]
        if has_nonempty_mineru_tex(raw_paper_root(vault_path, slug)):
            changed_artifacts.append("mineru/paper.tex")
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reparsed",
                "last_action": "redo-parse",
                "next_action": "redo-read",
                "human_gate_required": False,
            },
            changed_artifacts,
            ["redo-read the reparsed paper"],
        )
    if stage == "redo-read":
        changed_artifacts = [
            "reader/reader.md",
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/figures.md",
            "reader/reproducibility.md",
            "reader/implementation-ideas.md",
        ]
        guidance_path = raw_paper_root(vault_path, slug) / "reader" / "revision-guidance.md"
        if guidance_path.exists():
            changed_artifacts.append("reader/revision-guidance.md")
        changed_artifacts.append("reader/evidence-map.json")
        changed_artifacts.append("reader/claim-support.json")
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reader_regenerated",
                "last_action": "redo-read",
                "next_action": "recritic",
                "human_gate_required": False,
            },
            changed_artifacts,
            ["recritic the regenerated reader outputs"],
        )
    if stage == "recritic":
        critic_report_path = raw_paper_root(vault_path, slug) / "critic" / "critic-report.json"
        critic_report = json.loads(critic_report_path.read_text(encoding="utf-8"))
        next_action = critic_report.get("next_action", "stage")
        state = "critic_passed" if next_action == "stage" else "critic_failed"
        next_actions = (
            ["stage the paper for promotion review"]
            if next_action == "stage"
            else ["revise the reader outputs before another critic pass"]
        )
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": state,
                "last_action": "recritic",
                "next_action": next_action,
                "human_gate_required": False,
            },
            ["critic/critic-report.json"],
            next_actions,
        )
    if stage == "redo-read-recritic":
        critic_report_path = raw_paper_root(vault_path, slug) / "critic" / "critic-report.json"
        critic_report = json.loads(critic_report_path.read_text(encoding="utf-8"))
        next_action = critic_report.get("next_action", "stage")
        state = "critic_passed" if next_action == "stage" else "critic_failed"
        next_actions = (
            ["stage the paper for promotion review"]
            if next_action == "stage"
            else ["revise the reader outputs before another critic pass"]
        )
        changed_artifacts = [
            "reader/reader.md",
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/figures.md",
            "reader/reproducibility.md",
            "reader/implementation-ideas.md",
            "reader/revision-guidance.md",
            "reader/evidence-map.json",
            "reader/claim-support.json",
            "critic/critic-report.json",
            "critic/critic-quorum.json",
            "critic/research-decision.json",
            "critic/research-decision.md",
            "critic/reader-revision-plan.json",
            "critic/reader-revision-plan.md",
        ]
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": state,
                "last_action": "redo-read-recritic",
                "next_action": next_action,
                "human_gate_required": False,
            },
            changed_artifacts,
            next_actions,
        )
    raise ValueError(f"unsupported repair stage: {stage}")


def _write_repair_run_state(
    run_dir: Path,
    *,
    run_id: str,
    workflow_type: str,
    vault_path: Path,
    slug: str,
    state: str,
    status: str,
    started_at: str,
    input_artifact_hashes: dict[str, str],
    changed_artifacts: list[str],
) -> None:
    paper_root = raw_paper_root(vault_path, slug)
    output_paths = {
        artifact: paper_root / artifact
        for artifact in changed_artifacts
    }
    output_paths["redo-records.jsonl"] = paper_root / "redo-records.jsonl"
    output_paths["report.md"] = run_dir / "report.md"
    output_paths["report.json"] = run_dir / "report.json"
    write_json_atomic(
        run_dir / "run-state.json",
        {
            "stage": workflow_type,
            "run_id": run_id,
            "workflow_type": workflow_type,
            "state": state,
            "status": status,
            "paper_slug": slug,
            "vault_path": str(vault_path.resolve()),
            "compiled_wiki_write": False,
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_status": 0 if status == "success" else 1,
            "tool_versions": _tool_versions("orchestrator", "report_run", "redo"),
            "input_artifact_hashes": input_artifact_hashes,
            "output_artifact_hashes": _hash_existing_outputs(output_paths),
        },
    )


def _write_repair_routed_report(
    vault_path: Path,
    slug: str,
    record: dict,
    *,
    started_at: str,
    input_artifact_hashes: dict[str, str],
) -> None:
    workflow_type = record["stage"]
    run_id, run_dir = _new_run_dir(vault_path.resolve(), workflow_type)
    paper_state, changed_artifacts, next_actions = _repair_report_contract(vault_path, slug, record)
    write_report(
        run_dir,
        [],
        [],
        workflow_type=workflow_type,
        run_id=run_id,
        paper_states=[paper_state],
        failed_papers=[],
        budget_usage={"paper_count": 1},
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        changed_artifacts=changed_artifacts,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {
            "paper_slug": slug,
            "state": paper_state["state"],
            "next_action": paper_state["next_action"],
        }
    ]
    report_payload["failed_papers"] = []
    report_payload["changed_artifacts"] = changed_artifacts
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    if record.get("revision_delta"):
        report_payload["revision_delta"] = record["revision_delta"]
    write_json_atomic(report_json_path, report_payload)
    _append_revision_delta_section(run_dir / "report.md", record.get("revision_delta"))
    _write_repair_run_state(
        run_dir,
        run_id=run_id,
        workflow_type=workflow_type,
        vault_path=vault_path,
        slug=slug,
        state=paper_state["state"],
        status=record.get("status", "success"),
        started_at=started_at,
        input_artifact_hashes=input_artifact_hashes,
        changed_artifacts=changed_artifacts,
    )
    paper_root = raw_paper_root(vault_path.resolve(), slug)
    if workflow_type in {"recritic", "redo-read-recritic"}:
        stage_record = json.loads((paper_root / "critic" / "critic-report.json").read_text(encoding="utf-8"))
    else:
        stage_record = record
    _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state=paper_state["state"],
            last_action=paper_state["last_action"],
            next_action=paper_state["next_action"],
            stage_record=stage_record,
            human_gate_required=paper_state.get("human_gate_required", False),
        ),
    )
    _refresh_run_index(vault_path)


def run_dry_run(
    plugin_root: Path,
    vault_path: Path,
    query: str | None,
    max_results: int | None,
    fixture_path: Path | None = None,
    paper_search_command: str | None = None,
    sources: list[str] | None = None,
    use_query_plan: bool = True,
    query_plan_domain: str = "auto",
    query_plan_max_queries: int = 6,
    enable_easyscholar: bool = True,
    resume: bool = True,
    refresh: bool = False,
    from_brief: Path | None = None,
    allow_draft_brief: bool = False,
) -> Path:
    config = load_config(plugin_root=plugin_root, vault_path=vault_path, max_results=max_results)
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
            "query_plan_domain": query_plan_domain,
            "query_plan_max_queries": query_plan_max_queries,
            "enable_easyscholar": bool(enable_easyscholar and config.easyscholar_enabled),
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
    )
    filter_report["existing_library"] = {
        "papers_root": existing_library_index.get("papers_root"),
        "count": existing_library_index.get("count", 0),
    }
    filtered = filter_report["kept"]
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
        "rejected_count": len(rejected),
    }
    if query_plan:
        budget_usage["query_variant_count"] = len(query_plan.get("query_variants") or [])
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
            "rejected": len(rejected),
        },
        "query_records": search_record.get("query_records", []),
        "source_coverage": source_coverage,
        "warnings": search_record.get("warnings", []),
        "easyscholar": {
            "enabled": easyscholar_record.get("enabled"),
            "summary": easyscholar_record.get("summary", {}),
            "record_path": str(easyscholar_record_path),
        },
        "review_session": review_session_payload,
    }
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
                "research_brief": brief_metadata,
            }
        )
    }
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
        reader_record = generate_reader_outputs(paper_root)
    if workflow_mode == AUDITED_INGEST_MODE:
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

    critic_report = json.loads(critic_report_path.read_text(encoding="utf-8")) if critic_report_path.exists() else {}
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
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
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
    }

    batch = {
        "stage": "batch-advance",
        "run_id": run_id,
        "workflow_type": workflow_type,
        "state": batch_state,
        "status": status,
        "workflow_mode": workflow_mode,
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
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["processed_count"] = batch["processed_count"]
    report_payload["skipped_count"] = batch["skipped_count"]
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
) -> tuple[list[dict], list[dict], list[str]]:
    allowed = ["advance-candidate"]
    if include_review_candidates:
        allowed.append("review-candidate")
    selected: list[dict] = []
    skipped: list[dict] = []
    for candidate in candidates:
        decision = _rank_decision(candidate)
        if decision in allowed:
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
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    rank_path = existing_run_dir(vault_path, run_id) / "rank.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    candidates = json.loads(rank_path.read_text(encoding="utf-8"))
    selected_candidates, skipped_ranked_candidates, rank_decision_filter = _select_ranked_candidates(
        candidates,
        include_review_candidates=include_review_candidates,
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
        generate_reader_outputs(paper_root)

    if workflow_mode == AUDITED_INGEST_MODE and not critic_report_path.exists():
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

    critic_report = json.loads(critic_report_path.read_text(encoding="utf-8")) if critic_report_path.exists() else {}
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
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
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
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
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
) -> dict:
    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    initialize_paper_wiki(vault_path)
    rank_path = existing_run_dir(vault_path, run_id) / "rank.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    candidates = json.loads(rank_path.read_text(encoding="utf-8"))
    selected_candidates, skipped_ranked_candidates, rank_decision_filter = _select_ranked_candidates(
        candidates,
        include_review_candidates=include_review_candidates,
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
        },
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        manual_downloads=manual_downloads,
    )
    report_json_path = batch_run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
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


def main() -> int:
    from paper_source.cli import main as cli_main

    return cli_main()

if __name__ == "__main__":
    raise SystemExit(main())
