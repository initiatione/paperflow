from epi import cli
from epi.cli import build_parser


def test_dry_run_parser_defaults_to_query_plan_and_accepts_overrides():
    args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--query-plan-domain",
            "auv-control",
            "--query-plan-max-queries",
            "8",
        ]
    )

    assert args.command == "dry-run"
    assert args.no_query_plan is False
    assert args.query_plan_domain == "auv-control"
    assert args.query_plan_max_queries == 8


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


def test_prepare_ranked_parser_defaults_to_one_paper_and_stops_after_parse():
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
    ):
        captured.update(
            {
                "vault": vault,
                "run_id": run_id,
                "mineru_command": mineru_command,
                "max_papers": max_papers,
                "include_review_candidates": include_review_candidates,
                "skip_existing": skip_existing,
            }
        )
        return {"run_id": "prepare-ranked-001", "state": "parsed", "processed_count": 0}

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
    }
    assert "stops_after=parse" in capsys.readouterr().out


def test_advance_ranked_cli_does_not_forward_prepare_only_skip_existing(tmp_path, monkeypatch):
    captured = {}

    def fake_advance_paper_batch_from_run(
        vault,
        run_id,
        *,
        mineru_command=None,
        max_papers=None,
        include_review_candidates=False,
    ):
        captured.update(
            {
                "vault": vault,
                "run_id": run_id,
                "mineru_command": mineru_command,
                "max_papers": max_papers,
                "include_review_candidates": include_review_candidates,
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


def test_run_lifecycle_parser_defaults_to_dry_run():
    args = build_parser().parse_args(
        [
            "run-lifecycle",
            "--keep-latest",
            "20",
            "--keep-per-workflow",
            "3",
            "--json",
        ]
    )

    assert args.command == "run-lifecycle"
    assert args.keep_latest == 20
    assert args.keep_per_workflow == 3
    assert args.apply is False
    assert args.json is True


def test_wiki_reset_parser_requires_confirmation_and_supports_config_reset_gate():
    args = build_parser().parse_args(
        [
            "wiki-reset",
            "--confirmed-by",
            "确认重置 EPI wiki",
            "--reset-config-confirmed-by",
            "确认同时重置 EPI config",
            "--no-backup",
            "--preview",
            "--json",
        ]
    )

    assert args.command == "wiki-reset"
    assert args.confirmed_by == "确认重置 EPI wiki"
    assert args.reset_config_confirmed_by == "确认同时重置 EPI config"
    assert args.no_backup is True
    assert args.preview is True
    assert args.json is True


def test_config_recover_and_restore_parsers_accept_paths():
    recover_args = build_parser().parse_args(["config-recover", "--backup-root", "backups", "--json"])
    restore_args = build_parser().parse_args(
        [
            "config-restore",
            "--from",
            "backup/epi-config.yaml",
            "--confirmed-by",
            "确认恢复 EPI config",
            "--json",
        ]
    )

    assert recover_args.command == "config-recover"
    assert recover_args.backup_root.name == "backups"
    assert restore_args.command == "config-restore"
    assert restore_args.source_path.name == "epi-config.yaml"


def test_wiki_repair_parser_accepts_optional_restore_source():
    args = build_parser().parse_args(
        [
            "wiki-repair",
            "--backup-root",
            "backups",
            "--restore-from",
            "backups/epi-config.yaml",
            "--confirmed-by",
            "确认恢复 EPI config",
            "--json",
        ]
    )

    assert args.command == "wiki-repair"
    assert args.backup_root.name == "backups"
    assert args.restore_from.name == "epi-config.yaml"
    assert args.confirmed_by == "确认恢复 EPI config"


def test_research_agenda_command_is_not_registered():
    parser = build_parser()

    try:
        parser.parse_args(["research-agenda"])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("research-agenda should not be exposed as an EPI CLI command")


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
            "_runs/index.json#1",
            "--evidence-type",
            "plugin_eval_warning",
            "--before-metrics-json",
            "{\"plugin_eval_score\":91}",
            "--acceptance-gates-json",
            "[{\"id\":\"tests_epi_pass\"}]",
            "--risk-level",
            "low",
        ]
    )

    assert args.command == "propose-evolution"
    assert args.evidence_type == "plugin_eval_warning"
    assert args.before_metrics_json == "{\"plugin_eval_score\":91}"
    assert args.acceptance_gates_json == "[{\"id\":\"tests_epi_pass\"}]"
    assert args.risk_level == "low"


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
