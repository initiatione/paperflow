from epi.rank_papers import rank_candidates


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
    assert top["paper_classification"]["schema_version"] == "epi-paper-classification-v1"
    assert top["ranking_rubric"]["schema_version"] == "epi-ranking-rubric-v1"
    assert set(top["ranking_rubric"]["dimensions"]) == {
        "relevance",
        "method_rigor",
        "evidence_sufficiency",
        "reproducibility",
        "source_confidence",
    }
    assert top["ranking_confidence"] == top["ranking_rubric"]["ranking_confidence"]
    assert top["ranking_protocol"]["schema_version"] == "epi-ranking-protocol-v1"
    assert top["ranking_protocol"]["paper_type"] == "benchmark"
    assert top["ranking_protocol"]["classification_confidence"] == top["classification_confidence"]
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
    assert rationale["schema_version"] == "epi-ranking-rationale-v1"
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
    )

    protocol = ranked[0]["ranking_protocol"]
    assert protocol["decision"] == "review-candidate"
    assert "weak_reproducibility_signal" in protocol["cautions"]
    assert ranked[0]["paper_type"] == "method"
    assert ranked[0]["ranking_rubric"]["dimensions"]["reproducibility"]["score"] == protocol["rubric_scores"]["reproducibility"]
    rationale = ranked[0]["ranking_rationale"]
    assert rationale["recommendation"] == "review-candidate"
    assert "review before ingest" in rationale["one_sentence"]
    assert "weak_reproducibility_signal" in rationale["review_before_ingest"]


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
    assert "negative_keyword_overlap: biomedical trial" in negative["ranking_protocol"]["cautions"]
    assert negative["ranking_protocol"]["decision"] == "review-candidate"
