import json

import pytest

from epi.artifacts import review_root, reviews_root
from epi.fetch_plan import build_fetch_plan
from epi.review_sessions import (
    build_review_signature,
    create_or_update_review_session,
    find_matching_review_session,
    load_review_session_for_resume,
    rehydrate_search_record_from_review,
)


def _signature_inputs():
    return {
        "query": "robotics navigation control",
        "query_plan": {
            "domain": "profile-derived",
            "query_variants": [
                "robotics navigation control -review -survey",
                "mobile robot control navigation -review -survey",
            ],
        },
        "requested_sources": ["arxiv", "semantic"],
        "effective_sources": ["arxiv", "semantic"],
        "source_routing": {"selected_sources": ["arxiv", "semantic"]},
        "max_results": 5,
        "profile": "robotics_ai_control",
        "domains": ["robotics", "control"],
        "positive_keywords": ["navigation"],
        "negative_keywords": ["survey"],
        "venue_prior": {"IROS": 2.0},
        "use_query_plan": True,
        "query_plan_domain": "auto",
        "query_plan_max_queries": 6,
        "enable_easyscholar": True,
    }


def _search_record():
    return {
        "source_mode": "fixture",
        "query_strategy": "query_plan_multi_query",
        "records": [
            {
                "source": "fixture",
                "title": "Robot Navigation Control",
                "authors": ["A. Researcher"],
                "year": 2025,
                "venue": "IROS",
                "abstract": "robotics navigation control",
                "pdf_url": "https://example.org/paper.pdf",
                "citation_count": 7,
            }
        ],
        "query_records": [
            {
                "index": 1,
                "query": "robotics navigation control -review -survey",
                "source_mode": "fixture",
                "record_count": 1,
                "upstream": {"source_results": {"fixture": 1}, "raw_total": 1},
            }
        ],
        "warnings": [],
        "upstream": {"source_results": {"fixture": 1}, "raw_total": 1},
    }


def _create_session(vault, signature=None):
    signature = signature or build_review_signature(_signature_inputs())
    ranked = [{"slug": "robot-navigation-control", "title": "Robot Navigation Control", "doi": "10.1000/robot"}]
    return create_or_update_review_session(
        vault,
        topic="robotics navigation control",
        signature=signature,
        query_plan=_signature_inputs()["query_plan"],
        search_record=_search_record(),
        normalized=_search_record()["records"],
        filter_report={"kept": ranked, "rejected": []},
        easyscholar_record={"enabled": False, "summary": {"disabled": 1}},
        ranked_pool=ranked,
        accepted=ranked,
        coverage={"sources_used": ["fixture"], "raw_total": 1, "deduped_total": 1},
        run_id="run-001",
        refreshed=False,
    )


def test_review_signature_is_stable_and_ignores_timestamps():
    first = build_review_signature({**_signature_inputs(), "created_at": "one"})
    second = build_review_signature({**_signature_inputs(), "created_at": "two"})
    changed = build_review_signature({**_signature_inputs(), "max_results": 10})

    assert first["signature"] == second["signature"]
    assert first["signature"] != changed["signature"]
    assert first["signature_inputs"]["query"] == "robotics navigation control"
    assert "created_at" not in first["signature_inputs"]


def test_review_session_writes_state_and_artifacts(tmp_path):
    vault = tmp_path / "vault"
    session = _create_session(vault)

    root = review_root(vault, session["review_id"])
    assert reviews_root(vault).is_dir()
    assert (root / "state.json").is_file()
    assert (root / "query-plan.json").is_file()
    assert (root / "candidates.json").is_file()
    assert (root / "shortlist.json").is_file()
    assert (root / "fetch_plan.json").is_file()
    assert (root / "coverage.json").is_file()
    assert (root / "provider-cache" / "query-01.json").is_file()
    assert (root / "runs" / "run-001.json").is_file()
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state["schema_version"] == "epi-review-session-v1"
    assert state["phase"] == "ranked"
    assert state["resume_count"] == 0
    assert state["refresh_count"] == 0
    assert state["candidate_counts"]["accepted"] == 1
    fetch_plan = json.loads((root / "fetch_plan.json").read_text(encoding="utf-8"))
    assert fetch_plan["items"][0]["slug"] == "robot-navigation-control"
    assert fetch_plan["items"][0]["doi"] == "10.1000/robot"


def test_find_matching_review_session_and_rehydrate_search_record(tmp_path):
    vault = tmp_path / "vault"
    signature = build_review_signature(_signature_inputs())
    session = _create_session(vault, signature)

    found = find_matching_review_session(vault, signature["signature"])
    assert found["review_id"] == session["review_id"]
    loaded = load_review_session_for_resume(vault, signature["signature"])
    assert loaded["state"]["review_id"] == session["review_id"]
    search_record = rehydrate_search_record_from_review(loaded)
    assert search_record["resumed"] is True
    assert search_record["provider_call_skipped"] is True
    assert search_record["records"][0]["title"] == "Robot Navigation Control"


def test_provider_cache_can_rebuild_candidates_when_candidates_json_missing(tmp_path):
    vault = tmp_path / "vault"
    signature = build_review_signature(_signature_inputs())
    session = _create_session(vault, signature)
    root = review_root(vault, session["review_id"])
    (root / "candidates.json").unlink()

    loaded = load_review_session_for_resume(vault, signature["signature"])
    assert loaded["resume_phase"] == "provider-cache"
    rebuilt = rehydrate_search_record_from_review(loaded)
    assert rebuilt["records"][0]["title"] == "Robot Navigation Control"
    assert rebuilt["provider_call_skipped"] is True


def test_corrupt_review_state_requires_refresh(tmp_path):
    vault = tmp_path / "vault"
    signature = build_review_signature(_signature_inputs())
    session = _create_session(vault, signature)
    (review_root(vault, session["review_id"]) / "shortlist.json").write_text("{bad json", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupt review session"):
        load_review_session_for_resume(vault, signature["signature"])


def test_build_fetch_plan_preserves_pdf_and_manual_links():
    ranked = [
        {
            "slug": "manual-paper",
            "title": "Manual Paper",
            "doi": "10.1000/manual",
            "arxiv_id": "2501.12345",
            "pdf_url": "https://example.org/main.pdf",
            "pdf_urls": ["https://example.org/main.pdf"],
            "alternate_pdf_urls": [{"source": "semantic", "url": "https://example.org/alt.pdf"}],
            "raw_records": [{"source": "arxiv", "paper_id": "2501.12345"}],
        }
    ]

    plan = build_fetch_plan(ranked)

    assert plan["schema_version"] == "epi-fetch-plan-v1"
    assert plan["items"][0]["slug"] == "manual-paper"
    assert plan["items"][0]["candidate_pdf_urls"] == [
        "https://example.org/main.pdf",
        "https://example.org/alt.pdf",
    ]
    assert plan["items"][0]["source_identities"] == [{"source": "arxiv", "paper_id": "2501.12345"}]
    assert plan["items"][0]["manual_download"]["doi_url"] == "https://doi.org/10.1000/manual"
