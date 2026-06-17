import json

from paper_source.report_run import write_report


def test_write_report_emits_routed_run_fields_and_markdown_shape(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    accepted = [
        {
            "slug": "embodied-control",
            "title": "Embodied Control for Mobile Robots",
            "state": "staging_ready",
        }
    ]
    paper_states = [
        {
            "slug": "embodied-control",
            "title": "Embodied Control for Mobile Robots",
            "state": "staging_ready",
            "last_action": "critic",
            "next_action": "run-wiki-ingest-agent",
            "human_gate_required": True,
        },
        {
            "slug": "vision-failure",
            "title": "Vision Failure Analysis",
            "state": "critic_failed",
            "last_action": "critic",
            "next_action": "redo-reader",
            "human_gate_required": False,
        },
    ]
    failed_papers = [paper_states[1]]

    write_report(
        run_dir,
        ranked=accepted,
        errors=[],
        workflow_type="advance-batch",
        run_id="20260528T120000Z-batch",
        paper_states=paper_states,
        failed_papers=failed_papers,
        budget_usage={"processed_count": 2, "skipped_count": 1, "max_papers": 3},
        wiki_pages_written=[],
        next_actions=[
            "Promote staging-ready papers after human approval.",
            "Redo reader output for critic-failed papers.",
        ],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report_json["workflow_type"] == "advance-batch"
    assert report_json["run_id"] == "20260528T120000Z-batch"
    assert report_json["paper_states"] == paper_states
    assert report_json["failed_papers"] == failed_papers
    assert report_json["budget_usage"] == {"processed_count": 2, "skipped_count": 1, "max_papers": 3}
    assert report_json["wiki_pages_written"] == []
    assert report_json["next_actions"] == [
        "Promote staging-ready papers after human approval.",
        "Redo reader output for critic-failed papers.",
    ]

    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "# Paper Source Routed Run" in report_md
    assert "Workflow type: advance-batch" in report_md
    assert "## Paper States" in report_md
    assert "## Failed Papers" in report_md
    assert "# Paper Source Dry Run" not in report_md


def test_write_report_surfaces_research_decisions_for_routed_runs(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    decision = {
        "slug": "embodied-control",
        "title": "Embodied Control for Mobile Robots",
        "recommendation": "revise-reader",
        "next_action": "revise-reader",
        "role_verdicts": {
            "nature-sci-editor": "pass",
            "peer-reviewer": "fail",
            "senior-domain-researcher": "pass",
        },
        "action_items": [
            {
                "lens": "peer-reviewer",
                "action": "revise",
                "rationale": "peer-reviewer reviewer requires reader repair before promotion.",
            }
        ],
    }

    write_report(
        run_dir,
        ranked=[],
        errors=[],
        workflow_type="advance-batch",
        run_id="20260528T123000Z-batch",
        paper_states=[
            {
                "slug": "embodied-control",
                "title": "Embodied Control for Mobile Robots",
                "state": "critic_failed",
                "last_action": "critic",
                "next_action": "revise-reader",
                "human_gate_required": False,
            }
        ],
        failed_papers=[],
        research_decisions=[decision],
        next_actions=["revise-reader"],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["research_decisions"] == [decision]
    assert "## Research Decisions" in report_md
    assert "Embodied Control for Mobile Robots - revise-reader" in report_md
    assert "peer-reviewer: fail" in report_md
    assert "peer-reviewer -> revise" in report_md
