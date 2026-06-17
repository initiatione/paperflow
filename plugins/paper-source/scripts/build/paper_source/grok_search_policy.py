from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from paper_source.config import GrokSearchConfig


PARALLEL_FAN_IN_GRACE_SECONDS = int(os.environ.get("PAPER_SOURCE_GROK_PARALLEL_GRACE_SECONDS", "180"))


@dataclass(frozen=True)
class EffectiveGrokMode:
    mode: str
    requested_mode: str
    configured: bool
    reason: str | None = None


def grok_runtime_configured() -> bool:
    return bool(os.environ.get("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND"))


def resolve_grok_mode(
    config: GrokSearchConfig,
    *,
    cli_mode: str | None = None,
    no_grok_search: bool = False,
    runtime_configured: bool | None = None,
) -> EffectiveGrokMode:
    if no_grok_search:
        return EffectiveGrokMode(mode="off", requested_mode=cli_mode or config.mode, configured=False, reason="disabled_by_cli")
    requested = cli_mode or config.mode
    if requested == "off":
        return EffectiveGrokMode(mode="off", requested_mode=requested, configured=False, reason="disabled")
    configured = grok_runtime_configured() if runtime_configured is None else runtime_configured
    if not configured:
        return EffectiveGrokMode(mode="off", requested_mode=requested, configured=False, reason="not_configured")
    return EffectiveGrokMode(mode=requested, requested_mode=requested, configured=True, reason=None)


def stable_identity(candidate: dict[str, Any]) -> bool:
    if candidate.get("doi") or candidate.get("arxiv_id"):
        return True
    for key in ("landing_page_url", "publisher_url", "url", "pdf_url"):
        value = str(candidate.get(key) or "").strip().lower()
        if value.startswith(("http://", "https://")):
            return True
    return False


def usable_paper_search_candidate(candidate: dict[str, Any]) -> bool:
    provenance = candidate.get("provider_provenance")
    providers = set(provenance if isinstance(provenance, list) else [])
    raw_records = candidate.get("raw_records") if isinstance(candidate.get("raw_records"), list) else []
    if "paper_search" not in providers:
        for record in raw_records:
            if isinstance(record, dict) and record.get("provider") == "paper_search":
                providers.add("paper_search")
    if "paper_search" not in providers:
        return False
    if candidate.get("filter_status") == "rejected":
        return False
    decision = ((candidate.get("ranking_protocol") or {}) if isinstance(candidate.get("ranking_protocol"), dict) else {}).get("decision")
    readiness = str(candidate.get("staging_readiness") or "")
    return stable_identity(candidate) or readiness in {"staging_ready", "needs_pdf"} or decision in {
        "advance-candidate",
        "review-candidate",
    }


def provider_gap_risk(source_routing: dict[str, Any] | None) -> bool:
    source_routing = source_routing if isinstance(source_routing, dict) else {}
    gaps = source_routing.get("provider_gaps")
    if not isinstance(gaps, list):
        return False
    for gap in gaps:
        if isinstance(gap, dict) and gap.get("importance") in {"required", "recommended"}:
            return True
    return False


def paper_search_good_enough(
    ranked: list[dict[str, Any]],
    *,
    source_routing: dict[str, Any] | None = None,
) -> bool:
    if provider_gap_risk(source_routing):
        return False
    high_quality = []
    stable_or_ready = []
    for candidate in ranked:
        tier = str(candidate.get("quality_tier") or "")
        decision = ((candidate.get("ranking_protocol") or {}) if isinstance(candidate.get("ranking_protocol"), dict) else {}).get("decision")
        if tier in {"Tier A", "Tier B"} or decision == "advance-candidate":
            high_quality.append(candidate)
        if candidate.get("staging_readiness") == "staging_ready" or stable_identity(candidate):
            stable_or_ready.append(candidate)
    return len(high_quality) >= 3 and len(stable_or_ready) >= 2


def _query_variants(query: str, query_plan: dict[str, Any] | None) -> list[str]:
    variants = []
    if isinstance(query_plan, dict):
        variants.extend(str(item).strip() for item in query_plan.get("query_variants") or [] if str(item).strip())
    if not variants:
        variants.append(query)
    return list(dict.fromkeys(variants))


def _gap_terms(source_routing: dict[str, Any] | None) -> list[str]:
    source_routing = source_routing if isinstance(source_routing, dict) else {}
    terms: list[str] = []
    for item in source_routing.get("provider_gaps") or []:
        if isinstance(item, dict):
            provider = str(item.get("provider") or "").strip()
            if provider:
                terms.append(provider)
    for item in source_routing.get("demoted_sources") or []:
        if isinstance(item, dict):
            source = str(item.get("source") or "").strip()
            if source:
                terms.append(source)
    return list(dict.fromkeys(terms))


def build_parallel_grok_queries(
    *,
    query: str,
    query_plan: dict[str, Any] | None,
    source_routing: dict[str, Any] | None,
    budget: int,
) -> list[str]:
    variants = _query_variants(query, query_plan)
    queries: list[str] = []
    for variant in variants:
        queries.append(f"{variant} IEEE ACM publisher DOI PDF")
        if len(queries) >= budget:
            return queries
    for term in _gap_terms(source_routing):
        queries.append(f"{query} {term} academic paper DOI PDF")
        if len(queries) >= budget:
            return list(dict.fromkeys(queries))
    for suffix in ("IEEE Xplore", "ACM Digital Library", "ScienceDirect Springer"):
        queries.append(f"{query} {suffix} DOI PDF")
        if len(queries) >= budget:
            break
    return list(dict.fromkeys(queries))[:budget]


def build_targeted_grok_queries(
    *,
    query: str,
    query_plan: dict[str, Any] | None,
    source_routing: dict[str, Any] | None,
    ranked: list[dict[str, Any]],
    budget: int,
) -> list[str]:
    queries: list[str] = []
    for term in _gap_terms(source_routing):
        queries.append(f"{query} {term} academic paper DOI PDF")
        if len(queries) >= budget:
            return queries
    for variant in _query_variants(query, query_plan):
        queries.append(f"{variant} IEEE ACM ScienceDirect Springer DOI PDF")
        if len(queries) >= budget:
            return list(dict.fromkeys(queries))
    for candidate in ranked[: max(0, budget - len(queries))]:
        title = str(candidate.get("title") or "").strip()
        if title and not candidate.get("pdf_url"):
            queries.append(f'"{title}" PDF DOI')
    if len(queries) < budget:
        queries.append(f"{query} academic publisher DOI PDF")
    return list(dict.fromkeys(queries))[:budget]


def grok_only_quota(ranked: list[dict[str, Any]], cap: int) -> int:
    usable = sum(1 for candidate in ranked if usable_paper_search_candidate(candidate))
    return min(usable, max(0, min(cap, 5)))
