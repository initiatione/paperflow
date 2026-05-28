import json
from datetime import datetime, timezone

from epi import orchestrator as orchestrator_module
from epi.artifacts import file_sha256
from epi.orchestrator import run_dry_run


def _write_minimal_plugin_template(plugin_root):
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "  - control\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )


def _write_fake_paper_search(tmp_path, payload: dict) -> str:
    script = tmp_path / "paper-search.ps1"
    script.write_text(
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        f"$payload = @'\n{json.dumps(payload)}\n'@\n"
        "$payload | Write-Output\n"
        "exit 0\n",
        encoding="utf-8",
    )
    return str(script)


def test_write_json_uses_atomic_writer(tmp_path, monkeypatch):
    captured = {}

    def _fake_write_json_atomic(path, payload):
        captured["path"] = path
        captured["payload"] = payload

    monkeypatch.setattr(orchestrator_module, "write_json_atomic", _fake_write_json_atomic, raising=False)
    target = tmp_path / "state.json"
    payload = {"state": "ok"}

    orchestrator_module._write_json(target, payload)

    assert captured == {"path": target, "payload": payload}


def test_dry_run_writes_phase_1_artifacts(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Embodied Navigation Control for Mobile Robots",
                    "authors": ["B. Engineer"],
                    "year": 2024,
                    "venue": "IROS",
                    "abstract": "Robotics navigation and control with code.",
                    "pdf_url": "https://example.org/nav.pdf",
                    "citation_count": 9,
                    "code_url": "https://github.com/example/nav",
                },
                {
                    "source": "fixture",
                    "title": "Graph Theory Notes",
                    "authors": ["C. Mathematician"],
                    "year": 2023,
                    "venue": "Discrete Math",
                    "abstract": "Pure graph theory and combinatorics notes.",
                    "pdf_url": "",
                    "citation_count": 2,
                },
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
    )

    assert (run_dir / "run-state.json").is_file()
    assert (run_dir / "search-record.json").is_file()
    assert (run_dir / "normalized.json").is_file()
    assert (run_dir / "filter-report.json").is_file()
    assert (run_dir / "rank.json").is_file()
    assert (run_dir / "report.md").is_file()
    state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((run_dir.parent / "index.json").read_text(encoding="utf-8"))
    dashboard_text = (run_dir.parent / "dashboard.md").read_text(encoding="utf-8")
    assert state["run_id"] == run_dir.name
    assert state["workflow_type"] == "paper-discovery-dry-run"
    assert state["state"] == "reported"
    assert state["status"] == "success"
    assert state["dry_run"] is True
    assert state["started_at"]
    assert state["finished_at"]
    assert state["exit_status"] == 0
    assert state["tool_versions"]["orchestrator"] == "epi-local"
    assert state["tool_versions"]["paper_search_adapter"] == "epi-local"
    assert len(state["input_artifact_hashes"]["request"]) == 64
    assert state["input_artifact_hashes"]["fixture.json"] == file_sha256(fixture)
    assert state["output_artifact_hashes"]["search-record.json"] == file_sha256(run_dir / "search-record.json")
    assert state["output_artifact_hashes"]["normalized.json"] == file_sha256(run_dir / "normalized.json")
    assert state["output_artifact_hashes"]["filter-report.json"] == file_sha256(run_dir / "filter-report.json")
    assert state["output_artifact_hashes"]["rank.json"] == file_sha256(run_dir / "rank.json")
    assert state["output_artifact_hashes"]["report.md"] == file_sha256(run_dir / "report.md")
    assert report["accepted"][0]["title"] == "Embodied Navigation Control for Mobile Robots"
    assert report["rejected"][0]["title"] == "Graph Theory Notes"
    assert sorted(report["rejected"][0]["filter_reasons"]) == ["missing_pdf", "outside_domain"]
    assert report["quarantined"] == []
    assert report["critic_failures"] == []
    assert report["budget_usage"]["max_results"] == 5
    assert report["budget_usage"]["discovered_count"] == 2
    assert report["wiki_pages_written"] == []
    assert report["zotero_results"]["status"] == "not_run"
    assert report["next_actions"] == [
        "Review accepted dry-run candidates before advancing ranked papers.",
        "Refine the query or domain profile if too many candidates were rejected.",
    ]
    assert "## Budget Usage" in report_md
    assert "## Next Actions" in report_md
    assert index_payload["runs"][0]["run_id"] == run_dir.name
    assert index_payload["runs"][0]["workflow_type"] == "paper-discovery-dry-run"
    assert run_dir.name in dashboard_text


def test_dry_run_live_search_preserves_raw_upstream_response(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fake_command = _write_fake_paper_search(
        tmp_path,
        {
            "query": "robotics control",
            "sources_used": ["arxiv"],
            "source_results": {"arxiv": 1},
            "errors": {},
            "total": 1,
            "papers": [
                {
                    "paper_id": "2401.12345",
                    "title": "Embodied Control for Robots",
                    "authors": "A. Researcher",
                    "abstract": "Robotics control.",
                    "doi": "",
                    "published_date": "2025-01-02T00:00:00",
                    "pdf_url": "https://arxiv.org/pdf/2401.12345",
                    "url": "https://arxiv.org/abs/2401.12345",
                    "source": "arxiv",
                    "citations": 3,
                    "extra": {},
                }
            ],
        },
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=2,
        paper_search_command=fake_command,
        sources=["arxiv"],
    )

    raw_response = run_dir / "paper-search-raw.json"
    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))

    assert raw_response.is_file()
    assert search_record["source_mode"] == "paper_search_cli"
    assert search_record["raw_response_path"] == str(raw_response)
    assert json.loads(raw_response.read_text(encoding="utf-8"))["papers"][0]["paper_id"] == "2401.12345"


def test_dry_run_uses_unique_run_ids_within_same_second(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text("[]", encoding="utf-8")
    timestamps = iter(
        [
            datetime(2026, 5, 27, 12, 0, 0, 123456, tzinfo=timezone.utc),
            datetime(2026, 5, 27, 12, 0, 0, 654321, tzinfo=timezone.utc),
        ]
    )

    class _FakeDateTime:
        @classmethod
        def now(cls, tz=None):
            return next(timestamps)

    monkeypatch.setattr(orchestrator_module, "datetime", _FakeDateTime)

    first_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=2,
        fixture_path=fixture,
    )
    second_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics control",
        max_results=2,
        fixture_path=fixture,
    )

    assert first_run.name != second_run.name
