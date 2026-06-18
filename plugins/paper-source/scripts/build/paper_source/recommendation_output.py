from __future__ import annotations

from collections import Counter
from typing import Any

from paper_source.grok_search_policy import grok_only_quota, usable_paper_search_candidate

SCHEMA_VERSION = "paper-source-session-recommendations-v1"
DEFAULT_PRIMARY_LIMIT = 10


def _text(value: object) -> str:
    return str(value or "").strip()


def _decision(candidate: dict[str, Any]) -> str:
    protocol = candidate.get("ranking_protocol")
    protocol = protocol if isinstance(protocol, dict) else {}
    return _text(protocol.get("decision"))


def _quality_tier(candidate: dict[str, Any]) -> str:
    tier = _text(candidate.get("quality_tier"))
    if tier:
        return tier
    gate = candidate.get("quality_gate")
    gate = gate if isinstance(gate, dict) else {}
    return _text(gate.get("tier"))


def _is_quality_reject(candidate: dict[str, Any]) -> bool:
    return _quality_tier(candidate).lower() == "reject"


def _is_primary_candidate(candidate: dict[str, Any]) -> bool:
    if _is_quality_reject(candidate):
        return False
    decision = _decision(candidate)
    if decision == "review-candidate":
        return False
    tier = _quality_tier(candidate)
    if tier == "Tier C":
        return False
    return tier in {"Tier A", "Tier B"} or decision == "advance-candidate"


def _is_review_appendix_candidate(candidate: dict[str, Any]) -> bool:
    if _is_quality_reject(candidate):
        return False
    return _decision(candidate) == "review-candidate" or _quality_tier(candidate) == "Tier C"


def _is_grok_only_candidate(candidate: dict[str, Any]) -> bool:
    provenance = candidate.get("provider_provenance")
    providers = set(provenance if isinstance(provenance, list) else [])
    if not providers:
        return False
    return providers == {"grok_search"} or candidate.get("provenance_label") == "grok_only_with_paper_search_anchor"


def _apply_paper_search_anchor_gate(candidates: list[dict[str, Any]], *, cap: int = 5) -> list[dict[str, Any]]:
    usable_paper = [candidate for candidate in candidates if usable_paper_search_candidate(candidate)]
    if not usable_paper:
        return [candidate for candidate in candidates if not _is_grok_only_candidate(candidate)]
    quota = grok_only_quota(candidates, cap)
    accepted: list[dict[str, Any]] = []
    grok_only_count = 0
    for candidate in candidates:
        if not _is_grok_only_candidate(candidate):
            accepted.append(candidate)
            continue
        if grok_only_count < quota:
            accepted.append(candidate)
            grok_only_count += 1
    return accepted


def _doi_payload(candidate: dict[str, Any]) -> dict[str, str | None]:
    if "doi" not in candidate:
        return {"value": None, "display": "未核实", "status": "unverified"}
    doi = _text(candidate.get("doi"))
    if not doi:
        return {"value": None, "display": "缺失", "status": "missing"}
    return {"value": doi, "display": doi, "status": "present"}


def _has_present_doi(candidate: dict[str, Any]) -> bool:
    return _doi_payload(candidate)["status"] == "present"


def _doi_url(doi: str | None) -> str | None:
    if not doi:
        return None
    if doi.lower().startswith(("http://", "https://")):
        return doi
    return f"https://doi.org/{doi}"


def _primary_url(candidate: dict[str, Any], doi_url: str | None) -> str | None:
    for value in (
        candidate.get("pdf_url"),
        doi_url,
        candidate.get("publisher_url"),
        candidate.get("landing_page_url"),
        candidate.get("url"),
    ):
        text = _text(value)
        if text:
            return text
    return None


def _manual_links(candidate: dict[str, Any], manual_card: dict[str, Any] | None) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []

    for item in candidate.get("candidate_manual_urls") or []:
        if isinstance(item, dict) and item.get("url"):
            links.append({"kind": _text(item.get("kind") or "candidate"), "url": _text(item.get("url"))})

    if manual_card:
        for item in manual_card.get("candidate_manual_urls") or []:
            if isinstance(item, dict) and item.get("url"):
                links.append({"kind": _text(item.get("kind") or "manual"), "url": _text(item.get("url"))})
        if manual_card.get("doi_url"):
            links.append({"kind": "doi", "url": _text(manual_card.get("doi_url"))})

    doi = _doi_payload(candidate).get("value")
    doi_link = _doi_url(doi)
    if doi_link:
        links.append({"kind": "doi", "url": doi_link})

    arxiv_id = _text(candidate.get("arxiv_id"))
    if arxiv_id:
        links.append({"kind": "arxiv", "url": f"https://arxiv.org/abs/{arxiv_id}"})

    for key, kind in [
        ("publisher_url", "publisher"),
        ("landing_page_url", "landing_page"),
        ("url", "stable_url"),
    ]:
        if candidate.get(key):
            links.append({"kind": kind, "url": _text(candidate.get(key))})

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        marker = (link["kind"], link["url"])
        if link["url"] and marker not in seen:
            seen.add(marker)
            deduped.append(link)
    return deduped


def _manual_cards_by_identity(manual_downloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for card in manual_downloads:
        for key in ("slug", "title", "doi"):
            value = _text(card.get(key))
            if value:
                cards[value] = card
    return cards


def _manual_card_for(candidate: dict[str, Any], cards: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in ("slug", "title", "doi"):
        value = _text(candidate.get(key))
        if value and value in cards:
            return cards[value]
    return None


def _pdf_status(candidate: dict[str, Any]) -> str:
    if candidate.get("pdf_url"):
        return "available"
    readiness = [_text(item) for item in candidate.get("readiness_reasons") or []]
    if candidate.get("staging_readiness") == "needs_pdf" or "missing_pdf" in readiness:
        return "needs_pdf"
    return "unknown"


def _quality_reason(candidate: dict[str, Any]) -> dict[str, Any]:
    gate = candidate.get("quality_gate")
    gate = gate if isinstance(gate, dict) else {}
    rationale = candidate.get("ranking_rationale")
    rationale = rationale if isinstance(rationale, dict) else {}
    protocol = candidate.get("ranking_protocol")
    protocol = protocol if isinstance(protocol, dict) else {}
    return {
        "tier": _quality_tier(candidate),
        "evidence": list(gate.get("evidence") or []),
        "cautions": list(gate.get("cautions") or []),
        "blocking_reasons": list(gate.get("blocking_reasons") or []),
        "ranking_reasons": list(protocol.get("reasons") or []),
        "ranking_cautions": list(protocol.get("cautions") or []),
        "one_sentence": _text(rationale.get("one_sentence")) or None,
    }


def _quality_risk(candidate: dict[str, Any]) -> dict[str, Any]:
    risk = candidate.get("quality_risk")
    if isinstance(risk, dict):
        return risk
    return {
        "schema_version": "paper-source-quality-risk-v1",
        "status": "unverified",
        "severity": "unknown",
        "confidence": "none",
        "risk_types": [],
        "cautions": ["quality_risk_unverified"],
    }


def _classification(candidate: dict[str, Any]) -> dict[str, Any]:
    classification = candidate.get("paper_classification")
    classification = classification if isinstance(classification, dict) else {}
    return {
        "paper_type": candidate.get("paper_type") or classification.get("primary_type"),
        "confidence": candidate.get("classification_confidence") or classification.get("confidence"),
        "evidence": list(candidate.get("classification_evidence") or classification.get("evidence") or []),
    }


def _summary_payload(candidate: dict[str, Any]) -> dict[str, str | None]:
    abstract = _text(candidate.get("abstract"))
    if not abstract:
        abstract = _text(candidate.get("summary") or candidate.get("description"))
    return {
        "status": "agent_generated_required",
        "language": "zh",
        "source_field": "original_abstract",
        "source_text": abstract or None,
    }


def _recommendation_item(
    candidate: dict[str, Any],
    *,
    manual_card: dict[str, Any] | None,
    appendix_reason: str | None = None,
) -> dict[str, Any]:
    doi = _doi_payload(candidate)
    doi_url = _doi_url(doi["value"])
    citation_status = _text(candidate.get("citation_count_status")) or "unverified"
    verified_metrics = candidate.get("verified_metrics") or {}
    item = {
        "slug": candidate.get("slug"),
        "title": candidate.get("title"),
        "venue": candidate.get("venue"),
        "year": candidate.get("year"),
        "score": candidate.get("score"),
        "doi": doi["display"],
        "doi_value": doi["value"],
        "doi_status": doi["status"],
        "doi_url": doi_url,
        "primary_url": _primary_url(candidate, doi_url),
        "citation_count": candidate.get("citation_count"),
        "citation_count_status": citation_status,
        "citation_count_source": candidate.get("citation_count_source"),
        "citation_count_sources": candidate.get("citation_count_sources") or [],
        "verified_metrics": verified_metrics,
        "original_abstract": _summary_payload(candidate)["source_text"],
        "chinese_summary": _summary_payload(candidate),
        "classification": _classification(candidate),
        "quality_tier": _quality_tier(candidate),
        "quality_reason": _quality_reason(candidate),
        "quality_risk": _quality_risk(candidate),
        "ranking_decision": _decision(candidate),
        "ranking_rationale": candidate.get("ranking_rationale") or {},
        "provenance_label": candidate.get("provenance_label"),
        "provider_provenance": candidate.get("provider_provenance") or [],
        "pdf_status": _pdf_status(candidate),
        "pdf_url": candidate.get("pdf_url") or None,
        "manual_download": {
            "status": "available" if manual_card else ("needed" if _pdf_status(candidate) == "needs_pdf" else "not_needed"),
            "links": _manual_links(candidate, manual_card),
            "preferred_next_step": (manual_card or {}).get("preferred_next_step"),
        },
        "auto_staging_status": candidate.get("auto_staging_status") or "not_run",
    }
    item["verification_warnings"] = _verification_warnings(item)
    if appendix_reason:
        item["appendix_reason"] = appendix_reason
    return item


def _verification_warnings(item: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if item.get("doi_status") != "present":
        warnings.append(f"doi_{item.get('doi_status') or 'unverified'}")
    if item.get("citation_count_status") != "verified" or not item.get("citation_count_source"):
        warnings.append("citation_count_unverified")
    metrics = item.get("verified_metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    if not metrics.get("easyscholar"):
        warnings.append("venue_metrics_unverified")
    risk = item.get("quality_risk")
    risk = risk if isinstance(risk, dict) else {}
    risk_status = _text(risk.get("status")) or "unverified"
    if risk_status == "verified":
        warnings.append("quality_risk_verified")
    elif risk_status == "suspected":
        warnings.append("quality_risk_suspected")
    elif risk_status != "verified_clear":
        warnings.append("quality_risk_unverified")
    return warnings


def _verification_summary(primary_recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    citation_verified = [
        item
        for item in primary_recommendations
        if item.get("citation_count_status") == "verified" and item.get("citation_count_source")
    ]
    venue_metrics_verified = [
        item
        for item in primary_recommendations
        if isinstance(item.get("verified_metrics"), dict) and item.get("verified_metrics", {}).get("easyscholar")
    ]
    risk_statuses = Counter(
        _text((item.get("quality_risk") if isinstance(item.get("quality_risk"), dict) else {}).get("status"))
        or "unverified"
        for item in primary_recommendations
    )
    items_requiring_verification = [
        {
            "slug": item.get("slug"),
            "title": item.get("title"),
            "warnings": item.get("verification_warnings") or [],
        }
        for item in primary_recommendations
        if item.get("verification_warnings")
    ]
    return {
        "primary_total": len(primary_recommendations),
        "citation_count": {
            "verified": len(citation_verified),
            "unverified": len(primary_recommendations) - len(citation_verified),
        },
        "venue_metrics": {
            "verified": len(venue_metrics_verified),
            "unverified": len(primary_recommendations) - len(venue_metrics_verified),
        },
        "quality_risk": {
            "verified": risk_statuses.get("verified", 0),
            "suspected": risk_statuses.get("suspected", 0),
            "unverified": risk_statuses.get("unverified", 0),
        },
        "items_requiring_verification": items_requiring_verification,
    }


def _appendix_reason(candidate: dict[str, Any]) -> str:
    if _decision(candidate) == "review-candidate":
        rationale = candidate.get("ranking_rationale")
        rationale = rationale if isinstance(rationale, dict) else {}
        return _text(rationale.get("one_sentence")) or "review-candidate"
    if _quality_tier(candidate) == "Tier C":
        return "Tier C"
    return "lower-priority candidate"


def _rejected_summary(rejected: list[dict[str, Any]]) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    for candidate in rejected:
        reasons = candidate.get("filter_reasons") or ["unknown"]
        for reason in reasons:
            reason_counts[_text(reason) or "unknown"] += 1
    return {
        "total": len(rejected),
        "reason_counts": [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def _query_source_provenance(candidate: dict[str, Any]) -> dict[str, Any]:
    queries: list[dict[str, Any]] = []
    for record in candidate.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        query = _text(record.get("query_variant"))
        if not query:
            continue
        query_item = {
            "query_variant": query,
            "query_variant_index": record.get("query_variant_index"),
            "provider": record.get("provider") or record.get("source"),
            "source": record.get("source"),
        }
        if query_item not in queries:
            queries.append(query_item)
    return {
        "provider_provenance": candidate.get("provider_provenance") or [],
        "provenance_label": candidate.get("provenance_label"),
        "sources": candidate.get("sources") or [],
        "query_records": queries[:5],
    }


def _quality_reject_item(candidate: dict[str, Any]) -> dict[str, Any]:
    doi = _doi_payload(candidate)
    gate = candidate.get("quality_gate")
    gate = gate if isinstance(gate, dict) else {}
    return {
        "slug": candidate.get("slug"),
        "title": candidate.get("title"),
        "venue": candidate.get("venue"),
        "year": candidate.get("year"),
        "score": candidate.get("score"),
        "doi": doi["display"],
        "doi_value": doi["value"],
        "doi_status": doi["status"],
        "doi_url": _doi_url(doi["value"]),
        "arxiv_id": candidate.get("arxiv_id"),
        "primary_url": _primary_url(candidate, _doi_url(doi["value"])),
        "quality_tier": _quality_tier(candidate),
        "blocking_reasons": list(gate.get("blocking_reasons") or []),
        "ranking_decision": _decision(candidate),
        "filter_status": candidate.get("filter_status"),
        "recommendation_filter_status": candidate.get("recommendation_filter_status"),
        "provenance": _query_source_provenance(candidate),
    }


def _quality_reject_debug(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    items = [_quality_reject_item(candidate) for candidate in ranked if _is_quality_reject(candidate)]
    reason_counts: Counter[str] = Counter()
    for item in items:
        reasons = item.get("blocking_reasons") or ["unknown"]
        for reason in reasons:
            reason_counts[_text(reason) or "unknown"] += 1
    return {
        "total": len(items),
        "reason_counts": [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "items": items,
    }


def _existing_library_appendix(rejected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    appendix: list[dict[str, Any]] = []
    for candidate in rejected:
        reasons = [_text(reason) for reason in candidate.get("filter_reasons") or []]
        existing_reasons = [
            reason for reason in reasons if reason.startswith("already_in_wiki:") or reason.startswith("already_in_library:")
        ]
        if not existing_reasons:
            continue
        doi = _doi_payload(candidate)
        doi_url = _doi_url(doi["value"])
        match = candidate.get("existing_library_match")
        match = match if isinstance(match, dict) else {}
        appendix.append(
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "venue": candidate.get("venue"),
                "year": candidate.get("year"),
                "doi": doi["display"],
                "doi_value": doi["value"],
                "doi_status": doi["status"],
                "doi_url": doi_url,
                "primary_url": _primary_url(candidate, doi_url),
                "reason": existing_reasons[0],
                "reasons": existing_reasons,
                "existing_source_type": match.get("source_type"),
                "existing_page": match.get("page"),
                "existing_slug": match.get("slug"),
                "existing_source_id": match.get("source_id"),
            }
        )
    return appendix


def _doi_filtered_items(candidates: list[dict[str, Any]], *, surface: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        doi = _doi_payload(candidate)
        if doi["status"] == "present":
            continue
        items.append(
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "venue": candidate.get("venue"),
                "year": candidate.get("year"),
                "score": candidate.get("score"),
                "quality_tier": _quality_tier(candidate),
                "ranking_decision": _decision(candidate),
                "primary_url": _primary_url(candidate, None),
                "arxiv_id": candidate.get("arxiv_id"),
                "surface": surface,
                "reason": "missing_required_doi",
                "doi_status": doi["status"],
            }
        )
    return items


def _doi_resolution_bucket(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    present = [candidate for candidate in candidates if _has_present_doi(candidate)]
    sources = Counter(_text(candidate.get("doi_source")) or "unspecified" for candidate in present)
    return {
        "considered": len(candidates),
        "success": len(present),
        "failed": len(candidates) - len(present),
        "success_sources": [
            {"source": source, "count": count}
            for source, count in sorted(sources.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def _blocking_reason_category(reason: object) -> str | None:
    text = _text(reason).lower()
    if not text:
        return None
    if "concept" in text and ("required" in text or "group" in text or "mismatch" in text):
        return "required_concept_group_failure"
    return None


def _top_blocked_card(
    item: dict[str, Any],
    *,
    surface: str,
    blocking_reasons: list[str],
) -> dict[str, Any]:
    doi = item.get("doi_value") or item.get("doi")
    doi_status = item.get("doi_status")
    if doi in {"未核实", "缺失", "missing", "unverified"}:
        doi = None
    return {
        "surface": surface,
        "slug": item.get("slug"),
        "title": item.get("title"),
        "year": item.get("year"),
        "doi": doi,
        "doi_status": doi_status,
        "doi_url": item.get("doi_url") or _doi_url(_text(doi)),
        "arxiv_id": item.get("arxiv_id"),
        "score": item.get("score"),
        "quality_tier": item.get("quality_tier"),
        "ranking_decision": item.get("ranking_decision"),
        "blocking_reasons": blocking_reasons,
    }


def _blocked_sort_score(item: dict[str, Any]) -> float:
    try:
        return float(item.get("score"))
    except (TypeError, ValueError):
        return float("-inf")


def _top_blocked_candidates(
    *,
    review_appendix: list[dict[str, Any]],
    quality_reject_debug: dict[str, Any],
    existing_library_appendix: list[dict[str, Any]],
    doi_filtered_items: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for item in doi_filtered_items:
        blocked.append(
            _top_blocked_card(
                item,
                surface=str(item.get("surface") or "doi_filtered"),
                blocking_reasons=[str(item.get("reason") or "missing_required_doi")],
            )
        )
    for item in quality_reject_debug.get("items") or []:
        if not isinstance(item, dict):
            continue
        reasons = [str(reason) for reason in item.get("blocking_reasons") or ["quality_gate_rejected"]]
        blocked.append(_top_blocked_card(item, surface="quality_reject_debug", blocking_reasons=reasons))
    for item in review_appendix:
        reason = _text(item.get("appendix_reason")) or _text(item.get("quality_tier")) or "review_appendix"
        blocked.append(_top_blocked_card(item, surface="review_appendix", blocking_reasons=[reason]))
    for item in existing_library_appendix:
        reasons = [str(reason) for reason in item.get("reasons") or [item.get("reason") or "existing_library"]]
        blocked.append(_top_blocked_card(item, surface="existing_library", blocking_reasons=reasons))
    return sorted(blocked, key=_blocked_sort_score, reverse=True)[:limit]


def _dominant_reason(reason_counts: dict[str, int]) -> str | None:
    if not reason_counts:
        return None
    return sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _no_primary_recommendations_summary(
    *,
    primary_candidates: list[dict[str, Any]],
    primary_candidates_with_doi: list[dict[str, Any]],
    primary_recommendations: list[dict[str, Any]],
    review_appendix: list[dict[str, Any]],
    existing_library_appendix: list[dict[str, Any]],
    quality_reject_debug: dict[str, Any],
    doi_filtered_items: list[dict[str, Any]],
    ranked_count: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    missing_doi_count = len([item for item in doi_filtered_items if item.get("surface") == "primary_recommendations"])
    quality_reject_count = int(quality_reject_debug.get("total") or 0)
    existing_count = len(existing_library_appendix)
    review_count = len(review_appendix)
    concept_group_count = 0
    for item in quality_reject_debug.get("items") or []:
        if not isinstance(item, dict):
            continue
        if any(_blocking_reason_category(reason) == "required_concept_group_failure" for reason in item.get("blocking_reasons") or []):
            concept_group_count += 1

    if not primary_recommendations:
        if not ranked_count:
            reasons.append("no_ranked_candidates")
        if missing_doi_count:
            reasons.append("primary_candidates_missing_required_doi")
        if concept_group_count:
            reasons.append("required_concept_group_failure")
        if quality_reject_count:
            reasons.append("quality_gate_rejected_candidates")
        if review_count:
            reasons.append("only_review_appendix_candidates")
        if existing_count:
            reasons.append("existing_library_saturation")
        if primary_candidates and not primary_candidates_with_doi:
            reasons.append("all_primary_candidates_failed_doi_policy")
        if not reasons:
            reasons.append("no_primary_candidate_met_selection_policy")

    next_actions: list[str] = []
    if missing_doi_count:
        next_actions.append("Run targeted DOI recovery or inspect DOI-filtered candidates.")
    if concept_group_count:
        next_actions.append("Refine query variants or required concept groups, then rerun discovery.")
    if quality_reject_count:
        next_actions.append("Inspect quality_reject_debug before tightening or relaxing query/ranking gates.")
    if existing_count:
        next_actions.append("Review existing_library_appendix before rerunning duplicate discovery.")
    if not next_actions and not primary_recommendations:
        next_actions.append("Tighten query variants or broaden source routing based on discovery diagnostics.")

    counts = {
        "ranked": ranked_count,
        "primary_candidates_before_doi": len(primary_candidates),
        "primary_candidates_with_doi": len(primary_candidates_with_doi),
        "primary_shown": len(primary_recommendations),
        "review_appendix": review_count,
        "existing_library": existing_count,
        "quality_reject": quality_reject_count,
        "missing_doi": missing_doi_count,
        "required_concept_group_failure": concept_group_count,
    }
    reason_counts = {
        "no_ranked_candidates": 1 if not primary_recommendations and not ranked_count else 0,
        "primary_candidates_missing_required_doi": missing_doi_count,
        "required_concept_group_failure": concept_group_count,
        "quality_gate_rejected_candidates": quality_reject_count,
        "only_review_appendix_candidates": review_count,
        "existing_library_saturation": existing_count,
        "all_primary_candidates_failed_doi_policy": 1 if primary_candidates and not primary_candidates_with_doi else 0,
        "no_primary_candidate_met_selection_policy": 1 if reasons == ["no_primary_candidate_met_selection_policy"] else 0,
    }
    reason_counts = {reason: count for reason, count in reason_counts.items() if count}
    top_blocked = _top_blocked_candidates(
        review_appendix=review_appendix,
        quality_reject_debug=quality_reject_debug,
        existing_library_appendix=existing_library_appendix,
        doi_filtered_items=doi_filtered_items,
    )
    if primary_recommendations:
        secondary_status = "primary_recommendations_available"
    elif review_count:
        secondary_status = "review_appendix_available_not_primary"
    elif top_blocked:
        secondary_status = "blocked_candidates_available"
    else:
        secondary_status = "no_useful_candidates"

    return {
        "status": "primary_recommendations_available" if primary_recommendations else "no_primary_recommendations",
        "primary_candidates_before_doi": len(primary_candidates),
        "primary_candidates_with_doi": len(primary_candidates_with_doi),
        "primary_shown": len(primary_recommendations),
        "review_appendix_count": review_count,
        "existing_library_saturation_count": existing_count,
        "quality_reject_count": quality_reject_count,
        "missing_doi_count": missing_doi_count,
        "ranked_count": ranked_count,
        "reasons": reasons,
        "counts": counts,
        "reason_counts": [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "dominant_blocking_reason": _dominant_reason(reason_counts),
        "secondary_candidate_status": secondary_status,
        "top_blocked_candidates": top_blocked if not primary_recommendations else [],
        "recommended_next_actions": next_actions,
    }


def build_session_recommendations(
    ranked: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    *,
    discovery_context: dict[str, Any] | None = None,
    manual_downloads: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
    primary_limit: int = DEFAULT_PRIMARY_LIMIT,
) -> dict[str, Any]:
    discovery_context = discovery_context or {}
    manual_downloads = manual_downloads or []
    manual_cards = _manual_cards_by_identity(manual_downloads)

    primary_candidates = _apply_paper_search_anchor_gate(
        [candidate for candidate in ranked if _is_primary_candidate(candidate)]
    )
    primary_doi_filtered = _doi_filtered_items(primary_candidates, surface="primary_recommendations")
    primary_candidates_with_doi = [candidate for candidate in primary_candidates if _has_present_doi(candidate)]
    primary_shown = primary_candidates_with_doi[:primary_limit]
    primary_ids = {id(candidate) for candidate in primary_shown}
    appendix_candidates_before_doi = [
        candidate
        for candidate in ranked
        if id(candidate) not in primary_ids and _is_review_appendix_candidate(candidate)
    ]
    appendix_doi_filtered = _doi_filtered_items(appendix_candidates_before_doi, surface="review_appendix")
    appendix_candidates = [candidate for candidate in appendix_candidates_before_doi if _has_present_doi(candidate)]
    doi_resolution = {
        "primary_recommendations": _doi_resolution_bucket(primary_candidates),
        "review_appendix": _doi_resolution_bucket(appendix_candidates_before_doi),
    }
    doi_resolution["total"] = {
        "considered": doi_resolution["primary_recommendations"]["considered"]
        + doi_resolution["review_appendix"]["considered"],
        "success": doi_resolution["primary_recommendations"]["success"]
        + doi_resolution["review_appendix"]["success"],
        "failed": doi_resolution["primary_recommendations"]["failed"] + doi_resolution["review_appendix"]["failed"],
    }

    primary_recommendations = [
        _recommendation_item(candidate, manual_card=_manual_card_for(candidate, manual_cards))
        for candidate in primary_shown
    ]
    review_appendix = [
        _recommendation_item(
            candidate,
            manual_card=_manual_card_for(candidate, manual_cards),
            appendix_reason=_appendix_reason(candidate),
        )
        for candidate in appendix_candidates
    ]
    existing_library_appendix = _existing_library_appendix(rejected)
    quality_reject_debug = _quality_reject_debug(ranked)
    doi_filtered_items = [*primary_doi_filtered, *appendix_doi_filtered]
    no_primary_summary = _no_primary_recommendations_summary(
        primary_candidates=primary_candidates,
        primary_candidates_with_doi=primary_candidates_with_doi,
        primary_recommendations=primary_recommendations,
        review_appendix=review_appendix,
        existing_library_appendix=existing_library_appendix,
        quality_reject_debug=quality_reject_debug,
        doi_filtered_items=doi_filtered_items,
        ranked_count=len(ranked),
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "summary_policy": {
            "language": "zh",
            "producer": "calling_agent",
            "source": "original_abstract",
        },
        "doi_required_policy": {
            "required_for": ["primary_recommendations", "review_appendix"],
            "missing_reason": "missing_required_doi",
        },
        "primary_limit": primary_limit,
        "primary_recommendations": primary_recommendations,
        "review_appendix": review_appendix,
        "existing_library_appendix": existing_library_appendix,
        "verification_summary": _verification_summary(primary_recommendations),
        "rejected_summary": _rejected_summary(rejected),
        "quality_reject_debug": quality_reject_debug,
        "no_primary_recommendations_summary": no_primary_summary,
        "doi_recovery_summary": discovery_context.get("doi_recovery") or {},
        "doi_resolution_summary": doi_resolution,
        "doi_filtered_summary": {
            "total": len(doi_filtered_items),
            "items": doi_filtered_items,
        },
        "overflow": {
            "primary_total": len(primary_candidates_with_doi),
            "hidden_count": max(0, len(primary_candidates_with_doi) - len(primary_recommendations)),
            "full_artifact": "report.json",
        },
        "source_artifacts": {
            "run_id": run_id,
            "diagnostics_path": discovery_context.get("diagnostics_path"),
            "review_session": discovery_context.get("review_session") or {},
        },
    }
