import json
from pathlib import Path

import pytest

from epi.evaluation_loop import build_improvement_brief
from epi.feedback import record_feedback
from epi.skill_aware_evolve import activate_evolution, propose_evolution, query_evolution, render_evolution_query
from epi.zotero_sync import sync_zotero_record


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_templates(vault_path: Path) -> None:
    _write_text(
        vault_path / "templates" / "ranking.example.yaml",
        "\n".join(
            [
                "weights:",
                "  topic_relevance: 0.35",
                "  reproducibility_signal: 0.06",
                "",
            ]
        ),
    )
    _write_text(
        vault_path / "templates" / "critic-checklist.example.yaml",
        "\n".join(
            [
                "paper_quality_critic:",
                "  enabled_from_phase: 2",
                "",
            ]
        ),
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_zotero_sync_disabled_writes_skip_record(tmp_path):
    paper_root = tmp_path / "_epi" / "raw" / "paper"
    paper_root.mkdir(parents=True)

    record = sync_zotero_record(paper_root, enabled=False, collection="EPI")

    assert record["status"] == "skipped"
    assert record["reason"] == "zotero_disabled"
    written = json.loads((paper_root / "zotero-record.json").read_text(encoding="utf-8"))
    assert written["collection"] == "EPI"


def test_record_feedback_appends_jsonl(tmp_path):
    first = record_feedback(
        tmp_path,
        feedback_type="reader-correction",
        target="paper/reader.md",
        message="Claim needs stronger evidence.",
        source="human",
    )
    second = record_feedback(
        tmp_path,
        feedback_type="plugin-eval",
        target="plugins/epi",
        message="Token budget warning reviewed.",
        source="plugin-eval",
    )

    feedback_log = tmp_path / "_epi" / "runs" / "feedback.jsonl"
    rows = [json.loads(line) for line in feedback_log.read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in rows] == [first["id"], second["id"]]
    assert rows[0]["type"] == "reader-correction"
    assert rows[1]["source"] == "plugin-eval"


def test_record_feedback_updates_run_local_summary_when_run_id_is_provided(tmp_path):
    first = record_feedback(
        tmp_path,
        feedback_type="reader-correction",
        target="paper/reader.md",
        message="Need better traceability for claim 2.",
        source="human",
        run_id="run-123",
    )
    second = record_feedback(
        tmp_path,
        feedback_type="plugin-eval",
        target="plugins/epi",
        message="Whitelist policy confirmed.",
        source="plugin-eval",
        run_id="run-123",
    )

    feedback_log = tmp_path / "_epi" / "runs" / "feedback.jsonl"
    rows = [json.loads(line) for line in feedback_log.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in rows] == ["run-123", "run-123"]

    summary = _read_json(tmp_path / "_epi" / "runs" / "run-123" / "feedback-summary.json")
    assert summary["run_id"] == "run-123"
    assert summary["feedback_count"] == 2
    assert summary["feedback_ids"] == [first["id"], second["id"]]
    assert summary["last_feedback_id"] == second["id"]


def test_evolution_proposal_requires_approval_and_validation_before_applying_whitelisted_asset(tmp_path):
    _seed_templates(tmp_path)
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Boost reproducibility signal after repeated user feedback.",
        proposed_change={"weights": {"reproducibility_signal": 0.12}},
        evidence=["_epi/runs/feedback.jsonl#1"],
    )

    proposal_path = tmp_path / "_epi" / "evolution" / "proposals" / f"{proposal['id']}.json"
    assert proposal_path.is_file()

    with pytest.raises(PermissionError, match="approval"):
        activate_evolution(tmp_path, proposal["id"], approved=False)

    pending = activate_evolution(tmp_path, proposal["id"], approved=True)

    assert pending["status"] == "pending_validation"
    assert pending["activation_status"] == "action_required"
    assert pending["asset_application"]["status"] == "record_only"
    assert pending["asset_application"]["reason"] == "validation_required_before_skill_change"
    assert pending["check_suite"]["status"] == "completed"
    assert pending["check_suite"]["conclusion"] == "action_required"
    assert "reproducibility_signal: 0.06" in (
        tmp_path / "templates" / "ranking.example.yaml"
    ).read_text(encoding="utf-8")
    assert (tmp_path / "_epi" / "evolution" / "pending" / f"{proposal['id']}.json").is_file()

    activated = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "summary": "tests and plugin eval passed"},
    )

    assert activated["status"] == "active"
    assert activated["activation_status"] == "active"
    assert activated["check_suite"]["status"] == "completed"
    assert activated["check_suite"]["conclusion"] == "success"
    assert all(run["conclusion"] in {"success", "skipped", "neutral"} for run in activated["check_suite"]["check_runs"])
    assert activated["code_modified"] is False
    assert activated["asset_application"]["status"] == "applied"
    assert (tmp_path / "_epi" / "evolution" / "active" / f"{proposal['id']}.json").is_file()
    assert "reproducibility_signal: 0.12" in (
        tmp_path / "templates" / "ranking.example.yaml"
    ).read_text(encoding="utf-8")


def test_evolution_proposal_records_skillopt_and_embodiskill_control_contract(tmp_path):
    _seed_templates(tmp_path)

    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Use run outcomes to tune paper ranking without touching runtime code.",
        proposed_change={"weights": {"topic_relevance": 0.39}},
        evidence=["_epi/runs/index.json#latest_success_by_workflow"],
        evidence_type="plugin_eval_warning",
        before_metrics={"plugin_eval_score": 91, "coverage_percent": 94.39},
        acceptance_gates=[
            {"id": "plugin_eval_non_regression", "metric": "plugin_eval_score", "operator": ">=", "value": 91},
            {"id": "tests_epi_pass", "command": "python -m pytest tests\\epi -q"},
        ],
    )

    assert proposal["activation_status"] == "pending_human_approval"
    assert proposal["reflection_classification"] == "skill_change"
    assert proposal["skill_change_allowed"] is True
    assert proposal["risk_level"] == "low"
    assert proposal["before_metrics"]["plugin_eval_score"] == 91
    assert proposal["acceptance_gates"][0]["id"] == "plugin_eval_non_regression"
    assert proposal["bounded_change"]["single_target_asset"] is True
    assert proposal["bounded_change"]["target_asset"] == "templates/ranking.example.yaml"
    assert set(proposal["bounded_change"]["allowed_operations"]) == {"add", "replace", "delete"}
    assert "SkillOpt" in proposal["optimizer_protocol"]["inspired_by"]
    assert proposal["optimizer_protocol"]["skillopt"]["validation_improvement_required"] is True
    assert proposal["optimizer_protocol"]["embodiskill"]["skill_aware_reflection"] is True


def test_execution_lapse_evolution_is_record_only_and_preserves_whitelisted_asset(tmp_path):
    _seed_templates(tmp_path)
    target_path = tmp_path / "templates" / "ranking.example.yaml"
    original = target_path.read_text(encoding="utf-8")
    proposal = propose_evolution(
        tmp_path,
        reflection_type="EXECUTION_LAPSE",
        target_asset="templates/ranking.example.yaml",
        rationale="The agent ignored an existing instruction; the skill itself is still correct.",
        proposed_change={"weights": {"topic_relevance": 0.99}},
        evidence=["_epi/runs/run-123/report.md#missed-existing-instruction"],
        evidence_type="missed_existing_instruction",
    )

    activated = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "summary": "rollback metadata smoke passed"},
    )

    assert proposal["reflection_classification"] == "execution_lapse"
    assert proposal["skill_change_allowed"] is False
    assert activated["status"] == "active"
    assert activated["asset_application"]["status"] == "record_only"
    assert activated["asset_application"]["reason"] == "execution_lapse_preserves_existing_skill"
    assert target_path.read_text(encoding="utf-8") == original


def test_configuration_change_evolution_is_record_only_and_preserves_whitelisted_asset(tmp_path):
    _seed_templates(tmp_path)
    target_path = tmp_path / "templates" / "ranking.example.yaml"
    original = target_path.read_text(encoding="utf-8")
    proposal = propose_evolution(
        tmp_path,
        reflection_type="CONFIGURATION_CHANGE",
        target_asset="templates/ranking.example.yaml",
        rationale="The user's topic profile needs a config update, not a skill template edit.",
        proposed_change={"weights": {"topic_relevance": 0.99}},
        evidence=["_epi/runs/run-123/report.md#profile-mismatch"],
        evidence_type="configuration_change",
    )

    activated = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "summary": "record-only config routing validated"},
    )
    result = query_evolution(tmp_path)

    assert proposal["reflection_classification"] == "configuration_change"
    assert proposal["skill_change_allowed"] is False
    assert activated["status"] == "active"
    assert activated["asset_application"]["status"] == "record_only"
    assert activated["asset_application"]["reason"] == "configuration_change_uses_config_proposal_flow"
    assert result["items"][0]["next_action"] == "propose-config-update"
    assert target_path.read_text(encoding="utf-8") == original


def test_activate_evolution_records_rejected_edit_when_validation_gate_fails(tmp_path):
    _seed_templates(tmp_path)
    target_path = tmp_path / "templates" / "ranking.example.yaml"
    original = target_path.read_text(encoding="utf-8")
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Only activate if the validation score does not regress.",
        proposed_change={"weights": {"topic_relevance": 0.41}},
        evidence=["plugin-eval#score"],
        acceptance_gates=[
            {"id": "plugin_eval_non_regression", "metric": "plugin_eval_score", "operator": ">=", "value": 91},
        ],
    )

    rejected = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": False, "plugin_eval_score": 88, "reason": "score regression"},
    )

    assert rejected["status"] == "rejected"
    assert rejected["activation_status"] == "rejected_by_validation"
    assert rejected["check_suite"]["status"] == "completed"
    assert rejected["check_suite"]["conclusion"] == "failure"
    plugin_eval_check = next(
        run for run in rejected["check_suite"]["check_runs"] if run["name"] == "plugin_eval_non_regression"
    )
    assert plugin_eval_check["conclusion"] == "failure"
    assert rejected["asset_application"]["status"] == "record_only"
    assert rejected["asset_application"]["reason"] == "validation_gate_failed"
    assert (tmp_path / "_epi" / "evolution" / "rejected" / f"{proposal['id']}.json").is_file()
    assert target_path.read_text(encoding="utf-8") == original


def test_activate_evolution_rejects_when_metric_gate_regresses_even_if_passed_flag_is_true(tmp_path):
    _seed_templates(tmp_path)
    target_path = tmp_path / "templates" / "ranking.example.yaml"
    original = target_path.read_text(encoding="utf-8")
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="SkillOpt-style validation gates must compare the held-out score, not just a boolean flag.",
        proposed_change={"weights": {"topic_relevance": 0.41}},
        evidence=["plugin-eval#score"],
        before_metrics={"plugin_eval_score": 91},
        acceptance_gates=[
            {"id": "plugin_eval_non_regression", "metric": "plugin_eval_score", "operator": ">=", "value": 91},
        ],
    )

    rejected = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "plugin_eval_score": 90, "summary": "tests passed but eval regressed"},
    )

    plugin_eval_check = next(
        run for run in rejected["check_suite"]["check_runs"] if run["name"] == "plugin_eval_non_regression"
    )
    assert rejected["status"] == "rejected"
    assert rejected["activation_status"] == "rejected_by_validation"
    assert plugin_eval_check["conclusion"] == "failure"
    assert "does not satisfy" in plugin_eval_check["output"]["summary"]
    assert rejected["asset_application"]["status"] == "record_only"
    assert target_path.read_text(encoding="utf-8") == original


def test_activate_evolution_rejects_incomplete_quality_loop_sources_even_if_validation_passed(tmp_path):
    _seed_templates(tmp_path)
    target_path = tmp_path / "templates" / "ranking.example.yaml"
    original = target_path.read_text(encoding="utf-8")
    missing_plugin_eval = tmp_path / "missing-plugin-eval.json"
    brief = build_improvement_brief(
        target_asset="templates/ranking.example.yaml",
        rationale="Do not activate a quality-loop proposal until all evidence sources are complete.",
        proposed_change={"weights": {"topic_relevance": 0.41}},
        before_metrics={"plugin_eval_score": 91},
        after_metrics={"plugin_eval_score": 92},
        plugin_eval_path=missing_plugin_eval,
        metric_pack_path=None,
        benchmark_path=None,
    )
    proposed = brief["proposed_evolution"]
    proposal = propose_evolution(
        tmp_path,
        reflection_type=proposed["reflection_type"],
        target_asset=proposed["target_asset"],
        rationale=proposed["rationale"],
        proposed_change=proposed["proposed_change"],
        evidence=proposed["evidence"],
        evidence_type=proposed["evidence_type"],
        before_metrics=proposed["before_metrics"],
        acceptance_gates=proposed["acceptance_gates"],
    )

    rejected = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "summary": "tests passed but quality-loop sources are incomplete"},
    )

    completeness_check = next(
        run for run in rejected["check_suite"]["check_runs"] if run["name"] == "quality_loop_sources_complete"
    )
    assert rejected["status"] == "rejected"
    assert rejected["activation_status"] == "rejected_by_validation"
    assert completeness_check["conclusion"] == "failure"
    assert "plugin_eval" in completeness_check["output"]["summary"]
    assert "epi_quality_gates" in completeness_check["output"]["summary"]
    assert "benchmark" in completeness_check["output"]["summary"]
    assert rejected["asset_application"]["status"] == "record_only"
    assert target_path.read_text(encoding="utf-8") == original


def test_activate_evolution_accepts_nested_metric_gate_when_non_regressing(tmp_path):
    _seed_templates(tmp_path)
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Accept only when validation metrics prove non-regression.",
        proposed_change={"weights": {"topic_relevance": 0.41}},
        evidence=["plugin-eval#score"],
        before_metrics={"plugin_eval_score": 91},
        acceptance_gates=[
            {"id": "plugin_eval_non_regression", "metric": "plugin_eval_score", "operator": ">=", "value": 91},
        ],
    )

    activated = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={
            "passed": True,
            "metrics": {"plugin_eval_score": 92},
            "summary": "tests and plugin eval passed",
        },
    )

    plugin_eval_check = next(
        run for run in activated["check_suite"]["check_runs"] if run["name"] == "plugin_eval_non_regression"
    )
    assert activated["status"] == "active"
    assert activated["asset_application"]["status"] == "applied"
    assert plugin_eval_check["conclusion"] == "success"
    assert "satisfies" in plugin_eval_check["output"]["summary"]
    assert "topic_relevance: 0.41" in (
        tmp_path / "templates" / "ranking.example.yaml"
    ).read_text(encoding="utf-8")


def test_activate_evolution_forces_validation_check_even_with_custom_human_only_gate(tmp_path):
    _seed_templates(tmp_path)
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Custom gates cannot bypass the validation status contract.",
        proposed_change={"weights": {"topic_relevance": 0.42}},
        evidence=["plugin-eval#score"],
        acceptance_gates=[{"id": "human_approval", "required": True}],
    )

    pending = activate_evolution(tmp_path, proposal["id"], approved=True)

    assert pending["status"] == "pending_validation"
    assert pending["activation_status"] == "action_required"
    assert pending["check_suite"]["conclusion"] == "action_required"
    assert any(run["conclusion"] == "action_required" for run in pending["check_suite"]["check_runs"])

    rejected = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": False, "reason": "score regression"},
    )

    assert rejected["status"] == "rejected"
    assert rejected["activation_status"] == "rejected_by_validation"
    assert rejected["check_suite"]["conclusion"] == "failure"
    assert any(run["conclusion"] == "failure" for run in rejected["check_suite"]["check_runs"])


def test_activate_evolution_keeps_non_whitelisted_assets_record_only(tmp_path):
    _seed_templates(tmp_path)
    original = "rules:\n  min_score: 0.42\n"
    target_path = tmp_path / "templates" / "filter-rules.example.yaml"
    _write_text(target_path, original)
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/filter-rules.example.yaml",
        rationale="This asset is intentionally outside the whitelist.",
        proposed_change={"rules": {"min_score": 0.55}},
        evidence=["_epi/runs/feedback.jsonl#2"],
    )

    activated = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "summary": "rollback metadata smoke passed"},
    )

    assert activated["status"] == "active"
    assert activated["asset_application"]["status"] == "record_only"
    assert target_path.read_text(encoding="utf-8") == original


def test_propose_evolution_rejects_unbounded_target_asset_paths(tmp_path):
    with pytest.raises(ValueError, match="bounded relative target_asset"):
        propose_evolution(
            tmp_path,
            reflection_type="OPTIMIZATION",
            target_asset="../plugins/epi/scripts/build/epi/orchestrator.py",
            rationale="Do not allow path traversal evolution targets.",
            proposed_change={"anything": True},
            evidence=["_epi/runs/feedback.jsonl#4"],
        )


def test_activate_evolution_records_backup_and_rollback_metadata(tmp_path):
    _seed_templates(tmp_path)
    target_path = tmp_path / "templates" / "ranking.example.yaml"
    original = target_path.read_text(encoding="utf-8")
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Track rollback metadata for applied template changes.",
        proposed_change={"weights": {"topic_relevance": 0.33}},
        evidence=["_epi/runs/feedback.jsonl#3"],
    )

    activated = activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "summary": "rollback metadata smoke passed"},
    )
    active_record = _read_json(tmp_path / "_epi" / "evolution" / "active" / f"{proposal['id']}.json")

    backup_path = Path(active_record["rollback"]["backup_path"])
    assert activated["asset_application"]["backup_created"] is True
    assert active_record["rollback"]["target_asset"] == "templates/ranking.example.yaml"
    assert backup_path.is_file()
    assert backup_path.read_text(encoding="utf-8") == original


def test_query_evolution_summarizes_pending_rejected_and_active_records(tmp_path):
    _seed_templates(tmp_path)
    pending_proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Needs validation before any template write.",
        proposed_change={"weights": {"topic_relevance": 0.44}},
        evidence=["plugin-eval#warning"],
    )
    rejected_proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Reject when validation regresses.",
        proposed_change={"weights": {"topic_relevance": 0.45}},
        evidence=["plugin-eval#score"],
    )
    active_proposal = propose_evolution(
        tmp_path,
        reflection_type="EXECUTION_LAPSE",
        target_asset="templates/ranking.example.yaml",
        rationale="Record an execution lapse without changing valid guidance.",
        proposed_change={"weights": {"topic_relevance": 0.99}},
        evidence=["_epi/runs/run-1/report.md#missed-instruction"],
        evidence_type="missed_existing_instruction",
    )

    activate_evolution(tmp_path, pending_proposal["id"], approved=True)
    activate_evolution(
        tmp_path,
        rejected_proposal["id"],
        approved=True,
        validation_result={"passed": False, "reason": "score regression"},
    )
    activate_evolution(
        tmp_path,
        active_proposal["id"],
        approved=True,
        validation_result={"passed": True, "summary": "record-only validation passed"},
    )

    result = query_evolution(tmp_path)

    assert result["summary"] == {
        "total_records": 3,
        "status_counts": {
            "active": 1,
            "pending_validation": 1,
            "rejected": 1,
        },
        "check_suite_counts": {
            "action_required": 1,
            "failure": 1,
            "success": 1,
        },
    }
    assert [item["id"] for item in result["items"]] == [
        active_proposal["id"],
        rejected_proposal["id"],
        pending_proposal["id"],
    ]
    pending = query_evolution(tmp_path, status="pending_validation")
    assert [item["id"] for item in pending["items"]] == [pending_proposal["id"]]
    assert pending["items"][0]["next_action"] == "provide-validation-result"
    assert pending["items"][0]["check_suite_conclusion"] == "action_required"
    assert pending["items"][0]["action_required_checks"][0]["name"] == "validation_non_regression"

    rendered = render_evolution_query(result)
    assert "# EPI Evolution Status" in rendered
    assert "pending_validation: 1" in rendered
    assert "provide-validation-result" in rendered
    assert "score regression" in rendered
    assert "failed-check:" in rendered
    assert "action-required-check:" in rendered


def test_query_evolution_surfaces_metric_gate_failure_summary(tmp_path):
    _seed_templates(tmp_path)
    proposal = propose_evolution(
        tmp_path,
        reflection_type="OPTIMIZATION",
        target_asset="templates/ranking.example.yaml",
        rationale="Make metric-gated rejections explainable.",
        proposed_change={"weights": {"topic_relevance": 0.41}},
        evidence=["plugin-eval#score"],
        acceptance_gates=[
            {"id": "plugin_eval_non_regression", "metric": "plugin_eval_score", "operator": ">=", "value": 91},
        ],
    )
    activate_evolution(
        tmp_path,
        proposal["id"],
        approved=True,
        validation_result={"passed": True, "plugin_eval_score": 90, "summary": "tests passed but score regressed"},
    )

    result = query_evolution(tmp_path, status="rejected")
    item = result["items"][0]
    rendered = render_evolution_query(result)

    assert item["failed_checks"][0]["name"] == "plugin_eval_non_regression"
    assert "plugin_eval_score=90" in item["failed_checks"][0]["summary"]
    assert "plugin_eval_non_regression" in rendered
    assert "plugin_eval_score=90" in rendered
