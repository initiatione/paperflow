from epi.cli import build_parser


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
