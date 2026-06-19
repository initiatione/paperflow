import json

from paper_source.recommendation_output import build_session_recommendations
from paper_source.report_run import write_report
from paper_source.zotero_dedupe import (
    apply_zotero_dedupe_to_filter_report,
    not_checked_payload,
    unavailable_payload,
)
from paper_source.zotero_helper_adapter import ZoteroHelperAdapter
from zotero_helper_fixture import create_fake_zotero_plugin


def _candidate(title, doi, *, score=0.9, year=2026, authors=None):
    return {
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "doi": doi,
        "year": year,
        "authors": authors or ["Ada Lovelace"],
        "abstract": "A strong paper with reproducible experiments.",
        "pdf_url": "https://example.org/paper.pdf",
        "score": score,
        "quality_tier": "Tier A",
        "ranking_protocol": {"decision": "advance-candidate"},
        "verified_metrics": {"easyscholar": {"status": "verified"}},
        "citation_count": 5,
        "citation_count_status": "verified",
        "citation_count_source": "fixture",
    }


def test_zotero_dedupe_separates_exact_and_possible_matches(tmp_path, monkeypatch):
    plugin = create_fake_zotero_plugin(tmp_path)
    monkeypatch.setenv(
        "FAKE_ZOTERO_INVENTORY_JSON",
        json.dumps(
            [
                {
                    "key": "ZOTERO1",
                    "title": "Collected Exact Paper",
                    "DOI": "10.1000/exact",
                    "year": "2026",
                    "creators": [{"lastName": "Lovelace"}],
                },
                {
                    "key": "ZOTERO2",
                    "title": "Possible Duplicate Paper",
                    "year": "2026",
                    "creators": [{"lastName": "Hopper"}],
                },
            ]
        ),
    )
    monkeypatch.setenv("FAKE_ZOTERO_SEARCH_JSON", "[]")
    adapter = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False)
    exact = _candidate("Collected Exact Paper", "https://doi.org/10.1000/exact")
    possible = _candidate("Possible Duplicate Paper Study", "10.1000/other", authors=["Grace Hopper"])
    new = _candidate("New Paper", "10.1000/new")
    report = {
        "kept": [exact, possible, new],
        "recommendable": [exact, possible, new],
        "staging_ready": [exact, possible, new],
        "needs_pdf": [],
        "rejected": [],
    }

    result = apply_zotero_dedupe_to_filter_report(report, enabled=True, adapter=adapter)

    assert [item["title"] for item in result["kept"]] == ["New Paper"]
    assert result["kept"][0]["zotero_dedupe"]["candidate_status"] == "new_candidate"
    assert [item["zotero_dedupe"]["candidate_status"] for item in result["rejected"]] == [
        "already_in_zotero_not_wiki",
        "possible_zotero_duplicate",
    ]
    assert result["rejected"][0]["filter_reasons"] == ["already_in_zotero_not_wiki:ZOTERO1"]
    assert result["rejected"][1]["filter_reasons"] == ["possible_zotero_duplicate:ZOTERO2"]
    assert result["zotero_dedupe"]["summary"]["already_in_zotero_not_wiki"] == 1
    assert result["zotero_dedupe"]["summary"]["possible_zotero_duplicate"] == 1
    assert result["zotero_dedupe"]["summary"]["new_candidate"] == 1


def test_zotero_unavailable_keeps_candidates_visible_but_warns():
    class UnavailableAdapter:
        def status(self):
            return {"ok": False, "gate": "local_api_disabled", "message": "Local API disabled."}

    candidate = _candidate("Visible Candidate", "10.1000/visible")
    report = {
        "kept": [candidate],
        "recommendable": [candidate],
        "staging_ready": [candidate],
        "needs_pdf": [],
        "rejected": [],
    }

    result = apply_zotero_dedupe_to_filter_report(report, enabled=True, adapter=UnavailableAdapter())

    assert result["kept"][0]["zotero_dedupe"]["candidate_status"] == "zotero_unavailable"
    assert result["kept"][0]["zotero_dedupe"]["dedupe_warning"] == "local_api_disabled"
    assert result["zotero_dedupe"]["warnings"] == ["local_api_disabled"]
    assert result["rejected"] == []


def test_zotero_disabled_is_not_unavailable_warning():
    candidate = _candidate("Unchecked Candidate", "10.1000/unchecked")
    report = {
        "kept": [candidate],
        "recommendable": [candidate],
        "staging_ready": [candidate],
        "needs_pdf": [],
        "rejected": [],
    }

    result = apply_zotero_dedupe_to_filter_report(report, enabled=False)

    assert result["kept"][0]["zotero_dedupe"]["candidate_status"] == "not_checked"
    assert result["kept"][0]["zotero_dedupe"]["zotero_status"] == "not_checked"
    assert result["zotero_dedupe"]["status"] == "disabled"
    assert result["zotero_dedupe"]["warnings"] == []


def test_session_recommendations_project_zotero_dedupe_groups():
    ranked = [_candidate("New Ranked Paper", "10.1000/new")]
    ranked[0]["zotero_dedupe"] = {
        **not_checked_payload(),
        "dedupe_warning": "zotero_dedupe_disabled",
    }
    already = _candidate("Collected Paper", "10.1000/exact")
    already["zotero_dedupe"] = {
        "candidate_status": "already_in_zotero_not_wiki",
        "zotero_status": "exact_match",
        "zotero_item_key": "ZOTERO1",
        "identity_basis": "doi",
        "recommended_action": "Run Paper Wiki Zotero sync/apply to link or deposit this item.",
    }
    already["filter_reasons"] = ["already_in_zotero_not_wiki:ZOTERO1"]
    possible = _candidate("Possible Paper", "10.1000/possible")
    possible["zotero_dedupe"] = {
        "candidate_status": "possible_zotero_duplicate",
        "zotero_status": "possible_duplicate",
        "zotero_item_key": "ZOTERO2",
        "identity_basis": "title_similarity",
        "matched_title": "Possible Paper Extended",
        "recommended_action": "Review the possible Zotero duplicate before staging with Paper Source.",
    }
    possible["filter_reasons"] = ["possible_zotero_duplicate:ZOTERO2"]

    session = build_session_recommendations(ranked, [already, possible])

    assert [item["title"] for item in session["primary_recommendations"]] == ["New Ranked Paper"]
    assert session["primary_recommendations"][0]["zotero_dedupe"]["candidate_status"] == "not_checked"
    assert session["zotero_dedupe"]["summary"]["already_in_zotero_not_wiki"] == 1
    assert session["zotero_dedupe"]["summary"]["possible_zotero_duplicate"] == 1
    assert session["zotero_dedupe"]["already_in_zotero_not_wiki"][0]["zotero_item_key"] == "ZOTERO1"
    assert session["zotero_dedupe"]["possible_zotero_duplicates"][0]["identity_basis"] == "title_similarity"


def test_report_renders_zotero_dedupe_sections(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ranked = [_candidate("Unavailable But Ranked", "10.1000/unavailable")]
    ranked[0]["zotero_dedupe"] = unavailable_payload(
        {"ok": False, "gate": "zotero_desktop_unavailable", "message": "Zotero not reachable."}
    )
    already = _candidate("Collected Paper", "10.1000/exact")
    already["zotero_dedupe"] = {
        "candidate_status": "already_in_zotero_not_wiki",
        "zotero_status": "exact_match",
        "zotero_item_key": "ZOTERO1",
        "identity_basis": "doi",
        "recommended_action": "Run Paper Wiki Zotero sync/apply to link or deposit this item.",
    }
    already["filter_reasons"] = ["already_in_zotero_not_wiki:ZOTERO1"]

    write_report(run_dir, ranked, [], run_id="run-1", rejected=[already])

    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    payload = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert "### Zotero Discovery Dedupe" in markdown
    assert "#### Collected In Zotero But Not Deposited To Paper Wiki" in markdown
    assert "ZOTERO1" in markdown
    assert payload["session_recommendations"]["zotero_dedupe"]["summary"]["zotero_unavailable"] == 1
