from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from paper_source.artifacts import read_json, utc_now, write_json_atomic
from paper_source.filter_candidates import default_discovery_exclusion_terms, filter_candidates_with_report
from paper_source.normalize_candidates import normalize_candidates
from paper_source.orchestrator_discovery import (
    filter_required_concept_groups_from_query_plan,
    filter_domains_from_profile,
    ranking_keywords_from_profile,
    ranking_priority_keywords_from_query_plan,
    ranking_quality_evidence_terms_from_inputs,
    venue_tiers_from_profile,
)
from paper_source.quality_risk_recall import (
    annotate_recall_expansion_candidates,
    build_recall_gap_record,
    enrich_candidates_with_quality_risk,
)
from paper_source.query_planner import build_query_plan
from paper_source.rank_papers import rank_candidates
from paper_source.recommendation_output import build_session_recommendations
from paper_source.schemas import canonical_key


BENCHMARK_SCHEMA_VERSION = "paper-source-benchmark-v1"
CASE_SET_SCHEMA_VERSION = "paper-source-discovery-benchmark-cases-v1"
RUNNER_SCHEMA_VERSION = "paper-source-discovery-benchmark-runner-v1"


@dataclass
class BenchmarkProfile:
    name: str = "general_academic_research"
    domains: list[str] = field(default_factory=list)
    positive_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    venue_prior: list[str] = field(default_factory=list)
    quality_evidence_terms: object | None = None


def _strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        return [str(key).strip() for key in value if str(key).strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_strings(item))
        return result
    text = str(value).strip()
    return [text] if text else []


def _profile_from_case(case: dict[str, Any]) -> BenchmarkProfile:
    profile = case.get("profile")
    profile = profile if isinstance(profile, dict) else {}
    return BenchmarkProfile(
        name=str(profile.get("name") or "general_academic_research"),
        domains=_strings(profile.get("domains")),
        positive_keywords=_strings(profile.get("positive_keywords")),
        negative_keywords=_strings(profile.get("negative_keywords")),
        venue_prior=_strings(profile.get("venue_prior")),
        quality_evidence_terms=profile.get("quality_evidence_terms"),
    )


def _merge_by_canonical_key(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            key = canonical_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _title_key(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _title_set(items: list[dict[str, Any]]) -> set[str]:
    return {_title_key(item.get("title")) for item in items if _title_key(item.get("title"))}


def _contains_any_title(items: list[dict[str, Any]], titles: list[str]) -> list[str]:
    present = _title_set(items)
    return [title for title in titles if _title_key(title) in present]


def _collect_query_plan_terms(value: object) -> set[str]:
    terms: set[str] = set()
    if isinstance(value, str):
        text = value.strip().lower()
        if text:
            terms.add(text)
    elif isinstance(value, dict):
        for item in value.values():
            terms.update(_collect_query_plan_terms(item))
    elif isinstance(value, list):
        for item in value:
            terms.update(_collect_query_plan_terms(item))
    return terms


def _review_like(candidate: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(candidate.get("title") or ""),
            str(candidate.get("abstract") or ""),
            str(candidate.get("paper_type") or ""),
        ]
    ).lower()
    markers = ("review", "survey", "meta-analysis", "meta analysis", "literature review")
    return any(marker in text for marker in markers)


def _verified_metric_coverage(candidates: list[dict[str, Any]]) -> float:
    if not candidates:
        return 0.0
    covered = 0
    for candidate in candidates:
        signals = candidate.get("ranking_signals") if isinstance(candidate.get("ranking_signals"), dict) else {}
        citation_status = str(
            signals.get("citation_count_status") or candidate.get("citation_count_status") or ""
        ).lower()
        verified_metrics = candidate.get("verified_metrics") if isinstance(candidate.get("verified_metrics"), dict) else {}
        citation_or_metric_verified = citation_status == "verified" or bool(verified_metrics.get("easyscholar"))
        if (
            (candidate.get("doi") or candidate.get("arxiv_id"))
            and candidate.get("venue")
            and candidate.get("year")
            and candidate.get("pdf_url")
            and citation_or_metric_verified
        ):
            covered += 1
    return round(covered / len(candidates), 4)


def _precision_at(candidates: list[dict[str, Any]], relevant_titles: list[str], limit: int) -> float | None:
    if not relevant_titles:
        return None
    top = candidates[:limit]
    relevant = {_title_key(title) for title in relevant_titles}
    hits = len([candidate for candidate in top if _title_key(candidate.get("title")) in relevant])
    return round(hits / max(1, len(top)), 4)


def _recall_at(candidates: list[dict[str, Any]], expected_titles: list[str], limit: int) -> float | None:
    if not expected_titles:
        return None
    found = _contains_any_title(candidates[:limit], expected_titles)
    return round(len(found) / len(expected_titles), 4)


def _top_kept_papers(ranked: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    top: list[dict[str, Any]] = []
    for candidate in ranked[:limit]:
        top.append(
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "doi": candidate.get("doi"),
                "year": candidate.get("year"),
                "venue": candidate.get("venue"),
                "score": candidate.get("score"),
                "quality_tier": candidate.get("quality_tier"),
                "ranking_decision": (candidate.get("ranking_protocol") or {}).get("decision"),
                "citation_count": candidate.get("citation_count"),
                "citation_count_status": (candidate.get("ranking_signals") or {}).get("citation_count_status"),
                "citation_normalized_score": (candidate.get("ranking_signals") or {}).get(
                    "citation_normalized_score"
                ),
                "recall_expansion": candidate.get("recall_expansion"),
            }
        )
    return top


def _check(check_id: str, passed: bool, details: dict[str, Any] | None = None, *, required: bool = True) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": bool(passed),
        "required": required,
        "details": details or {},
    }


def _citation_preserved(session: dict[str, Any], title: str, expected_count: int) -> bool:
    for section in ("primary_recommendations", "review_appendix"):
        for item in session.get(section) or []:
            if _title_key(item.get("title")) == _title_key(title):
                return item.get("citation_count") == expected_count
    return False


def _case_status(checks: list[dict[str, Any]]) -> str:
    required = [check for check in checks if check.get("required") is not False]
    if not required:
        return "warning"
    return "pass" if all(check.get("passed") is True for check in required) else "fail"


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("id") or case.get("name") or "unnamed-case")
    query = str(case.get("query") or "").strip()
    if not query:
        raise ValueError(f"benchmark case {case_id!r} requires query")
    raw_records = case.get("raw_records")
    if not isinstance(raw_records, list):
        raise ValueError(f"benchmark case {case_id!r} requires raw_records list")

    profile = _profile_from_case(case)
    expectations = case.get("expectations") if isinstance(case.get("expectations"), dict) else {}
    query_plan = build_query_plan(
        query,
        max_queries=int(case.get("query_plan_max_queries") or 6),
        profile=profile.name,
        domains=profile.domains,
        positive_keywords=profile.positive_keywords,
        negative_keywords=profile.negative_keywords,
        venue_prior=profile.venue_prior,
    )
    normalized = normalize_candidates(raw_records)
    filter_report = filter_candidates_with_report(
        normalized,
        domains=filter_domains_from_profile(profile, query_plan),
        require_pdf=bool(case.get("require_pdf", True)),
        exclude_terms=default_discovery_exclusion_terms(query),
        existing_library_index=None,
        year_min=case.get("year_min"),
        code_policy=case.get("code_policy"),
        required_concept_groups=filter_required_concept_groups_from_query_plan(query_plan),
    )
    filtered = list(filter_report.get("kept") or [])
    rejected = list(filter_report.get("rejected") or [])

    recall_record = build_recall_gap_record(filtered, existing_candidates=normalized)
    recall_filter_report: dict[str, list[dict[str, Any]]] = {"kept": [], "rejected": []}
    if recall_record.get("expansion_records"):
        recall_normalized = normalize_candidates(recall_record.get("expansion_records") or [])
        recall_normalized = annotate_recall_expansion_candidates(recall_normalized, recall_record)
        recall_filter_report = filter_candidates_with_report(
            recall_normalized,
            domains=filter_domains_from_profile(profile, query_plan),
            require_pdf=bool(case.get("require_pdf", True)),
            exclude_terms=default_discovery_exclusion_terms(query),
            existing_library_index=None,
            year_min=case.get("year_min"),
            code_policy=case.get("code_policy"),
            required_concept_groups=filter_required_concept_groups_from_query_plan(query_plan),
        )
        filtered = _merge_by_canonical_key(filtered, recall_filter_report.get("kept") or [])
        rejected.extend(recall_filter_report.get("rejected") or [])
    recall_record["filter_summary"] = {
        "recommendable": len(recall_filter_report.get("kept") or []),
        "rejected": len(recall_filter_report.get("rejected") or []),
    }

    filtered, quality_risk_record = enrich_candidates_with_quality_risk(filtered)
    ranked = rank_candidates(
        filtered,
        positive_keywords=ranking_keywords_from_profile(profile, query, query_plan),
        venue_tiers=venue_tiers_from_profile(profile, query_plan),
        negative_keywords=profile.negative_keywords + default_discovery_exclusion_terms(query),
        year_min=case.get("year_min"),
        code_policy=case.get("code_policy"),
        selection_policy=str(case.get("selection_policy") or "balanced_high_quality"),
        priority_keywords=ranking_priority_keywords_from_query_plan(query_plan),
        quality_evidence_terms=ranking_quality_evidence_terms_from_inputs(profile, query_plan),
    )
    session = build_session_recommendations(ranked, rejected)
    top_kept = _top_kept_papers(ranked)

    relevant_titles = _strings(expectations.get("relevant_titles"))
    expected_recall_titles = _strings(expectations.get("required_recall_titles"))
    precision_at_10 = _precision_at(ranked, relevant_titles, 10)
    recall_at_20 = _recall_at(ranked, expected_recall_titles, 20)
    review_leakage = len([candidate for candidate in ranked if candidate.get("quality_tier") != "Reject" and _review_like(candidate)])
    duplicate_rate = round((len(raw_records) - len(normalized)) / max(1, len(raw_records)), 4)
    verified_coverage = _verified_metric_coverage(ranked)

    checks: list[dict[str, Any]] = []
    if "min_precision_at_10" in expectations and precision_at_10 is not None:
        checks.append(
            _check(
                "precision_at_10",
                precision_at_10 >= float(expectations["min_precision_at_10"]),
                {"actual": precision_at_10, "expected_min": expectations["min_precision_at_10"]},
            )
        )
    if "max_review_leakage" in expectations:
        checks.append(
            _check(
                "review_leakage",
                review_leakage <= int(expectations["max_review_leakage"]),
                {"actual": review_leakage, "expected_max": expectations["max_review_leakage"]},
            )
        )
    if "max_duplicate_rate" in expectations:
        checks.append(
            _check(
                "duplicate_rate",
                duplicate_rate <= float(expectations["max_duplicate_rate"]),
                {"actual": duplicate_rate, "expected_max": expectations["max_duplicate_rate"]},
            )
        )
    if "min_verified_metric_coverage" in expectations:
        checks.append(
            _check(
                "verified_metric_coverage",
                verified_coverage >= float(expectations["min_verified_metric_coverage"]),
                {"actual": verified_coverage, "expected_min": expectations["min_verified_metric_coverage"]},
            )
        )
    if expected_recall_titles:
        found_recall_titles = _contains_any_title(ranked[:20], expected_recall_titles)
        checks.append(
            _check(
                "recall_at_20",
                len(found_recall_titles) == len(expected_recall_titles),
                {"found_titles": found_recall_titles, "expected_titles": expected_recall_titles},
            )
        )
    required_query_terms = _strings(expectations.get("required_query_plan_terms"))
    if required_query_terms:
        query_terms = _collect_query_plan_terms(query_plan)
        checks.append(
            _check(
                "config_terms_in_query_plan",
                all(_title_key(term) in query_terms for term in required_query_terms),
                {"required_terms": required_query_terms},
            )
        )
    citation_expectation = expectations.get("citation_normalization") if isinstance(expectations.get("citation_normalization"), dict) else {}
    if citation_expectation:
        preferred_title = str(citation_expectation.get("preferred_title") or "")
        comparison_title = str(citation_expectation.get("comparison_title") or "")
        ranked_titles = [_title_key(candidate.get("title")) for candidate in ranked]
        preferred_index = ranked_titles.index(_title_key(preferred_title)) if _title_key(preferred_title) in ranked_titles else None
        comparison_index = ranked_titles.index(_title_key(comparison_title)) if _title_key(comparison_title) in ranked_titles else None
        checks.append(
            _check(
                "normalized_citation_order",
                preferred_index is not None and comparison_index is not None and preferred_index < comparison_index,
                {
                    "preferred_title": preferred_title,
                    "comparison_title": comparison_title,
                    "preferred_index": preferred_index,
                    "comparison_index": comparison_index,
                },
            )
        )
        preserve = citation_expectation.get("preserve_absolute_citation_count")
        if isinstance(preserve, dict):
            title = str(preserve.get("title") or "")
            count = preserve.get("citation_count")
            checks.append(
                _check(
                    "absolute_citation_count_preserved",
                    isinstance(count, int) and _citation_preserved(session, title, count),
                    {"title": title, "expected_citation_count": count},
                )
            )

    status = _case_status(checks)
    return {
        "id": case_id,
        "status": status,
        "passed": status == "pass",
        "query": query,
        "query_plan": query_plan,
        "raw_candidate_count": len(raw_records),
        "deduped_candidate_count": len(normalized),
        "accepted_count": len(filtered),
        "rejected_count": len(rejected),
        "top_kept_papers": top_kept,
        "review_leakage": review_leakage,
        "recall_gaps": {
            "attempted": (recall_record.get("summary") or {}).get("attempted", 0),
            "recovered": (recall_record.get("summary") or {}).get("recovered", 0),
            "filter_summary": recall_record.get("filter_summary", {}),
            "required_recall_titles": expected_recall_titles,
            "found_required_recall_titles": _contains_any_title(ranked[:20], expected_recall_titles),
        },
        "quality_risk": quality_risk_record.get("summary", {}),
        "metrics": {
            "precision_at_10": precision_at_10,
            "recall_at_20": recall_at_20,
            "review_leakage": review_leakage,
            "duplicate_rate": duplicate_rate,
            "verified_metric_coverage": verified_coverage,
            "recall_gap_count": (recall_record.get("summary") or {}).get("recovered", 0),
        },
        "checks": checks,
        "session_recommendations": {
            "verification_summary": session.get("verification_summary"),
            "primary_count": len(session.get("primary_recommendations") or []),
            "review_appendix_count": len(session.get("review_appendix") or []),
        },
    }


def _mean(values: list[float]) -> float | None:
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _aggregate_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    passed = len([case for case in cases if case.get("status") == "pass"])
    failed = len([case for case in cases if case.get("status") == "fail"])
    metrics = [case.get("metrics") or {} for case in cases]
    return {
        "case_count": total,
        "passed": passed,
        "failed": failed,
        "warnings": len([case for case in cases if case.get("status") == "warning"]),
        "benchmark_pass_rate": round(passed / total, 4) if total else 0.0,
        "precision_at_10": _mean([item.get("precision_at_10") for item in metrics if item.get("precision_at_10") is not None]),
        "recall_at_20": _mean([item.get("recall_at_20") for item in metrics if item.get("recall_at_20") is not None]),
        "review_leakage": sum(int(item.get("review_leakage") or 0) for item in metrics),
        "duplicate_rate": _mean([float(item.get("duplicate_rate") or 0.0) for item in metrics]),
        "verified_metric_coverage": _mean([float(item.get("verified_metric_coverage") or 0.0) for item in metrics]),
        "recall_gap_count": sum(int(item.get("recall_gap_count") or 0) for item in metrics),
    }


def run_discovery_benchmark(case_json: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    payload = read_json(case_json)
    if not isinstance(payload, dict):
        raise ValueError("benchmark case JSON must contain an object")
    cases_payload = payload.get("cases")
    if not isinstance(cases_payload, list) or not cases_payload:
        raise ValueError("benchmark case JSON requires non-empty cases list")

    cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases_payload, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"benchmark cases[{index}] must be an object")
        cases.append(_run_case(case))
    metrics = _aggregate_metrics(cases)
    result = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "benchmark_id": payload.get("benchmark_id") or "paper-source-discovery-local-fixtures",
        "runner_schema_version": RUNNER_SCHEMA_VERSION,
        "case_schema_version": payload.get("schema_version") or CASE_SET_SCHEMA_VERSION,
        "created_at": utc_now(),
        "source_case_json": str(case_json),
        "status": "pass" if metrics["failed"] == 0 and metrics["case_count"] else "fail",
        "metrics": metrics,
        "cases": cases,
    }
    if output_path is not None:
        result["output_path"] = str(output_path)
        write_json_atomic(output_path, result)
    return result
