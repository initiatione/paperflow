from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from epi import orchestrator as workflows
from epi.artifacts import file_sha256, raw_paper_root, utc_now
from epi.config import apply_config_update, config_status as get_config_status, init_config, propose_config_update
from epi.doctor import collect_doctor_report, render_doctor_report


Handler = Callable[[argparse.Namespace], int]


def _default_plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_vault() -> Path:
    return Path(r"D:\paper-research-wiki")


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
    doctor.add_argument("--paper-search-command", default="paper-search")
    doctor.add_argument("--mineru-command", default=None)
    doctor.add_argument("--json", action="store_true")

    config_status = subparsers.add_parser("config-status")
    _add_common_vault(config_status)
    config_status.add_argument("--json", action="store_true")

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

    dry_run = subparsers.add_parser("dry-run")
    dry_run.add_argument("--query", required=True)
    dry_run.add_argument("--max-results", type=int, default=None)
    _add_common_vault(dry_run)
    dry_run.add_argument("--plugin-root", type=Path, default=_default_plugin_root())
    dry_run.add_argument("--fixture", type=Path, default=None)
    dry_run.add_argument("--paper-search-command", default=None)
    dry_run.add_argument("--sources", default=None, help="Comma-separated paper-search sources for live discovery.")

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

    advance_batch = subparsers.add_parser("advance-batch")
    advance_batch.add_argument("--candidates", type=Path, required=True)
    _add_common_vault(advance_batch)
    advance_batch.add_argument("--max-papers", type=int, default=None)
    advance_batch.add_argument("--mineru-command", default=None)

    advance_ranked = subparsers.add_parser("advance-ranked")
    advance_ranked.add_argument("--run-id", required=True)
    _add_common_vault(advance_ranked)
    advance_ranked.add_argument("--max-papers", type=int, default=None)
    advance_ranked.add_argument("--mineru-command", default=None)

    parse_paper = subparsers.add_parser("parse-paper")
    _add_common_vault(parse_paper)
    parse_paper.add_argument("--slug", required=True)
    parse_paper.add_argument("--mineru-command", default=None)

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

    propose = subparsers.add_parser("propose-evolution")
    _add_common_vault(propose)
    propose.add_argument("--reflection-type", required=True)
    propose.add_argument("--target-asset", required=True)
    propose.add_argument("--rationale", required=True)
    propose.add_argument("--proposed-change-json", required=True)
    propose.add_argument("--evidence", action="append", default=[])

    activate = subparsers.add_parser("activate-evolution")
    _add_common_vault(activate)
    activate.add_argument("--proposal-id", required=True)
    activate.add_argument("--approved", action="store_true")

    runs_query = subparsers.add_parser("runs-query")
    _add_common_vault(runs_query)
    runs_query_group = runs_query.add_mutually_exclusive_group()
    runs_query_group.add_argument("--failed", action="store_true")
    runs_query_group.add_argument("--human-gate", action="store_true")
    runs_query_group.add_argument("--latest-success")
    runs_query.add_argument("--workflow", default=None)
    runs_query.add_argument("--limit", type=int, default=10)

    return parser


def _handle_doctor(args: argparse.Namespace) -> int:
    report = collect_doctor_report(
        plugin_root=args.plugin_root,
        vault_path=args.vault,
        paper_search_command=args.paper_search_command,
        mineru_command=args.mineru_command,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_doctor_report(report))
    return 1 if report["overall_status"] == "error" else 0


def _handle_config_status(args: argparse.Namespace) -> int:
    status = get_config_status(args.vault)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"configured={str(status['configured']).lower()}")
        print(f"needs_onboarding={str(status['needs_onboarding']).lower()}")
        print(f"config_path={status['config_path']}")
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
    )
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
    )
    print(f"run_dir={args.vault.resolve() / '_runs' / batch['run_id']}")
    print(f"batch_state={batch['state']}")
    print(f"processed_count={batch['processed_count']}")
    return 0 if batch["state"] != "batch_failed" else 1


def _handle_advance_ranked(args: argparse.Namespace) -> int:
    batch = workflows.advance_paper_batch_from_run(
        args.vault,
        args.run_id,
        mineru_command=args.mineru_command,
        max_papers=args.max_papers,
    )
    print(f"run_dir={args.vault.resolve() / '_runs' / batch['run_id']}")
    print(f"batch_state={batch['state']}")
    print(f"processed_count={batch['processed_count']}")
    return 0 if batch["state"] != "batch_failed" else 1


def _handle_parse_paper(args: argparse.Namespace) -> int:
    record = workflows.parse_paper_with_mineru(args.vault, args.slug, mineru_command=args.mineru_command)
    print(f"parse_status={record['status']}")
    if record.get("batch_id"):
        print(f"batch_id={record['batch_id']}")
    return 0 if record["status"] == "success" else 1


def _handle_promote_to_wiki(args: argparse.Namespace) -> int:
    vault_path = args.vault.resolve()
    run_id, run_dir = workflows._new_run_dir(vault_path, "promote-to-wiki")
    started_at = utc_now()
    record = workflows.promote_paper(args.vault, args.slug, approved_by=args.approved_by)
    paper_root = raw_paper_root(vault_path, args.slug)
    promotion_record_path = paper_root / "promotion-record.json"
    workflows._write_promotion_routed_report(
        run_dir,
        run_id=run_id,
        slug=args.slug,
        promoted_page_paths=record["promoted_page_paths"],
        human_gate=record.get("human_gate_decision", {}),
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
                "report.md": run_dir / "report.md",
                "report.json": run_dir / "report.json",
            }
        ),
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
    record = workflows.redo_read(args.vault, args.slug, reason=args.reason)
    workflows._write_repair_routed_report(
        args.vault.resolve(),
        args.slug,
        record,
        started_at=started_at,
        input_artifact_hashes={
            "mineru/paper.md": file_sha256(raw_paper_root(args.vault.resolve(), args.slug) / "mineru" / "paper.md"),
        },
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


def _handle_propose_evolution(args: argparse.Namespace) -> int:
    proposal = workflows.propose_evolution(
        args.vault,
        reflection_type=args.reflection_type,
        target_asset=args.target_asset,
        rationale=args.rationale,
        proposed_change=json.loads(args.proposed_change_json),
        evidence=args.evidence,
    )
    print(f"proposal_id={proposal['id']}")
    return 0


def _handle_activate_evolution(args: argparse.Namespace) -> int:
    activated = workflows.activate_evolution(args.vault, args.proposal_id, approved=args.approved)
    print(f"evolution_status={activated['status']}")
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


HANDLERS: dict[str, Handler] = {
    "doctor": _handle_doctor,
    "config-status": _handle_config_status,
    "init-config": _handle_init_config,
    "propose-config-update": _handle_propose_config_update,
    "apply-config-update": _handle_apply_config_update,
    "dry-run": _handle_dry_run,
    "ingest-one": _handle_ingest_one,
    "acquire-paper": _handle_acquire_paper,
    "advance-paper": _handle_advance_paper,
    "advance-batch": _handle_advance_batch,
    "advance-ranked": _handle_advance_ranked,
    "parse-paper": _handle_parse_paper,
    "promote-to-wiki": _handle_promote_to_wiki,
    "rollback-promotion": _handle_rollback_promotion,
    "redo-acquire": _handle_redo_acquire,
    "redo-parse": _handle_redo_parse,
    "redo-read": _handle_redo_read,
    "recritic": _handle_recritic,
    "zotero-sync": _handle_zotero_sync,
    "record-feedback": _handle_record_feedback,
    "propose-evolution": _handle_propose_evolution,
    "activate-evolution": _handle_activate_evolution,
    "runs-query": _handle_runs_query,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return HANDLERS[args.command](args)
