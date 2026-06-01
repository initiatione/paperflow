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


def test_dry_run_cli_json_outputs_run_artifact_paths(tmp_path, monkeypatch, capsys):
    run_dir = tmp_path / "_epi" / "runs" / "run-json-001"
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
            }
        )
        return {
            "run_id": "prepare-ranked-001",
            "source_run_id": run_id,
            "state": "prepared",
            "status": "prepared",
            "processed_count": 2,
            "skipped_count": 1,
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
    run_dir = tmp_path / "_epi" / "runs" / "prepare-ranked-001"
    assert exit_code == 0
    assert payload["run_id"] == "prepare-ranked-001"
    assert payload["source_run_id"] == "run-001"
    assert payload["batch_state"] == "prepared"
    assert payload["processed_count"] == 2
    assert payload["skipped_count"] == 1
    assert payload["stops_after"] == "parse"
    assert payload["run_dir"] == str(run_dir)
    assert payload["artifacts"]["batch_record"] == str(run_dir / "batch-advance-record.json")
    assert payload["artifacts"]["report_json"] == str(run_dir / "report.json")
    assert captured["skip_existing"] is True
    assert captured["include_review_candidates"] is True


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
        "mineru_timeout": None,
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
        mineru_timeout=None,
    ):
        captured.update(
            {
                "vault": vault,
                "run_id": run_id,
                "mineru_command": mineru_command,
                "max_papers": max_papers,
                "include_review_candidates": include_review_candidates,
                "mineru_timeout": mineru_timeout,
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
            "_epi/staging/papers/fixture-paper/final-source-review.json",
            "--json",
        ]
    )

    assert args.command == "record-wiki-ingest"
    assert args.slug == "fixture-paper"
    assert args.page == ["papers/fixture-paper.md", "concepts/fixture-concept.md"]
    assert args.approved_by == "codex-test"
    assert args.notes == "agent applied target vault contract"
    assert args.source_review == "_epi/staging/papers/fixture-paper/final-source-review.json"
    assert args.json is True


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
            "_epi/runs/index.json#1",
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
            ".plugin-eval/epi-quality-gates.json",
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
    assert args.metric_pack_json.name == "epi-quality-gates.json"
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
