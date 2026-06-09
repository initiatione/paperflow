from __future__ import annotations

import json
import re
from pathlib import Path

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


def _rewrite_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _json_path(result):
    return Path(result["json_path"])


def test_create_research_brief_writes_managed_artifacts(tmp_path):
    result = create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")

    brief_dir = tmp_path / "_paper_source" / "research-briefs" / "20260609-auv-current-disturbance-control"
    assert result["brief_dir"] == str(brief_dir)
    assert (brief_dir / "research-brief.json").exists()
    research_brief_markdown = (brief_dir / "research-brief.md").read_text(encoding="utf-8")
    agent_brief_markdown = (brief_dir / "agent-brief.md").read_text(encoding="utf-8")
    assert research_brief_markdown.startswith("# AUV强海流扰动控制")
    assert "状态：" in research_brief_markdown
    assert "## 任务" in research_brief_markdown
    assert "## 领域范围" in research_brief_markdown
    assert "## 具体问题" in research_brief_markdown
    assert "## 关键词" in research_brief_markdown
    assert "## 策略" in research_brief_markdown
    assert not re.search(
        r"(?m)^(Status:|## Task$|## Domain Scope$|## Specific Questions$|## Keywords$|## Policy$)",
        research_brief_markdown,
    )
    assert "Research Brief" in agent_brief_markdown
    assert (brief_dir / "revisions").is_dir()

    payload = json.loads((brief_dir / "research-brief.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper-source-research-brief-v1"
    assert payload["revision_number"] == 1
    assert payload["status"] == "confirmed"
    assert payload["created_at"] == "2026-06-09T12:00:00Z"
    assert result["hash"] == payload["content_hash"]


def test_create_research_brief_rejects_duplicate_slug(tmp_path):
    create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")

    with pytest.raises(ResearchBriefValidationError, match="already exists"):
        create_research_brief(tmp_path, _answers(), now="2026-06-09T13:00:00Z")


def test_slug_validation_rejects_unsafe_names(tmp_path):
    with pytest.raises(ResearchBriefValidationError, match="slug"):
        create_research_brief(tmp_path, _answers(slug="../bad"), now="2026-06-09T12:00:00Z")


def test_slug_validation_requires_yyyymmdd_prefix(tmp_path):
    with pytest.raises(ResearchBriefValidationError, match="YYYYMMDD"):
        create_research_brief(tmp_path, _answers(slug="auv-current-disturbance-control"), now="2026-06-09T12:00:00Z")


def test_slug_validation_rejects_double_hyphen_separators(tmp_path):
    with pytest.raises(ResearchBriefValidationError, match="single hyphen"):
        create_research_brief(tmp_path, _answers(slug="20260609-auv--current"), now="2026-06-09T12:00:00Z")


def test_validate_requires_minimum_complete_fields():
    payload = _answers()
    payload["task"] = ""
    with pytest.raises(ResearchBriefValidationError, match="task"):
        validate_research_brief_payload(payload)


def test_default_load_rejects_draft_but_allow_draft_loads_metadata(tmp_path):
    result = create_research_brief(tmp_path, _answers(status="draft"), now="2026-06-09T12:00:00Z")

    with pytest.raises(ResearchBriefValidationError, match="allow_draft"):
        load_research_brief(result["json_path"])

    loaded = load_research_brief(result["json_path"], allow_draft=True)
    assert loaded["payload"]["status"] == "draft"
    assert loaded["formal_use_eligible"] is False


def test_load_research_brief_rejects_missing_schema_version(tmp_path):
    result = create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")
    json_path = _json_path(result)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload.pop("schema_version")
    _rewrite_json(json_path, payload)

    with pytest.raises(ResearchBriefValidationError, match="schema_version"):
        load_research_brief(json_path)


def test_load_research_brief_rejects_missing_or_tampered_content_hash(tmp_path):
    missing = create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")
    missing_path = _json_path(missing)
    missing_payload = json.loads(missing_path.read_text(encoding="utf-8"))
    missing_payload.pop("content_hash")
    _rewrite_json(missing_path, missing_payload)

    with pytest.raises(ResearchBriefValidationError, match="content_hash"):
        load_research_brief(missing_path)

    tampered = create_research_brief(
        tmp_path,
        _answers(slug="20260609-auv-hash-tamper"),
        now="2026-06-09T13:00:00Z",
    )
    tampered_path = _json_path(tampered)
    tampered_payload = json.loads(tampered_path.read_text(encoding="utf-8"))
    tampered_payload["task"] = "Tampered after hashing."
    _rewrite_json(tampered_path, tampered_payload)

    with pytest.raises(ResearchBriefValidationError, match="content_hash"):
        load_research_brief(tampered_path)


def test_confirmed_revision_preserves_prior_json_snapshot(tmp_path):
    created = create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")
    prior_payload = json.loads(_json_path(created).read_text(encoding="utf-8"))
    revised = _answers()
    revised["task"] = "Find AUV current-disturbance control papers with field trials."

    result = revise_research_brief(created["json_path"], revised, now="2026-06-09T13:00:00Z")

    payload = json.loads((tmp_path / "_paper_source" / "research-briefs" / revised["slug"] / "research-brief.json").read_text(encoding="utf-8"))
    snapshots = sorted((tmp_path / "_paper_source" / "research-briefs" / revised["slug"] / "revisions").glob("*-research-brief.json"))
    assert payload["revision_number"] == 2
    assert payload["supersedes_hash"] == created["hash"]
    assert len(snapshots) == 1
    snapshot_payload = json.loads(snapshots[0].read_text(encoding="utf-8"))
    assert snapshot_payload == prior_payload
    assert snapshot_payload["content_hash"] == created["hash"]
