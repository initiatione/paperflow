import json
import sys

import pytest

from epi.orchestrator import main, record_human_approval
from epi.report_run import load_run_report
from epi.run_index import _paper_gate_allows_promotion, refresh_run_index
from epi.stage_wiki import _build_wiki_ingest_brief
from epi.wiki_contracts import required_wiki_skills


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_run(
    runs_root,
    run_id,
    *,
    workflow_type,
    state,
    status,
    paper_slug,
    next_actions=None,
    human_gate=None,
    report_extra=None,
):
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "run-state.json",
        {
            "run_id": run_id,
            "workflow_type": workflow_type,
            "state": state,
            "status": status,
            "paper_slug": paper_slug,
            "started_at": f"{run_id}-start",
            "finished_at": f"{run_id}-finish",
        },
    )
    report = {
        "next_actions": next_actions or [],
        "human_gate": human_gate,
    }
    if report_extra:
        report.update(report_extra)
    _write_json(run_dir / "report.json", report)
    return run_dir


def _seed_ready_paper_gate(vault, slug):
    paper_root = vault / "_epi/raw" / slug
    staging_root = vault / "_epi/staging" / "papers" / slug
    critic_root = paper_root / "critic"
    critic_root.mkdir(parents=True, exist_ok=True)
    mineru_root = paper_root / "mineru"
    image_root = mineru_root / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    _write_json(paper_root / "metadata.json", {"slug": slug, "title": "Ready Paper"})
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nready fixture\n")
    (mineru_root / f"{slug}.md").write_text("# Ready Paper\n\nMethod and experiments.\n", encoding="utf-8")
    (mineru_root / "paper.tex").write_text("\\section{Method}\n", encoding="utf-8")
    (mineru_root / "mineru-manifest.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
    (image_root / "figure-1.png").write_bytes(b"image")
    _write_json(
        critic_root / "critic-quorum.json",
        {
            "stage": "critic-quorum",
            "final_outcome": "pass",
            "reviewers": [
                {"name": "paper-quality-critic", "verdict": "pass"},
                {"name": "peer-review-methods-critic", "verdict": "pass"},
            ],
        },
    )
    _write_json(
        critic_root / "critic-report.json",
        {
            "outcome": "pass",
            "next_action": "stage",
            "hard_rule": "No critic pass, no compiled wiki write.",
            "reviewer_quorum_path": str(critic_root / "critic-quorum.json"),
        },
    )
    staged_source_reader = staging_root / "evidence" / "source-reader.md"
    staged_report = staging_root / "briefs" / "reading-report.md"
    for staged_path in [staged_source_reader, staged_report]:
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_text(f"# {staged_path.stem}\n", encoding="utf-8")
    brief_path = staging_root / "wiki-ingest-brief.json"
    batch_path = vault / "_epi/staging/wiki-batches/pending/wiki-batch-ingest-brief.json"
    wiki_ingest_brief = _build_wiki_ingest_brief(
        slug=slug,
        title="Ready Paper",
        source_reader_target="evidence/source-reader.md",
        reading_report_target="briefs/reading-report.md",
        editorial_summary_text="",
        technical_reading_text="",
        research_notes_text="",
        evidence_map={},
        research_decision={},
        reproduction_plan={},
    )
    _write_json(brief_path, wiki_ingest_brief)
    _write_json(
        batch_path,
        {
            "schema_version": "epi-wiki-batch-ingest-brief-v1",
            "handoff_type": "wiki-skill-batch-distillation",
            "epi_write_scope": "internal-underscore-artifacts-only",
            "formal_routes_suggested": False,
            "paper_slugs": [slug],
            "papers": [{"paper_slug": slug, "wiki_ingest_brief": str(brief_path)}],
        },
    )
    _write_json(
        staging_root / "promotion-plan.json",
        {
            "paper_slug": slug,
            "critic_outcome": "pass",
            "handoff_type": "agent-mediated-wiki-ingest",
            "wiki_write_model": "wiki-skill-batch-distillation",
            "final_page_authority": "wiki-skill-batch-distillation",
            "epi_write_scope": "internal-underscore-artifacts-only",
            "formal_routes_suggested": False,
            "wiki_batch_handoff_required": True,
            "required_wiki_skills": required_wiki_skills(),
            "staged_evidence": [str(staged_source_reader)],
            "staged_reports": [str(staged_report)],
            "wiki_ingest_brief_path": str(brief_path),
            "wiki_batch_ingest_brief_path": str(batch_path),
            "agent_handoff_paths": [str(brief_path), str(batch_path), str(staged_report), str(staged_source_reader)],
            "suggested_route_targets": [],
        },
    )


def _seed_failed_paper_gate(vault, slug):
    _seed_ready_paper_gate(vault, slug)
    paper_root = vault / "_epi/raw" / slug
    critic_root = paper_root / "critic"
    _write_json(
        critic_root / "critic-quorum.json",
        {
            "stage": "critic-quorum",
            "final_outcome": "revise-reader",
            "reviewers": [
                {"name": "paper-quality-critic", "verdict": "revise-reader"},
                {"name": "peer-review-methods-critic", "verdict": "pass"},
            ],
        },
    )
    _write_json(
        critic_root / "critic-report.json",
        {
            "outcome": "revise-reader",
            "next_action": "revise-reader",
            "hard_rule": "No critic pass, no compiled wiki write.",
            "reviewer_quorum_path": str(critic_root / "critic-quorum.json"),
        },
    )


def _seed_unstaged_paper_gate(vault, slug):
    paper_root = vault / "_epi/raw" / slug
    critic_root = paper_root / "critic"
    critic_root.mkdir(parents=True, exist_ok=True)
    _write_json(paper_root / "metadata.json", {"slug": slug, "title": "Unstaged Paper"})
    _write_json(
        critic_root / "critic-quorum.json",
        {
            "stage": "critic-quorum",
            "final_outcome": "pass",
            "reviewers": [
                {"name": "paper-quality-critic", "verdict": "pass"},
                {"name": "peer-review-methods-critic", "verdict": "pass"},
            ],
        },
    )
    _write_json(
        critic_root / "critic-report.json",
        {
            "outcome": "pass",
            "next_action": "stage",
            "hard_rule": "No critic pass, no compiled wiki write.",
            "reviewer_quorum_path": str(critic_root / "critic-quorum.json"),
        },
    )


def _seed_agent_handoff_paper_gate(vault, slug):
    _seed_ready_paper_gate(vault, slug)


def _run_orchestrator_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def test_report_cli_prints_existing_run_markdown(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    run_dir = _seed_run(
        runs_root,
        "20260528T120000Z-report",
        workflow_type="record-wiki-ingest",
        state="wiki_ingest_recorded",
        status="success",
        paper_slug="paper-a",
    )
    (run_dir / "report.md").write_text("# Existing Report\n\n- status: ok\n", encoding="utf-8")

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "report",
        "--vault",
        str(vault),
        "--run-id",
        "20260528T120000Z-report",
    )

    assert exit_code == 0
    assert output == "# Existing Report\n\n- status: ok\n"


def test_report_cli_json_returns_paths_and_report_payload(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    run_dir = _seed_run(
        runs_root,
        "20260528T121000Z-report",
        workflow_type="promote-to-wiki",
        state="promoted",
        status="success",
        paper_slug="paper-b",
        report_extra={
            "workflow_type": "promote-to-wiki",
            "run_id": "20260528T121000Z-report",
            "zotero_results": {"status": "recorded", "collection": "EPI"},
        },
    )
    (run_dir / "report.md").write_text("# Promotion Report\n", encoding="utf-8")

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "report",
        "--vault",
        str(vault),
        "--run-id",
        "20260528T121000Z-report",
        "--json",
    )

    payload = json.loads(output)
    assert exit_code == 0
    assert payload["run_id"] == "20260528T121000Z-report"
    assert payload["artifacts"]["report"] == str(run_dir / "report.md")
    assert payload["artifacts"]["report_json"] == str(run_dir / "report.json")
    assert payload["artifacts"]["run_state"] == str(run_dir / "run-state.json")
    assert payload["run_state"]["workflow_type"] == "promote-to-wiki"
    assert payload["run_state"]["state"] == "promoted"
    assert payload["report"]["workflow_type"] == "promote-to-wiki"
    assert payload["report"]["zotero_results"]["status"] == "recorded"
    assert payload["markdown"] == "# Promotion Report\n"


def test_report_cli_text_falls_back_to_json_when_markdown_missing(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T122000Z-report",
        workflow_type="dry-run",
        state="completed",
        status="success",
        paper_slug="paper-c",
        report_extra={"workflow_type": "dry-run", "accepted_count": 2},
    )

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "report",
        "--vault",
        str(vault),
        "--run-id",
        "20260528T122000Z-report",
    )

    assert exit_code == 0
    payload = json.loads(output)
    assert payload["workflow_type"] == "dry-run"
    assert payload["accepted_count"] == 2


def test_report_cli_json_allows_markdown_only_report(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    run_dir = vault / "_epi/runs" / "20260528T123000Z-report"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.md").write_text("# Markdown Only\n", encoding="utf-8")

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "report",
        "--vault",
        str(vault),
        "--run-id",
        "20260528T123000Z-report",
        "--json",
    )

    payload = json.loads(output)
    assert exit_code == 0
    assert payload["report"] == {}
    assert payload["run_state"] == {}
    assert payload["markdown"] == "# Markdown Only\n"
    assert payload["artifacts"]["report_json"] is None


def test_report_loader_errors_when_run_dir_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing EPI run directory"):
        load_run_report(tmp_path / "vault", "missing-run")


def test_report_loader_errors_when_report_artifacts_missing(tmp_path):
    vault = tmp_path / "vault"
    (vault / "_epi/runs" / "empty-report-run").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="missing report artifacts"):
        load_run_report(vault, "empty-report-run")


def test_research_queue_cli_actions_puts_paper_gate_before_wiki_ingest_handoff(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    slug = "ready-paper"
    _seed_ready_paper_gate(vault, slug)
    _seed_run(
        runs_root,
        "20260529T110000Z-ready",
        workflow_type="advance-batch",
        state="staging_ready",
        status="waiting_for_human_gate",
        paper_slug=slug,
        next_actions=["run-wiki-ingest-agent"],
        human_gate={"status": "required"},
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--bucket",
        "ready_to_promote",
        "--actions",
        "--json",
        "--vault",
        str(vault),
    )

    payload = json.loads(output)
    actions = payload["items"][0]["recommended_actions"]
    assert exit_code == 0
    assert [action["action"] for action in actions] == [
        "inspect-paper-gate",
        "wiki-ingest-handoff",
        "record-human-approval",
    ]
    assert f"paper-gate --slug {slug}" in actions[0]["command"]
    assert actions[0]["human_gate_required"] is True
    assert f"wiki-ingest-handoff --slug {slug}" in actions[1]["command"]
    assert actions[1]["human_gate_required"] is True
    assert f"record-human-approval --slug {slug}" in actions[2]["command"]
    assert actions[2]["uses"] == "human-approval.json"


def test_research_queue_cli_actions_blocks_promotion_when_current_paper_gate_fails(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    slug = "stale-ready-paper"
    _seed_failed_paper_gate(vault, slug)
    _seed_run(
        runs_root,
        "20260529T111000Z-stale-ready",
        workflow_type="advance-batch",
        state="staging_ready",
        status="waiting_for_human_gate",
        paper_slug=slug,
        next_actions=["run-wiki-ingest-agent"],
        human_gate={"status": "required"},
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--bucket",
        "ready_to_promote",
        "--actions",
        "--json",
        "--vault",
        str(vault),
    )

    payload = json.loads(output)
    item = payload["items"][0]
    actions = item["recommended_actions"]
    assert exit_code == 0
    assert [action["action"] for action in actions] == ["inspect-paper-gate"]
    assert item["paper_gate"]["conclusion"] == "failure"
    assert item["paper_gate"]["failure_checks"] == ["critic-outcome", "critic-quorum"]


def test_research_queue_cli_actions_rechecks_stale_cached_ready_gate(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    slug = "stale-cached-ready-paper"
    _seed_ready_paper_gate(vault, slug)
    _seed_run(
        runs_root,
        "20260529T111500Z-stale-cached-ready",
        workflow_type="advance-batch",
        state="staging_ready",
        status="waiting_for_human_gate",
        paper_slug=slug,
        next_actions=["run-wiki-ingest-agent"],
        human_gate={"status": "required"},
    )
    refresh_run_index(vault)
    cached_queue = json.loads((runs_root / "index.json").read_text(encoding="utf-8"))["research_queue"]
    assert cached_queue["ready_to_promote"][0]["paper_gate"]["conclusion"] == "action_required"
    assert cached_queue["ready_to_promote"][0]["paper_gate"]["action_required_checks"] == ["human-approval"]

    _seed_failed_paper_gate(vault, slug)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--bucket",
        "ready_to_promote",
        "--actions",
        "--json",
        "--vault",
        str(vault),
    )

    payload = json.loads(output)
    item = payload["items"][0]
    actions = item["recommended_actions"]
    assert exit_code == 0
    assert item["paper_gate"]["conclusion"] == "failure"
    assert item["paper_gate"]["failure_checks"] == ["critic-outcome", "critic-quorum"]
    assert [action["action"] for action in actions] == ["inspect-paper-gate"]


def test_research_queue_cli_actions_blocks_promotion_when_gate_requires_non_human_action(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    slug = "unstaged-ready-paper"
    _seed_unstaged_paper_gate(vault, slug)
    _seed_run(
        runs_root,
        "20260529T112000Z-stale-ready",
        workflow_type="advance-batch",
        state="staging_ready",
        status="waiting_for_human_gate",
        paper_slug=slug,
        next_actions=["promote-to-wiki"],
        human_gate={"status": "required"},
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--bucket",
        "ready_to_promote",
        "--actions",
        "--json",
        "--vault",
        str(vault),
    )

    payload = json.loads(output)
    item = payload["items"][0]
    actions = item["recommended_actions"]
    assert exit_code == 0
    assert [action["action"] for action in actions] == ["inspect-paper-gate"]
    assert item["paper_gate"]["conclusion"] == "action_required"
    assert item["paper_gate"]["action_required_checks"] == ["promotion-plan"]


def test_research_queue_cli_actions_points_agent_handoff_to_handoff_command(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    slug = "agent-handoff-paper"
    _seed_agent_handoff_paper_gate(vault, slug)
    _seed_run(
        runs_root,
        "20260529T112500Z-agent-handoff",
        workflow_type="advance-batch",
        state="staging_ready",
        status="waiting_for_human_gate",
        paper_slug=slug,
        next_actions=["run-wiki-ingest-agent"],
        human_gate={"status": "required"},
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--bucket",
        "ready_to_promote",
        "--actions",
        "--json",
        "--vault",
        str(vault),
    )

    payload = json.loads(output)
    actions = payload["items"][0]["recommended_actions"]
    assert exit_code == 0
    assert [action["action"] for action in actions] == [
        "inspect-paper-gate",
        "wiki-ingest-handoff",
        "record-human-approval",
    ]
    assert f"wiki-ingest-handoff --slug {slug}" in actions[1]["command"]
    assert actions[1]["uses"] == "wiki-ingest-brief.json"
    assert "read target vault AGENTS.md and _meta/*" in actions[1]["checklist"]
    assert f"record-human-approval --slug {slug}" in actions[2]["command"]
    assert "--scope run-wiki-ingest-agent" in actions[2]["command"]
    assert actions[2]["uses"] == "human-approval.json"


def test_research_queue_cli_actions_points_approved_agent_handoff_to_trigger_command(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    slug = "approved-agent-handoff-paper"
    _seed_agent_handoff_paper_gate(vault, slug)
    _seed_run(
        runs_root,
        "20260529T112700Z-agent-handoff",
        workflow_type="advance-batch",
        state="staging_ready",
        status="waiting_for_human_gate",
        paper_slug=slug,
        next_actions=["run-wiki-ingest-agent"],
        human_gate={"status": "required"},
    )
    refresh_run_index(vault)
    record_human_approval(
        vault,
        slug,
        approved_by="codex-test",
        scope="run-wiki-ingest-agent",
    )

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--bucket",
        "ready_to_promote",
        "--actions",
        "--json",
        "--vault",
        str(vault),
    )

    payload = json.loads(output)
    actions = payload["items"][0]["recommended_actions"]
    assert exit_code == 0
    assert payload["items"][0]["reason"] == "wiki ingest agent is approved and ready"
    assert [action["action"] for action in actions] == [
        "inspect-paper-gate",
        "wiki-ingest-handoff",
        "wiki-ingest-trigger",
    ]
    assert f"wiki-ingest-trigger --slug {slug}" in actions[2]["command"]
    assert actions[2]["uses"] == "wiki-agent-trigger.json"
    assert actions[2]["human_gate_required"] is False


def test_research_queue_cli_actions_can_resume_from_human_approval_run(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    slug = "approval-only-agent-handoff-paper"
    _seed_agent_handoff_paper_gate(vault, slug)
    record_human_approval(
        vault,
        slug,
        approved_by="codex-test",
        scope="run-wiki-ingest-agent",
    )

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--bucket",
        "ready_to_promote",
        "--actions",
        "--json",
        "--vault",
        str(vault),
    )

    payload = json.loads(output)
    actions = payload["items"][0]["recommended_actions"]
    assert exit_code == 0
    assert payload["items"][0]["paper_slug"] == slug
    assert payload["items"][0]["reason"] == "wiki ingest agent is approved and ready"
    assert [action["action"] for action in actions] == [
        "inspect-paper-gate",
        "wiki-ingest-handoff",
        "wiki-ingest-trigger",
    ]


def test_research_queue_does_not_promote_when_gate_action_required_checks_are_missing():
    assert not _paper_gate_allows_promotion(
        {
            "paper_slug": "malformed-gate-paper",
            "paper_gate": {
                "conclusion": "action_required",
                "next_action": "promote-to-wiki",
                "failure_checks": [],
                "action_required_checks": [],
            },
        }
    )


def test_runs_query_failed_filters_failed_runs_only(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T100000Z-promote",
        workflow_type="promote-to-wiki",
        state="promoted",
        status="succeeded",
        paper_slug="paper-a",
    )
    _seed_run(
        runs_root,
        "20260528T101000Z-recritic",
        workflow_type="recritic",
        state="critic_failed",
        status="failed",
        paper_slug="paper-b",
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(monkeypatch, capsys, "runs-query", "--vault", str(vault), "--failed")

    assert exit_code == 0
    assert "20260528T101000Z-recritic" in output
    assert "20260528T100000Z-promote" not in output


def test_runs_query_human_gate_filters_pending_runs(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T102000Z-ranked",
        workflow_type="advance-ranked",
        state="staging_ready",
        status="succeeded",
        paper_slug="paper-c",
        next_actions=["promote-after-approval"],
        human_gate={"status": "required"},
    )
    _seed_run(
        runs_root,
        "20260528T103000Z-repair",
        workflow_type="redo-read",
        state="reader_regenerated",
        status="succeeded",
        paper_slug="paper-d",
        next_actions=["recritic"],
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(monkeypatch, capsys, "runs-query", "--vault", str(vault), "--human-gate")

    assert exit_code == 0
    assert "20260528T102000Z-ranked" in output
    assert "20260528T103000Z-repair" not in output


def test_runs_query_latest_success_returns_only_latest_successful_workflow_run(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T090000Z-promote-old",
        workflow_type="promote-to-wiki",
        state="promoted",
        status="succeeded",
        paper_slug="paper-old",
    )
    _seed_run(
        runs_root,
        "20260528T110000Z-promote-new",
        workflow_type="promote-to-wiki",
        state="promoted",
        status="succeeded",
        paper_slug="paper-new",
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "runs-query",
        "--vault",
        str(vault),
        "--latest-success",
        "promote-to-wiki",
    )

    assert exit_code == 0
    assert "20260528T110000Z-promote-new" in output
    assert "20260528T090000Z-promote-old" not in output


def test_runs_query_workflow_filters_recent_runs(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T100000Z-ranked",
        workflow_type="advance-ranked",
        state="staging_ready",
        status="succeeded",
        paper_slug="paper-a",
    )
    _seed_run(
        runs_root,
        "20260528T101000Z-batch",
        workflow_type="advance-batch",
        state="critic_failed",
        status="failed",
        paper_slug="paper-b",
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "runs-query",
        "--vault",
        str(vault),
        "--workflow",
        "advance-ranked",
    )

    assert exit_code == 0
    assert "20260528T100000Z-ranked" in output
    assert "20260528T101000Z-batch" not in output


def test_research_queue_cli_filters_bucket_and_shows_checks(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T140000Z-ready",
        workflow_type="advance-batch",
        state="staged",
        status="succeeded",
        paper_slug="ready-paper",
        next_actions=["promote-to-wiki"],
        human_gate={"status": "required"},
    )
    _seed_run(
        runs_root,
        "20260528T142000Z-recritic",
        workflow_type="redo-read-recritic",
        state="critic_passed",
        status="succeeded",
        paper_slug="warning-paper",
        next_actions=["stage the paper for promotion review"],
        report_extra={
            "revision_delta": {
                "after": {
                    "blocking_count": 0,
                    "warning_count": 1,
                    "blocking_checks": [],
                    "warning_checks": ["engineering_reproducibility"],
                },
                "remaining_blocking_checks": [],
                "remaining_warning_checks": ["engineering_reproducibility"],
            },
        },
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--vault",
        str(vault),
        "--bucket",
        "reproducibility_caveats",
    )

    assert exit_code == 0
    assert "EPI Research Queue - reproducibility_caveats" in output
    assert "warning-paper" in output
    assert "engineering_reproducibility" in output
    assert "ready-paper" not in output


def test_research_queue_cli_json_returns_bucket_items(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T141000Z-repair",
        workflow_type="advance-batch",
        state="critic_failed",
        status="failed",
        paper_slug=None,
        next_actions=["revise-reader"],
        report_extra={
            "reader_revision_plans": [
                {
                    "slug": "repair-paper",
                    "title": "Repair Paper",
                    "next_action": "revise-reader",
                    "blocking_count": 2,
                    "warning_count": 1,
                }
            ],
        },
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--vault",
        str(vault),
        "--bucket",
        "needs_reader_repair",
        "--json",
    )

    payload = json.loads(output)
    assert exit_code == 0
    assert payload["bucket"] == "needs_reader_repair"
    assert payload["items"][0]["paper_slug"] == "repair-paper"
    assert payload["items"][0]["title"] == "Repair Paper"


def test_research_queue_cli_actions_suggest_reader_repair_command(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T141000Z-repair",
        workflow_type="advance-batch",
        state="critic_failed",
        status="failed",
        paper_slug=None,
        next_actions=["revise-reader"],
        report_extra={
            "reader_revision_plans": [
                {
                    "slug": "repair-paper",
                    "title": "Repair Paper",
                    "next_action": "revise-reader",
                    "blocking_count": 2,
                    "warning_count": 1,
                    "plan_path": str(vault / "_epi/raw" / "repair-paper" / "critic" / "reader-revision-plan.json"),
                }
            ],
        },
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--vault",
        str(vault),
        "--bucket",
        "needs_reader_repair",
        "--actions",
    )

    assert exit_code == 0
    assert "action: redo-read-recritic" in output
    assert "redo-read --vault" in output
    assert "--slug repair-paper" in output
    assert "--from-revision-plan --recritic" in output


def test_research_queue_cli_json_actions_describe_reproduction_plan(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    runs_root = vault / "_epi/runs"
    _seed_run(
        runs_root,
        "20260528T142000Z-recritic",
        workflow_type="redo-read-recritic",
        state="critic_passed",
        status="succeeded",
        paper_slug="warning-paper",
        next_actions=["stage the paper for promotion review"],
        report_extra={
            "revision_delta": {
                "after": {
                    "blocking_count": 0,
                    "warning_count": 1,
                    "blocking_checks": [],
                    "warning_checks": ["engineering_reproducibility"],
                },
                "remaining_blocking_checks": [],
                "remaining_warning_checks": ["engineering_reproducibility"],
            },
        },
    )
    refresh_run_index(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "research-queue",
        "--vault",
        str(vault),
        "--bucket",
        "reproducibility_caveats",
        "--actions",
        "--json",
    )

    payload = json.loads(output)
    action = payload["items"][0]["recommended_actions"][0]
    assert exit_code == 0
    assert action["action"] == "review-reproducibility-caveats"
    assert action["human_gate_required"] is True
    assert "code" in action["checklist"]
    assert "hardware" in action["checklist"]


def test_research_agenda_cli_is_not_available(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"

    try:
        _run_orchestrator_cli(monkeypatch, capsys, "research-agenda", "--vault", str(vault))
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("research-agenda should not be available after narrowing EPI scope")
