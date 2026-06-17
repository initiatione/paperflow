import json

from paper_source.run_index import refresh_run_index
from paper_source.stage_wiki import _build_wiki_ingest_brief
from paper_source.wiki_contracts import required_wiki_skills


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_run(runs_root, run_id, run_state=None, report=None):
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if run_state is not None:
        _write_json(run_dir / "run-state.json", run_state)
    if report is not None:
        _write_json(run_dir / "report.json", report)
    return run_dir


def _seed_ready_paper_gate(vault_path, slug):
    paper_root = vault_path / "_paper_source/raw" / slug
    staging_root = vault_path / "_paper_source/staging" / "papers" / slug
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
    batch_path = vault_path / "_paper_source/staging/wiki-batches/pending/wiki-batch-ingest-brief.json"
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
            "schema_version": "paper-source-wiki-batch-ingest-brief-v1",
            "handoff_type": "wiki-skill-batch-distillation",
            "paper_source_write_scope": "internal-underscore-artifacts-only",
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
            "paper_source_write_scope": "internal-underscore-artifacts-only",
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


def _seed_legacy_compiled_target_failure(vault_path, slug):
    _seed_ready_paper_gate(vault_path, slug)
    staging_root = vault_path / "_paper_source/staging" / "papers" / slug
    plan_path = staging_root / "promotion-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for key in [
        "handoff_type",
        "wiki_write_model",
        "final_page_authority",
        "paper_source_write_scope",
        "formal_routes_suggested",
        "wiki_batch_handoff_required",
        "required_wiki_skills",
        "wiki_ingest_brief_path",
        "wiki_batch_ingest_brief_path",
        "agent_handoff_paths",
        "suggested_route_targets",
    ]:
        plan.pop(key, None)
    plan["staged_reference"] = plan.pop("staged_evidence")[0]
    plan["compiled_targets"] = [
        f"references/{slug}.md",
        "../unsafe.md",
    ]
    _write_json(plan_path, plan)


def test_refresh_run_index_enriches_ready_queue_with_paper_gate(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    slug = "ready-paper"
    _seed_ready_paper_gate(vault_path, slug)
    _seed_run(
        runs_root,
        "20260529T100000Z-ready",
        run_state={
            "run_id": "20260529T100000Z-ready",
            "workflow_type": "advance-batch",
            "state": "staging_ready",
            "status": "waiting_for_human_gate",
            "paper_slug": slug,
            "started_at": "2026-05-29T10:00:00Z",
            "finished_at": "2026-05-29T10:05:00Z",
        },
        report={
            "next_actions": ["run-wiki-ingest-agent"],
            "human_gate": {"status": "required"},
        },
    )

    index_payload = refresh_run_index(vault_path)

    item = index_payload["research_queue"]["ready_to_promote"][0]
    assert item["paper_gate"] == {
        "status": "waiting_for_human_gate",
        "conclusion": "action_required",
        "next_action": "run-wiki-ingest-agent",
        "action_required_checks": ["human-approval"],
        "failure_checks": [],
    }


def test_refresh_run_index_marks_ready_queue_reason_blocked_when_current_paper_gate_fails(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    slug = "unsafe-ready-paper"
    _seed_legacy_compiled_target_failure(vault_path, slug)
    _seed_run(
        runs_root,
        "20260529T101000Z-stale-ready",
        run_state={
            "run_id": "20260529T101000Z-stale-ready",
            "workflow_type": "advance-batch",
            "state": "staging_ready",
            "status": "waiting_for_human_gate",
            "paper_slug": slug,
            "started_at": "2026-05-29T10:10:00Z",
            "finished_at": "2026-05-29T10:15:00Z",
        },
        report={
            "next_actions": ["run-wiki-ingest-agent"],
            "human_gate": {"status": "required"},
        },
    )

    index_payload = refresh_run_index(vault_path)

    item = index_payload["research_queue"]["ready_to_promote"][0]
    assert item["reason"] == "paper gate blocked by failed checks"
    assert item["paper_gate"]["conclusion"] == "failure"
    assert item["paper_gate"]["failure_checks"] == ["compiled-targets"]


def test_refresh_run_index_writes_sorted_index_entries(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T090000Z-repair",
        run_state={
            "run_id": "20260528T090000Z-repair",
            "workflow_type": "redo-read",
            "state": "reader_regenerated",
            "status": "succeeded",
            "paper_slug": "paper-b",
            "started_at": "2026-05-28T09:00:00Z",
            "finished_at": "2026-05-28T09:05:00Z",
        },
        report={
            "next_actions": ["recritic"],
            "human_gate": None,
        },
    )
    _seed_run(
        runs_root,
        "20260528T100000Z-promote",
        run_state={
            "run_id": "20260528T100000Z-promote",
            "workflow_type": "run-wiki-ingest-agent",
            "state": "promoted",
            "status": "succeeded",
            "paper_slug": "paper-a",
            "started_at": "2026-05-28T10:00:00Z",
            "finished_at": "2026-05-28T10:15:00Z",
        },
        report={
            "next_actions": ["inspect-promoted-pages"],
            "human_gate": {"status": "approved", "approved_by": "codex-test"},
        },
    )
    _seed_run(
        runs_root,
        "20260528T093000Z-batch",
        run_state={
            "run_id": "20260528T093000Z-batch",
            "workflow_type": "advance-batch",
            "state": "critic_failed",
            "status": "failed",
            "paper_slug": None,
            "started_at": "2026-05-28T09:30:00Z",
            "finished_at": "2026-05-28T09:40:00Z",
        },
    )
    _seed_run(
        runs_root,
        "20260528T103000Z-ranked",
        run_state={
            "run_id": "20260528T103000Z-ranked",
            "workflow_type": "advance-ranked",
            "state": "staging_ready",
            "status": "succeeded",
            "paper_slug": "paper-c",
            "started_at": "2026-05-28T10:30:00Z",
            "finished_at": "2026-05-28T10:35:00Z",
        },
        report={
            "next_actions": ["await-human-approval"],
            "human_gate": {"status": "pending"},
        },
    )
    _seed_run(
        runs_root,
        "20260528T110000Z-report-only",
        report={
            "next_actions": ["should-not-crash"],
            "human_gate": None,
        },
    )

    refresh_run_index(vault_path)

    index_payload = json.loads((runs_root / "index.json").read_text(encoding="utf-8"))
    entries = index_payload["runs"]
    assert index_payload["summary"] == {
        "total_runs": 4,
        "workflow_counts": {
            "advance-batch": 1,
            "advance-ranked": 1,
            "run-wiki-ingest-agent": 1,
            "redo-read": 1,
        },
        "status_counts": {
            "failed": 1,
            "succeeded": 3,
        },
        "human_gate_pending_count": 1,
        "failed_run_count": 1,
    }
    assert [entry["run_id"] for entry in index_payload["latest_failures"]] == [
        "20260528T093000Z-batch",
    ]
    assert [entry["run_id"] for entry in index_payload["latest_human_gate_pending"]] == [
        "20260528T103000Z-ranked",
    ]
    assert index_payload["latest_success_by_workflow"] == {
        "advance-ranked": {
            "run_id": "20260528T103000Z-ranked",
            "workflow_type": "advance-ranked",
            "state": "staging_ready",
            "status": "succeeded",
            "paper_slug": "paper-c",
            "started_at": "2026-05-28T10:30:00Z",
            "finished_at": "2026-05-28T10:35:00Z",
            "next_actions": ["await-human-approval"],
            "human_gate": {"status": "pending"},
        },
        "run-wiki-ingest-agent": {
            "run_id": "20260528T100000Z-promote",
            "workflow_type": "run-wiki-ingest-agent",
            "state": "promoted",
            "status": "succeeded",
            "paper_slug": "paper-a",
            "started_at": "2026-05-28T10:00:00Z",
            "finished_at": "2026-05-28T10:15:00Z",
            "next_actions": ["inspect-promoted-pages"],
            "human_gate": {"status": "approved", "approved_by": "codex-test"},
        },
        "redo-read": {
            "run_id": "20260528T090000Z-repair",
            "workflow_type": "redo-read",
            "state": "reader_regenerated",
            "status": "succeeded",
            "paper_slug": "paper-b",
            "started_at": "2026-05-28T09:00:00Z",
            "finished_at": "2026-05-28T09:05:00Z",
            "next_actions": ["recritic"],
            "human_gate": None,
        },
    }
    assert [entry["run_id"] for entry in entries] == [
        "20260528T103000Z-ranked",
        "20260528T100000Z-promote",
        "20260528T093000Z-batch",
        "20260528T090000Z-repair",
    ]

    assert entries[1] == {
        "run_id": "20260528T100000Z-promote",
        "workflow_type": "run-wiki-ingest-agent",
        "state": "promoted",
        "status": "succeeded",
        "paper_slug": "paper-a",
        "started_at": "2026-05-28T10:00:00Z",
        "finished_at": "2026-05-28T10:15:00Z",
        "next_actions": ["inspect-promoted-pages"],
        "human_gate": {"status": "approved", "approved_by": "codex-test"},
    }
    assert entries[2]["next_actions"] == []
    assert entries[2]["human_gate"] is None


def test_refresh_run_index_writes_dashboard_and_skips_broken_runs(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T120000Z-ranked",
        run_state={
            "run_id": "20260528T120000Z-ranked",
            "workflow_type": "advance-ranked",
            "state": "staging_ready",
            "status": "succeeded",
            "paper_slug": "paper-c",
            "started_at": "2026-05-28T12:00:00Z",
            "finished_at": "2026-05-28T12:08:00Z",
        },
        report={
            "next_actions": ["run-wiki-ingest-agent"],
            "human_gate": {"status": "required"},
        },
    )
    _seed_run(
        runs_root,
        "20260528T115000Z-recritic",
        run_state={
            "run_id": "20260528T115000Z-recritic",
            "workflow_type": "recritic",
            "state": "critic_failed",
            "status": "failed",
            "paper_slug": "paper-b",
            "started_at": "2026-05-28T11:50:00Z",
            "finished_at": "2026-05-28T11:55:00Z",
        },
        report={
            "next_actions": [],
            "human_gate": None,
        },
    )
    _seed_run(
        runs_root,
        "20260528T113000Z-promote",
        run_state={
            "run_id": "20260528T113000Z-promote",
            "workflow_type": "run-wiki-ingest-agent",
            "state": "promoted",
            "status": "succeeded",
            "paper_slug": "paper-a",
            "started_at": "2026-05-28T11:30:00Z",
            "finished_at": "2026-05-28T11:35:00Z",
        },
        report={
            "next_actions": ["inspect-promoted-pages"],
            "human_gate": None,
        },
    )
    broken_dir = runs_root / "broken-run"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "run-state.json").write_text("{not-json", encoding="utf-8")

    refresh_run_index(vault_path)

    dashboard_text = (runs_root / "dashboard.md").read_text(encoding="utf-8")
    failures_text = (runs_root / "dashboard-failures.md").read_text(encoding="utf-8")
    human_gate_text = (runs_root / "dashboard-human-gate.md").read_text(encoding="utf-8")
    success_text = (runs_root / "dashboard-recent-success.md").read_text(encoding="utf-8")
    assert dashboard_text.startswith("# Paper Source Run Dashboard")
    assert "## Summary" in dashboard_text
    assert "## Needs Attention" in dashboard_text
    assert "## Recent Failures" in dashboard_text
    assert "## Pending Human Gate" in dashboard_text
    assert "## Latest Success By Workflow" in dashboard_text
    assert "## Runs By Workflow" in dashboard_text
    assert "## Recent Runs" in dashboard_text
    assert "- total runs: 3" in dashboard_text
    assert "- advance-ranked: 1" in dashboard_text
    assert "- run-wiki-ingest-agent: 1" in dashboard_text
    assert "- recritic: 1" in dashboard_text

    needs_attention = dashboard_text.split("## Needs Attention", 1)[1].split("## Runs By Workflow", 1)[0]
    assert "20260528T120000Z-ranked" in needs_attention
    assert "20260528T115000Z-recritic" in needs_attention
    assert "20260528T113000Z-promote" in needs_attention

    recent_failures = dashboard_text.split("## Recent Failures", 1)[1].split("## Pending Human Gate", 1)[0]
    assert "20260528T115000Z-recritic" in recent_failures
    assert "20260528T120000Z-ranked" not in recent_failures

    pending_human_gate = dashboard_text.split("## Pending Human Gate", 1)[1].split("## Latest Success By Workflow", 1)[0]
    assert "20260528T120000Z-ranked" in pending_human_gate
    assert "20260528T115000Z-recritic" not in pending_human_gate

    latest_success_by_workflow = dashboard_text.split("## Latest Success By Workflow", 1)[1].split("## Runs By Workflow", 1)[0]
    assert "advance-ranked" in latest_success_by_workflow
    assert "run-wiki-ingest-agent" in latest_success_by_workflow
    assert latest_success_by_workflow.index("20260528T120000Z-ranked") < latest_success_by_workflow.index("20260528T113000Z-promote")

    recent_runs = dashboard_text.split("## Recent Runs", 1)[1]
    assert recent_runs.index("20260528T120000Z-ranked") < recent_runs.index("20260528T115000Z-recritic")
    assert recent_runs.index("20260528T115000Z-recritic") < recent_runs.index("20260528T113000Z-promote")
    assert "broken-run" not in dashboard_text

    assert failures_text.startswith("# Paper Source Failed Runs")
    assert "20260528T115000Z-recritic" in failures_text
    assert "20260528T120000Z-ranked" not in failures_text
    assert "20260528T113000Z-promote" not in failures_text

    assert human_gate_text.startswith("# Paper Source Human Gate Runs")
    assert "20260528T120000Z-ranked" in human_gate_text
    assert "20260528T115000Z-recritic" not in human_gate_text
    assert "20260528T113000Z-promote" not in human_gate_text

    assert success_text.startswith("# Paper Source Recent Successful Runs")
    assert success_text.index("20260528T120000Z-ranked") < success_text.index("20260528T113000Z-promote")
    assert "20260528T115000Z-recritic" not in success_text


def test_refresh_run_index_surfaces_research_decisions(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T121500Z-recritic",
        run_state={
            "run_id": "20260528T121500Z-recritic",
            "workflow_type": "recritic",
            "state": "critic_failed",
            "status": "failed",
            "paper_slug": "embodied-control",
            "started_at": "2026-05-28T12:15:00Z",
            "finished_at": "2026-05-28T12:18:00Z",
        },
        report={
            "next_actions": ["revise-reader"],
            "human_gate": None,
            "research_decisions": [
                {
                    "slug": "embodied-control",
                    "title": "Embodied Control for Mobile Robots",
                    "recommendation": "revise-reader",
                    "next_action": "revise-reader",
                    "role_verdicts": {
                        "nature-sci-editor": "pass",
                        "peer-reviewer": "fail",
                        "senior-domain-researcher": "pass",
                    },
                }
            ],
        },
    )

    index_payload = refresh_run_index(vault_path)
    dashboard_text = (runs_root / "dashboard.md").read_text(encoding="utf-8")

    entry = index_payload["runs"][0]
    assert entry["research_decisions"][0]["recommendation"] == "revise-reader"
    assert entry["research_decisions"][0]["role_verdicts"]["peer-reviewer"] == "fail"
    assert "decision: embodied-control -> revise-reader / revise-reader" in dashboard_text


def test_refresh_run_index_surfaces_zotero_results_in_index_and_dashboard(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T122000Z-record-wiki",
        run_state={
            "run_id": "20260528T122000Z-record-wiki",
            "workflow_type": "record-wiki-ingest",
            "state": "wiki_ingest_recorded",
            "status": "success",
            "paper_slug": "paper-a",
            "started_at": "2026-05-28T12:20:00Z",
            "finished_at": "2026-05-28T12:21:00Z",
        },
        report={
            "next_actions": ["review-recorded-wiki-pages"],
            "human_gate": {"status": "approved", "approved_by": "codex-test"},
            "zotero_results": {
                "status": "recorded",
                "collection": "Reading Lab",
                "wiki_ingest": {"final_wiki_pages": [{"relative_path": "papers/paper-a.md"}]},
            },
        },
    )
    _seed_run(
        runs_root,
        "20260528T121000Z-promote",
        run_state={
            "run_id": "20260528T121000Z-promote",
            "workflow_type": "run-wiki-ingest-agent",
            "state": "promoted",
            "status": "success",
            "paper_slug": "paper-b",
            "started_at": "2026-05-28T12:10:00Z",
            "finished_at": "2026-05-28T12:11:00Z",
            "zotero_results": {
                "status": "skipped",
                "reason": "zotero_disabled",
                "collection": "Paper Source",
            },
        },
        report={"next_actions": []},
    )

    index_payload = refresh_run_index(vault_path)
    dashboard_text = (runs_root / "dashboard.md").read_text(encoding="utf-8")
    success_text = (runs_root / "dashboard-recent-success.md").read_text(encoding="utf-8")

    assert index_payload["runs"][0]["zotero_results"]["status"] == "recorded"
    assert index_payload["runs"][0]["zotero_results"]["collection"] == "Reading Lab"
    assert index_payload["runs"][1]["zotero_results"]["reason"] == "zotero_disabled"
    assert "zotero: recorded | collection=Reading Lab" in dashboard_text
    assert "zotero: skipped | collection=Paper Source | reason=zotero_disabled" in dashboard_text
    assert "zotero: recorded | collection=Reading Lab" in success_text


def test_refresh_run_index_writes_research_queue_from_decisions_revision_plans_and_delta(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T140000Z-promote-ready",
        run_state={
            "run_id": "20260528T140000Z-promote-ready",
            "workflow_type": "advance-batch",
            "state": "staged",
            "status": "succeeded",
            "paper_slug": "ready-paper",
            "started_at": "2026-05-28T14:00:00Z",
            "finished_at": "2026-05-28T14:05:00Z",
        },
        report={
            "next_actions": ["run-wiki-ingest-agent"],
            "human_gate": {"status": "required"},
        },
    )
    _seed_run(
        runs_root,
        "20260528T141000Z-repair",
        run_state={
            "run_id": "20260528T141000Z-repair",
            "workflow_type": "advance-batch",
            "state": "critic_failed",
            "status": "failed",
            "paper_slug": None,
            "started_at": "2026-05-28T14:10:00Z",
            "finished_at": "2026-05-28T14:12:00Z",
        },
        report={
            "next_actions": ["revise-reader"],
            "reader_revision_plans": [
                {
                    "slug": "repair-paper",
                    "title": "Repair Paper",
                    "next_action": "revise-reader",
                    "blocking_count": 2,
                    "warning_count": 1,
                    "plan_path": "D:\\vault\\_paper_source/raw\\papers\\repair-paper\\critic\\reader-revision-plan.json",
                }
            ],
            "research_decisions": [
                {
                    "slug": "repair-paper",
                    "title": "Repair Paper",
                    "recommendation": "revise-reader",
                    "next_action": "revise-reader",
                    "role_verdicts": {"peer-reviewer": "fail"},
                }
            ],
        },
    )
    _seed_run(
        runs_root,
        "20260528T142000Z-recritic",
        run_state={
            "run_id": "20260528T142000Z-recritic",
            "workflow_type": "redo-read-recritic",
            "state": "critic_passed",
            "status": "succeeded",
            "paper_slug": "warning-paper",
            "started_at": "2026-05-28T14:20:00Z",
            "finished_at": "2026-05-28T14:22:00Z",
        },
        report={
            "next_actions": ["stage the paper for promotion review"],
            "revision_delta": {
                "before": {
                    "blocking_count": 1,
                    "warning_count": 1,
                    "blocking_checks": ["benchmark_integrity"],
                    "warning_checks": ["engineering_reproducibility"],
                },
                "after": {
                    "blocking_count": 0,
                    "warning_count": 1,
                    "blocking_checks": [],
                    "warning_checks": ["engineering_reproducibility"],
                },
                "resolved_blocking_checks": ["benchmark_integrity"],
                "remaining_blocking_checks": [],
                "remaining_warning_checks": ["engineering_reproducibility"],
            },
        },
    )

    index_payload = refresh_run_index(vault_path)

    queue_json = json.loads((runs_root / "research-queue.json").read_text(encoding="utf-8"))
    queue_md = (runs_root / "research-queue.md").read_text(encoding="utf-8")
    dashboard_text = (runs_root / "dashboard.md").read_text(encoding="utf-8")

    assert index_payload["research_queue"]["ready_to_promote"][0]["paper_slug"] == "ready-paper"
    assert index_payload["research_queue"]["needs_reader_repair"][0]["paper_slug"] == "repair-paper"
    assert index_payload["research_queue"]["warning_only"][0]["paper_slug"] == "warning-paper"
    assert index_payload["research_queue"]["reproducibility_caveats"][0]["paper_slug"] == "warning-paper"
    assert queue_json == index_payload["research_queue"]
    assert "# Paper Source Research Queue" in queue_md
    assert "## Ready To Promote" in queue_md
    assert "ready-paper" in queue_md
    assert "repair-paper" in queue_md
    assert "engineering_reproducibility" in queue_md
    assert "## Research Queue" in dashboard_text
    assert "ready_to_promote: 1" in dashboard_text
    assert "needs_reader_repair: 1" in dashboard_text
    assert "reproducibility_caveats: 1" in dashboard_text


def test_refresh_run_index_treats_waiting_human_gate_as_ready_not_failed(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T144000Z-waiting-promote",
        run_state={
            "run_id": "20260528T144000Z-waiting-promote",
            "workflow_type": "advance-ranked",
            "state": "staging_ready",
            "status": "waiting_for_human_gate",
            "paper_slug": "waiting-paper",
            "started_at": "2026-05-28T14:40:00Z",
            "finished_at": "2026-05-28T14:45:00Z",
        },
        report={
            "next_actions": ["run-wiki-ingest-agent"],
            "human_gate": {"status": "required"},
        },
    )

    index_payload = refresh_run_index(vault_path)

    assert index_payload["summary"]["failed_run_count"] == 0
    assert index_payload["latest_failures"] == []
    assert index_payload["latest_human_gate_pending"][0]["paper_slug"] == "waiting-paper"
    assert index_payload["research_queue"]["ready_to_promote"][0]["paper_slug"] == "waiting-paper"


def test_refresh_run_index_adds_reproducibility_caveat_items_to_research_queue(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T143000Z-reproduction",
        run_state={
            "run_id": "20260528T143000Z-reproduction",
            "workflow_type": "advance-batch",
            "state": "critic_passed",
            "status": "succeeded",
            "paper_slug": "repro-paper",
            "started_at": "2026-05-28T14:30:00Z",
            "finished_at": "2026-05-28T14:35:00Z",
        },
        report={
            "next_actions": ["stage"],
            "reproduction_plans": [
                {
                    "slug": "repro-paper",
                    "title": "Repro Paper",
                    "plan_path": "D:\\vault\\_paper_source/raw\\papers\\repro-paper\\critic\\reproduction-plan.json",
                    "next_action": "prepare-reproduction-plan",
                    "missing_count": 2,
                    "human_gate_required": True,
                }
            ],
        },
    )

    index_payload = refresh_run_index(vault_path)

    item = index_payload["research_queue"]["reproducibility_caveats"][0]
    assert item["paper_slug"] == "repro-paper"
    assert item["title"] == "Repro Paper"
    assert item["source"].endswith("reproduction-plan.json")
    assert item["reason"] == "reproducibility caveats need evidence review"


def test_refresh_run_index_does_not_write_research_agenda_outputs(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T150000Z-ready",
        run_state={
            "run_id": "20260528T150000Z-ready",
            "workflow_type": "advance-batch",
            "state": "staged",
            "status": "succeeded",
            "paper_slug": "ready-paper",
            "started_at": "2026-05-28T15:00:00Z",
            "finished_at": "2026-05-28T15:05:00Z",
        },
        report={
            "next_actions": ["run-wiki-ingest-agent"],
            "human_gate": {"status": "required"},
            "research_decisions": [
                {
                    "slug": "ready-paper",
                    "title": "Ready Paper",
                    "recommendation": "stage-for-promotion-review",
                    "next_action": "stage",
                    "role_verdicts": {
                        "nature-sci-editor": "pass",
                        "peer-reviewer": "pass",
                        "senior-domain-researcher": "pass",
                    },
                }
            ],
        },
    )
    _seed_run(
        runs_root,
        "20260528T151000Z-repair",
        run_state={
            "run_id": "20260528T151000Z-repair",
            "workflow_type": "recritic",
            "state": "critic_failed",
            "status": "failed",
            "paper_slug": "repair-paper",
            "started_at": "2026-05-28T15:10:00Z",
            "finished_at": "2026-05-28T15:12:00Z",
        },
        report={
            "next_actions": ["revise-reader"],
            "reader_revision_plans": [
                {
                    "slug": "repair-paper",
                    "title": "Repair Paper",
                    "next_action": "revise-reader",
                    "blocking_count": 1,
                    "warning_count": 0,
                    "plan_path": "D:\\vault\\_paper_source/raw\\papers\\repair-paper\\critic\\reader-revision-plan.json",
                }
            ],
            "research_decisions": [
                {
                    "slug": "repair-paper",
                    "title": "Repair Paper",
                    "recommendation": "revise-reader",
                    "next_action": "revise-reader",
                    "role_verdicts": {
                        "nature-sci-editor": "pass",
                        "peer-reviewer": "fail",
                        "senior-domain-researcher": "pass",
                    },
                }
            ],
        },
    )
    _seed_run(
        runs_root,
        "20260528T152000Z-repro",
        run_state={
            "run_id": "20260528T152000Z-repro",
            "workflow_type": "advance-batch",
            "state": "critic_passed",
            "status": "succeeded",
            "paper_slug": "repro-paper",
            "started_at": "2026-05-28T15:20:00Z",
            "finished_at": "2026-05-28T15:25:00Z",
        },
        report={
            "next_actions": ["stage"],
            "reproduction_plans": [
                {
                    "slug": "repro-paper",
                    "title": "Repro Paper",
                    "plan_path": "D:\\vault\\_paper_source/raw\\papers\\repro-paper\\critic\\reproduction-plan.json",
                    "next_action": "prepare-reproduction-plan",
                    "missing_count": 2,
                    "human_gate_required": True,
                }
            ],
        },
    )

    index_payload = refresh_run_index(vault_path)

    dashboard_text = (runs_root / "dashboard.md").read_text(encoding="utf-8")

    assert "research_agenda" not in index_payload
    assert not (runs_root / "research-agenda.json").exists()
    assert not (runs_root / "research-agenda.md").exists()
    assert "## Research Agenda" not in dashboard_text
    assert index_payload["research_queue"]["ready_to_promote"][0]["paper_slug"] == "ready-paper"
    assert index_payload["research_queue"]["needs_reader_repair"][0]["paper_slug"] == "repair-paper"
    assert index_payload["research_queue"]["reproducibility_caveats"][0]["paper_slug"] == "repro-paper"


def test_refresh_run_index_writes_empty_filtered_views_when_no_matches(tmp_path):
    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    _seed_run(
        runs_root,
        "20260528T130000Z-promote",
        run_state={
            "run_id": "20260528T130000Z-promote",
            "workflow_type": "run-wiki-ingest-agent",
            "state": "promoted",
            "status": "succeeded",
            "paper_slug": "paper-z",
            "started_at": "2026-05-28T13:00:00Z",
            "finished_at": "2026-05-28T13:05:00Z",
        },
        report={
            "next_actions": [],
            "human_gate": {"status": "approved", "approved_by": "codex-test"},
        },
    )

    refresh_run_index(vault_path)

    failures_text = (runs_root / "dashboard-failures.md").read_text(encoding="utf-8")
    human_gate_text = (runs_root / "dashboard-human-gate.md").read_text(encoding="utf-8")
    success_text = (runs_root / "dashboard-recent-success.md").read_text(encoding="utf-8")
    dashboard_text = (runs_root / "dashboard.md").read_text(encoding="utf-8")

    assert failures_text.startswith("# Paper Source Failed Runs")
    assert "No failed runs." in failures_text
    assert human_gate_text.startswith("# Paper Source Human Gate Runs")
    assert "No runs waiting on a human gate." in human_gate_text
    assert success_text.startswith("# Paper Source Recent Successful Runs")
    assert "20260528T130000Z-promote" in success_text
    assert "## Recent Failures" in dashboard_text
    assert "No failed runs." in dashboard_text
    assert "## Pending Human Gate" in dashboard_text
    assert "No runs waiting on a human gate." in dashboard_text


def test_refresh_run_index_uses_atomic_writer_for_machine_json(tmp_path, monkeypatch):
    from paper_source import run_index as run_index_module

    vault_path = tmp_path / "vault"
    runs_root = vault_path / "_paper_source/runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    calls = []

    def _fake_write_json_atomic(path, payload):
        calls.append(path.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    monkeypatch.setattr(run_index_module, "write_json_atomic", _fake_write_json_atomic)

    run_index_module.refresh_run_index(vault_path)

    assert "index.json" in calls
    assert "research-queue.json" in calls
