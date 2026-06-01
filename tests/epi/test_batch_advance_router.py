import json
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from epi.artifacts import file_sha256, json_sha256
from epi.generate_reader import generate_reader_outputs
from epi.orchestrator import advance_paper_batch, advance_paper_batch_from_run, prepare_ranked_papers_from_run


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
(document_dir / "paper.md").write_text("# Parsed Paper\\n\\nThis paper has batch evidence.\\n", encoding="utf-8")
manifest = {
    "batch_id": "batch-router-001",
    "outputs": [
        {
            "file_name": "paper.pdf",
            "state": "done",
            "markdown_path": "parsed/paper/paper.md",
            "image_count": 0,
        }
    ],
}
(output_root / "mineru_batch_batch-router-001.json").write_text(json.dumps(manifest), encoding="utf-8")
print("batch_id: batch-router-001")
""".strip(),
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


def _candidate(slug, title, pdf_url):
    return {
        "slug": slug,
        "title": title,
        "authors": ["B. Router"],
        "year": 2026,
        "venue": "RSS",
        "doi": f"10.1000/{slug}",
        "pdf_url": pdf_url,
        "score": 0.9,
        "sources": ["local-http"],
    }


def _seed_critic_ready_paper(vault, candidate, *, sources=None):
    paper_root = vault / "_epi" / "raw" / "papers" / candidate["slug"]
    mineru_dir = paper_root / "mineru"
    mineru_dir.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\ncritic ready fixture\n")
    (paper_root / "metadata.json").write_text(
        json.dumps(
            {
                "slug": candidate["slug"],
                "title": candidate["title"],
                "venue": candidate["venue"],
                "year": candidate["year"],
                "doi": candidate["doi"],
                "pdf_url": candidate["pdf_url"],
                "sources": sources or ["code", "dataset", "model", "config", "simulator", "hardware"],
            }
        ),
        encoding="utf-8",
    )
    (mineru_dir / "paper.md").write_text(
        "# Abstract\n\n"
        "This paper presents embodied navigation control for mobile robots.\n\n"
        "## Method\n\n"
        "The method combines perception, planning, and feedback control.\n\n"
        "## Results\n\n"
        "The method is evaluated on a navigation benchmark with a baseline and reward metric.\n",
        encoding="utf-8",
    )
    (mineru_dir / "paper.tex").write_text("\\section{Abstract}\nCritic ready fixture.\n", encoding="utf-8")
    (mineru_dir / "mineru-manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "critic-ready-fixture",
                "outputs": [
                    {
                        "file_name": "paper.pdf",
                        "state": "done",
                        "markdown_path": "parsed/paper/paper.md",
                        "image_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    images_dir = mineru_dir / "images"
    images_dir.mkdir()
    (images_dir / "figure-1.png").write_bytes(b"fake image bytes")
    (paper_root / "parse-record.json").write_text(
        json.dumps({"stage": "parse", "status": "success"}), encoding="utf-8"
    )
    generate_reader_outputs(paper_root)
    return paper_root


def test_advance_paper_batch_routes_candidates_once_and_records_run_state(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "alpha.pdf").write_bytes(b"%PDF-1.4\nalpha fixture\n")
    (server_root / "beta.pdf").write_bytes(b"%PDF-1.4\nbeta fixture\n")
    vault = tmp_path / "vault"
    mineru_command = _write_success_mineru_command(tmp_path)

    with _LocalServer(server_root) as base_url:
        candidates = [
            _candidate("batch-alpha", "Batch Alpha", f"{base_url}/alpha.pdf"),
            _candidate("batch-beta", "Batch Beta", f"{base_url}/beta.pdf"),
        ]
        batch = advance_paper_batch(vault, candidates, mineru_command=mineru_command, max_papers=2)

    assert batch["state"] == "batch_advanced"
    assert batch["processed_count"] == 2
    assert batch["compiled_wiki_write"] is False
    assert batch["started_at"]
    assert batch["finished_at"]
    assert batch["exit_status"] == 0
    assert batch["tool_versions"]["orchestrator"] == "epi-local"
    assert batch["tool_versions"]["advance_paper_batch"] == "epi-local"
    assert batch["input_artifact_hashes"]["candidates"] == json_sha256(candidates)
    assert [result["last_action"] for result in batch["results"]] == ["acquire", "acquire"]
    assert [result["next_action"] for result in batch["results"]] == ["parse", "parse"]

    run_dir = vault / "_epi" / "runs" / batch["run_id"]
    assert run_dir.is_dir()
    assert json.loads((run_dir / "run-state.json").read_text(encoding="utf-8")) == batch
    record = json.loads((run_dir / "batch-advance-record.json").read_text(encoding="utf-8"))
    assert record["stage"] == "batch-advance"
    assert record["processed_count"] == 2
    assert record["results"] == batch["results"]
    assert record["tool_versions"] == batch["tool_versions"]
    assert record["output_artifact_hashes"]["paper:batch-alpha:run-state.json"] == file_sha256(
        vault / "_epi" / "raw" / "papers" / "batch-alpha" / "run-state.json"
    )
    assert record["output_artifact_hashes"]["paper:batch-beta:run-state.json"] == file_sha256(
        vault / "_epi" / "raw" / "papers" / "batch-beta" / "run-state.json"
    )
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((vault / "_epi" / "runs" / "index.json").read_text(encoding="utf-8"))
    dashboard_text = (vault / "_epi" / "runs" / "dashboard.md").read_text(encoding="utf-8")
    assert report_json["processed_count"] == 2
    assert report_json["skipped_count"] == 0
    assert report_json["paper_states"] == [
        {"paper_slug": "batch-alpha", "state": "acquired", "next_action": "parse"},
        {"paper_slug": "batch-beta", "state": "acquired", "next_action": "parse"},
    ]
    assert report_json["failed_papers"] == []
    assert report_json["wiki_pages_written"] == []
    assert report_json["next_actions"] == ["parse"]
    assert "batch-alpha" in report_md
    assert "batch-beta" in report_md
    assert index_payload["runs"][0]["run_id"] == batch["run_id"]
    assert index_payload["runs"][0]["workflow_type"] == "advance-batch"
    assert batch["run_id"] in dashboard_text

    for slug in ("batch-alpha", "batch-beta"):
        assert (vault / "_epi" / "raw" / "papers" / slug / "paper.pdf").is_file()
        assert (vault / "_epi" / "raw" / "papers" / slug / "run-state.json").is_file()
        assert not (vault / "references" / f"{slug}.md").exists()


def test_advance_paper_batch_reports_research_decisions_after_critic(tmp_path):
    vault = tmp_path / "vault"
    candidate = _candidate("decision-paper", "Decision Paper", "https://example.org/decision.pdf")
    _seed_critic_ready_paper(vault, candidate)

    batch = advance_paper_batch(vault, [candidate])

    run_dir = vault / "_epi" / "runs" / batch["run_id"]
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((vault / "_epi" / "runs" / "index.json").read_text(encoding="utf-8"))

    assert batch["results"][0]["state"] == "critic_passed"
    assert report_json["research_decisions"][0]["slug"] == "decision-paper"
    assert report_json["research_decisions"][0]["recommendation"] == "stage-for-promotion-review"
    assert report_json["research_decisions"][0]["role_verdicts"] == {
        "nature-sci-editor": "pass",
        "peer-reviewer": "pass",
        "senior-domain-researcher": "pass",
    }
    assert report_json["reader_revision_plans"][0]["slug"] == "decision-paper"
    assert report_json["reader_revision_plans"][0]["next_action"] == "stage"
    assert report_json["reader_revision_plans"][0]["blocking_count"] == 0
    assert report_json["reader_revision_plans"][0]["warning_count"] == 0
    assert report_json["reader_revision_plans"][0]["plan_path"].endswith("reader-revision-plan.json")
    assert "## Research Decisions" in report_md
    assert "Decision Paper - stage-for-promotion-review" in report_md
    assert "## Reader Revision Plans" in report_md
    assert "Decision Paper - stage" in report_md
    assert index_payload["runs"][0]["research_decisions"][0]["recommendation"] == "stage-for-promotion-review"
    assert index_payload["runs"][0]["reader_revision_plans"][0]["slug"] == "decision-paper"


def test_advance_paper_batch_reports_reproducibility_caveats_after_critic(tmp_path):
    vault = tmp_path / "vault"
    candidate = _candidate("repro-plan-paper", "Repro Plan Paper", "https://example.org/repro.pdf")
    _seed_critic_ready_paper(vault, candidate, sources=["code", "dataset", "robot"])

    batch = advance_paper_batch(vault, [candidate])

    run_dir = vault / "_epi" / "runs" / batch["run_id"]
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    index_payload = json.loads((vault / "_epi" / "runs" / "index.json").read_text(encoding="utf-8"))

    assert batch["results"][0]["state"] == "critic_passed"
    assert report_json["reproduction_plans"][0]["slug"] == "repro-plan-paper"
    assert report_json["reproduction_plans"][0]["next_action"] == "prepare-reproduction-plan"
    assert report_json["reproduction_plans"][0]["missing_count"] >= 1
    assert report_json["reproduction_plans"][0]["plan_path"].endswith("reproduction-plan.json")
    assert "## Reproducibility Caveats" in report_md
    assert "Repro Plan Paper - review-reproducibility-caveats" in report_md
    assert index_payload["research_queue"]["reproducibility_caveats"][0]["paper_slug"] == "repro-plan-paper"


def test_advance_paper_batch_respects_max_papers_budget_and_records_skips(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "alpha.pdf").write_bytes(b"%PDF-1.4\nalpha fixture\n")
    (server_root / "beta.pdf").write_bytes(b"%PDF-1.4\nbeta fixture\n")
    vault = tmp_path / "vault"

    with _LocalServer(server_root) as base_url:
        candidates = [
            _candidate("budget-alpha", "Budget Alpha", f"{base_url}/alpha.pdf"),
            _candidate("budget-beta", "Budget Beta", f"{base_url}/beta.pdf"),
        ]
        batch = advance_paper_batch(vault, candidates, max_papers=1)

    assert batch["processed_count"] == 1
    assert batch["skipped_count"] == 1
    assert batch["input_artifact_hashes"]["candidates"] == json_sha256([candidates[0]])
    assert [result["paper_slug"] for result in batch["results"]] == ["budget-alpha"]
    record = json.loads(
        (vault / "_epi" / "runs" / batch["run_id"] / "batch-advance-record.json").read_text(encoding="utf-8")
    )
    assert record["input_artifact_hashes"]["candidates"] == json_sha256([candidates[0]])
    assert (vault / "_epi" / "raw" / "papers" / "budget-alpha" / "paper.pdf").is_file()
    assert not (vault / "_epi" / "raw" / "papers" / "budget-beta" / "paper.pdf").exists()


def test_advance_paper_batch_from_run_uses_ranked_candidates_without_manual_copy(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "ranked.pdf").write_bytes(b"%PDF-1.4\nranked fixture\n")
    vault = tmp_path / "vault"
    run_id = "20260527T120000Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)

    with _LocalServer(server_root) as base_url:
        ranked_candidate = _candidate("ranked-alpha", "Ranked Alpha", f"{base_url}/ranked.pdf")
        ranked_candidate["score"] = 0.99
        ranked_candidate["ranking_protocol"] = {"decision": "advance-candidate"}
        (run_dir / "rank.json").write_text(json.dumps([ranked_candidate]), encoding="utf-8")

        batch = advance_paper_batch_from_run(vault, run_id, max_papers=1)

    assert batch["source_run_id"] == run_id
    assert batch["candidate_source"] == str(run_dir / "rank.json")
    assert batch["processed_count"] == 1
    assert batch["started_at"]
    assert batch["finished_at"]
    assert batch["exit_status"] == 0
    assert batch["tool_versions"]["orchestrator"] == "epi-local"
    assert batch["input_artifact_hashes"]["candidate_source"] == file_sha256(run_dir / "rank.json")
    assert batch["results"][0]["paper_slug"] == "ranked-alpha"
    assert batch["results"][0]["last_action"] == "acquire"
    batch_run_dir = vault / "_epi" / "runs" / batch["run_id"]
    routed_report = json.loads((batch_run_dir / "report.json").read_text(encoding="utf-8"))
    assert routed_report["processed_count"] == 1
    assert routed_report["skipped_count"] == 0
    assert routed_report["paper_states"] == [
        {"paper_slug": "ranked-alpha", "state": "acquired", "next_action": "parse"}
    ]
    assert routed_report["failed_papers"] == []
    assert routed_report["next_actions"] == ["parse"]
    assert routed_report["wiki_pages_written"] == []
    assert batch["source_run_id"] == run_id
    assert json.loads((batch_run_dir / "batch-advance-record.json").read_text(encoding="utf-8"))["source_run_id"] == run_id
    assert (vault / "_epi" / "raw" / "papers" / "ranked-alpha" / "paper.pdf").is_file()


def test_prepare_ranked_papers_from_run_acquires_and_parses_then_stops(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "ranked.pdf").write_bytes(b"%PDF-1.4\nranked fixture\n")
    vault = tmp_path / "vault"
    run_id = "20260527T121500Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)
    mineru_command = _write_success_mineru_command(tmp_path)

    with _LocalServer(server_root) as base_url:
        ranked_candidate = _candidate("prepared-alpha", "Prepared Alpha", f"{base_url}/ranked.pdf")
        ranked_candidate["ranking_protocol"] = {"decision": "advance-candidate"}
        (run_dir / "rank.json").write_text(json.dumps([ranked_candidate]), encoding="utf-8")

        batch = prepare_ranked_papers_from_run(vault, run_id, mineru_command=mineru_command)

    assert batch["workflow_type"] == "prepare-ranked"
    assert batch["processed_count"] == 1
    assert batch["results"][0]["paper_slug"] == "prepared-alpha"
    assert batch["results"][0]["state"] == "parsed"
    assert batch["results"][0]["last_action"] == "parse"
    assert batch["results"][0]["next_action"] == "read"
    assert batch["next_actions"] == ["read"]
    paper_root = vault / "_epi" / "raw" / "papers" / "prepared-alpha"
    assert (paper_root / "paper.pdf").is_file()
    assert (paper_root / "mineru" / "paper.md").is_file()
    assert not (paper_root / "reader" / "reader.md").exists()
    assert not (paper_root / "critic" / "critic-report.json").exists()
    assert json.loads((vault / "_epi" / "runs" / batch["run_id"] / "batch-advance-record.json").read_text(encoding="utf-8"))[
        "workflow_type"
    ] == "prepare-ranked"


def test_prepare_ranked_papers_repairs_incomplete_existing_parse_outputs(tmp_path):
    vault = tmp_path / "vault"
    run_id = "20260527T122000Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)
    candidate = _candidate("incomplete-parse", "Incomplete Parse", "https://example.org/incomplete.pdf")
    candidate["ranking_protocol"] = {"decision": "advance-candidate"}
    (run_dir / "rank.json").write_text(json.dumps([candidate]), encoding="utf-8")
    paper_root = vault / "_epi" / "raw" / "papers" / "incomplete-parse"
    mineru_dir = paper_root / "mineru"
    mineru_dir.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nexisting fixture\n")
    (mineru_dir / "paper.md").write_text("# Old Parse\n\nExisting markdown.\n", encoding="utf-8")
    (mineru_dir / "paper.tex").write_text("", encoding="utf-8")
    mineru_command = _write_success_mineru_command(tmp_path)

    batch = prepare_ranked_papers_from_run(vault, run_id, mineru_command=mineru_command)

    result = batch["results"][0]
    assert result["state"] == "parsed"
    assert result["last_action"] == "parse"
    assert result["stage_record"]["status"] == "success"
    assert (mineru_dir / "paper.tex").stat().st_size > 0
    assert not (paper_root / "reader" / "reader.md").exists()


def test_prepare_ranked_papers_records_failed_candidate_and_continues(tmp_path, monkeypatch):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "good.pdf").write_bytes(b"%PDF-1.4\ngood fixture\n")
    vault = tmp_path / "vault"
    run_id = "20260527T122500Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)
    mineru_command = _write_success_mineru_command(tmp_path)

    failing_candidate = _candidate("download-timeout", "Download Timeout", "https://example.org/timeout.pdf")
    failing_candidate["ranking_protocol"] = {"decision": "advance-candidate"}

    with _LocalServer(server_root) as base_url:
        good_candidate = _candidate("after-timeout", "After Timeout", f"{base_url}/good.pdf")
        good_candidate["ranking_protocol"] = {"decision": "advance-candidate"}
        (run_dir / "rank.json").write_text(
            json.dumps([failing_candidate, good_candidate]),
            encoding="utf-8",
        )

        from epi.orchestrator import _prepare_candidate_until_parsed as original_prepare_candidate

        def _prepare_candidate(vault_path, candidate, *, mineru_command=None, mineru_timeout=None):
            if candidate["slug"] == "download-timeout":
                raise TimeoutError("simulated download timeout")

            return original_prepare_candidate(
                vault_path,
                candidate,
                mineru_command=mineru_command,
                mineru_timeout=mineru_timeout,
            )

        monkeypatch.setattr("epi.orchestrator._prepare_candidate_until_parsed", _prepare_candidate)

        batch = prepare_ranked_papers_from_run(
            vault,
            run_id,
            mineru_command=mineru_command,
            max_papers=2,
        )

    assert batch["status"] == "failed"
    assert batch["state"] == "prepare_failed"
    assert batch["processed_count"] == 2
    assert [result["paper_slug"] for result in batch["results"]] == ["download-timeout", "after-timeout"]
    assert batch["results"][0]["state"] == "prepare_failed"
    assert batch["results"][0]["last_action"] == "prepare"
    assert batch["results"][0]["stage_record"]["status"] == "failed"
    assert "simulated download timeout" in batch["results"][0]["stage_record"]["error"]
    assert batch["results"][1]["state"] == "parsed"
    assert (vault / "_epi" / "raw" / "papers" / "after-timeout" / "mineru" / "paper.md").is_file()

    report_json = json.loads((vault / "_epi" / "runs" / batch["run_id"] / "report.json").read_text(encoding="utf-8"))
    assert report_json["failed_papers"] == [
        {"paper_slug": "download-timeout", "state": "prepare_failed", "next_action": None}
    ]
    assert report_json["paper_states"][1] == {
        "paper_slug": "after-timeout",
        "state": "parsed",
        "next_action": "read",
    }


def test_prepare_ranked_papers_can_skip_existing_parsed_candidates_when_resuming(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "new.pdf").write_bytes(b"%PDF-1.4\nnew fixture\n")
    vault = tmp_path / "vault"
    run_id = "20260527T123000Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)
    mineru_command = _write_success_mineru_command(tmp_path)

    existing = _candidate("already-parsed", "Already Parsed", "https://example.org/already.pdf")
    existing["ranking_protocol"] = {"decision": "advance-candidate"}
    existing_root = vault / "_epi" / "raw" / "papers" / "already-parsed"
    existing_mineru = existing_root / "mineru"
    existing_mineru.mkdir(parents=True)
    (existing_root / "paper.pdf").write_bytes(b"%PDF-1.4\nexisting fixture\n")
    (existing_mineru / "paper.md").write_text("# Already Parsed\n", encoding="utf-8")
    (existing_mineru / "paper.tex").write_text("\\section{Already Parsed}\n", encoding="utf-8")
    (existing_mineru / "mineru-manifest.json").write_text("{}", encoding="utf-8")
    (existing_mineru / "images").mkdir()
    (existing_root / "parse-record.json").write_text(
        json.dumps({"stage": "parse", "status": "success"}), encoding="utf-8"
    )

    with _LocalServer(server_root) as base_url:
        new_candidate = _candidate("resume-new", "Resume New", f"{base_url}/new.pdf")
        new_candidate["ranking_protocol"] = {"decision": "advance-candidate"}
        (run_dir / "rank.json").write_text(
            json.dumps([existing, new_candidate]),
            encoding="utf-8",
        )

        batch = prepare_ranked_papers_from_run(
            vault,
            run_id,
            mineru_command=mineru_command,
            max_papers=1,
            skip_existing=True,
        )

    assert batch["processed_count"] == 1
    assert batch["skip_existing"] is True
    assert batch["skipped_existing_candidates"] == [
        {"slug": "already-parsed", "title": "Already Parsed", "reason": "already_parsed"}
    ]
    assert batch["results"][0]["paper_slug"] == "resume-new"
    assert batch["results"][0]["state"] == "parsed"
    assert (vault / "_epi" / "raw" / "papers" / "resume-new" / "mineru" / "paper.md").is_file()

    report_json = json.loads((vault / "_epi" / "runs" / batch["run_id"] / "report.json").read_text(encoding="utf-8"))
    assert report_json["skip_existing"] is True
    assert report_json["skipped_existing_candidates"] == batch["skipped_existing_candidates"]


def test_prepare_ranked_papers_reparses_when_parse_record_missing_or_unsuccessful(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    vault = tmp_path / "vault"
    run_id = "20260527T124500Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)
    mineru_command = _write_success_mineru_command(tmp_path)

    # Complete mineru/ files but NO success parse-record (e.g. process killed between
    # writing mineru/ outputs and parse-record.json, or a leftover/corrupted parse).
    # --skip-existing must NOT treat this as done; it must reparse.
    stale = _candidate("stale-parse", "Stale Parse", "https://example.org/stale.pdf")
    stale["ranking_protocol"] = {"decision": "advance-candidate"}
    stale_root = vault / "_epi" / "raw" / "papers" / "stale-parse"
    stale_mineru = stale_root / "mineru"
    stale_mineru.mkdir(parents=True)
    (stale_root / "paper.pdf").write_bytes(b"%PDF-1.4\nstale fixture\n")
    (stale_mineru / "paper.md").write_text("# Stale Parse\n", encoding="utf-8")
    (stale_mineru / "paper.tex").write_text("\\section{Stale Parse}\n", encoding="utf-8")
    (stale_mineru / "mineru-manifest.json").write_text("{}", encoding="utf-8")
    (stale_mineru / "images").mkdir()
    (stale_root / "parse-record.json").write_text(
        json.dumps({"stage": "parse", "status": "failed"}), encoding="utf-8"
    )
    (run_dir / "rank.json").write_text(json.dumps([stale]), encoding="utf-8")

    batch = prepare_ranked_papers_from_run(
        vault,
        run_id,
        mineru_command=mineru_command,
        max_papers=1,
        skip_existing=True,
    )

    assert batch["skipped_existing_candidates"] == []
    assert batch["processed_count"] == 1
    assert batch["results"][0]["paper_slug"] == "stale-parse"
    assert batch["results"][0]["state"] == "parsed"
    assert json.loads((stale_root / "parse-record.json").read_text(encoding="utf-8"))["status"] == "success"


def test_advance_paper_batch_from_run_skips_review_candidates_by_default(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "advance.pdf").write_bytes(b"%PDF-1.4\nadvance fixture\n")
    (server_root / "review.pdf").write_bytes(b"%PDF-1.4\nreview fixture\n")
    vault = tmp_path / "vault"
    run_id = "20260527T130000Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)

    with _LocalServer(server_root) as base_url:
        advance_candidate = _candidate("ranked-advance", "Ranked Advance", f"{base_url}/advance.pdf")
        advance_candidate["ranking_protocol"] = {"decision": "advance-candidate"}
        review_candidate = _candidate("ranked-review", "Ranked Review", f"{base_url}/review.pdf")
        review_candidate["ranking_protocol"] = {
            "decision": "review-candidate",
            "cautions": ["weak_reproducibility_signal"],
        }
        (run_dir / "rank.json").write_text(
            json.dumps([advance_candidate, review_candidate]),
            encoding="utf-8",
        )

        batch = advance_paper_batch_from_run(vault, run_id)

    assert batch["rank_decision_filter"] == ["advance-candidate"]
    assert batch["candidate_count"] == 2
    assert batch["processed_count"] == 1
    assert batch["skipped_count"] == 1
    assert batch["skipped_ranked_candidates"] == [
        {
            "slug": "ranked-review",
            "title": "Ranked Review",
            "decision": "review-candidate",
            "reason": "decision_not_selected",
        }
    ]
    assert (vault / "_epi" / "raw" / "papers" / "ranked-advance" / "paper.pdf").is_file()
    assert not (vault / "_epi" / "raw" / "papers" / "ranked-review" / "paper.pdf").exists()


def test_advance_paper_batch_from_run_can_include_review_candidates_explicitly(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    (server_root / "advance.pdf").write_bytes(b"%PDF-1.4\nadvance fixture\n")
    (server_root / "review.pdf").write_bytes(b"%PDF-1.4\nreview fixture\n")
    vault = tmp_path / "vault"
    run_id = "20260527T140000Z"
    run_dir = vault / "_epi" / "runs" / run_id
    run_dir.mkdir(parents=True)

    with _LocalServer(server_root) as base_url:
        advance_candidate = _candidate("include-advance", "Include Advance", f"{base_url}/advance.pdf")
        advance_candidate["ranking_protocol"] = {"decision": "advance-candidate"}
        review_candidate = _candidate("include-review", "Include Review", f"{base_url}/review.pdf")
        review_candidate["ranking_protocol"] = {"decision": "review-candidate"}
        (run_dir / "rank.json").write_text(
            json.dumps([advance_candidate, review_candidate]),
            encoding="utf-8",
        )

        batch = advance_paper_batch_from_run(vault, run_id, include_review_candidates=True)

    assert batch["rank_decision_filter"] == ["advance-candidate", "review-candidate"]
    assert batch["candidate_count"] == 2
    assert batch["processed_count"] == 2
    assert batch["skipped_count"] == 0
    assert batch["skipped_ranked_candidates"] == []
    assert (vault / "_epi" / "raw" / "papers" / "include-advance" / "paper.pdf").is_file()
    assert (vault / "_epi" / "raw" / "papers" / "include-review" / "paper.pdf").is_file()


def test_advance_paper_batch_from_run_fails_closed_when_rank_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing ranked candidates"):
        advance_paper_batch_from_run(tmp_path / "vault", "missing-run")
