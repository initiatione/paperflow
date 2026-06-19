import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "plugins" / "paper-wiki" / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from paper_wiki.zotero_report import (
    SCHEMA_VERSION,
    build_zotero_sync_report,
    validate_zotero_sync_report,
)


def test_build_zotero_sync_report_has_required_shape_and_redacts_diagnostics(tmp_path):
    report = build_zotero_sync_report(
        run_id="run-1",
        mode="dry-run",
        vault=tmp_path,
        zotero_helper={
            "ok": False,
            "gate": "local_api_disabled",
            "diagnostics": {"api_key": "secret", "stderr": "token=abc123"},
        },
        summary={"linked": 1},
        items=[{"page": "references/a.md", "outcome": "linked", "item_key": "ITEM1"}],
        gates=[{"gate": "local_api_disabled", "message": "Local API disabled"}],
        metadata_provenance=[{"page": "references/a.md", "source": "frontmatter"}],
        snapshots=[{"page": "references/a.md", "path": "_meta/zotero-sync/snapshots/a.md"}],
        bibtex={"path": "references.bib", "entry_count": 1},
        created_at="2026-06-19T00:00:00+00:00",
    )

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["target_collection"] == "Paper Wiki"
    assert validate_zotero_sync_report(report) == []
    assert report["zotero_helper"]["diagnostics"]["api_key"] == "<redacted>"
    assert "abc123" not in str(report)


def test_validate_zotero_sync_report_reports_bad_item_and_gate():
    report = build_zotero_sync_report(run_id="run-1", mode="apply", vault="vault")
    report["items"] = [{"outcome": "maybe"}]
    report["gates"] = [{"gate": "unknown_gate"}]

    issues = validate_zotero_sync_report(report)

    assert {issue["code"] for issue in issues} == {"invalid_item_outcome", "invalid_gate_code"}
