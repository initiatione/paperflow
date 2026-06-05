import json
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from epi.orchestrator import advance_paper_batch_from_run, run_dry_run


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


def _write_fake_mineru_command(tmp_path):
    script = tmp_path / "fake_mineru_e2e.py"
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
(document_dir / "paper.md").write_text(
    "# Abstract\\n\\n"
    "This paper presents embodied navigation control for mobile robots with code, dataset, model, config, simulator, and hardware references.\\n\\n"
    "## Method\\n\\n"
    "The controller combines perception, planning, and feedback control for robotics navigation.\\n\\n"
    "## Results\\n\\n"
    "The method outperforms prior baselines by 12% on a navigation benchmark with a reward metric.\\n",
    encoding="utf-8",
)
manifest = {
    "batch_id": "e2e-fixture-001",
    "outputs": [
        {
            "file_name": "paper.pdf",
            "state": "done",
            "markdown_path": "parsed/paper/paper.md",
            "image_count": 0,
        }
    ],
}
(output_root / "mineru_batch_e2e-fixture-001.json").write_text(json.dumps(manifest), encoding="utf-8")
print("batch_id: e2e-fixture-001")
""".strip(),
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


def test_dry_run_to_critic_decision_e2e_fixture_updates_reports_index_and_dashboard(tmp_path):
    plugin_root = tmp_path / "plugin"
    vault = tmp_path / "vault"
    server_root = tmp_path / "server"
    fixture = tmp_path / "fixture.json"
    server_root.mkdir()
    _write_minimal_plugin_template(plugin_root)
    mineru_command = _write_fake_mineru_command(tmp_path)
    (server_root / "nav.pdf").write_bytes(b"%PDF-1.4\nnavigation fixture\n")

    with _LocalServer(server_root) as base_url:
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
                        "pdf_url": f"{base_url}/nav.pdf",
                        "doi": "10.1000/e2e-nav",
                        "citation_count": 50,
                        "code_url": "https://github.com/example/e2e-nav",
                    }
                ]
            ),
            encoding="utf-8",
        )

        dry_run_dir = run_dry_run(
            plugin_root=plugin_root,
            vault_path=vault,
            query="robotics embodied navigation control benchmark",
            max_results=5,
            fixture_path=fixture,
        )

        stage_results = [
            advance_paper_batch_from_run(
                vault,
                dry_run_dir.name,
                mineru_command=mineru_command,
                max_papers=1,
                workflow_mode="audited-ingest",
            )
            for _ in range(4)
        ]

    slug = "embodied-navigation-control-benchmark-for-mobile-robots"
    final_batch = stage_results[-1]
    final_run_dir = vault / "_epi" / "runs" / final_batch["run_id"]
    paper_root = vault / "_epi" / "raw" / slug
    decision = json.loads((paper_root / "critic" / "research-decision.json").read_text(encoding="utf-8"))
    report_json = json.loads((final_run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (final_run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((vault / "_epi" / "runs" / "index.json").read_text(encoding="utf-8"))
    dashboard_text = (vault / "_epi" / "runs" / "dashboard.md").read_text(encoding="utf-8")

    assert [batch["results"][0]["last_action"] for batch in stage_results] == [
        "acquire",
        "parse",
        "read",
        "critic",
    ]
    assert final_batch["results"][0]["state"] == "critic_passed"
    assert final_batch["results"][0]["next_action"] == "staging"
    assert decision["recommendation"] == "stage-for-promotion-review"
    assert decision["next_action"] == "stage"
    assert decision["role_verdicts"] == {
        "nature-sci-editor": "pass",
        "peer-reviewer": "pass",
        "senior-domain-researcher": "pass",
    }
    assert [item["action"] for item in decision["action_items"]] == ["preserve", "preserve", "preserve"]
    assert report_json["research_decisions"][0]["slug"] == slug
    assert report_json["research_decisions"][0]["recommendation"] == "stage-for-promotion-review"
    assert "## Research Decisions" in report_md
    assert "nature-sci-editor: pass" in report_md
    assert "peer-reviewer: pass" in report_md
    assert "senior-domain-researcher: pass" in report_md
    assert index_payload["runs"][0]["research_decisions"][0]["slug"] == slug
    assert f"decision: {slug} -> stage-for-promotion-review / stage" in dashboard_text
    assert not (vault / "references" / f"{slug}.md").exists()
