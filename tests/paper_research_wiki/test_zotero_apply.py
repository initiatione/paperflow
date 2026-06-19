import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "plugins" / "paper-wiki" / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from paper_wiki.zotero_apply import (
    APPLY_SCHEMA_VERSION,
    apply_zotero_plan,
    build_zotero_apply_plan,
    make_apply_approval,
)


def _write_reference(
    vault: Path,
    name: str,
    *,
    title: str = "Formal Paper",
    doi: str | None = None,
    arxiv_id: str | None = None,
    year: int | None = 2026,
    authors: list[str] | None = None,
) -> Path:
    references = vault / "references"
    references.mkdir(parents=True, exist_ok=True)
    author_lines = "\n".join(f"  - {author}" for author in (authors or ["Ada Author"]))
    text = f"""---
title: {title}
source_id: {name}
year: {year}
authors:
{author_lines}
"""
    if doi:
        text += f"doi: {doi}\n"
    if arxiv_id:
        text += f"arxiv_id: {arxiv_id}\n"
    text += """---
Body.
"""
    path = references / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


class FakeApplyAdapter:
    def __init__(self, *, selected_target_ok=True, search_rows=None, post_import_rows=None):
        self.selected_target_ok = selected_target_ok
        self.search_rows = search_rows or []
        self.post_import_rows = post_import_rows or []
        self.imports = []

    def status(self):
        return {"ok": True, "gate": None, "data": {"api_running": True, "connector_running": True}}

    def inventory(self):
        return {"ok": True, "data": []}

    def selected_target(self, *, required_name=None):
        if self.selected_target_ok:
            return {"ok": True, "data": {"collection": {"name": required_name or "Paper Wiki"}}}
        return {
            "ok": False,
            "gate": "selected_target_mismatch",
            "message": "Selected Zotero target is 'Other', expected 'Paper Wiki'.",
        }

    def search(self, query, *, with_bibtex_keys=False):
        query = str(query).lower()
        rows_source = self.search_rows + (self.post_import_rows if self.imports else [])
        rows = [
            row for row in rows_source if query in json.dumps(row, ensure_ascii=False).lower()
        ]
        return {"ok": True, "data": rows}

    def export_item_bibtex(self, item_key):
        rows = [
            row
            for row in self.search_rows + self.post_import_rows
            if row.get("key") == item_key or row.get("item_key") == item_key
        ]
        row = rows[0] if rows else {"title": "Unknown", "doi": "", "bibtexKey": item_key}
        return {
            "ok": True,
            "data": (
                f"@article{{{row.get('bibtexKey', item_key)}, "
                f"title={{{row.get('title', 'Unknown')}}}, doi={{{row.get('doi', '')}}}}}"
            ),
        }

    def import_bibtex(self, *, file=None, text=None, session=None, approved=False):
        self.imports.append({"text": text, "session": session, "approved": approved})
        return {"ok": True, "data": {"imported": 1}}


def _vault_files(vault: Path) -> set[str]:
    return {path.relative_to(vault).as_posix() for path in vault.rglob("*") if path.is_file()}


def test_apply_refuses_without_approval_and_performs_no_writes(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    _write_reference(vault, "formal-paper", title="Formal DOI Paper", doi="10.1000/formal")
    adapter = FakeApplyAdapter(
        post_import_rows=[
            {
                "key": "ITEM1",
                "title": "Formal DOI Paper",
                "doi": "10.1000/formal",
                "bibtexKey": "formal_2026",
            }
        ]
    )
    plan = build_zotero_apply_plan(vault, adapter=adapter)
    before = _vault_files(vault)

    result = apply_zotero_plan(vault, plan=plan, adapter=adapter, approval=None)

    assert result["ok"] is False
    assert result["gate"] == "write_not_authorized"
    assert result["writes_performed"] is False
    assert _vault_files(vault) == before


def test_apply_selected_target_mismatch_blocks_import_writes_but_records_report(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    _write_reference(vault, "wiki-only", title="Wiki Only DOI Paper", doi="10.1000/wiki-only")
    adapter = FakeApplyAdapter(selected_target_ok=False)
    plan = build_zotero_apply_plan(vault, adapter=adapter)
    approval = make_apply_approval(plan)

    result = apply_zotero_plan(vault, plan=plan, approval=approval, adapter=adapter, run_id="run-target")

    assert result["ok"] is False
    assert result["gate"] == "selected_target_mismatch"
    assert adapter.imports == []
    report = json.loads((vault / "_meta" / "zotero-sync" / "runs" / "run-target.json").read_text(encoding="utf-8"))
    assert report["gates"][0]["gate"] == "selected_target_mismatch"
    assert report["items"][0]["outcome"] == "failed"


def test_apply_links_existing_zotero_item_refreshes_index_and_bibtex(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    page = _write_reference(vault, "linked", title="Formal DOI Paper", doi="10.1000/formal")
    adapter = FakeApplyAdapter(
        search_rows=[
            {
                "key": "ITEM1",
                "title": "Formal DOI Paper",
                "doi": "10.1000/formal",
                "bibtexKey": "formal_2026",
            }
        ]
    )
    plan = build_zotero_apply_plan(vault, adapter=adapter)
    result = apply_zotero_plan(vault, plan=plan, approval=make_apply_approval(plan), adapter=adapter, run_id="run-link")

    text = page.read_text(encoding="utf-8")
    assert result["ok"] is True
    assert "sync_status: linked" in text
    assert "item_key: ITEM1" in text
    assert "identity_basis: doi" in text
    assert adapter.imports == []
    assert "@article{formal_2026" in (vault / "references.bib").read_text(encoding="utf-8")
    index = json.loads((vault / "_meta" / "reference-index.json").read_text(encoding="utf-8"))
    linked = index["entries"][0]
    assert linked["zotero"]["item_key"] == "ITEM1"
    report = json.loads((vault / "_meta" / "zotero-sync" / "runs" / "run-link.json").read_text(encoding="utf-8"))
    assert report["summary"]["linked"] == 1
    assert report["post_task_check"]["reference_index_exists"] is True


def test_apply_imports_wiki_only_page_and_writes_imported_metadata(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    page = _write_reference(vault, "imported", title="Wiki Only DOI Paper", doi="10.1000/wiki-only")
    adapter = FakeApplyAdapter(
        post_import_rows=[
            {
                "key": "NEW1",
                "title": "Wiki Only DOI Paper",
                "doi": "10.1000/wiki-only",
                "bibtexKey": "wiki_only_2026",
            }
        ]
    )
    plan = build_zotero_apply_plan(vault, adapter=adapter)

    result = apply_zotero_plan(vault, plan=plan, approval=make_apply_approval(plan), adapter=adapter, run_id="run-import")

    text = page.read_text(encoding="utf-8")
    assert result["ok"] is True
    assert len(adapter.imports) == 1
    assert adapter.imports[0]["approved"] is True
    assert "sync_status: imported" in text
    assert "item_key: NEW1" in text
    assert "10.1000/wiki-only" in (vault / "references.bib").read_text(encoding="utf-8")


def test_apply_metadata_supplementation_overwrite_creates_single_page_snapshot(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    page = _write_reference(vault, "missing-id", title="Missing Identity Paper", year=2024)
    adapter = FakeApplyAdapter(
        post_import_rows=[
            {
                "key": "META1",
                "title": "Missing Identity Paper",
                "doi": "10.1000/recovered",
                "bibtexKey": "missing_identity_2026",
            }
        ]
    )
    plan = build_zotero_apply_plan(vault, adapter=adapter)

    def provider(item):
        return {
            "source": "fixture-search",
            "query": item["title"],
            "confidence": "high",
            "doi": "10.1000/recovered",
            "year": 2026,
        }

    result = apply_zotero_plan(
        vault,
        plan=plan,
        approval=make_apply_approval(plan),
        adapter=adapter,
        metadata_provider=provider,
        run_id="run-metadata",
    )

    assert result["ok"] is True
    text = page.read_text(encoding="utf-8")
    assert "doi: 10.1000/recovered" in text
    assert "year: 2026" in text
    snapshot = vault / "_paper_source" / "meta" / "formal-page-snapshots" / "run-metadata-pre-zotero-sync" / "references" / "missing-id.md"
    assert snapshot.exists()
    assert "year: 2024" in snapshot.read_text(encoding="utf-8")
    report = json.loads((vault / "_meta" / "zotero-sync" / "runs" / "run-metadata.json").read_text(encoding="utf-8"))
    assert report["metadata_provenance"][0]["source"] == "fixture-search"
    assert report["overwrite_diffs"][0]["diffs"]
