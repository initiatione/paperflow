import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
import requests

from paper_source.orchestrator import parse_paper_with_mineru
from paper_source.run_mineru_parse import _vault_path_from_paper_root, run_mineru_command

ROOT = Path(__file__).resolve().parents[2]


def _load_mineru_batch_module():
    script = ROOT / "plugins" / "paper-source" / "build" / "mineru-paper-parser" / "mineru_batch_to_md.py"
    spec = importlib.util.spec_from_file_location("paper_source_mineru_batch_to_md_under_test", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _mineru_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", "# Parsed Paper\n")
        archive.writestr("images/figure-1.png", b"PNG")
    return buffer.getvalue()


def _response(status_code=200, content=b""):
    response = requests.Response()
    response.status_code = status_code
    response._content = content
    return response


def _seed_paper_root(tmp_path, slug="paper"):
    paper_root = tmp_path / "vault" / "_paper_source" / "raw" / slug
    paper_root.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    return paper_root


def _write_success_command(tmp_path):
    script = tmp_path / "fake_mineru_success.py"
    script.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project-root", required=True)
parser.add_argument("--input-dir", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--layout", default="document-dir")
args = parser.parse_args()

project_root = Path(args.project_root)
output_root = project_root / args.output_dir
document_dir = output_root / "paper"
images_dir = document_dir / "images"
images_dir.mkdir(parents=True, exist_ok=True)
(document_dir / "paper.md").write_text("# Parsed Paper\\n\\nEvidence from MinerU.\\n", encoding="utf-8")
(document_dir / "paper.tex").write_text("\\\\section{Parsed Paper}\\n", encoding="utf-8")
(images_dir / "figure-1.png").write_bytes(b"PNG")
manifest = {
    "batch_id": "fake-batch-001",
    "outputs": [
        {
            "file_name": "paper.pdf",
            "state": "done",
            "document_dir": "parsed/paper",
            "markdown_path": "parsed/paper/paper.md",
            "image_count": 1,
            "image_dir": "parsed/paper/images",
        }
    ],
}
(output_root / "mineru_batch_fake-batch-001.json").write_text(json.dumps(manifest), encoding="utf-8")
print("batch_id: fake-batch-001")
""".strip(),
        encoding="utf-8",
    )
    return script


def _write_markdown_only_success_command(tmp_path):
    script = tmp_path / "fake_mineru_markdown_only.py"
    script.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project-root", required=True)
parser.add_argument("--input-dir", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--layout", default="document-dir")
args = parser.parse_args()

project_root = Path(args.project_root)
output_root = project_root / args.output_dir
document_dir = output_root / "paper"
images_dir = document_dir / "images"
images_dir.mkdir(parents=True, exist_ok=True)
(document_dir / "paper.md").write_text("# Parsed Paper\\n\\nEvidence from Markdown-only MinerU.\\n", encoding="utf-8")
(images_dir / "figure-1.png").write_bytes(b"PNG")
manifest = {
    "batch_id": "fake-batch-md-only",
    "outputs": [
        {
            "file_name": "paper.pdf",
            "state": "done",
            "document_dir": "parsed/paper",
            "markdown_path": "parsed/paper/paper.md",
            "image_count": 1,
            "image_dir": "parsed/paper/images",
        }
    ],
}
(output_root / "mineru_batch_fake-batch-md-only.json").write_text(json.dumps(manifest), encoding="utf-8")
print("batch_id: fake-batch-md-only")
""".strip(),
        encoding="utf-8",
    )
    return script


def _write_failure_command(tmp_path):
    script = tmp_path / "fake_mineru_failure.py"
    script.write_text(
        """
import sys

print("simulated mineru failure", file=sys.stderr)
raise SystemExit(7)
""".strip(),
        encoding="utf-8",
    )
    return script


def _write_done_without_markdown_command(tmp_path):
    script = tmp_path / "fake_mineru_done_without_markdown.py"
    script.write_text(
        """
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project-root", required=True)
parser.add_argument("--input-dir", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--layout", default="document-dir")
args = parser.parse_args()

output_root = Path(args.project_root) / args.output_dir
(output_root / "paper").mkdir(parents=True, exist_ok=True)
print("batch_id: done-no-markdown")
print("batch done-no-markdown: paper.pdf:done")
raise SystemExit(1)
""".strip(),
        encoding="utf-8",
    )
    return script


def test_mineru_zip_download_uses_configured_host_ip_override_after_tls_failure(tmp_path, monkeypatch):
    module = _load_mineru_batch_module()
    monkeypatch.setenv(module.MINERU_CDN_RESOLVE_ENV, "cdn-mineru.openxlab.org.cn=47.251.5.11")
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    def fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return [(module.socket.AF_INET, module.socket.SOCK_STREAM, 6, "", (str(host), port))]

    seen_addresses = []

    def fake_get(url, timeout):
        seen_addresses.append(module.socket.getaddrinfo("cdn-mineru.openxlab.org.cn", 443)[0][4][0])
        if len(seen_addresses) == 1:
            raise module.RequestException("SSL EOF")
        return _response(content=_mineru_zip_bytes())

    monkeypatch.setattr(module.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(module.requests, "get", fake_get)

    md_bytes, image_count, recovery = module.download_markdown_and_assets_with_recovery(
        "https://cdn-mineru.openxlab.org.cn/pdf/fixture.zip",
        tmp_path,
        extract_images=True,
    )

    assert md_bytes == b"# Parsed Paper\n"
    assert image_count == 1
    assert seen_addresses == ["cdn-mineru.openxlab.org.cn", "47.251.5.11"]
    assert recovery == {
        "mode": "host-ip-override",
        "host": "cdn-mineru.openxlab.org.cn",
        "ip": "47.251.5.11",
        "attempt": 1,
        "env": module.MINERU_CDN_RESOLVE_ENV,
    }


def test_mineru_zip_download_ignores_unrelated_or_invalid_host_ip_override(tmp_path, monkeypatch):
    module = _load_mineru_batch_module()
    monkeypatch.setenv(
        module.MINERU_CDN_RESOLVE_ENV,
        "other.example=47.251.5.11;cdn-mineru.openxlab.org.cn=not-an-ip",
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        raise module.RequestException("SSL EOF")

    monkeypatch.setattr(module.requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="download zip failed after 3 attempts: SSL EOF"):
        module.download_markdown_and_assets_with_recovery(
            "https://cdn-mineru.openxlab.org.cn/pdf/fixture.zip",
            tmp_path,
            extract_images=True,
        )

    assert calls == ["https://cdn-mineru.openxlab.org.cn/pdf/fixture.zip"] * 3


def test_mineru_batch_manifest_records_download_recovery_metadata(tmp_path, monkeypatch):
    module = _load_mineru_batch_module()
    recovery = {
        "mode": "host-ip-override",
        "host": "cdn-mineru.openxlab.org.cn",
        "ip": "47.251.5.11",
        "attempt": 1,
        "env": module.MINERU_CDN_RESOLVE_ENV,
    }
    monkeypatch.setenv("MINERU_TOKEN", "token")
    monkeypatch.setattr(
        module,
        "poll_batch",
        lambda token, batch_id, timeout, interval: [
            {
                "file_name": "paper.pdf",
                "data_id": "paper",
                "state": "done",
                "full_zip_url": "https://cdn-mineru.openxlab.org.cn/pdf/fixture.zip",
            }
        ],
    )
    monkeypatch.setattr(
        module,
        "download_markdown_and_assets_with_recovery",
        lambda zip_url, asset_root, extract_images: (b"# Parsed Paper\n", 0, recovery),
    )
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "mineru_batch_to_md.py",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            "parsed",
            "--batch-id",
            "batch-with-recovery",
        ],
    )

    assert module.main() == 0

    manifest = json.loads((tmp_path / "parsed" / "mineru_batch_batch-with-recovery.json").read_text(encoding="utf-8"))
    assert manifest["outputs"][0]["download_recovery"] == recovery
    assert (tmp_path / "parsed" / "paper" / "paper.md").read_bytes() == b"# Parsed Paper\n"


def _write_download_failed_manifest_command(tmp_path):
    script = tmp_path / "fake_mineru_download_failed_manifest.py"
    script.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project-root", required=True)
parser.add_argument("--input-dir", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--layout", default="document-dir")
args = parser.parse_args()

output_root = Path(args.project_root) / args.output_dir
output_root.mkdir(parents=True, exist_ok=True)
manifest = {
    "batch_id": "zip-download-failed",
    "outputs": [
        {
            "file_name": "paper.pdf",
            "state": "download_failed",
            "err_msg": "download zip failed after 3 attempts: SSL EOF",
            "full_zip_url": "https://cdn-mineru.example/paper.zip",
        }
    ],
}
(output_root / "mineru_batch_zip-download-failed.json").write_text(json.dumps(manifest), encoding="utf-8")
print("batch_id: zip-download-failed")
print("batch zip-download-failed: paper.pdf:done")
raise SystemExit(1)
""".strip(),
        encoding="utf-8",
    )
    return script


def test_mineru_command_imports_markdown_images_manifest_and_records_job(tmp_path):
    paper_root = _seed_paper_root(tmp_path, slug="fixture-paper")
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    assert record["stage"] == "parse"
    assert record["mode"] == "mineru-command"
    assert record["status"] == "success"
    assert record["exit_code"] == 0
    assert record["exit_status"] == 0
    assert record["started_at"]
    assert record["finished_at"]
    assert record["batch_id"] == "fake-batch-001"
    assert record["input_artifact_hashes"]["paper.pdf"]
    assert record["output_artifact_hashes"]["fixture-paper.md"]
    assert "paper.md" not in record["output_artifact_hashes"]
    assert record["output_artifact_hashes"]["paper.tex"]
    assert record["output_artifact_hashes"]["mineru-manifest.json"]
    assert record["tex_source"] == "mineru-native"
    assert record["markdown_path"] == str(paper_root / "mineru" / "fixture-paper.md")
    assert record["tex_path"] == str(paper_root / "mineru" / "paper.tex")
    assert record["image_count"] == 1
    assert (paper_root / "mineru" / "fixture-paper.md").read_text(encoding="utf-8").startswith("# Parsed Paper")
    assert not (paper_root / "mineru" / "paper.md").exists()
    assert (paper_root / "mineru" / "paper.tex").read_text(encoding="utf-8").startswith("\\section")
    assert (paper_root / "mineru" / "images" / "figure-1.png").read_bytes() == b"PNG"
    assert json.loads((paper_root / "mineru" / "mineru-manifest.json").read_text(encoding="utf-8"))["batch_id"] == (
        "fake-batch-001"
    )
    assert "batch_id: fake-batch-001" in (paper_root / "mineru-command" / "stdout.txt").read_text(encoding="utf-8")
    assert json.loads((paper_root / "parse-record.json").read_text(encoding="utf-8")) == record


def test_mineru_command_keeps_single_canonical_slug_markdown(tmp_path):
    paper_root = _seed_paper_root(tmp_path, slug="fixture-paper")
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    markdown_files = sorted(path.name for path in (paper_root / "mineru").glob("*.md"))
    assert markdown_files == ["fixture-paper.md"]
    assert record["markdown_path"] == str(paper_root / "mineru" / "fixture-paper.md")
    assert "fixture-paper.md" in record["output_artifact_hashes"]
    assert "paper.md" not in record["output_artifact_hashes"]
    assert not (paper_root / "mineru" / "paper.md").exists()


def test_mineru_command_pauses_tex_fallback_and_removes_success_work_copies(tmp_path):
    paper_root = _seed_paper_root(tmp_path)
    stale_tex = paper_root / "mineru" / "paper.tex"
    stale_tex.parent.mkdir(parents=True)
    stale_tex.write_text("\\section{Stale fallback}\n", encoding="utf-8")
    command = [sys.executable, str(_write_markdown_only_success_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    assert record["status"] == "success"
    assert record["tex_source"] == "paused-no-native-tex"
    assert record["tex_path"] is None
    assert "paper.tex" not in record["output_artifact_hashes"]
    assert record["work_dir_retention"] == "logs-only"
    assert not (paper_root / "mineru" / "paper.tex").exists()
    assert not (paper_root / "mineru-command" / "paper").exists()
    assert not (paper_root / "mineru-command" / "parsed").exists()
    assert (paper_root / "mineru-command" / "stdout.txt").is_file()
    assert (paper_root / "mineru-command" / "stderr.txt").is_file()
    assert (paper_root / "mineru" / "images" / "figure-1.png").read_bytes() == b"PNG"


def test_mineru_command_accepts_windows_command_string(tmp_path):
    paper_root = _seed_paper_root(tmp_path)
    command = f"{sys.executable} {_write_success_command(tmp_path)}"

    record = run_mineru_command(paper_root, command=command)

    assert record["status"] == "success"
    assert record["batch_id"] == "fake-batch-001"


def test_mineru_command_failure_records_error_without_fake_markdown(tmp_path):
    paper_root = _seed_paper_root(tmp_path)
    command = [sys.executable, str(_write_failure_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    assert record["stage"] == "parse"
    assert record["mode"] == "mineru-command"
    assert record["status"] == "failed"
    assert record["exit_code"] == 7
    assert record["exit_status"] == 1
    assert record["started_at"]
    assert record["finished_at"]
    assert record["input_artifact_hashes"]["paper.pdf"]
    assert "MinerU command failed" in record["error"]
    assert not (paper_root / "mineru" / "paper.md").exists()
    assert "simulated mineru failure" in (paper_root / "mineru-command" / "stderr.txt").read_text(encoding="utf-8")
    assert json.loads((paper_root / "parse-record.json").read_text(encoding="utf-8")) == record


def test_mineru_command_reports_done_without_markdown_as_missing_output(tmp_path):
    paper_root = _seed_paper_root(tmp_path)
    command = [sys.executable, str(_write_done_without_markdown_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    assert record["status"] == "failed"
    assert record["exit_code"] == 1
    assert record["error"] == "MinerU reported done but produced no Markdown output"
    assert record["batch_id"] == "done-no-markdown"
    assert "batch done-no-markdown: paper.pdf:done" in (
        paper_root / "mineru-command" / "stdout.txt"
    ).read_text(encoding="utf-8")
    assert not (paper_root / "mineru" / "paper.md").exists()


def test_mineru_command_surfaces_manifest_download_failure(tmp_path):
    paper_root = _seed_paper_root(tmp_path)
    command = [sys.executable, str(_write_download_failed_manifest_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    assert record["status"] == "failed"
    assert record["batch_id"] == "zip-download-failed"
    assert record["error"].startswith("MinerU output download failed:")
    assert "paper.pdf:download_failed: download zip failed after 3 attempts: SSL EOF" in record["error"]
    assert not (paper_root / "mineru" / "paper.md").exists()


def test_parse_paper_with_mineru_uses_vault_slug_boundary(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = vault / "_paper_source" / "raw" / slug
    paper_root.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = parse_paper_with_mineru(vault, slug, mineru_command=command)

    assert record["status"] == "success"
    assert record["batch_id"] == "fake-batch-001"
    assert (paper_root / "mineru" / f"{slug}.md").is_file()
    assert not (paper_root / "mineru" / "paper.md").exists()


def test_vault_path_from_paper_root_does_not_accept_retired_epi_root(tmp_path):
    vault = tmp_path / "vault"

    assert _vault_path_from_paper_root(vault / "_paper_source" / "raw" / "paper-a") == vault.resolve()
    assert _vault_path_from_paper_root(vault / "_epi" / "raw" / "paper-a") is None


def test_mineru_command_success_writes_evidence_index_and_aggregate(tmp_path):
    paper_root = _seed_paper_root(tmp_path, slug="fixture-paper")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": "fixture-paper", "title": "Fixture Paper", "doi": "10.1000/fixture"}),
        encoding="utf-8",
    )
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    evidence_index = json.loads((paper_root / "evidence-index.json").read_text(encoding="utf-8"))
    aggregate = json.loads((tmp_path / "vault" / "_paper_source" / "meta" / "evidence-index.json").read_text(encoding="utf-8"))
    assert record["evidence_index"]["path"] == str(paper_root / "evidence-index.json")
    assert record["evidence_index"]["chunk_count"] >= 1
    assert evidence_index["paper_slug"] == "fixture-paper"
    assert aggregate["papers"][0]["paper_slug"] == "fixture-paper"


def test_parse_paper_with_mineru_writes_evidence_index(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = vault / "_paper_source" / "raw" / slug
    paper_root.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper"}),
        encoding="utf-8",
    )
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = parse_paper_with_mineru(vault, slug, mineru_command=command)

    assert record["status"] == "success"
    assert (paper_root / "evidence-index.json").is_file()
    assert (vault / "_paper_source" / "meta" / "evidence-index.json").is_file()


def test_resolve_mineru_timeout_prefers_param_then_env_then_default(monkeypatch):
    from paper_source.run_mineru_parse import _resolve_mineru_timeout

    monkeypatch.delenv("PAPER_SOURCE_MINERU_TIMEOUT", raising=False)
    assert _resolve_mineru_timeout(None) == 7200
    assert _resolve_mineru_timeout(120) == 120

    monkeypatch.setenv("PAPER_SOURCE_MINERU_TIMEOUT", "300")
    assert _resolve_mineru_timeout(None) == 300
    # explicit positive param overrides the environment
    assert _resolve_mineru_timeout(120) == 120

    # invalid / non-positive env values fall back to the default
    monkeypatch.setenv("PAPER_SOURCE_MINERU_TIMEOUT", "not-a-number")
    assert _resolve_mineru_timeout(None) == 7200
    monkeypatch.setenv("PAPER_SOURCE_MINERU_TIMEOUT", "0")
    assert _resolve_mineru_timeout(None) == 7200
    # booleans are not valid timeouts
    monkeypatch.delenv("PAPER_SOURCE_MINERU_TIMEOUT", raising=False)
    assert _resolve_mineru_timeout(True) == 7200


def test_resolve_mineru_timeout_ignores_old_alias_env(monkeypatch):
    from paper_source.run_mineru_parse import _resolve_mineru_timeout

    monkeypatch.delenv("PAPER_SOURCE_MINERU_TIMEOUT", raising=False)
    monkeypatch.setenv("EPI_MINERU_TIMEOUT", "300")
    assert _resolve_mineru_timeout(None) == 7200

    monkeypatch.setenv("PAPER_SOURCE_MINERU_TIMEOUT", "180")
    assert _resolve_mineru_timeout(None) == 180

    monkeypatch.delenv("PAPER_SOURCE_MINERU_TIMEOUT", raising=False)
    monkeypatch.delenv("EPI_MINERU_TIMEOUT", raising=False)


def _write_sleeping_command(tmp_path):
    script = tmp_path / "fake_mineru_sleep.py"
    script.write_text("import time\ntime.sleep(15)\n", encoding="utf-8")
    return script


def test_mineru_command_times_out_with_explicit_timeout(tmp_path):
    paper_root = _seed_paper_root(tmp_path)
    command = [sys.executable, str(_write_sleeping_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command, timeout_seconds=1)

    assert record["status"] == "failed"
    assert record["error"] == "MinerU command timed out after 1 seconds"
    assert json.loads((paper_root / "parse-record.json").read_text(encoding="utf-8"))["status"] == "failed"


def test_mineru_command_times_out_using_env_timeout(tmp_path, monkeypatch):
    paper_root = _seed_paper_root(tmp_path)
    command = [sys.executable, str(_write_sleeping_command(tmp_path))]
    monkeypatch.setenv("PAPER_SOURCE_MINERU_TIMEOUT", "1")

    record = run_mineru_command(paper_root, command=command)

    assert record["status"] == "failed"
    assert record["error"] == "MinerU command timed out after 1 seconds"
