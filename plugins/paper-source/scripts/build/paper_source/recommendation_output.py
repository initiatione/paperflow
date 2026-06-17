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
    return _text(candidate.get("quality_tier"))


def _is_primary_candidate(candidate: dict[str, Any]) -> bool:
    decision = _decision(candidate)
    if decision == "review-candidate":
        return False
    tier = _quality_tier(candidate)
    if tier == "Tier C":
        return False
    return tier in {"Tier A", "Tier B"} or decision == "advance-candidate"


def _is_review_appendix_candidate(candidate: dict[str, Any]) -> bool:
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
    primary_shown = primary_candidates[:primary_limit]
    primary_ids = {id(candidate) for candidate in primary_shown}
    appendix_candidates = [
        candidate
        for candidate in ranked
        if id(candidate) not in primary_ids and _is_review_appendix_candidate(candidate)
    ]

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

    return {
        "schema_version": SCHEMA_VERSION,
        "summary_policy": {
            "language": "zh",
            "producer": "calling_agent",
            "source": "original_abstract",
        },
        "primary_limit": primary_limit,
        "primary_recommendations": primary_recommendations,
        "review_appendix": review_appendix,
        "existing_library_appendix": _existing_library_appendix(rejected),
        "verification_summary": _verification_summary(primary_recommendations),
        "rejected_summary": _rejected_summary(rejected),
        "overflow": {
            "primary_total": len(primary_candidates),
            "hidden_count": max(0, len(primary_candidates) - len(primary_recommendations)),
            "full_artifact": "report.json",
        },
        "source_artifacts": {
            "run_id": run_id,
            "diagnostics_path": discovery_context.get("diagnostics_path"),
            "review_session": discovery_context.get("review_session") or {},
        },
    }
