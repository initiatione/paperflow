from __future__ import annotations

import re

from paper_source.concept_groups import evaluate_required_concept_groups, normalize_required_concept_groups
from paper_source.lexical_match import term_matches_text
from paper_source.paper_library import existing_library_match


DOCUMENT_TYPE_EXCLUSION_TERMS = {
    "review": ("review", "review paper", "systematic review", "literature review"),
    "survey": ("survey",),
    "meta": ("meta-analysis", "meta analysis"),
}

REVIEW_REQUEST_PHRASES = (
    "review paper",
    "review papers",
    "survey paper",
    "survey papers",
    "systematic review",
    "literature review",
    "meta-analysis",
    "meta analysis",
    "state-of-the-art review",
    "综述",
    "文献综述",
    "调研论文",
)


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


def _term_matches_haystack(term: str, haystack: str) -> bool:
    return term_matches_text(term, haystack)


def _excluded_term_matches_haystack(term: str, haystack: str) -> bool:
    term = " ".join(term.lower().split())
    if not term:
        return False
    tokens = [token for token in re.split(r"\s+", term) if token]
    if not tokens:
        return False
    if len(tokens) == 1:
        pattern = r"(?<![a-z0-9])" + re.escape(tokens[0]) + r"(?![a-z0-9])"
        return re.search(pattern, haystack) is not None
    pattern = r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(re.escape(token) for token in tokens) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _candidate_year(candidate: dict) -> int | None:
    value = candidate.get("year")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
    return None


def _has_code_identity(candidate: dict) -> bool:
    return bool(candidate.get("code_url") or candidate.get("repository_url"))


def _has_stable_paper_identity(candidate: dict) -> bool:
    return bool(
        candidate.get("doi")
        or candidate.get("arxiv_id")
        or candidate.get("url")
        or candidate.get("publisher_url")
        or candidate.get("landing_page_url")
    )


def _normalize_code_policy(code_policy: str | None) -> str:
    policy = str(code_policy or "ignore").strip().lower()
    if policy not in {"ignore", "prefer", "require"}:
        raise ValueError(f"unknown code_policy: {code_policy}")
    return policy


def _existing_library_reason(match: dict | None) -> str | None:
    if not match:
        return None
    if match.get("source_type") == "wiki_reference_index":
        label = match.get("page") or match.get("source_id") or match.get("slug") or "unknown"
        return f"already_in_wiki:{label}"
    label = match.get("slug") or match.get("source_id") or "unknown"
    return f"already_in_library:{label}"


def default_discovery_exclusion_terms(query: str) -> list[str]:
    requested_terms = exclusion_terms_from_query(query)
    if requested_terms:
        terms: list[str] = []
        for key in ("review", "survey", "meta"):
            terms.extend(DOCUMENT_TYPE_EXCLUSION_TERMS[key])
        return terms

    query_lower = query.lower()
    if any(phrase in query_lower for phrase in REVIEW_REQUEST_PHRASES):
        return []

    terms: list[str] = []
    for key in ("review", "survey", "meta"):
        terms.extend(DOCUMENT_TYPE_EXCLUSION_TERMS[key])
    return terms


def filter_candidates_with_report(
    candidates: list[dict],
    domains: list[str],
    require_pdf: bool,
    exclude_terms: list[str] | None = None,
    existing_library_index: dict | None = None,
    year_min: int | None = None,
    code_policy: str | None = None,
    required_concept_groups: list[dict] | None = None,
) -> dict[str, list[dict]]:
    recommendable: list[dict] = []
    staging_ready: list[dict] = []
    needs_pdf: list[dict] = []
    rejected: list[dict] = []
    domain_terms = [term.lower() for term in domains]
    excluded = [term.lower() for term in (exclude_terms or [])]
    normalized_code_policy = _normalize_code_policy(code_policy)
    concept_groups = normalize_required_concept_groups(required_concept_groups or [])
    concept_group_failure_counts: dict[str, int] = {str(group["id"]): 0 for group in concept_groups}
    concept_group_evaluated = 0
    concept_group_failed = 0
    for candidate in candidates:
        haystack = " ".join(
            [
                str(candidate.get("title") or ""),
                str(candidate.get("abstract") or ""),
                str(candidate.get("venue") or ""),
            ]
        ).lower()
        hard_reasons: list[str] = []
        readiness_reasons: list[str] = []
        if require_pdf and not candidate.get("pdf_url"):
            readiness_reasons.append("missing_pdf")
        matched_excluded_terms = [term for term in excluded if _excluded_term_matches_haystack(term, haystack)]
        if matched_excluded_terms:
            hard_reasons.append("excluded_terms:" + ",".join(matched_excluded_terms))
        library_match = existing_library_match(candidate, existing_library_index)
        library_reason = _existing_library_reason(library_match)
        if library_reason:
            hard_reasons.append(library_reason)
        if domain_terms and not any(_term_matches_haystack(term, haystack) for term in domain_terms):
            hard_reasons.append("outside_domain")
        concept_group_evaluation = None
        if concept_groups:
            concept_group_evaluated += 1
            concept_group_evaluation = evaluate_required_concept_groups(concept_groups, haystack)
            if not concept_group_evaluation["passed"]:
                concept_group_failed += 1
                for group_id in concept_group_evaluation.get("missing_required_groups") or []:
                    concept_group_failure_counts[str(group_id)] = concept_group_failure_counts.get(str(group_id), 0) + 1
                    hard_reasons.append(f"required_concept_group_mismatch:{group_id}")
        if year_min is not None:
            candidate_year = _candidate_year(candidate)
            if candidate_year is None:
                hard_reasons.append("year_missing")
            elif candidate_year < int(year_min):
                hard_reasons.append(f"year_before:{int(year_min)}")
        if normalized_code_policy == "require" and not _has_code_identity(candidate):
            hard_reasons.append("missing_code")
        if readiness_reasons and not _has_stable_paper_identity(candidate):
            hard_reasons.append("missing_pdf_and_stable_identity")
        filtered = dict(candidate)
        if library_match:
            filtered["existing_library_match"] = library_match
        if concept_group_evaluation:
            filtered["required_concept_groups"] = concept_group_evaluation["groups"]
            filtered["required_concept_groups_passed"] = concept_group_evaluation["passed"]
            filtered["required_concept_group_failures"] = concept_group_evaluation["missing_required_groups"]
        filtered["filter_reasons"] = hard_reasons
        filtered["readiness_reasons"] = readiness_reasons
        filtered["recommendation_filter_status"] = "rejected" if hard_reasons else "recommendable"
        filtered["staging_readiness"] = "needs_pdf" if readiness_reasons and not hard_reasons else "ready"
        filtered["filter_status"] = "rejected" if hard_reasons else "kept"
        if hard_reasons:
            rejected.append(filtered)
        else:
            recommendable.append(filtered)
            if readiness_reasons:
                needs_pdf.append(filtered)
            else:
                staging_ready.append(filtered)
    return {
        "kept": recommendable,
        "recommendable": recommendable,
        "staging_ready": staging_ready,
        "needs_pdf": needs_pdf,
        "rejected": rejected,
        "required_concept_groups": {
            "schema_version": "paper-source-required-concept-groups-v1",
            "groups": concept_groups,
            "evaluated_count": concept_group_evaluated,
            "passed_count": concept_group_evaluated - concept_group_failed,
            "failed_count": concept_group_failed,
            "failure_counts": [
                {"group_id": group_id, "count": count}
                for group_id, count in sorted(concept_group_failure_counts.items())
                if count
            ],
            "policy": "required groups are additive; absent groups preserve legacy filtering",
        },
    }


def filter_candidates(
    candidates: list[dict],
    domains: list[str],
    require_pdf: bool,
    exclude_terms: list[str] | None = None,
    existing_library_index: dict | None = None,
    year_min: int | None = None,
    code_policy: str | None = None,
    required_concept_groups: list[dict] | None = None,
) -> list[dict]:
    return filter_candidates_with_report(
        candidates,
        domains=domains,
        require_pdf=require_pdf,
        exclude_terms=exclude_terms,
        existing_library_index=existing_library_index,
        year_min=year_min,
        code_policy=code_policy,
        required_concept_groups=required_concept_groups,
    )["kept"]
