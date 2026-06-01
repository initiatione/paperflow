import json
import sys

import pytest

from epi.orchestrator import main
from epi.promote_to_wiki import promote_paper, rollback_promotion


def _run_orchestrator_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    return main()


def _run_dirs(vault):
    return [path for path in (vault / "_epi/runs").iterdir() if path.is_dir()]


def _seed_legacy_staged_paper(vault, slug):
    paper_root = vault / "_epi/raw" / "papers" / slug
    staging_root = vault / "_epi/staging" / "papers" / slug
    (paper_root / "critic").mkdir(parents=True)
    (staging_root / "references").mkdir(parents=True)
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture"}),
        encoding="utf-8",
    )
    (paper_root / "critic" / "critic-report.json").write_text(
        json.dumps({"outcome": "pass", "hard_rule": "No critic pass, no compiled wiki write."}),
        encoding="utf-8",
    )
    (staging_root / "references" / f"{slug}.md").write_text("# Legacy Draft\n", encoding="utf-8")
    (staging_root / "promotion-plan.json").write_text(
        json.dumps(
            {
                "paper_slug": slug,
                "critic_outcome": "pass",
                "staged_reference": str(staging_root / "references" / f"{slug}.md"),
                "compiled_targets": [f"references/{slug}.md"],
            }
        ),
        encoding="utf-8",
    )
    return paper_root


def test_promote_paper_is_deprecated_and_never_writes_formal_pages(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = _seed_legacy_staged_paper(vault, slug)

    with pytest.raises(ValueError, match="promote-to-wiki is deprecated"):
        promote_paper(vault, slug, approved_by="codex-test")

    assert not (vault / "references" / f"{slug}.md").exists()
    assert not (paper_root / "promotion-record.json").exists()


def test_promote_to_wiki_cli_writes_deprecated_failure_report_without_formal_pages(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_legacy_staged_paper(vault, slug)

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

    assert exit_code == 1
    assert not (vault / "references" / f"{slug}.md").exists()
    run_dirs = _run_dirs(vault)
    assert len(run_dirs) == 1
    report_json = json.loads((run_dirs[0] / "report.json").read_text(encoding="utf-8"))
    run_state = json.loads((run_dirs[0] / "run-state.json").read_text(encoding="utf-8"))
    assert report_json["status"] == "failed"
    assert "deprecated" in report_json["error"]
    assert report_json["wiki_pages_written"] == []
    assert report_json["next_actions"] == ["wiki-ingest-handoff"]
    assert run_state["compiled_wiki_write"] is False
    assert run_state["status"] == "failed"


def test_rollback_promotion_rejects_recorded_compiled_path_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = vault / "_epi/raw" / "papers" / slug
    paper_root.mkdir(parents=True)
    outside_page = tmp_path / "outside.md"
    outside_page.write_text("# Outside\n", encoding="utf-8")
    (paper_root / "promotion-record.json").write_text(
        json.dumps(
            {
                "page_transactions": [
                    {
                        "compiled_path": str(outside_page),
                        "previous_snapshot_path": None,
                    }
                ],
                "previous_state_snapshot_paths": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="compiled path"):
        rollback_promotion(vault, slug)

    assert outside_page.read_text(encoding="utf-8") == "# Outside\n"


def test_rollback_promotion_rejects_recorded_snapshot_path_outside_backups(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = vault / "_epi/raw" / "papers" / slug
    paper_root.mkdir(parents=True)
    compiled = vault / "references" / f"{slug}.md"
    compiled.parent.mkdir(parents=True)
    compiled.write_text("# Current\n", encoding="utf-8")
    outside_snapshot = tmp_path / "outside-snapshot.md"
    outside_snapshot.write_text("# Outside Snapshot\n", encoding="utf-8")
    (paper_root / "promotion-record.json").write_text(
        json.dumps(
            {
                "page_transactions": [
                    {
                        "compiled_path": str(compiled),
                        "previous_snapshot_path": str(outside_snapshot),
                    }
                ],
                "previous_state_snapshot_paths": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="snapshot path"):
        rollback_promotion(vault, slug)

    assert compiled.read_text(encoding="utf-8") == "# Current\n"

