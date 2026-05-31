from epi.filter_candidates import (
    default_discovery_exclusion_terms,
    exclusion_terms_from_query,
    filter_candidates,
    filter_candidates_with_report,
)
from epi.normalize_candidates import normalize_candidates
from epi.rank_papers import rank_candidates


def test_normalize_filter_rank_keeps_relevant_pdf_candidate():
    raw_records = [
        {
            "source": "semantic_scholar",
            "title": "Learning Agile Humanoid Motion Control",
            "authors": ["A. Researcher"],
            "year": 2025,
            "venue": "ICRA",
            "abstract": "Robot learning for humanoid motion control with reproducible experiments.",
            "doi": "10.1000/example",
            "pdf_url": "https://example.org/paper.pdf",
            "citation_count": 42,
            "code_url": "https://github.com/example/code",
        },
        {
            "source": "openalex",
            "title": "Learning Agile Humanoid Motion Control",
            "authors": ["A. Researcher"],
            "year": 2025,
            "venue": "ICRA",
            "abstract": "Robot learning for humanoid motion control with reproducible experiments.",
            "doi": "10.1000/example",
            "pdf_url": "https://example.org/paper.pdf",
            "citation_count": 40,
        },
    ]

    normalized = normalize_candidates(raw_records)
    filtered = filter_candidates(normalized, domains=["robotics", "control"], require_pdf=True)
    ranked = rank_candidates(filtered, positive_keywords=["humanoid", "control"], venue_tiers={"icra": 1.0})

    assert len(normalized) == 1
    assert filtered[0]["filter_status"] == "kept"
    assert ranked[0]["score"] > 0.75
    assert ranked[0]["sources"] == ["openalex", "semantic_scholar"]


def test_filter_candidates_can_hard_exclude_reviews_when_requested():
    candidates = [
        {
            "title": "AUV Trajectory Tracking: A Systematic Review",
            "abstract": "This review summarizes autonomous underwater vehicle controllers.",
            "pdf_url": "https://example.org/review.pdf",
        },
        {
            "title": "Safety-Critical RL Control for an AUV",
            "abstract": "A method paper with simulation experiments for trajectory tracking.",
            "pdf_url": "https://example.org/method.pdf",
        },
    ]

    exclude_terms = exclusion_terms_from_query("AUV reinforcement learning control -review -survey")
    report = filter_candidates_with_report(
        candidates,
        domains=["control"],
        require_pdf=True,
        exclude_terms=exclude_terms,
    )

    assert [item["title"] for item in report["kept"]] == ["Safety-Critical RL Control for an AUV"]
    assert report["rejected"][0]["filter_reasons"] == ["excluded_terms:review,systematic review"]


def test_filter_candidates_matches_domain_anchors_across_method_words():
    candidates = [
        {
            "title": "AUV Reinforcement Learning Control: A Systematic Review",
            "abstract": "This systematic review surveys autonomous underwater vehicle control.",
            "pdf_url": "https://example.org/review.pdf",
        }
    ]

    report = filter_candidates_with_report(
        candidates,
        domains=["auv control"],
        require_pdf=True,
        exclude_terms=[],
    )

    assert report["kept"][0]["title"] == "AUV Reinforcement Learning Control: A Systematic Review"


def test_exclusion_terms_from_query_accepts_chinese_review_request():
    terms = exclusion_terms_from_query("AUV 结合 RL AI 控制方向论文，这次不找综述类型论文")

    assert "review" in terms
    assert "systematic review" in terms


def test_default_discovery_exclusion_terms_skip_reviews_unless_requested():
    default_terms = default_discovery_exclusion_terms("latest high quality AUV reinforcement learning control papers")
    review_terms = default_discovery_exclusion_terms("latest survey papers about AUV reinforcement learning control")

    assert "review" in default_terms
    assert "survey" in default_terms
    assert "meta-analysis" in default_terms
    assert review_terms == []


def test_default_discovery_exclusion_terms_treat_not_review_as_non_review_discovery():
    terms = default_discovery_exclusion_terms("latest high quality AUV control papers not review")

    assert "review" in terms
    assert "survey" in terms
    assert "meta-analysis" in terms
