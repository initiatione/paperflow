from __future__ import annotations

import re


DOCUMENT_TYPE_EXCLUSION_TERMS = {
    "review": ("review", "review paper", "systematic review", "literature review"),
    "survey": ("survey",),
    "meta": ("meta-analysis", "meta analysis"),
}


def exclusion_terms_from_query(query: str) -> list[str]:
    query_lower = query.lower()
    requested: set[str] = set()
    for key in DOCUMENT_TYPE_EXCLUSION_TERMS:
        if re.search(rf"(?<!\w)-{re.escape(key)}s?(?!\w)", query_lower):
            requested.add(key)
    if any(phrase in query_lower for phrase in ("no review", "not review", "non-review", "exclude review")):
        requested.add("review")
    if any(phrase in query_lower for phrase in ("不要综述", "非综述", "排除综述", "不找综述", "不是综述")):
        requested.add("review")
    if any(phrase in query_lower for phrase in ("no survey", "not survey", "non-survey", "exclude survey")):
        requested.add("survey")
    if any(phrase in query_lower for phrase in ("不要调研", "非调研", "排除调研", "不找调研")):
        requested.add("survey")
    if any(phrase in query_lower for phrase in ("不要meta", "排除meta", "不要荟萃", "排除荟萃")):
        requested.add("meta")
    terms: list[str] = []
    for key in ("review", "survey", "meta"):
        if key in requested:
            terms.extend(DOCUMENT_TYPE_EXCLUSION_TERMS[key])
    return terms


def filter_candidates_with_report(
    candidates: list[dict],
    domains: list[str],
    require_pdf: bool,
    exclude_terms: list[str] | None = None,
) -> dict[str, list[dict]]:
    kept: list[dict] = []
    rejected: list[dict] = []
    domain_terms = [term.lower() for term in domains]
    excluded = [term.lower() for term in (exclude_terms or [])]
    for candidate in candidates:
        haystack = " ".join(
            [
                str(candidate.get("title") or ""),
                str(candidate.get("abstract") or ""),
                str(candidate.get("venue") or ""),
            ]
        ).lower()
        reasons: list[str] = []
        if require_pdf and not candidate.get("pdf_url"):
            reasons.append("missing_pdf")
        matched_excluded_terms = [term for term in excluded if term in haystack]
        if matched_excluded_terms:
            reasons.append("excluded_terms:" + ",".join(matched_excluded_terms))
        if domain_terms and not any(term in haystack for term in domain_terms):
            robotics_terms = ["robot", "humanoid", "control", "navigation", "embodied"]
            if not any(term in haystack for term in robotics_terms):
                reasons.append("outside_domain")
        filtered = dict(candidate)
        filtered["filter_reasons"] = reasons
        filtered["filter_status"] = "rejected" if reasons else "kept"
        if reasons:
            rejected.append(filtered)
        else:
            kept.append(filtered)
    return {"kept": kept, "rejected": rejected}


def filter_candidates(
    candidates: list[dict],
    domains: list[str],
    require_pdf: bool,
    exclude_terms: list[str] | None = None,
) -> list[dict]:
    return filter_candidates_with_report(
        candidates,
        domains=domains,
        require_pdf=require_pdf,
        exclude_terms=exclude_terms,
    )["kept"]
