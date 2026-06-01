import json
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from epi.orchestrator import advance_paper_once


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


def _write_success_mineru_command(tmp_path):
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
document_dir.mkdir(parents=True, exist_ok=True)
(document_dir / "paper.md").write_text("# Parsed Paper\\n\\nThis paper has routed evidence.\\n", encoding="utf-8")
manifest = {
    "batch_id": "advance-batch-001",
    "outputs": [
        {
            "file_name": "paper.pdf",
            "state": "done",
            "markdown_path": "parsed/paper/paper.md",
            "image_count": 0,
        }
    ],
}
(output_root / "mineru_batch_advance-batch-001.json").write_text(json.dumps(manifest), encoding="utf-8")
print("batch_id: advance-batch-001")
""".strip(),
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


def _candidate(pdf_url):
    return {
        "slug": "routed-paper",
        "title": "Routed Paper",
        "authors": ["A. Router"],
        "year": 2026,
        "venue": "ICRA",
        "doi": "10.1000/routed",
        "pdf_url": pdf_url,
        "score": 0.8,
        "sources": ["local-http"],
    }


def test_advance_paper_once_routes_one_safe_stage_at_a_time(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "paper.pdf").write_bytes(b"%PDF-1.4\nrouter fixture\n")
    vault = tmp_path / "vault"
    mineru_command = _write_success_mineru_command(tmp_path)

    with _LocalServer(server_root) as base_url:
        candidate = _candidate(f"{base_url}/paper.pdf")
        records = [
            advance_paper_once(vault, candidate, mineru_command=mineru_command),
            advance_paper_once(vault, candidate, mineru_command=mineru_command),
            advance_paper_once(vault, candidate, mineru_command=mineru_command),
            advance_paper_once(vault, candidate, mineru_command=mineru_command),
            advance_paper_once(vault, candidate, mineru_command=mineru_command),
            advance_paper_once(vault, candidate, mineru_command=mineru_command),
        ]

    assert [record["last_action"] for record in records] == [
        "acquire",
        "parse",
        "read",
        "critic",
        "staging",
        "awaiting-wiki-ingest",
    ]
    assert [record["state"] for record in records] == [
        "acquired",
        "parsed",
        "read",
        "critic_passed",
        "staged",
        "staged",
    ]
    assert records[-1]["next_action"] == "run-wiki-ingest-agent"
    assert records[-1]["human_gate_required"] is True

    paper_root = vault / "_epi" / "raw" / "papers" / "routed-paper"
    assert (paper_root / "paper.pdf").is_file()
    assert (paper_root / "mineru" / "routed-paper.md").is_file()
    assert not (paper_root / "mineru" / "paper.md").exists()
    assert (paper_root / "reader" / "reader.md").is_file()
    assert (paper_root / "critic" / "critic-report.json").is_file()
    assert (vault / "_epi" / "staging" / "papers" / "routed-paper" / "promotion-plan.json").is_file()
    assert not (vault / "references" / "routed-paper.md").exists()

    run_state = json.loads((paper_root / "run-state.json").read_text(encoding="utf-8"))
    assert run_state == records[-1]


def test_advance_paper_once_reparses_incomplete_existing_parse_outputs(tmp_path):
    vault = tmp_path / "vault"
    candidate = _candidate("https://example.org/routed.pdf")
    paper_root = vault / "_epi" / "raw" / "papers" / "routed-paper"
    mineru_root = paper_root / "mineru"
    mineru_root.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nstale parse fixture\n")
    (mineru_root / "paper.md").write_text("# Stale Parse\n", encoding="utf-8")
    (mineru_root / "paper.tex").write_text("\\section{Stale Parse}\n", encoding="utf-8")
    (mineru_root / "mineru-manifest.json").write_text("{}", encoding="utf-8")
    (mineru_root / "images").mkdir()
    (paper_root / "parse-record.json").write_text(
        json.dumps({"stage": "parse", "status": "failed"}), encoding="utf-8"
    )

    record = advance_paper_once(vault, candidate, mineru_command=_write_success_mineru_command(tmp_path))

    assert record["state"] == "parsed"
    assert record["last_action"] == "parse"
    assert json.loads((paper_root / "parse-record.json").read_text(encoding="utf-8"))["status"] == "success"
