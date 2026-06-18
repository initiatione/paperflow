import json
from pathlib import Path

from paper_source.orchestrator import run_dry_run


def _write_template(plugin_root: Path, grok_mode: str) -> None:
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: general_academic_research\n"
        "domains:\n"
        "  - robotics\n"
        "budget:\n"
        "  max_results: 5\n"
        "grok_search:\n"
        f"  mode: {grok_mode}\n",
        encoding="utf-8",
    )


def _paper_record(index: int) -> dict:
    return {
        "source": "semantic",
        "title": f"Robot Control Paper {index}",
        "authors": ["A. Researcher"],
        "year": 2025,
        "venue": "ICRA",
        "abstract": "Robotics control experiments with stable paper identity.",
        "doi": f"10.1000/robot-{index}",
        "pdf_url": f"https://example.org/robot-{index}.pdf",
        "citation_count": 10 + index,
    }


def _paper_search_record(records: list[dict]) -> dict:
    return {
        "query": "robotics control",
        "max_results": 5,
        "source_mode": "paper_search_mcp",
        "raw_response_path": "paper-search-raw.json",
        "records": records,
        "upstream": {
            "sources_used": ["semantic"],
            "source_results": {"semantic": len(records)},
            "errors": {},
            "total": len(records),
        },
    }


def test_targeted_grok_skips_when_paper_search_is_good_enough(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_template(plugin_root, "targeted")
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    monkeypatch.setattr(
        "paper_source.orchestrator._run_query_plan_discovery",
        lambda **kwargs: _paper_search_record([_paper_record(1), _paper_record(2), _paper_record(3)]),
    )

    def fail_grok(**kwargs):
        raise AssertionError("targeted Grok should be skipped")

    monkeypatch.setattr("paper_source.orchestrator._run_grok_queries", fail_grok)

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=None,
        sources=["semantic"],
        use_query_plan=False,
        resume=False,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    assert (run_dir / "paper-search-record.json").exists()
    assert not (run_dir / "grok-search-record.json").exists()
    assert search_record["provider_records"]["grok_search"]["status"] == "skipped_good_enough"
    assert search_record["provider_records"]["grok_search"]["reason"] == "paper_search_good_enough"


def test_parallel_grok_writes_provider_artifacts_and_merged_search_record(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_template(plugin_root, "parallel")
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    monkeypatch.setattr(
        "paper_source.orchestrator._run_query_plan_discovery",
        lambda **kwargs: _paper_search_record([_paper_record(1)]),
    )
    captured = {}

    def fake_grok(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "grok_search",
            "source_mode": "grok_search_mcp",
            "status": "ok",
            "queries": kwargs["queries"],
            "records": [
                {
                    "source": "grok_search",
                    "provider": "grok_search",
                    "title": "Publisher Supplemental Robot Paper",
                    "abstract": "Robotics control paper from a publisher gap search.",
                    "doi": "10.1000/grok-robot",
                    "landing_page_url": "https://publisher.example/grok-robot",
                }
            ],
            "evidence": [],
            "raw_response_path": str(kwargs["run_dir"] / "grok-search-raw.json"),
            "evidence_path": str(kwargs["run_dir"] / "grok-search-evidence.json"),
        }

    monkeypatch.setattr("paper_source.orchestrator._run_grok_queries", fake_grok)

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=None,
        sources=["semantic"],
        use_query_plan=False,
        resume=False,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    assert (run_dir / "paper-search-record.json").exists()
    assert (run_dir / "grok-search-record.json").exists()
    assert search_record["provider_records"]["paper_search"]["record_count"] == 1
    assert search_record["provider_records"]["grok_search"]["record_count"] == 1
    assert len(search_record["records"]) == 2
    assert captured["queries"]
    assert captured["include_domains"]


def test_targeted_doi_recovery_uses_grok_to_restore_missing_doi_candidate(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_template(plugin_root, "targeted")
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    paper_records = [_paper_record(1), _paper_record(2), _paper_record(3)]
    for record in paper_records:
        record.pop("doi", None)
    monkeypatch.setattr(
        "paper_source.orchestrator._run_query_plan_discovery",
        lambda **kwargs: _paper_search_record(paper_records),
    )
    captured = {}

    def fake_discover_grok(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "grok_search",
            "source_mode": "grok_search_mcp",
            "status": "ok",
            "queries": kwargs["queries"],
            "records": [
                {
                    "source": "grok_search",
                    "provider": "grok_search",
                    "title": "Robot Control Paper 1",
                    "abstract": "Publisher metadata with DOI.",
                    "doi": "10.1000/recovered-robot-1",
                    "landing_page_url": "https://doi.org/10.1000/recovered-robot-1",
                }
            ],
            "evidence": [],
            "raw_response_path": str(kwargs["raw_response_path"]),
            "evidence_path": str(kwargs["evidence_path"]),
        }

    monkeypatch.setattr("paper_source.orchestrator.discover_grok", fake_discover_grok)

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=None,
        sources=["semantic"],
        use_query_plan=False,
        resume=False,
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    session = report_json["session_recommendations"]
    assert (run_dir / "doi-recovery-grok-record.json").exists()
    assert captured["include_domains"] == ["doi.org", "openalex.org", "crossref.org", "arxiv.org"]
    assert session["doi_recovery_summary"]["recovered_count"] == 1
    assert session["doi_recovery_summary"]["failed_count"] == 2
    assert [item["title"] for item in session["primary_recommendations"]] == ["Robot Control Paper 1"]
    assert session["primary_recommendations"][0]["doi"] == "10.1000/recovered-robot-1"
    assert session["doi_filtered_summary"]["total"] == 2


def test_targeted_doi_recovery_rejects_grok_warning_records(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_template(plugin_root, "targeted")
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    paper_records = [_paper_record(1), _paper_record(2), _paper_record(3)]
    for record in paper_records:
        record.pop("doi", None)
    monkeypatch.setattr(
        "paper_source.orchestrator._run_query_plan_discovery",
        lambda **kwargs: _paper_search_record(paper_records),
    )

    def fake_discover_grok(**kwargs):
        return {
            "provider": "grok_search",
            "source_mode": "grok_search_mcp",
            "status": "warning",
            "queries": kwargs["queries"],
            "records": [
                {
                    "source": "grok_search",
                    "provider": "grok_search",
                    "title": "Robot Control Paper 1",
                    "doi": "10.1000/fallback-robot-1",
                }
            ],
            "warnings": ["source_fallback"],
            "evidence": [],
            "raw_response_path": str(kwargs["raw_response_path"]),
            "evidence_path": str(kwargs["evidence_path"]),
        }

    monkeypatch.setattr("paper_source.orchestrator.discover_grok", fake_discover_grok)

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=None,
        sources=["semantic"],
        use_query_plan=False,
        resume=False,
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    session = report_json["session_recommendations"]
    assert session["doi_recovery_summary"]["reason"] == "grok_status_not_ok"
    assert session["doi_recovery_summary"]["recovered_count"] == 0
    assert session["doi_recovery_summary"]["failed_count"] == 3
    assert session["primary_recommendations"] == []
    assert session["doi_filtered_summary"]["total"] == 3


def test_parallel_grok_records_filter_rank_no_contribution_diagnostics(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_template(plugin_root, "parallel")
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    monkeypatch.setattr(
        "paper_source.orchestrator._run_query_plan_discovery",
        lambda **kwargs: _paper_search_record([_paper_record(1)]),
    )

    def fake_grok(**kwargs):
        return {
            "provider": "grok_search",
            "source_mode": "grok_search_mcp",
            "status": "ok",
            "queries": kwargs["queries"],
            "records": [
                {
                    "source": "grok_search",
                    "provider": "grok_search",
                    "title": "Marine Biology Sensor Dataset",
                    "abstract": "A marine biology dataset for coral reef surveys.",
                    "doi": "10.1000/grok-marine",
                    "landing_page_url": "https://doi.org/10.1000/grok-marine",
                }
            ],
            "evidence": [],
            "raw_response_path": str(kwargs["run_dir"] / "grok-search-raw.json"),
            "evidence_path": str(kwargs["run_dir"] / "grok-search-evidence.json"),
            "diagnostics": {
                "schema_version": "paper-source-grok-search-diagnostics-v1",
                "returned_count": 1,
                "usable_count": 1,
                "evidence_only_count": 0,
                "quarantined_count": 0,
                "retry_attempts": [],
                "retryable": False,
                "retry_outcome": "not_needed",
            },
        }

    monkeypatch.setattr("paper_source.orchestrator._run_grok_queries", fake_grok)

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=None,
        sources=["semantic"],
        use_query_plan=False,
        resume=False,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    grok = search_record["provider_records"]["grok_search"]
    assert grok["contribution"]["merged_count"] == 1
    assert grok["contribution"]["filtered_rejected_count"] == 1
    assert grok["contribution"]["accepted_count"] == 0
    assert grok["failure_stage"] == "merged_but_filtered_or_rank_rejected"

    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "failure_stage: merged_but_filtered_or_rank_rejected" in report
    assert "filtered_rejected_count: 1" in report
