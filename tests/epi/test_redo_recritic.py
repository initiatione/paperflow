import json
import sys

from epi.artifacts import file_sha256
from epi.orchestrator import main, run_one_paper_ingest
from epi.redo import redo_acquire, redo_parse, redo_read, recritic


def _write_phase2_fixture(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\noriginal paper\n")
    mineru_md = tmp_path / "paper.md"
    mineru_md.write_text(
        "# Abstract\n\nThis paper presents embodied navigation control for mobile robots.\n\n"
        "# Method\n\nThe controller combines perception, planning, and feedback control.\n",
        encoding="utf-8",
    )
    mineru_tex = tmp_path / "paper.tex"
    mineru_tex.write_text("\\section{Abstract} Fixture paper.\n", encoding="utf-8")
    candidate = {
        "id": "doi:10.1000/nav",
        "slug": "embodied-navigation-control-for-mobile-robots",
        "title": "Embodied Navigation Control for Mobile Robots",
        "authors": ["B. Engineer"],
        "year": 2024,
        "venue": "IROS",
        "abstract": "Robotics navigation and control with code.",
        "doi": "10.1000/nav",
        "pdf_url": "file://fixture-paper.pdf",
        "citation_count": 9,
        "score": 0.82,
        "sources": ["fixture"],
    }
    return candidate, pdf, mineru_md, mineru_tex


def _ingest_fixture(tmp_path):
    candidate, pdf, mineru_md, mineru_tex = _write_phase2_fixture(tmp_path)
    result = run_one_paper_ingest(
        vault_path=tmp_path / "vault",
        candidate=candidate,
        pdf_path=pdf,
        mineru_markdown_path=mineru_md,
        mineru_tex_path=mineru_tex,
    )
    return tmp_path / "vault", candidate["slug"], result["paper_root"]


def _redo_events(paper_root):
    return [
        json.loads(line)
        for line in (paper_root / "redo-records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_orchestrator_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    return main()


def _single_run_dir(vault):
    run_dirs = [path for path in (vault / "_epi" / "runs").iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def _assert_repair_run_state_contract(
    run_dir,
    *,
    workflow_type,
    expected_state,
    slug,
    vault,
    required_input_hash_keys,
    required_output_hash_keys,
):
    run_state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))

    assert run_state["stage"] == workflow_type
    assert run_state["run_id"] == run_dir.name
    assert run_state["workflow_type"] == workflow_type
    assert run_state["state"] == expected_state
    assert run_state["status"] == "success"
    assert run_state["paper_slug"] == slug
    assert run_state["vault_path"] == str(vault.resolve())
    assert run_state["compiled_wiki_write"] is False
    assert run_state["started_at"]
    assert run_state["finished_at"]
    assert run_state["exit_status"] == 0
    assert "orchestrator" in run_state["tool_versions"]
    assert run_state["input_artifact_hashes"]
    assert run_state["output_artifact_hashes"]
    for key in required_input_hash_keys:
        assert key in run_state["input_artifact_hashes"]
        assert run_state["input_artifact_hashes"][key]
    for key in required_output_hash_keys:
        assert key in run_state["output_artifact_hashes"]
        assert run_state["output_artifact_hashes"][key]


def test_redo_acquire_replaces_pdf_and_records_event_without_compiled_write(tmp_path):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    replacement_pdf = tmp_path / "replacement.pdf"
    replacement_pdf.write_bytes(b"%PDF-1.4\nreplacement paper\n")

    record = redo_acquire(vault, slug, replacement_pdf, reason="better source")

    assert record["stage"] == "redo-acquire"
    assert record["status"] == "success"
    assert record["reason"] == "better source"
    assert (paper_root / "paper.pdf").read_bytes() == replacement_pdf.read_bytes()
    assert _redo_events(paper_root)[-1]["stage"] == "redo-acquire"
    assert not (vault / "references" / f"{slug}.md").exists()


def test_redo_parse_and_redo_read_refresh_outputs_and_record_events(tmp_path):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    revised_md = tmp_path / "revised.md"
    revised_md.write_text(
        "# Abstract\n\nRevised embodied control summary.\n\n# Results\n\nNew parse evidence.\n",
        encoding="utf-8",
    )

    parse_record = redo_parse(vault, slug, revised_md, reason="parse critic requested redo")
    read_record = redo_read(vault, slug, reason="reader stale after parse redo")

    assert parse_record["stage"] == "redo-parse"
    assert read_record["stage"] == "redo-read"
    assert "Revised embodied control summary" in (paper_root / "mineru" / f"{slug}.md").read_text(encoding="utf-8")
    assert "Revised embodied control summary" in (paper_root / "reader" / "reader.md").read_text(encoding="utf-8")
    assert [event["stage"] for event in _redo_events(paper_root)[-2:]] == ["redo-parse", "redo-read"]
    assert not (vault / "references" / f"{slug}.md").exists()


def test_redo_read_consumes_reader_revision_plan_as_role_guidance(tmp_path):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    plan_path = paper_root / "critic" / "reader-revision-plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "epi-reader-revision-plan-v1",
                "recommendation": "revise-reader",
                "next_action": "revise-reader",
                "hard_rule": "No critic pass, no compiled wiki write.",
                "blocking_repairs": [
                    {
                        "reviewer": "peer-review-methods-critic",
                        "lens": "peer-reviewer",
                        "check": "benchmark_integrity",
                        "target_artifacts": ["reader/technical-reading.md"],
                        "instruction": "Add baseline, metric, and task context.",
                        "evidence": "benchmark_integrity: performance claim missing baseline",
                    }
                ],
                "warning_followups": [
                    {
                        "reviewer": "paper-quality-critic",
                        "lens": "peer-reviewer",
                        "check": "engineering_reproducibility",
                        "target_artifacts": ["reader/reproducibility.md"],
                        "instruction": "Record code/data/model/config/simulator/hardware gaps.",
                        "evidence": "engineering_reproducibility: missing model, config",
                    }
                ],
                "role_worklist": [
                    {
                        "lens": "nature-sci-editor",
                        "heading": "Nature Sci Editor",
                        "responsibility": "Tighten novelty and scope.",
                        "target_artifacts": ["reader/editorial-summary.md"],
                        "blocking_repairs": [],
                        "warning_followups": [],
                    },
                    {
                        "lens": "peer-reviewer",
                        "heading": "Peer Reviewer",
                        "responsibility": "Audit methods and reproducibility.",
                        "target_artifacts": ["reader/technical-reading.md", "reader/reproducibility.md"],
                        "blocking_repairs": [
                            {
                                "check": "benchmark_integrity",
                                "instruction": "Add baseline, metric, and task context.",
                                "evidence": "benchmark_integrity: performance claim missing baseline",
                            }
                        ],
                        "warning_followups": [
                            {
                                "check": "engineering_reproducibility",
                                "instruction": "Record code/data/model/config/simulator/hardware gaps.",
                                "evidence": "engineering_reproducibility: missing model, config",
                            }
                        ],
                    },
                    {
                        "lens": "senior-domain-researcher",
                        "heading": "Senior Domain Researcher",
                        "responsibility": "Check transfer value.",
                        "target_artifacts": ["reader/research-notes.md"],
                        "blocking_repairs": [],
                        "warning_followups": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    record = redo_read(vault, slug, reason="apply critic revision plan")
    guidance_path = paper_root / "reader" / "revision-guidance.md"
    guidance = guidance_path.read_text(encoding="utf-8")
    technical = (paper_root / "reader" / "technical-reading.md").read_text(encoding="utf-8")
    reproducibility = (paper_root / "reader" / "reproducibility.md").read_text(encoding="utf-8")
    research_notes = (paper_root / "reader" / "research-notes.md").read_text(encoding="utf-8")

    assert record["stage"] == "redo-read"
    assert record["revision_plan_path"] == str(plan_path)
    assert record["revision_guidance_path"] == str(guidance_path)
    assert record["revision_blocking_count"] == 1
    assert record["revision_warning_count"] == 1
    assert "## Peer Reviewer" in guidance
    assert "benchmark_integrity" in guidance
    assert "engineering_reproducibility" in guidance
    assert "reader/technical-reading.md" in guidance
    assert "## Critic Revision Focus" in technical
    assert "benchmark_integrity: Add baseline, metric, and task context." in technical
    assert "engineering_reproducibility: Record code/data/model/config/simulator/hardware gaps." in technical
    assert "Evidence: source=inference; basis=critic-revision-guidance" in technical
    assert "## Critic Revision Focus" in reproducibility
    assert "engineering_reproducibility" in reproducibility
    assert "## Critic Revision Focus" in research_notes
    assert "Check transfer value." in research_notes
    assert _redo_events(paper_root)[-1]["revision_guidance_path"] == str(guidance_path)


def test_recritic_refreshes_critic_report_and_records_event(tmp_path):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    (paper_root / "reader" / "reader.md").write_text(
        f"# Reader\n\n- Claim 1: repaired reader.\n  Evidence: source=mineru/{slug}.md; heading=Abstract\n",
        encoding="utf-8",
    )

    record = recritic(vault, slug, reason="reader revised")
    critic_report = json.loads((paper_root / "critic" / "critic-report.json").read_text(encoding="utf-8"))

    assert record["stage"] == "recritic"
    assert record["status"] == "success"
    assert record["critic_outcome"] == "pass"
    assert critic_report["outcome"] == "pass"
    assert _redo_events(paper_root)[-1]["stage"] == "recritic"
    assert not (vault / "references" / f"{slug}.md").exists()


def test_redo_acquire_cli_writes_routed_report_with_changed_artifacts(tmp_path, monkeypatch):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    replacement_pdf = tmp_path / "replacement.pdf"
    replacement_pdf.write_bytes(b"%PDF-1.4\nreplacement paper\n")
    expected_replacement_hash = file_sha256(replacement_pdf)

    exit_code = _run_orchestrator_cli(
        monkeypatch,
        "redo-acquire",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--pdf",
        str(replacement_pdf),
        "--reason",
        "better source",
    )

    assert exit_code == 0
    run_dir = _single_run_dir(vault)
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((vault / "_epi" / "runs" / "index.json").read_text(encoding="utf-8"))
    dashboard_text = (vault / "_epi" / "runs" / "dashboard.md").read_text(encoding="utf-8")

    assert report_json["workflow_type"] == "redo-acquire"
    assert report_json["paper_states"] == [
        {"paper_slug": slug, "state": "reacquired", "next_action": "redo-parse"}
    ]
    assert report_json["changed_artifacts"] == ["paper.pdf"]
    assert report_json["next_actions"] == ["redo-parse the reacquired PDF"]
    assert report_json["wiki_pages_written"] == []
    assert "paper.pdf" in report_md
    _assert_repair_run_state_contract(
        run_dir,
        workflow_type="redo-acquire",
        expected_state="reacquired",
        slug=slug,
        vault=vault,
        required_input_hash_keys=["input_pdf"],
        required_output_hash_keys=["paper.pdf", "redo-records.jsonl"],
    )
    run_state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    assert run_state["input_artifact_hashes"]["input_pdf"] == expected_replacement_hash
    assert _redo_events(paper_root)[-1]["stage"] == "redo-acquire"
    assert index_payload["runs"][0]["run_id"] == run_dir.name
    assert index_payload["runs"][0]["workflow_type"] == "redo-acquire"
    assert run_dir.name in dashboard_text


def test_redo_parse_cli_writes_routed_report_with_changed_artifacts(tmp_path, monkeypatch):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    revised_md = tmp_path / "revised.md"
    revised_md.write_text(
        "# Abstract\n\nRevised embodied control summary.\n\n# Results\n\nNew parse evidence.\n",
        encoding="utf-8",
    )
    expected_markdown_hash = file_sha256(revised_md)

    exit_code = _run_orchestrator_cli(
        monkeypatch,
        "redo-parse",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--mineru-md",
        str(revised_md),
        "--reason",
        "parse critic requested redo",
    )

    assert exit_code == 0
    run_dir = _single_run_dir(vault)
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["workflow_type"] == "redo-parse"
    assert report_json["paper_states"] == [
        {"paper_slug": slug, "state": "reparsed", "next_action": "redo-read"}
    ]
    canonical_mineru_md = f"mineru/{slug}.md"
    assert report_json["changed_artifacts"] == [canonical_mineru_md, "mineru/paper.tex"]
    assert report_json["next_actions"] == ["redo-read the reparsed paper"]
    assert report_json["wiki_pages_written"] == []
    assert "mineru/paper.tex" in report_md
    _assert_repair_run_state_contract(
        run_dir,
        workflow_type="redo-parse",
        expected_state="reparsed",
        slug=slug,
        vault=vault,
        required_input_hash_keys=["input_markdown"],
        required_output_hash_keys=[canonical_mineru_md, "mineru/paper.tex", "redo-records.jsonl"],
    )
    run_state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    assert run_state["input_artifact_hashes"]["input_markdown"] == expected_markdown_hash
    assert _redo_events(paper_root)[-1]["stage"] == "redo-parse"


def test_redo_read_cli_writes_routed_report_with_changed_artifacts(tmp_path, monkeypatch):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    revised_md = tmp_path / "revised.md"
    revised_md.write_text(
        "# Abstract\n\nRevised embodied control summary.\n\n# Results\n\nNew parse evidence.\n",
        encoding="utf-8",
    )
    redo_parse(vault, slug, revised_md, reason="prepare for reader refresh")

    exit_code = _run_orchestrator_cli(
        monkeypatch,
        "redo-read",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--reason",
        "reader stale after parse redo",
    )

    assert exit_code == 0
    run_dir = _single_run_dir(vault)
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["workflow_type"] == "redo-read"
    assert report_json["paper_states"] == [
        {"paper_slug": slug, "state": "reader_regenerated", "next_action": "recritic"}
    ]
    assert report_json["changed_artifacts"] == [
        "reader/reader.md",
        "reader/editorial-summary.md",
        "reader/technical-reading.md",
        "reader/research-notes.md",
        "reader/figures.md",
        "reader/reproducibility.md",
        "reader/implementation-ideas.md",
        "reader/revision-guidance.md",
        "reader/evidence-map.json",
        "reader/claim-support.json",
    ]
    assert report_json["next_actions"] == ["recritic the regenerated reader outputs"]
    assert report_json["wiki_pages_written"] == []
    assert "reader/implementation-ideas.md" in report_md
    canonical_mineru_md = f"mineru/{slug}.md"
    _assert_repair_run_state_contract(
        run_dir,
        workflow_type="redo-read",
        expected_state="reader_regenerated",
        slug=slug,
        vault=vault,
        required_input_hash_keys=[canonical_mineru_md],
        required_output_hash_keys=[
            "reader/reader.md",
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/figures.md",
            "reader/reproducibility.md",
            "reader/implementation-ideas.md",
            "reader/revision-guidance.md",
            "reader/evidence-map.json",
            "reader/claim-support.json",
            "redo-records.jsonl",
        ],
    )
    assert _redo_events(paper_root)[-1]["stage"] == "redo-read"


def test_redo_read_cli_can_apply_revision_plan_and_recritic_in_one_routed_run(tmp_path, monkeypatch):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    plan_path = paper_root / "critic" / "reader-revision-plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "epi-reader-revision-plan-v1",
                "recommendation": "revise-reader",
                "next_action": "revise-reader",
                "hard_rule": "No critic pass, no compiled wiki write.",
                "blocking_repairs": [
                    {
                        "reviewer": "peer-review-methods-critic",
                        "lens": "peer-reviewer",
                        "check": "benchmark_integrity",
                        "target_artifacts": ["reader/technical-reading.md"],
                        "instruction": "Add baseline, metric, and task context.",
                        "evidence": "benchmark_integrity: performance claim missing baseline",
                    }
                ],
                "warning_followups": [
                    {
                        "reviewer": "paper-quality-critic",
                        "lens": "peer-reviewer",
                        "check": "engineering_reproducibility",
                        "target_artifacts": ["reader/reproducibility.md"],
                        "instruction": "Record reproducibility gaps.",
                        "evidence": "engineering_reproducibility: missing code, model",
                    }
                ],
                "role_worklist": [
                    {
                        "lens": "peer-reviewer",
                        "heading": "Peer Reviewer",
                        "responsibility": "Audit methods and reproducibility.",
                        "target_artifacts": ["reader/technical-reading.md", "reader/reproducibility.md"],
                        "blocking_repairs": [
                            {
                                "check": "benchmark_integrity",
                                "instruction": "Add baseline, metric, and task context.",
                                "evidence": "benchmark_integrity: performance claim missing baseline",
                            }
                        ],
                        "warning_followups": [
                            {
                                "check": "engineering_reproducibility",
                                "instruction": "Record reproducibility gaps.",
                                "evidence": "engineering_reproducibility: missing code, model",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = _run_orchestrator_cli(
        monkeypatch,
        "redo-read",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--from-revision-plan",
        "--recritic",
        "--reason",
        "apply critic plan and re-review",
    )

    assert exit_code == 0
    run_dir = _single_run_dir(vault)
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    events = _redo_events(paper_root)

    assert report_json["workflow_type"] == "redo-read-recritic"
    assert report_json["paper_states"] == [
        {"paper_slug": slug, "state": "critic_passed", "next_action": "stage"}
    ]
    assert "reader/revision-guidance.md" in report_json["changed_artifacts"]
    assert "reader/claim-support.json" in report_json["changed_artifacts"]
    assert "critic/critic-report.json" in report_json["changed_artifacts"]
    assert "critic/reader-revision-plan.json" in report_json["changed_artifacts"]
    assert report_json["next_actions"] == ["stage the paper for promotion review"]
    assert report_json["revision_delta"]["before"]["blocking_count"] == 1
    assert report_json["revision_delta"]["before"]["warning_count"] == 1
    assert report_json["revision_delta"]["after"]["blocking_count"] == 0
    assert report_json["revision_delta"]["resolved_blocking_checks"] == ["benchmark_integrity"]
    assert report_json["revision_delta"]["remaining_warning_checks"]
    assert "## Revision Delta" in report_md
    assert "resolved blocking checks: benchmark_integrity" in report_md
    assert [event["stage"] for event in events[-2:]] == ["redo-read", "redo-read-recritic"]
    assert events[-1]["critic_outcome"] == "pass"
    canonical_mineru_md = f"mineru/{slug}.md"
    _assert_repair_run_state_contract(
        run_dir,
        workflow_type="redo-read-recritic",
        expected_state="critic_passed",
        slug=slug,
        vault=vault,
        required_input_hash_keys=[canonical_mineru_md, "critic/reader-revision-plan.json"],
        required_output_hash_keys=[
            "reader/revision-guidance.md",
            "reader/claim-support.json",
            "critic/critic-report.json",
            "critic/reader-revision-plan.json",
            "redo-records.jsonl",
        ],
    )


def test_recritic_cli_writes_routed_report_with_changed_artifacts(tmp_path, monkeypatch):
    vault, slug, paper_root = _ingest_fixture(tmp_path)
    (paper_root / "reader" / "reader.md").write_text(
        f"# Reader\n\n- Claim 1: repaired reader.\n  Evidence: source=mineru/{slug}.md; heading=Abstract\n",
        encoding="utf-8",
    )
    expected_reader_hash = file_sha256(paper_root / "reader" / "reader.md")

    exit_code = _run_orchestrator_cli(
        monkeypatch,
        "recritic",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--reason",
        "reader revised",
    )

    assert exit_code == 0
    run_dir = _single_run_dir(vault)
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["workflow_type"] == "recritic"
    assert report_json["paper_states"] == [
        {"paper_slug": slug, "state": "critic_passed", "next_action": "stage"}
    ]
    assert report_json["changed_artifacts"] == ["critic/critic-report.json"]
    assert report_json["next_actions"] == ["stage the paper for promotion review"]
    assert report_json["wiki_pages_written"] == []
    assert "critic/critic-report.json" in report_md
    _assert_repair_run_state_contract(
        run_dir,
        workflow_type="recritic",
        expected_state="critic_passed",
        slug=slug,
        vault=vault,
        required_input_hash_keys=["reader/reader.md"],
        required_output_hash_keys=["critic/critic-report.json", "redo-records.jsonl"],
    )
    run_state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    assert run_state["input_artifact_hashes"]["reader/reader.md"] == expected_reader_hash
    paper_run_state = json.loads((paper_root / "run-state.json").read_text(encoding="utf-8"))
    assert paper_run_state["paper_slug"] == slug
    assert paper_run_state["state"] == "critic_passed"
    assert paper_run_state["last_action"] == "recritic"
    assert paper_run_state["next_action"] == "stage"
    assert paper_run_state["stage_record"]["outcome"] == "pass"
    assert _redo_events(paper_root)[-1]["stage"] == "recritic"
