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
    assert (run_dir / "query-plan.json").is_file()
    assert (run_dir / "search-record.json").is_file()
    assert (run_dir / "normalized.json").is_file()
    assert (run_dir / "filter-report.json").is_file()
    assert (run_dir / "rank.json").is_file()
    assert (run_dir / "report.md").is_file()
    state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    query_plan = json.loads((run_dir / "query-plan.json").read_text(encoding="utf-8"))
    ranked = json.loads((run_dir / "rank.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((run_dir.parent / "index.json").read_text(encoding="utf-8"))
    dashboard_text = (run_dir.parent / "dashboard.md").read_text(encoding="utf-8")
    assert state["run_id"] == run_dir.name
    assert state["workflow_type"] == "paper-discovery-dry-run"
    assert state["state"] == "reported"
    assert state["status"] == "success"
    assert state["dry_run"] is True
    assert state["query_strategy"] == "single_query"
    assert state["query_plan"]["domain"] == "profile-derived"
    assert query_plan["workflow"] == "epi-query-plan"
    assert query_plan["domain"] == "profile-derived"
    assert query_plan["profile"]["domains"] == ["robotics", "control"]
    assert "robotics" in query_plan["concept_blocks"]["domain_terms"]
    assert all("-review -survey" in query for query in query_plan["query_variants"])
    assert report["discovery_context"]["query_plan"]["domain"] == "profile-derived"
    assert report["discovery_context"]["candidate_pool"]["raw"] == 2
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
    assert report["workflow_type"] == "paper-discovery-dry-run"
    assert report["run_id"] == run_dir.name
    assert report["accepted"][0]["title"] == "Embodied Navigation Control for Mobile Robots"
    assert ranked[0]["ranking_protocol"]["schema_version"] == "epi-ranking-protocol-v1"
    assert ranked[0]["ranking_protocol"]["lenses"]["editorial"]["signals"] == [
        "venue_tier",
        "freshness",
        "topic_relevance",
    ]
    assert ranked[0]["ranking_protocol"]["decision"] in {"advance-candidate", "review-candidate"}
    assert report["accepted"][0]["ranking_protocol"] == ranked[0]["ranking_protocol"]
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
    assert report_md.startswith("# EPI Dry Run")
    assert "## Budget Usage" in report_md
    assert "## Next Actions" in report_md
    assert index_payload["runs"][0]["run_id"] == run_dir.name
    assert index_payload["runs"][0]["workflow_type"] == "paper-discovery-dry-run"
    assert run_dir.name in dashboard_text
    assert sorted(path.name for path in (tmp_path / "vault").iterdir()) == ["_runs"]


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
        query_plan_domain="auv-control",
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
    assert search_record["query_plan"]["domain"] == "auv-control"
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
    assert (run_dir / "paper-search-raw-01.json").is_file()
    assert (run_dir / "paper-search-raw.json").is_file()


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


def test_dry_run_uses_configured_paper_search_command_and_sources(tmp_path):
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
    meta = vault / "_meta"
    meta.mkdir(parents=True)
    (meta / "epi-config.yaml").write_text(
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
    invoked_args = json.loads(args_path.read_text(encoding="utf-8-sig"))

    assert search_record["upstream"]["cli_command"].endswith("configured-paper-search.ps1")
    assert search_record["upstream"]["sources_requested"] == ["arxiv", "semantic", "openalex"]
    assert invoked_args == ["search", "robotics survey", "-n", "10", "-s", "arxiv,semantic,openalex"]


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
    monkeypatch.setenv("EPI_PAPER_SEARCH_COMMAND", str(env_command))
    vault = tmp_path / "vault"
    meta = vault / "_meta"
    meta.mkdir(parents=True)
    (meta / "epi-config.yaml").write_text(
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
    meta = vault / "_meta"
    meta.mkdir(parents=True)
    (meta / "epi-config.yaml").write_text(
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
