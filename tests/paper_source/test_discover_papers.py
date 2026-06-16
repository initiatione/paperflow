import json

from paper_source import discover_papers as discover_papers_module
from paper_source.discover_papers import discover_papers


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


def test_discover_papers_composes_dry_run_and_auto_staging_without_default_recency(tmp_path, monkeypatch):
    captured = {}
    vault = tmp_path / "vault"
    discovery_run_dir = vault / "_paper_source" / "runs" / "dry-run-001"
    discovery_run_dir.mkdir(parents=True)
    (discovery_run_dir / "run-state.json").write_text("{}", encoding="utf-8")
    (discovery_run_dir / "report.json").write_text(
        json.dumps(
            {
                "session_recommendations": {
                    "schema_version": "paper-source-session-recommendations-v1",
                    "primary_recommendations": [{"slug": "fixture-paper"}],
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run_dry_run(**kwargs):
        captured["dry_run"] = kwargs
        return discovery_run_dir

    def fake_auto_stage(vault_path, run_id, **kwargs):
        captured["auto_stage"] = {"vault_path": vault_path, "run_id": run_id, **kwargs}
        auto_run_dir = vault / "_paper_source" / "runs" / "auto-staging-001"
        auto_run_dir.mkdir(parents=True)
        (auto_run_dir / "run-state.json").write_text("{}", encoding="utf-8")
        (auto_run_dir / "report.json").write_text(
            json.dumps(
                {
                    "auto_staging_plan": {"selected": [{"slug": "fixture-paper"}], "skipped": []},
                    "session_recommendations": {
                        "primary_recommendations": [
                            {"slug": "fixture-paper", "auto_staging_status": "staged"}
                        ]
                    },
                    "manual_downloads": [],
                }
            ),
            encoding="utf-8",
        )
        return {
            "run_id": "auto-staging-001",
            "state": "prepared",
            "status": "waiting_for_human_gate",
            "processed_count": 1,
            "skipped_count": 0,
            "auto_staging_plan": {"selected": [{"slug": "fixture-paper"}], "skipped": []},
            "session_recommendations": {
                "primary_recommendations": [{"slug": "fixture-paper", "auto_staging_status": "staged"}]
            },
        }

    monkeypatch.setattr(discover_papers_module, "run_dry_run", fake_run_dry_run)
    monkeypatch.setattr(discover_papers_module, "auto_stage_recommendations_from_run", fake_auto_stage)

    record = discover_papers(
        plugin_root=tmp_path / "plugin",
        vault_path=vault,
        query="robotics control",
        max_results=None,
        selection_policy="code_preferred",
        max_auto_stage=2,
        review_survey_requested=True,
        skip_existing=False,
    )

    assert captured["dry_run"]["year_min"] is None
    assert captured["dry_run"]["review_survey_policy"] == "include_by_default"
    assert captured["dry_run"]["selection_policy"] == "code_preferred"
    assert captured["auto_stage"]["run_id"] == "dry-run-001"
    assert captured["auto_stage"]["auto_limit"] == 2
    assert captured["auto_stage"]["review_survey_requested"] is True
    assert captured["auto_stage"]["skip_existing"] is False
    assert record["workflow_type"] == "discover-papers"
    assert record["discovery_run_id"] == "dry-run-001"
    assert record["auto_staging_run_id"] == "auto-staging-001"
    assert record["compiled_wiki_write"] is False
    assert record["human_approval_written"] is False
    assert record["paper_wiki_invoked"] is False
    run_dir = vault / "_paper_source" / "runs" / record["run_id"]
    assert (run_dir / "discover-papers-record.json").is_file()
    assert (run_dir / "report.json").is_file()


def test_discover_papers_no_auto_stage_writes_high_level_record(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    discovery_run_dir = vault / "_paper_source" / "runs" / "dry-run-001"
    discovery_run_dir.mkdir(parents=True)
    (discovery_run_dir / "run-state.json").write_text("{}", encoding="utf-8")
    (discovery_run_dir / "report.json").write_text(
        json.dumps(
            {
                "session_recommendations": {
                    "schema_version": "paper-source-session-recommendations-v1",
                    "primary_recommendations": [{"slug": "needs-review"}],
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(discover_papers_module, "run_dry_run", lambda **kwargs: discovery_run_dir)

    record = discover_papers(
        plugin_root=tmp_path / "plugin",
        vault_path=vault,
        query="robotics survey papers",
        max_results=5,
        auto_stage=False,
    )

    assert record["auto_stage"] is False
    assert record["auto_staging_run_id"] is None
    assert record["stops_after"] == "recommendation-output"
    assert record["processed_count"] == 0
    assert record["session_recommendations"]["primary_recommendations"][0]["slug"] == "needs-review"
    run_dir = vault / "_paper_source" / "runs" / record["run_id"]
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["auto_stage"] is False
    assert report["compiled_wiki_write"] is False
    assert not list(vault.rglob("human-approval.json"))
    assert not list(vault.rglob("wiki-ingest-record.json"))


def test_discover_papers_keeps_review_survey_by_default_and_excludes_only_on_explicit_intent(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(tmp_path / "missing-runtime.json"))
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Robot Control Survey with Benchmarks",
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "venue": "Annual Reviews in Control",
                    "abstract": "A survey paper about robotics control benchmarks and methods.",
                    "pdf_url": "https://example.org/survey.pdf",
                    "citation_count": 12,
                }
            ]
        ),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"

    kept_record = discover_papers(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics control papers",
        max_results=None,
        fixture_path=fixture,
        auto_stage=False,
        enable_easyscholar=False,
    )
    kept_discovery = vault / "_paper_source" / "runs" / kept_record["discovery_run_id"]
    kept_filter = json.loads((kept_discovery / "filter-report.json").read_text(encoding="utf-8"))
    kept_query_plan = json.loads((kept_discovery / "query-plan.json").read_text(encoding="utf-8"))

    assert [item["title"] for item in kept_filter["kept"]] == ["Robot Control Survey with Benchmarks"]
    assert all("-review -survey" not in query for query in kept_query_plan["query_variants"])

    excluded_record = discover_papers(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics control non-review papers",
        max_results=None,
        fixture_path=fixture,
        auto_stage=False,
        enable_easyscholar=False,
        refresh=True,
    )
    excluded_discovery = vault / "_paper_source" / "runs" / excluded_record["discovery_run_id"]
    excluded_filter = json.loads((excluded_discovery / "filter-report.json").read_text(encoding="utf-8"))
    excluded_query_plan = json.loads((excluded_discovery / "query-plan.json").read_text(encoding="utf-8"))

    assert excluded_filter["kept"] == []
    assert excluded_filter["rejected"][0]["title"] == "Robot Control Survey with Benchmarks"
    assert "excluded_terms:survey" in excluded_filter["rejected"][0]["filter_reasons"]
    assert any("-review -survey" in query for query in excluded_query_plan["query_variants"])
