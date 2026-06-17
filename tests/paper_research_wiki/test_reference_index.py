import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "plugins" / "paper-wiki" / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from paper_wiki.reference_index import refresh_reference_index


def test_refresh_reference_index_records_formal_reference_pages_and_raw_fallback(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    references = vault / "references"
    references.mkdir(parents=True)
    raw = vault / "_paper_source" / "raw" / "formal-paper"
    raw.mkdir(parents=True)
    (raw / "metadata.json").write_text(
        json.dumps(
            {
                "slug": "formal-paper",
                "title": "Formal Paper From Raw",
                "doi": "10.1000/raw-copy",
            }
        ),
        encoding="utf-8",
    )
    (references / "formal-paper.md").write_text(
        """---
title: Formal Paper
source_id: formal-paper
doi: 10.1000/formal
arxiv_id: 2601.12345v2
year: 2026
venue: ICRA
tags:
  - domain/auv
aliases:
  - Formal AUV Paper
lifecycle: draft
tier: core
---

## 原文与证据入口

- 原论文 PDF：[Formal Paper](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Fformal-paper%2Fpaper.pdf)
""",
        encoding="utf-8",
    )
    raw_only = vault / "_paper_source" / "raw" / "raw-only"
    raw_only.mkdir(parents=True)
    (raw_only / "metadata.json").write_text(
        json.dumps(
            {
                "slug": "raw-only",
                "title": "Raw Only Paper",
                "doi": "https://doi.org/10.1000/raw-only",
                "arxiv_id": "2602.54321v1",
                "year": 2026,
            }
        ),
        encoding="utf-8",
    )

    result = refresh_reference_index(vault)
    payload = json.loads((vault / "_meta" / "reference-index.json").read_text(encoding="utf-8"))

    assert result["record_count"] == 2
    assert payload["schema_version"] == "paper-research-reference-index-v1"
    assert payload["record_count"] == 2
    formal = next(item for item in payload["entries"] if item["source_id"] == "formal-paper")
    assert formal["page"] == "references/formal-paper.md"
    assert formal["doi"] == "10.1000/formal"
    assert formal["arxiv_base_id"] == "2601.12345"
    assert "doi:10.1000/formal" in formal["dedupe_keys"]
    assert "arxiv:2601.12345" in formal["dedupe_keys"]
    raw_entry = next(item for item in payload["entries"] if item["source_id"] == "raw-only")
    assert raw_entry["page"] is None
    assert raw_entry["status"] == "collected"
    assert raw_entry["doi"] == "10.1000/raw-only"
