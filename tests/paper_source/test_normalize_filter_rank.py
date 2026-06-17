from paper_source.filter_candidates import (
    default_discovery_exclusion_terms,
    exclusion_terms_from_query,
    filter_candidates,
    filter_candidates_with_report,
)
from paper_source.normalize_candidates import normalize_candidates
from paper_source.rank_papers import rank_candidates


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


def test_normalize_candidates_prefers_direct_pdf_over_doi_landing_url():
    raw_records = [
        {
            "source": "semantic",
            "title": "AUV Reinforcement Learning Control",
            "authors": ["A. Researcher"],
            "year": 2025,
            "doi": "10.1000/auv-rl",
            "pdf_url": "https://doi.org/10.1000/auv-rl",
            "citation_count": 5,
        },
        {
            "source": "openalex",
            "title": "AUV Reinforcement Learning Control",
            "authors": ["A. Researcher"],
            "year": 2025,
            "doi": "10.1000/auv-rl",
            "pdf_url": "https://example.org/articles/auv-rl.pdf",
            "citation_count": 7,
        },
    ]

    normalized = normalize_candidates(raw_records)

    assert len(normalized) == 1
    assert normalized[0]["pdf_url"] == "https://example.org/articles/auv-rl.pdf"
    assert normalized[0]["pdf_urls"] == [
        "https://example.org/articles/auv-rl.pdf",
        "https://doi.org/10.1000/auv-rl",
    ]


def test_normalize_candidates_enriches_arxiv_doi_and_code_url_from_metadata():
    normalized = normalize_candidates(
        [
            {
                "source": "arxiv",
                "title": "EROAS: 3D Efficient Reactive Obstacle Avoidance System",
                "authors": ["A. Researcher"],
                "year": 2024,
                "arxiv_id": "2411.05516v3",
                "pdf_url": "https://arxiv.org/pdf/2411.05516v3",
                "abstract": (
                    "AUV obstacle avoidance with hardware-in-the-loop experiments. "
                    "Code: https://github.com/AIRLabIISc/EROAS"
                ),
            }
        ]
    )

    assert normalized[0]["doi"] == "10.48550/arXiv.2411.05516"
    assert normalized[0]["doi_source"] == "arxiv_id:arxiv_id"
    assert normalized[0]["code_url"] == "https://github.com/AIRLabIISc/EROAS"
    assert normalized[0]["code_url_source"] == "abstract"


def test_normalize_candidates_enriches_doi_from_raw_url_metadata():
    normalized = normalize_candidates(
        [
            {
                "source": "openalex",
                "title": "Exact DOI From Raw URL",
                "authors": ["A. Researcher"],
                "year": 2025,
                "raw_record": {
                    "ids": {"doi": "https://doi.org/10.48550/arxiv.2501.12345"},
                    "primary_location": {"landing_page_url": "https://arxiv.org/abs/2501.12345"},
                },
            }
        ]
    )

    assert normalized[0]["doi"] == "10.48550/arxiv.2501.12345"
    assert normalized[0]["doi_source"] == "raw_record.ids.doi"


def test_normalize_candidates_preserves_alternate_sources_and_pdf_urls_for_deduped_records():
    raw_records = [
        {
            "source": "crossref",
            "title": "Exact AUV Control Paper",
            "authors": ["A. Researcher"],
            "year": 2024,
            "doi": "10.1016/j.oceaneng.2024.119432",
            "pdf_url": "https://doi.org/10.1016/j.oceaneng.2024.119432",
            "citation_count": 3,
            "raw_record": {"source": "crossref", "paper_id": "10.1016/j.oceaneng.2024.119432"},
        },
        {
            "source": "unpaywall",
            "title": "Exact AUV Control Paper",
            "authors": ["A. Researcher"],
            "year": 2024,
            "doi": "10.1016/j.oceaneng.2024.119432",
            "pdf_url": "https://repository.example/auv-control.pdf",
            "citation_count": 1,
            "raw_record": {
                "source": "unpaywall",
                "paper_id": "10.1016/j.oceaneng.2024.119432",
                "pdf_url": "https://mirror.example/auv-control.pdf",
            },
        },
    ]

    normalized = normalize_candidates(raw_records)

    assert len(normalized) == 1
    assert normalized[0]["sources"] == ["crossref", "unpaywall"]
    assert normalized[0]["alternate_sources"] == [
        {"source": "crossref", "paper_id": "10.1016/j.oceaneng.2024.119432"},
        {"source": "unpaywall", "paper_id": "10.1016/j.oceaneng.2024.119432"},
    ]
    assert normalized[0]["pdf_urls"] == [
        "https://repository.example/auv-control.pdf",
        "https://mirror.example/auv-control.pdf",
        "https://doi.org/10.1016/j.oceaneng.2024.119432",
    ]
    assert normalized[0]["alternate_pdf_urls"] == [
        {"source": "unpaywall", "url": "https://repository.example/auv-control.pdf"},
        {"source": "unpaywall", "url": "https://mirror.example/auv-control.pdf"},
        {"source": "crossref", "url": "https://doi.org/10.1016/j.oceaneng.2024.119432"},
    ]
    assert len(normalized[0]["raw_records"]) == 2


def test_normalize_candidates_merges_grok_with_paper_search_priority():
    raw_records = [
        {
            "source": "grok_search",
            "provider": "grok_search",
            "title": "Noisy Grok Title",
            "authors": ["Wrong Author"],
            "year": 2023,
            "venue": "Web",
            "abstract": "Noisy snippet.",
            "doi": "10.1000/merge",
            "pdf_url": "https://publisher.example/merge.pdf",
            "landing_page_url": "https://publisher.example/merge",
        },
        {
            "source": "semantic",
            "provider": "paper_search",
            "title": "Authoritative Paper Search Title",
            "authors": ["A. Researcher"],
            "year": 2025,
            "venue": "ICRA",
            "abstract": "Authoritative abstract.",
            "doi": "10.1000/merge",
        },
    ]

    normalized = normalize_candidates(raw_records)

    assert len(normalized) == 1
    assert normalized[0]["title"] == "Authoritative Paper Search Title"
    assert normalized[0]["authors"] == ["A. Researcher"]
    assert normalized[0]["year"] == 2025
    assert normalized[0]["venue"] == "ICRA"
    assert normalized[0]["abstract"] == "Authoritative abstract."
    assert normalized[0]["pdf_url"] == "https://publisher.example/merge.pdf"
    assert normalized[0]["landing_page_url"] == "https://publisher.example/merge"
    assert normalized[0]["provider_provenance"] == ["grok_search", "paper_search"]
    assert normalized[0]["provenance_label"] == "both_providers"
    assert normalized[0]["citation_count_source"] is None
    assert normalized[0]["citation_count_status"] == "unverified"


def test_normalize_candidates_preserves_citation_count_source_provenance():
    normalized = normalize_candidates(
        [
            {
                "source": "crossref",
                "title": "AUV Attitude Control",
                "doi": "10.1000/auv",
                "citation_count": 12,
            },
            {
                "source": "openalex",
                "title": "AUV Attitude Control",
                "doi": "10.1000/auv",
                "citation_count": 55,
            },
        ]
    )

    assert normalized[0]["citation_count"] == 55
    assert normalized[0]["citation_count_source"] == "openalex"
    assert normalized[0]["citation_count_status"] == "verified"
    assert normalized[0]["citation_count_sources"] == [
        {"source": "openalex", "count": 55},
        {"source": "crossref", "count": 12},
    ]


def test_normalize_candidates_treats_provider_zero_citations_as_verified():
    normalized = normalize_candidates(
        [
            {
                "source": "openalex",
                "title": "New AUV Attitude Control",
                "doi": "10.1000/new-auv-zero",
                "citation_count": 0,
            },
            {
                "source": "semantic",
                "title": "New AUV Attitude Control",
                "doi": "10.1000/new-auv-zero",
            },
        ]
    )

    assert normalized[0]["citation_count"] == 0
    assert normalized[0]["citation_count_source"] == "openalex"
    assert normalized[0]["citation_count_status"] == "verified"
    assert normalized[0]["citation_count_sources"] == [{"source": "openalex", "count": 0}]


def test_normalize_candidates_labels_grok_only_as_anchor_required_supplemental():
    normalized = normalize_candidates(
        [
            {
                "source": "grok_search",
                "provider": "grok_search",
                "title": "Supplemental Publisher Paper",
                "doi": "10.1000/supplemental",
                "landing_page_url": "https://publisher.example/supplemental",
            }
        ]
    )

    assert normalized[0]["provider_provenance"] == ["grok_search"]
    assert normalized[0]["provenance_label"] == "grok_only_with_paper_search_anchor"


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


def test_filter_candidates_applies_request_year_and_code_requirements():
    candidates = [
        {
            "title": "Recent AUV Attitude Control with Code",
            "abstract": "Autonomous underwater vehicle attitude control with experiments.",
            "year": 2025,
            "pdf_url": "https://example.org/recent.pdf",
            "code_url": "https://github.com/example/auv-control",
        },
        {
            "title": "Old AUV Attitude Control with Code",
            "abstract": "Autonomous underwater vehicle attitude control with experiments.",
            "year": 2019,
            "pdf_url": "https://example.org/old.pdf",
            "code_url": "https://github.com/example/old-auv-control",
        },
        {
            "title": "Recent AUV Attitude Control without Code",
            "abstract": "Autonomous underwater vehicle attitude control with experiments.",
            "year": 2025,
            "pdf_url": "https://example.org/no-code.pdf",
        },
    ]

    report = filter_candidates_with_report(
        candidates,
        domains=["AUV", "autonomous underwater vehicle"],
        require_pdf=True,
        year_min=2021,
        code_policy="require",
    )

    assert [candidate["title"] for candidate in report["kept"]] == ["Recent AUV Attitude Control with Code"]
    rejected = {candidate["title"]: candidate["filter_reasons"] for candidate in report["rejected"]}
    assert rejected["Old AUV Attitude Control with Code"] == ["year_before:2021"]
    assert rejected["Recent AUV Attitude Control without Code"] == ["missing_code"]


def test_rank_candidates_records_request_constraints_and_prefers_code_when_requested():
    candidates = [
        {
            "title": "AUV Attitude Control with Public Code",
            "abstract": "Autonomous underwater vehicle attitude control with reproducible experiments.",
            "year": 2024,
            "venue": "Ocean Engineering",
            "pdf_url": "https://example.org/code.pdf",
            "code_url": "https://github.com/example/auv-code",
            "citation_count": 5,
        },
        {
            "title": "AUV Attitude Control without Public Code",
            "abstract": "Autonomous underwater vehicle attitude control with reproducible experiments.",
            "year": 2024,
            "venue": "Ocean Engineering",
            "pdf_url": "https://example.org/no-code.pdf",
            "citation_count": 5,
        },
    ]

    ranked = rank_candidates(
        candidates,
        positive_keywords=["AUV", "attitude control"],
        venue_tiers={"ocean engineering": 0.8},
        year_min=2021,
        code_policy="prefer",
    )

    assert ranked[0]["title"] == "AUV Attitude Control with Public Code"
    assert ranked[0]["ranking_signals"]["year_min"] == 2021
    assert ranked[0]["ranking_signals"]["code_policy"] == "prefer"


def test_rank_candidates_uses_priority_keywords_to_avoid_profile_dilution_for_narrow_topic():
    ranked = rank_candidates(
        [
            {
                "title": "Adaptive Integral Sliding Mode Control for Attitude Tracking of Underwater Robots",
                "abstract": (
                    "This paper studies underwater robot attitude control with large range pitch variations, "
                    "simultaneous roll and yaw control, experiments, comparison studies, and Lyapunov analysis."
                ),
                "year": 2024,
                "venue": "IEEE Robotics and Automation Letters",
                "doi": "10.1109/LRA.2024.3515733",
                "pdf_url": "https://arxiv.org/pdf/2405.00269v1",
                "citation_count": 18,
            }
        ],
        positive_keywords=[
            "robot control",
            "embodied intelligence",
            "reinforcement learning",
            "learning-based control",
            "sim-to-real",
            "real robot",
            "field trial",
            "sea trial",
            "benchmark",
            "reproducible code",
            "AUV",
            "underwater robot",
            "attitude control",
            "yaw",
            "pitch",
            "roll",
            "sliding mode control",
        ],
        priority_keywords=["underwater robot", "attitude control", "yaw", "pitch", "roll", "sliding mode control"],
        venue_tiers={},
        selection_policy="broad_map",
    )

    candidate = ranked[0]
    assert candidate["ranking_signals"]["priority_topic_score"] >= 0.8
    assert "weak_topic_fit" not in candidate["quality_gate"]["blocking_reasons"]
    assert candidate["quality_tier"] in {"Tier A", "Tier B"}
    assert candidate["ranking_protocol"]["decision"] == "advance-candidate"


def test_filter_candidates_does_not_treat_surveying_as_survey_paper():
    candidates = [
        {
            "title": "Toward 6-DOF Autonomous Underwater Vehicle Energy-Aware Position Control",
            "abstract": (
                "Autonomous underwater vehicles are used for surveying and mapping. "
                "This paper proposes deep reinforcement learning for AUV position control."
            ),
            "pdf_url": "https://example.org/auv.pdf",
        }
    ]

    report = filter_candidates_with_report(
        candidates,
        domains=["AUV"],
        require_pdf=True,
        exclude_terms=["review", "survey", "systematic review"],
    )

    assert [item["title"] for item in report["kept"]] == [
        "Toward 6-DOF Autonomous Underwater Vehicle Energy-Aware Position Control"
    ]
    assert report["rejected"] == []


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
