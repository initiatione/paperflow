from __future__ import annotations

from pathlib import Path

from paper_source.artifacts import write_json_atomic
from paper_source.concept_groups import required_concept_groups_from_query_plan
from paper_source.filter_candidates import default_discovery_exclusion_terms
from paper_source.paper_search_adapter import discover, paper_search_provider_readiness, paper_search_source_capabilities
from paper_source.query_plan_build import exact_lookup_query
from paper_source.query_planner import topic_focus_terms


def ranking_keywords_from_profile(config, query: str, query_plan: dict | None) -> list[str]:
    keywords: list[str] = []
    if query_plan:
        blocks = query_plan.get("concept_blocks") or {}
        for key in ("domain_focus_terms", "hard_domain_anchors", "method_or_topic_terms", "problem_terms", "context_terms"):
            for term in blocks.get(key) or []:
                text = str(term).strip()
                if text:
                    keywords.append(text)
        for term in query_plan.get("soft_recall_terms") or []:
            text = str(term).strip()
            if text:
                keywords.append(text)
    keywords.extend(topic_focus_terms(query))
    keywords.extend(config.positive_keywords)
    seen: set[str] = set()
    unique: list[str] = []
    for keyword in keywords:
        normalized = keyword.lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(keyword)
    return unique


def _strings_from_nested(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        terms: list[str] = []
        for item in value.values():
            terms.extend(_strings_from_nested(item))
        return terms
    if isinstance(value, (list, tuple, set)):
        terms: list[str] = []
        for item in value:
            terms.extend(_strings_from_nested(item))
        return terms
    text = str(value).strip()
    return [text] if text else []


def ranking_priority_keywords_from_query_plan(query_plan: dict | None) -> list[str]:
    if not query_plan:
        return []
    blocks = query_plan.get("concept_blocks") or {}
    terms: list[str] = []
    for key in ("hard_domain_anchors", "domain_focus_terms"):
        terms.extend(_strings_from_nested(blocks.get(key)))
    terms.extend(_strings_from_nested(query_plan.get("hard_domain_anchors")))
    hard_constraints = query_plan.get("hard_constraints")
    if isinstance(hard_constraints, dict):
        for key in ("domain_anchors", "hard_domain_anchors", "domain_focus_terms"):
            terms.extend(_strings_from_nested(hard_constraints.get(key)))
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        normalized = term.lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(term)
    return unique


def venue_tiers_from_profile(config, query_plan: dict | None) -> dict[str, float]:
    tiers = {str(venue).lower(): 0.75 for venue in config.venue_prior}
    if query_plan:
        recall = query_plan.get("recall_gap_checks") or {}
        for venue in recall.get("venue_families") or []:
            tiers.setdefault(str(venue).lower(), 0.75)
    return tiers


def ranking_quality_evidence_terms_from_inputs(config, query_plan: dict | None) -> list[object]:
    payloads: list[object] = []
    config_terms = getattr(config, "quality_evidence_terms", None)
    if isinstance(config_terms, (dict, list)) and config_terms:
        payloads.append(config_terms)
    if isinstance(query_plan, dict) and query_plan:
        payloads.append(query_plan)
    return payloads


def filter_domains_from_profile(config, query_plan: dict | None) -> list[str]:
    if query_plan:
        blocks = query_plan.get("concept_blocks") or {}
        domain_focus_terms = blocks.get("domain_focus_terms") or blocks.get("hard_domain_anchors") or []
        if domain_focus_terms:
            return [str(term) for term in domain_focus_terms]
        if query_plan.get("domain") == "research-brief":
            research_brief = query_plan.get("research_brief") or {}
            anchors = research_brief.get("current_intent_anchors") or {}
            domain_focus_terms = anchors.get("domain_focus_terms") or []
            if domain_focus_terms:
                return [str(term) for term in domain_focus_terms]
        return []
    if config.domains:
        return config.domains
    return []


def filter_required_concept_groups_from_query_plan(query_plan: dict | None) -> list[dict]:
    return required_concept_groups_from_query_plan(query_plan)


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


def source_coverage_from_search_record(search_record: dict, deduped_total: int | None = None) -> dict:
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


def reason_counts(candidates: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        for reason in candidate.get(field) or []:
            reason_text = str(reason)
            counts[reason_text] = counts.get(reason_text, 0) + 1
    return counts


def run_query_plan_discovery(
    *,
    query: str,
    query_plan: dict | None,
    max_results: int,
    fixture_path: Path | None,
    command: str | None,
    sources: list[str],
    run_dir: Path,
    source_routing: dict | None = None,
    progress=None,
) -> dict:
    effective_sources = (
        source_routing.get("selected_sources")
        if isinstance(source_routing, dict) and source_routing.get("selected_sources")
        else sources
    )
    exact_lookup = source_routing.get("exact_lookup") if isinstance(source_routing, dict) else None
    if fixture_path is not None or not query_plan or isinstance(exact_lookup, dict):
        discovery_query = exact_lookup_query(source_routing, query) if isinstance(exact_lookup, dict) else query
        discover_kwargs = {
            "query": discovery_query,
            "max_results": max_results,
            "fixture_path": fixture_path,
            "command": command,
            "sources": effective_sources,
            "raw_response_path": run_dir / "paper-search-raw.json",
        }
        if progress is not None:
            search_record = progress.run_with_heartbeat(
                "paper_search",
                "paper-search query started",
                discover,
                heartbeat_message="paper-search query still running",
                details={"query_variant": discovery_query, "query_variant_index": 1, "sources": effective_sources},
                artifacts={"raw_response_path": str(run_dir / "paper-search-raw.json")},
                result_counts=lambda result: {"records": len((result or {}).get("records") or [])},
                **discover_kwargs,
            )
        else:
            search_record = discover(**discover_kwargs)
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
        discover_kwargs = {
            "query": query_variant,
            "max_results": max_results,
            "fixture_path": None,
            "command": command,
            "sources": effective_sources,
            "raw_response_path": raw_path,
        }
        if progress is not None:
            search_record = progress.run_with_heartbeat(
                "paper_search",
                "paper-search query started",
                discover,
                heartbeat_message="paper-search query still running",
                details={"query_variant": query_variant, "query_variant_index": index, "sources": effective_sources},
                artifacts={"raw_response_path": str(raw_path)},
                result_counts=lambda result: {"records": len((result or {}).get("records") or [])},
                **discover_kwargs,
            )
        else:
            search_record = discover(**discover_kwargs)
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
