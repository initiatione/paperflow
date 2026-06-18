from __future__ import annotations

from datetime import date
from math import log10
from typing import NamedTuple

from paper_source.lexical_match import matched_terms, term_matches_text


REPRODUCIBILITY_TERMS = (
    "reproducible",
    "benchmark",
    "ablation",
    "code",
    "dataset",
    "open-source",
    "open source",
    "simulator",
    "implementation",
)
BENCHMARK_TERMS = (
    "benchmark",
    "baseline",
    "ablation",
    "comparison",
    "evaluated",
    "experiment",
    "metric",
)
TOPIC_FIT_SATURATION_HITS = 3
TOPIC_FIT_REVIEW_THRESHOLD = 0.30
GENERIC_VENUE_METADATA_SCORE = 0.35
CONFIGURED_VENUE_SENTINEL_MAX = 0.20
DEFAULT_CONFIGURED_VENUE_SCORE = 0.75


class QualityLexicon(NamedTuple):
    benchmark_terms: tuple[str, ...]
    reproducibility_terms: tuple[str, ...]
    paper_type_rules: tuple[tuple[str, tuple[str, ...]], ...]

SELECTION_POLICIES = {
    "balanced_high_quality",
    "code_preferred",
    "code_required",
    "recent_high_quality",
    "broad_map",
    "strict_advance",
}

PAPER_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "survey",
        (
            "survey",
            "review",
            "systematic review",
            "literature review",
            "meta-analysis",
            "meta analysis",
            "overview",
            "tutorial",
        ),
    ),
    (
        "dataset",
        (
            "dataset",
            "data set",
            "corpus",
            "benchmark dataset",
            "data collection",
        ),
    ),
    (
        "benchmark",
        (
            "benchmark",
            "leaderboard",
            "evaluation suite",
            "baseline comparison",
            "comparative study",
        ),
    ),
    (
        "field-trial",
        (
            "field trial",
            "sea trial",
            "real-world experiment",
            "hardware experiment",
            "deployment",
            "in-the-wild",
        ),
    ),
    (
        "theory",
        (
            "theorem",
            "proof",
            "stability analysis",
            "convergence",
            "theoretical analysis",
        ),
    ),
    (
        "system",
        (
            "system",
            "platform",
            "pipeline",
            "toolkit",
            "simulator",
            "implementation",
        ),
    ),
    (
        "method",
        (
            "method",
            "algorithm",
            "approach",
            "framework",
            "model",
            "architecture",
            "control",
            "controller",
            "policy",
        ),
    ),
    (
        "application",
        (
            "application",
            "case study",
            "empirical study",
            "experiment",
            "evaluation",
        ),
    ),
    (
        "reproducibility",
        (
            "reproducibility",
            "reproducible",
            "replication",
            "replicate",
            "open-source",
            "open source",
        ),
    ),
)


def _text(candidate: dict) -> str:
    return f"{candidate.get('title', '')} {candidate.get('abstract', '')}".lower()


def _term_score(text: str, terms: tuple[str, ...]) -> float:
    hits = sum(1 for term in terms if term_matches_text(term, text))
    return min(1.0, hits / 3)


def _normalize_term(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _strings_from_nested(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        terms = [" ".join(item.strip().split()) for item in value.split(",")]
        return [term for term in terms if term]
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
    text = " ".join(str(value).strip().split())
    return [text] if text else []


def _unique_terms(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    terms: list[str] = []
    for value in values:
        normalized = _normalize_term(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
    return tuple(terms)


def _collect_keyed_terms(payload: object, keys: set[str]) -> list[str]:
    if not payload:
        return []
    terms: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).strip().lower().replace("-", "_")
            if normalized_key in keys:
                terms.extend(_strings_from_nested(value))
                continue
            if isinstance(value, (dict, list, tuple, set)):
                terms.extend(_collect_keyed_terms(value, keys))
    elif isinstance(payload, (list, tuple, set)):
        for item in payload:
            if isinstance(item, dict):
                terms.extend(_collect_keyed_terms(item, keys))
    return terms


def _collect_paper_type_rules(payload: object) -> list[tuple[str, tuple[str, ...]]]:
    if not payload:
        return []
    rules: list[tuple[str, tuple[str, ...]]] = []

    def parse_rule_value(value: object) -> None:
        if isinstance(value, dict):
            if any(key in value for key in ("type", "paper_type", "name")) and any(
                key in value for key in ("terms", "signals", "keywords")
            ):
                paper_type = str(value.get("type") or value.get("paper_type") or value.get("name") or "").strip()
                terms = _strings_from_nested(value.get("terms") or value.get("signals") or value.get("keywords"))
                if paper_type and terms:
                    rules.append((paper_type, _unique_terms(terms)))
                return
            for paper_type, terms_value in value.items():
                if isinstance(terms_value, (dict, list, tuple, set, str)):
                    terms = _strings_from_nested(terms_value)
                    if str(paper_type).strip() and terms:
                        rules.append((str(paper_type).strip(), _unique_terms(terms)))
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                parse_rule_value(item)

    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).strip().lower().replace("-", "_")
            if normalized_key in {"paper_type_rules", "paper_types", "classification_terms"}:
                parse_rule_value(value)
            elif isinstance(value, (dict, list, tuple, set)):
                rules.extend(_collect_paper_type_rules(value))
    elif isinstance(payload, (list, tuple, set)):
        for item in payload:
            rules.extend(_collect_paper_type_rules(item))
    return rules


def _merge_paper_type_rules(extra_rules: list[tuple[str, tuple[str, ...]]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    merged: dict[str, list[str]] = {paper_type: list(terms) for paper_type, terms in PAPER_TYPE_RULES}
    order = [paper_type for paper_type, _ in PAPER_TYPE_RULES]
    for paper_type, terms in extra_rules:
        normalized_type = str(paper_type).strip()
        if not normalized_type:
            continue
        if normalized_type not in merged:
            merged[normalized_type] = []
            order.append(normalized_type)
        merged[normalized_type].extend(terms)
    return tuple((paper_type, _unique_terms(merged[paper_type])) for paper_type in order)


def _quality_lexicon(quality_evidence_terms: object | None) -> QualityLexicon:
    benchmark_keys = {
        "benchmark_terms",
        "benchmarks",
        "benchmark_evidence_terms",
        "validation_terms",
        "validation_evidence_terms",
        "evidence_terms",
        "quality_signals",
    }
    reproducibility_keys = {
        "reproducibility_terms",
        "reproducibility_evidence_terms",
        "code_data_terms",
        "code_terms",
        "data_terms",
        "open_science_terms",
    }
    benchmark_terms = _unique_terms(
        [*BENCHMARK_TERMS, *_collect_keyed_terms(quality_evidence_terms, benchmark_keys)]
    )
    reproducibility_terms = _unique_terms(
        [*REPRODUCIBILITY_TERMS, *_collect_keyed_terms(quality_evidence_terms, reproducibility_keys)]
    )
    paper_type_rules = _merge_paper_type_rules(_collect_paper_type_rules(quality_evidence_terms))
    return QualityLexicon(
        benchmark_terms=benchmark_terms,
        reproducibility_terms=reproducibility_terms,
        paper_type_rules=paper_type_rules,
    )


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return matched_terms(text, keywords)


def _saturating_topic_score(hit_count: int, term_count: int) -> float:
    if term_count <= 0:
        return 0.0
    denominator = min(TOPIC_FIT_SATURATION_HITS, term_count)
    return min(1.0, hit_count / max(1, denominator))


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _venue_signal(candidate: dict, venue_tiers: dict[str, float], easyscholar_score: float) -> dict[str, object]:
    venue = _normalize_term(candidate.get("venue"))
    configured_raw = venue_tiers.get(venue) if venue else None
    configured = configured_raw is not None
    if configured:
        try:
            raw_score = float(configured_raw)
        except (TypeError, ValueError):
            raw_score = DEFAULT_CONFIGURED_VENUE_SCORE
        if 0 < raw_score <= CONFIGURED_VENUE_SENTINEL_MAX:
            score = DEFAULT_CONFIGURED_VENUE_SCORE
        else:
            score = max(0.0, min(1.0, raw_score))
        status = "configured_prior"
    elif venue:
        score = GENERIC_VENUE_METADATA_SCORE
        status = "metadata_only"
    else:
        score = 0.0
        status = "missing"

    if easyscholar_score > 0:
        metrics_score = min(1.0, 0.45 + easyscholar_score * 0.40)
        if metrics_score > score:
            score = metrics_score
            status = "configured_prior_and_verified_metrics" if configured else "verified_metrics"
    return {
        "score": round(score, 4),
        "status": status,
        "configured": configured,
        "configured_raw": configured_raw,
    }


def _citation_signal(candidate: dict, *, candidate_year: int, reference_year: int) -> dict[str, object]:
    raw_available = "citation_count" in candidate and candidate.get("citation_count") not in {None, ""}
    raw_count = _int_or_none(candidate.get("citation_count")) if raw_available else None
    source = candidate.get("citation_count_source")
    status = str(candidate.get("citation_count_status") or ("verified" if source else "unverified"))
    if raw_count is None:
        basis = {
            "status": status if status else "unverified",
            "source": source,
            "raw_count": None,
            "reference_year": reference_year,
            "publication_age_years": None,
            "citations_per_year": None,
            "normalizer": "missing citation_count -> ranking score 0",
        }
        return {
            "score": 0.0,
            "absolute_score": 0.0,
            "normalized_score": 0.0,
            "age_adjusted_score": 0.0,
            "raw_count": None,
            "available": False,
            "status": basis["status"],
            "source": source,
            "basis": basis,
        }

    raw_count = max(0, raw_count)
    publication_age_years = max(0, reference_year - candidate_year) if candidate_year else None
    age_denominator = max(1, (publication_age_years if publication_age_years is not None else 0) + 1)
    citations_per_year = raw_count / age_denominator
    absolute_score = min(1.0, log10(raw_count + 1) / 3)
    normalized_score = min(1.0, log10(citations_per_year + 1) / 2)
    basis = {
        "status": status,
        "source": source,
        "raw_count": raw_count,
        "reference_year": reference_year,
        "publication_age_years": publication_age_years,
        "citations_per_year": round(citations_per_year, 4),
        "normalizer": "log10(citations_per_year + 1) / 2",
        "absolute_log_score": round(absolute_score, 4),
    }
    return {
        "score": round(normalized_score, 4),
        "absolute_score": round(absolute_score, 4),
        "normalized_score": round(normalized_score, 4),
        "age_adjusted_score": round(normalized_score, 4),
        "raw_count": raw_count,
        "available": True,
        "status": status,
        "source": source,
        "basis": basis,
    }


def _freshness_signal(candidate_year: int, *, year_min: int | None, reference_year: int) -> dict[str, object]:
    if year_min is not None:
        score = 1.0 if candidate_year >= int(year_min) else 0.0
        return {
            "score": score,
            "basis": {
                "mode": "request_year_min",
                "year_min": int(year_min),
                "reference_year": reference_year,
                "candidate_year": candidate_year or None,
            },
        }
    if not candidate_year:
        return {
            "score": 0.0,
            "basis": {
                "mode": "current_year_relative",
                "reference_year": reference_year,
                "candidate_year": None,
                "status": "missing_year",
            },
        }
    age = max(0, reference_year - candidate_year)
    if age <= 1:
        score = 1.0
    elif age <= 2:
        score = 0.9
    elif age <= 5:
        score = 0.75
    else:
        score = 0.55
    return {
        "score": score,
        "basis": {
            "mode": "current_year_relative",
            "reference_year": reference_year,
            "candidate_year": candidate_year,
            "publication_age_years": age,
        },
    }


def _classify_paper_type(
    candidate: dict,
    paper_type_rules: tuple[tuple[str, tuple[str, ...]], ...] = PAPER_TYPE_RULES,
) -> dict:
    text = _text(candidate)
    matches: list[tuple[str, list[str], int]] = []
    for priority, (paper_type, terms) in enumerate(paper_type_rules):
        hits = matched_terms(text, list(terms))
        if hits:
            matches.append((paper_type, hits, priority))

    if not matches:
        return {
            "schema_version": "paper-source-paper-classification-v1",
            "primary_type": "unknown",
            "secondary_types": [],
            "confidence": 0.25,
            "evidence": [],
            "type_scores": {},
        }

    matches.sort(key=lambda item: (-len(item[1]), item[2]))
    primary_type, primary_hits, _ = matches[0]
    confidence = round(min(0.95, 0.45 + len(primary_hits) * 0.12 + (0.08 if len(matches) == 1 else 0.0)), 4)
    return {
        "schema_version": "paper-source-paper-classification-v1",
        "primary_type": primary_type,
        "secondary_types": [paper_type for paper_type, _, _ in matches[1:4]],
        "confidence": confidence,
        "evidence": [f"{primary_type}:{term}" for term in primary_hits[:5]],
        "type_scores": {paper_type: len(hits) for paper_type, hits, _ in matches},
    }


def _rubric_dimension(score: float, signals: list[str]) -> dict:
    return {"score": round(score, 4), "signals": signals}


def _ranking_rubric(
    *,
    signals: dict[str, float],
    matched_keywords: list[str],
    classification: dict,
) -> dict:
    source_confidence = round(
        signals["venue_score"] * 0.35
        + signals["citation_score"] * 0.25
        + signals["pdf_score"] * 0.30
        + signals["easyscholar_score"] * 0.10,
        4,
    )
    method_rigor = round(
        signals.get("method_rigor_score", 0.0) * 0.65 + signals["peer_review_score"] * 0.35,
        4,
    )
    evidence_sufficiency = round(
        signals["pdf_score"] * 0.30
        + signals.get("validation_strength_score", signals["benchmark_score"]) * 0.35
        + signals["citation_score"] * 0.15
        + signals["reproducibility_score"] * 0.20,
        4,
    )
    keyword_confidence = min(1.0, len(matched_keywords) / 3)
    ranking_confidence = round(
        min(
            1.0,
            0.20
            + keyword_confidence * 0.25
            + signals["pdf_score"] * 0.20
            + source_confidence * 0.20
            + max(signals["benchmark_score"], signals["reproducibility_score"]) * 0.15,
        ),
        4,
    )
    dimensions = {
        "relevance": _rubric_dimension(
            signals["domain_fit_score"],
            ["positive_keyword_overlap", "negative_keyword_penalty"],
        ),
        "method_rigor": _rubric_dimension(
            method_rigor,
            ["benchmark_signal", "validation_strength", "reproducibility_signal", "citation_signal"],
        ),
        "evidence_sufficiency": _rubric_dimension(
            evidence_sufficiency,
            ["pdf_available", "validation_strength", "citation_signal", "reproducibility_signal"],
        ),
        "reproducibility": _rubric_dimension(
            signals["reproducibility_score"],
            ["code_available", "reproducibility_terms"],
        ),
        "source_confidence": _rubric_dimension(
            source_confidence,
            [
                "venue_prior",
                "citation_signal",
                "pdf_available",
                *(["easyscholar_verified_metrics"] if signals["easyscholar_score"] > 0 else []),
            ],
        ),
    }
    return {
        "schema_version": "paper-source-ranking-rubric-v1",
        "paper_type": classification["primary_type"],
        "dimensions": dimensions,
        "ranking_confidence": ranking_confidence,
        "score_explanation": [
            "Score combines profile/topic relevance, venue prior, normalized citations, recency, PDF/code/data availability, validation strength, and reproducibility evidence.",
            f"Classified as {classification['primary_type']} from title/abstract evidence.",
        ],
    }


def _quality_risk_payload(candidate: dict) -> dict:
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


def _quality_risk_signal(quality_risk: dict) -> dict[str, object]:
    status = str(quality_risk.get("status") or "unverified").strip().lower()
    severity = str(quality_risk.get("severity") or "unknown").strip().lower()
    confidence = str(quality_risk.get("confidence") or "none").strip().lower()
    risk_types = [str(item) for item in quality_risk.get("risk_types") or [] if str(item).strip()]
    verified = status == "verified"
    suspected = status == "suspected"
    severe = severity == "severe"
    penalty = 0.0
    if verified and severe:
        penalty = 0.45
    elif verified:
        penalty = 0.25
    elif suspected:
        penalty = 0.08
    return {
        "status": status,
        "severity": severity,
        "confidence": confidence,
        "risk_types": risk_types,
        "verified": verified,
        "suspected": suspected,
        "verified_severe": bool(verified and severe),
        "penalty": penalty,
    }


def _quality_risk_dimension(quality_risk: dict) -> dict:
    signal = _quality_risk_signal(quality_risk)
    if signal["verified_severe"]:
        status = "verified_severe"
        score = 0.0
    elif signal["verified"]:
        status = "verified"
        score = 0.25
    elif signal["suspected"]:
        status = "suspected"
        score = 0.5
    else:
        status = "unverified"
        score = 0.5
    return {
        "score": score,
        "status": status,
        "severity": signal["severity"],
        "confidence": signal["confidence"],
        "signals": list(signal["risk_types"]) or ["risk_metadata_unverified"],
    }


def _ranking_protocol(
    *,
    matched_keywords: list[str],
    matched_negative_keywords: list[str],
    signals: dict[str, float],
    code_available: bool,
    easyscholar_signal: dict | None = None,
    selection_policy: str = "balanced_high_quality",
    quality_risk: dict | None = None,
) -> dict:
    reasons: list[str] = []
    cautions: list[str] = []
    if matched_keywords:
        reasons.append("matched keywords: " + ", ".join(matched_keywords))
    if matched_negative_keywords:
        cautions.append("negative_keyword_overlap: " + ", ".join(matched_negative_keywords))
    if code_available:
        reasons.append("code availability signal present")
    else:
        cautions.append("weak_reproducibility_signal")
    if signals.get("data_score", 0.0) > 0:
        reasons.append("data availability signal present")
    if signals.get("validation_strength_score", 0.0) >= 0.34:
        reasons.append("validation evidence signal present")
    if easyscholar_signal and float(easyscholar_signal.get("score") or 0) > 0:
        evidence = ", ".join(str(item) for item in easyscholar_signal.get("evidence") or [])
        reasons.append("EasyScholar verified metrics: " + evidence)
    if easyscholar_signal:
        cautions.extend(str(item) for item in easyscholar_signal.get("cautions") or [])
    quality_risk = quality_risk or {}
    risk_signal = _quality_risk_signal(quality_risk)
    if risk_signal["verified_severe"]:
        cautions.append("verified_quality_risk")
    for caution in quality_risk.get("cautions") or []:
        text = str(caution)
        if text and text not in cautions:
            cautions.append(text)
    if signals["benchmark_score"] < 0.34:
        cautions.append("weak_benchmark_signal")
    if signals.get("validation_strength_score", signals["benchmark_score"]) < 0.34:
        cautions.append("weak_validation_signal")
    if signals["venue_score"] < 0.5:
        cautions.append("weak_venue_signal")

    if selection_policy == "strict_advance":
        advance = (
            signals["score"] >= 0.75
            and signals["reproducibility_score"] >= 0.35
            and signals["negative_keyword_penalty"] < 0.34
        )
    elif selection_policy == "code_required":
        advance = code_available and signals["score"] >= 0.68 and signals["negative_keyword_penalty"] < 0.34
    elif selection_policy == "code_preferred":
        advance = (
            signals["score"] >= 0.70
            and signals["domain_fit_score"] >= 0.34
            and signals["negative_keyword_penalty"] < 0.34
            and (code_available or signals["reproducibility_score"] >= 0.25)
        )
    elif selection_policy == "recent_high_quality":
        advance = (
            signals["score"] >= 0.70
            and signals["freshness_score"] >= 1.0
            and signals["domain_fit_score"] >= 0.34
            and signals["negative_keyword_penalty"] < 0.34
        )
    elif selection_policy == "broad_map":
        advance = (
            signals["score"] >= 0.58
            and signals["domain_fit_score"] >= 0.25
            and signals["negative_keyword_penalty"] < 0.5
        )
    else:
        advance = (
            signals["score"] >= 0.68
            and signals["domain_fit_score"] >= 0.34
            and signals["negative_keyword_penalty"] < 0.34
        )
    decision = "advance-candidate" if advance else "review-candidate"
    return {
        "schema_version": "paper-source-ranking-protocol-v1",
        "selection_policy": selection_policy,
        "decision": decision,
        "matched_positive_keywords": matched_keywords,
        "matched_negative_keywords": matched_negative_keywords,
        "reasons": reasons,
        "cautions": cautions,
        "lenses": {
            "editorial": {
                "score": signals["editorial_score"],
                "signals": ["venue_tier", "freshness", "topic_relevance"],
            },
            "peer_review": {
                "score": signals["peer_review_score"],
                "signals": ["normalized_citation_signal", "benchmark_signal", "validation_strength", "pdf_available"],
            },
            "domain_fit": {
                "score": signals["domain_fit_score"],
                "signals": ["positive_keyword_overlap", "negative_keyword_penalty"],
            },
            "reproducibility": {
                "score": signals["reproducibility_score"],
                "signals": ["code_available", "data_available", "reproducibility_terms"],
            },
        },
    }


def _quality_gate(
    *,
    candidate: dict,
    signals: dict[str, float],
    classification: dict,
    score: float,
) -> dict:
    evidence: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []
    has_stable_identifier = bool(candidate.get("doi") or candidate.get("arxiv_id"))
    quality_risk = _quality_risk_payload(candidate)
    risk_signal = _quality_risk_signal(quality_risk)

    if has_stable_identifier:
        evidence.append("stable_identifier")
    else:
        cautions.append("stable_identifier_unverified")
    if signals["pdf_score"] > 0:
        evidence.append("pdf_available")
    else:
        cautions.append("missing_pdf")
    if signals["domain_fit_score"] >= 0.67:
        evidence.append("high_topic_fit")
    elif signals["domain_fit_score"] >= TOPIC_FIT_REVIEW_THRESHOLD:
        evidence.append("topic_fit")
    else:
        blockers.append("weak_topic_fit")
    if signals.get("venue_score_status") in {"configured_prior", "configured_prior_and_verified_metrics"}:
        evidence.append("configured_venue_prior")
    elif signals["venue_score"] >= GENERIC_VENUE_METADATA_SCORE:
        evidence.append("generic_venue_metadata")
    else:
        cautions.append("venue_metadata_unverified")
    if signals["citation_score"] >= 0.5:
        evidence.append("strong_normalized_citation_signal")
    elif signals["citation_score"] > 0:
        evidence.append("normalized_citation_signal")
    if signals["benchmark_score"] >= 0.34:
        evidence.append("benchmark_signal")
    else:
        cautions.append("weak_benchmark_signal")
    if signals["reproducibility_score"] >= 0.35:
        evidence.append("reproducibility_signal")
    else:
        cautions.append("weak_reproducibility_signal")
    if signals.get("data_score", 0.0) > 0:
        evidence.append("data_available")
    if signals.get("validation_strength_score", 0.0) >= 0.34:
        evidence.append("validation_signal")
    if signals["negative_keyword_penalty"] >= 0.5:
        blockers.append("negative_keyword_overlap")
    if risk_signal["verified_severe"]:
        blockers.append("verified_quality_risk")
        evidence.append("quality_risk_verified")
    elif risk_signal["verified"]:
        cautions.append("quality_risk_verified")
        evidence.append("quality_risk_verified")
    elif risk_signal["suspected"]:
        cautions.append("quality_risk_suspected")
    else:
        cautions.append("quality_risk_unverified")

    source_confidence_score = round(
        signals["venue_score"] * 0.35
        + signals["citation_score"] * 0.25
        + signals["pdf_score"] * 0.30
        + signals["easyscholar_score"] * 0.10,
        4,
    )
    validation_score = round(signals.get("validation_strength_score", 0.0), 4)
    dimensions = {
        "identity": {
            "score": 1.0 if has_stable_identifier else 0.0,
            "status": "stable" if has_stable_identifier else "unverified",
            "signals": ["doi_or_arxiv"] if has_stable_identifier else ["missing_doi_or_arxiv"],
        },
        "relevance": {
            "score": round(signals["domain_fit_score"], 4),
            "status": "pass" if signals["domain_fit_score"] >= TOPIC_FIT_REVIEW_THRESHOLD else "weak",
            "basis": signals.get("topic_fit_basis"),
            "signals": ["priority_keyword_overlap" if signals.get("topic_fit_basis") == "priority_keywords" else "positive_keyword_overlap"],
        },
        "inspectability": {
            "score": round(signals["pdf_score"], 4),
            "status": "pdf_available" if signals["pdf_score"] > 0 else "needs_pdf",
            "signals": ["pdf_available"] if signals["pdf_score"] > 0 else ["missing_pdf"],
        },
        "validation": {
            "score": validation_score,
            "status": "supported" if validation_score >= 0.34 else "thin",
            "signals": ["benchmark", "normalized_citation", "reproducibility_terms", "code_or_data"],
        },
        "source_confidence": {
            "score": source_confidence_score,
            "status": "strong" if source_confidence_score >= 0.67 else "limited",
            "signals": ["venue", "citation", "pdf", "easyscholar"],
        },
        "reproducibility": {
            "score": round(signals["reproducibility_score"], 4),
            "status": "present" if signals["reproducibility_score"] >= 0.35 else "weak",
            "signals": ["code_or_data_or_reproducibility_terms"],
        },
        "request_risk": {
            "score": round(max(0.0, 1.0 - signals["negative_keyword_penalty"]), 4),
            "status": "blocked" if signals["negative_keyword_penalty"] >= 0.5 else "clear",
            "signals": ["negative_keyword_overlap"] if signals["negative_keyword_penalty"] > 0 else [],
        },
        "quality_risk": _quality_risk_dimension(quality_risk),
    }

    has_tier_a_validation = (
        signals.get("validation_strength_score", 0.0) >= 0.34
        and (
            signals["benchmark_score"] >= 0.34
            or signals["reproducibility_score"] >= 0.35
            or signals["citation_score"] >= 0.5
        )
    )

    if blockers:
        tier = "Reject"
    elif (
        score >= 0.78
        and has_stable_identifier
        and signals["domain_fit_score"] >= 0.67
        and signals["pdf_score"] > 0
        and has_tier_a_validation
    ):
        tier = "Tier A"
    elif (
        score >= 0.60
        and signals["domain_fit_score"] >= TOPIC_FIT_REVIEW_THRESHOLD
        and signals["pdf_score"] > 0
        and (
            signals["venue_score"] >= DEFAULT_CONFIGURED_VENUE_SCORE
            or signals["citation_score"] > 0
            or signals["benchmark_score"] >= 0.34
            or signals.get("validation_strength_score", 0.0) >= 0.34
        )
    ):
        tier = "Tier B"
    else:
        tier = "Tier C"

    return {
        "schema_version": "paper-source-quality-gate-v1",
        "tier": tier,
        "paper_type": classification["primary_type"],
        "evidence": evidence,
        "cautions": cautions,
        "blocking_reasons": blockers,
        "dimensions": dimensions,
    }


def _score_take(score: float, *, strong: str, weak: str) -> str:
    return strong if score >= 0.7 else weak


def _ranking_rationale(
    *,
    decision: str,
    matched_keywords: list[str],
    matched_negative_keywords: list[str],
    protocol: dict,
    signals: dict[str, float],
) -> dict:
    review_before_ingest = list(protocol.get("cautions") or [])
    if decision == "advance-candidate":
        one_sentence = (
            "Advance for low-burden reading report and LLM Wiki deposition: "
            "the paper matches the user profile and has enough evidence signals to inspect."
        )
    else:
        one_sentence = (
            "review before ingest: the paper may match the topic, but ranking checks found signals "
            "that need human or critic attention first."
        )
    if matched_negative_keywords:
        review_before_ingest.append("negative_keyword_overlap")

    return {
        "schema_version": "paper-source-ranking-rationale-v1",
        "recommendation": decision,
        "one_sentence": one_sentence,
        "user_interest_match": {
            "positive_keywords": matched_keywords,
            "negative_keywords": matched_negative_keywords,
        },
        "role_views": {
            "nature_sci_editor": {
                "lens": "editorial significance",
                "take": _score_take(
                    signals["editorial_score"],
                    strong="Strong topic, venue, or freshness signal for a concise editorial summary.",
                    weak="Editorial value is plausible but not yet strong enough to prioritize without review.",
                ),
            },
            "peer_reviewer": {
                "lens": "method and evidence",
                "take": _score_take(
                    signals["peer_review_score"],
                    strong="Benchmark, citation, or PDF evidence is inspectable for method review.",
                    weak="Method evidence looks thin; check baselines, metrics, and experimental setup before ingest.",
                ),
            },
            "senior_domain_researcher": {
                "lens": "theory and experiment transfer",
                "take": _score_take(
                    signals["domain_fit_score"],
                    strong="Good fit for theory notes, experiment ideas, and domain synthesis.",
                    weak="Domain fit is partial; keep it in review unless it fills a specific wiki gap.",
                ),
            },
        },
        "wiki_deposition": {
            "value": "If advanced, distill into reference, concept, synthesis, and low-burden reading report pages.",
            "suggested_pages": ["references", "concepts", "synthesis", "reports"],
        },
        "review_before_ingest": review_before_ingest,
    }


def rank_candidates(
    candidates: list[dict],
    positive_keywords: list[str],
    venue_tiers: dict[str, float],
    negative_keywords: list[str] | None = None,
    year_min: int | None = None,
    code_policy: str | None = None,
    selection_policy: str = "balanced_high_quality",
    priority_keywords: list[str] | None = None,
    quality_evidence_terms: object | None = None,
) -> list[dict]:
    ranked: list[dict] = []
    keywords = [keyword.lower() for keyword in positive_keywords]
    priority_terms = [keyword.lower() for keyword in (priority_keywords or [])]
    negative_terms = [keyword.lower() for keyword in (negative_keywords or [])]
    reference_year = date.today().year
    lexicon = _quality_lexicon(quality_evidence_terms)
    normalized_code_policy = str(code_policy or "ignore").strip().lower()
    if normalized_code_policy not in {"ignore", "prefer", "require"}:
        raise ValueError(f"unknown code_policy: {code_policy}")
    normalized_selection_policy = str(selection_policy or "balanced_high_quality").strip().lower()
    if normalized_selection_policy not in SELECTION_POLICIES:
        raise ValueError(f"unknown selection_policy: {selection_policy}")
    for candidate in candidates:
        text = _text(candidate)
        easyscholar_signal = (candidate.get("quality_signals") or {}).get("easyscholar") or {}
        easyscholar_score = max(0.0, min(1.0, float(easyscholar_signal.get("score") or 0.0)))
        matched_keywords = _matched_keywords(text, keywords)
        matched_priority_keywords = _matched_keywords(text, priority_terms)
        for keyword in matched_priority_keywords:
            if keyword not in matched_keywords:
                matched_keywords.append(keyword)
        matched_negative_keywords = _matched_keywords(text, negative_terms)
        keyword_hits = len(matched_keywords)
        keyword_topic_score = _saturating_topic_score(keyword_hits, len(keywords))
        keyword_coverage_score = min(1.0, keyword_hits / max(1, len(keywords))) if keywords else 0.0
        priority_topic_score = (
            min(1.0, len(matched_priority_keywords) / max(1, len(priority_terms))) if priority_terms else 0.0
        )
        if priority_terms:
            topic_score = priority_topic_score
            topic_fit_basis = "priority_keywords"
        else:
            topic_score = keyword_topic_score
            topic_fit_basis = "positive_keywords_saturated"
        negative_keyword_penalty = min(1.0, len(matched_negative_keywords) / max(1, len(negative_terms)))
        profile_fit_score = max(0.0, topic_score - negative_keyword_penalty)
        candidate_year = _int_or_none(candidate.get("year")) or 0
        venue_signal = _venue_signal(candidate, venue_tiers, easyscholar_score)
        venue_score = float(venue_signal["score"])
        citation_signal = _citation_signal(candidate, candidate_year=candidate_year, reference_year=reference_year)
        citation_score = float(citation_signal["score"])
        freshness_signal = _freshness_signal(candidate_year, year_min=year_min, reference_year=reference_year)
        freshness_score = float(freshness_signal["score"])
        pdf_score = 1.0 if candidate.get("pdf_url") else 0.0
        code_score = 1.0 if candidate.get("code_url") else 0.0
        data_score = 1.0 if candidate.get("data_url") or candidate.get("dataset_url") else 0.0
        availability_score = max(code_score, data_score)
        quality_risk = _quality_risk_payload(candidate)
        quality_risk_signal = _quality_risk_signal(quality_risk)
        code_weight = 0.08
        if normalized_code_policy == "prefer":
            code_weight = 0.12
        elif normalized_code_policy == "require":
            code_weight = 0.14
        reproducibility_terms_score = _term_score(text, lexicon.reproducibility_terms)
        benchmark_score = _term_score(text, lexicon.benchmark_terms)
        classification = _classify_paper_type(candidate, lexicon.paper_type_rules)
        paper_type_signal = 0.0 if classification["primary_type"] == "unknown" else float(classification["confidence"])
        editorial_score = round(topic_score * 0.5 + venue_score * 0.3 + freshness_score * 0.2, 4)
        domain_fit_score = round(profile_fit_score, 4)
        reproducibility_score = round(availability_score * 0.55 + reproducibility_terms_score * 0.45, 4)
        validation_strength_score = round(
            max(
                benchmark_score,
                reproducibility_terms_score * 0.85,
                citation_score * 0.65,
                code_score * 0.45,
                data_score * 0.50,
            ),
            4,
        )
        method_rigor_score = round(
            benchmark_score * 0.40
            + reproducibility_score * 0.25
            + validation_strength_score * 0.20
            + paper_type_signal * 0.10
            + pdf_score * 0.05,
            4,
        )
        peer_review_score = round(
            citation_score * 0.25
            + benchmark_score * 0.30
            + validation_strength_score * 0.25
            + pdf_score * 0.20,
            4,
        )
        base_score = (
            topic_score * 0.34
            + venue_score * 0.16
            + citation_score * 0.10
            + freshness_score * 0.10
            + pdf_score * 0.08
            + code_score * code_weight
            + benchmark_score * 0.08
            + reproducibility_score * 0.06
            + validation_strength_score * 0.06
            + 0.05
        )
        score = round(
            min(1.0, max(0.0, base_score - negative_keyword_penalty * 0.25 - float(quality_risk_signal["penalty"]))),
            4,
        )
        ranked_candidate = dict(candidate)
        ranked_candidate["score"] = score
        ranked_candidate["ranking_signals"] = {
            "topic_score": round(topic_score, 4),
            "keyword_topic_score": round(keyword_topic_score, 4),
            "keyword_coverage_score": round(keyword_coverage_score, 4),
            "priority_topic_score": round(priority_topic_score, 4),
            "topic_fit_basis": topic_fit_basis,
            "matched_positive_keywords_count": len(matched_keywords),
            "positive_keyword_count": len(keywords),
            "matched_priority_keywords_count": len(matched_priority_keywords),
            "priority_keyword_count": len(priority_terms),
            "venue_score": round(venue_score, 4),
            "venue_score_status": venue_signal["status"],
            "venue_configured_prior": bool(venue_signal["configured"]),
            "venue_configured_raw": venue_signal["configured_raw"],
            "citation_score": round(citation_score, 4),
            "citation_count_raw": citation_signal["raw_count"],
            "citation_count_available": citation_signal["available"],
            "citation_count_status": citation_signal["status"],
            "citation_count_source": citation_signal["source"],
            "citation_absolute_score": citation_signal["absolute_score"],
            "citation_normalized_score": citation_signal["normalized_score"],
            "citation_age_adjusted_score": citation_signal["age_adjusted_score"],
            "citation_score_basis": citation_signal["basis"],
            "freshness_score": freshness_score,
            "freshness_basis": freshness_signal["basis"],
            "pdf_score": pdf_score,
            "code_score": code_score,
            "data_score": data_score,
            "availability_score": availability_score,
            "benchmark_score": round(benchmark_score, 4),
            "reproducibility_terms_score": round(reproducibility_terms_score, 4),
            "validation_strength_score": validation_strength_score,
            "method_rigor_score": method_rigor_score,
            "easyscholar_score": round(easyscholar_score, 4),
            "year_min": year_min,
            "code_policy": normalized_code_policy,
            "negative_keyword_penalty": round(negative_keyword_penalty, 4),
            "quality_risk_status": quality_risk_signal["status"],
            "quality_risk_severity": quality_risk_signal["severity"],
            "quality_risk_confidence": quality_risk_signal["confidence"],
            "quality_risk_types": quality_risk_signal["risk_types"],
            "quality_risk_verified_severe": quality_risk_signal["verified_severe"],
            "quality_risk_penalty": quality_risk_signal["penalty"],
            "editorial_score": editorial_score,
            "peer_review_score": peer_review_score,
            "domain_fit_score": domain_fit_score,
            "reproducibility_score": reproducibility_score,
        }
        quality_gate = _quality_gate(
            candidate=candidate,
            signals=ranked_candidate["ranking_signals"],
            classification=classification,
            score=score,
        )
        rubric = _ranking_rubric(
            signals=ranked_candidate["ranking_signals"],
            matched_keywords=matched_keywords,
            classification=classification,
        )
        protocol = _ranking_protocol(
            matched_keywords=matched_keywords,
            matched_negative_keywords=matched_negative_keywords,
            signals={
                **ranked_candidate["ranking_signals"],
                "score": score,
            },
            code_available=bool(candidate.get("code_url")),
            easyscholar_signal=easyscholar_signal,
            selection_policy=normalized_selection_policy,
            quality_risk=quality_risk,
        )
        if quality_gate["tier"] in {"Reject", "Tier C"} and protocol["decision"] == "advance-candidate":
            protocol["decision"] = "review-candidate"
            protocol.setdefault("cautions", []).append(f"quality_tier_{quality_gate['tier'].lower().replace(' ', '_')}")
        protocol["paper_type"] = classification["primary_type"]
        protocol["classification_confidence"] = classification["confidence"]
        protocol["quality_tier"] = quality_gate["tier"]
        protocol["quality_gate"] = quality_gate
        protocol["rubric_scores"] = {
            name: dimension["score"]
            for name, dimension in rubric["dimensions"].items()
        }
        protocol["ranking_confidence"] = rubric["ranking_confidence"]
        ranked_candidate["paper_type"] = classification["primary_type"]
        ranked_candidate["classification_confidence"] = classification["confidence"]
        ranked_candidate["classification_evidence"] = classification["evidence"]
        ranked_candidate["paper_classification"] = classification
        ranked_candidate["quality_risk"] = quality_risk
        ranked_candidate["quality_tier"] = quality_gate["tier"]
        ranked_candidate["quality_gate"] = quality_gate
        ranked_candidate["ranking_rubric"] = rubric
        ranked_candidate["ranking_confidence"] = rubric["ranking_confidence"]
        ranked_candidate["ranking_protocol"] = protocol
        ranked_candidate["ranking_rationale"] = _ranking_rationale(
            decision=protocol["decision"],
            matched_keywords=matched_keywords,
            matched_negative_keywords=matched_negative_keywords,
            protocol=protocol,
            signals=ranked_candidate["ranking_signals"],
        )
        ranked.append(ranked_candidate)
    return sorted(ranked, key=lambda item: item["score"], reverse=True)
