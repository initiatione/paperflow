import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "paper-wiki" / "scripts" / "migrate_formal_page_contract.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("paper_wiki_migrate_formal_page_contract", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_migrate_page_rewrites_sources_lifecycle_and_body_paths(tmp_path):
    module = _load_module()
    page = tmp_path / "vault" / "references" / "fixture.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "\n".join(
            [
                "---",
                'title: "Fixture"',
                "category: references",
                "page_family: references",
                'sources: ["[Fixture](obsidian://open?vault=paper-research-wiki&file=_epi%2Fraw%2Ffixture-paper%2Fpaper.pdf)"]',
                "lifecycle: review-needed",
                "lifecycle_changed: 2026-06-08",
                "updated: 2026-06-08",
                "---",
                "",
                "## 原文与证据入口",
                "",
                "- 原论文 PDF：[Fixture](obsidian://open?vault=paper-research-wiki&file=_epi%2Fraw%2Ffixture-paper%2Fpaper.pdf)",
                "- Source bundle：`_epi/raw/fixture-paper/paper.pdf`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = module.migrate_page(page)

    assert result["changed"] is True
    assert 'sources: ["[Fixture](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Ffixture-paper%2Fpaper.pdf)"]' in result["text"]
    assert "lifecycle: draft" in result["text"]
    assert "review-needed" not in result["text"]
    assert "_epi%2Fraw%2Ffixture-paper%2Fpaper.pdf" not in result["text"]
    assert "_paper_source%2Fraw%2Ffixture-paper%2Fpaper.pdf" in result["text"]
    assert "_paper_source/raw/fixture-paper/paper.pdf" in result["text"]
    assert "[Fixture](obsidian://open" in result["text"]
    assert "[原论文 PDF](obsidian://open" not in result["text"]


def test_migrate_page_adds_source_entry_section_when_missing(tmp_path):
    module = _load_module()
    page = tmp_path / "vault" / "concepts" / "fixture.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "\n".join(
            [
                "---",
                'title: "Fixture"',
                "category: concepts",
                "page_family: concepts",
                'sources: ["[Fixture](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Ffixture-paper%2Fpaper.pdf)", "[Other](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Fother-paper%2Fpaper.pdf)"]',
                "lifecycle: draft",
                "lifecycle_changed: 2026-06-11",
                "updated: 2026-06-11",
                "---",
                "",
                "# Fixture",
                "",
                "Body.",
                "",
                "## Provenance",
                "",
                "- source-grounded",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = module.migrate_page(page, vault_name="paper-research-wiki")

    assert result["inserted_source_section"] is True
    assert "## 原文与证据入口" in result["text"]
    assert "- 原论文 PDF：[Fixture](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Ffixture-paper%2Fpaper.pdf)" in result["text"]
    assert "- 原论文 PDF：[Other](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Fother-paper%2Fpaper.pdf)" in result["text"]
    assert result["text"].index("## 原文与证据入口") < result["text"].index("## Provenance")


def test_migrate_page_rewrites_block_list_sources(tmp_path):
    module = _load_module()
    page = tmp_path / "vault" / "experiments" / "fixture.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "\n".join(
            [
                "---",
                'title: "Fixture Experiment"',
                "category: experiments",
                "page_family: experiments",
                "sources:",
                "  - fixture-paper",
                "  - other-paper",
                "lifecycle: draft",
                "lifecycle_changed: 2026-06-11",
                "updated: 2026-06-11",
                "---",
                "",
                "# Fixture Experiment",
                "",
                "## 原文与证据入口",
                "",
                "- 原论文 PDF：[原论文 PDF](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Ffixture-paper%2Fpaper.pdf)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = module.migrate_page(
        page,
        vault_name="paper-research-wiki",
        source_titles={"fixture-paper": "Fixture", "other-paper": "Other"},
    )

    assert result["changed"] is True
    assert 'sources: ["[Fixture](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Ffixture-paper%2Fpaper.pdf)", "[Other](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Fother-paper%2Fpaper.pdf)"]' in result["text"]
    assert "  - fixture-paper" not in result["text"]
    assert "[原论文 PDF](obsidian://open" not in result["text"]
    assert "[Fixture](obsidian://open" in result["text"]


def test_snapshot_formal_pages_writes_under_paper_source_and_detaches_links(tmp_path):
    module = _load_module()
    vault = tmp_path / "vault"
    page = vault / "concepts" / "fixture.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("Body links [[references/source-paper]] and [[concepts/target|target alias]].\n", encoding="utf-8")

    snapshot = module._snapshot_formal_pages(vault, "snapshot-test", execute=True)

    assert snapshot == "_paper_source/meta/formal-page-snapshots/snapshot-test/"
    text = (
        vault
        / "_paper_source"
        / "meta"
        / "formal-page-snapshots"
        / "snapshot-test"
        / "concepts"
        / "fixture.md"
    ).read_text(encoding="utf-8")
    assert "[[" not in text
    assert "references/source-paper" in text
    assert "target alias" in text

    manifest = json.loads(
        (
            vault
            / "_paper_source"
            / "meta"
            / "formal-page-snapshots"
            / "snapshot-test"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["file_count"] == 1
    record = manifest["files"][0]
    assert record["path"] == "concepts/fixture.md"
    assert record["snapshot_path"] == (
        "_paper_source/meta/formal-page-snapshots/snapshot-test/concepts/fixture.md"
    )
    assert len(record["original_sha256"]) == 64
    assert len(record["snapshot_sha256"]) == 64
    assert record["original_sha256"] != record["snapshot_sha256"]
    assert record["original_bytes"] > record["snapshot_bytes"]
    assert record["wikilinks_detached"] is True
