import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "plugins" / "paper-wiki" / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from paper_wiki.bibtex import bibtex_entry_key, compose_wiki_scoped_bibtex


def test_compose_wiki_scoped_bibtex_includes_only_linked_or_imported_records():
    result = compose_wiki_scoped_bibtex(
        [
            {
                "page": "references/linked.md",
                "sync_status": "linked",
                "item_key": "ITEM1",
                "bibtex": "@article{linked_2026, title={Linked}}\n",
            },
            {
                "page": "references/imported.md",
                "sync_status": "imported",
                "item_key": "ITEM2",
                "bibtex": "@article{imported_2026, title={Imported}}\n",
            },
            {
                "page": "references/skipped.md",
                "sync_status": "skipped",
                "item_key": "ITEM3",
                "bibtex": "@article{skipped_2026, title={Skipped}}\n",
            },
        ]
    )

    assert "linked_2026" in result["content"]
    assert "imported_2026" in result["content"]
    assert "skipped_2026" not in result["content"]
    assert result["diagnostics"]["counts"] == {"included": 2, "skipped": 1, "duplicates": 0}


def test_compose_wiki_scoped_bibtex_dedupes_by_bibtex_key_before_item_key():
    result = compose_wiki_scoped_bibtex(
        [
            {
                "page": "references/a.md",
                "sync_status": "linked",
                "item_key": "ITEM1",
                "bibtex": "@article{same_key, title={A}}\n",
            },
            {
                "page": "references/b.md",
                "sync_status": "linked",
                "item_key": "ITEM2",
                "bibtex": "@article{same_key, title={B}}\n",
            },
            {
                "page": "references/c.md",
                "sync_status": "linked",
                "item_key": "ITEM3",
                "bibtex": "not really bibtex",
                "bibtex_key": "fallback_key",
            },
        ]
    )

    assert result["content"].count("@article{same_key") == 1
    assert "not really bibtex" in result["content"]
    assert result["diagnostics"]["counts"] == {"included": 2, "skipped": 0, "duplicates": 1}
    assert result["diagnostics"]["duplicates"][0]["key"] == "same_key"


def test_bibtex_entry_key_extracts_key():
    assert bibtex_entry_key("@inproceedings{paper_key,\ntitle={Paper}}") == "paper_key"
    assert bibtex_entry_key("plain text") is None
