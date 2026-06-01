from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable

from epi import orchestrator as workflows
from epi.artifacts import file_sha256, raw_paper_root, runs_root, utc_now
from epi.config import (
    apply_config_update,
    config_status as get_config_status,
    init_config,
    load_wiki_config,
    propose_config_update,
    recover_config_candidates,
    restore_config_from_file,
)
from epi.doctor import collect_doctor_report, open_setup_links, render_doctor_report
from epi.epi_repository import cleanup_epi_repository, migrate_legacy_epi_roots
from epi.report_run import load_run_report
from epi.runtime_config import apply_runtime_config
from epi.run_index import RESEARCH_QUEUE_BUCKETS
from epi.source_artifacts import resolve_mineru_markdown_path, resolved_mineru_markdown_relative_path
from epi.wiki_reset import reset_wiki_vault


Handler = Callable[[argparse.Namespace], int]


def _default_plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_vault() -> Path:
    configured = os.environ.get("EPI_VAULT")
    if configured:
        return Path(configured)
    return Path.cwd() / "paper-research-wiki"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _add_common_vault(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vault", type=Path, default=_default_vault())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EPI orchestrator.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--plugin-root", type=Path, default=_default_plugin_root())
    doctor.add_argument("--vault", type=Path, default=_default_vault())
    doctor.add_argument("--paper-search-command", default=None)
    doctor.add_argument("--mineru-command", default=None)
    doctor.add_argument("--open-setup", action="store_true")
    doctor.add_argument("--json", action="store_true")

    config_status = subparsers.add_parser("config-status")
    _add_common_vault(config_status)
    config_status.add_argument("--json", action="store_true")
    config_status.add_argument("--include-values", action="store_true")
    config_status.add_argument("--include-runtime", action="store_true")

    init_config = subparsers.add_parser("init-config")
    _add_common_vault(init_config)
    init_config.add_argument("--answers-json", type=Path, required=True)

    propose_config = subparsers.add_parser("propose-config-update")
    _add_common_vault(propose_config)
    propose_config.add_argument("--proposal-json", type=Path, required=True)
    propose_config.add_argument("--json", action="store_true")

    apply_config = subparsers.add_parser("apply-config-update")
    _add_common_vault(apply_config)
    apply_config.add_argument("--proposal-json", type=Path, required=True)
    apply_config.add_argument("--confirmed-by", required=True)

    config_recover = subparsers.add_parser("config-recover")
    _add_common_vault(config_recover)
    config_recover.add_argument("--backup-root", type=Path, default=None)
    config_recover.add_argument("--json", action="store_true")

    config_restore = subparsers.add_parser("config-restore")
    _add_common_vault(config_restore)
    config_restore.add_argument("--from", dest="source_path", type=Path, required=True)
    config_restore.add_argument("--confirmed-by", required=True)
    config_restore.add_argument("--json", action="store_true")

    wiki_reset = subparsers.add_parser("wiki-reset")
    _add_common_vault(wiki_reset)
    wiki_reset.add_argument("--confirmed-by", default=None)
    wiki_reset.add_argument("--reset-config-confirmed-by", default=None)
    wiki_reset.add_argument("--backup-root", type=Path, default=None)
    wiki_reset.add_argument("--no-backup", action="store_true")
    wiki_reset.add_argument("--preview", action="store_true")
    wiki_reset.add_argument("--json", action="store_true")

    wiki_repair = subparsers.add_parser("wiki-repair")
    _add_common_vault(wiki_repair)
    wiki_repair.add_argument("--backup-root", type=Path, default=None)
    wiki_repair.add_argument("--restore-from", type=Path, default=None)
    wiki_repair.add_argument("--confirmed-by", default=None)
    wiki_repair.add_argument("--json", action="store_true")

    epi_migrate = subparsers.add_parser("epi-repository-migrate")
    _add_common_vault(epi_migrate)
    epi_migrate.add_argument("--preview", action="store_true")
    epi_migrate.add_argument("--json", action="store_true")

    epi_cleanup = subparsers.add_parser("epi-repository-cleanup")
    _add_common_vault(epi_cleanup)
    epi_cleanup.add_argument("--preview", action="store_true")
    epi_cleanup.add_argument("--json", action="store_true")

    dry_run = subparsers.add_parser("dry-run")
    dry_run.add_argument("--query", required=True)
    dry_run.add_argument("--max-results", type=int, default=None)
    _add_common_vault(dry_run)
    dry_run.add_argument("--plugin-root", type=Path, default=_default_plugin_root())
    dry_run.add_argument("--fixture", type=Path, default=None)
    dry_run.add_argument("--paper-search-command", default=None)
    dry_run.add_argument("--sources", default=None, help="Comma-separated paper-search sources for live discovery.")
    dry_run.add_argument("--no-query-plan", action="store_true")
    dry_run.add_argument(
        "--query-plan-domain",
        default="auto",
        choices=["auto", "profile", "auv-control", "embodied-ai", "general-robotics"],
    )
    dry_run.add_argument("--query-plan-max-queries", type=int, default=6)
    dry_run.add_argument("--json", action="store_true")

    ingest_one = subparsers.add_parser("ingest-one")
    ingest_one.add_argument("--candidate", type=Path, required=True)
    ingest_one.add_argument("--pdf", type=Path, required=True)
    ingest_one.add_argument("--mineru-md", type=Path, required=True)
    ingest_one.add_argument("--mineru-tex", type=Path, default=None)
    ingest_one.add_argument("--mineru-images", type=Path, default=None)
    _add_common_vault(ingest_one)

    acquire = subparsers.add_parser("acquire-paper")
    acquire.add_argument("--candidate", type=Path, required=True)
    _add_common_vault(acquire)

    advance = subparsers.add_parser("advance-paper")
    advance.add_argument("--candidate", type=Path, required=True)
    _add_common_vault(advance)
    advance.add_argument("--mineru-command", default=None)
    advance.add_argument("--mineru-timeout", type=int, default=None)

    advance_batch = subparsers.add_parser("advance-batch")
    advance_batch.add_argument("--candidates", type=Path, required=True)
    _add_common_vault(advance_batch)
    advance_batch.add_argument("--max-papers", type=int, default=None)
    advance_batch.add_argument("--mineru-command", default=None)
    advance_batch.add_argument("--mineru-timeout", type=int, default=None)

    advance_ranked = subparsers.add_parser("advance-ranked")
    advance_ranked.add_argument("--run-id", required=True)
    _add_common_vault(advance_ranked)
    advance_ranked.add_argument("--max-papers", type=int, default=None)
    advance_ranked.add_argument("--mineru-command", default=None)
    advance_ranked.add_argument("--mineru-timeout", type=int, default=None)
    advance_ranked.add_argument("--include-review-candidates", action="store_true")

    prepare_ranked = subparsers.add_parser("prepare-ranked")
    prepare_ranked.add_argument("--run-id", required=True)
    _add_common_vault(prepare_ranked)
    prepare_ranked.add_argument("--max-papers", type=int, default=1)
    prepare_ranked.add_argument("--mineru-command", default=None)
    prepare_ranked.add_argument("--mineru-timeout", type=int, default=None)
    prepare_ranked.add_argument("--include-review-candidates", action="store_true")
    prepare_ranked.add_argument("--skip-existing", action="store_true")
    prepare_ranked.add_argument("--json", action="store_true")

    parse_paper = subparsers.add_parser("parse-paper")
    _add_common_vault(parse_paper)
    parse_paper.add_argument("--slug", required=True)
    parse_paper.add_argument("--mineru-command", default=None)
    parse_paper.add_argument("--mineru-timeout", type=int, default=None)

    promote = subparsers.add_parser("promote-to-wiki")
    _add_common_vault(promote)
    promote.add_argument("--slug", required=True)
    promote.add_argument("--approved-by", default=None)

    rollback = subparsers.add_parser("rollback-promotion")
    _add_common_vault(rollback)
    rollback.add_argument("--slug", required=True)

    redo_acquire = subparsers.add_parser("redo-acquire")
    _add_common_vault(redo_acquire)
    redo_acquire.add_argument("--slug", required=True)
    redo_acquire.add_argument("--pdf", type=Path, required=True)
    redo_acquire.add_argument("--reason", default="")

    redo_parse = subparsers.add_parser("redo-parse")
    _add_common_vault(redo_parse)
    redo_parse.add_argument("--slug", required=True)
    redo_parse.add_argument("--mineru-md", type=Path, required=True)
    redo_parse.add_argument("--mineru-tex", type=Path, default=None)
    redo_parse.add_argument("--mineru-images", type=Path, default=None)
    redo_parse.add_argument("--reason", default="")

    redo_read = subparsers.add_parser("redo-read")
    _add_common_vault(redo_read)
    redo_read.add_argument("--slug", required=True)
    redo_read.add_argument("--reason", default="")
    redo_read.add_argument("--from-revision-plan", action="store_true")
    redo_read.add_argument("--recritic", action="store_true")

    recritic = subparsers.add_parser("recritic")
    _add_common_vault(recritic)
    recritic.add_argument("--slug", required=True)
    recritic.add_argument("--reason", default="")

    zotero = subparsers.add_parser("zotero-sync")
    zotero.add_argument("--paper-root", type=Path, required=True)
    zotero.add_argument("--collection", default="EPI")
    zotero.add_argument("--enabled", action="store_true")
    zotero.add_argument("--item-key", default=None)

    feedback = subparsers.add_parser("record-feedback")
    _add_common_vault(feedback)
    feedback.add_argument("--type", required=True)
    feedback.add_argument("--target", required=True)
    feedback.add_argument("--message", required=True)
    feedback.add_argument("--source", default="human")

    evaluation_brief = subparsers.add_parser("evaluation-brief")
    evaluation_brief.add_argument("--target-asset", required=True)
    evaluation_brief.add_argument("--rationale", required=True)
    evaluation_brief.add_argument("--proposed-change-json", required=True)
    evaluation_brief.add_argument("--before-metrics-json", default=None)
    evaluation_brief.add_argument("--after-metrics-json", default=None)
    evaluation_brief.add_argument("--plugin-eval-json", type=Path, default=None)
    evaluation_brief.add_argument("--metric-pack-json", type=Path, default=None)
    evaluation_brief.add_argument("--benchmark-json", type=Path, default=None)
    evaluation_brief.add_argument("--evidence", action="append", default=[])
    evaluation_brief.add_argument("--reflection-type", default="OPTIMIZATION")
    evaluation_brief.add_argument("--evidence-type", default="plugin_eval_warning")
    evaluation_brief.add_argument("--brief-id", default=None)
    evaluation_brief.add_argument("--out-dir", type=Path, default=Path(".plugin-eval") / "improvement-briefs")
    evaluation_brief.add_argument("--json", action="store_true")

    propose = subparsers.add_parser("propose-evolution")
    _add_common_vault(propose)
    propose.add_argument("--reflection-type", required=True)
    propose.add_argument("--target-asset", required=True)
    propose.add_argument("--rationale", required=True)
    propose.add_argument("--proposed-change-json", required=True)
    propose.add_argument("--evidence", action="append", default=[])
    propose.add_argument("--evidence-type", default=None)
    propose.add_argument("--before-metrics-json", default=None)
    propose.add_argument("--acceptance-gates-json", default=None)
    propose.add_argument("--risk-level", default=None)

    activate = subparsers.add_parser("activate-evolution")
    _add_common_vault(activate)
    activate.add_argument("--proposal-id", required=True)
    activate.add_argument("--approved", action="store_true")
    activate.add_argument("--validation-result-json", default=None)

    evolution_query = subparsers.add_parser("evolution-query")
    _add_common_vault(evolution_query)
    evolution_query.add_argument("--status", default=None)
    evolution_query.add_argument("--limit", type=int, default=20)
    evolution_query.add_argument("--json", action="store_true")

    runs_query = subparsers.add_parser("runs-query")
    _add_common_vault(runs_query)
    runs_query_group = runs_query.add_mutually_exclusive_group()
    runs_query_group.add_argument("--failed", action="store_true")
    runs_query_group.add_argument("--human-gate", action="store_true")
    runs_query_group.add_argument("--latest-success")
    runs_query.add_argument("--workflow", default=None)
    runs_query.add_argument("--limit", type=int, default=10)

    report = subparsers.add_parser("report")
    _add_common_vault(report)
    report.add_argument("--run-id", required=True)
    report.add_argument("--json", action="store_true")

    run_lifecycle = subparsers.add_parser("run-lifecycle")
    _add_common_vault(run_lifecycle)
    run_lifecycle.add_argument("--keep-latest", type=int, default=15)
    run_lifecycle.add_argument("--keep-per-workflow", type=int, default=2)
    run_lifecycle.add_argument("--max-age-days", type=int, default=None)
    run_lifecycle.add_argument("--apply", action="store_true")
    run_lifecycle.add_argument("--json", action="store_true")

    research_queue = subparsers.add_parser("research-queue")
    _add_common_vault(research_queue)
    research_queue.add_argument("--bucket", choices=RESEARCH_QUEUE_BUCKETS, default=None)
    research_queue.add_argument("--limit", type=int, default=10)
    research_queue.add_argument("--actions", action="store_true")
    research_queue.add_argument("--json", action="store_true")

    wiki_query = subparsers.add_parser("wiki-query")
    _add_common_vault(wiki_query)
    wiki_query.add_argument("--consensus", default=None)
    wiki_query.add_argument("--role", default=None)
    wiki_query.add_argument("--verdict", default=None)
    wiki_query.add_argument("--warning-reviewer", default=None)
    wiki_query.add_argument("--blocking-lens", default=None)
    wiki_query.add_argument("--limit", type=int, default=20)
    wiki_query.add_argument("--json", action="store_true")

    wiki_ingest_handoff = subparsers.add_parser("wiki-ingest-handoff")
    _add_common_vault(wiki_ingest_handoff)
    wiki_ingest_handoff.add_argument("--slug", required=True)
    wiki_ingest_handoff.add_argument("--json", action="store_true")

    wiki_ingest_trigger = subparsers.add_parser("wiki-ingest-trigger")
    _add_common_vault(wiki_ingest_trigger)
    wiki_ingest_trigger.add_argument("--slug", required=True)
    wiki_ingest_trigger.add_argument("--json", action="store_true")

    record_human_approval = subparsers.add_parser("record-human-approval")
    _add_common_vault(record_human_approval)
    record_human_approval.add_argument("--slug", required=True)
    record_human_approval.add_argument("--approved-by", required=True)
    record_human_approval.add_argument("--scope", required=True)
    record_human_approval.add_argument("--notes", default=None)
    record_human_approval.add_argument("--json", action="store_true")

    record_wiki_ingest = subparsers.add_parser("record-wiki-ingest")
    _add_common_vault(record_wiki_ingest)
    record_wiki_ingest.add_argument("--slug", required=True)
    record_wiki_ingest.add_argument("--page", action="append", required=True)
    record_wiki_ingest.add_argument("--approved-by", required=True)
    record_wiki_ingest.add_argument("--notes", default=None)
    record_wiki_ingest.add_argument("--source-review", default=None)
    record_wiki_ingest.add_argument("--json", action="store_true")

    paper_gate = subparsers.add_parser("paper-gate")
    _add_common_vault(paper_gate)
    paper_gate.add_argument("--slug", required=True)
    paper_gate.add_argument("--json", action="store_true")

    return parser


def _handle_doctor(args: argparse.Namespace) -> int:
    report = collect_doctor_report(
        plugin_root=args.plugin_root,
        vault_path=args.vault,
        paper_search_command=args.paper_search_command,
        mineru_command=args.mineru_command,
    )
    if args.open_setup:
        report["opened_setup_urls"] = open_setup_links(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_doctor_report(report))
    return 1 if report["overall_status"] == "error" else 0


def _handle_config_status(args: argparse.Namespace) -> int:
    status = get_config_status(args.vault)
    if args.include_values:
        status["config"] = load_wiki_config(args.vault)
    if args.include_runtime:
        runtime = apply_runtime_config()
        status["runtime_config"] = runtime
        status["mineru_token"] = "set" if os.environ.get("MINERU_TOKEN") else "missing"
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"configured={str(status['configured']).lower()}")
        print(f"needs_onboarding={str(status['needs_onboarding']).lower()}")
        print(f"config_path={status['config_path']}")
        if args.include_runtime:
            print(f"runtime_config_path={status['runtime_config']['path']}")
            print(f"MINERU_TOKEN={status['mineru_token']}")
    return 0 if status["configured"] else 1


def _handle_init_config(args: argparse.Namespace) -> int:
    answers = _load_json(args.answers_json)
    if not isinstance(answers, dict):
        raise ValueError("answers-json must contain a JSON object")
    result = init_config(args.vault, answers)
    print(f"config_path={result['config_path']}")
    print(f"state_path={result['state_path']}")
    print(f"history_path={result['history_path']}")
    return 0


def _handle_propose_config_update(args: argparse.Namespace) -> int:
    proposal_json = _load_json(args.proposal_json)
    if not isinstance(proposal_json, dict):
        raise ValueError("proposal-json must contain a JSON object")
    proposal = propose_config_update(args.vault, proposal_json)
    if args.json:
        print(json.dumps(proposal, ensure_ascii=False, indent=2))
    else:
        print("status=proposal")
        print(f"config_path={proposal['config_path']}")
        if proposal["diff"]:
            print("diff:")
            print(proposal["diff"])
    return 0


def _handle_apply_config_update(args: argparse.Namespace) -> int:
    proposal_json = _load_json(args.proposal_json)
    if not isinstance(proposal_json, dict):
        raise ValueError("proposal-json must contain a JSON object")
    result = apply_config_update(args.vault, proposal_json, confirmed_by=args.confirmed_by)
    print("config_updated=true")
    print(f"config_path={result['config_path']}")
    print(f"state_path={result['state_path']}")
    print(f"history_path={result['history_path']}")
    if result["diff"]:
        print("diff:")
        print(result["diff"])
    return 0


def _handle_dry_run(args: argparse.Namespace) -> int:
    sources = [source.strip() for source in args.sources.split(",") if source.strip()] if args.sources else None
    run_dir = workflows.run_dry_run(
        plugin_root=args.plugin_root,
        vault_path=args.vault,
        query=args.query,
        max_results=args.max_results,
        fixture_path=args.fixture,
        paper_search_command=args.paper_search_command,
        sources=sources,
        use_query_plan=not args.no_query_plan,
        query_plan_domain=args.query_plan_domain,
        query_plan_max_queries=args.query_plan_max_queries,
    )
    if args.json:
        payload = {
            "run_dir": str(run_dir),
            "run_id": run_dir.name,
            "artifacts": {
                "query_plan": str(run_dir / "query-plan.json") if (run_dir / "query-plan.json").exists() else None,
                "search_record": str(run_dir / "search-record.json"),
                "rank": str(run_dir / "rank.json"),
                "report": str(run_dir / "report.md"),
                "report_json": str(run_dir / "report.json"),
                "run_state": str(run_dir / "run-state.json"),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"run_dir={run_dir}")
    return 0


def _handle_ingest_one(args: argparse.Namespace) -> int:
    result = workflows.run_one_paper_ingest(
        vault_path=args.vault,
        candidate=_load_json(args.candidate),
        pdf_path=args.pdf,
        mineru_markdown_path=args.mineru_md,
        mineru_tex_path=args.mineru_tex,
        mineru_images_dir=args.mineru_images,
    )
    print(f"paper_root={result['paper_root']}")
    print(f"staging_root={result['staging_root']}")
    return 0


def _handle_acquire_paper(args: argparse.Namespace) -> int:
    candidate = _load_json(args.candidate)
    record = workflows.acquire_paper_from_candidate(args.vault, candidate)
    print(f"acquire_status={record['status']}")
    print(f"paper_root={raw_paper_root(args.vault, candidate['slug'])}")
    return 0 if record["status"] == "success" else 1


def _handle_advance_paper(args: argparse.Namespace) -> int:
    state = workflows.advance_paper_once(
        args.vault,
        _load_json(args.candidate),
        mineru_command=args.mineru_command,
        mineru_timeout=args.mineru_timeout,
    )
    print(f"paper_state={state['state']}")
    print(f"last_action={state['last_action']}")
    if state.get("next_action"):
        print(f"next_action={state['next_action']}")
    return 0 if not state["state"].endswith("_failed") else 1


def _handle_advance_batch(args: argparse.Namespace) -> int:
    batch = workflows.advance_paper_batch(
        args.vault,
        _load_json(args.candidates),
        mineru_command=args.mineru_command,
        max_papers=args.max_papers,
        mineru_timeout=args.mineru_timeout,
    )
    print(f"run_dir={runs_root(args.vault) / batch['run_id']}")
    print(f"batch_state={batch['state']}")
    print(f"processed_count={batch['processed_count']}")
    return 0 if batch["state"] != "batch_failed" else 1


def _handle_advance_ranked(args: argparse.Namespace) -> int:
    batch = workflows.advance_paper_batch_from_run(
        args.vault,
        args.run_id,
        mineru_command=args.mineru_command,
        max_papers=args.max_papers,
        include_review_candidates=args.include_review_candidates,
        mineru_timeout=args.mineru_timeout,
    )
    print(f"run_dir={runs_root(args.vault) / batch['run_id']}")
    print(f"batch_state={batch['state']}")
    print(f"processed_count={batch['processed_count']}")
    return 0 if batch["state"] != "batch_failed" else 1


def _handle_prepare_ranked(args: argparse.Namespace) -> int:
    batch = workflows.prepare_ranked_papers_from_run(
        args.vault,
        args.run_id,
        mineru_command=args.mineru_command,
        max_papers=args.max_papers,
        include_review_candidates=args.include_review_candidates,
        skip_existing=args.skip_existing,
        mineru_timeout=args.mineru_timeout,
    )
    run_dir = runs_root(args.vault) / batch["run_id"]
    if args.json:
        print(
            json.dumps(
                {
                    "run_dir": str(run_dir),
                    "run_id": batch["run_id"],
                    "source_run_id": batch.get("source_run_id"),
                    "batch_state": batch["state"],
                    "status": batch.get("status"),
                    "processed_count": batch["processed_count"],
                    "skipped_count": batch.get("skipped_count", 0),
                    "stops_after": "parse",
                    "artifacts": {
                        "batch_record": str(run_dir / "batch-advance-record.json"),
                        "report": str(run_dir / "report.md"),
                        "report_json": str(run_dir / "report.json"),
                        "run_state": str(run_dir / "run-state.json"),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if batch["state"] != "prepare_failed" else 1
    print(f"run_dir={runs_root(args.vault) / batch['run_id']}")
    print(f"batch_state={batch['state']}")
    print(f"processed_count={batch['processed_count']}")
    print("stops_after=parse")
    return 0 if batch["state"] != "prepare_failed" else 1


def _handle_parse_paper(args: argparse.Namespace) -> int:
    record = workflows.parse_paper_with_mineru(
        args.vault, args.slug, mineru_command=args.mineru_command, mineru_timeout=args.mineru_timeout
    )
    print(f"parse_status={record['status']}")
    if record.get("batch_id"):
        print(f"batch_id={record['batch_id']}")
    return 0 if record["status"] == "success" else 1


def _handle_promote_to_wiki(args: argparse.Namespace) -> int:
    vault_path = args.vault.resolve()
    run_id, run_dir = workflows._new_run_dir(vault_path, "promote-to-wiki")
    started_at = utc_now()
    try:
        record = workflows.promote_paper(args.vault, args.slug, approved_by=args.approved_by)
    except ValueError as exc:
        report_md = run_dir / "report.md"
        report_json = run_dir / "report.json"
        message = str(exc)
        report_md.write_text(
            "\n".join(
                [
                    f"# EPI Promote To Wiki Deprecated - {args.slug}",
                    "",
                    "- workflow_type: promote-to-wiki",
                    "- status: failed",
                    f"- reason: {message}",
                    "- next_action: wiki-ingest-handoff",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        report_json.write_text(
            json.dumps(
                {
                    "workflow_type": "promote-to-wiki",
                    "run_id": run_id,
                    "status": "failed",
                    "paper_slug": args.slug,
                    "error": message,
                    "wiki_pages_written": [],
                    "next_actions": ["wiki-ingest-handoff"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        workflows._write_json(
            run_dir / "run-state.json",
            {
                "stage": "promote-to-wiki",
                "run_id": run_id,
                "workflow_type": "promote-to-wiki",
                "state": "deprecated",
                "status": "failed",
                "paper_slug": args.slug,
                "vault_path": str(vault_path),
                "compiled_wiki_write": False,
                "record_only": True,
                "started_at": started_at,
                "finished_at": utc_now(),
                "exit_status": 1,
                "error": message,
            },
        )
        workflows._refresh_run_index(vault_path)
        print(f"promotion_status=deprecated")
        print(f"reason={message}")
        print(f"run_dir={run_dir}")
        return 1
    paper_root = raw_paper_root(vault_path, args.slug)
    promotion_record_path = paper_root / "promotion-record.json"
    zotero_results = workflows._zotero_record_only(vault_path, paper_root)
    workflows._write_promotion_routed_report(
        run_dir,
        run_id=run_id,
        slug=args.slug,
        promoted_page_paths=record["promoted_page_paths"],
        human_gate=record.get("human_gate_decision", {}),
        zotero_results=zotero_results,
    )
    workflows._write_promotion_or_rollback_run_state(
        run_dir,
        run_id=run_id,
        workflow_type="promote-to-wiki",
        vault_path=vault_path,
        slug=args.slug,
        started_at=started_at,
        finished_at=utc_now(),
        input_artifact_hashes={"promotion-record.json": file_sha256(promotion_record_path)},
        output_artifact_hashes=workflows._hash_existing_outputs(
            {
                "promotion-record.json": promotion_record_path,
                "zotero-record.json": paper_root / "zotero-record.json",
                "report.md": run_dir / "report.md",
                "report.json": run_dir / "report.json",
            }
        ),
        zotero_results=zotero_results,
    )
    workflows._refresh_run_index(vault_path)
    print(f"promotion_status={record['status']}")
    print(f"promoted_pages={len(record['promoted_page_paths'])}")
    return 0


def _handle_rollback_promotion(args: argparse.Namespace) -> int:
    vault_path = args.vault.resolve()
    run_id, run_dir = workflows._new_run_dir(vault_path, "rollback-promotion")
    started_at = utc_now()
    record = workflows.rollback_promotion(args.vault, args.slug)
    paper_root = raw_paper_root(vault_path, args.slug)
    promotion_record_path = paper_root / "promotion-record.json"
    rollback_record_path = paper_root / "rollback-record.json"
    promotion_record = _load_json(promotion_record_path)
    workflows._write_rollback_routed_report(
        run_dir,
        run_id=run_id,
        slug=args.slug,
        human_gate=promotion_record.get("human_gate_decision"),
        restored_paths=record.get("restored_paths", []),
        removed_paths=record.get("removed_paths", []),
    )
    workflows._write_promotion_or_rollback_run_state(
        run_dir,
        run_id=run_id,
        workflow_type="rollback-promotion",
        vault_path=vault_path,
        slug=args.slug,
        started_at=started_at,
        finished_at=utc_now(),
        input_artifact_hashes={"promotion-record.json": file_sha256(promotion_record_path)},
        output_artifact_hashes=workflows._hash_existing_outputs(
            {
                "promotion-record.json": promotion_record_path,
                "rollback-record.json": rollback_record_path,
                "report.md": run_dir / "report.md",
                "report.json": run_dir / "report.json",
            }
        ),
    )
    workflows._refresh_run_index(vault_path)
    print(f"rollback_status={record['status']}")
    return 0


def _handle_redo_acquire(args: argparse.Namespace) -> int:
    started_at = utc_now()
    record = workflows.redo_acquire(args.vault, args.slug, args.pdf, reason=args.reason)
    workflows._write_repair_routed_report(
        args.vault.resolve(),
        args.slug,
        record,
        started_at=started_at,
        input_artifact_hashes={"input_pdf": file_sha256(args.pdf)},
    )
    print(f"redo_status={record['status']}")
    return 0


def _handle_redo_parse(args: argparse.Namespace) -> int:
    started_at = utc_now()
    record = workflows.redo_parse(
        args.vault,
        args.slug,
        args.mineru_md,
        tex_path=args.mineru_tex,
        images_dir=args.mineru_images,
        reason=args.reason,
    )
    input_hashes = {"input_markdown": file_sha256(args.mineru_md)}
    if args.mineru_tex is not None and args.mineru_tex.exists():
        input_hashes["input_tex"] = file_sha256(args.mineru_tex)
    workflows._write_repair_routed_report(
        args.vault.resolve(),
        args.slug,
        record,
        started_at=started_at,
        input_artifact_hashes=input_hashes,
    )
    print(f"redo_status={record['status']}")
    return 0


def _handle_redo_read(args: argparse.Namespace) -> int:
    started_at = utc_now()
    paper_root = raw_paper_root(args.vault.resolve(), args.slug)
    input_hashes = {
        resolved_mineru_markdown_relative_path(paper_root): file_sha256(resolve_mineru_markdown_path(paper_root)),
    }
    revision_plan_path = paper_root / "critic" / "reader-revision-plan.json"
    if args.from_revision_plan and revision_plan_path.exists():
        input_hashes["critic/reader-revision-plan.json"] = file_sha256(revision_plan_path)
    if args.recritic:
        record = workflows.redo_read_recritic(
            args.vault,
            args.slug,
            reason=args.reason,
            require_revision_plan=args.from_revision_plan,
        )
    else:
        record = workflows.redo_read(
            args.vault,
            args.slug,
            reason=args.reason,
            require_revision_plan=args.from_revision_plan,
        )
    workflows._write_repair_routed_report(
        args.vault.resolve(),
        args.slug,
        record,
        started_at=started_at,
        input_artifact_hashes=input_hashes,
    )
    print(f"redo_status={record['status']}")
    return 0


def _handle_recritic(args: argparse.Namespace) -> int:
    started_at = utc_now()
    record = workflows.recritic(args.vault, args.slug, reason=args.reason)
    workflows._write_repair_routed_report(
        args.vault.resolve(),
        args.slug,
        record,
        started_at=started_at,
        input_artifact_hashes={
            "reader/reader.md": file_sha256(raw_paper_root(args.vault.resolve(), args.slug) / "reader" / "reader.md"),
        },
    )
    print(f"recritic_status={record['status']}")
    return 0


def _handle_zotero_sync(args: argparse.Namespace) -> int:
    record = workflows.sync_zotero_record(
        args.paper_root,
        enabled=args.enabled,
        collection=args.collection,
        item_key=args.item_key,
    )
    print(f"zotero_status={record['status']}")
    return 0


def _handle_record_feedback(args: argparse.Namespace) -> int:
    feedback_record = workflows.record_feedback(
        args.vault,
        feedback_type=args.type,
        target=args.target,
        message=args.message,
        source=args.source,
    )
    print(f"feedback_id={feedback_record['id']}")
    return 0


def _json_object_arg(value: str | None) -> dict:
    return json.loads(value) if value else {}


def _handle_evaluation_brief(args: argparse.Namespace) -> int:
    brief = workflows.build_improvement_brief(
        target_asset=args.target_asset,
        rationale=args.rationale,
        proposed_change=json.loads(args.proposed_change_json),
        before_metrics=_json_object_arg(args.before_metrics_json),
        after_metrics=_json_object_arg(args.after_metrics_json),
        plugin_eval_path=args.plugin_eval_json,
        metric_pack_path=args.metric_pack_json,
        benchmark_path=args.benchmark_json,
        evidence=args.evidence,
        reflection_type=args.reflection_type,
        evidence_type=args.evidence_type,
        brief_id=args.brief_id,
    )
    paths = workflows.write_improvement_brief(args.out_dir, brief)
    if args.json:
        print(json.dumps({"brief": brief, "paths": paths}, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_improvement_brief(brief))
        print(f"brief_json={paths['json']}")
        print(f"brief_markdown={paths['markdown']}")
    return 0


def _handle_propose_evolution(args: argparse.Namespace) -> int:
    before_metrics = json.loads(args.before_metrics_json) if args.before_metrics_json else None
    acceptance_gates = json.loads(args.acceptance_gates_json) if args.acceptance_gates_json else None
    proposal = workflows.propose_evolution(
        args.vault,
        reflection_type=args.reflection_type,
        target_asset=args.target_asset,
        rationale=args.rationale,
        proposed_change=json.loads(args.proposed_change_json),
        evidence=args.evidence,
        evidence_type=args.evidence_type,
        before_metrics=before_metrics,
        acceptance_gates=acceptance_gates,
        risk_level=args.risk_level,
    )
    print(f"proposal_id={proposal['id']}")
    return 0


def _handle_activate_evolution(args: argparse.Namespace) -> int:
    validation_result = json.loads(args.validation_result_json) if args.validation_result_json else None
    activated = workflows.activate_evolution(
        args.vault,
        args.proposal_id,
        approved=args.approved,
        validation_result=validation_result,
    )
    print(f"evolution_status={activated['status']}")
    return 0


def _handle_evolution_query(args: argparse.Namespace) -> int:
    result = workflows.query_evolution(
        args.vault.resolve(),
        status=args.status,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_evolution_query(result))
    return 0


def _handle_runs_query(args: argparse.Namespace) -> int:
    result = workflows.query_runs(
        args.vault.resolve(),
        failed=args.failed,
        human_gate=args.human_gate,
        workflow=args.workflow,
        latest_success=args.latest_success,
        limit=args.limit,
    )
    print(workflows.render_runs_query(result))
    return 0


def _handle_report(args: argparse.Namespace) -> int:
    result = load_run_report(args.vault, args.run_id)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        markdown = result.get("markdown") or ""
        if markdown:
            print(markdown.rstrip())
        else:
            print(json.dumps(result.get("report") or {}, ensure_ascii=False, indent=2))
    return 0


def _handle_config_recover(args: argparse.Namespace) -> int:
    result = recover_config_candidates(args.vault, backup_root=args.backup_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"candidate_count={result['candidate_count']}")
        print(f"config_path={result['config_path']}")
        for candidate in result["candidates"]:
            print(f"- {candidate['path']}")
    return 0


def _handle_config_restore(args: argparse.Namespace) -> int:
    result = restore_config_from_file(args.vault, args.source_path, confirmed_by=args.confirmed_by)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("config_restore_status=restored")
        print(f"config_path={result['config_path']}")
        print(f"restored_from={result['restored_from']}")
    return 0


def _handle_wiki_reset(args: argparse.Namespace) -> int:
    result = reset_wiki_vault(
        args.vault,
        confirmed_by=args.confirmed_by,
        reset_config_confirmed_by=args.reset_config_confirmed_by,
        backup_root=args.backup_root,
        no_backup=args.no_backup,
        preview=args.preview,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"wiki_reset_status={result['status']}")
        print(f"vault_path={result['vault_path']}")
        print(f"backup_root={result['backup_root']}")
        if result["status"] == "preview":
            print(f"preserve_config={str(result['preserve_config']).lower()}")
            print(f"planned_actions={len(result['actions'])}")
        else:
            print(f"preserved_config={str(result['preserved_config']).lower()}")
            print(f"manifest_path={result['manifest_path']}")
    return 0


def _handle_wiki_repair(args: argparse.Namespace) -> int:
    before = get_config_status(args.vault)
    recovery = recover_config_candidates(args.vault, backup_root=args.backup_root)
    result = {
        "status": "inspected",
        "before_config": before,
        "recovery": recovery,
        "restored": None,
        "after_config": before,
    }
    if args.restore_from is not None:
        restored = restore_config_from_file(args.vault, args.restore_from, confirmed_by=args.confirmed_by or "")
        result["status"] = "repaired"
        result["restored"] = restored
        result["after_config"] = get_config_status(args.vault)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"wiki_repair_status={result['status']}")
        print(f"configured_before={str(before['configured']).lower()}")
        print(f"candidate_count={recovery['candidate_count']}")
        if result["restored"]:
            print(f"restored_from={result['restored']['restored_from']}")
    return 0 if result["after_config"]["configured"] else 1


def _handle_run_lifecycle(args: argparse.Namespace) -> int:
    result = workflows.prune_run_lifecycle(
        args.vault.resolve(),
        keep_latest=args.keep_latest,
        keep_per_workflow=args.keep_per_workflow,
        max_age_days=args.max_age_days,
        apply=args.apply,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_run_lifecycle(result))
    return 0


def _handle_epi_repository_migrate(args: argparse.Namespace) -> int:
    result = migrate_legacy_epi_roots(args.vault, dry_run=args.preview)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"epi_repository_migrate_status={result['status']}")
        print(f"epi_root={result['epi_root']}")
        print(f"actions={len(result['actions'])}")
        if result.get("manifest_path"):
            print(f"manifest_path={result['manifest_path']}")
    return 0


def _handle_epi_repository_cleanup(args: argparse.Namespace) -> int:
    result = cleanup_epi_repository(args.vault, dry_run=args.preview)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"epi_repository_cleanup_status={result['status']}")
        print(f"over_budget={str(bool(result['over_budget'])).lower()}")
        print(f"actions={len(result['actions'])}")
        if result.get("manifest_path"):
            print(f"manifest_path={result['manifest_path']}")
    return 0


def _handle_research_queue(args: argparse.Namespace) -> int:
    result = workflows.query_research_queue(
        args.vault.resolve(),
        bucket=args.bucket,
        limit=args.limit,
        include_actions=args.actions,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_research_queue_query(result))
    return 0


def _handle_wiki_query(args: argparse.Namespace) -> int:
    result = workflows.query_wiki(
        args.vault.resolve(),
        consensus=args.consensus,
        role=args.role,
        verdict=args.verdict,
        warning_reviewer=args.warning_reviewer,
        blocking_lens=args.blocking_lens,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_wiki_query(result))
    return 0


def _handle_wiki_ingest_handoff(args: argparse.Namespace) -> int:
    result = workflows.build_wiki_ingest_handoff(args.vault.resolve(), args.slug)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_wiki_ingest_handoff(result))
    return 0


def _handle_wiki_ingest_trigger(args: argparse.Namespace) -> int:
    result = workflows.build_wiki_ingest_trigger(args.vault.resolve(), args.slug)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_wiki_ingest_trigger(result))
    return 0 if result.get("status") in {"ready", "already_recorded"} else 1


def _handle_record_human_approval(args: argparse.Namespace) -> int:
    result = workflows.record_human_approval(
        args.vault.resolve(),
        args.slug,
        approved_by=args.approved_by,
        scope=args.scope,
        notes=args.notes,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        record = result["record"]
        print(f"approval_status={record['status']}")
        print(f"approval_path={result['record_path']}")
        print(f"run_dir={result['run_dir']}")
    return 0


def _handle_record_wiki_ingest(args: argparse.Namespace) -> int:
    result = workflows.record_wiki_ingest(
        args.vault.resolve(),
        args.slug,
        args.page,
        approved_by=args.approved_by,
        notes=args.notes,
        source_review_path=args.source_review,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        record = result["record"]
        print(f"record_status={record['status']}")
        print(f"record_path={result['record_path']}")
        print(f"recorded_pages={len(record['page_records'])}")
        print(f"run_dir={result['run_dir']}")
    return 0


def _handle_paper_gate(args: argparse.Namespace) -> int:
    result = workflows.build_paper_gate(args.vault.resolve(), args.slug)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_paper_gate(result))
    return 0


HANDLERS: dict[str, Handler] = {
    "doctor": _handle_doctor,
    "config-status": _handle_config_status,
    "init-config": _handle_init_config,
    "propose-config-update": _handle_propose_config_update,
    "apply-config-update": _handle_apply_config_update,
    "config-recover": _handle_config_recover,
    "config-restore": _handle_config_restore,
    "wiki-reset": _handle_wiki_reset,
    "wiki-repair": _handle_wiki_repair,
    "epi-repository-migrate": _handle_epi_repository_migrate,
    "epi-repository-cleanup": _handle_epi_repository_cleanup,
    "dry-run": _handle_dry_run,
    "ingest-one": _handle_ingest_one,
    "acquire-paper": _handle_acquire_paper,
    "advance-paper": _handle_advance_paper,
    "advance-batch": _handle_advance_batch,
    "advance-ranked": _handle_advance_ranked,
    "prepare-ranked": _handle_prepare_ranked,
    "parse-paper": _handle_parse_paper,
    "promote-to-wiki": _handle_promote_to_wiki,
    "rollback-promotion": _handle_rollback_promotion,
    "redo-acquire": _handle_redo_acquire,
    "redo-parse": _handle_redo_parse,
    "redo-read": _handle_redo_read,
    "recritic": _handle_recritic,
    "zotero-sync": _handle_zotero_sync,
    "record-feedback": _handle_record_feedback,
    "evaluation-brief": _handle_evaluation_brief,
    "propose-evolution": _handle_propose_evolution,
    "activate-evolution": _handle_activate_evolution,
    "evolution-query": _handle_evolution_query,
    "runs-query": _handle_runs_query,
    "report": _handle_report,
    "run-lifecycle": _handle_run_lifecycle,
    "research-queue": _handle_research_queue,
    "wiki-query": _handle_wiki_query,
    "wiki-ingest-handoff": _handle_wiki_ingest_handoff,
    "wiki-ingest-trigger": _handle_wiki_ingest_trigger,
    "record-human-approval": _handle_record_human_approval,
    "record-wiki-ingest": _handle_record_wiki_ingest,
    "paper-gate": _handle_paper_gate,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return HANDLERS[args.command](args)
