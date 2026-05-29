import json
import subprocess

from epi.paper_search_adapter import COMMAND_UNAVAILABLE
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


def test_live_cli_discovery_invokes_paper_search_and_maps_records(tmp_path):
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


def test_live_cli_discovery_fails_closed_when_command_is_missing(tmp_path):
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


def test_probe_paper_search_fails_closed_on_timeout(monkeypatch):
    monkeypatch.setattr("epi.paper_search_adapter._resolve_command", lambda command: command)

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["paper-search", "--version"], timeout=15)

    monkeypatch.setattr("epi.paper_search_adapter._run_command", _timeout)

    result = probe_paper_search_mcp("paper-search")

    assert result["available"] is False
    assert result["command"] == "paper-search"
    assert result["error"] == "probe_timeout"
