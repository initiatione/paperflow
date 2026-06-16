from paper_source.auto_staging import build_auto_staging_plan, merge_auto_staging_status
from paper_source.recommendation_output import build_session_recommendations


def _candidate(
    slug,
    title,
    *,
    pdf_url="https://example.org/paper.pdf",
    paper_type="research-article",
    decision="advance-candidate",
    doi="10.1000/example",
    url=None,
):
    candidate = {
        "slug": slug,
        "title": title,
        "score": 0.9,
        "abstract": f"{title} original abstract.",
        "quality_tier": "Tier A",
        "ranking_protocol": {"decision": decision},
        "ranking_rationale": {"one_sentence": f"{title} is worth staging."},
        "paper_type": paper_type,
    }
    if pdf_url is not None:
        candidate["pdf_url"] = pdf_url
    if doi is not None:
        candidate["doi"] = doi
    if url is not None:
        candidate["url"] = url
    return candidate


def test_auto_staging_plan_caps_primary_pdf_candidates_and_review_survey_slot():
    ranked = [
        _candidate("research-1", "Research 1"),
        _candidate("review-1", "Review 1", paper_type="review"),
        _candidate("survey-1", "Survey 1", paper_type="survey"),
        _candidate(
            "needs-pdf",
            "Needs PDF",
            pdf_url=None,
            doi="10.1000/needs-pdf",
            url="https://publisher.example/needs-pdf",
        )
        | {"staging_readiness": "needs_pdf", "readiness_reasons": ["missing_pdf"]},
        _candidate("research-2", "Research 2"),
        _candidate("research-3", "Research 3"),
    ]
    session = build_session_recommendations(ranked, [])

    plan = build_auto_staging_plan(ranked, session)

    assert [item["slug"] for item in plan["selected"]] == ["research-1", "review-1", "research-2"]
    assert plan["counts"]["selected"] == 3
    assert plan["counts"]["skipped_by_reason"] == {
        "auto_limit_reached": 1,
        "needs_manual_pdf": 1,
        "review_survey_cap": 1,
    }
    skipped = {item["slug"]: item for item in plan["skipped"]}
    assert skipped["survey-1"]["auto_staging_status"] == "skipped_review_survey_cap"
    assert skipped["needs-pdf"]["auto_staging_status"] == "skipped_needs_manual_pdf"
    assert {"kind": "doi", "url": "https://doi.org/10.1000/needs-pdf"} in skipped["needs-pdf"][
        "manual_download_links"
    ]
    assert {"kind": "stable_url", "url": "https://publisher.example/needs-pdf"} in skipped["needs-pdf"][
        "manual_download_links"
    ]


def test_auto_staging_plan_lifts_review_survey_slot_only_when_requested():
    ranked = [
        _candidate("research-1", "Research 1"),
        _candidate("review-1", "Review 1", paper_type="review"),
        _candidate("survey-1", "Survey 1", paper_type="survey"),
        _candidate("research-2", "Research 2"),
    ]
    session = build_session_recommendations(ranked, [])

    plan = build_auto_staging_plan(ranked, session, review_survey_requested=True)

    assert [item["slug"] for item in plan["selected"]] == ["research-1", "review-1", "survey-1"]
    assert plan["review_survey_limit"] is None
    assert plan["counts"]["skipped_by_reason"] == {"auto_limit_reached": 1}


def test_auto_staging_plan_uses_only_primary_recommendations_and_skips_existing():
    ranked = [
        _candidate("primary", "Primary"),
        _candidate("appendix", "Appendix", decision="review-candidate"),
    ]
    session = build_session_recommendations(ranked, [])

    plan = build_auto_staging_plan(ranked, session, skip_existing_slugs={"primary"})

    assert plan["selected"] == []
    assert plan["counts"]["primary_total"] == 1
    assert plan["skipped"] == [
        {
            "slug": "primary",
            "title": "Primary",
            "reason": "already_source_staged",
            "pdf_status": "available",
            "auto_staging_status": "skipped_already_source_staged",
        }
    ]


def test_merge_auto_staging_status_uses_execution_results_over_plan_status():
    ranked = [
        _candidate("research-1", "Research 1"),
        _candidate("needs-pdf", "Needs PDF", pdf_url=None, url="https://publisher.example/needs-pdf")
        | {"staging_readiness": "needs_pdf", "readiness_reasons": ["missing_pdf"]},
    ]
    session = build_session_recommendations(ranked, [])
    plan = build_auto_staging_plan(ranked, session)

    merged = merge_auto_staging_status(
        session,
        plan,
        execution_results=[{"paper_slug": "research-1", "state": "staged"}],
    )

    statuses = {item["slug"]: item["auto_staging_status"] for item in merged["primary_recommendations"]}
    assert statuses == {
        "research-1": "staged",
        "needs-pdf": "skipped_needs_manual_pdf",
    }
