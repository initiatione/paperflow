import json
from datetime import datetime, timezone

import pytest

from paper_source import orchestrator as orchestrator_module
from paper_source.artifacts import file_sha256
from paper_source.orchestrator import run_dry_run


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


@pytest.fixture(autouse=True)
def _isolate_runtime_and_easyscholar_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(tmp_path / "missing-runtime.json"))
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)
    monkeypatch.setenv("PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED", "1")


def test_ensure_candidate_metadata_uses_atomic_writer(tmp_path, monkeypatch):
    captured = {}

    def _fake_write_json_atomic(path, payload):
        captured["path"] = path
        captured["payload"] = payload

    monkeypatch.setattr(orchestrator_module, "write_json_atomic", _fake_write_json_atomic, raising=False)
    monkeypatch.setattr(
        orchestrator_module,
        "_metadata_from_candidate",
        lambda candidate: {"title": candidate["title"]},
        raising=False,
    )
    payload = {"title": "Fixture Paper"}

    orchestrator_module._ensure_candidate_metadata(tmp_path, payload)

    assert captured == {"path": tmp_path / "metadata.json", "payload": {"title": "Fixture Paper"}}


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
    assert (run_dir / "query-plan.json").is_file()
    assert (run_dir / "search-record.json").is_file()
    assert (run_dir / "normalized.json").is_file()
    assert (run_dir / "filter-report.json").is_file()
    assert (run_dir / "easyscholar-record.json").is_file()
    assert (run_dir / "rank.json").is_file()
    assert (run_dir / "report.md").is_file()
    state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    easyscholar_record = json.loads((run_dir / "easyscholar-record.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((run_dir.parent / "index.json").read_text(encoding="utf-8"))
    dashboard_text = (run_dir.parent / "dashboard.md").read_text(encoding="utf-8")
    assert state["run_id"] == run_dir.name
    assert state["workflow_type"] == "paper-discovery-dry-run"
    assert state["state"] == "reported"
    assert state["status"] == "success"
    assert state["dry_run"] is True
    assert state["query_strategy"] == "single_query"
    assert state["research_mode"]["mode"] == "targeted-discovery"
    assert state["query_plan"]["domain"] == "profile-derived"
    assert query_plan["workflow"] == "paper-source-query-plan"
    assert query_plan["research_mode"]["mode"] == "targeted-discovery"
    assert query_plan["domain"] == "profile-derived"
    assert query_plan["profile"]["domains"] == ["robotics", "control"]
    assert "robotics" in query_plan["concept_blocks"]["domain_terms"]
    assert all("-review -survey" in query for query in query_plan["query_variants"])
    assert report["discovery_context"]["query_plan"]["domain"] == "profile-derived"
    assert report["discovery_context"]["research_mode"]["mode"] == "targeted-discovery"
    assert report["discovery_context"]["candidate_pool"]["raw"] == 2
    assert report["discovery_context"]["easyscholar"]["summary"]["missing_key"] == 1
    assert report["easyscholar"]["record_path"] == str(run_dir / "easyscholar-record.json")
    assert easyscholar_record["schema_version"] == "paper-source-easyscholar-record-v1"
    assert easyscholar_record["summary"]["missing_key"] == 1
    assert state["started_at"]
    assert state["finished_at"]
    assert state["exit_status"] == 0
    assert state["tool_versions"]["orchestrator"] == "paper-source-local"
    assert state["tool_versions"]["paper_search_adapter"] == "paper-source-local"
    assert state["tool_versions"]["easyscholar"] == "paper-source-local"
    assert len(state["input_artifact_hashes"]["request"]) == 64
    assert state["input_artifact_hashes"]["fixture.json"] == file_sha256(fixture)
    assert state["output_artifact_hashes"]["search-record.json"] == file_sha256(run_dir / "search-record.json")
    assert state["output_artifact_hashes"]["normalized.json"] == file_sha256(run_dir / "normalized.json")
    assert state["output_artifact_hashes"]["filter-report.json"] == file_sha256(run_dir / "filter-report.json")
    assert state["output_artifact_hashes"]["easyscholar-record.json"] == file_sha256(
        run_dir / "easyscholar-record.json"
    )
    assert state["output_artifact_hashes"]["rank.json"] == file_sha256(run_dir / "rank.json")
    assert state["output_artifact_hashes"]["report.md"] == file_sha256(run_dir / "report.md")
    assert report["workflow_type"] == "paper-discovery-dry-run"
    assert report["run_id"] == run_dir.name
    assert report["accepted"][0]["title"] == "Embodied Navigation Control for Mobile Robots"
    assert report["accepted"][0]["easyscholar_status"] == "missing_key"
    assert report["accepted"][0]["ranking_signals"]["easyscholar_score"] == 0.0
    assert ranked[0]["ranking_protocol"]["schema_version"] == "paper-source-ranking-protocol-v1"
    assert ranked[0]["paper_classification"]["schema_version"] == "paper-source-paper-classification-v1"
    assert ranked[0]["ranking_rubric"]["schema_version"] == "paper-source-ranking-rubric-v1"
    assert ranked[0]["quality_gate"]["schema_version"] == "paper-source-quality-gate-v1"
    assert ranked[0]["ranking_protocol"]["quality_tier"] == ranked[0]["quality_tier"]
    assert ranked[0]["ranking_protocol"]["quality_gate"] == ranked[0]["quality_gate"]
    assert ranked[0]["ranking_protocol"]["paper_type"] == ranked[0]["paper_type"]
    assert ranked[0]["ranking_protocol"]["ranking_confidence"] == ranked[0]["ranking_confidence"]
    assert ranked[0]["ranking_protocol"]["lenses"]["editorial"]["signals"] == [
        "venue_tier",
        "freshness",
        "topic_relevance",
    ]
    assert ranked[0]["ranking_protocol"]["decision"] in {"advance-candidate", "review-candidate"}
    assert report["accepted"][0]["ranking_protocol"] == ranked[0]["ranking_protocol"]
    assert report["accepted"][0]["quality_tier"] == ranked[0]["quality_tier"]
    assert report["research_queue"]["advance_candidates"] or report["research_queue"]["review_candidates"]
    queued_titles = [
        paper["title"]
        for group in report["research_queue"].values()
        for paper in group
    ]
    assert "Embodied Navigation Control for Mobile Robots" in queued_titles
    assert report["rejected"][0]["title"] == "Graph Theory Notes"
    assert sorted(report["rejected"][0]["filter_reasons"]) == ["missing_pdf", "outside_domain"]
    assert report["quarantined"] == []
    assert report["critic_failures"] == []
    assert report["budget_usage"]["max_results"] == 5
    assert report["budget_usage"]["raw_candidate_pool_count"] == 2
    assert report["budget_usage"]["discovered_count"] == 2
    assert report["budget_usage"]["query_variant_count"] == len(query_plan["query_variants"])
    assert report["wiki_pages_written"] == []
    assert report["zotero_results"]["status"] == "not_run"
    assert report["next_actions"] == [
        "Review accepted dry-run candidates before advancing ranked papers.",
        "Refine the query or domain profile if too many candidates were rejected.",
    ]
    assert f"Run ID: {run_dir.name}" in report_md
    assert report_md.startswith("# Paper Source Dry Run")
    assert "## Budget Usage" in report_md
    assert "## EasyScholar Enrichment" in report_md
    assert "missing_key: 1" in report_md
    assert "quality_tier:" in report_md
    assert "## Next Actions" in report_md
    assert index_payload["runs"][0]["run_id"] == run_dir.name
    assert index_payload["runs"][0]["workflow_type"] == "paper-discovery-dry-run"
    assert run_dir.name in dashboard_text
    assert sorted(path.name for path in (tmp_path / "vault").iterdir()) == ["_paper_source"]


def test_dry_run_can_disable_easyscholar_for_single_run(tmp_path):
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
                }
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
        enable_easyscholar=False,
    )

    record = json.loads((run_dir / "easyscholar-record.json").read_text(encoding="utf-8"))
    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))

    assert record["enabled"] is False
    assert record["summary"]["disabled"] == 1
    assert ranked[0]["easyscholar_status"] == "disabled"


def test_dry_run_resumes_matching_review_session_by_default_without_provider_call(tmp_path):
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
                }
            ]
        ),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    first_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
    )
    fixture.write_text("[]", encoding="utf-8")

    second_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
    )

    assert first_run != second_run
    second_state = json.loads((second_run / "run-state.json").read_text(encoding="utf-8"))
    second_search = json.loads((second_run / "search-record.json").read_text(encoding="utf-8"))
    second_report = json.loads((second_run / "report.json").read_text(encoding="utf-8"))
    second_ranked = json.loads((second_run / "rank.json").read_text(encoding="utf-8"))
    assert second_state["review_session"]["resumed"] is True
    assert second_state["review_session"]["provider_call_skipped"] is True
    assert second_search["provider_call_skipped"] is True
    assert second_ranked[0]["title"] == "Embodied Navigation Control for Mobile Robots"
    assert second_report["discovery_context"]["review_session"]["provider_call_skipped"] is True
    assert "## Review Session" in (second_run / "report.md").read_text(encoding="utf-8")


def test_dry_run_refresh_bypasses_review_cache(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Old Robot Navigation Control",
                    "authors": ["B. Engineer"],
                    "year": 2024,
                    "venue": "IROS",
                    "abstract": "robotics navigation control",
                    "pdf_url": "https://example.org/old.pdf",
                    "citation_count": 9,
                }
            ]
        ),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
    )
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Fresh Robot Navigation Control",
                    "authors": ["B. Engineer"],
                    "year": 2026,
                    "venue": "IROS",
                    "abstract": "robotics navigation control",
                    "pdf_url": "https://example.org/fresh.pdf",
                    "citation_count": 11,
                }
            ]
        ),
        encoding="utf-8",
    )

    refreshed_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
        refresh=True,
    )

    state = json.loads((refreshed_run / "run-state.json").read_text(encoding="utf-8"))
    ranked = json.loads((refreshed_run / "rank.json").read_text(encoding="utf-8"))
    assert state["review_session"]["resumed"] is False
    assert state["review_session"]["refreshed"] is True
    assert state["review_session"]["provider_call_skipped"] is False
    assert ranked[0]["title"] == "Fresh Robot Navigation Control"


def test_dry_run_query_plan_searches_variants_and_merges_candidate_pool(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fake_command = tmp_path / "planned-paper-search.ps1"
    args_path = tmp_path / "planned-args.jsonl"
    fake_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "Add-Content -Encoding UTF8 -LiteralPath "
        f"{json.dumps(str(args_path))} "
        "-Value $args_json\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        "$query = $args[1]\n"
        "$safe = ($query -replace '\"','')\n"
        "$payload = [ordered]@{\n"
        "  query = $query\n"
        "  sources_used = @('arxiv')\n"
        "  source_results = @{ arxiv = 1 }\n"
        "  errors = @{}\n"
        "  total = 1\n"
        "  papers = @(@{\n"
        "    paper_id = [Math]::Abs($safe.GetHashCode()).ToString()\n"
        "    title = \"AUV RL Control $([Math]::Abs($safe.GetHashCode()).ToString())\"\n"
        "    authors = 'A. Researcher'\n"
        "    abstract = 'AUV reinforcement learning control with ocean current and real AUV evidence.'\n"
        "    doi = ''\n"
        "    published_date = '2025-01-02T00:00:00'\n"
        "    pdf_url = 'https://example.org/paper.pdf'\n"
        "    url = 'https://example.org/paper'\n"
        "    source = 'arxiv'\n"
        "    citations = 3\n"
        "    extra = @{}\n"
        "  })\n"
        "}\n"
        "$payload | ConvertTo-Json -Depth 8 | Write-Output\n"
        "exit 0\n",
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="latest high quality AUV reinforcement learning control papers not review",
        max_results=3,
        paper_search_command=str(fake_command),
        sources=["arxiv"],
        query_plan_domain="profile",
        query_plan_max_queries=4,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    normalized = json.loads((run_dir / "normalized.json").read_text(encoding="utf-8"))
    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    invoked = [
        json.loads(line)
        for line in args_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]

    search_invocations = [args for args in invoked if args and args[0] == "search"]
    assert search_record["query_strategy"] == "query_plan_multi_query"
    assert search_record["query_plan"]["domain"] == "profile-derived"
    assert len(search_record["query_records"]) == 4
    assert len(search_invocations) == 4
    assert all("-review -survey" in args[1] for args in search_invocations)
    assert query_plan["query_variants"][0] == search_invocations[0][1]
    assert len(search_record["records"]) == 4
    assert all("query_variant" in record for record in search_record["records"])
    assert len(normalized) == 4
    assert len(ranked) == 3
    assert report["budget_usage"]["raw_candidate_pool_count"] == 4
    assert report["budget_usage"]["ranked_candidate_pool_count"] == 4
    assert report["budget_usage"]["accepted_count"] == 3
    assert report["discovery_context"]["query_strategy"] == "query_plan_multi_query"
    assert report["discovery_context"]["candidate_pool"]["accepted"] == 3
    assert report["discovery_context"]["source_coverage"]["source_results"] == {"arxiv": 4}
    assert report["discovery_context"]["source_coverage"]["raw_total"] == 4
    assert report["discovery_context"]["source_coverage"]["deduped_total"] == 4
    assert report["discovery_context"]["source_coverage"]["query_count"] == 4
    assert (run_dir / "paper-search-raw-01.json").is_file()
    assert (run_dir / "paper-search-raw.json").is_file()


def test_dry_run_uses_agent_supplied_query_variants_instead_of_raw_topic(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fake_command = tmp_path / "agent-planned-paper-search.ps1"
    args_path = tmp_path / "agent-planned-args.jsonl"
    fake_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "Add-Content -Encoding UTF8 -LiteralPath "
        f"{json.dumps(str(args_path))} "
        "-Value $args_json\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        "$query = $args[1]\n"
        "$safe = ($query -replace '\"','')\n"
        "$payload = [ordered]@{\n"
        "  query = $query\n"
        "  sources_used = @('arxiv')\n"
        "  source_results = @{ arxiv = 1 }\n"
        "  errors = @{}\n"
        "  total = 1\n"
        "  papers = @(@{\n"
        "    paper_id = [Math]::Abs($safe.GetHashCode()).ToString()\n"
        "    title = \"AUV Attitude Control $([Math]::Abs($safe.GetHashCode()).ToString())\"\n"
        "    authors = 'A. Researcher'\n"
        "    abstract = 'Autonomous underwater vehicle attitude control with experiment and code evidence.'\n"
        "    doi = ''\n"
        "    published_date = '2025-01-02T00:00:00'\n"
        "    pdf_url = 'https://example.org/auv.pdf'\n"
        "    url = 'https://example.org/auv'\n"
        "    source = 'arxiv'\n"
        "    citations = 3\n"
        "    extra = @{}\n"
        "  })\n"
        "}\n"
        "$payload | ConvertTo-Json -Depth 8 | Write-Output\n"
        "exit 0\n",
        encoding="utf-8",
    )
    raw_topic = "水下机器人 AUV 姿态控制 的 现代控制方向 或是 结合RL做的尽可能有公开代码的论文，近5年"
    variants = [
        '"autonomous underwater vehicle" "attitude control" "model predictive control" -review -survey',
        'AUV "attitude control" "reinforcement learning" code -review -survey',
        '"underwater robot" "orientation control" "sliding mode control" -review -survey',
    ]

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query=raw_topic,
        max_results=5,
        paper_search_command=str(fake_command),
        sources=["arxiv"],
        query_variants=variants,
        domain_focus_terms=["AUV", "autonomous underwater vehicle", "underwater robot"],
        query_plan_domain="profile",
    )

    invoked = [
        json.loads(line)
        for line in args_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    search_queries = [args[1] for args in invoked if args and args[0] == "search"]
    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))

    assert search_queries == variants
    assert raw_topic not in search_queries
    assert query_plan["query_variants"] == variants
    assert query_plan["query_variants_source"] == "agent_supplied"
    assert query_plan["agent_supplied"]["contract"] == "agent_compiles_natural_language; script_records_and_executes"
    assert query_plan["concept_blocks"]["domain_focus_terms"][:3] == [
        "AUV",
        "autonomous underwater vehicle",
        "underwater robot",
    ]
    assert search_record["query_strategy"] == "query_plan_multi_query"
    assert len(search_record["query_records"]) == len(variants)
    assert len(search_record["records"]) == len(variants)
    assert len(ranked) == len(variants)


def test_dry_run_records_structured_agent_query_plan_and_request_constraints(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    agent_plan = tmp_path / "agent-query-plan.json"
    agent_plan.write_text(
        json.dumps(
            {
                "schema_version": "paper-source-agent-query-plan-v1",
                "query_variants": [
                    '"autonomous underwater vehicle" "attitude control" "model predictive control" -review -survey',
                    '"AUV" "attitude control" "reinforcement learning" code -review -survey',
                ],
                "domain_focus_terms": ["AUV", "autonomous underwater vehicle"],
                "concept_blocks": {
                    "task_terms": ["attitude control"],
                    "method_branches": ["model predictive control", "reinforcement learning"],
                    "quality_signals": ["code", "experiment"],
                },
                "year_min": 2021,
                "code_policy": "prefer",
            }
        ),
        encoding="utf-8",
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "semantic",
                    "title": "Recent AUV Attitude Control with Public Code",
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "venue": "Ocean Engineering",
                    "abstract": "Autonomous underwater vehicle attitude control with experiments and code.",
                    "doi": "10.1000/recent-code",
                    "pdf_url": "https://example.org/recent-code.pdf",
                    "code_url": "https://github.com/example/recent-auv-control",
                    "citation_count": 8,
                },
                {
                    "source": "semantic",
                    "title": "Recent AUV Attitude Control without Public Code",
                    "authors": ["B. Researcher"],
                    "year": 2024,
                    "venue": "Ocean Engineering",
                    "abstract": "Autonomous underwater vehicle attitude control with experiments.",
                    "doi": "10.1000/recent-no-code",
                    "pdf_url": "https://example.org/recent-no-code.pdf",
                    "citation_count": 7,
                },
                {
                    "source": "semantic",
                    "title": "Old AUV Attitude Control with Public Code",
                    "authors": ["C. Researcher"],
                    "year": 2019,
                    "venue": "Ocean Engineering",
                    "abstract": "Autonomous underwater vehicle attitude control with experiments and code.",
                    "doi": "10.1000/old-code",
                    "pdf_url": "https://example.org/old-code.pdf",
                    "code_url": "https://github.com/example/old-auv-control",
                    "citation_count": 10,
                },
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="AUV 现代控制或RL智能控制 姿态控制 有公开代码 近期论文",
        max_results=5,
        fixture_path=fixture,
        agent_query_plan_json=agent_plan,
        sources=["semantic"],
    )

    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    filter_report = json.loads((run_dir / "filter-report.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))
    state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert query_plan["query_variants_source"] == "agent_supplied"
    assert query_plan["query_variants"] == [
        '"autonomous underwater vehicle" "attitude control" "model predictive control" -review -survey',
        '"AUV" "attitude control" "reinforcement learning" code -review -survey',
    ]
    assert query_plan["concept_blocks"]["domain_focus_terms"] == ["AUV", "autonomous underwater vehicle"]
    assert query_plan["request_constraints"] == {
        "year_min": 2021,
        "code_policy": "prefer",
        "source": "agent_supplied",
    }
    assert filter_report["request_constraints"] == {"year_min": 2021, "code_policy": "prefer"}
    assert [candidate["title"] for candidate in ranked] == [
        "Recent AUV Attitude Control with Public Code",
        "Recent AUV Attitude Control without Public Code",
    ]
    rejected = {candidate["title"]: candidate["filter_reasons"] for candidate in report["rejected"]}
    assert rejected["Old AUV Attitude Control with Public Code"] == ["year_before:2021"]
    assert report["budget_usage"]["year_min"] == 2021
    assert report["budget_usage"]["code_policy"] == "prefer"
    assert report["discovery_context"]["request_constraints"] == {"year_min": 2021, "code_policy": "prefer"}
    assert ranked[0]["ranking_signals"]["code_policy"] == "prefer"
    assert "request_constraints: year_min=2021, code_policy=prefer" in report_md
    assert state["input_artifact_hashes"]["agent-query-plan.json"] == file_sha256(agent_plan)


def test_dry_run_source_coverage_reports_normalized_dedupe_total_for_query_plan(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fake_command = tmp_path / "planned-duplicate-paper-search.ps1"
    fake_command.write_text(
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        "$payload = [ordered]@{\n"
        "  query = $args[1]\n"
        "  sources_used = @('arxiv','semantic')\n"
        "  source_results = @{ arxiv = 1; semantic = 1 }\n"
        "  errors = @{}\n"
        "  raw_total = 2\n"
        "  total = 1\n"
        "  papers = @(@{\n"
        "    paper_id = '2401.12345'\n"
        "    title = 'Shared AUV Reinforcement Learning Control Paper'\n"
        "    authors = 'A. Researcher'\n"
        "    abstract = 'AUV reinforcement learning control with ocean current and real AUV evidence.'\n"
        "    doi = '10.1234/shared-auv'\n"
        "    published_date = '2025-01-02T00:00:00'\n"
        "    pdf_url = 'https://example.org/shared.pdf'\n"
        "    url = 'https://example.org/shared'\n"
        "    source = 'arxiv'\n"
        "    citations = 3\n"
        "    extra = @{}\n"
        "  })\n"
        "}\n"
        "$payload | ConvertTo-Json -Depth 8 | Write-Output\n"
        "exit 0\n",
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="latest high quality AUV reinforcement learning control papers not review",
        max_results=3,
        paper_search_command=str(fake_command),
        sources=["arxiv", "semantic"],
        query_plan_domain="profile",
        query_plan_max_queries=4,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    normalized = json.loads((run_dir / "normalized.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert len(search_record["records"]) == 4
    assert len(normalized) == 1
    assert report["discovery_context"]["source_coverage"]["raw_total"] == 8
    assert report["discovery_context"]["source_coverage"]["deduped_total"] == 1
    assert report["discovery_context"]["source_coverage"]["source_results"] == {"arxiv": 4, "semantic": 4}


def test_dry_run_with_generic_config_derives_filter_terms_from_query_plan(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: general_academic_research\n"
        "domains: []\n"
        "positive_keywords: []\n"
        "negative_keywords: []\n"
        "venue_prior: []\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Graph Neural Networks for Molecular Property Prediction",
                    "authors": ["C. Chemist"],
                    "year": 2025,
                    "venue": "JCIM",
                    "abstract": "Molecular property prediction with graph neural network benchmarks.",
                    "pdf_url": "https://example.org/molecule.pdf",
                    "citation_count": 12,
                },
                {
                    "source": "fixture",
                    "title": "Warehouse Robot Navigation",
                    "authors": ["R. Engineer"],
                    "year": 2025,
                    "venue": "ICRA",
                    "abstract": "Mobile robot navigation and control benchmark.",
                    "pdf_url": "https://example.org/robot.pdf",
                    "citation_count": 8,
                },
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="molecular property prediction graph neural network",
        max_results=5,
        fixture_path=fixture,
    )

    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert query_plan["domain"] == "topic-derived"
    assert "molecular property prediction" in query_plan["concept_blocks"]["domain_terms"]
    assert [candidate["title"] for candidate in report["accepted"]] == [
        "Graph Neural Networks for Molecular Property Prediction"
    ]
    assert report["rejected"][0]["title"] == "Warehouse Robot Navigation"
    assert "outside_domain" in report["rejected"][0]["filter_reasons"]


def test_dry_run_filters_method_only_results_with_generic_topic_anchors(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: machine_learning_research\n"
        "domains:\n"
        "  - machine learning\n"
        "  - artificial intelligence\n"
        "positive_keywords:\n"
        "  - graph neural network\n"
        "  - deep learning\n"
        "negative_keywords:\n"
        "  - review\n"
        "venue_prior: []\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Graph Neural Networks for Molecular Property Prediction",
                    "authors": ["C. Chemist"],
                    "year": 2025,
                    "venue": "Journal of Chemical Information and Modeling",
                    "abstract": "Molecular property prediction with graph neural network benchmarks.",
                    "pdf_url": "https://example.org/molecule.pdf",
                    "citation_count": 12,
                },
                {
                    "source": "fixture",
                    "title": "Scalable Graph Neural Network Training",
                    "authors": ["M. Researcher"],
                    "year": 2025,
                    "venue": "arXiv",
                    "abstract": "A graph neural network and deep learning benchmark for generic node classification.",
                    "pdf_url": "https://example.org/gnn.pdf",
                    "citation_count": 3,
                },
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="latest high quality graph neural network molecular property prediction papers not review",
        max_results=5,
        fixture_path=fixture,
    )

    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert "molecular property prediction" in query_plan["concept_blocks"]["domain_focus_terms"]
    assert [candidate["title"] for candidate in report["accepted"]] == [
        "Graph Neural Networks for Molecular Property Prediction"
    ]
    rejected = {candidate["title"]: candidate["filter_reasons"] for candidate in report["rejected"]}
    assert rejected["Scalable Graph Neural Network Training"] == ["outside_domain"]


def test_dry_run_ranking_does_not_dilute_topic_fit_with_recall_expansion_terms(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Embodied Navigation Control Benchmark for Mobile Robots",
                    "authors": ["E. Researcher"],
                    "year": 2026,
                    "venue": "RSS",
                    "abstract": (
                        "Robotics embodied navigation control with benchmark, baseline, "
                        "ablation, reproducible code, dataset, simulator, and implementation details."
                    ),
                    "pdf_url": "https://example.org/nav.pdf",
                    "doi": "10.1000/e2e-nav",
                    "citation_count": 50,
                    "code_url": "https://github.com/example/e2e-nav",
                }
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics embodied navigation control benchmark",
        max_results=5,
        fixture_path=fixture,
    )

    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))

    assert "world model" not in query_plan["concept_blocks"]["method_or_topic_terms"]
    assert "world model" not in ranked[0]["ranking_protocol"]["matched_positive_keywords"]
    assert ranked[0]["ranking_signals"]["topic_score"] >= 0.6
    assert ranked[0]["ranking_protocol"]["decision"] == "advance-candidate"


def test_dry_run_filters_method_only_results_when_topic_has_domain_anchors(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "  - robot control\n"
        "  - reinforcement learning\n"
        "  - AUV control\n"
        "positive_keywords:\n"
        "  - reinforcement learning\n"
        "  - AUV\n"
        "  - underwater robot\n"
        "negative_keywords:\n"
        "  - review\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Fault-tolerant AUV Trajectory Tracking Control",
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "venue": "Ocean Engineering",
                    "abstract": (
                        "Autonomous underwater vehicle control with trajectory tracking, "
                        "benchmark simulation, and current disturbance experiments."
                    ),
                    "pdf_url": "https://example.org/auv.pdf",
                    "citation_count": 4,
                },
                {
                    "source": "fixture",
                    "title": "Causal-Paced Deep Reinforcement Learning",
                    "authors": ["B. Researcher"],
                    "year": 2025,
                    "venue": "arXiv",
                    "abstract": "A curriculum reinforcement learning method for point-mass benchmark tasks.",
                    "pdf_url": "https://example.org/rl.pdf",
                    "citation_count": 0,
                },
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="latest high quality AUV reinforcement learning control papers not review",
        max_results=5,
        fixture_path=fixture,
        domain_focus_terms=["AUV", "autonomous underwater vehicle"],
    )

    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert [candidate["title"] for candidate in report["accepted"]] == [
        "Fault-tolerant AUV Trajectory Tracking Control"
    ]
    rejected = {candidate["title"]: candidate["filter_reasons"] for candidate in report["rejected"]}
    assert rejected["Causal-Paced Deep Reinforcement Learning"] == ["outside_domain"]


def test_dry_run_filters_broad_vehicle_tracking_when_underwater_anchor_is_required(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "  - robot control\n"
        "  - reinforcement learning\n"
        "  - AUV control\n"
        "positive_keywords:\n"
        "  - reinforcement learning\n"
        "  - AUV\n"
        "  - underwater robot\n"
        "negative_keywords:\n"
        "  - review\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Robust Trajectory Tracking Control for Underactuated Autonomous Underwater Vehicles",
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "venue": "Ocean Engineering",
                    "abstract": (
                        "Autonomous underwater vehicle control with trajectory tracking, "
                        "ocean current disturbance experiments, and benchmark simulation."
                    ),
                    "pdf_url": "https://example.org/auv.pdf",
                    "citation_count": 4,
                },
                {
                    "source": "fixture",
                    "title": "Gaussian-Process-based Adaptive Tracking Control for Autonomous Ground Vehicles",
                    "authors": ["B. Researcher"],
                    "year": 2025,
                    "venue": "arXiv",
                    "abstract": (
                        "Autonomous ground vehicles use trajectory tracking and adaptive control "
                        "with real experiments on an electric car."
                    ),
                    "pdf_url": "https://example.org/ground.pdf",
                    "citation_count": 2,
                },
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query=(
            "AUV autonomous underwater vehicle reinforcement learning trajectory tracking "
            "path following ocean current adaptive control safety critical control not review"
        ),
        max_results=5,
        fixture_path=fixture,
        domain_focus_terms=["AUV", "autonomous underwater vehicle"],
    )

    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert [candidate["title"] for candidate in report["accepted"]] == [
        "Robust Trajectory Tracking Control for Underactuated Autonomous Underwater Vehicles"
    ]
    rejected = {candidate["title"]: candidate["filter_reasons"] for candidate in report["rejected"]}
    assert rejected["Gaussian-Process-based Adaptive Tracking Control for Autonomous Ground Vehicles"] == [
        "outside_domain"
    ]


def test_dry_run_keeps_review_query_when_user_explicitly_requests_reviews(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "AUV Reinforcement Learning Control: A Systematic Review",
                    "authors": ["B. Engineer"],
                    "year": 2025,
                    "venue": "Ocean Engineering",
                    "abstract": "This systematic review surveys AUV reinforcement learning control.",
                    "pdf_url": "https://example.org/review.pdf",
                    "citation_count": 9,
                }
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="latest survey papers about AUV reinforcement learning control",
        max_results=5,
        fixture_path=fixture,
    )

    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    filter_report = json.loads((run_dir / "filter-report.json").read_text(encoding="utf-8"))

    assert all("-review -survey" not in query for query in query_plan["query_variants"])
    assert filter_report["kept"][0]["title"] == "AUV Reinforcement Learning Control: A Systematic Review"
    assert filter_report["rejected"] == []


def test_dry_run_can_disable_query_plan_for_single_search(tmp_path):
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
        use_query_plan=False,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert not (run_dir / "query-plan.json").exists()
    assert search_record["source_mode"] == "paper_search_cli"
    assert "query_plan" not in search_record
    assert state["query_strategy"] == "single_query"
    assert report["discovery_context"]["query_plan"] == {}


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
        use_query_plan=False,
    )

    raw_response = run_dir / "paper-search-raw.json"
    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))

    assert raw_response.is_file()
    assert search_record["source_mode"] == "paper_search_cli"
    assert search_record["raw_response_path"] == str(raw_response)
    assert json.loads(raw_response.read_text(encoding="utf-8"))["papers"][0]["paper_id"] == "2401.12345"


def test_dry_run_uses_configured_paper_search_command_and_sources(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.delenv("PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY", raising=False)
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fake_command = tmp_path / "configured-paper-search.ps1"
    args_path = tmp_path / "configured-args.json"
    fake_payload = {
        "query": "robotics survey",
        "sources_used": ["arxiv", "semantic", "openalex"],
        "source_results": {"arxiv": 1, "semantic": 0, "openalex": 0},
        "errors": {},
        "total": 1,
        "papers": [
            {
                "paper_id": "2401.12345",
                "title": "Robot Control Survey for Embodied AI",
                "authors": "A. Researcher",
                "abstract": "Robotics control survey with embodied AI benchmark coverage.",
                "doi": "",
                "published_date": "2025-01-02T00:00:00",
                "pdf_url": "https://arxiv.org/pdf/2401.12345",
                "url": "https://arxiv.org/abs/2401.12345",
                "source": "arxiv",
                "citations": 3,
                "extra": {},
            }
        ],
    }
    fake_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        f"$payload = @'\n{json.dumps(fake_payload)}\n'@\n"
        "$payload | Write-Output\n"
        f"$args_json | Set-Content -Encoding UTF8 -LiteralPath {json.dumps(str(args_path))}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    meta = vault / "_paper_source" / "meta"
    meta.mkdir(parents=True)
    (meta / "paper-source-config.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "positive_keywords:\n"
        "  - survey\n"
        "budget:\n"
        "  max_results: 10\n"
        "paper_search:\n"
        f"  command: {fake_command}\n"
        "  sources:\n"
        "    - arxiv\n"
        "    - semantic\n"
        "    - openalex\n",
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics survey",
        max_results=None,
        paper_search_command=None,
        sources=None,
        use_query_plan=False,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    invoked_args = json.loads(args_path.read_text(encoding="utf-8-sig"))

    assert search_record["upstream"]["cli_command"].endswith("configured-paper-search.ps1")
    assert search_record["upstream"]["sources_requested"] == ["arxiv", "semantic", "openalex"]
    source_coverage = report["discovery_context"]["source_coverage"]
    assert source_coverage["sources_used"] == ["arxiv", "semantic", "openalex"]
    assert source_coverage["source_results"] == {"arxiv": 1, "semantic": 0, "openalex": 0}
    assert source_coverage["errors"] == {}
    assert source_coverage["raw_total"] == 1
    assert source_coverage["deduped_total"] == 1
    assert source_coverage["query_count"] == 1
    assert source_coverage["capabilities"]["openalex"]["download"] == "unsupported"
    assert source_coverage["capabilities"]["semantic"]["read"] == "oa"
    assert source_coverage["provider_readiness"]["semantic"]["status"] == "missing_optional_env"
    assert "## Source Coverage" in report_md
    assert "- arxiv: 1" in report_md
    assert "- semantic: 0" in report_md
    assert "- openalex: 0" in report_md
    assert "openalex capability: download=unsupported" in report_md
    assert "semantic: missing_optional_env" in report_md
    assert invoked_args == ["search", "robotics survey", "-n", "10", "-s", "arxiv,semantic,openalex"]


def test_dry_run_records_provider_aware_source_routing_in_query_plan_search_and_report(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.delenv("PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL", raising=False)
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    args_path = tmp_path / "args.json"
    fake_command = tmp_path / "provider-aware-paper-search.ps1"
    fake_payload = {
        "query": "auv pinn rl control",
        "sources_used": ["semantic", "unpaywall"],
        "source_results": {"semantic": 0, "unpaywall": 0},
        "errors": {},
        "total": 0,
        "papers": [],
    }
    fake_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        f"$payload = @'\n{json.dumps(fake_payload)}\n'@\n"
        "$payload | Write-Output\n"
        f"$args_json | Set-Content -Encoding UTF8 -LiteralPath {json.dumps(str(args_path))}\n"
        "exit 0\n",
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="auv pinn rl control",
        max_results=3,
        paper_search_command=fake_command,
        sources=["google_scholar", "semantic", "unpaywall"],
        use_query_plan=True,
        query_plan_max_queries=1,
    )

    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    invoked_args = json.loads(args_path.read_text(encoding="utf-8-sig"))

    assert query_plan["source_routing"]["selected_sources"] == ["semantic", "unpaywall"]
    assert query_plan["source_routing"]["demoted_sources"] == [
        {"source": "google_scholar", "reason": "unstable_source"}
    ]
    assert query_plan["source_routing"]["provider_readiness"]["unpaywall"]["status"] == "missing_required_env"
    assert query_plan["source_routing"]["provider_gaps"][0]["provider_gap"] == "unpaywall_email_missing"
    assert search_record["source_routing"]["provider_gaps"][0]["provider_gap"] == "unpaywall_email_missing"
    source_coverage = report["discovery_context"]["source_coverage"]
    assert source_coverage["source_routing"]["selected_sources"] == ["semantic", "unpaywall"]
    assert source_coverage["source_routing"]["provider_gaps"][0]["provider_gap"] == "unpaywall_email_missing"
    assert "## Source Routing" in report_md
    assert "selected_sources: semantic, unpaywall" in report_md
    assert "demoted: google_scholar (unstable_source)" in report_md
    assert "risk: unpaywall missing_required_env (PAPER_SEARCH_MCP_UNPAYWALL_EMAIL)" in report_md
    assert invoked_args[-1] == "semantic,unpaywall"


def test_dry_run_exact_doi_uses_single_identifier_query_and_narrowed_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", "research@example.org")
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    args_path = tmp_path / "args.json"
    fake_command = tmp_path / "exact-doi-paper-search.ps1"
    fake_payload = {
        "query": "10.1016/j.oceaneng.2024.119432",
        "sources_used": ["unpaywall", "crossref"],
        "source_results": {"unpaywall": 1, "crossref": 1},
        "errors": {},
        "total": 1,
        "papers": [
            {
                "paper_id": "10.1016/j.oceaneng.2024.119432",
                "title": "Fault Tolerant Control for AUVs",
                "authors": "A. Researcher",
                "abstract": "AUV control with experiments.",
                "doi": "10.1016/j.oceaneng.2024.119432",
                "url": "https://doi.org/10.1016/j.oceaneng.2024.119432",
                "source": "crossref",
                "citations": 4,
                "extra": {"venue": "Ocean Engineering"},
            }
        ],
    }
    fake_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        f"$payload = @'\n{json.dumps(fake_payload)}\n'@\n"
        "$payload | Write-Output\n"
        f"$args_json | Set-Content -Encoding UTF8 -LiteralPath {json.dumps(str(args_path))}\n"
        "exit 0\n",
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="https://doi.org/10.1016/j.oceaneng.2024.119432",
        max_results=3,
        paper_search_command=fake_command,
        sources=["arxiv", "semantic", "openalex", "crossref", "unpaywall", "dblp"],
        use_query_plan=True,
    )

    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    invoked_args = json.loads(args_path.read_text(encoding="utf-8-sig"))

    assert query_plan["research_mode"]["mode"] == "exact-lookup"
    assert query_plan["query_variants"] == ["10.1016/j.oceaneng.2024.119432"]
    assert query_plan["source_routing"]["exact_lookup"]["kind"] == "doi"
    assert query_plan["source_routing"]["selected_sources"] == [
        "unpaywall",
        "crossref",
        "openalex",
        "semantic",
    ]
    assert search_record["query_strategy"] == "exact_lookup_single_query"
    assert search_record["query_records"] == []
    assert state["query_strategy"] == "exact_lookup_single_query"
    assert invoked_args == [
        "search",
        "10.1016/j.oceaneng.2024.119432",
        "-n",
        "3",
        "-s",
        "unpaywall,crossref,openalex,semantic",
    ]


def test_dry_run_keeps_environment_command_override_for_default_config_command(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    env_command = tmp_path / "env-paper-search.ps1"
    args_path = tmp_path / "env-args.json"
    fake_payload = {
        "query": "robotics control",
        "sources_used": ["arxiv"],
        "source_results": {"arxiv": 1},
        "errors": {},
        "total": 1,
        "papers": [
            {
                "paper_id": "2401.12345",
                "title": "Robot Control Survey",
                "authors": "A. Researcher",
                "abstract": "Robotics control survey with benchmark evidence.",
                "published_date": "2025-01-02T00:00:00",
                "pdf_url": "https://arxiv.org/pdf/2401.12345",
                "url": "https://arxiv.org/abs/2401.12345",
                "source": "arxiv",
                "citations": 3,
                "extra": {},
            }
        ],
    }
    env_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        f"$payload = @'\n{json.dumps(fake_payload)}\n'@\n"
        "$payload | Write-Output\n"
        f"$args_json | Set-Content -Encoding UTF8 -LiteralPath {json.dumps(str(args_path))}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", str(env_command))
    monkeypatch.setenv("PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED", "1")
    vault = tmp_path / "vault"
    meta = vault / "_paper_source" / "meta"
    meta.mkdir(parents=True)
    (meta / "paper-source-config.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "budget:\n"
        "  max_results: 3\n"
        "paper_search:\n"
        "  command: paper-search\n"
        "  sources:\n"
        "    - arxiv\n",
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics control",
        max_results=None,
        paper_search_command=None,
        sources=None,
        use_query_plan=False,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    invoked_args = json.loads(args_path.read_text(encoding="utf-8-sig"))

    assert search_record["upstream"]["cli_command"].endswith("env-paper-search.ps1")
    assert invoked_args == ["search", "robotics control", "-n", "3", "-s", "arxiv"]


def test_dry_run_ranking_uses_configured_interest_profile_keywords(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    vault = tmp_path / "vault"
    meta = vault / "_paper_source" / "meta"
    meta.mkdir(parents=True)
    (meta / "paper-source-config.yaml").write_text(
        "profile: humanoid_control\n"
        "domains:\n"
        "  - robotics\n"
        "  - control\n"
        "positive_keywords:\n"
        "  - sim2real\n"
        "  - humanoid\n"
        "negative_keywords:\n"
        "  - biomedical trial\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Humanoid Sim2Real Control with Open Benchmarks",
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "venue": "ICRA",
                    "abstract": "Robotics control with sim2real benchmark ablations and open code.",
                    "pdf_url": "https://example.org/fit.pdf",
                    "citation_count": 10,
                    "code_url": "https://github.com/example/fit",
                },
                {
                    "source": "fixture",
                    "title": "Robot Control for Biomedical Trial Screening",
                    "authors": ["B. Researcher"],
                    "year": 2025,
                    "venue": "ICRA",
                    "abstract": "Robotics control benchmark with open code for a biomedical trial workflow.",
                    "pdf_url": "https://example.org/negative.pdf",
                    "citation_count": 10,
                    "code_url": "https://github.com/example/negative",
                },
            ]
        ),
        encoding="utf-8",
    )

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics control",
        max_results=None,
        fixture_path=fixture,
    )

    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))

    assert [candidate["title"] for candidate in ranked] == [
        "Humanoid Sim2Real Control with Open Benchmarks",
        "Robot Control for Biomedical Trial Screening",
    ]
    assert {"sim2real", "humanoid"}.issubset(set(ranked[0]["ranking_protocol"]["matched_positive_keywords"]))
    assert "robotics" in ranked[0]["ranking_protocol"]["matched_positive_keywords"]
    assert ranked[1]["ranking_protocol"]["matched_negative_keywords"] == ["biomedical trial"]
    assert "negative_keyword_overlap: biomedical trial" in ranked[1]["ranking_protocol"]["cautions"]


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
