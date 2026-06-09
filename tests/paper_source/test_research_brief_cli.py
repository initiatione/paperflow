from __future__ import annotations

import json
from pathlib import Path

from paper_source import cli
from paper_source.cli import build_parser
from paper_source.research_brief import create_research_brief


def _answers(slug="20260609-auv-current-disturbance-control", status="confirmed"):
    return {
        "status": status,
        "slug": slug,
        "title": "AUV strong-current disturbance control",
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


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_research_brief_parser_accepts_create_validate_and_list(tmp_path):
    parser = build_parser()

    create_args = parser.parse_args(
        [
            "research-brief",
            "create",
            "--answers-json",
            str(tmp_path / "answers.json"),
            "--vault",
            str(tmp_path / "vault"),
            "--json",
        ]
    )
    validate_args = parser.parse_args(
        [
            "research-brief",
            "validate",
            "--brief",
            str(tmp_path / "research-brief.json"),
            "--json",
        ]
    )
    list_args = parser.parse_args(
        [
            "research-brief",
            "list",
            "--vault",
            str(tmp_path / "vault"),
            "--json",
        ]
    )

    assert create_args.command == "research-brief"
    assert create_args.research_brief_action == "create"
    assert create_args.answers_json.name == "answers.json"
    assert create_args.vault == tmp_path / "vault"
    assert create_args.json is True
    assert validate_args.command == "research-brief"
    assert validate_args.research_brief_action == "validate"
    assert validate_args.brief.name == "research-brief.json"
    assert validate_args.json is True
    assert list_args.command == "research-brief"
    assert list_args.research_brief_action == "list"
    assert list_args.vault == tmp_path / "vault"
    assert list_args.json is True


def test_research_brief_create_json_outputs_artifact_paths(tmp_path, capsys):
    answers_path = _write_json(tmp_path / "answers.json", _answers())

    exit_code = cli.main(
        [
            "research-brief",
            "create",
            "--answers-json",
            str(answers_path),
            "--vault",
            str(tmp_path),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["brief_slug"] == "20260609-auv-current-disturbance-control"
    assert payload["status"] == "confirmed"
    assert payload["revision_number"] == 1
    assert payload["hash"]
    assert payload["json_path"].endswith("research-brief.json")
    assert payload["markdown_path"].endswith("research-brief.md")
    assert payload["agent_brief_path"].endswith("agent-brief.md")
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()
    assert Path(payload["agent_brief_path"]).exists()


def test_research_brief_list_json_returns_compact_entries_without_keywords(tmp_path, capsys):
    create_research_brief(tmp_path, _answers(), now="2026-06-09T12:00:00Z")
    create_research_brief(
        tmp_path,
        _answers(slug="20260609-auv-draft-brief", status="draft"),
        now="2026-06-09T13:00:00Z",
    )

    exit_code = cli.main(["research-brief", "list", "--vault", str(tmp_path), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["errors"] == []
    assert [entry["brief_slug"] for entry in payload["briefs"]] == [
        "20260609-auv-current-disturbance-control",
        "20260609-auv-draft-brief",
    ]
    for entry in payload["briefs"]:
        assert set(entry) == {
            "brief_slug",
            "status",
            "title",
            "task",
            "created_at",
            "updated_at",
            "revision_number",
            "last_used_at",
            "path",
        }
        assert entry["last_used_at"] is None
        assert "keywords" not in entry
        assert "constraints" not in entry
        assert "provenance" not in entry


def test_research_brief_validate_returns_invalid_json_and_exit_code_for_bad_payload(tmp_path, capsys):
    brief_path = _write_json(
        tmp_path / "research-brief.json",
        {
            "schema_version": "paper-source-research-brief-v1",
            "status": "confirmed",
            "slug": "not-a-valid-persisted-brief",
        },
    )

    exit_code = cli.main(["research-brief", "validate", "--brief", str(brief_path), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["valid"] is False
    assert payload["brief_slug"] is None
    assert payload["status"] == "confirmed"
    assert payload["revision_number"] is None
    assert payload["path"] == str(brief_path)
    assert payload["hash"] is None
    assert payload["errors"]


def test_research_brief_validate_accepts_draft_artifact_without_formal_use(tmp_path, capsys):
    result = create_research_brief(
        tmp_path,
        _answers(slug="20260609-auv-draft-brief", status="draft"),
        now="2026-06-09T12:00:00Z",
    )

    exit_code = cli.main(["research-brief", "validate", "--brief", result["json_path"], "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["brief_slug"] == "20260609-auv-draft-brief"
    assert payload["status"] == "draft"
    assert payload["revision_number"] == 1
    assert payload["path"] == result["json_path"]
    assert payload["hash"] == result["hash"]
    assert payload["errors"] == []
