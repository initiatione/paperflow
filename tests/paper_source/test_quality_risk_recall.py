from paper_source.quality_risk_recall import (
    annotate_recall_expansion_candidates,
    build_recall_gap_record,
    enrich_candidates_with_quality_risk,
)
from paper_source.rank_papers import rank_candidates
from paper_source.recommendation_output import build_session_recommendations


def test_recall_gap_record_extracts_provider_official_version():
    seed = {
        "slug": "seed-conference-version",
        "title": "Robotics Control Conference Version",
        "year": 2024,
        "venue": "Workshop",
        "doi": "10.1000/seed",
        "pdf_url": "https://example.org/seed.pdf",
        "abstract": "Robotics control benchmark study.",
        "raw_records": [
            {
                "source": "semantic",
                "provider": "paper_search",
                "official_version": {
                    "source": "crossref",
                    "title": "Robotics Control Journal Version",
                    "year": 2025,
                    "venue": "Journal of Robotics",
                    "doi": "10.1000/journal",
                    "pdf_url": "https://example.org/journal.pdf",
                    "abstract": "Robotics control journal version with field experiments and code.",
                    "citation_count": 30,
                },
            }
        ],
    }

    record = build_recall_gap_record([seed])

    assert record["schema_version"] == "paper-source-recall-gap-record-v1"
    assert record["summary"]["recovered"] == 1
    assert record["attempts"][0]["expansion_kind"] == "official_version"
    assert record["expansion_records"][0]["title"] == "Robotics Control Journal Version"
    assert record["expansion_records"][0]["recall_expansion"]["source_candidate"]["slug"] == "seed-conference-version"


def test_annotate_recall_expansion_candidates_preserves_auditable_evidence():
    seed = {
        "slug": "seed",
        "title": "Seed Paper",
        "doi": "10.1000/seed",
        "raw_records": [
            {
                "source": "semantic",
                "related_papers": [
                    {
                        "source": "semantic",
                        "title": "Recovered Related Robotics Paper",
                        "doi": "10.1000/related",
                    }
                ],
            }
        ],
    }
    record = build_recall_gap_record([seed])

    annotated = annotate_recall_expansion_candidates(
        [{"title": "Recovered Related Robotics Paper", "doi": "10.1000/related"}],
        record,
    )

    expansion = annotated[0]["recall_expansion"]
    assert expansion["schema_version"] == "paper-source-recall-expansion-v1"
    assert expansion["expansion_kind"] == "related_paper"
    assert expansion["evidence"][0]["source_field"] == "raw_records[0].related_papers"


def test_quality_risk_enrichment_marks_verified_and_missing_data():
    enriched, record = enrich_candidates_with_quality_risk(
        [
            {
                "slug": "retracted-paper",
                "title": "Retracted Robotics Control",
                "doi": "10.1000/retracted",
                "raw_records": [{"source": "crossref", "retracted": True}],
            },
            {
                "slug": "missing-risk-paper",
                "title": "Ordinary Robotics Control",
                "doi": "10.1000/ordinary",
                "raw_records": [{"source": "semantic"}],
            },
        ]
    )

    by_slug = {item["slug"]: item for item in enriched}
    assert by_slug["retracted-paper"]["quality_risk"]["status"] == "verified"
    assert by_slug["retracted-paper"]["quality_risk"]["severity"] == "severe"
    assert by_slug["retracted-paper"]["quality_risk"]["risk_types"] == ["retracted"]
    assert by_slug["missing-risk-paper"]["quality_risk"]["status"] == "unverified"
    assert by_slug["missing-risk-paper"]["quality_risk"]["cautions"] == ["quality_risk_unverified"]
    assert record["summary"]["verified"] == 1
    assert record["summary"]["unverified"] == 1


def test_rank_candidates_lowers_verified_severe_risk_but_not_missing_risk():
    candidates, _ = enrich_candidates_with_quality_risk(
        [
            {
                "slug": "risky",
                "title": "Robotics Control With Field Experiments",
                "year": 2025,
                "venue": "ICRA",
                "abstract": "Robotics control benchmark field experiments with code.",
                "doi": "10.1000/risky",
                "pdf_url": "https://example.org/risky.pdf",
                "code_url": "https://github.com/example/risky",
                "citation_count": 50,
                "citation_count_status": "verified",
                "citation_count_source": "semantic",
                "raw_records": [{"source": "crossref", "withdrawn": True}],
            },
            {
                "slug": "unverified-risk",
                "title": "Robotics Control With Field Experiments",
                "year": 2025,
                "venue": "ICRA",
                "abstract": "Robotics control benchmark field experiments with code.",
                "doi": "10.1000/unverified",
                "pdf_url": "https://example.org/unverified.pdf",
                "code_url": "https://github.com/example/unverified",
                "citation_count": 50,
                "citation_count_status": "verified",
                "citation_count_source": "semantic",
                "raw_records": [{"source": "semantic"}],
            },
        ]
    )

    ranked = rank_candidates(
        candidates,
        positive_keywords=["robotics", "control"],
        venue_tiers={"icra": 1.0},
        priority_keywords=["robotics", "control"],
    )
    by_slug = {item["slug"]: item for item in ranked}

    assert by_slug["risky"]["quality_tier"] == "Reject"
    assert by_slug["risky"]["ranking_protocol"]["decision"] == "review-candidate"
    assert "verified_quality_risk" in by_slug["risky"]["quality_gate"]["blocking_reasons"]
    assert by_slug["risky"]["quality_gate"]["dimensions"]["quality_risk"]["status"] == "verified_severe"
    assert by_slug["unverified-risk"]["quality_gate"]["dimensions"]["quality_risk"]["status"] == "unverified"
    assert by_slug["unverified-risk"]["quality_risk"]["schema_version"] == "paper-source-quality-risk-v1"
    assert "verified_quality_risk" not in by_slug["unverified-risk"]["quality_gate"]["blocking_reasons"]


def test_session_recommendations_expose_quality_risk_warnings():
    candidates, _ = enrich_candidates_with_quality_risk(
        [
            {
                "slug": "unverified-risk",
                "title": "Robotics Control With Field Experiments",
                "year": 2025,
                "venue": "ICRA",
                "abstract": "Robotics control benchmark field experiments with code.",
                "doi": "10.1000/unverified",
                "pdf_url": "https://example.org/unverified.pdf",
                "code_url": "https://github.com/example/unverified",
                "citation_count": 50,
                "citation_count_status": "verified",
                "citation_count_source": "semantic",
                "raw_records": [{"source": "semantic"}],
            }
        ]
    )
    ranked = rank_candidates(
        candidates,
        positive_keywords=["robotics", "control"],
        venue_tiers={"icra": 1.0},
        priority_keywords=["robotics", "control"],
    )

    session = build_session_recommendations(ranked, [])

    item = session["primary_recommendations"][0]
    assert item["quality_risk"]["schema_version"] == "paper-source-quality-risk-v1"
    assert item["quality_risk"]["status"] == "unverified"
    assert "quality_risk_unverified" in item["verification_warnings"]
    assert session["verification_summary"]["quality_risk"]["unverified"] == 1
