import json
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from epi.acquire_papers import acquire_paper_from_url, _classify_acquire_failure
from epi.orchestrator import acquire_paper_from_candidate


def _candidate(url, slug="downloaded-paper"):
    return {
        "slug": slug,
        "title": "Downloaded Paper",
        "authors": ["A. Researcher"],
        "year": 2026,
        "venue": "ICRA",
        "doi": "10.1000/downloaded",
        "pdf_url": url,
        "score": 0.7,
        "sources": ["local-http"],
    }


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return


class _LocalServer:
    def __init__(self, root):
        self.root = root
        self.server = None
        self.thread = None
        self.previous_cwd = None

    def __enter__(self):
        self.previous_cwd = os.getcwd()
        os.chdir(self.root)
        handler = partial(_QuietHandler, directory=str(self.root))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        os.chdir(self.previous_cwd)


def test_acquire_paper_from_url_downloads_pdf_and_records_metadata(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    source_pdf = server_root / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nurl fixture\n")
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "papers" / "downloaded-paper"

    with _LocalServer(server_root) as base_url:
        record = acquire_paper_from_url(_candidate(f"{base_url}/paper.pdf"), paper_root)

    assert record["stage"] == "acquire"
    assert record["mode"] == "url"
    assert record["status"] == "success"
    assert record["exit_status"] == 0
    assert record["started_at"]
    assert record["finished_at"]
    assert record["http_status"] == 200
    assert record["pdf_url"].endswith("/paper.pdf")
    assert record["output_path"] == str(paper_root / "paper.pdf")
    assert record["size_bytes"] == len(b"%PDF-1.4\nurl fixture\n")
    assert record["input_artifact_hashes"]["candidate_metadata"]
    assert record["output_artifact_hashes"]["paper.pdf"]
    assert record["output_artifact_hashes"]["metadata.json"]
    assert (paper_root / "paper.pdf").read_bytes() == source_pdf.read_bytes()
    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["slug"] == "downloaded-paper"
    assert metadata["pdf_url"] == record["pdf_url"]
    assert json.loads((paper_root / "acquire-record.json").read_text(encoding="utf-8")) == record


def test_acquire_paper_from_url_records_http_failure_without_pdf(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "papers" / "missing-paper"

    with _LocalServer(server_root) as base_url:
        record = acquire_paper_from_url(_candidate(f"{base_url}/missing.pdf", slug="missing-paper"), paper_root)

    assert record["status"] == "failed"
    assert record["mode"] == "url"
    assert record["exit_status"] == 1
    assert record["started_at"]
    assert record["finished_at"]
    assert record["http_status"] == 404
    assert "HTTP 404" in record["error"]
    assert record["failure_class"] == "not-found"
    assert record["retryable"] is False
    assert record["recovery_hint"]
    assert record["input_artifact_hashes"]["candidate_metadata"]
    assert record["output_artifact_hashes"]["metadata.json"]
    assert not (paper_root / "paper.pdf").exists()
    assert json.loads((paper_root / "acquire-record.json").read_text(encoding="utf-8")) == record


def test_acquire_paper_from_candidate_prefers_paper_search_cli_download(tmp_path, monkeypatch):
    monkeypatch.setenv("EPI_PAPER_SEARCH_MCP_DISABLED", "1")
    fake_command = tmp_path / "paper-search-download.ps1"
    args_path = tmp_path / "download-args.json"
    fake_command.write_text(
        "$args_json = $args | ConvertTo-Json -Compress\n"
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        "$output_index = [Array]::IndexOf($args, '--save-path')\n"
        "if ($output_index -lt 0) { Write-Error 'missing --save-path'; exit 2 }\n"
        "$output_dir = $args[$output_index + 1]\n"
        "New-Item -ItemType Directory -Force -Path $output_dir | Out-Null\n"
        "$bytes = [System.Text.Encoding]::ASCII.GetBytes('%PDF-1.4 paper-search fixture')\n"
        "[System.IO.File]::WriteAllBytes((Join-Path $output_dir 'downloaded.pdf'), $bytes)\n"
        f"$args_json | Set-Content -Encoding UTF8 -LiteralPath {json.dumps(str(args_path))}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPI_PAPER_SEARCH_COMMAND", str(fake_command))
    candidate = _candidate("https://example.org/fallback.pdf", slug="paper-search-cli-paper")
    candidate["sources"] = ["arxiv"]
    candidate["raw_records"] = [
        {
            "source": "arxiv",
            "arxiv_id": "2401.12345",
            "raw_record": {"paper_id": "2401.12345", "source": "arxiv"},
        }
    ]
    vault = tmp_path / "vault"

    record = acquire_paper_from_candidate(vault, candidate)

    paper_root = vault / "_epi" / "raw" / "papers" / "paper-search-cli-paper"
    invoked_args = json.loads(args_path.read_text(encoding="utf-8-sig"))

    assert record["status"] == "success"
    assert record["mode"] == "paper_search_cli_download"
    assert record["source"] == "arxiv"
    assert record["paper_id"] == "2401.12345"
    assert record["upstream"]["package"] == "paper-search-mcp"
    assert invoked_args[:3] == ["download", "arxiv", "2401.12345"]
    assert "--save-path" in invoked_args
    assert (paper_root / "paper.pdf").read_bytes().startswith(b"%PDF-1.4")
    assert json.loads((paper_root / "acquire-record.json").read_text(encoding="utf-8")) == record


def test_acquire_paper_from_candidate_records_paper_search_mcp_download_mode(tmp_path, monkeypatch):
    def _fake_download_paper_pdf(*, source, paper_id, output_dir, command=None, timeout_seconds=120):
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / "mcp.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mcp acquire fixture")
        return {
            "status": "success",
            "mode": "paper_search_mcp_download",
            "source": source,
            "paper_id": paper_id,
            "mcp_probe": {"available": True, "transport": "stdio"},
            "downloaded_pdf": str(pdf_path),
            "upstream": {"package": "paper-search-mcp", "transport": "stdio", "tool": "download_arxiv"},
        }

    monkeypatch.setattr("epi.acquire_papers.download_paper_pdf", _fake_download_paper_pdf)
    candidate = _candidate("https://example.org/fallback.pdf", slug="paper-search-mcp-paper")
    candidate["sources"] = ["arxiv"]
    candidate["raw_records"] = [
        {
            "source": "arxiv",
            "arxiv_id": "2401.12345",
            "raw_record": {"paper_id": "2401.12345", "source": "arxiv"},
        }
    ]
    vault = tmp_path / "vault"

    record = acquire_paper_from_candidate(vault, candidate)

    paper_root = vault / "_epi" / "raw" / "papers" / "paper-search-mcp-paper"
    assert record["status"] == "success"
    assert record["mode"] == "paper_search_mcp_download"
    assert record["upstream"]["tool"] == "download_arxiv"
    assert (paper_root / "paper.pdf").read_bytes().startswith(b"%PDF-1.4")


def test_acquire_paper_from_candidate_uses_vault_slug_boundary(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "paper.pdf").write_bytes(b"%PDF-1.4\norchestrator fixture\n")
    vault = tmp_path / "vault"

    with _LocalServer(server_root) as base_url:
        record = acquire_paper_from_candidate(vault, _candidate(f"{base_url}/paper.pdf"))

    paper_root = vault / "_epi" / "raw" / "papers" / "downloaded-paper"
    assert record["status"] == "success"
    assert record["output_path"] == str(paper_root / "paper.pdf")
    assert (paper_root / "paper.pdf").is_file()


def test_classify_acquire_failure_maps_status_and_kind():
    assert _classify_acquire_failure(403) == (
        "access-denied",
        False,
        "Source denied access; try arXiv/open-access source or a mirror.",
    )
    assert _classify_acquire_failure(401)[0] == "access-denied"
    assert _classify_acquire_failure(404)[0] == "not-found"
    assert _classify_acquire_failure(410)[0] == "not-found"

    rate_limited = _classify_acquire_failure(429)
    assert rate_limited[0] == "rate-limited"
    assert rate_limited[1] is True

    server_error = _classify_acquire_failure(502)
    assert server_error[0] == "server-error"
    assert server_error[1] is True

    network = _classify_acquire_failure(None, "network")
    assert network[0] == "network"
    assert network[1] is True

    empty = _classify_acquire_failure(200, "empty-pdf")
    assert empty[0] == "empty-pdf"
    assert empty[1] is True

    assert _classify_acquire_failure(None, "no-url")[0] == "no-url"
    assert _classify_acquire_failure(None, "already-exists")[0] == "already-exists"
    assert _classify_acquire_failure(None)[0] == "unknown"
