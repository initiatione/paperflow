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
            "signals": ["citation_signal", "benchmark_signal", "pdf_available"],
        },
        "domain_fit": {
            "score": top["ranking_signals"]["domain_fit_score"],
            "signals": ["positive_keyword_overlap", "negative_keyword_penalty"],
        },
        "reproducibility": {
            "score": top["ranking_signals"]["reproducibility_score"],
            "signals": ["code_available", "reproducibility_terms"],
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
