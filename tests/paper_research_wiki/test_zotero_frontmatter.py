import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "plugins" / "paper-wiki" / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from paper_wiki.frontmatter import parse_frontmatter, replace_frontmatter
from paper_wiki.zotero_contract import is_bibtex_eligible, normalize_zotero_metadata
from paper_wiki.reference_index import refresh_reference_index


def test_nested_zotero_frontmatter_round_trips_without_touching_body():
    text = """---
title: Formal Paper
tags:
  - domain/auv
zotero:
  sync_status: linked
  item_key: PXW99EKT
  bibtex_key: formal_2026
  collection: Paper Wiki
  identity_basis: doi
---
# Body

Keep this exact body.
"""

    document = parse_frontmatter(text)
    document.frontmatter["zotero"]["last_checked_at"] = "2026-06-19T00:00:00+08:00"
    rendered = replace_frontmatter(text, document.frontmatter)
    reparsed = parse_frontmatter(rendered)

    assert document.frontmatter["tags"] == ["domain/auv"]
    assert document.frontmatter["zotero"]["sync_status"] == "linked"
    assert rendered.endswith("# Body\n\nKeep this exact body.\n")
    assert reparsed.frontmatter["zotero"]["last_checked_at"] == "2026-06-19T00:00:00+08:00"


def test_invalid_zotero_sync_status_is_structured_issue():
    metadata, issues = normalize_zotero_metadata({"sync_status": "synced", "item_key": "ITEM1"})

    assert metadata is None
    assert issues == [
        {
            "code": "zotero_sync_status_invalid",
            "field": "zotero.sync_status",
            "value": "synced",
            "allowed": [
                "unlinked",
                "linked",
                "imported",
                "skipped",
                "conflict",
                "zotero_unavailable",
            ],
        }
    ]


def test_body_tail_frontmatter_is_reported_but_not_used_as_metadata():
    text = """---
title: Formal Paper
---
Body.

---
zotero:
  sync_status: linked
  item_key: BODYTAIL
---
"""

    document = parse_frontmatter(text)

    assert document.frontmatter == {"title": "Formal Paper"}
    assert document.issues[0]["code"] == "body_frontmatter_block_unsupported"


def test_reference_index_promotes_only_valid_optional_zotero_metadata(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    references = vault / "references"
    references.mkdir(parents=True)
    (references / "linked.md").write_text(
        """---
title: Linked Paper
source_id: linked-paper
doi: 10.1000/linked
zotero:
  sync_status: linked
  item_key: ITEM1
  bibtex_key: linked_2026
  collection: Paper Wiki
  identity_basis: doi
---
Body.
""",
        encoding="utf-8",
    )
    (references / "invalid.md").write_text(
        """---
title: Invalid Paper
source_id: invalid-paper
zotero:
  sync_status: synced
  item_key: ITEM2
---
Body.
""",
        encoding="utf-8",
    )
    raw = vault / "_paper_source" / "raw" / "raw-only"
    raw.mkdir(parents=True)
    (raw / "metadata.json").write_text(json.dumps({"slug": "raw-only", "title": "Raw Only"}), encoding="utf-8")

    refresh_reference_index(vault)
    payload = json.loads((vault / "_meta" / "reference-index.json").read_text(encoding="utf-8"))

    linked = next(item for item in payload["entries"] if item["source_id"] == "linked-paper")
    invalid = next(item for item in payload["entries"] if item["source_id"] == "invalid-paper")
    raw_only = next(item for item in payload["entries"] if item["source_id"] == "raw-only")
    assert linked["zotero"] == {
        "sync_status": "linked",
        "item_key": "ITEM1",
        "bibtex_key": "linked_2026",
        "collection": "Paper Wiki",
        "identity_basis": "doi",
    }
    assert "zotero" not in invalid
    assert "zotero" not in raw_only
    assert "doi:10.1000/linked" in linked["dedupe_keys"]


def test_bibtex_eligibility_requires_linked_or_imported_item_key():
    assert is_bibtex_eligible({"sync_status": "linked", "item_key": "ITEM1"})
    assert is_bibtex_eligible({"sync_status": "imported", "item_key": "ITEM2"})
    assert not is_bibtex_eligible({"sync_status": "skipped", "item_key": "ITEM3"})
    assert not is_bibtex_eligible({"sync_status": "linked"})
