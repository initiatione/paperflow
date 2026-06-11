import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "paper-wiki" / "scripts" / "maintain_related.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("paper_wiki_maintain_related", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_update_page_appends_related_from_multiline_relationships(tmp_path):
    module = _load_module()
    page = tmp_path / "vault" / "synthesis" / "fixture.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "\n".join(
            [
                "---",
                "relationships:",
                '  - target: "[[concepts/auv-planning]]"',
                "    type: related_to",
                '  - target: "[[references/source-paper]]"',
                "    type: uses",
                "---",
                "",
                "# Fixture",
                "",
                "Body.",
                "",
                "## Provenance",
                "",
                "- Claim: source-grounded.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = module.update_page(page, execute=True)

    assert result.changed is True
    text = page.read_text(encoding="utf-8")
    assert text.endswith(
        "\n## Related\n\n"
        "- [[concepts/auv-planning]]\n"
        "- [[references/source-paper]]\n"
    )


def test_update_page_replaces_related_and_filters_internal_targets(tmp_path):
    module = _load_module()
    page = tmp_path / "vault" / "references" / "fixture.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "\n".join(
            [
                "---",
                'relationships: [{target: "[[concepts/auv-planning]]", type: related_to}, {target: "[[concepts/auv-planning]]", type: uses}, {target: "[[_paper_source/raw/paper/paper.pdf]]", type: related_to}]',
                "---",
                "",
                "# Fixture",
                "",
                "## Provenance",
                "",
                "- Claim: source-grounded.",
                "",
                "## Related",
                "",
                "- [[stale-link]]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = module.update_page(page, execute=True)

    assert result.changed is True
    text = page.read_text(encoding="utf-8")
    assert "[[stale-link]]" not in text
    related = text.split("## Related", 1)[1]
    assert "_paper_source" not in related
    assert related.count("[[concepts/auv-planning]]") == 1
    assert text.endswith("\n## Related\n\n- [[concepts/auv-planning]]\n")


def test_update_page_only_renders_formal_page_relationship_targets(tmp_path):
    module = _load_module()
    page = tmp_path / "vault" / "references" / "fixture.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "\n".join(
            [
                "---",
                "relationships:",
                '  - target: "[[references/source-paper]]"',
                "    type: related_to",
                '  - target: "[[loose-unresolved-page]]"',
                "    type: related_to",
                '  - target: "[[entities/non-paper-node]]"',
                "    type: related_to",
                '  - target: "[[_epi/meta/formal-page-snapshots/old/references/source-paper]]"',
                "    type: related_to",
                "---",
                "",
                "# Fixture",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = module.update_page(page, execute=True)

    assert result.targets == ["[[references/source-paper]]"]
    text = page.read_text(encoding="utf-8")
    related = text.split("## Related", 1)[1]
    assert "- [[references/source-paper]]" in related
    assert "loose-unresolved-page" not in related
    assert "entities/non-paper-node" not in related
    assert "_epi" not in related


def test_snapshot_formal_pages_detaches_wikilinks_in_snapshot_copy(tmp_path):
    module = _load_module()
    vault = tmp_path / "vault"
    page = vault / "synthesis" / "fixture.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "Body links [[references/source-paper]] and [[concepts/target|target alias]].\n",
        encoding="utf-8",
    )

    snapshot = module._snapshot_formal_pages(vault, "snapshot-test", execute=True)

    assert snapshot == "_epi/meta/formal-page-snapshots/snapshot-test/"
    snapshot_text = (
        vault
        / "_epi"
        / "meta"
        / "formal-page-snapshots"
        / "snapshot-test"
        / "synthesis"
        / "fixture.md"
    ).read_text(encoding="utf-8")
    assert "[[" not in snapshot_text
    assert "references/source-paper" in snapshot_text
    assert "target alias" in snapshot_text


def test_detach_internal_markdown_links_breaks_backlinks_from_internal_trees(tmp_path):
    module = _load_module()
    vault = tmp_path / "vault"
    internal = vault / "_epi" / "staging" / "papers" / "fixture" / "draft.md"
    raw = vault / "_paper_source" / "raw" / "fixture" / "mineru" / "paper.md"
    internal.parent.mkdir(parents=True)
    raw.parent.mkdir(parents=True)
    internal.write_text(
        "Draft points to [[references/source-paper]] and [[concepts/target|target alias]].\n",
        encoding="utf-8",
    )
    raw.write_text("Raw MinerU has [[not-a-formal-link]].\n", encoding="utf-8")

    result = module.detach_internal_markdown_links(vault, execute=True)

    assert result["changed"] == ["_epi/staging/papers/fixture/draft.md"]
    assert "[[" not in internal.read_text(encoding="utf-8")
    assert "[[not-a-formal-link]]" in raw.read_text(encoding="utf-8")
