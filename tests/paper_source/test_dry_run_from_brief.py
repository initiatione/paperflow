from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_source.cli_parser import build_parser
from paper_source.orchestrator import run_dry_run
from paper_source.query_planner import build_query_plan_from_research_brief
from paper_source.research_brief import create_research_brief


ROOT = Path(__file__).resolve().parents[2]


def _write_minimal_plugin_template(plugin_root: Path) -> None:
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "  - control\n"
        "positive_keywords:\n"
        "  - navigation\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )


def _answers(slug: str = "20260609-auv-current-disturbance-control", status: str = "confirmed") -> dict:
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


def _fixture(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "AUV Current Disturbance Rejection Control",
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "venue": "Ocean Engineering",
                    "abstract": "AUV trajectory tracking under ocean current disturbance with benchmark.",
                    "pdf_url": "https://example.org/auv.pdf",
                    "citation_count": 7,
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_dry_run_parser_accepts_from_brief_and_rejects_query_mix(tmp_path):
    parser = build_parser()

    args = parser.parse_args(["dry-run", "--from-brief", str(tmp_path / "research-brief.json")])
    assert args.from_brief == tmp_path / "research-brief.json"
    assert args.query is None
    assert args.allow_draft_brief is False

    with pytest.raises(SystemExit):
        parser.parse_args(["dry-run", "--query", "AUV control", "--from-brief", str(tmp_path / "research-brief.json")])


def test_query_planner_maps_research_brief_as_current_intent_over_profile():
    plan = build_query_plan_from_research_brief(
        {
            "slug": "20260609-aircraft-control-reviews",
            "status": "confirmed",
            "revision_number": 1,
            "task": "Find papers on aircraft control reviews",
            "domain_scope": "fixed-wing aircraft fault-tolerant control",
            "specific_questions": ["Which papers compare real flight experiments?"],
            "keywords": ["fault-tolerant control", "flight experiment"],
            "exclusions": ["AUV"],
            "review_policy": {"type": "include"},
            "source_scope": {"type": "paper_search_mcp_default"},
            "output_goal": {"type": "literature_review_seed"},
        },
        profile="auv_control",
        domains=["AUV", "underwater robot"],
        positive_keywords=["ocean current"],
        negative_keywords=["acoustic communication"],
        venue_prior=[],
        max_queries=4,
    )

    assert plan["topic"] == "Find papers on aircraft control reviews"
    assert plan["domain"] == "research-brief"
    assert plan["concept_blocks"]["domain_terms"][0] == "fixed-wing aircraft fault-tolerant control"
    assert "AUV" in plan["concept_blocks"]["exclusions"]
    assert all("-review -survey" not in query for query in plan["query_variants"])
    assert plan["research_brief"]["output_goal"] == "literature_review_seed"
    assert plan["research_brief"]["precedence"] == "brief_overrides_profile"


def test_dry_run_from_confirmed_brief_records_metadata_and_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(tmp_path / "missing-runtime.json"))
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    brief = create_research_brief(tmp_path / "vault", _answers(), now="2026-06-09T12:00:00Z")

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query=None,
        from_brief=Path(brief["json_path"]),
        max_results=3,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        resume=False,
    )

    state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    assert state["research_brief"]["slug"] == "20260609-auv-current-disturbance-control"
    assert state["research_brief"]["hash"] == brief["hash"]
    assert state["input_artifact_hashes"]["research-brief.json"] == brief["hash"]
    assert report["discovery_context"]["research_brief"]["revision_number"] == 1
    assert search_record["research_brief"]["status"] == "confirmed"


def test_dry_run_from_draft_brief_requires_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(tmp_path / "missing-runtime.json"))
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    brief = create_research_brief(tmp_path / "vault", _answers(status="draft"), now="2026-06-09T12:00:00Z")

    with pytest.raises(ValueError, match="draft"):
        run_dry_run(
            plugin_root=plugin_root,
            vault_path=tmp_path / "vault",
            query=None,
            from_brief=Path(brief["json_path"]),
            max_results=3,
            fixture_path=_fixture(tmp_path / "fixture.json"),
            resume=False,
        )


def test_brief_hash_changes_review_signature_and_prevents_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(tmp_path / "missing-runtime.json"))
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    first = create_research_brief(tmp_path / "vault", _answers(), now="2026-06-09T12:00:00Z")
    second_answers = _answers(slug="20260609-auv-current-sea-trials")
    second_answers["task"] = "Find AUV current disturbance control papers with sea trials."
    second = create_research_brief(tmp_path / "vault", second_answers, now="2026-06-09T13:00:00Z")

    first_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query=None,
        from_brief=Path(first["json_path"]),
        max_results=3,
        fixture_path=_fixture(tmp_path / "fixture-one.json"),
        resume=True,
    )
    second_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query=None,
        from_brief=Path(second["json_path"]),
        max_results=3,
        fixture_path=_fixture(tmp_path / "fixture-two.json"),
        resume=True,
    )

    first_state = json.loads((first_run / "run-state.json").read_text(encoding="utf-8"))
    second_state = json.loads((second_run / "run-state.json").read_text(encoding="utf-8"))
    assert first_state["review_session"]["review_id"] != second_state["review_session"]["review_id"]
    assert second_state["review_session"]["resumed"] is False
