from datetime import date

from paper_source.rank_papers import rank_candidates


def test_rank_candidates_emits_explainable_research_quality_protocol():
    candidates = [
        {
            "slug": "embodied-control",
            "title": "Embodied Humanoid Control with Reproducible Benchmarks",
            "abstract": (
                "Robot learning for humanoid control with benchmark comparisons, "
                "ablation studies, and open code."
            ),
            "year": 2025,
            "venue": "ICRA",
            "doi": "10.1234/embodied-control",
            "citation_count": 42,
            "pdf_url": "https://example.org/paper.pdf",
            "code_url": "https://github.com/example/embodied-control",
            "sources": ["semantic_scholar", "openalex"],
        }
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["humanoid", "control", "benchmark"],
        venue_tiers={"icra": 1.0},
    )

    top = ranked[0]
    assert top["score"] > 0.8
    assert top["paper_type"] == "benchmark"
    assert top["classification_confidence"] >= 0.5
    assert top["paper_classification"]["schema_version"] == "paper-source-paper-classification-v1"
    assert top["ranking_rubric"]["schema_version"] == "paper-source-ranking-rubric-v1"
    assert set(top["ranking_rubric"]["dimensions"]) == {
        "relevance",
        "method_rigor",
        "evidence_sufficiency",
        "reproducibility",
        "source_confidence",
    }
    assert top["ranking_confidence"] == top["ranking_rubric"]["ranking_confidence"]
    assert top["ranking_protocol"]["schema_version"] == "paper-source-ranking-protocol-v1"
    assert top["ranking_protocol"]["paper_type"] == "benchmark"
    assert top["ranking_protocol"]["classification_confidence"] == top["classification_confidence"]
    assert top["quality_tier"] == "Tier A"
    assert top["quality_gate"]["schema_version"] == "paper-source-quality-gate-v1"
    assert top["quality_gate"]["tier"] == "Tier A"
    assert "stable_identifier" in top["quality_gate"]["evidence"]
    assert "high_topic_fit" in top["quality_gate"]["evidence"]
    assert set(top["quality_gate"]["dimensions"]) == {
        "identity",
        "relevance",
        "inspectability",
        "validation",
        "source_confidence",
        "reproducibility",
        "request_risk",
        "quality_risk",
    }
    assert top["quality_gate"]["dimensions"]["relevance"]["basis"] == "positive_keywords_saturated"
    assert top["quality_gate"]["dimensions"]["quality_risk"]["status"] == "unverified"
    assert top["quality_risk"]["status"] == "unverified"
    assert top["ranking_protocol"]["quality_tier"] == "Tier A"
    assert top["ranking_protocol"]["quality_gate"] == top["quality_gate"]
    assert top["ranking_protocol"]["ranking_confidence"] == top["ranking_confidence"]
    assert set(top["ranking_protocol"]["rubric_scores"]) == set(top["ranking_rubric"]["dimensions"])
    assert top["ranking_protocol"]["lenses"] == {
        "editorial": {
            "score": top["ranking_signals"]["editorial_score"],
            "signals": ["venue_tier", "freshness", "topic_relevance"],
        },
        "peer_review": {
            "score": top["ranking_signals"]["peer_review_score"],
            "signals": ["normalized_citation_signal", "benchmark_signal", "validation_strength", "pdf_available"],
        },
        "domain_fit": {
            "score": top["ranking_signals"]["domain_fit_score"],
            "signals": ["positive_keyword_overlap", "negative_keyword_penalty"],
        },
        "reproducibility": {
            "score": top["ranking_signals"]["reproducibility_score"],
            "signals": ["code_available", "data_available", "reproducibility_terms"],
        },
    }
    assert top["ranking_protocol"]["decision"] == "advance-candidate"
    assert any("humanoid" in reason for reason in top["ranking_protocol"]["reasons"])
    assert any("code" in reason for reason in top["ranking_protocol"]["reasons"])
    rationale = top["ranking_rationale"]
    assert rationale["schema_version"] == "paper-source-ranking-rationale-v1"
    assert rationale["recommendation"] == "advance-candidate"
    assert "low-burden reading report" in rationale["one_sentence"]
    assert rationale["user_interest_match"]["positive_keywords"] == ["humanoid", "control", "benchmark"]
    assert rationale["role_views"]["nature_sci_editor"]["lens"] == "editorial significance"
    assert rationale["role_views"]["peer_reviewer"]["lens"] == "method and evidence"
    assert rationale["role_views"]["senior_domain_researcher"]["lens"] == "theory and experiment transfer"
    assert rationale["wiki_deposition"]["suggested_pages"] == [
        "references",
        "concepts",
        "synthesis",
        "reports",
    ]


def test_rank_candidates_routes_weak_reproducibility_as_review_candidate():
    candidates = [
        {
            "slug": "interesting-no-code",
            "title": "Humanoid Control in Simulation",
            "abstract": "A robotics control method evaluated in simulation.",
            "year": 2025,
            "venue": "Workshop",
            "citation_count": 1,
            "pdf_url": "https://example.org/paper.pdf",
        }
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["humanoid", "control"],
        venue_tiers={"icra": 1.0},
        selection_policy="strict_advance",
    )

    protocol = ranked[0]["ranking_protocol"]
    assert protocol["decision"] == "review-candidate"
    assert protocol["quality_tier"] == "Tier B"
    assert ranked[0]["quality_gate"]["tier"] == "Tier B"
    assert "stable_identifier_unverified" in ranked[0]["quality_gate"]["cautions"]
    assert "weak_reproducibility_signal" in protocol["cautions"]
    assert ranked[0]["paper_type"] == "method"
    assert ranked[0]["ranking_rubric"]["dimensions"]["reproducibility"]["score"] == protocol["rubric_scores"]["reproducibility"]
    rationale = ranked[0]["ranking_rationale"]
    assert rationale["recommendation"] == "review-candidate"
    assert "review before ingest" in rationale["one_sentence"]
    assert "weak_reproducibility_signal" in rationale["review_before_ingest"]


def test_rank_candidates_balanced_policy_advances_reviewable_tier_b_candidate():
    candidates = [
        {
            "slug": "interesting-no-code",
            "title": "Humanoid Control in Simulation",
            "abstract": "A robotics control method evaluated in simulation.",
            "year": 2025,
            "venue": "Workshop",
            "citation_count": 1,
            "pdf_url": "https://example.org/paper.pdf",
        }
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["humanoid", "control"],
        venue_tiers={"icra": 1.0},
    )

    protocol = ranked[0]["ranking_protocol"]
    assert protocol["selection_policy"] == "balanced_high_quality"
    assert protocol["decision"] == "advance-candidate"
    assert protocol["quality_tier"] == "Tier B"
    assert "weak_reproducibility_signal" in protocol["cautions"]
    assert ranked[0]["ranking_rationale"]["recommendation"] == "advance-candidate"


def test_rank_candidates_penalizes_negative_profile_keywords():
    candidates = [
        {
            "slug": "profile-fit",
            "title": "Humanoid Sim2Real Control with Open Benchmarks",
            "abstract": "Humanoid robot control with benchmark ablations and open code.",
            "year": 2025,
            "venue": "ICRA",
            "citation_count": 10,
            "pdf_url": "https://example.org/fit.pdf",
            "code_url": "https://github.com/example/fit",
        },
        {
            "slug": "negative-overlap",
            "title": "Humanoid Control for Biomedical Trial Screening",
            "abstract": "Robot control benchmark with open code for a biomedical trial workflow.",
            "year": 2025,
            "venue": "ICRA",
            "citation_count": 10,
            "pdf_url": "https://example.org/negative.pdf",
            "code_url": "https://github.com/example/negative",
        },
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["humanoid", "control"],
        negative_keywords=["biomedical trial"],
        venue_tiers={"icra": 1.0},
    )

    assert [candidate["slug"] for candidate in ranked] == ["profile-fit", "negative-overlap"]
    negative = ranked[1]
    assert negative["ranking_signals"]["negative_keyword_penalty"] > 0
    assert negative["ranking_signals"]["domain_fit_score"] < ranked[0]["ranking_signals"]["domain_fit_score"]
    assert negative["quality_tier"] == "Reject"
    assert "negative_keyword_overlap" in negative["quality_gate"]["blocking_reasons"]
    assert "negative_keyword_overlap: biomedical trial" in negative["ranking_protocol"]["cautions"]
    assert negative["ranking_protocol"]["decision"] == "review-candidate"


def test_rank_candidates_uses_easyscholar_signal_for_source_confidence():
    candidates = [
        {
            "slug": "strong-venue",
            "title": "Humanoid Control with Reproducible Benchmarks",
            "abstract": "Humanoid robot control with benchmark ablations and open code.",
            "year": 2025,
            "venue": "Journal of Applied Psychology",
            "doi": "10.1234/strong-venue",
            "citation_count": 10,
            "pdf_url": "https://example.org/strong.pdf",
            "code_url": "https://github.com/example/strong",
            "verified_metrics": {
                "easyscholar": {
                    "status": "matched",
                    "publication_name": "Journal of Applied Psychology",
                    "source": "easyscholar",
                    "metrics": {"jcr_quartile": "Q1", "cas_zone_upgraded": "1", "impact_factor": "9.4"},
                    "warnings": [],
                }
            },
            "quality_signals": {
                "easyscholar": {
                    "score": 0.95,
                    "evidence": ["JCR Q1", "CAS 1", "impact_factor:9.4"],
                    "cautions": [],
                }
            },
        }
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["humanoid", "control", "benchmark"],
        venue_tiers={},
    )

    top = ranked[0]
    assert top["ranking_signals"]["easyscholar_score"] == 0.95
    assert top["ranking_signals"]["venue_score"] > 0.45
    assert "easyscholar_verified_metrics" in top["ranking_rubric"]["dimensions"]["source_confidence"]["signals"]
    assert any("EasyScholar" in reason and "JCR Q1" in reason for reason in top["ranking_protocol"]["reasons"])
    assert top["quality_gate"]["tier"] == "Tier A"


def test_rank_candidates_does_not_let_easyscholar_override_weak_topic_fit():
    candidates = [
        {
            "slug": "off-topic-strong-venue",
            "title": "Organizational Psychology Survey",
            "abstract": "A management paper about workplace behavior and organizational surveys.",
            "year": 2025,
            "venue": "Journal of Applied Psychology",
            "doi": "10.1234/off-topic",
            "citation_count": 100,
            "pdf_url": "https://example.org/off-topic.pdf",
            "quality_signals": {
                "easyscholar": {
                    "score": 1.0,
                    "evidence": ["JCR Q1", "CAS 1", "impact_factor:9.4"],
                    "cautions": [],
                }
            },
        }
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["humanoid", "robotics", "control"],
        venue_tiers={},
    )

    top = ranked[0]
    assert top["ranking_signals"]["easyscholar_score"] == 1.0
    assert top["quality_tier"] == "Reject"
    assert "weak_topic_fit" in top["quality_gate"]["blocking_reasons"]


def test_rank_candidates_does_not_dilute_cross_discipline_profile_without_hard_anchors():
    candidates = [
        {
            "slug": "drug-discovery-gnn",
            "title": "Graph Neural Network Benchmark for Drug Discovery",
            "abstract": (
                "We evaluate graph neural networks for molecular property prediction in drug discovery "
                "with benchmark comparisons and ablation studies."
            ),
            "year": 2025,
            "venue": "Bioinformatics",
            "doi": "10.1234/drug-gnn",
            "citation_count": 5,
            "pdf_url": "https://example.org/drug-gnn.pdf",
        }
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=[
            "robotics",
            "humanoid",
            "control",
            "drug discovery",
            "molecular property prediction",
            "graph neural network",
            "clinical trial",
            "ecology",
            "econometrics",
            "materials science",
            "benchmark",
            "reproducible code",
        ],
        venue_tiers={"bioinformatics": 0.75},
    )

    candidate = ranked[0]
    assert candidate["ranking_signals"]["topic_fit_basis"] == "positive_keywords_saturated"
    assert candidate["ranking_signals"]["keyword_coverage_score"] < 0.5
    assert candidate["ranking_signals"]["domain_fit_score"] >= 0.67
    assert "weak_topic_fit" not in candidate["quality_gate"]["blocking_reasons"]
    assert candidate["quality_tier"] in {"Tier A", "Tier B", "Tier C"}
    assert candidate["quality_gate"]["dimensions"]["relevance"]["status"] == "pass"


def test_configured_venue_prior_affects_order_but_does_not_create_tier_a_alone():
    current_year = date.today().year
    candidates = [
        {
            "slug": "configured-venue-only",
            "title": "AUV Control Method from Preferred Venue",
            "abstract": "Autonomous underwater vehicle control method for tracking.",
            "year": current_year,
            "venue": "Preferred Journal",
            "doi": "10.1234/preferred",
            "pdf_url": "https://example.org/preferred.pdf",
        },
        {
            "slug": "unconfigured-venue",
            "title": "AUV Control Method from Other Venue",
            "abstract": "Autonomous underwater vehicle control method for tracking.",
            "year": current_year,
            "venue": "Other Journal",
            "doi": "10.1234/other",
            "pdf_url": "https://example.org/other.pdf",
        },
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["AUV", "control", "tracking"],
        venue_tiers={"preferred journal": 0.1},
    )

    assert [candidate["slug"] for candidate in ranked] == ["configured-venue-only", "unconfigured-venue"]
    assert ranked[0]["ranking_signals"]["venue_score"] > ranked[1]["ranking_signals"]["venue_score"]
    assert ranked[0]["ranking_signals"]["venue_score_status"] == "configured_prior"
    assert ranked[0]["quality_tier"] != "Tier A"
    assert ranked[0]["ranking_protocol"]["quality_tier"] == ranked[0]["quality_tier"]


def test_normalized_citation_scoring_favors_recent_strong_evidence_over_old_absolute_count():
    current_year = date.today().year
    candidates = [
        {
            "slug": "recent-strong",
            "title": "AUV Control with Reproducible Field Benchmarks",
            "abstract": (
                "Autonomous underwater vehicle control with benchmark baselines, "
                "ablation studies, open code, and reproducible experiments."
            ),
            "year": current_year,
            "venue": "Ocean Engineering",
            "doi": "10.1234/recent",
            "citation_count": 25,
            "citation_count_status": "verified",
            "citation_count_source": "openalex",
            "pdf_url": "https://example.org/recent.pdf",
            "code_url": "https://github.com/example/recent",
        },
        {
            "slug": "old-high-citation",
            "title": "AUV Control Method with Historical Citations",
            "abstract": "Autonomous underwater vehicle control method for trajectory tracking.",
            "year": current_year - 12,
            "venue": "Ocean Engineering",
            "doi": "10.1234/old",
            "citation_count": 600,
            "citation_count_status": "verified",
            "citation_count_source": "semantic_scholar",
            "pdf_url": "https://example.org/old.pdf",
        },
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["AUV", "control", "trajectory tracking"],
        venue_tiers={"ocean engineering": 0.75},
    )

    assert [candidate["slug"] for candidate in ranked] == ["recent-strong", "old-high-citation"]
    recent_signals = ranked[0]["ranking_signals"]
    old_signals = ranked[1]["ranking_signals"]
    assert ranked[0]["citation_count"] == 25
    assert ranked[1]["citation_count"] == 600
    assert recent_signals["citation_count_raw"] == 25
    assert recent_signals["citation_count_status"] == "verified"
    assert recent_signals["citation_count_source"] == "openalex"
    assert recent_signals["citation_normalized_score"] == recent_signals["citation_score"]
    assert recent_signals["citation_score_basis"]["reference_year"] == current_year
    assert old_signals["citation_score_basis"]["publication_age_years"] >= 12
    assert recent_signals["freshness_basis"]["reference_year"] == current_year


def test_method_rigor_and_validation_evidence_change_ordering():
    current_year = date.today().year
    candidates = [
        {
            "slug": "thin-method",
            "title": "AUV Control Method",
            "abstract": "Autonomous underwater vehicle control method for trajectory tracking.",
            "year": current_year,
            "venue": "Ocean Engineering",
            "doi": "10.1234/thin",
            "citation_count": 8,
            "citation_count_status": "verified",
            "citation_count_source": "openalex",
            "pdf_url": "https://example.org/thin.pdf",
        },
        {
            "slug": "rigorous-method",
            "title": "AUV Control Method with Validation Evidence",
            "abstract": (
                "Autonomous underwater vehicle control method for trajectory tracking "
                "with baseline comparison, ablation experiment, metric reporting, and open data."
            ),
            "year": current_year,
            "venue": "Ocean Engineering",
            "doi": "10.1234/rigorous",
            "citation_count": 8,
            "citation_count_status": "verified",
            "citation_count_source": "openalex",
            "pdf_url": "https://example.org/rigorous.pdf",
        },
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["AUV", "control", "trajectory tracking"],
        venue_tiers={"ocean engineering": 0.75},
    )

    assert [candidate["slug"] for candidate in ranked] == ["rigorous-method", "thin-method"]
    assert ranked[0]["ranking_signals"]["method_rigor_score"] > ranked[1]["ranking_signals"]["method_rigor_score"]
    assert ranked[0]["quality_gate"]["dimensions"]["validation"]["score"] > ranked[1]["quality_gate"]["dimensions"]["validation"]["score"]


def test_quality_evidence_terms_can_be_injected_for_cross_discipline_validation():
    current_year = date.today().year
    candidates = [
        {
            "slug": "clinical-rigorous",
            "title": "Randomized Cohort Therapy Study with Clinical Endpoints",
            "abstract": (
                "A randomized cohort therapy study reports clinical endpoint results, "
                "hazard ratio confidence intervals, preregistered protocol, and data availability."
            ),
            "year": current_year,
            "venue": "Clinical Science",
            "doi": "10.1234/clinical",
            "citation_count": 6,
            "citation_count_status": "verified",
            "citation_count_source": "openalex",
            "pdf_url": "https://example.org/clinical.pdf",
        }
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["therapy", "clinical endpoint", "cohort"],
        venue_tiers={"clinical science": 0.75},
        quality_evidence_terms={
            "benchmark_terms": ["clinical endpoint", "hazard ratio", "confidence interval"],
            "reproducibility_terms": ["preregistered protocol", "data availability"],
            "paper_type_rules": {
                "clinical-trial": ["randomized", "cohort", "clinical endpoint"],
            },
        },
    )

    candidate = ranked[0]
    assert candidate["paper_type"] == "clinical-trial"
    assert candidate["ranking_signals"]["benchmark_score"] >= 0.67
    assert candidate["ranking_signals"]["reproducibility_terms_score"] >= 0.66
    assert candidate["quality_gate"]["dimensions"]["validation"]["status"] == "supported"
    assert "weak_benchmark_signal" not in candidate["quality_gate"]["cautions"]
    assert candidate["quality_tier"] in {"Tier A", "Tier B"}


def test_ranking_signals_distinguish_missing_citations_from_verified_zero():
    current_year = date.today().year
    ranked = rank_candidates(
        [
            {
                "slug": "missing-citations",
                "title": "AUV Control with Missing Citation Metadata",
                "abstract": "Autonomous underwater vehicle control benchmark with open code.",
                "year": current_year,
                "venue": "Ocean Engineering",
                "doi": "10.1234/missing",
                "pdf_url": "https://example.org/missing.pdf",
                "code_url": "https://github.com/example/missing",
            },
            {
                "slug": "zero-citations",
                "title": "AUV Control with Verified Zero Citations",
                "abstract": "Autonomous underwater vehicle control benchmark with open code.",
                "year": current_year,
                "venue": "Ocean Engineering",
                "doi": "10.1234/zero",
                "citation_count": 0,
                "citation_count_status": "verified",
                "citation_count_source": "openalex",
                "pdf_url": "https://example.org/zero.pdf",
                "code_url": "https://github.com/example/zero",
            },
        ],
        positive_keywords=["AUV", "control", "benchmark"],
        venue_tiers={"ocean engineering": 0.75},
    )

    by_slug = {candidate["slug"]: candidate for candidate in ranked}
    missing = by_slug["missing-citations"]["ranking_signals"]
    zero = by_slug["zero-citations"]["ranking_signals"]

    assert missing["citation_count_raw"] is None
    assert missing["citation_count_available"] is False
    assert missing["citation_count_status"] == "unverified"
    assert missing["citation_score_basis"]["status"] == "unverified"
    assert zero["citation_count_raw"] == 0
    assert zero["citation_count_available"] is True
    assert zero["citation_count_status"] == "verified"
    assert zero["citation_score_basis"]["status"] == "verified"
