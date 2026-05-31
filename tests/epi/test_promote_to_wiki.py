import json
import sys

import pytest

from epi.orchestrator import main
from epi.promote_to_wiki import promote_paper, rollback_promotion


def _compiled_page_set(vault, slug):
    return {
        "reference": vault / "references" / f"{slug}.md",
        "concept": vault / "concepts" / f"{slug}-concept.md",
        "synthesis": vault / "synthesis" / f"{slug}-synthesis.md",
        "report": vault / "reports" / f"{slug}-reading-report.md",
    }


def _run_orchestrator_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    return main()


def _run_dirs(vault):
    return [path for path in (vault / "_runs").iterdir() if path.is_dir()]


def _research_decision_fixture():
    return {
        "schema_version": "epi-research-decision-v1",
        "recommendation": "stage-for-promotion-review",
        "next_action": "stage",
        "panel_summary": {
            "consensus": "approve-for-staging",
            "blocking_lenses": [],
            "warning_reviewers": ["paper-quality-critic"],
            "hard_rule": "No critic pass, no compiled wiki write.",
        },
        "role_verdicts": {
            "nature-sci-editor": "pass",
            "peer-reviewer": "pass",
            "senior-domain-researcher": "pass",
        },
        "role_assessments": [
            {
                "lens": "nature-sci-editor",
                "artifact": "reader/editorial-summary.md",
                "verdict": "pass",
                "action": "preserve",
                "promotion_blocking": False,
            },
            {
                "lens": "peer-reviewer",
                "artifact": "reader/technical-reading.md",
                "verdict": "pass",
                "action": "preserve",
                "promotion_blocking": False,
            },
            {
                "lens": "senior-domain-researcher",
                "artifact": "reader/research-notes.md",
                "verdict": "pass",
                "action": "preserve",
                "promotion_blocking": False,
            },
        ],
    }


def _seed_staged_paper(
    vault,
    slug,
    *,
    outcome="pass",
    existing_compiled=None,
    existing_compiled_pages=None,
    research_decision=None,
    reproduction_plan=None,
    reading_report=False,
):
    paper_root = vault / "_raw" / "papers" / slug
    staging_root = vault / "_staging" / "papers" / slug
    (paper_root / "critic").mkdir(parents=True)
    (staging_root / "references").mkdir(parents=True)
    (staging_root / "concepts").mkdir(parents=True)
    (staging_root / "synthesis").mkdir(parents=True)
    if reproduction_plan is not None:
        (staging_root / "reproduction").mkdir(parents=True)
    if reading_report:
        (staging_root / "reports").mkdir(parents=True)
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture"}),
        encoding="utf-8",
    )
    critic_report = {"outcome": outcome, "hard_rule": "No critic pass, no compiled wiki write."}
    if research_decision is not None:
        decision_path = paper_root / "critic" / "research-decision.json"
        decision_path.write_text(json.dumps(research_decision), encoding="utf-8")
        critic_report["research_decision_path"] = str(decision_path)
        critic_report["research_decision"] = research_decision
    if reproduction_plan is not None:
        reproduction_plan_path = paper_root / "critic" / "reproduction-plan.json"
        reproduction_plan_path.write_text(json.dumps(reproduction_plan), encoding="utf-8")
        critic_report["reproduction_plan_path"] = str(reproduction_plan_path)
        critic_report["reproduction_plan"] = reproduction_plan
    (paper_root / "critic" / "critic-report.json").write_text(json.dumps(critic_report), encoding="utf-8")
    (staging_root / "references" / f"{slug}.md").write_text(
        "---\nstage: staging\n---\n\n# Fixture Paper\n",
        encoding="utf-8",
    )
    (staging_root / "concepts" / f"{slug}-concept.md").write_text(
        "---\nstage: staging\npage_type: concept\n---\n\n# Fixture Paper Concept\n",
        encoding="utf-8",
    )
    (staging_root / "synthesis" / f"{slug}-synthesis.md").write_text(
        "---\nstage: staging\npage_type: synthesis\n---\n\n# Fixture Paper Synthesis\n",
        encoding="utf-8",
    )
    if reproduction_plan is not None:
        (staging_root / "reproduction" / f"{slug}-reproduction.md").write_text(
            "---\nstage: staging\npage_type: reproduction\n---\n\n"
            "# Fixture Paper Reproduction\n\n"
            "## Senior Domain Researcher Reproduction Tasks\n",
            encoding="utf-8",
        )
    if reading_report:
        (staging_root / "reports" / f"{slug}-reading-report.md").write_text(
            "---\nstage: staging\npage_type: reading_report\n---\n\n"
            "# Fixture Paper Reading Report\n\n"
            "## Quick Take\n\n"
            "- Keep this paper in the LLM Wiki.\n\n"
            "## What To Read If You Only Have 5 Minutes\n\n"
            "- Read the quick take and quality gates.\n\n"
            "## Wiki Knowledge Targets\n",
            encoding="utf-8",
        )
    plan = {
        "paper_slug": slug,
        "critic_outcome": outcome,
        "staged_reference": str(staging_root / "references" / f"{slug}.md"),
        "staged_concepts": [str(staging_root / "concepts" / f"{slug}-concept.md")],
        "staged_synthesis": [str(staging_root / "synthesis" / f"{slug}-synthesis.md")],
        "compiled_targets": [
            f"references/{slug}.md",
            f"concepts/{slug}-concept.md",
            f"synthesis/{slug}-synthesis.md",
        ],
    }
    if research_decision is not None:
        plan["research_decision_path"] = str(paper_root / "critic" / "research-decision.json")
        plan["recommendation"] = research_decision["recommendation"]
        plan["next_action"] = research_decision["next_action"]
        plan["panel_summary"] = research_decision["panel_summary"]
        plan["role_verdicts"] = research_decision["role_verdicts"]
        plan["role_assessments"] = research_decision["role_assessments"]
    if reproduction_plan is not None:
        plan["reproduction_plan_path"] = str(paper_root / "critic" / "reproduction-plan.json")
        plan["staged_reproduction"] = [str(staging_root / "reproduction" / f"{slug}-reproduction.md")]
        plan["compiled_targets"].append(f"reproduction/{slug}-reproduction.md")
    if reading_report:
        plan["staged_reports"] = [str(staging_root / "reports" / f"{slug}-reading-report.md")]
        plan["compiled_targets"].append(f"reports/{slug}-reading-report.md")
    (staging_root / "promotion-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (vault / ".manifest.json").write_text(
        json.dumps({"vault_type": "academic-paper-research", "papers": []}),
        encoding="utf-8",
    )
    (vault / "log.md").write_text("# Log\n", encoding="utf-8")
    (vault / "index.md").write_text("# Paper Research Wiki\n\nOriginal index intro.\n", encoding="utf-8")
    (vault / "hot.md").write_text("# Hot\n\nOriginal hot intro.\n", encoding="utf-8")
    compiled_pages = _compiled_page_set(vault, slug)
    if existing_compiled is not None:
        compiled_pages["reference"].parent.mkdir(parents=True, exist_ok=True)
        compiled_pages["reference"].write_text(existing_compiled, encoding="utf-8")
    for page_type, content in (existing_compiled_pages or {}).items():
        compiled_pages[page_type].parent.mkdir(parents=True, exist_ok=True)
        compiled_pages[page_type].write_text(content, encoding="utf-8")
    return paper_root, staging_root


def test_promote_paper_writes_compiled_reference_and_records_backup(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, _ = _seed_staged_paper(vault, slug, existing_compiled="# Old Page\n")

    record = promote_paper(vault, slug, approved_by="codex-test")

    compiled = vault / "references" / f"{slug}.md"
    assert compiled.read_text(encoding="utf-8").startswith("---\nstage: staging")
    promotion_record = json.loads((paper_root / "promotion-record.json").read_text(encoding="utf-8"))
    assert promotion_record["status"] == "promoted"
    assert promotion_record["critic_outcome"] == "pass"
    assert promotion_record["promoted_page_paths"][0] == str(compiled)
    assert str(vault / "concepts" / f"{slug}-concept.md") in promotion_record["promoted_page_paths"]
    assert str(vault / "synthesis" / f"{slug}-synthesis.md") in promotion_record["promoted_page_paths"]
    assert promotion_record["previous_page_snapshot_paths"]
    assert promotion_record["human_gate_decision"]["status"] == "approved"
    assert promotion_record["human_gate_decision"]["approved_by"] == "codex-test"
    assert record["backup_paths"] == promotion_record["previous_page_snapshot_paths"]

    manifest = json.loads((vault / ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["papers"][0]["slug"] == slug
    assert manifest["papers"][0]["promotion_status"] == "promoted"
    assert "Promoted fixture-paper" in (vault / "log.md").read_text(encoding="utf-8")


def test_promote_paper_persists_research_decision_for_manifest_queries(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    decision = _research_decision_fixture()
    paper_root, _ = _seed_staged_paper(vault, slug, research_decision=decision)

    record = promote_paper(vault, slug, approved_by="codex-test")

    manifest = json.loads((vault / ".manifest.json").read_text(encoding="utf-8"))
    paper = manifest["papers"][0]
    promotion_record = json.loads((paper_root / "promotion-record.json").read_text(encoding="utf-8"))
    compiled_reference = (vault / "references" / f"{slug}.md").read_text(encoding="utf-8")
    expected_summary = {
        "recommendation": "stage-for-promotion-review",
        "next_action": "stage",
        "panel_consensus": "approve-for-staging",
        "blocking_lenses": [],
        "warning_reviewers": ["paper-quality-critic"],
        "role_verdicts": {
            "nature-sci-editor": "pass",
            "peer-reviewer": "pass",
            "senior-domain-researcher": "pass",
        },
    }

    assert paper["research_decision"] == expected_summary
    assert paper["role_assessments"] == decision["role_assessments"]
    assert promotion_record["research_decision"] == expected_summary
    assert promotion_record["role_assessments"] == decision["role_assessments"]
    assert record["research_decision"] == expected_summary
    assert 'epi_panel_consensus: "approve-for-staging"' in compiled_reference
    assert 'epi_peer_reviewer_verdict: "pass"' in compiled_reference


def test_promote_paper_rejects_nonpassing_critic(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_staged_paper(vault, slug, outcome="human-review")

    with pytest.raises(ValueError, match="critic outcome"):
        promote_paper(vault, slug)

    assert not (vault / "references" / f"{slug}.md").exists()


def test_promote_paper_rejects_missing_human_gate_approval(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_staged_paper(vault, slug)

    with pytest.raises(ValueError, match="human gate approval"):
        promote_paper(vault, slug)

    assert not (vault / "references" / f"{slug}.md").exists()
    assert not (vault / "_raw" / "papers" / slug / "promotion-record.json").exists()


def test_promote_paper_rejects_missing_compiled_targets_from_plan(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, staging_root = _seed_staged_paper(vault, slug)
    plan_path = staging_root / "promotion-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    del plan["compiled_targets"]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="compiled_targets"):
        promote_paper(vault, slug, approved_by="codex-test")

    assert not (paper_root / "promotion-record.json").exists()
    assert not (vault / "references" / f"{slug}.md").exists()


@pytest.mark.parametrize(
    "compiled_target, leaked_path",
    [
        ("../outside.md", "outside.md"),
        ("notes/not-allowed.md", None),
    ],
)
def test_promote_paper_rejects_untrusted_compiled_targets(tmp_path, compiled_target, leaked_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, staging_root = _seed_staged_paper(vault, slug)
    plan_path = staging_root / "promotion-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["compiled_targets"][0] = compiled_target
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="compiled target"):
        promote_paper(vault, slug, approved_by="codex-test")

    assert not (paper_root / "promotion-record.json").exists()
    assert not (vault / compiled_target).exists()
    if leaked_path:
        assert not (tmp_path / leaked_path).exists()


def test_promote_paper_writes_compiled_concept_and_synthesis_pages(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, staging_root = _seed_staged_paper(
        vault,
        slug,
        existing_compiled="# Old Reference\n",
        existing_compiled_pages={"concept": "# Old Concept\n"},
    )

    promote_paper(vault, slug, approved_by="codex-test")

    compiled_pages = _compiled_page_set(vault, slug)
    assert compiled_pages["reference"].read_text(encoding="utf-8").startswith("---\nstage: staging")
    assert compiled_pages["concept"].read_text(encoding="utf-8").startswith("---\nstage: staging")
    assert compiled_pages["synthesis"].read_text(encoding="utf-8").startswith("---\nstage: staging")

    promotion_record = json.loads((paper_root / "promotion-record.json").read_text(encoding="utf-8"))
    assert promotion_record["staged_draft_paths"] == [
        str(staging_root / "references" / f"{slug}.md"),
        str(staging_root / "concepts" / f"{slug}-concept.md"),
        str(staging_root / "synthesis" / f"{slug}-synthesis.md"),
    ]
    assert promotion_record["promoted_page_paths"] == [
        str(compiled_pages["reference"]),
        str(compiled_pages["concept"]),
        str(compiled_pages["synthesis"]),
    ]
    page_records = {entry["compiled_path"]: entry for entry in promotion_record["page_transactions"]}
    assert page_records[str(compiled_pages["reference"])]["previous_snapshot_path"]
    assert page_records[str(compiled_pages["concept"])]["previous_snapshot_path"]
    assert page_records[str(compiled_pages["synthesis"])]["previous_snapshot_path"] is None


def test_promote_paper_writes_compiled_reading_report_page(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, staging_root = _seed_staged_paper(vault, slug, reading_report=True)

    promote_paper(vault, slug, approved_by="codex-test")

    compiled_report = vault / "reports" / f"{slug}-reading-report.md"
    assert compiled_report.is_file()
    compiled_text = compiled_report.read_text(encoding="utf-8")
    assert "page_type: reading_report" in compiled_text
    assert "## Quick Take" in compiled_text
    assert "## What To Read If You Only Have 5 Minutes" in compiled_text

    promotion_record = json.loads((paper_root / "promotion-record.json").read_text(encoding="utf-8"))
    assert str(staging_root / "reports" / f"{slug}-reading-report.md") in promotion_record["staged_draft_paths"]
    assert str(compiled_report) in promotion_record["promoted_page_paths"]
    page_records = {entry["compiled_path"]: entry for entry in promotion_record["page_transactions"]}
    assert page_records[str(compiled_report)]["previous_snapshot_path"] is None


def test_rollback_promotion_restores_previous_page(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_staged_paper(vault, slug, existing_compiled="# Old Page\n")
    promote_paper(vault, slug, approved_by="codex-test")

    rollback = rollback_promotion(vault, slug)

    assert rollback["status"] == "rolled_back"
    assert (vault / "references" / f"{slug}.md").read_text(encoding="utf-8") == "# Old Page\n"
    manifest = json.loads((vault / ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["papers"] == []
    assert "Rolled back fixture-paper" in (vault / "log.md").read_text(encoding="utf-8")
    assert rollback["restored_state_paths"]["manifest"] == str(vault / ".manifest.json")


def test_rollback_promotion_restores_or_removes_concept_and_synthesis_pages(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_staged_paper(
        vault,
        slug,
        existing_compiled="# Old Reference\n",
        existing_compiled_pages={"concept": "# Old Concept\n"},
    )
    promote_paper(vault, slug, approved_by="codex-test")

    rollback = rollback_promotion(vault, slug)

    compiled_pages = _compiled_page_set(vault, slug)
    assert compiled_pages["reference"].read_text(encoding="utf-8") == "# Old Reference\n"
    assert compiled_pages["concept"].read_text(encoding="utf-8") == "# Old Concept\n"
    assert not compiled_pages["synthesis"].exists()
    assert sorted(rollback["restored_paths"]) == sorted(
        [str(compiled_pages["reference"]), str(compiled_pages["concept"])]
    )
    assert rollback["removed_paths"] == [str(compiled_pages["synthesis"])]


def test_rollback_promotion_rejects_recorded_compiled_path_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, _ = _seed_staged_paper(vault, slug)
    outside_page = tmp_path / "outside.md"
    outside_page.write_text("# Outside\n", encoding="utf-8")
    promote_paper(vault, slug, approved_by="codex-test")
    record_path = paper_root / "promotion-record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["page_transactions"][0]["compiled_path"] = str(outside_page)
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="compiled path"):
        rollback_promotion(vault, slug)

    assert outside_page.read_text(encoding="utf-8") == "# Outside\n"


def test_rollback_promotion_rejects_recorded_snapshot_path_outside_backups(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, _ = _seed_staged_paper(vault, slug, existing_compiled="# Old Page\n")
    outside_snapshot = tmp_path / "outside-snapshot.md"
    outside_snapshot.write_text("# Outside Snapshot\n", encoding="utf-8")
    promote_paper(vault, slug, approved_by="codex-test")
    record_path = paper_root / "promotion-record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["page_transactions"][0]["previous_snapshot_path"] = str(outside_snapshot)
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot path"):
        rollback_promotion(vault, slug)

    assert (vault / "references" / f"{slug}.md").read_text(encoding="utf-8").startswith("---\nstage: staging")


def test_promotion_snapshots_manifest_and_log_for_rollback(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, _ = _seed_staged_paper(vault, slug)
    original_manifest = {
        "vault_type": "academic-paper-research",
        "papers": [{"slug": "old-paper", "promotion_status": "promoted"}],
    }
    original_log = "# Log\n- Existing entry.\n"
    (vault / ".manifest.json").write_text(json.dumps(original_manifest), encoding="utf-8")
    (vault / "log.md").write_text(original_log, encoding="utf-8")

    promote_paper(vault, slug, approved_by="codex-test")
    promotion_record = json.loads((paper_root / "promotion-record.json").read_text(encoding="utf-8"))

    snapshot_paths = promotion_record["previous_state_snapshot_paths"]
    assert set(snapshot_paths) == {"manifest", "log", "index", "hot"}
    assert json.loads((paper_root / snapshot_paths["manifest"]).read_text(encoding="utf-8")) == original_manifest
    assert (paper_root / snapshot_paths["log"]).read_text(encoding="utf-8") == original_log
    assert promotion_record["manifest_update_summary"]["paper_slug"] == slug
    assert "Promoted fixture-paper" in (vault / "log.md").read_text(encoding="utf-8")

    rollback = rollback_promotion(vault, slug)

    assert rollback["status"] == "rolled_back"
    assert json.loads((vault / ".manifest.json").read_text(encoding="utf-8")) == original_manifest
    restored_log = (vault / "log.md").read_text(encoding="utf-8")
    assert restored_log.startswith(original_log)
    assert "Promoted fixture-paper" not in restored_log
    assert "Rolled back fixture-paper" in restored_log
    assert rollback["restored_state_paths"] == {
        "manifest": str(vault / ".manifest.json"),
        "log": str(vault / "log.md"),
        "index": str(vault / "index.md"),
        "hot": str(vault / "hot.md"),
    }


def test_promotion_refreshes_index_and_hot_and_rolls_them_back(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root, _ = _seed_staged_paper(vault, slug, research_decision=_research_decision_fixture())
    original_index = "# Paper Research Wiki\n\nOriginal index intro.\n"
    original_hot = "# Hot\n\nOriginal hot intro.\n"
    (vault / "index.md").write_text(original_index, encoding="utf-8")
    (vault / "hot.md").write_text(original_hot, encoding="utf-8")

    promote_paper(vault, slug, approved_by="codex-test")

    promotion_record = json.loads((paper_root / "promotion-record.json").read_text(encoding="utf-8"))
    snapshot_paths = promotion_record["previous_state_snapshot_paths"]
    assert (paper_root / snapshot_paths["index"]).read_text(encoding="utf-8") == original_index
    assert (paper_root / snapshot_paths["hot"]).read_text(encoding="utf-8") == original_hot
    index_text = (vault / "index.md").read_text(encoding="utf-8")
    hot_text = (vault / "hot.md").read_text(encoding="utf-8")
    assert "Original index intro." in index_text
    assert "Original hot intro." in hot_text
    assert "<!-- EPI:PROMOTED-PAPERS:START -->" in index_text
    assert "<!-- EPI:HOT-PAPERS:START -->" in hot_text
    assert "[[references/fixture-paper|Fixture Paper]]" in index_text
    assert "[[references/fixture-paper|Fixture Paper]]" in hot_text
    assert "10.1000/fixture" in index_text
    assert "decision: approve-for-staging" in index_text
    assert "roles: editor=pass, reviewer=pass, domain=pass" in index_text
    assert "warnings: paper-quality-critic" in index_text
    assert "decision: approve-for-staging" in hot_text
    assert "roles: editor=pass, reviewer=pass, domain=pass" in hot_text

    rollback = rollback_promotion(vault, slug)

    assert rollback["restored_state_paths"]["index"] == str(vault / "index.md")
    assert rollback["restored_state_paths"]["hot"] == str(vault / "hot.md")
    assert (vault / "index.md").read_text(encoding="utf-8") == original_index
    assert (vault / "hot.md").read_text(encoding="utf-8") == original_hot


def test_promote_to_wiki_cli_writes_routed_report_with_human_gate_and_all_pages(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_staged_paper(vault, slug)

    exit_code = _run_orchestrator_cli(
        monkeypatch,
        "promote-to-wiki",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--approved-by",
        "codex-test",
    )

    assert exit_code == 0
    run_dirs = _run_dirs(vault)
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((vault / "_runs" / "index.json").read_text(encoding="utf-8"))
    dashboard_text = (vault / "_runs" / "dashboard.md").read_text(encoding="utf-8")
    compiled_pages = _compiled_page_set(vault, slug)
    expected_written = [
        str(compiled_pages["reference"]),
        str(compiled_pages["concept"]),
        str(compiled_pages["synthesis"]),
    ]

    assert report_json["workflow_type"] == "promote-to-wiki"
    assert report_json["paper_states"] == [
        {"paper_slug": slug, "state": "promoted", "next_action": "review-promoted-pages"}
    ]
    assert report_json["failed_papers"] == []
    assert sorted(report_json["wiki_pages_written"]) == sorted(expected_written)
    assert report_json["human_gate"]["status"] == "approved"
    assert report_json["human_gate"]["approved_by"] == "codex-test"
    assert report_json["next_actions"] == ["review-promoted-pages"]
    assert "approved" in report_md
    for path in expected_written:
        assert path in report_md
    assert index_payload["runs"][0]["run_id"] == run_dir.name
    assert index_payload["runs"][0]["workflow_type"] == "promote-to-wiki"
    assert run_dir.name in dashboard_text


def test_rollback_promotion_cli_writes_routed_report_with_restored_and_removed_paths(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_staged_paper(
        vault,
        slug,
        existing_compiled="# Old Reference\n",
        existing_compiled_pages={"concept": "# Old Concept\n"},
    )
    promote_paper(vault, slug, approved_by="codex-test")

    exit_code = _run_orchestrator_cli(
        monkeypatch,
        "rollback-promotion",
        "--vault",
        str(vault),
        "--slug",
        slug,
    )

    assert exit_code == 0
    run_dirs = _run_dirs(vault)
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    compiled_pages = _compiled_page_set(vault, slug)
    expected_restored = [str(compiled_pages["reference"]), str(compiled_pages["concept"])]
    expected_removed = [str(compiled_pages["synthesis"])]

    assert report_json["workflow_type"] == "rollback-promotion"
    assert report_json["paper_states"] == [
        {"paper_slug": slug, "state": "rolled_back", "next_action": "re-review-before-repromote"}
    ]
    assert report_json["failed_papers"] == []
    assert report_json["wiki_pages_written"] == []
    assert sorted(report_json["restored_paths"]) == sorted(expected_restored)
    assert report_json["removed_paths"] == expected_removed
    assert report_json["next_actions"] == ["re-review-before-repromote"]
    for path in expected_restored + expected_removed:
        assert path in report_md
