import json
import sys
from pathlib import Path

from epi.evaluation_loop import BENCHMARK_SCHEMA_VERSION, build_improvement_brief, write_improvement_brief
from epi.orchestrator import main


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_improvement_brief_links_quality_loop_metrics_and_evolution_payload(tmp_path):
    plugin_eval = _write_json(
        tmp_path / "plugin-eval.json",
        {"score": 82, "metrics": {"coverage_percent": 93.49}},
    )
    metric_pack = _write_json(
        tmp_path / "epi-quality-gates.json",
        {"metrics": [{"id": "epi-quality-gate-pass-rate", "value": 1.0}]},
    )
    benchmark = _write_json(
        tmp_path / "benchmark.json",
        {
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "benchmark_id": "ranking-quality-fixture",
            "cases": [
                {"id": "case-1", "status": "pass"},
                {"id": "case-2", "status": "pass"},
            ],
        },
    )

    brief = build_improvement_brief(
        brief_id="brief-fixture",
        target_asset="templates/ranking.example.yaml",
        rationale="Promote a ranking tuning only after quality metrics do not regress.",
        proposed_change={"weights": {"topic_relevance": 0.41}},
        before_metrics={
            "plugin_eval_score": 80,
            "coverage_percent": 92.0,
            "epi-quality-gate-pass-rate": 0.75,
            "benchmark_pass_rate": 0.5,
        },
        after_metrics={"plugin_eval_score": 83},
        plugin_eval_path=plugin_eval,
        metric_pack_path=metric_pack,
        benchmark_path=benchmark,
        evidence=["docs/evaluation.md#quality-loop"],
    )

    assert brief["schema_version"] == "epi-improvement-brief-v1"
    assert brief["quality_loop"] == [
        "plugin-eval",
        "epi-quality-gates",
        "benchmark",
        "compare-before-after",
        "improvement-brief",
        "skill-aware-evolve-proposal",
    ]
    assert brief["after_metrics"]["plugin_eval_score"] == 83
    assert brief["after_metrics"]["epi-quality-gate-pass-rate"] == 1.0
    assert brief["after_metrics"]["benchmark_pass_rate"] == 1.0
    assert brief["source_completeness"] == {
        "required_sources": ["plugin_eval", "epi_quality_gates", "benchmark"],
        "present_sources": ["plugin_eval", "epi_quality_gates", "benchmark"],
        "missing_sources": [],
        "invalid_sources": [],
        "complete": True,
    }
    assert brief["sources"]["benchmark"]["benchmark_contract"] == {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "valid": True,
        "case_count": 2,
        "metric_count": 0,
        "issues": [],
    }

    comparisons = {item["metric"]: item for item in brief["metric_comparisons"]}
    assert comparisons["plugin_eval_score"]["trend"] == "improved"
    assert comparisons["coverage_percent"]["trend"] == "improved"
    assert comparisons["epi-quality-gate-pass-rate"]["trend"] == "improved"
    assert comparisons["benchmark_pass_rate"]["trend"] == "improved"

    proposed = brief["proposed_evolution"]
    assert proposed["target_asset"] == "templates/ranking.example.yaml"
    assert proposed["before_metrics"]["plugin_eval_score"] == 80.0
    gate_ids = {gate["id"] for gate in proposed["acceptance_gates"]}
    assert "human_approval" in gate_ids
    assert "quality_loop_sources_complete" not in gate_ids
    assert "plugin_eval_score_non_regression" in gate_ids
    assert "epi_quality_gate_pass_rate_non_regression" in gate_ids
    assert str(plugin_eval) in proposed["evidence"]


def test_evaluation_brief_cli_writes_json_and_markdown(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "briefs"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "epi.orchestrator",
            "evaluation-brief",
            "--brief-id",
            "brief-cli",
            "--target-asset",
            "templates/ranking.example.yaml",
            "--rationale",
            "Document the before/after quality signal before proposing a template change.",
            "--proposed-change-json",
            '{"weights":{"topic_relevance":0.4}}',
            "--before-metrics-json",
            '{"plugin_eval_score":82}',
            "--after-metrics-json",
            '{"plugin_eval_score":83}',
            "--out-dir",
            str(output_dir),
            "--json",
        ],
    )

    exit_code = main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["brief"]["id"] == "brief-cli"
    assert payload["brief"]["metric_comparisons"][0]["trend"] == "improved"
    json_path = Path(payload["paths"]["json"])
    markdown_path = Path(payload["paths"]["markdown"])
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert "skill-aware-evolve-proposal" in markdown_path.read_text(encoding="utf-8")


def test_improvement_brief_records_missing_quality_loop_sources_as_action_required(tmp_path):
    missing_source = tmp_path / "missing-plugin-eval.json"

    brief = build_improvement_brief(
        brief_id="brief-missing-source",
        target_asset="skills/paper-discovery/SKILL.md",
        rationale="Keep the development loop usable when one optional report was not produced.",
        proposed_change={"note": "tighten trigger wording"},
        before_metrics={"plugin_eval_score": 82},
        plugin_eval_path=missing_source,
    )

    assert brief["sources"]["plugin_eval"]["present"] is False
    assert brief["source_completeness"]["complete"] is False
    assert brief["source_completeness"]["missing_sources"] == [
        "plugin_eval",
        "epi_quality_gates",
        "benchmark",
    ]
    assert brief["source_completeness"]["invalid_sources"] == []
    assert brief["improvement_summary"]["next_action"] == "collect-missing-quality-evidence"
    gates = {gate["id"]: gate for gate in brief["proposed_evolution"]["acceptance_gates"]}
    assert gates["quality_loop_sources_complete"]["required"] is True
    assert gates["quality_loop_sources_complete"]["missing_sources"] == [
        "plugin_eval",
        "epi_quality_gates",
        "benchmark",
    ]
    assert gates["quality_loop_sources_complete"]["invalid_sources"] == []
    assert str(missing_source) not in brief["proposed_evolution"]["evidence"]


def test_improvement_brief_marks_invalid_benchmark_contract_as_incomplete(tmp_path):
    plugin_eval = _write_json(tmp_path / "plugin-eval.json", {"score": 82})
    metric_pack = _write_json(
        tmp_path / "epi-quality-gates.json",
        {"metrics": [{"id": "epi-quality-gate-pass-rate", "value": 1.0}]},
    )
    invalid_benchmark = _write_json(
        tmp_path / "benchmark.json",
        {"cases": [{"status": "pass"}]},
    )

    brief = build_improvement_brief(
        brief_id="brief-invalid-benchmark",
        target_asset="templates/ranking.example.yaml",
        rationale="Do not promote changes from a benchmark without a schema and stable case ids.",
        proposed_change={"weights": {"topic_relevance": 0.42}},
        before_metrics={"benchmark_pass_rate": 0.5},
        plugin_eval_path=plugin_eval,
        metric_pack_path=metric_pack,
        benchmark_path=invalid_benchmark,
    )

    contract = brief["sources"]["benchmark"]["benchmark_contract"]
    assert contract["valid"] is False
    assert "schema_version must be epi-benchmark-v1" in contract["issues"]
    assert "cases[1] must include id or name" in contract["issues"]
    assert brief["source_completeness"]["invalid_sources"] == ["benchmark"]
    assert brief["improvement_summary"]["next_action"] == "collect-missing-quality-evidence"
    gates = {gate["id"]: gate for gate in brief["proposed_evolution"]["acceptance_gates"]}
    assert gates["quality_loop_sources_complete"]["invalid_sources"] == ["benchmark"]
