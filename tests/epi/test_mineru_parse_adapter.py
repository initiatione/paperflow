import json
import sys

from epi.orchestrator import parse_paper_with_mineru
from epi.run_mineru_parse import run_mineru_command


def _seed_paper_root(tmp_path, slug="paper"):
    paper_root = tmp_path / "vault" / "_epi" / "raw" / slug
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


def test_mineru_command_generates_tex_fallback_and_removes_success_work_copies(tmp_path):
    paper_root = _seed_paper_root(tmp_path)
    command = [sys.executable, str(_write_markdown_only_success_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    tex_path = paper_root / "mineru" / "paper.tex"
    tex_text = tex_path.read_text(encoding="utf-8")
    assert record["status"] == "success"
    assert record["tex_source"] == "markdown-fallback"
    assert record["work_dir_retention"] == "logs-only"
    assert "\\section{Parsed Paper}" in tex_text
    assert "Evidence from Markdown-only MinerU" in tex_text
    assert tex_path.stat().st_size > 0
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


def test_parse_paper_with_mineru_uses_vault_slug_boundary(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = vault / "_epi" / "raw" / slug
    paper_root.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = parse_paper_with_mineru(vault, slug, mineru_command=command)

    assert record["status"] == "success"
    assert record["batch_id"] == "fake-batch-001"
    assert (paper_root / "mineru" / f"{slug}.md").is_file()
    assert not (paper_root / "mineru" / "paper.md").exists()


def test_resolve_mineru_timeout_prefers_param_then_env_then_default(monkeypatch):
    from epi.run_mineru_parse import _resolve_mineru_timeout

    monkeypatch.delenv("EPI_MINERU_TIMEOUT", raising=False)
    assert _resolve_mineru_timeout(None) == 7200
    assert _resolve_mineru_timeout(120) == 120

    monkeypatch.setenv("EPI_MINERU_TIMEOUT", "300")
    assert _resolve_mineru_timeout(None) == 300
    # explicit positive param overrides the environment
    assert _resolve_mineru_timeout(120) == 120

    # invalid / non-positive env values fall back to the default
    monkeypatch.setenv("EPI_MINERU_TIMEOUT", "not-a-number")
    assert _resolve_mineru_timeout(None) == 7200
    monkeypatch.setenv("EPI_MINERU_TIMEOUT", "0")
    assert _resolve_mineru_timeout(None) == 7200
    # booleans are not valid timeouts
    monkeypatch.delenv("EPI_MINERU_TIMEOUT", raising=False)
    assert _resolve_mineru_timeout(True) == 7200


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
    monkeypatch.setenv("EPI_MINERU_TIMEOUT", "1")

    record = run_mineru_command(paper_root, command=command)

    assert record["status"] == "failed"
    assert record["error"] == "MinerU command timed out after 1 seconds"
