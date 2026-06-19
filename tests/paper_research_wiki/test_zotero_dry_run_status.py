import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "plugins" / "paper-wiki" / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from paper_wiki.zotero_status import (
    PLAN_SCHEMA_VERSION,
    build_zotero_status_plan,
    render_zotero_status_summary,
    write_zotero_diagnostic_report,
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
    zotero: str = "",
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
    if zotero:
        text += zotero
    text += """---
Body.
"""
    path = references / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


class FakeAdapter:
    def __init__(
        self,
        *,
        status_ok: bool = True,
        search_rows: list[dict] | None = None,
        inventory_rows: list[dict] | None = None,
        selected_target_ok: bool = True,
    ) -> None:
        self.status_ok = status_ok
        self.search_rows = search_rows or []
        self.inventory_rows = inventory_rows or []
        self.selected_target_ok = selected_target_ok

    def status(self):
        if self.status_ok:
            return {"ok": True, "gate": None, "data": {"api_running": True, "connector_running": True}}
        return {
            "ok": False,
            "gate": "local_api_disabled",
            "message": "Zotero local API is disabled.",
            "data": {"local_api_enabled_pref": False},
        }

    def search(self, query, *, with_bibtex_keys=False):
        query = str(query).lower()
        rows = [
            row
            for row in self.search_rows
            if query in json.dumps(row, ensure_ascii=False).lower()
        ]
        return {"ok": True, "data": rows}

    def export_item_bibtex(self, item_key):
        rows = [item for item in self.search_rows + self.inventory_rows if item.get("key") == item_key]
        if not rows:
            return {"ok": False, "gate": "zotero_helper_failed", "message": "missing item"}
        doi = " ".join(str(row.get("doi", "")) for row in rows)
        arxiv = " ".join(str(row.get("arxiv_id", "")) for row in rows)
        title = " ".join(str(row.get("title", "")) for row in rows)
        return {
            "ok": True,
            "data": f"@article{{{rows[0].get('bibtexKey', item_key)}, title={{{title}}}, doi={{{doi}}}, eprint={{{arxiv}}}}}",
        }

    def inventory(self):
        return {"ok": True, "data": self.inventory_rows}

    def selected_target(self, *, required_name=None):
        if self.selected_target_ok:
            return {"ok": True, "data": {"collection": {"name": required_name or "Paper Wiki"}}}
        return {
            "ok": False,
            "gate": "selected_target_mismatch",
            "message": "Selected Zotero target is 'Other', expected 'Paper Wiki'.",
        }


def test_status_with_missing_helper_scans_local_pages_and_does_not_write(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    page = _write_reference(vault, "formal-paper", doi="10.1000/formal")

    before = {path.relative_to(vault).as_posix() for path in vault.rglob("*") if path.is_file()}
    plan = build_zotero_status_plan(vault, mode="status", adapter=FakeAdapter(status_ok=False))
    after = {path.relative_to(vault).as_posix() for path in vault.rglob("*") if path.is_file()}

    assert before == after == {page.relative_to(vault).as_posix()}
    assert plan["schema_version"] == PLAN_SCHEMA_VERSION
    assert plan["writes_performed"] is False
    assert plan["summary"]["reference_pages"] == 1
    assert plan["summary"]["unavailable"] == 1
    assert plan["gates"][0]["gate"] == "local_api_disabled"
    rendered = render_zotero_status_summary(plan)
    assert "Zotero warnings" in rendered
    assert "local_api_disabled" in rendered


def test_dry_run_validates_doi_match_with_bibtex_and_reports_zotero_only_top_20(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    _write_reference(vault, "linked-plan", title="Formal DOI Paper", doi="10.1000/formal")
    inventory = [
        {"key": f"ONLY{i:02d}", "title": f"Zotero Only {i:02d}", "year": str(2026 - i)}
        for i in range(25)
    ]
    adapter = FakeAdapter(
        search_rows=[
            {
                "key": "ITEM1",
                "title": "Formal DOI Paper",
                "doi": "10.1000/formal",
                "year": "2026",
                "bibtexKey": "formal_2026",
            }
        ],
        inventory_rows=inventory,
    )

    plan = build_zotero_status_plan(vault, mode="dry-run", adapter=adapter)

    assert plan["summary"]["linked"] == 1
    assert plan["items"][0]["planned_action"] == "link_existing"
    assert plan["items"][0]["identity_basis"] == "doi"
    assert plan["zotero_only"]["total"] == 25
    assert len(plan["zotero_only"]["shown"]) == 20
    assert plan["zotero_only"]["truncated"] is True
    assert "Full Zotero-only output requires an explicit expand/export request" in render_zotero_status_summary(plan)


def test_dry_run_reports_selected_target_mismatch_as_future_apply_warning(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    _write_reference(vault, "ready-import", title="Wiki Only DOI Paper", doi="10.1000/wiki-only")

    plan = build_zotero_status_plan(
        vault,
        mode="dry-run",
        adapter=FakeAdapter(selected_target_ok=False),
    )

    assert plan["items"][0]["planned_action"] == "ready_for_import"
    assert plan["summary"]["ready_for_import"] == 1
    assert plan["gates"][0]["gate"] == "selected_target_mismatch"
    assert plan["summary"]["gates"] == 1


def test_multiple_wiki_pages_for_one_zotero_item_become_distinct_conflict(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    _write_reference(vault, "page-a", title="Duplicate Paper", doi="10.1000/a")
    _write_reference(vault, "page-b", title="Duplicate Paper Copy", doi="10.1000/b")
    adapter = FakeAdapter(
        search_rows=[
            {"key": "DUP", "title": "Duplicate Paper", "doi": "10.1000/a", "bibtexKey": "dup_a"},
            {"key": "DUP", "title": "Duplicate Paper Copy", "doi": "10.1000/b", "bibtexKey": "dup_b"},
        ]
    )

    plan = build_zotero_status_plan(vault, mode="dry-run", adapter=adapter)

    assert plan["summary"]["conflict"] == 2
    assert {item["reason"] for item in plan["items"]} == {"conflict_multiple_wiki_pages"}
    assert all(item["planned_action"] == "review_conflict" for item in plan["items"])


def test_persisted_diagnostic_requires_explicit_writer_call(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    _write_reference(vault, "formal-paper", doi="10.1000/formal")
    output = vault / "_meta" / "zotero-sync" / "dry-runs" / "report.json"

    plan = build_zotero_status_plan(vault, mode="status", adapter=FakeAdapter(status_ok=False))
    assert not output.exists()

    result = write_zotero_diagnostic_report(plan, output)

    assert result["path"] == str(output)
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == PLAN_SCHEMA_VERSION
