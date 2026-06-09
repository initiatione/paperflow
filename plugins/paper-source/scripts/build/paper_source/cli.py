from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from paper_source import research_brief
from paper_source import cli_routes, orchestrator as workflows
from paper_source.artifacts import file_sha256, raw_paper_root, runs_root, utc_now, write_json_atomic
from paper_source.cli_parser import build_parser
from paper_source.config import (
    apply_config_update,
    config_status as get_config_status,
    init_config,
    load_wiki_config,
    propose_config_update,
    recover_config_candidates,
    restore_config_from_file,
)
from paper_source.doctor import collect_doctor_report, open_setup_links, render_doctor_report
from paper_source.paper_source_repository import cleanup_paper_source_repository, migrate_legacy_paper_source_roots
from paper_source.report_run import load_run_report
from paper_source.runtime_config import apply_runtime_config
from paper_source.source_artifacts import resolve_mineru_markdown_path, resolved_mineru_markdown_relative_path
from paper_source.wiki_reset import reset_wiki_vault


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_review_payload(run_dir: Path) -> dict | None:
    try:
        state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    review = state.get("review_session")
    return review if isinstance(review, dict) else None


def _run_research_brief_payload(run_dir: Path) -> dict | None:
    try:
        state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    brief = state.get("research_brief")
    return brief if isinstance(brief, dict) else None


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
        status["easyscholar_secret_key"] = "set" if os.environ.get("EASYSCHOLAR_SECRET_KEY") else "missing"
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"configured={str(status['configured']).lower()}")
        print(f"needs_onboarding={str(status['needs_onboarding']).lower()}")
        print(f"config_path={status['config_path']}")
        if args.include_runtime:
            print(f"runtime_config_path={status['runtime_config']['path']}")
            print(f"MINERU_TOKEN={status['mineru_token']}")
            print(f"EASYSCHOLAR_SECRET_KEY={status['easyscholar_secret_key']}")
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


def _research_brief_output(result: dict) -> dict:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    return {
        "brief_slug": result.get("slug") or payload.get("slug"),
        "status": result.get("status") or payload.get("status"),
        "revision_number": result.get("revision_number") or payload.get("revision_number"),
        "path": result.get("json_path"),
        "json_path": result.get("json_path"),
        "markdown_path": result.get("markdown_path"),
        "agent_brief_path": result.get("agent_brief_path"),
        "hash": result.get("hash") or payload.get("content_hash"),
    }


def _research_brief_validation_result(path: Path) -> tuple[dict, int]:
    json_path = Path(path)
    payload: dict = {}
    try:
        raw = _load_json(json_path)
        if isinstance(raw, dict):
            payload = raw
        result = research_brief.load_research_brief(json_path, allow_draft=True)
    except (json.JSONDecodeError, OSError, research_brief.ResearchBriefValidationError) as exc:
        brief_slug = payload.get("slug")
        try:
            brief_slug = research_brief.validate_slug(brief_slug)
        except research_brief.ResearchBriefValidationError:
            brief_slug = None
        return (
            {
                "valid": False,
                "brief_slug": brief_slug,
                "status": payload.get("status"),
                "revision_number": payload.get("revision_number"),
                "path": str(json_path),
                "hash": payload.get("content_hash"),
                "errors": [str(exc)],
            },
            1,
        )
    output = _research_brief_output(result)
    return (
        {
            "valid": True,
            "brief_slug": output["brief_slug"],
            "status": output["status"],
            "revision_number": output["revision_number"],
            "path": output["path"],
            "hash": output["hash"],
            "errors": [],
        },
        0,
    )


def _compact_research_brief_entry(result: dict) -> dict:
    payload = result["payload"]
    return {
        "brief_slug": payload["slug"],
        "status": payload["status"],
        "title": payload["title"],
        "task": payload["task"],
        "created_at": payload["created_at"],
        "updated_at": payload["updated_at"],
        "revision_number": payload["revision_number"],
        "last_used_at": None,
        "path": result["json_path"],
    }


def _list_research_briefs(vault_path: Path) -> dict:
    root = research_brief.research_briefs_root(vault_path)
    briefs: list[dict] = []
    errors: list[dict] = []
    if not root.exists():
        return {"briefs": briefs, "errors": errors}
    for brief_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        json_path = brief_dir / "research-brief.json"
        if not json_path.exists():
            continue
        try:
            loaded = research_brief.load_research_brief(json_path, allow_draft=True)
        except (json.JSONDecodeError, OSError, research_brief.ResearchBriefValidationError) as exc:
            errors.append({"path": str(json_path), "error": str(exc)})
            continue
        briefs.append(_compact_research_brief_entry(loaded))
    return {"briefs": briefs, "errors": errors}


def _handle_research_brief(args: argparse.Namespace) -> int:
    if args.research_brief_action == "create":
        answers = _load_json(args.answers_json)
        if not isinstance(answers, dict):
            raise ValueError("answers-json must contain a JSON object")
        result = research_brief.create_research_brief(args.vault, answers)
        output = _research_brief_output(result)
        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(f"brief_slug={output['brief_slug']}")
            print(f"json_path={output['json_path']}")
            print(f"markdown_path={output['markdown_path']}")
            print(f"agent_brief_path={output['agent_brief_path']}")
        return 0

    if args.research_brief_action == "validate":
        result, exit_code = _research_brief_validation_result(args.brief)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"valid={str(result['valid']).lower()}")
            print(f"brief_slug={result['brief_slug']}")
            print(f"path={result['path']}")
            for error in result["errors"]:
                print(f"error={error}")
        return exit_code

    if args.research_brief_action == "list":
        result = _list_research_briefs(args.vault)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for entry in result["briefs"]:
                print(
                    f"brief_slug={entry['brief_slug']} status={entry['status']} "
                    f"revision_number={entry['revision_number']} path={entry['path']}"
                )
            for error in result["errors"]:
                print(f"error_path={error['path']} error={error['error']}")
        return 0

    raise ValueError(f"unsupported research-brief action: {args.research_brief_action}")


def _handle_dry_run(args: argparse.Namespace) -> int:
    sources = [source.strip() for source in args.sources.split(",") if source.strip()] if args.sources else None
    run_dir = workflows.run_dry_run(
        plugin_root=args.plugin_root,
        vault_path=args.vault,
        query=args.query,
        from_brief=args.from_brief,
        allow_draft_brief=args.allow_draft_brief,
        max_results=args.max_results,
        fixture_path=args.fixture,
        paper_search_command=args.paper_search_command,
        sources=sources,
        use_query_plan=not args.no_query_plan,
        query_plan_domain=args.query_plan_domain,
        query_plan_max_queries=args.query_plan_max_queries,
        enable_easyscholar=not args.no_easyscholar,
        resume=not args.no_resume,
        refresh=args.refresh,
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
        review_payload = _run_review_payload(run_dir)
        if review_payload:
            payload["review"] = review_payload
        brief_payload = _run_research_brief_payload(run_dir)
        if brief_payload:
            payload["research_brief"] = brief_payload
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"run_dir={run_dir}")
        brief_payload = _run_research_brief_payload(run_dir)
        if brief_payload:
            print(
                f"research_brief={brief_payload.get('slug')} "
                f"status={brief_payload.get('status')} overrides_profile=true"
            )
    return 0


def _handle_ingest_one(args: argparse.Namespace) -> int:
    result = workflows.run_one_paper_ingest(
        vault_path=args.vault,
        candidate=_load_json(args.candidate),
        pdf_path=args.pdf,
        mineru_markdown_path=args.mineru_md,
        mineru_tex_path=args.mineru_tex,
        mineru_images_dir=args.mineru_images,
        workflow_mode=args.mode,
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
        workflow_mode=args.mode,
    )
    print(f"paper_state={state['state']}")
    print(f"last_action={state['last_action']}")
    print(f"workflow_mode={state.get('workflow_mode', args.mode)}")
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
        workflow_mode=args.mode,
    )
    print(f"run_dir={runs_root(args.vault) / batch['run_id']}")
    print(f"batch_state={batch['state']}")
    print(f"workflow_mode={batch.get('workflow_mode', args.mode)}")
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
        workflow_mode=args.mode,
    )
    print(f"run_dir={runs_root(args.vault) / batch['run_id']}")
    print(f"batch_state={batch['state']}")
    print(f"workflow_mode={batch.get('workflow_mode', args.mode)}")
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
        workflow_mode=args.mode,
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
                    "workflow_mode": batch.get("workflow_mode", args.mode),
                    "processed_count": batch["processed_count"],
                    "skipped_count": batch.get("skipped_count", 0),
                    "stops_after": batch.get("stops_after", "source-staging"),
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
    print(f"workflow_mode={batch.get('workflow_mode', args.mode)}")
    print(f"processed_count={batch['processed_count']}")
    print(f"stops_after={batch.get('stops_after', 'source-staging')}")
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
                    f"# Paper Source Promote To Wiki Deprecated - {args.slug}",
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
        write_json_atomic(
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
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
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


def _handle_paper_source_repository_migrate(args: argparse.Namespace) -> int:
    result = migrate_legacy_paper_source_roots(args.vault, dry_run=args.preview)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"paper_source_repository_migrate_status={result['status']}")
        print(f"paper_source_root={result['paper_source_root']}")
        print(f"actions={len(result['actions'])}")
        if result.get("manifest_path"):
            print(f"manifest_path={result['manifest_path']}")
    return 0


def _handle_paper_source_repository_cleanup(args: argparse.Namespace) -> int:
    result = cleanup_paper_source_repository(args.vault, dry_run=args.preview)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"paper_source_repository_cleanup_status={result['status']}")
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


def _handle_wiki_ask(args: argparse.Namespace) -> int:
    result = workflows.ask_wiki(
        args.vault.resolve(),
        question=args.question,
        limit=args.limit,
        max_hops=args.max_hops,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(workflows.render_wiki_ask(result))
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
        args.page or [],
        approved_by=args.approved_by,
        notes=args.notes,
        source_review_path=args.source_review,
        from_paper_wiki_request=args.from_paper_wiki_request,
        from_prw_request=args.from_prw_request,
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


HANDLERS = cli_routes.bind_handlers(globals())


def main(argv: list[str] | None = None) -> int:
    apply_runtime_config()
    args = build_parser().parse_args(argv)
    return cli_routes.dispatch(args, HANDLERS)
