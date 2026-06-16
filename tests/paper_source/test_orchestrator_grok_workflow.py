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
