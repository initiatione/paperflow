import argparse
import importlib

import pytest

from paper_source import cli
from paper_source.cli import build_parser


def _parser_commands(parser):
    subparser_action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    return set(subparser_action.choices)


def test_cli_build_parser_is_reexported_from_parser_module():
    cli_parser = importlib.import_module("paper_source.cli_parser")

    assert cli.build_parser is cli_parser.build_parser
    assert build_parser is cli_parser.build_parser


def test_cli_parser_commands_match_route_registry():
    cli_parser = importlib.import_module("paper_source.cli_parser")
    cli_routes = importlib.import_module("paper_source.cli_routes")

    assert _parser_commands(cli_parser.build_parser()) == set(cli_routes.COMMAND_ROUTES)


def test_cli_routes_dispatches_to_registered_handler():
    cli_routes = importlib.import_module("paper_source.cli_routes")
    calls = []

    def fixture_handler(args):
        calls.append(args)
        return 23

    args = argparse.Namespace(command="fixture")

    assert cli_routes.dispatch(args, {"fixture": fixture_handler}) == 23
    assert calls == [args]


def test_dry_run_parser_defaults_to_query_plan_and_accepts_overrides():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--query-plan-domain",
            "profile",
            "--query-plan-max-queries",
            "8",
        ]
    )

    assert args.command == "dry-run"
    assert args.no_query_plan is False
    assert args.query_plan_domain == "profile"
    assert args.query_plan_max_queries == 8


def test_dry_run_parser_rejects_fixed_discipline_query_plan_domains():
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "dry-run",
                "--query",
                "AUV reinforcement learning control",
                "--query-plan-domain",
                "auv-control",
            ]
        )


def test_dry_run_parser_accepts_agent_supplied_query_variants_and_focus_terms():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "水下机器人 AUV 姿态控制 的 现代控制方向 或是 结合RL做的尽可能有公开代码的论文，近5年",
            "--query-variant",
            '"autonomous underwater vehicle" "attitude control" "model predictive control" -review -survey',
            "--query-variant",
            'AUV "attitude control" "reinforcement learning" code -review -survey',
            "--domain-focus-term",
            "AUV",
            "--domain-focus-term",
            "autonomous underwater vehicle,underwater robot",
            "--agent-query-plan-json",
            "agent-plan.json",
            "--year-min",
            "2021",
            "--code-policy",
            "prefer",
        ]
    )

    assert args.command == "dry-run"
    assert args.query_variant == [
        '"autonomous underwater vehicle" "attitude control" "model predictive control" -review -survey',
        'AUV "attitude control" "reinforcement learning" code -review -survey',
    ]
    assert args.domain_focus_term == ["AUV", "autonomous underwater vehicle,underwater robot"]
    assert str(args.agent_query_plan_json) == "agent-plan.json"
    assert args.year_min == 2021
    assert args.code_policy == "prefer"


def test_dry_run_parser_accepts_selection_policy():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--selection-policy",
            "strict_advance",
        ]
    )

    assert args.selection_policy == "strict_advance"


def test_dry_run_parser_accepts_json_output():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--json",
        ]
    )

    assert args.command == "dry-run"
    assert args.json is True


def test_dry_run_parser_accepts_no_easyscholar_override():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--no-easyscholar",
        ]
    )

    assert args.command == "dry-run"
    assert args.no_easyscholar is True


def test_dry_run_cli_json_outputs_run_artifact_paths(tmp_path, monkeypatch, capsys):
    run_dir = tmp_path / "_paper_source" / "runs" / "run-json-001"
    run_dir.mkdir(parents=True)
    for name in [
        "query-plan.json",
        "search-record.json",
        "rank.json",
        "report.md",
        "report.json",
        "run-state.json",
    ]:
        (run_dir / name).write_text("{}", encoding="utf-8")
    captured = {}

    def fake_run_dry_run(**kwargs):
        captured.update(kwargs)
        return run_dir

    monkeypatch.setattr(cli.workflows, "run_dry_run", fake_run_dry_run)

    exit_code = cli.main(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--vault",
            str(tmp_path),
            "--json",
        ]
    )

    output = capsys.readouterr().out
    payload = __import__("json").loads(output)
    assert exit_code == 0
    assert payload["run_id"] == "run-json-001"
    assert payload["run_dir"] == str(run_dir)
    assert payload["artifacts"]["query_plan"] == str(run_dir / "query-plan.json")
    assert payload["artifacts"]["rank"] == str(run_dir / "rank.json")
    assert captured["query"] == "AUV reinforcement learning control"
    assert captured["use_query_plan"] is True
    assert captured["query_variants"] is None
    assert captured["domain_focus_terms"] is None
    assert captured["enable_easyscholar"] is True


def test_dry_run_cli_passes_agent_supplied_query_inputs_to_workflow(tmp_path, monkeypatch):
    run_dir = tmp_path / "_paper_source" / "runs" / "run-json-001"
    run_dir.mkdir(parents=True)
    captured = {}

    def fake_run_dry_run(**kwargs):
        captured.update(kwargs)
        return run_dir

    monkeypatch.setattr(cli.workflows, "run_dry_run", fake_run_dry_run)

    exit_code = cli.main(
        [
            "dry-run",
            "--query",
            "natural language topic",
            "--vault",
            str(tmp_path),
            "--query-variant",
            '"domain object" "task" method -review -survey',
            "--query-variant",
            '"domain object" "task" code -review -survey',
            "--domain-focus-term",
            "domain object",
            "--agent-query-plan-json",
            str(tmp_path / "agent-query-plan.json"),
            "--year-min",
            "2021",
            "--code-policy",
            "require",
        ]
    )

    assert exit_code == 0
    assert captured["query_variants"] == [
        '"domain object" "task" method -review -survey',
        '"domain object" "task" code -review -survey',
    ]
    assert captured["domain_focus_terms"] == ["domain object"]
    assert captured["agent_query_plan_json"] == tmp_path / "agent-query-plan.json"
    assert captured["year_min"] == 2021
    assert captured["code_policy"] == "require"


def test_dry_run_cli_passes_no_easyscholar_to_workflow(tmp_path, monkeypatch):
    run_dir = tmp_path / "_paper_source" / "runs" / "run-json-001"
    run_dir.mkdir(parents=True)
    captured = {}

    def fake_run_dry_run(**kwargs):
        captured.update(kwargs)
        return run_dir

    monkeypatch.setattr(cli.workflows, "run_dry_run", fake_run_dry_run)

    exit_code = cli.main(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--vault",
            str(tmp_path),
            "--no-easyscholar",
        ]
    )

    assert exit_code == 0
    assert captured["enable_easyscholar"] is False


def test_dry_run_parser_accepts_refresh_and_no_resume_as_exclusive_options():
    refresh_args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--refresh",
        ]
    )
    no_resume_args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--no-resume",
        ]
    )

    assert refresh_args.refresh is True
    assert refresh_args.no_resume is False
    assert no_resume_args.refresh is False
    assert no_resume_args.no_resume is True


def test_dry_run_parser_rejects_refresh_with_no_resume():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "dry-run",
                "--query",
                "robotics control",
                "--refresh",
                "--no-resume",
            ]
        )


def test_dry_run_cli_passes_resume_and_refresh_flags(tmp_path, monkeypatch):
    run_dir = tmp_path / "_paper_source" / "runs" / "run-json-001"
    run_dir.mkdir(parents=True)
    captured = {}

    def fake_run_dry_run(**kwargs):
        captured.update(kwargs)
        return run_dir

    monkeypatch.setattr(cli.workflows, "run_dry_run", fake_run_dry_run)

    exit_code = cli.main(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--vault",
            str(tmp_path),
            "--refresh",
        ]
    )

    assert exit_code == 0
    assert captured["resume"] is True
    assert captured["refresh"] is True


def test_dry_run_cli_json_includes_review_artifacts_when_present(tmp_path, monkeypatch, capsys):
    run_dir = tmp_path / "_paper_source" / "runs" / "run-json-001"
    run_dir.mkdir(parents=True)
    for name in ["search-record.json", "rank.json", "report.md", "report.json", "run-state.json"]:
        (run_dir / name).write_text("{}", encoding="utf-8")
    review_dir = tmp_path / "_paper_source" / "reviews" / "robotics-abc"
    review_dir.mkdir(parents=True)
    for name in ["state.json", "candidates.json", "shortlist.json", "fetch_plan.json", "coverage.json"]:
        (review_dir / name).write_text("{}", encoding="utf-8")
    (run_dir / "run-state.json").write_text(
        __import__("json").dumps(
            {
                "review_session": {
                    "review_id": "robotics-abc",
                    "review_dir": str(review_dir),
                    "resumed": True,
                    "refreshed": False,
                    "provider_call_skipped": True,
                    "artifacts": {
                        "state": str(review_dir / "state.json"),
                        "candidates": str(review_dir / "candidates.json"),
                        "shortlist": str(review_dir / "shortlist.json"),
                        "fetch_plan": str(review_dir / "fetch_plan.json"),
                        "coverage": str(review_dir / "coverage.json"),
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run_dry_run(**kwargs):
        return run_dir

    monkeypatch.setattr(cli.workflows, "run_dry_run", fake_run_dry_run)

    exit_code = cli.main(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--vault",
            str(tmp_path),
            "--json",
        ]
    )

    payload = __import__("json").loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["review"]["review_id"] == "robotics-abc"
    assert payload["review"]["provider_call_skipped"] is True
    assert payload["review"]["artifacts"]["fetch_plan"] == str(review_dir / "fetch_plan.json")



def test_dry_run_parser_accepts_profile_derived_query_plan_domain():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "molecular property prediction",
            "--query-plan-domain",
            "profile",
        ]
    )

    assert args.command == "dry-run"
    assert args.query_plan_domain == "profile"


def test_dry_run_parser_accepts_no_query_plan_fallback():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--no-query-plan",
        ]
    )

    assert args.command == "dry-run"
    assert args.no_query_plan is True


def test_advance_ranked_parser_accepts_include_review_candidates():
    args = build_parser().parse_args(
        [
            "advance-ranked",
            "--run-id",
            "run-001",
            "--include-review-candidates",
        ]
    )

    assert args.command == "advance-ranked"
    assert args.run_id == "run-001"
    assert args.include_review_candidates is True


def test_prepare_ranked_parser_defaults_to_one_paper_and_source_staging():
    args = build_parser().parse_args(
        [
            "prepare-ranked",
            "--run-id",
            "run-001",
        ]
    )

    assert args.command == "prepare-ranked"
    assert args.run_id == "run-001"
    assert args.max_papers == 1
    assert args.include_review_candidates is False
    assert args.skip_existing is False
    assert args.mode == "fast-ingest"


def test_prepare_ranked_parser_accepts_skip_existing_for_resumable_batches():
    args = build_parser().parse_args(
        [
            "prepare-ranked",
            "--run-id",
            "run-001",
            "--max-papers",
            "10",
            "--skip-existing",
        ]
    )

    assert args.command == "prepare-ranked"
    assert args.max_papers == 10
    assert args.skip_existing is True


def test_prepare_ranked_parser_accepts_json_output():
    args = build_parser().parse_args(
        [
            "prepare-ranked",
            "--run-id",
            "run-001",
            "--json",
        ]
    )

    assert args.command == "prepare-ranked"
    assert args.json is True


def test_mineru_timeout_flag_accepted_on_parse_and_batch_commands_and_defaults_to_none():
    parser = build_parser()
    default_parse = parser.parse_args(["parse-paper", "--slug", "fixture-paper"])
    assert default_parse.mineru_timeout is None

    for command in ("advance-paper", "advance-batch", "advance-ranked", "prepare-ranked", "parse-paper"):
        if command == "advance-paper":
            argv = [command, "--candidate", "candidate.json", "--mineru-timeout", "120"]
        elif command == "advance-batch":
            argv = [command, "--candidates", "candidates.json", "--mineru-timeout", "120"]
        elif command == "parse-paper":
            argv = [command, "--slug", "fixture-paper", "--mineru-timeout", "120"]
        else:
            argv = [command, "--run-id", "run-001", "--mineru-timeout", "120"]
        args = build_parser().parse_args(argv)
        assert args.command == command
        assert args.mineru_timeout == 120


def test_prepare_ranked_cli_json_outputs_run_artifact_paths(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_prepare_ranked_papers_from_run(
        vault,
        run_id,
        *,
        mineru_command=None,
        max_papers=None,
        include_review_candidates=False,
        skip_existing=False,
        mineru_timeout=None,
        workflow_mode=None,
        selection_policy=None,
    ):
        captured.update(
            {
                "vault": vault,
                "run_id": run_id,
                "mineru_command": mineru_command,
                "max_papers": max_papers,
                "include_review_candidates": include_review_candidates,
                "skip_existing": skip_existing,
                "mineru_timeout": mineru_timeout,
                "workflow_mode": workflow_mode,
                "selection_policy": selection_policy,
            }
        )
        return {
            "run_id": "prepare-ranked-001",
            "source_run_id": run_id,
            "state": "prepared",
            "status": "waiting_for_human_gate",
            "workflow_mode": "fast-ingest",
            "processed_count": 2,
            "skipped_count": 1,
            "stops_after": "source-staging",
        }

    monkeypatch.setattr(cli.workflows, "prepare_ranked_papers_from_run", fake_prepare_ranked_papers_from_run)

    exit_code = cli.main(
        [
            "prepare-ranked",
            "--run-id",
            "run-001",
            "--vault",
            str(tmp_path),
            "--max-papers",
            "10",
            "--skip-existing",
            "--include-review-candidates",
            "--json",
        ]
    )

    output = capsys.readouterr().out
    payload = __import__("json").loads(output)
    run_dir = tmp_path / "_paper_source" / "runs" / "prepare-ranked-001"
    assert exit_code == 0
    assert payload["run_id"] == "prepare-ranked-001"
    assert payload["source_run_id"] == "run-001"
    assert payload["batch_state"] == "prepared"
    assert payload["status"] == "waiting_for_human_gate"
    assert payload["workflow_mode"] == "fast-ingest"
    assert payload["selection_policy"] == "balanced_high_quality"
    assert payload["processed_count"] == 2
    assert payload["skipped_count"] == 1
    assert payload["stops_after"] == "source-staging"
    assert payload["run_dir"] == str(run_dir)
    assert payload["artifacts"]["batch_record"] == str(run_dir / "batch-advance-record.json")
    assert payload["artifacts"]["report_json"] == str(run_dir / "report.json")
    assert captured["skip_existing"] is True
    assert captured["include_review_candidates"] is True
    assert captured["workflow_mode"] == "fast-ingest"
    assert captured["selection_policy"] == "balanced_high_quality"


def test_prepare_ranked_cli_passes_skip_existing_to_workflow(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_prepare_ranked_papers_from_run(
        vault,
        run_id,
        *,
        mineru_command=None,
        max_papers=None,
        include_review_candidates=False,
        skip_existing=False,
        mineru_timeout=None,
        workflow_mode=None,
        selection_policy=None,
    ):
        captured.update(
            {
                "vault": vault,
                "run_id": run_id,
                "mineru_command": mineru_command,
                "max_papers": max_papers,
                "include_review_candidates": include_review_candidates,
                "skip_existing": skip_existing,
                "mineru_timeout": mineru_timeout,
                "workflow_mode": workflow_mode,
                "selection_policy": selection_policy,
            }
        )
        return {
            "run_id": "prepare-ranked-001",
            "state": "prepared",
            "workflow_mode": "reviewed-ingest",
            "processed_count": 0,
            "stops_after": "source-staging",
        }

    monkeypatch.setattr(cli.workflows, "prepare_ranked_papers_from_run", fake_prepare_ranked_papers_from_run)

    exit_code = cli.main(
        [
            "prepare-ranked",
            "--run-id",
            "run-001",
            "--vault",
            str(tmp_path),
            "--max-papers",
            "10",
            "--skip-existing",
            "--include-review-candidates",
            "--mode",
            "reviewed-ingest",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "vault": tmp_path,
        "run_id": "run-001",
        "mineru_command": None,
        "max_papers": 10,
        "include_review_candidates": True,
        "skip_existing": True,
        "mineru_timeout": None,
        "workflow_mode": "reviewed-ingest",
        "selection_policy": "balanced_high_quality",
    }
    output = capsys.readouterr().out
    assert "workflow_mode=reviewed-ingest" in output
    assert "stops_after=source-staging" in output


def test_discover_to_handoff_cli_outputs_safe_handoff_record(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_discover_to_handoff(**kwargs):
        captured.update(kwargs)
        return {
            "run_id": "discover-to-handoff-001",
            "source_run_id": "dry-run-001",
            "prepare_run_id": "prepare-ranked-001",
            "status": "waiting_for_human_gate",
            "state": "handoff_prepared",
            "selection_policy": "code_preferred",
            "stops_after": "source-staging",
            "compiled_wiki_write": False,
            "human_approval_written": False,
            "paper_wiki_invoked": False,
            "processed_count": 1,
            "skipped_count": 0,
            "prepared_papers": [
                {
                    "slug": "fixture-paper",
                    "state": "staged",
                    "next_action": "run-wiki-ingest-agent",
                    "wiki_ingest_brief": str(tmp_path / "_paper_source" / "staging" / "papers" / "fixture-paper" / "wiki-ingest-brief.json"),
                }
            ],
            "manual_downloads": [],
            "artifacts": {"discovery": {}, "prepare": {}},
            "exit_status": 0,
        }

    monkeypatch.setattr(cli.workflows, "discover_to_handoff", fake_discover_to_handoff)

    exit_code = cli.main(
        [
            "discover-to-handoff",
            "--query",
            "natural language topic",
            "--vault",
            str(tmp_path),
            "--query-variant",
            '"domain object" "task" -review -survey',
            "--domain-focus-term",
            "domain object",
            "--selection-policy",
            "code_preferred",
            "--max-papers",
            "2",
            "--no-skip-existing",
            "--json",
        ]
    )

    payload = __import__("json").loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["run_id"] == "discover-to-handoff-001"
    assert payload["source_run_id"] == "dry-run-001"
    assert payload["prepare_run_id"] == "prepare-ranked-001"
    assert payload["compiled_wiki_write"] is False
    assert payload["human_approval_written"] is False
    assert payload["paper_wiki_invoked"] is False
    assert captured["query"] == "natural language topic"
    assert captured["query_variants"] == ['"domain object" "task" -review -survey']
    assert captured["domain_focus_terms"] == ["domain object"]
    assert captured["selection_policy"] == "code_preferred"
    assert captured["max_papers"] == 2
    assert captured["skip_existing"] is False


def test_discover_papers_parser_accepts_discovery_and_auto_staging_options():
    args = build_parser().parse_args(
        [
            "discover-papers",
            "--query",
            "AUV attitude control recent papers",
            "--query-variant",
            '"AUV" "attitude control" "model predictive control"',
            "--domain-focus-term",
            "AUV",
            "--code-policy",
            "prefer",
            "--selection-policy",
            "code_preferred",
            "--max-results",
            "20",
            "--max-auto-stage",
            "2",
            "--review-survey-requested",
            "--no-skip-existing",
            "--json",
        ]
    )

    assert args.command == "discover-papers"
    assert args.query == "AUV attitude control recent papers"
    assert args.query_variant == ['"AUV" "attitude control" "model predictive control"']
    assert args.domain_focus_term == ["AUV"]
    assert args.year_min is None
    assert args.code_policy == "prefer"
    assert args.selection_policy == "code_preferred"
    assert args.max_results == 20
    assert args.max_auto_stage == 2
    assert args.review_survey_requested is True
    assert args.auto_stage is True
    assert args.skip_existing is False
    assert args.mode == "fast-ingest"
    assert args.json is True


def test_discover_papers_cli_outputs_high_level_record(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_discover_papers(**kwargs):
        captured.update(kwargs)
        return {
            "run_id": "discover-papers-001",
            "discovery_run_id": "dry-run-001",
            "auto_staging_run_id": "auto-staging-001",
            "status": "waiting_for_human_gate",
            "state": "source_staging_prepared",
            "selection_policy": "code_preferred",
            "workflow_mode": "fast-ingest",
            "stops_after": "source-staging",
            "compiled_wiki_write": False,
            "human_approval_written": False,
            "paper_wiki_invoked": False,
            "auto_stage": True,
            "processed_count": 2,
            "skipped_count": 1,
            "auto_staging_plan": {"selected": [{"slug": "fixture-paper"}]},
            "session_recommendations": {"primary_recommendations": []},
            "recommendation_summary": {"primary_count": 0, "auto_staging_status_counts": {}, "overflow_hidden_count": 0},
            "manual_downloads": [],
            "artifacts": {"discovery": {}, "auto_staging": {}},
            "exit_status": 0,
        }

    monkeypatch.setattr(cli.discover_papers_workflow, "discover_papers", fake_discover_papers)

    exit_code = cli.main(
        [
            "discover-papers",
            "--query",
            "natural language topic",
            "--vault",
            str(tmp_path),
            "--query-variant",
            '"domain object" "task"',
            "--domain-focus-term",
            "domain object",
            "--selection-policy",
            "code_preferred",
            "--max-auto-stage",
            "2",
            "--no-skip-existing",
            "--json",
        ]
    )

    payload = __import__("json").loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["run_id"] == "discover-papers-001"
    assert payload["discovery_run_id"] == "dry-run-001"
    assert payload["auto_staging_run_id"] == "auto-staging-001"
    assert payload["compiled_wiki_write"] is False
    assert payload["human_approval_written"] is False
    assert payload["paper_wiki_invoked"] is False
    assert captured["query"] == "natural language topic"
    assert captured["query_variants"] == ['"domain object" "task"']
    assert captured["domain_focus_terms"] == ["domain object"]
    assert captured["selection_policy"] == "code_preferred"
    assert captured["max_auto_stage"] == 2
    assert captured["auto_stage"] is True
    assert captured["skip_existing"] is False
    assert captured["year_min"] is None


def test_advance_ranked_cli_does_not_forward_prepare_only_skip_existing(tmp_path, monkeypatch):
    captured = {}

    def fake_advance_paper_batch_from_run(
        vault,
        run_id,
        *,
        mineru_command=None,
        max_papers=None,
        include_review_candidates=False,
        mineru_timeout=None,
        workflow_mode=None,
        selection_policy=None,
    ):
        captured.update(
            {
                "vault": vault,
                "run_id": run_id,
                "mineru_command": mineru_command,
                "max_papers": max_papers,
                "include_review_candidates": include_review_candidates,
                "mineru_timeout": mineru_timeout,
                "workflow_mode": workflow_mode,
                "selection_policy": selection_policy,
            }
        )
        return {"run_id": "advance-ranked-001", "state": "batch_done", "processed_count": 0}

    monkeypatch.setattr(cli.workflows, "advance_paper_batch_from_run", fake_advance_paper_batch_from_run)

    exit_code = cli.main(
        [
            "advance-ranked",
            "--run-id",
            "run-001",
            "--vault",
            str(tmp_path),
            "--max-papers",
            "3",
            "--include-review-candidates",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "vault": tmp_path,
        "run_id": "run-001",
        "mineru_command": None,
        "max_papers": 3,
        "include_review_candidates": True,
        "mineru_timeout": None,
        "workflow_mode": "fast-ingest",
        "selection_policy": "balanced_high_quality",
    }


def test_wiki_query_parser_accepts_research_decision_filters():
    args = build_parser().parse_args(
        [
            "wiki-query",
            "--consensus",
            "revise-before-staging",
            "--role",
            "peer-reviewer",
            "--verdict",
            "fail",
            "--blocking-lens",
            "peer-reviewer",
            "--warning-reviewer",
            "paper-quality-critic",
        ]
    )

    assert args.command == "wiki-query"
    assert args.consensus == "revise-before-staging"
    assert args.role == "peer-reviewer"
    assert args.verdict == "fail"
    assert args.blocking_lens == "peer-reviewer"
    assert args.warning_reviewer == "paper-quality-critic"


def test_wiki_ask_parser_accepts_question_graph_options_and_json():
    args = build_parser().parse_args(
        [
            "wiki-ask",
            "--question",
            "How should I start AUV strong-current attitude-control research with AI?",
            "--limit",
            "7",
            "--max-hops",
            "2",
            "--json",
        ]
    )

    assert args.command == "wiki-ask"
    assert args.question == "How should I start AUV strong-current attitude-control research with AI?"
    assert args.limit == 7
    assert args.max_hops == 2
    assert args.json is True


def test_wiki_ask_cli_outputs_read_only_ask_result_json(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_ask_wiki(vault, *, question, limit=8, max_hops=1):
        captured.update(
            {
                "vault": vault,
                "question": question,
                "limit": limit,
                "max_hops": max_hops,
            }
        )
        return {
            "title": "Paper Wiki Ask",
            "mode": "read-only",
            "question": question,
            "write_performed": False,
            "retrieval": {"primary": "formal_graph"},
            "pages": [],
            "correction_candidates": [],
        }

    monkeypatch.setattr(cli.workflows, "ask_wiki", fake_ask_wiki, raising=False)

    exit_code = cli.main(
        [
            "wiki-ask",
            "--question",
            "AUV strong-current attitude-control first step",
            "--vault",
            str(tmp_path),
            "--limit",
            "3",
            "--max-hops",
            "2",
            "--json",
        ]
    )

    payload = __import__("json").loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["title"] == "Paper Wiki Ask"
    assert payload["mode"] == "read-only"
    assert payload["write_performed"] is False
    assert captured == {
        "vault": tmp_path.resolve(),
        "question": "AUV strong-current attitude-control first step",
        "limit": 3,
        "max_hops": 2,
    }


def test_wiki_ingest_handoff_parser_accepts_slug_and_json():
    args = build_parser().parse_args(
        [
            "wiki-ingest-handoff",
            "--slug",
            "fixture-paper",
            "--json",
        ]
    )

    assert args.command == "wiki-ingest-handoff"
    assert args.slug == "fixture-paper"
    assert args.json is True


def test_wiki_ingest_trigger_parser_accepts_slug_and_json():
    args = build_parser().parse_args(
        [
            "wiki-ingest-trigger",
            "--slug",
            "fixture-paper",
            "--json",
        ]
    )

    assert args.command == "wiki-ingest-trigger"
    assert args.slug == "fixture-paper"
    assert args.json is True


def test_record_wiki_ingest_parser_accepts_pages_approval_notes_and_json():
    args = build_parser().parse_args(
        [
            "record-wiki-ingest",
            "--slug",
            "fixture-paper",
            "--page",
            "papers/fixture-paper.md",
            "--page",
            "concepts/fixture-concept.md",
            "--approved-by",
            "codex-test",
            "--notes",
            "agent applied target vault contract",
            "--source-review",
            "_paper_source/staging/papers/fixture-paper/final-source-review.json",
            "--json",
        ]
    )

    assert args.command == "record-wiki-ingest"
    assert args.slug == "fixture-paper"
    assert args.page == ["papers/fixture-paper.md", "concepts/fixture-concept.md"]
    assert args.approved_by == "codex-test"
    assert args.notes == "agent applied target vault contract"
    assert args.source_review == "_paper_source/staging/papers/fixture-paper/final-source-review.json"
    assert args.json is True


def test_record_wiki_ingest_parser_accepts_paper_wiki_record_request():
    args = build_parser().parse_args(
        [
            "record-wiki-ingest",
            "--from-paper-wiki-request",
            "_paper_source/staging/papers/fixture-paper/paper-wiki-record-request.json",
            "--json",
        ]
    )

    assert args.command == "record-wiki-ingest"
    assert args.from_paper_wiki_request.name == "paper-wiki-record-request.json"
    assert args.slug is None
    assert args.page is None
    assert args.approved_by is None
    assert args.json is True


def test_discover_to_handoff_parser_accepts_discovery_and_prepare_options():
    args = build_parser().parse_args(
        [
            "discover-to-handoff",
            "--query",
            "AUV attitude control recent papers",
            "--query-variant",
            '"AUV" "attitude control" -review -survey',
            "--domain-focus-term",
            "AUV",
            "--year-min",
            "2021",
            "--code-policy",
            "prefer",
            "--selection-policy",
            "code_preferred",
            "--max-results",
            "20",
            "--max-papers",
            "5",
            "--include-review-candidates",
            "--no-skip-existing",
            "--json",
        ]
    )

    assert args.command == "discover-to-handoff"
    assert args.query == "AUV attitude control recent papers"
    assert args.query_variant == ['"AUV" "attitude control" -review -survey']
    assert args.domain_focus_term == ["AUV"]
    assert args.year_min == 2021
    assert args.code_policy == "prefer"
    assert args.selection_policy == "code_preferred"
    assert args.max_results == 20
    assert args.max_papers == 5
    assert args.include_review_candidates is True
    assert args.skip_existing is False
    assert args.json is True


def test_record_wiki_ingest_parser_rejects_old_prw_record_request_flag():
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "record-wiki-ingest",
                "--from-prw-request",
                "_paper_source/staging/papers/fixture-paper/paper-wiki-record-request.json",
                "--json",
            ]
        )


def test_repository_maintenance_parser_uses_paper_source_commands():
    migrate = build_parser().parse_args(
        ["paper-source-repository-migrate", "--vault", "vault", "--preview", "--json"]
    )
    cleanup = build_parser().parse_args(
        ["paper-source-repository-cleanup", "--vault", "vault", "--preview", "--json"]
    )

    assert migrate.command == "paper-source-repository-migrate"
    assert migrate.preview is True
    assert migrate.json is True
    assert cleanup.command == "paper-source-repository-cleanup"
    assert cleanup.preview is True
    assert cleanup.json is True


def test_repository_maintenance_parser_rejects_old_epi_commands():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["epi-repository-migrate", "--vault", "vault", "--preview"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["epi-repository-cleanup", "--vault", "vault", "--preview"])


def test_record_human_approval_parser_accepts_scope_notes_and_json():
    args = build_parser().parse_args(
        [
            "record-human-approval",
            "--slug",
            "fixture-paper",
            "--approved-by",
            "codex-test",
            "--scope",
            "run-wiki-ingest-agent",
            "--notes",
            "approved for final wiki ingest agent",
            "--json",
        ]
    )

    assert args.command == "record-human-approval"
    assert args.slug == "fixture-paper"
    assert args.approved_by == "codex-test"
    assert args.scope == "run-wiki-ingest-agent"
    assert args.notes == "approved for final wiki ingest agent"
    assert args.json is True


def test_record_human_approval_parser_accepts_codex_automation_fields():
    args = build_parser().parse_args(
        [
            "record-human-approval",
            "--slug",
            "fixture-paper",
            "--approved-by",
            "codex-automation:task-123",
            "--scope",
            "run-wiki-ingest-agent",
            "--automation-mode",
            "codex-task",
            "--automation-task-id",
            "task-123",
            "--automation-task-source",
            ".trellis/tasks/example",
            "--automation-authorization",
            "User explicitly approved automation in this task.",
            "--json",
        ]
    )

    assert args.command == "record-human-approval"
    assert args.approved_by == "codex-automation:task-123"
    assert args.automation_mode == "codex-task"
    assert args.automation_task_id == "task-123"
    assert args.automation_task_source == ".trellis/tasks/example"
    assert args.automation_authorization == "User explicitly approved automation in this task."


def test_paper_gate_parser_accepts_slug_and_json():
    args = build_parser().parse_args(
        [
            "paper-gate",
            "--slug",
            "fixture-paper",
            "--json",
        ]
    )

    assert args.command == "paper-gate"
    assert args.slug == "fixture-paper"
    assert args.json is True


def test_research_queue_parser_accepts_bucket_json_and_limit():
    args = build_parser().parse_args(
        [
            "research-queue",
            "--bucket",
            "reproducibility_caveats",
            "--limit",
            "3",
            "--json",
        ]
    )

    assert args.command == "research-queue"
    assert args.bucket == "reproducibility_caveats"
    assert args.limit == 3
    assert args.json is True


def test_research_queue_parser_accepts_actions_flag():
    args = build_parser().parse_args(
        [
            "research-queue",
            "--bucket",
            "needs_reader_repair",
            "--actions",
        ]
    )

    assert args.command == "research-queue"
    assert args.bucket == "needs_reader_repair"
    assert args.actions is True


def test_report_parser_accepts_run_id_and_json():
    args = build_parser().parse_args(
        [
            "report",
            "--run-id",
            "run-001",
            "--json",
        ]
    )

    assert args.command == "report"
    assert args.run_id == "run-001"
    assert args.json is True


def test_run_lifecycle_parser_defaults_to_dry_run():
    args = build_parser().parse_args(
        [
            "run-lifecycle",
            "--keep-per-workflow",
            "3",
            "--json",
        ]
    )

    assert args.command == "run-lifecycle"
    assert args.keep_latest == 15
    assert args.keep_per_workflow == 3
    assert args.apply is False
    assert args.json is True


def test_wiki_reset_parser_requires_confirmation_and_supports_config_reset_gate():
    args = build_parser().parse_args(
        [
            "wiki-reset",
            "--confirmed-by",
            "确认重置 Paper Source wiki",
            "--reset-config-confirmed-by",
            "确认同时重置 Paper Source config",
            "--no-backup",
            "--preview",
            "--json",
        ]
    )

    assert args.command == "wiki-reset"
    assert args.confirmed_by == "确认重置 Paper Source wiki"
    assert args.reset_config_confirmed_by == "确认同时重置 Paper Source config"
    assert args.no_backup is True
    assert args.preview is True
    assert args.json is True


def test_config_recover_and_restore_parsers_accept_paths():
    recover_args = build_parser().parse_args(["config-recover", "--backup-root", "backups", "--json"])
    restore_args = build_parser().parse_args(
        [
            "config-restore",
            "--from",
            "backup/paper-source-config.yaml",
            "--confirmed-by",
            "确认恢复 Paper Source config",
            "--json",
        ]
    )

    assert recover_args.command == "config-recover"
    assert recover_args.backup_root.name == "backups"
    assert restore_args.command == "config-restore"
    assert restore_args.source_path.name == "paper-source-config.yaml"


def test_wiki_repair_parser_accepts_optional_restore_source():
    args = build_parser().parse_args(
        [
            "wiki-repair",
            "--backup-root",
            "backups",
            "--restore-from",
            "backups/paper-source-config.yaml",
            "--confirmed-by",
            "确认恢复 Paper Source config",
            "--json",
        ]
    )

    assert args.command == "wiki-repair"
    assert args.backup_root.name == "backups"
    assert args.restore_from.name == "paper-source-config.yaml"
    assert args.confirmed_by == "确认恢复 Paper Source config"


def test_research_agenda_command_is_not_registered():
    parser = build_parser()

    try:
        parser.parse_args(["research-agenda"])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("research-agenda should not be exposed as a Paper Source CLI command")


def test_propose_evolution_parser_accepts_skillopt_control_metadata():
    args = build_parser().parse_args(
        [
            "propose-evolution",
            "--reflection-type",
            "OPTIMIZATION",
            "--target-asset",
            "templates/ranking.example.yaml",
            "--rationale",
            "Improve ranking from evidence.",
            "--proposed-change-json",
            "{\"weights\":{\"topic_relevance\":0.39}}",
            "--evidence",
            "_paper_source/runs/index.json#1",
            "--evidence-type",
            "plugin_eval_warning",
            "--before-metrics-json",
            "{\"plugin_eval_score\":91}",
            "--acceptance-gates-json",
            "[{\"id\":\"tests_paper_source_pass\"}]",
            "--risk-level",
            "low",
        ]
    )

    assert args.command == "propose-evolution"
    assert args.evidence_type == "plugin_eval_warning"
    assert args.before_metrics_json == "{\"plugin_eval_score\":91}"
    assert args.acceptance_gates_json == "[{\"id\":\"tests_paper_source_pass\"}]"
    assert args.risk_level == "low"


def test_evaluation_brief_parser_accepts_quality_loop_inputs():
    args = build_parser().parse_args(
        [
            "evaluation-brief",
            "--target-asset",
            "templates/ranking.example.yaml",
            "--rationale",
            "Compare before/after quality signals before proposing a bounded change.",
            "--proposed-change-json",
            "{\"weights\":{\"topic_relevance\":0.41}}",
            "--before-metrics-json",
            "{\"plugin_eval_score\":82}",
            "--after-metrics-json",
            "{\"plugin_eval_score\":84}",
            "--plugin-eval-json",
            ".plugin-eval/plugin-eval.json",
            "--metric-pack-json",
            ".plugin-eval/paper-source-quality-gates.json",
            "--benchmark-json",
            ".plugin-eval/benchmark.json",
            "--evidence",
            "docs/evaluation.md#development-quality-loop",
            "--brief-id",
            "brief-001",
            "--out-dir",
            ".plugin-eval/improvement-briefs",
            "--json",
        ]
    )

    assert args.command == "evaluation-brief"
    assert args.brief_id == "brief-001"
    assert args.metric_pack_json.name == "paper-source-quality-gates.json"
    assert args.evidence == ["docs/evaluation.md#development-quality-loop"]
    assert args.json is True


def test_activate_evolution_parser_accepts_validation_result_json():
    args = build_parser().parse_args(
        [
            "activate-evolution",
            "--proposal-id",
            "evo-123",
            "--approved",
            "--validation-result-json",
            "{\"passed\":true}",
        ]
    )

    assert args.command == "activate-evolution"
    assert args.validation_result_json == "{\"passed\":true}"


def test_evolution_query_parser_accepts_status_json_and_limit():
    args = build_parser().parse_args(
        [
            "evolution-query",
            "--status",
            "pending_validation",
            "--json",
            "--limit",
            "5",
        ]
    )

    assert args.command == "evolution-query"
    assert args.status == "pending_validation"
    assert args.json is True
    assert args.limit == 5
