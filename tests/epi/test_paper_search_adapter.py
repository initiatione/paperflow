import json
import subprocess

from epi.paper_search_adapter import COMMAND_UNAVAILABLE
from epi.paper_search_adapter import MCPToolError
from epi.paper_search_adapter import SEARCH_TIMEOUT_SECONDS
from epi.paper_search_adapter import download_paper_pdf
from epi.paper_search_adapter import discover
from epi.paper_search_adapter import plan_source_routing
from epi.paper_search_adapter import probe_paper_search_mcp
import epi.paper_search_adapter as paper_search_adapter


def _write_fake_paper_search(tmp_path, payload: dict, version: str = "paper-search 0.1.4") -> str:
    script = tmp_path / "paper-search.ps1"
    script.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        f"if ($args -contains '--version') {{ Write-Output {json.dumps(version)}; exit 0 }}\n"
        f"$payload = @'\n{json.dumps(payload)}\n'@\n"
        "$payload | Write-Output\n"
        "$args_json | Set-Content -Encoding UTF8 -LiteralPath "
        + json.dumps(str(tmp_path / "args.json"))
        + "\n"
        "exit 0\n",
        encoding="utf-8",
    )
    return str(script)


def test_plan_source_routing_demotes_unstable_sources_and_reports_provider_risks(monkeypatch):
    monkeypatch.delenv("PAPER_SEARCH_MCP_CORE_API_KEY", raising=False)
    monkeypatch.delenv("PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL", raising=False)
    monkeypatch.setenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", "research@example.org")

    plan = plan_source_routing(
        ["google_scholar", "semantic", "core", "unpaywall", "base"],
        include_unstable=False,
    )

    assert plan["requested_sources"] == ["google_scholar", "semantic", "core", "unpaywall", "base"]
    assert plan["selected_sources"] == ["semantic", "core", "unpaywall"]
    assert plan["demoted_sources"] == [
        {"source": "google_scholar", "reason": "unstable_source"},
        {"source": "base", "reason": "unstable_source"},
    ]
    assert plan["provider_readiness"]["unpaywall"]["status"] == "set"
    assert plan["provider_readiness"]["core"]["status"] == "missing_recommended_env"
    assert plan["provider_risks"] == [
        {
            "provider": "core",
            "status": "missing_recommended_env",
            "env": "PAPER_SEARCH_MCP_CORE_API_KEY",
            "importance": "recommended",
            "reason": "CORE works better with a free API key and may rate-limit keyless access.",
        }
    ]


def test_plan_source_routing_narrows_exact_doi_lookup_to_identifier_sources(monkeypatch):
    monkeypatch.setenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", "research@example.org")

    plan = plan_source_routing(query="https://doi.org/10.1016/j.oceaneng.2024.119432")

    assert plan["exact_lookup"] == {
        "kind": "doi",
        "value": "10.1016/j.oceaneng.2024.119432",
        "source_policy": "doi_exact",
    }
    assert plan["selected_sources"] == ["unpaywall", "crossref", "openalex", "semantic"]
    assert {"source": "arxiv", "reason": "exact_doi_lookup"} in plan["demoted_sources"]
    assert {"source": "dblp", "reason": "exact_doi_lookup"} in plan["demoted_sources"]


def test_plan_source_routing_prioritizes_arxiv_id_exact_lookup():
    plan = plan_source_routing(
        ["semantic", "arxiv", "openalex", "crossref"],
        query="arXiv:2401.12345v2",
    )

    assert plan["exact_lookup"] == {
        "kind": "arxiv_id",
        "value": "2401.12345v2",
        "source_policy": "arxiv_exact",
    }
    assert plan["selected_sources"] == ["arxiv"]
    assert plan["demoted_sources"] == [
        {"source": "semantic", "reason": "exact_arxiv_lookup"},
        {"source": "openalex", "reason": "exact_arxiv_lookup"},
        {"source": "crossref", "reason": "exact_arxiv_lookup"},
    ]


def test_plan_source_routing_detects_explicit_exact_title_lookup():
    plan = plan_source_routing(
        ["arxiv", "semantic", "openalex", "crossref", "unpaywall"],
        query='title:"Fault Tolerant Model Predictive Control for Autonomous Underwater Vehicles"',
    )

    assert plan["exact_lookup"] == {
        "kind": "title",
        "value": "Fault Tolerant Model Predictive Control for Autonomous Underwater Vehicles",
        "source_policy": "title_exact",
    }
    assert plan["selected_sources"] == ["semantic", "openalex", "crossref"]
    assert {"source": "arxiv", "reason": "exact_title_lookup"} in plan["demoted_sources"]
    assert {"source": "unpaywall", "reason": "exact_title_lookup"} in plan["demoted_sources"]


def test_discovery_prefers_paper_search_mcp_server_over_cli(tmp_path, monkeypatch):
    cli_command = _write_fake_paper_search(tmp_path, {"papers": []})

    def _unexpected_cli(*args, **kwargs):
        raise AssertionError("CLI fallback should not run when MCP search succeeds")

    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        assert tool_name == "search_papers"
        assert arguments == {
            "query": "robotics control",
            "max_results_per_source": 3,
            "sources": "arxiv,semantic",
        }
        return {
            "payload": {
                "query": "robotics control",
                "sources_used": ["arxiv"],
                "source_results": {"arxiv": 1},
                "errors": {},
                "total": 1,
                "papers": [
                    {
                        "paper_id": "2401.12345",
                        "title": "Embodied Control with Foundation Models",
                        "authors": ["Ada Lovelace", "Grace Hopper"],
                        "abstract": "A survey of embodied AI control.",
                        "published_date": "2025-01-02",
                        "pdf_url": "https://arxiv.org/pdf/2401.12345",
                        "url": "https://arxiv.org/abs/2401.12345",
                        "source": "arxiv",
                        "citations": 17,
                    }
                ],
            },
            "probe": {
                "available": True,
                "command": "python",
                "args": ["-m", "paper_search_mcp.server"],
                "transport": "stdio",
                "server_info": {"name": "paper_search_server"},
            },
            "raw_response": {"result": {"structuredContent": {"total": 1}}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _fake_mcp_tool)
    monkeypatch.setattr("epi.paper_search_adapter._run_command", _unexpected_cli)

    result = discover(
        query="robotics control",
        max_results=3,
        command=cli_command,
        sources=["arxiv", "semantic"],
        raw_response_path=tmp_path / "raw-search.json",
    )

    assert result["source_mode"] == "paper_search_mcp"
    assert result["mcp_probe"]["available"] is True
    assert result["upstream"]["transport"] == "stdio"
    assert result["upstream"]["tool"] == "search_papers"
    assert result["upstream"]["sources_used"] == ["arxiv"]
    assert result["raw_response_path"] == str(tmp_path / "raw-search.json")
    assert json.loads((tmp_path / "raw-search.json").read_text(encoding="utf-8"))["total"] == 1
    assert result["records"][0]["title"] == "Embodied Control with Foundation Models"
    assert result["records"][0]["arxiv_id"] == "2401.12345"


def test_discovery_records_source_health_for_mcp_search(tmp_path, monkeypatch):
    perf_counter_values = iter([100.0, 102.5])

    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        assert timeout_seconds == 180
        return {
            "payload": {
                "query": "robotics control",
                "sources_used": ["semantic", "openalex", "google_scholar"],
                "source_results": {"semantic": 2, "openalex": 1, "google_scholar": 0},
                "errors": {"google_scholar": "bot detection blocked request"},
                "raw_total": 3,
                "total": 3,
                "papers": [
                    {
                        "paper_id": "semantic-123",
                        "title": "Semantic Paper",
                        "authors": "A. Researcher",
                        "source": "semantic",
                        "year": 2025,
                    }
                ],
            },
            "probe": {"available": True, "transport": "stdio"},
            "raw_response": {"result": {"structuredContent": {"total": 3}}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _fake_mcp_tool)
    monkeypatch.setattr("epi.paper_search_adapter.time.perf_counter", lambda: next(perf_counter_values))

    result = discover(
        query="robotics control",
        max_results=3,
        command=str(tmp_path / "missing-cli"),
        sources=["semantic", "openalex", "google_scholar"],
        timeout_seconds=180,
    )

    source_health = result["upstream"]["source_health"]
    assert result["upstream"]["timeout_budget_seconds"] == 180
    assert source_health["semantic"] == {
        "status": "ok",
        "result_count": 2,
        "error": None,
        "duration_ms": None,
        "timeout_budget_seconds": 180,
    }
    assert source_health["openalex"]["status"] == "ok"
    assert source_health["openalex"]["result_count"] == 1
    assert source_health["google_scholar"] == {
        "status": "failed",
        "result_count": 0,
        "error": "bot detection blocked request",
        "duration_ms": None,
        "timeout_budget_seconds": 180,
    }
    assert result["upstream"]["search_duration_ms"] == 2500


def test_discovery_falls_back_to_cli_when_paper_search_mcp_server_fails(tmp_path, monkeypatch):
    cli_command = _write_fake_paper_search(
        tmp_path,
        {
            "query": "robotics control",
            "sources_used": ["semantic"],
            "source_results": {"semantic": 1},
            "errors": {},
            "total": 1,
            "papers": [
                {
                    "paper_id": "semantic-123",
                    "title": "Fallback Paper",
                    "authors": "A. Researcher",
                    "source": "semantic",
                    "year": 2024,
                }
            ],
        },
    )

    def _failing_mcp_tool(*args, **kwargs):
        raise MCPToolError(
            "mcp unavailable",
            probe={
                "available": False,
                "command": "python",
                "args": ["-m", "paper_search_mcp.server"],
                "transport": "stdio",
                "error": "mcp unavailable",
            },
        )

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _failing_mcp_tool)

    result = discover(
        query="robotics control",
        max_results=2,
        command=cli_command,
        sources=["semantic"],
    )

    assert result["source_mode"] == "paper_search_cli"
    assert result["mcp_server_probe"]["available"] is False
    assert result["upstream"]["fallback_from"] == "paper_search_mcp"
    assert result["upstream"]["fallback_error"] == "mcp unavailable"
    assert result["records"][0]["title"] == "Fallback Paper"


def test_discovery_falls_back_to_cli_when_mcp_returns_no_papers(tmp_path, monkeypatch):
    cli_command = _write_fake_paper_search(
        tmp_path,
        {
            "query": "robotics",
            "sources_used": ["semantic"],
            "source_results": {"semantic": 1},
            "errors": {},
            "total": 1,
            "papers": [
                {
                    "paper_id": "semantic-123",
                    "title": "CLI Fallback After Empty MCP",
                    "authors": "A. Researcher",
                    "source": "semantic",
                    "year": 2025,
                }
            ],
        },
    )

    def _empty_mcp_tool(*args, **kwargs):
        return {
            "payload": {
                "query": "robotics",
                "sources_used": ["semantic"],
                "source_results": {"semantic": 0},
                "errors": {},
                "papers": [],
                "total": 0,
            },
            "probe": {"available": True, "transport": "stdio"},
            "raw_response": {"result": {"structuredContent": {"result": {"total": 0}}}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _empty_mcp_tool)

    result = discover(
        query="robotics",
        max_results=1,
        command=cli_command,
        sources=["semantic"],
    )

    assert result["source_mode"] == "paper_search_cli"
    assert result["mcp_server_probe"]["available"] is False
    assert result["mcp_server_probe"]["error"] == "paper-search MCP search returned no papers"
    assert result["upstream"]["fallback_from"] == "paper_search_mcp"
    assert result["records"][0]["title"] == "CLI Fallback After Empty MCP"


def test_discovery_unwraps_mcp_structured_content_result(tmp_path, monkeypatch):
    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        return {
            "payload": {
                "result": {
                    "query": "robotics survey",
                    "sources_used": ["arxiv"],
                    "source_results": {"arxiv": 1},
                    "errors": {},
                    "total": 1,
                    "papers": [
                        {
                            "paper_id": "2501.00001",
                            "title": "Robotics Foundation Model Survey",
                            "authors": "A. Researcher",
                            "source": "arxiv",
                            "published_date": "2025-01-01",
                        }
                    ],
                }
            },
            "probe": {"available": True, "transport": "stdio"},
            "raw_response": {"result": {"structuredContent": {"result": {"total": 1}}}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _fake_mcp_tool)

    result = discover(
        query="robotics survey",
        max_results=1,
        command=str(tmp_path / "missing-cli"),
        sources=["arxiv"],
    )

    assert result["source_mode"] == "paper_search_mcp"
    assert result["upstream"]["sources_used"] == ["arxiv"]
    assert result["upstream"]["source_results"] == {"arxiv": 1}
    assert result["upstream"]["total"] == 1
    assert result["records"][0]["title"] == "Robotics Foundation Model Survey"


def test_download_prefers_paper_search_mcp_fallback_chain(tmp_path, monkeypatch):
    output_dir = tmp_path / "downloads"

    def _unexpected_cli(*args, **kwargs):
        raise AssertionError("CLI fallback should not run when MCP download succeeds")

    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        assert tool_name == "download_with_fallback"
        assert arguments == {
            "source": "semantic",
            "paper_id": "semantic-123",
            "doi": "10.1234/semantic",
            "title": "Semantic Fallback Paper",
            "save_path": str(output_dir),
            "use_scihub": False,
            "scihub_base_url": "https://sci-hub.se",
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mcp fallback fixture")
        return {
            "payload": {"text": str(pdf_path)},
            "probe": {
                "available": True,
                "command": "python",
                "args": ["-m", "paper_search_mcp.server"],
                "transport": "stdio",
            },
            "raw_response": {"result": {"content": [{"type": "text", "text": str(pdf_path)}]}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _fake_mcp_tool)
    monkeypatch.setattr("epi.paper_search_adapter._run_command", _unexpected_cli)

    result = download_paper_pdf(
        source="semantic",
        paper_id="semantic-123",
        doi="10.1234/semantic",
        title="Semantic Fallback Paper",
        output_dir=output_dir,
    )

    assert result["status"] == "success"
    assert result["mode"] == "paper_search_mcp_fallback_download"
    assert result["mcp_probe"]["available"] is True
    assert result["mcp_server_probe"]["available"] is True
    assert result["upstream"]["transport"] == "stdio"
    assert result["upstream"]["tool"] == "download_with_fallback"
    assert result["upstream"]["fallback_chain"] == [
        "source-native",
        "openaire",
        "core",
        "europepmc",
        "pmc",
        "unpaywall",
    ]
    assert result["upstream"]["use_scihub"] is False
    assert result["downloaded_pdf"] == str(output_dir / "paper.pdf")


def test_download_falls_back_to_source_native_mcp_when_fallback_tool_fails(tmp_path, monkeypatch):
    output_dir = tmp_path / "downloads"
    calls = []

    def _unexpected_cli(*args, **kwargs):
        raise AssertionError("CLI fallback should not run when source-native MCP download succeeds")

    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        calls.append((tool_name, arguments))
        if tool_name == "download_with_fallback":
            raise MCPToolError(
                "unknown tool: download_with_fallback",
                probe={"available": False, "transport": "stdio", "error": "unknown_tool"},
            )
        assert tool_name == "download_arxiv"
        assert arguments == {"paper_id": "2401.12345", "save_path": str(output_dir)}
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / "arxiv.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mcp source-native fixture")
        return {
            "payload": {"text": str(pdf_path)},
            "probe": {"available": True, "transport": "stdio"},
            "raw_response": {"result": {"content": [{"type": "text", "text": str(pdf_path)}]}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _fake_mcp_tool)
    monkeypatch.setattr("epi.paper_search_adapter._run_command", _unexpected_cli)

    result = download_paper_pdf(
        source="arxiv",
        paper_id="2401.12345",
        doi="10.1234/arxiv",
        title="Arxiv Source Native Paper",
        output_dir=output_dir,
    )

    assert [call[0] for call in calls] == ["download_with_fallback", "download_arxiv"]
    assert result["status"] == "success"
    assert result["mode"] == "paper_search_mcp_download"
    assert result["mcp_server_probe"]["error"] == "unknown tool: download_with_fallback"
    assert result["upstream"]["fallback_from"] == "paper_search_mcp_fallback_download"
    assert result["upstream"]["tool"] == "download_arxiv"
    assert result["downloaded_pdf"] == str(output_dir / "arxiv.pdf")


def test_download_can_stop_after_oa_fallback_without_source_native_or_cli(tmp_path, monkeypatch):
    output_dir = tmp_path / "downloads"
    calls = []

    def _unexpected_cli(*args, **kwargs):
        raise AssertionError("CLI fallback should not run after OA fallback is exhausted")

    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        calls.append((tool_name, arguments))
        assert tool_name == "download_with_fallback"
        return {
            "payload": {"text": "no OA URL found"},
            "probe": {"available": True, "transport": "stdio"},
            "raw_response": {"result": {"content": [{"type": "text", "text": "no OA URL found"}]}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _fake_mcp_tool)
    monkeypatch.setattr("epi.paper_search_adapter._run_command", _unexpected_cli)

    result = download_paper_pdf(
        source="semantic",
        paper_id="semantic-123",
        doi="10.1016/j.oceaneng.2024.119432",
        title="Publisher Only Paper",
        output_dir=output_dir,
        stop_after_oa_fallback=True,
    )

    assert [call[0] for call in calls] == ["download_with_fallback"]
    assert result["status"] == "failed"
    assert result["mode"] == "paper_search_mcp_fallback_download"
    assert result["mcp_server_probe"]["error"] == "paper-search MCP fallback download produced no PDF"
    assert result["upstream"]["tool"] == "download_with_fallback"
    assert result["upstream"]["fallback_chain"] == [
        "source-native",
        "openaire",
        "core",
        "europepmc",
        "pmc",
        "unpaywall",
    ]
    assert result["error"] == "paper-search OA fallback produced no PDF"


def test_download_treats_cli_timeout_as_upstream_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    monkeypatch.setattr("epi.paper_search_adapter._resolve_command", lambda command: command)

    def _run_command(resolved_command, args, timeout_seconds):
        if args == ["--version"]:
            return subprocess.CompletedProcess(
                args=[resolved_command, *args],
                returncode=0,
                stdout="paper-search 0.1.4\n",
                stderr="",
            )
        raise subprocess.TimeoutExpired(
            cmd=[resolved_command, *args],
            timeout=timeout_seconds,
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr("epi.paper_search_adapter._run_command", _run_command)

    result = download_paper_pdf(
        source="arxiv",
        paper_id="2511.06465v1",
        output_dir=tmp_path / "downloads",
        command="paper-search",
        timeout_seconds=7,
    )

    assert result["status"] == "failed"
    assert result["mode"] == "paper_search_cli_download"
    assert result["error"] == "paper-search download timed out"
    assert result["upstream"]["returncode"] is None
    assert result["upstream"]["stdout"] == "partial stdout"
    assert result["upstream"]["stderr"] == "partial stderr"
    assert result["upstream"]["timeout_seconds"] == 7


def test_read_preview_prefers_paper_search_mcp_read_tool(tmp_path, monkeypatch):
    output_path = tmp_path / "paper-search-read-preview.txt"

    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        assert tool_name == "read_arxiv_paper"
        assert arguments == {"paper_id": "2401.12345", "save_path": str(tmp_path)}
        return {
            "payload": {"text": "Full extracted paper text from MCP."},
            "probe": {"available": True, "transport": "stdio"},
            "raw_response": {"result": {"content": [{"type": "text", "text": "Full extracted paper text from MCP."}]}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _fake_mcp_tool)

    result = paper_search_adapter.read_paper_preview(
        source="arxiv",
        paper_id="2401.12345",
        output_path=output_path,
    )

    assert result["status"] == "success"
    assert result["mode"] == "paper_search_mcp_read_preview"
    assert result["tool"] == "read_arxiv_paper"
    assert result["output_path"] == str(output_path)
    assert result["char_count"] == len("Full extracted paper text from MCP.")
    assert result["authoritative"] is False
    assert result["replaces_mineru"] is False
    assert output_path.read_text(encoding="utf-8") == "Full extracted paper text from MCP.\n"


def test_read_preview_soft_fails_when_mcp_and_cli_are_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")

    result = paper_search_adapter.read_paper_preview(
        source="semantic",
        paper_id="semantic-123",
        output_path=tmp_path / "paper-search-read-preview.txt",
        command=str(tmp_path / "missing-paper-search"),
    )

    assert result["status"] == "failed"
    assert result["mode"] == "paper_search_cli_read_preview"
    assert result["tool"] == "read_semantic_paper"
    assert result["authoritative"] is False
    assert result["replaces_mineru"] is False
    assert "disabled" in result["mcp_server_probe"]["error"]
    assert result["mcp_probe"]["error"] == "command_not_found"
    assert not (tmp_path / "paper-search-read-preview.txt").exists()


def test_read_preview_rejects_info_only_mcp_text(tmp_path, monkeypatch):
    output_path = tmp_path / "paper-search-read-preview.txt"

    def _info_only_mcp_tool(tool_name, arguments, timeout_seconds):
        return {
            "payload": {"text": "Info-only: read_semantic_paper is unsupported for this source."},
            "probe": {"available": True, "transport": "stdio"},
            "raw_response": {"result": {"content": [{"type": "text", "text": "unsupported"}]}},
        }

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _info_only_mcp_tool)

    result = paper_search_adapter.read_paper_preview(
        source="semantic",
        paper_id="semantic-123",
        output_path=output_path,
        command=str(tmp_path / "missing-paper-search"),
    )

    assert result["status"] == "failed"
    assert result["mode"] == "paper_search_cli_read_preview"
    assert result["mcp_server_probe"]["error"] == "paper-search MCP read preview produced no meaningful text"
    assert not output_path.exists()


def test_read_preview_falls_back_to_cli_when_mcp_read_fails(tmp_path, monkeypatch):
    output_path = tmp_path / "paper-search-read-preview.txt"
    fake_command = tmp_path / "paper-search-read.ps1"
    args_path = tmp_path / "read-args.json"
    fake_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        "Write-Output 'CLI extracted paper text.'\n"
        f"$args_json | Set-Content -Encoding UTF8 -LiteralPath {json.dumps(str(args_path))}\n"
        "exit 0\n",
        encoding="utf-8",
    )

    def _failing_mcp_tool(*args, **kwargs):
        raise MCPToolError(
            "read tool unavailable",
            probe={"available": False, "transport": "stdio", "error": "unknown_tool"},
        )

    monkeypatch.setattr("epi.paper_search_adapter._call_mcp_tool", _failing_mcp_tool)

    result = paper_search_adapter.read_paper_preview(
        source="semantic",
        paper_id="semantic-123",
        output_path=output_path,
        command=str(fake_command),
    )

    assert result["status"] == "success"
    assert result["mode"] == "paper_search_cli_read_preview"
    assert result["tool"] == "read_semantic_paper"
    assert result["mcp_server_probe"]["error"] == "read tool unavailable"
    assert result["upstream"]["fallback_error"] == "read tool unavailable"
    assert result["output_path"] == str(output_path)
    assert result["char_count"] == len("CLI extracted paper text.")
    assert output_path.read_text(encoding="utf-8") == "CLI extracted paper text.\n"
    assert json.loads(args_path.read_text(encoding="utf-8-sig")) == [
        "read",
        "semantic",
        "semantic-123",
        "--save-path",
        str(tmp_path),
    ]


def test_live_cli_discovery_invokes_paper_search_and_maps_records(tmp_path, monkeypatch):
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    fake_command = _write_fake_paper_search(
        tmp_path,
        {
            "query": "robotics control",
            "sources_used": ["arxiv", "semantic"],
            "source_results": {"arxiv": 1, "semantic": 0},
            "errors": {"semantic": "rate limited"},
            "total": 1,
            "papers": [
                {
                    "paper_id": "2401.12345",
                    "title": "Embodied Control for Humanoid Robots",
                    "authors": "Ada Lovelace; Grace Hopper",
                    "abstract": "Robotics control with reproducible experiments.",
                    "doi": "10.1234/example",
                    "published_date": "2025-01-02T00:00:00",
                    "pdf_url": "https://arxiv.org/pdf/2401.12345",
                    "url": "https://arxiv.org/abs/2401.12345",
                    "source": "arxiv",
                    "citations": 17,
                    "extra": {"venue": "ICRA", "code_url": "https://github.com/example/control"},
                }
            ],
        },
    )

    result = discover(
        query="robotics control",
        max_results=3,
        command=fake_command,
        sources=["arxiv", "semantic"],
        raw_response_path=tmp_path / "raw-search.json",
    )

    assert result["source_mode"] == "paper_search_cli"
    assert result["query"] == "robotics control"
    assert result["max_results"] == 3
    assert result["mcp_probe"]["available"] is True
    assert result["upstream"]["package"] == "paper-search-mcp"
    assert result["upstream"]["cli_command"].endswith("paper-search.ps1")
    assert result["upstream"]["version_probe"]["stdout"] == "paper-search 0.1.4"
    assert result["upstream"]["sources_used"] == ["arxiv", "semantic"]
    assert result["upstream"]["source_results"] == {"arxiv": 1, "semantic": 0}
    assert result["upstream"]["errors"] == {"semantic": "rate limited"}
    assert result["raw_response_path"] == str(tmp_path / "raw-search.json")
    assert (tmp_path / "raw-search.json").is_file()
    assert json.loads((tmp_path / "raw-search.json").read_text(encoding="utf-8"))["total"] == 1
    assert json.loads((tmp_path / "args.json").read_text(encoding="utf-8-sig")) == [
        "search",
        "robotics control",
        "-n",
        "3",
        "-s",
        "arxiv,semantic",
    ]
    assert result["records"] == [
        {
            "source": "arxiv",
            "title": "Embodied Control for Humanoid Robots",
            "authors": ["Ada Lovelace", "Grace Hopper"],
            "year": 2025,
            "venue": "ICRA",
            "abstract": "Robotics control with reproducible experiments.",
            "doi": "10.1234/example",
            "arxiv_id": "2401.12345",
            "pdf_url": "https://arxiv.org/pdf/2401.12345",
            "url": "https://arxiv.org/abs/2401.12345",
            "code_url": "https://github.com/example/control",
            "citation_count": 17,
            "raw_record": {
                "paper_id": "2401.12345",
                "title": "Embodied Control for Humanoid Robots",
                "authors": "Ada Lovelace; Grace Hopper",
                "abstract": "Robotics control with reproducible experiments.",
                "doi": "10.1234/example",
                "published_date": "2025-01-02T00:00:00",
                "pdf_url": "https://arxiv.org/pdf/2401.12345",
                "url": "https://arxiv.org/abs/2401.12345",
                "source": "arxiv",
                "citations": 17,
                "extra": {"venue": "ICRA", "code_url": "https://github.com/example/control"},
            },
        }
    ]


def test_live_cli_discovery_fails_closed_when_command_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    result = discover(
        query="robotics",
        max_results=2,
        command=str(tmp_path / "missing-paper-search"),
    )

    assert result["source_mode"] == "paper_search_cli"
    assert result["records"] == []
    assert result["mcp_probe"]["available"] is False
    assert result["mcp_probe"]["error"] == "command_not_found"
    assert result["error"] == COMMAND_UNAVAILABLE


def test_live_cli_discovery_treats_empty_stdout_with_stderr_as_upstream_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    script = tmp_path / "paper-search-empty.ps1"
    script.write_text(
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        "[Console]::Error.WriteLine('Failed to resolve --with requirement: Git operation failed')\n"
        "exit 0\n",
        encoding="utf-8",
    )

    result = discover(
        query="robotics",
        max_results=2,
        command=str(script),
        sources=["arxiv"],
        raw_response_path=tmp_path / "raw-search.json",
    )

    assert result["records"] == []
    assert result["error"] == "paper-search search failed"
    assert result["upstream"]["returncode"] == 0
    assert "Git operation failed" in result["upstream"]["stderr"]


def test_live_cli_discovery_treats_search_timeout_as_upstream_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    raw_response_path = tmp_path / "raw-search.json"
    monkeypatch.setattr("epi.paper_search_adapter._resolve_command", lambda command: command)

    def _run_command(resolved_command, args, timeout_seconds):
        if args == ["--version"]:
            return subprocess.CompletedProcess(
                args=[resolved_command, *args],
                returncode=0,
                stdout="paper-search 0.1.4\n",
                stderr="",
            )
        raise subprocess.TimeoutExpired(
            cmd=[resolved_command, *args],
            timeout=timeout_seconds,
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr("epi.paper_search_adapter._run_command", _run_command)

    result = discover(
        query="robotics",
        max_results=2,
        command="paper-search",
        sources=["arxiv"],
        raw_response_path=raw_response_path,
    )

    assert result["records"] == []
    assert result["error"] == "paper-search search timed out"
    assert result["upstream"]["returncode"] is None
    assert result["upstream"]["timeout_seconds"] == SEARCH_TIMEOUT_SECONDS
    assert result["raw_response_path"] == str(raw_response_path)
    raw_payload = json.loads(raw_response_path.read_text(encoding="utf-8"))
    assert raw_payload["timeout_seconds"] == SEARCH_TIMEOUT_SECONDS
    assert raw_payload["stderr"] == "partial stderr"


def test_probe_paper_search_fails_closed_on_timeout(monkeypatch):
    monkeypatch.setattr("epi.paper_search_adapter._resolve_command", lambda command: command)

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["paper-search", "--version"], timeout=15)

    monkeypatch.setattr("epi.paper_search_adapter._run_command", _timeout)

    result = probe_paper_search_mcp("paper-search")

    assert result["available"] is False
    assert result["command"] == "paper-search"
    assert result["error"] == "probe_timeout"
