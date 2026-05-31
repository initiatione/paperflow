import json

from epi.report_run import write_report


def test_write_report_emits_required_sections_even_when_empty(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        ranked=[
            {
                "title": "Embodied Navigation Control for Mobile Robots",
                "score": 0.91,
                "venue": "IROS",
                "year": 2024,
                "pdf_url": "https://example.org/nav.pdf",
            }
        ],
        errors=[],
        rejected=[],
        quarantined=[],
        critic_failures=[],
        budget_usage={"max_results": 5, "discovered_count": 1},
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=[],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report_json["accepted"][0]["title"] == "Embodied Navigation Control for Mobile Robots"
    assert report_json["rejected"] == []
    assert report_json["quarantined"] == []
    assert report_json["critic_failures"] == []
    assert report_json["budget_usage"] == {"max_results": 5, "discovered_count": 1}
    assert report_json["wiki_pages_written"] == []
    assert report_json["zotero_results"] == {"status": "not_run", "records": []}
    assert report_json["next_actions"] == []

    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## Budget Usage" in report_md
    assert "## Next Actions" in report_md


def test_write_report_groups_dry_run_candidates_by_research_queue(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        ranked=[
            {
                "title": "Strong Embodied Control Paper",
                "score": 0.91,
                "venue": "ICRA",
                "year": 2025,
                "pdf_url": "https://example.org/strong.pdf",
                "paper_type": "benchmark",
                "paper_classification": {"primary_type": "benchmark", "confidence": 0.69},
                "ranking_confidence": 0.82,
                "ranking_protocol": {
                    "decision": "advance-candidate",
                    "reasons": ["matched keywords: humanoid, control", "code availability signal present"],
                    "cautions": [],
                },
                "ranking_rationale": {
                    "one_sentence": "Advance for low-burden reading report and wiki deposition.",
                    "role_views": {
                        "nature_sci_editor": {"take": "Strong editorial fit."},
                        "peer_reviewer": {"take": "Benchmarks are inspectable."},
                        "senior_domain_researcher": {"take": "Good theory and experiment transfer."},
                    },
                    "wiki_deposition": {"value": "Create reference, concept, synthesis, and report pages."},
                },
            },
            {
                "title": "Interesting Simulation Paper",
                "score": 0.63,
                "venue": "Workshop",
                "year": 2025,
                "pdf_url": "https://example.org/review.pdf",
                "ranking_protocol": {
                    "decision": "review-candidate",
                    "reasons": ["matched keywords: control"],
                    "cautions": ["weak_reproducibility_signal"],
                },
            },
        ],
        errors=[],
        workflow_type="paper-discovery-dry-run",
        run_id="dry-run-001",
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert [paper["title"] for paper in report_json["research_queue"]["advance_candidates"]] == [
        "Strong Embodied Control Paper"
    ]
    assert [paper["title"] for paper in report_json["research_queue"]["review_candidates"]] == [
        "Interesting Simulation Paper"
    ]
    assert report_json["research_queue"]["unknown_decision"] == []
    assert "## Research Queue" in report_md
    assert "### Advance Candidates" in report_md
    assert "Strong Embodied Control Paper - score 0.91" in report_md
    assert "paper_type: benchmark (confidence=0.69)" in report_md
    assert "ranking_confidence: 0.82" in report_md
    assert "reasons: matched keywords: humanoid, control; code availability signal present" in report_md
    assert "rationale: Advance for low-burden reading report and wiki deposition." in report_md
    assert "nature-sci-editor: Strong editorial fit." in report_md
    assert "peer-reviewer: Benchmarks are inspectable." in report_md
    assert "senior-domain-researcher: Good theory and experiment transfer." in report_md
    assert "### Review Candidates" in report_md
    assert "Interesting Simulation Paper - score 0.63" in report_md
    assert "cautions: weak_reproducibility_signal" in report_md


def test_write_report_surfaces_reader_revision_plans_for_routed_runs(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        [],
        [],
        workflow_type="advance-batch",
        run_id="batch-001",
        paper_states=[
            {
                "slug": "paper",
                "paper_slug": "paper",
                "title": "Needs Reader Repair",
                "state": "critic_failed",
                "last_action": "critic",
                "next_action": "revise-reader",
                "human_gate_required": False,
            }
        ],
        reader_revision_plans=[
            {
                "slug": "paper",
                "title": "Needs Reader Repair",
                "plan_path": "D:\\vault\\_raw\\papers\\paper\\critic\\reader-revision-plan.json",
                "next_action": "revise-reader",
                "blocking_count": 2,
                "warning_count": 1,
            }
        ],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["reader_revision_plans"] == [
        {
            "slug": "paper",
            "title": "Needs Reader Repair",
            "plan_path": "D:\\vault\\_raw\\papers\\paper\\critic\\reader-revision-plan.json",
            "next_action": "revise-reader",
            "blocking_count": 2,
            "warning_count": 1,
        }
    ]
    assert "## Reader Revision Plans" in report_md
    assert "Needs Reader Repair - revise-reader" in report_md
    assert "blocking repairs: 2" in report_md
    assert "warning follow-ups: 1" in report_md
    assert "reader-revision-plan.json" in report_md


def test_write_report_surfaces_reproducibility_caveats_for_routed_runs(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    plan = {
        "slug": "paper",
        "title": "Needs Evidence Review",
        "plan_path": "D:\\vault\\_raw\\papers\\paper\\critic\\reproduction-plan.json",
        "next_action": "prepare-reproduction-plan",
        "missing_count": 4,
        "human_gate_required": True,
    }

    write_report(
        run_dir,
        [],
        [],
        workflow_type="advance-batch",
        run_id="batch-001",
        paper_states=[
            {
                "slug": "paper",
                "paper_slug": "paper",
                "title": "Needs Evidence Review",
                "state": "critic_passed",
                "last_action": "critic",
                "next_action": "stage",
                "human_gate_required": False,
            }
        ],
        reproduction_plans=[plan],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["reproduction_plans"] == [plan]
    assert "## Reproducibility Caveats" in report_md
    assert "Needs Evidence Review - review-reproducibility-caveats" in report_md
    assert "## Reproduction Plans" not in report_md
    assert "missing checklist items: 4" in report_md
    assert "reproduction-plan.json" in report_md
