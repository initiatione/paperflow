from __future__ import annotations

import json

import pytest

from paper_source.research_brief import (
    ResearchBriefValidationError,
    create_research_brief,
    load_research_brief,
    revise_research_brief,
    validate_research_brief_payload,
)


def _answers(slug="20260609-auv-current-disturbance-control", status="confirmed"):
    return {
        "status": status,
        "slug": slug,
        "title": "AUV强海流扰动控制",
        "task": "Find high-quality recent papers on AUV control under strong current disturbances.",
        "domain_scope": "AUV trajectory tracking and disturbance rejection with ocean current anchors.",
        "specific_questions": ["Which methods report real or high-fidelity current disturbance evaluation?"],
        "keywords": ["AUV", "ocean current", "disturbance rejection", "trajectory tracking"],
        "exclusions": ["acoustic communication"],
        "review_policy": {"type": "exclude"},
        "source_scope": {"type": "paper_search_mcp_default", "notes": ""},
        "output_goal": {"type": "reading_priority_list", "notes": ""},
        "unknowns": ["venue_prior"],
        "field_sources": {
            "task": "user_confirmed",
            "domain_scope": "user_confirmed",
            "review_policy.type": "brief_default",
            "output_goal.type": "user_confirmed",
        },
    }


def test_create_research_brief_writes_managed_artifacts(tmp_path):
    result = create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")

    brief_dir = tmp_path / "_paper_source" / "research-briefs" / "20260609-auv-current-disturbance-control"
    assert result["brief_dir"] == str(brief_dir)
    assert (brief_dir / "research-brief.json").exists()
    assert (brief_dir / "research-brief.md").read_text(encoding="utf-8").startswith("# AUV强海流扰动控制")
    assert "Research Brief" in (brief_dir / "agent-brief.md").read_text(encoding="utf-8")
    assert (brief_dir / "revisions").is_dir()

    payload = json.loads((brief_dir / "research-brief.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper-source-research-brief-v1"
    assert payload["revision_number"] == 1
    assert payload["status"] == "confirmed"
    assert payload["created_at"] == "2026-06-09T12:00:00Z"
    assert result["hash"] == payload["content_hash"]


def test_slug_validation_rejects_unsafe_names(tmp_path):
    with pytest.raises(ResearchBriefValidationError, match="slug"):
        create_research_brief(tmp_path, _answers(slug="../bad"), now="2026-06-09T12:00:00Z")


def test_validate_requires_minimum_complete_fields():
    payload = _answers()
    payload["task"] = ""
    with pytest.raises(ResearchBriefValidationError, match="task"):
        validate_research_brief_payload(payload)


def test_draft_is_valid_but_not_formal_use_eligible(tmp_path):
    result = create_research_brief(tmp_path, _answers(status="draft"), now="2026-06-09T12:00:00Z")
    loaded = load_research_brief(result["json_path"])
    assert loaded["payload"]["status"] == "draft"
    assert loaded["formal_use_eligible"] is False


def test_confirmed_revision_preserves_prior_json_snapshot(tmp_path):
    created = create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")
    revised = _answers()
    revised["task"] = "Find AUV current-disturbance control papers with field trials."

    result = revise_research_brief(created["json_path"], revised, now="2026-06-09T13:00:00Z")

    payload = json.loads((tmp_path / "_paper_source" / "research-briefs" / revised["slug"] / "research-brief.json").read_text(encoding="utf-8"))
    snapshots = sorted((tmp_path / "_paper_source" / "research-briefs" / revised["slug"] / "revisions").glob("*-research-brief.json"))
    assert payload["revision_number"] == 2
    assert payload["supersedes_hash"] == created["hash"]
    assert len(snapshots) == 1
