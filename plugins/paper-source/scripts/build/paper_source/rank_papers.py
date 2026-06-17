from __future__ import annotations

from math import log10


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
    hits = sum(1 for term in terms if term in text)
    return min(1.0, hits / 3)


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _classify_paper_type(candidate: dict) -> dict:
    text = _text(candidate)
    matches: list[tuple[str, list[str], int]] = []
    for priority, (paper_type, terms) in enumerate(PAPER_TYPE_RULES):
        hits = [term for term in terms if term in text]
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
    method_rigor = round(signals["benchmark_score"] * 0.55 + signals["peer_review_score"] * 0.45, 4)
    evidence_sufficiency = round(
        signals["pdf_score"] * 0.30
        + signals["benchmark_score"] * 0.35
        + signals["citation_score"] * 0.20
        + signals["reproducibility_score"] * 0.15,
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
            ["benchmark_signal", "citation_signal", "pdf_available"],
        ),
        "evidence_sufficiency": _rubric_dimension(
            evidence_sufficiency,
            ["pdf_available", "benchmark_signal", "citation_signal", "reproducibility_signal"],
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
            "Score combines profile/topic relevance, venue prior, citations, recency, PDF/code availability, and reproducibility evidence.",
            f"Classified as {classification['primary_type']} from title/abstract evidence.",
        ],
    }


def _ranking_protocol(
    *,
    matched_keywords: list[str],
    matched_negative_keywords: list[str],
    signals: dict[str, float],
    code_available: bool,
    easyscholar_signal: dict | None = None,
    selection_policy: str = "balanced_high_quality",
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
    if easyscholar_signal and float(easyscholar_signal.get("score") or 0) > 0:
        evidence = ", ".join(str(item) for item in easyscholar_signal.get("evidence") or [])
        reasons.append("EasyScholar verified metrics: " + evidence)
    if easyscholar_signal:
        cautions.extend(str(item) for item in easyscholar_signal.get("cautions") or [])
    if signals["benchmark_score"] < 0.34:
        cautions.append("weak_benchmark_signal")
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
                "signals": ["citation_signal", "benchmark_signal", "pdf_available"],
            },
            "domain_fit": {
                "score": signals["domain_fit_score"],
                "signals": ["positive_keyword_overlap", "negative_keyword_penalty"],
            },
            "reproducibility": {
                "score": signals["reproducibility_score"],
                "signals": ["code_available", "reproducibility_terms"],
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
    elif signals["domain_fit_score"] >= 0.34:
        evidence.append("topic_fit")
    else:
        blockers.append("weak_topic_fit")
    if signals["venue_score"] >= 0.75:
        evidence.append("configured_venue_prior")
    elif signals["venue_score"] >= 0.45:
        evidence.append("generic_venue_metadata")
    else:
        cautions.append("weak_venue_signal")
    if signals["citation_score"] >= 0.5:
        evidence.append("strong_citation_signal")
    elif signals["citation_score"] > 0:
        evidence.append("citation_signal")
    if signals["benchmark_score"] >= 0.34:
        evidence.append("benchmark_signal")
    else:
        cautions.append("weak_benchmark_signal")
    if signals["reproducibility_score"] >= 0.35:
        evidence.append("reproducibility_signal")
    else:
        cautions.append("weak_reproducibility_signal")
    if signals["negative_keyword_penalty"] >= 0.5:
        blockers.append("negative_keyword_overlap")

    if blockers:
        tier = "Reject"
    elif (
        score >= 0.78
        and has_stable_identifier
        and signals["domain_fit_score"] >= 0.67
        and signals["pdf_score"] > 0
        and (signals["venue_score"] >= 0.75 or signals["citation_score"] >= 0.5)
        and (signals["benchmark_score"] >= 0.34 or signals["reproducibility_score"] >= 0.35)
    ):
        tier = "Tier A"
    elif (
        score >= 0.60
        and signals["domain_fit_score"] >= 0.34
        and signals["pdf_score"] > 0
        and (
            signals["venue_score"] >= 0.45
            or signals["citation_score"] > 0
            or signals["benchmark_score"] >= 0.34
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
) -> list[dict]:
    ranked: list[dict] = []
    keywords = [keyword.lower() for keyword in positive_keywords]
    priority_terms = [keyword.lower() for keyword in (priority_keywords or [])]
    negative_terms = [keyword.lower() for keyword in (negative_keywords or [])]
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
        topic_score = min(1.0, keyword_hits / max(1, len(keywords)))
        priority_topic_score = (
            min(1.0, len(matched_priority_keywords) / max(1, len(priority_terms))) if priority_terms else 0.0
        )
        topic_score = max(topic_score, priority_topic_score)
        negative_keyword_penalty = min(1.0, len(matched_negative_keywords) / max(1, len(negative_terms)))
        profile_fit_score = max(0.0, topic_score - negative_keyword_penalty)
        venue_score = max(
            venue_tiers.get(str(candidate.get("venue") or "").lower(), 0.45),
            0.45 + easyscholar_score * 0.40,
        )
        citation_score = min(1.0, log10(int(candidate.get("citation_count") or 0) + 1) / 3)
        candidate_year = int(candidate.get("year") or 0)
        if year_min is not None:
            freshness_score = 1.0 if candidate_year >= int(year_min) else 0.0
        else:
            freshness_score = 1.0 if candidate_year >= 2024 else 0.7
        pdf_score = 1.0 if candidate.get("pdf_url") else 0.0
        code_score = 1.0 if candidate.get("code_url") else 0.0
        code_weight = 0.08
        if normalized_code_policy == "prefer":
            code_weight = 0.12
        elif normalized_code_policy == "require":
            code_weight = 0.14
        reproducibility_terms_score = _term_score(text, REPRODUCIBILITY_TERMS)
        benchmark_score = _term_score(text, BENCHMARK_TERMS)
        editorial_score = round(topic_score * 0.5 + venue_score * 0.3 + freshness_score * 0.2, 4)
        peer_review_score = round(citation_score * 0.35 + benchmark_score * 0.4 + pdf_score * 0.25, 4)
        domain_fit_score = round(profile_fit_score, 4)
        reproducibility_score = round(code_score * 0.6 + reproducibility_terms_score * 0.4, 4)
        base_score = (
            topic_score * 0.35
            + venue_score * 0.18
            + citation_score * 0.15
            + freshness_score * 0.10
            + pdf_score * 0.08
            + code_score * code_weight
            + 0.06
        )
        score = round(max(0.0, base_score - negative_keyword_penalty * 0.25), 4)
        ranked_candidate = dict(candidate)
        ranked_candidate["score"] = score
        ranked_candidate["ranking_signals"] = {
            "topic_score": round(topic_score, 4),
            "priority_topic_score": round(priority_topic_score, 4),
            "venue_score": round(venue_score, 4),
            "citation_score": round(citation_score, 4),
            "freshness_score": freshness_score,
            "pdf_score": pdf_score,
            "code_score": code_score,
            "benchmark_score": round(benchmark_score, 4),
            "reproducibility_terms_score": round(reproducibility_terms_score, 4),
            "easyscholar_score": round(easyscholar_score, 4),
            "year_min": year_min,
            "code_policy": normalized_code_policy,
            "negative_keyword_penalty": round(negative_keyword_penalty, 4),
            "editorial_score": editorial_score,
            "peer_review_score": peer_review_score,
            "domain_fit_score": domain_fit_score,
            "reproducibility_score": reproducibility_score,
        }
        classification = _classify_paper_type(candidate)
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
        )
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
