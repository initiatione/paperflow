import json
import subprocess

from epi.paper_search_adapter import COMMAND_UNAVAILABLE
from epi.paper_search_adapter import MCPToolError
from epi.paper_search_adapter import SEARCH_TIMEOUT_SECONDS
from epi.paper_search_adapter import download_paper_pdf
from epi.paper_search_adapter import discover
from epi.paper_search_adapter import probe_paper_search_mcp


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


def test_download_prefers_paper_search_mcp_server_over_cli(tmp_path, monkeypatch):
    output_dir = tmp_path / "downloads"

    def _unexpected_cli(*args, **kwargs):
        raise AssertionError("CLI fallback should not run when MCP download succeeds")

    def _fake_mcp_tool(tool_name, arguments, timeout_seconds):
        assert tool_name == "download_semantic"
        assert arguments == {"paper_id": "semantic-123", "save_path": str(output_dir)}
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mcp fixture")
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

    result = download_paper_pdf(source="semantic", paper_id="semantic-123", output_dir=output_dir)

    assert result["status"] == "success"
    assert result["mode"] == "paper_search_mcp_download"
    assert result["mcp_probe"]["available"] is True
    assert result["upstream"]["transport"] == "stdio"
    assert result["upstream"]["tool"] == "download_semantic"
    assert result["downloaded_pdf"] == str(output_dir / "paper.pdf")


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
        "Write-Error 'Failed to resolve --with requirement: Git operation failed'\n"
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
