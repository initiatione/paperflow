import json
import os
import threading
import urllib.error
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
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "downloaded-paper"

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
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "missing-paper"

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


def test_acquire_paper_from_url_quarantines_identity_mismatch_before_success(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "wrong.pdf").write_bytes(
        b"%PDF-1.4\nTitle: Wrong Publisher Paper\nDOI: 10.9999/wrong.paper\n"
    )
    vault = tmp_path / "vault"
    paper_root = vault / "_epi" / "raw" / "identity-mismatch-paper"
    candidate = _candidate(None, slug="identity-mismatch-paper")
    candidate["title"] = "Target AUV PINN RL Control Paper"
    candidate["doi"] = "10.1000/target.paper"

    with _LocalServer(server_root) as base_url:
        candidate["pdf_url"] = f"{base_url}/wrong.pdf"
        record = acquire_paper_from_url(candidate, paper_root)

    identity_path = paper_root / "identity-check.json"
    quarantine_pdf = vault / "_epi" / "quarantine" / "papers" / "identity-mismatch-paper" / "paper.pdf"

    assert record["status"] == "failed"
    assert record["failure_class"] == "identity-mismatch"
    assert record["identity_check"]["status"] == "failed"
    assert record["identity_check"]["reason"] == "doi_mismatch"
    assert record["quarantine_path"] == str(quarantine_pdf)
    assert identity_path.is_file()
    assert json.loads(identity_path.read_text(encoding="utf-8"))["status"] == "failed"
    assert quarantine_pdf.read_bytes().startswith(b"%PDF-1.4")
    assert not (paper_root / "paper.pdf").exists()


def test_acquire_paper_from_url_follows_landing_page_citation_pdf_url(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "paper.pdf").write_bytes(b"%PDF-1.4\nresolved landing fixture\n")
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "landing-paper"

    with _LocalServer(server_root) as base_url:
        landing_url = f"{base_url}/article"
        resolved_pdf_url = f"{base_url}/paper.pdf"
        (server_root / "article").write_text(
            f'<html><head><meta name="citation_pdf_url" content="{resolved_pdf_url}"></head></html>',
            encoding="utf-8",
        )

        record = acquire_paper_from_url(_candidate(landing_url, slug="landing-paper"), paper_root)

    assert record["status"] == "success"
    assert record["mode"] == "url"
    assert record["candidate_pdf_url"] == landing_url
    assert record["resolved_pdf_url"] == resolved_pdf_url
    assert record["pdf_url"] == resolved_pdf_url
    assert (paper_root / "paper.pdf").read_bytes().startswith(b"%PDF-1.4")


def test_acquire_paper_from_url_tries_candidate_pdf_url_fallbacks(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfallback fixture\n")
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "fallback-paper"

    with _LocalServer(server_root) as base_url:
        first_url = f"{base_url}/missing.pdf"
        fallback_url = f"{base_url}/paper.pdf"
        candidate = _candidate(first_url, slug="fallback-paper")
        candidate["pdf_urls"] = [first_url, fallback_url]

        record = acquire_paper_from_url(candidate, paper_root)

    assert record["status"] == "success"
    assert record["candidate_pdf_url"] == first_url
    assert record["resolved_pdf_url"] == fallback_url
    assert record["pdf_url"] == fallback_url
    assert record["acquire_attempts"][0]["url"] == first_url
    assert record["acquire_attempts"][0]["status"] == "failed"
    assert record["acquire_attempts"][0]["http_status"] == 404
    assert record["acquire_attempts"][1]["url"] == fallback_url
    assert record["acquire_attempts"][1]["status"] == "success"
    assert (paper_root / "paper.pdf").read_bytes().startswith(b"%PDF-1.4")


def test_acquire_paper_from_url_tries_alternate_pdf_urls_from_deduped_sources(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "alternate.pdf").write_bytes(b"%PDF-1.4\nalternate fixture\n")
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "alternate-url-paper"

    with _LocalServer(server_root) as base_url:
        first_url = f"{base_url}/missing.pdf"
        alternate_url = f"{base_url}/alternate.pdf"
        candidate = _candidate(first_url, slug="alternate-url-paper")
        candidate["pdf_urls"] = [first_url]
        candidate["alternate_pdf_urls"] = [
            {"source": "unpaywall", "url": alternate_url},
            {"source": "crossref", "url": first_url},
        ]

        record = acquire_paper_from_url(candidate, paper_root)

    assert record["status"] == "success"
    assert record["candidate_pdf_urls"] == [first_url, alternate_url]
    assert record["resolved_pdf_url"] == alternate_url
    assert record["acquire_attempts"][0]["url"] == first_url
    assert record["acquire_attempts"][1]["url"] == alternate_url
    assert record["acquire_attempts"][1]["status"] == "success"
    assert (paper_root / "paper.pdf").read_bytes().startswith(b"%PDF-1.4")


def test_acquire_paper_from_url_rejects_html_without_pdf_link(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "html-paper"

    with _LocalServer(server_root) as base_url:
        landing_url = f"{base_url}/article"
        (server_root / "article").write_text("<html><body>publisher landing page</body></html>", encoding="utf-8")

        record = acquire_paper_from_url(_candidate(landing_url, slug="html-paper"), paper_root)

    assert record["status"] == "failed"
    assert record["mode"] == "url"
    assert record["http_status"] == 200
    assert record["failure_class"] == "not-pdf"
    assert record["retryable"] is True
    assert "not a PDF" in record["error"]
    assert not (paper_root / "paper.pdf").exists()


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

    monkeypatch.setattr(
        "epi.acquire_papers.read_paper_preview",
        lambda **kwargs: {
            "status": "skipped",
            "mode": "paper_search_cli_read_preview",
            "authoritative": False,
            "replaces_mineru": False,
            "error": "not under test",
        },
    )

    record = acquire_paper_from_candidate(vault, candidate)

    paper_root = vault / "_epi" / "raw" / "paper-search-cli-paper"
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
    seen_preview = {}

    def _fake_download_paper_pdf(
        *,
        source,
        paper_id,
        output_dir,
        doi="",
        title="",
        use_scihub=False,
        scihub_base_url="https://sci-hub.se",
        stop_after_oa_fallback=False,
        command=None,
        timeout_seconds=120,
    ):
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

    def _fake_read_paper_preview(*, source, paper_id, output_path, save_dir=None, command=None, timeout_seconds=120):
        seen_preview.update(
            {
                "source": source,
                "paper_id": paper_id,
                "output_path": output_path,
                "save_dir": save_dir,
                "timeout_seconds": timeout_seconds,
            }
        )
        output_path.write_text("MCP extracted preview text.\n", encoding="utf-8")
        return {
            "status": "success",
            "mode": "paper_search_mcp_read_preview",
            "source": source,
            "paper_id": paper_id,
            "tool": f"read_{source}_paper",
            "output_path": str(output_path),
            "char_count": len("MCP extracted preview text."),
            "authoritative": False,
            "replaces_mineru": False,
            "mcp_probe": {"available": True, "transport": "stdio"},
        }

    monkeypatch.setattr("epi.acquire_papers.download_paper_pdf", _fake_download_paper_pdf)
    monkeypatch.setattr("epi.acquire_papers.read_paper_preview", _fake_read_paper_preview)
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

    paper_root = vault / "_epi" / "raw" / "paper-search-mcp-paper"
    assert record["status"] == "success"
    assert record["mode"] == "paper_search_mcp_download"
    assert record["upstream"]["tool"] == "download_arxiv"
    assert (paper_root / "paper.pdf").read_bytes().startswith(b"%PDF-1.4")
    assert seen_preview["source"] == "arxiv"
    assert seen_preview["paper_id"] == "2401.12345"
    assert seen_preview["output_path"] == paper_root / "paper-search-read-preview.txt"
    assert seen_preview["save_dir"].name.startswith("epi-paper-search-")
    assert record["retrieval_preview"]["status"] == "success"
    assert record["retrieval_preview"]["output_path"] == str(paper_root / "paper-search-read-preview.txt")
    assert record["retrieval_preview"]["authoritative"] is False
    assert record["retrieval_preview"]["replaces_mineru"] is False
    assert record["output_artifact_hashes"]["paper-search-read-preview.txt"]
    assert (paper_root / "paper-search-read-preview.txt").read_text(encoding="utf-8") == (
        "MCP extracted preview text.\n"
    )


def test_acquire_paper_from_candidate_soft_fails_retrieval_preview(tmp_path, monkeypatch):
    def _fake_download_paper_pdf(
        *,
        source,
        paper_id,
        output_dir,
        doi="",
        title="",
        use_scihub=False,
        scihub_base_url="https://sci-hub.se",
        stop_after_oa_fallback=False,
        command=None,
        timeout_seconds=120,
    ):
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

    def _failing_read_paper_preview(**kwargs):
        raise RuntimeError("preview extraction crashed")

    monkeypatch.setattr("epi.acquire_papers.download_paper_pdf", _fake_download_paper_pdf)
    monkeypatch.setattr("epi.acquire_papers.read_paper_preview", _failing_read_paper_preview)
    candidate = _candidate("https://example.org/fallback.pdf", slug="preview-soft-fail-paper")
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

    paper_root = vault / "_epi" / "raw" / "preview-soft-fail-paper"
    assert record["status"] == "success"
    assert record["retrieval_preview"]["status"] == "failed"
    assert record["retrieval_preview"]["error"] == "preview extraction crashed"
    assert record["retrieval_preview"]["authoritative"] is False
    assert record["retrieval_preview"]["replaces_mineru"] is False
    assert "paper-search-read-preview.txt" not in record["output_artifact_hashes"]
    assert (paper_root / "paper.pdf").read_bytes().startswith(b"%PDF-1.4")
    assert not (paper_root / "paper-search-read-preview.txt").exists()


def test_acquire_paper_from_candidate_uses_oa_identity_and_fallback_metadata(tmp_path, monkeypatch):
    seen = {}

    def _fake_download_paper_pdf(
        *,
        source,
        paper_id,
        output_dir,
        doi="",
        title="",
        use_scihub=False,
        scihub_base_url="https://sci-hub.se",
        stop_after_oa_fallback=False,
        command=None,
        timeout_seconds=120,
    ):
        seen.update(
            {
                "source": source,
                "paper_id": paper_id,
                "doi": doi,
                "title": title,
                "use_scihub": use_scihub,
                "scihub_base_url": scihub_base_url,
                "stop_after_oa_fallback": stop_after_oa_fallback,
            }
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / "fallback.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fallback acquire fixture")
        return {
            "status": "success",
            "mode": "paper_search_mcp_fallback_download",
            "source": source,
            "paper_id": paper_id,
            "doi": doi,
            "title": title,
            "use_scihub": use_scihub,
            "mcp_probe": {"available": True, "transport": "stdio"},
            "downloaded_pdf": str(pdf_path),
            "upstream": {
                "package": "paper-search-mcp",
                "transport": "stdio",
                "tool": "download_with_fallback",
                "fallback_chain": ["source-native", "openaire", "core", "europepmc", "pmc", "unpaywall"],
                "use_scihub": use_scihub,
            },
        }

    monkeypatch.setattr("epi.acquire_papers.download_paper_pdf", _fake_download_paper_pdf)
    candidate = _candidate("https://doi.org/10.1000/downloaded", slug="oa-priority-paper")
    candidate["title"] = "OA Priority Paper"
    candidate["doi"] = "10.1000/downloaded"
    candidate["sources"] = ["semantic", "arxiv"]
    candidate["raw_records"] = [
        {
            "source": "semantic",
            "paper_id": "semantic-123",
            "raw_record": {"paper_id": "semantic-123", "source": "semantic"},
        },
        {
            "source": "arxiv",
            "arxiv_id": "2401.12345",
            "raw_record": {"paper_id": "2401.12345", "source": "arxiv"},
        },
    ]
    vault = tmp_path / "vault"

    monkeypatch.setattr(
        "epi.acquire_papers.read_paper_preview",
        lambda **kwargs: {
            "status": "skipped",
            "mode": "paper_search_cli_read_preview",
            "authoritative": False,
            "replaces_mineru": False,
            "error": "not under test",
        },
    )

    record = acquire_paper_from_candidate(vault, candidate)

    assert seen == {
        "source": "arxiv",
        "paper_id": "2401.12345",
        "doi": "10.1000/downloaded",
        "title": "OA Priority Paper",
        "use_scihub": False,
        "scihub_base_url": "https://sci-hub.se",
        "stop_after_oa_fallback": False,
    }
    assert record["status"] == "success"
    assert record["mode"] == "paper_search_mcp_fallback_download"
    assert record["fallback_chain"] == ["source-native", "openaire", "core", "europepmc", "pmc", "unpaywall"]
    assert record["use_scihub"] is False
    assert record["doi"] == "10.1000/downloaded"
    assert record["title"] == "OA Priority Paper"


def test_acquire_paper_from_candidate_records_manual_download_when_oa_fallback_has_no_pdf(tmp_path, monkeypatch):
    seen = {}

    def _fake_download_paper_pdf(
        *,
        source,
        paper_id,
        output_dir,
        doi="",
        title="",
        use_scihub=False,
        scihub_base_url="https://sci-hub.se",
        stop_after_oa_fallback=False,
        command=None,
        timeout_seconds=120,
    ):
        seen.update(
            {
                "source": source,
                "paper_id": paper_id,
                "doi": doi,
                "title": title,
                "use_scihub": use_scihub,
                "stop_after_oa_fallback": stop_after_oa_fallback,
            }
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "failed",
            "mode": "paper_search_mcp_fallback_download",
            "source": source,
            "paper_id": paper_id,
            "doi": doi,
            "title": title,
            "mcp_probe": {"available": True, "transport": "stdio"},
            "mcp_server_probe": {
                "available": False,
                "transport": "stdio",
                "error": "no OA URL found",
                "fallback_chain": ["source-native", "openaire", "core", "europepmc", "pmc", "unpaywall"],
            },
            "upstream": {
                "package": "paper-search-mcp",
                "transport": "stdio",
                "tool": "download_with_fallback",
                "fallback_chain": ["source-native", "openaire", "core", "europepmc", "pmc", "unpaywall"],
                "use_scihub": False,
            },
            "error": "Download failed after OA fallback chain: no OA URL found",
        }

    monkeypatch.setattr("epi.acquire_papers.download_paper_pdf", _fake_download_paper_pdf)
    candidate = _candidate(None, slug="manual-download-paper")
    candidate["title"] = "Publisher Only AUV PINN RL Paper"
    candidate["doi"] = "10.1016/j.oceaneng.2024.119432"
    candidate["url"] = "https://www.sciencedirect.com/science/article/abs/pii/S0029801824027707"
    candidate["sources"] = ["semantic", "crossref"]
    candidate["raw_records"] = [
        {
            "source": "semantic",
            "paper_id": "semantic-123",
            "raw_record": {
                "paper_id": "semantic-123",
                "source": "semantic",
                "url": "https://www.sciencedirect.com/science/article/abs/pii/S0029801824027707",
            },
        }
    ]
    vault = tmp_path / "vault"

    record = acquire_paper_from_candidate(vault, candidate)

    assert seen == {
        "source": "semantic",
        "paper_id": "semantic-123",
        "doi": "10.1016/j.oceaneng.2024.119432",
        "title": "Publisher Only AUV PINN RL Paper",
        "use_scihub": False,
        "stop_after_oa_fallback": True,
    }
    assert record["status"] == "failed"
    assert record["failure_class"] == "manual-download-required"
    assert record["retryable"] is False
    assert "organization/institution" in record["recovery_hint"]
    assert record["manual_download"]["required"] is True
    assert record["manual_download"]["doi"] == "10.1016/j.oceaneng.2024.119432"
    assert record["manual_download"]["doi_url"] == "https://doi.org/10.1016/j.oceaneng.2024.119432"
    assert record["manual_download"]["preferred_next_step"].startswith("Download the PDF through your organization")
    assert {
        "kind": "publisher",
        "url": "https://www.sciencedirect.com/science/article/abs/pii/S0029801824027707",
    } in record["manual_download"]["candidate_manual_urls"]
    assert record["mcp_server_probe"]["error"] == "no OA URL found"
    assert record["upstream"]["tool"] == "download_with_fallback"
    assert not (vault / "_epi" / "raw" / "manual-download-paper" / "paper.pdf").exists()


def test_acquire_paper_from_url_attaches_manual_download_links_on_access_denied(tmp_path, monkeypatch):
    paper_root = tmp_path / "vault" / "_epi" / "raw" / "publisher-blocked-paper"
    candidate = _candidate("https://publisher.example/article.pdf", slug="publisher-blocked-paper")
    candidate["doi"] = "10.5555/publisher.blocked"
    candidate["url"] = "https://publisher.example/article"

    def _blocked_download(url, temp_pdf, timeout_seconds):
        raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("epi.acquire_papers._download_url_to_temp", _blocked_download)

    record = acquire_paper_from_url(candidate, paper_root)

    assert record["status"] == "failed"
    assert record["failure_class"] == "manual-download-required"
    assert record["manual_download"]["required"] is True
    assert record["manual_download"]["doi_url"] == "https://doi.org/10.5555/publisher.blocked"
    assert {
        "kind": "publisher",
        "url": "https://publisher.example/article",
    } in record["manual_download"]["candidate_manual_urls"]


def test_acquire_paper_from_candidate_uses_vault_slug_boundary(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "paper.pdf").write_bytes(b"%PDF-1.4\norchestrator fixture\n")
    vault = tmp_path / "vault"

    with _LocalServer(server_root) as base_url:
        record = acquire_paper_from_candidate(vault, _candidate(f"{base_url}/paper.pdf"))

    paper_root = vault / "_epi" / "raw" / "downloaded-paper"
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
