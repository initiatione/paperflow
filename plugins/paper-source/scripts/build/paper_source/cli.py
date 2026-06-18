from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from paper_source import discover_papers as discover_papers_workflow
from paper_source import research_brief
from paper_source import cli_routes, orchestrator as workflows
from paper_source.artifacts import existing_raw_paper_root, file_sha256, raw_paper_root, read_json, runs_root, utc_now, write_json_atomic
from paper_source.asset_normalization import normalize_mineru_assets
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
from paper_source.discovery_benchmark import run_discovery_benchmark
from paper_source.paper_source_repository import cleanup_paper_source_repository, migrate_legacy_paper_source_roots
from paper_source.report_run import load_run_report
from paper_source.runtime_config import apply_runtime_config
from paper_source.source_artifacts import is_nonempty_file, resolve_mineru_markdown_path, resolved_mineru_markdown_relative_path
from paper_source.wiki_reset import reset_wiki_vault


def _print_json(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.flush()
        return
    print(text, end="")


def _run_review_payload(run_dir: Path) -> dict | None:
    state = read_json(run_dir / "run-state.json", default=None)
    if not isinstance(state, dict):
        return None
    review = state.get("review_session")
    return review if isinstance(review, dict) else None


def _run_research_brief_payload(run_dir: Path) -> dict | None:
    state = read_json(run_dir / "run-state.json", default=None)
    if not isinstance(state, dict):
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
    answers = read_json(args.answers_json)
    if not isinstance(answers, dict):
        raise ValueError("answers-json must contain a JSON object")
    result = init_config(args.vault, answers)
    print(f"config_path={result['config_path']}")
    print(f"state_path={result['state_path']}")
    print(f"history_path={result['history_path']}")
    return 0


def _handle_propose_config_update(args: argparse.Namespace) -> int:
    proposal_json = read_json(args.proposal_json)
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
    proposal_json = read_json(args.proposal_json)
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
        raw = read_json(json_path)
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
        answers = read_json(args.answers_json)
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
        query_variants=args.query_variant,
        domain_focus_terms=args.domain_focus_term,
        agent_query_plan_json=args.agent_query_plan_json,
        year_min=args.year_min,
        code_policy=args.code_policy,
        query_plan_domain=args.query_plan_domain,
        query_plan_max_queries=args.query_plan_max_queries,
        enable_easyscholar=not args.no_easyscholar,
        selection_policy=args.selection_policy,
        grok_mode=args.grok_mode,
        no_grok_search=args.no_grok_search,
        resume=not args.no_resume,
        refresh=args.refresh,
    )
    if args.json:
        payload = {
            "run_dir": str(run_dir),
            "run_id": run_dir.name,
            "selection_policy": args.selection_policy,
            "artifacts": {
                "query_plan": str(run_dir / "query-plan.json") if (run_dir / "query-plan.json").exists() else None,
                "search_record": str(run_dir / "search-record.json"),
                "filter_report": str(run_dir / "filter-report.json"),
                "discovery_diagnostics": str(run_dir / "discovery-diagnostics.json")
                if (run_dir / "discovery-diagnostics.json").exists()
                else None,
                "rank": str(run_dir / "rank.json"),
                "report": str(run_dir / "report.md"),
                "report_json": str(run_dir / "report.json"),
                "run_state": str(run_dir / "run-state.json"),
                "progress_events": str(run_dir / "progress-events.jsonl")
                if (run_dir / "progress-events.jsonl").exists()
                else None,
                "progress_summary": str(run_dir / "progress-summary.json")
                if (run_dir / "progress-summary.json").exists()
                else None,
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


def _handle_discover_to_handoff(args: argparse.Namespace) -> int:
    sources = [source.strip() for source in args.sources.split(",") if source.strip()] if args.sources else None
    record = workflows.discover_to_handoff(
        plugin_root=args.plugin_root,
        vault_path=args.vault,
        query=args.query,
        from_brief=args.from_brief,
        allow_draft_brief=args.allow_draft_brief,
        max_results=args.max_results,
        max_papers=args.max_papers,
        fixture_path=args.fixture,
        paper_search_command=args.paper_search_command,
        sources=sources,
        use_query_plan=not args.no_query_plan,
        query_variants=args.query_variant,
        domain_focus_terms=args.domain_focus_term,
        agent_query_plan_json=args.agent_query_plan_json,
        year_min=args.year_min,
        code_policy=args.code_policy,
        query_plan_domain=args.query_plan_domain,
        query_plan_max_queries=args.query_plan_max_queries,
        enable_easyscholar=not args.no_easyscholar,
        selection_policy=args.selection_policy,
        grok_mode=args.grok_mode,
        no_grok_search=args.no_grok_search,
        refresh=args.refresh,
        include_review_candidates=args.include_review_candidates,
        skip_existing=args.skip_existing,
        mineru_command=args.mineru_command,
        mineru_timeout=args.mineru_timeout,
        workflow_mode=args.mode,
    )
    run_dir = runs_root(args.vault) / record["run_id"]
    if args.json:
        _print_json(
            {
                "run_dir": str(run_dir),
                "run_id": record["run_id"],
                "source_run_id": record["source_run_id"],
                "prepare_run_id": record["prepare_run_id"],
                "status": record["status"],
                "state": record["state"],
                "selection_policy": record["selection_policy"],
                "stops_after": record["stops_after"],
                "compiled_wiki_write": record["compiled_wiki_write"],
                "human_approval_written": record["human_approval_written"],
                "paper_wiki_invoked": record["paper_wiki_invoked"],
                "processed_count": record["processed_count"],
                "skipped_count": record["skipped_count"],
                "prepared_papers": record["prepared_papers"],
                "manual_downloads": record["manual_downloads"],
                "artifacts": {
                    "record": str(run_dir / "discover-to-handoff-record.json"),
                    "report": str(run_dir / "report.md"),
                    "report_json": str(run_dir / "report.json"),
                    "run_state": str(run_dir / "run-state.json"),
                    **record["artifacts"],
                },
            }
        )
        return int(record.get("exit_status", 0))
    print(f"run_dir={run_dir}")
    print(f"source_run_id={record['source_run_id']}")
    print(f"prepare_run_id={record['prepare_run_id']}")
    print(f"status={record['status']}")
    print(f"selection_policy={record['selection_policy']}")
    print(f"stops_after={record['stops_after']}")
    print(f"compiled_wiki_write={str(record['compiled_wiki_write']).lower()}")
    print(f"processed_count={record['processed_count']}")
    return int(record.get("exit_status", 0))


def _handle_discover_papers(args: argparse.Namespace) -> int:
    sources = [source.strip() for source in args.sources.split(",") if source.strip()] if args.sources else None
    record = discover_papers_workflow.discover_papers(
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
        query_variants=args.query_variant,
        domain_focus_terms=args.domain_focus_term,
        agent_query_plan_json=args.agent_query_plan_json,
        year_min=args.year_min,
        code_policy=args.code_policy,
        query_plan_domain=args.query_plan_domain,
        query_plan_max_queries=args.query_plan_max_queries,
        enable_easyscholar=not args.no_easyscholar,
        selection_policy=args.selection_policy,
        grok_mode=args.grok_mode,
        no_grok_search=args.no_grok_search,
        refresh=args.refresh,
        auto_stage=args.auto_stage,
        max_auto_stage=args.max_auto_stage,
        review_survey_requested=args.review_survey_requested,
        skip_existing=args.skip_existing,
        mineru_command=args.mineru_command,
        mineru_timeout=args.mineru_timeout,
        workflow_mode=args.mode,
    )
    run_dir = runs_root(args.vault) / record["run_id"]
    if args.json:
        _print_json(
            {
                "run_dir": str(run_dir),
                "run_id": record["run_id"],
                "discovery_run_id": record["discovery_run_id"],
                "auto_staging_run_id": record.get("auto_staging_run_id"),
                "status": record["status"],
                "state": record["state"],
                "selection_policy": record["selection_policy"],
                "workflow_mode": record["workflow_mode"],
                "stops_after": record["stops_after"],
                "compiled_wiki_write": record["compiled_wiki_write"],
                "human_approval_written": record["human_approval_written"],
                "paper_wiki_invoked": record["paper_wiki_invoked"],
                "auto_stage": record["auto_stage"],
                "processed_count": record["processed_count"],
                "skipped_count": record["skipped_count"],
                "recommendation_summary": record["recommendation_summary"],
                "auto_staging_plan": record.get("auto_staging_plan"),
                "manual_downloads": record["manual_downloads"],
                "artifacts": {
                    "record": str(run_dir / "discover-papers-record.json"),
                    "report": str(run_dir / "report.md"),
                    "report_json": str(run_dir / "report.json"),
                    "run_state": str(run_dir / "run-state.json"),
                    **record["artifacts"],
                },
            }
        )
        return int(record.get("exit_status", 0))
    print(f"run_dir={run_dir}")
    print(f"discovery_run_id={record['discovery_run_id']}")
    print(f"auto_staging_run_id={record.get('auto_staging_run_id') or 'not_run'}")
    print(f"status={record['status']}")
    print(f"selection_policy={record['selection_policy']}")
    print(f"workflow_mode={record['workflow_mode']}")
    print(f"stops_after={record['stops_after']}")
    print(f"compiled_wiki_write={str(record['compiled_wiki_write']).lower()}")
    print(f"processed_count={record['processed_count']}")
    return int(record.get("exit_status", 0))


def _handle_discovery_benchmark(args: argparse.Namespace) -> int:
    result = run_discovery_benchmark(args.case_json, output_path=args.out)
    if args.json:
        _print_json(result)
    else:
        metrics = result.get("metrics") or {}
        print(f"benchmark_id={result.get('benchmark_id')}")
        print(f"status={result.get('status')}")
        print(f"case_count={metrics.get('case_count', 0)}")
        print(f"benchmark_pass_rate={metrics.get('benchmark_pass_rate', 0)}")
        if result.get("output_path"):
            print(f"output_path={result['output_path']}")
    return 0 if result.get("status") == "pass" else 1


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
        selection_policy=args.selection_policy,
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
                    "selection_policy": batch.get("selection_policy", args.selection_policy),
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
    print(f"selection_policy={batch.get('selection_policy', args.selection_policy)}")
    print(f"processed_count={batch['processed_count']}")
    print(f"stops_after={batch.get('stops_after', 'source-staging')}")
    return 0 if batch["state"] != "prepare_failed" else 1


def _handle_normalize_mineru_assets(args: argparse.Namespace) -> int:
    paper_root = existing_raw_paper_root(args.vault, args.slug)
    record = normalize_mineru_assets(paper_root, execute=args.execute)
    if args.json:
        _print_json(record)
    else:
        print(f"normalization_mode={record['mode']}")
        print(f"paper_root={paper_root}")
        print(f"rename_count={len(record.get('rename_plan') or [])}")
        print(f"dropped_formula_image_count={len(record.get('dropped_formula_images') or [])}")
        print(f"needs_review_count={len(record.get('needs_review') or [])}")
        if record.get("warnings"):
            print("warnings:")
            for warning in record["warnings"]:
                print(f"- {warning}")
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
    if args.mineru_tex is not None and is_nonempty_file(args.mineru_tex):
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


def _render_report_result(result: dict) -> str:
    markdown = result.get("markdown") or ""
    if markdown:
        return markdown.rstrip()
    return json.dumps(result.get("report") or {}, ensure_ascii=False, indent=2)


def _render_config_recover(result: dict) -> str:
    lines = [
        f"candidate_count={result['candidate_count']}",
        f"config_path={result['config_path']}",
    ]
    lines.extend(f"- {candidate['path']}" for candidate in result["candidates"])
    return "\n".join(lines)


def _render_config_restore(result: dict) -> str:
    return "\n".join(
        [
            "config_restore_status=restored",
            f"config_path={result['config_path']}",
            f"restored_from={result['restored_from']}",
        ]
    )


def _render_wiki_reset(result: dict) -> str:
    lines = [
        f"wiki_reset_status={result['status']}",
        f"vault_path={result['vault_path']}",
        f"backup_root={result['backup_root']}",
    ]
    if result["status"] == "preview":
        lines.append(f"preserve_config={str(result['preserve_config']).lower()}")
        lines.append(f"planned_actions={len(result['actions'])}")
    else:
        lines.append(f"preserved_config={str(result['preserved_config']).lower()}")
        lines.append(f"manifest_path={result['manifest_path']}")
    return "\n".join(lines)


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


def _render_repository_migrate(result: dict) -> str:
    lines = [
        f"paper_source_repository_migrate_status={result['status']}",
        f"paper_source_root={result['paper_source_root']}",
        f"actions={len(result['actions'])}",
    ]
    if result.get("manifest_path"):
        lines.append(f"manifest_path={result['manifest_path']}")
    return "\n".join(lines)


def _render_repository_cleanup(result: dict) -> str:
    lines = [
        f"paper_source_repository_cleanup_status={result['status']}",
        f"over_budget={str(bool(result['over_budget'])).lower()}",
        f"actions={len(result['actions'])}",
    ]
    if result.get("manifest_path"):
        lines.append(f"manifest_path={result['manifest_path']}")
    return "\n".join(lines)


def _call_acquire_paper(args: argparse.Namespace) -> dict:
    candidate = read_json(args.candidate)
    record = workflows.acquire_paper_from_candidate(args.vault, candidate)
    return {"record": record, "paper_root": raw_paper_root(args.vault, candidate["slug"])}


def _call_advance_paper(args: argparse.Namespace) -> dict:
    state = workflows.advance_paper_once(
        args.vault,
        read_json(args.candidate),
        mineru_command=args.mineru_command,
        mineru_timeout=args.mineru_timeout,
        workflow_mode=args.mode,
    )
    return {**state, "workflow_mode": state.get("workflow_mode", args.mode)}


def _call_advance_batch(args: argparse.Namespace) -> dict:
    batch = workflows.advance_paper_batch(
        args.vault,
        read_json(args.candidates),
        mineru_command=args.mineru_command,
        max_papers=args.max_papers,
        mineru_timeout=args.mineru_timeout,
        workflow_mode=args.mode,
        selection_policy=args.selection_policy,
    )
    return _batch_output(batch, args)


def _call_advance_ranked(args: argparse.Namespace) -> dict:
    batch = workflows.advance_paper_batch_from_run(
        args.vault,
        args.run_id,
        mineru_command=args.mineru_command,
        max_papers=args.max_papers,
        include_review_candidates=args.include_review_candidates,
        mineru_timeout=args.mineru_timeout,
        workflow_mode=args.mode,
        selection_policy=args.selection_policy,
    )
    return _batch_output(batch, args)


def _batch_output(batch: dict, args: argparse.Namespace) -> dict:
    return {
        **batch,
        "run_dir": runs_root(args.vault) / batch["run_id"],
        "workflow_mode": batch.get("workflow_mode", args.mode),
        "selection_policy": batch.get("selection_policy", args.selection_policy),
    }


def _render_advance_paper(state: dict) -> str:
    lines = [
        f"paper_state={state['state']}",
        f"last_action={state['last_action']}",
        f"workflow_mode={state['workflow_mode']}",
    ]
    if state.get("next_action"):
        lines.append(f"next_action={state['next_action']}")
    return "\n".join(lines)


def _render_advance_batch(batch: dict) -> str:
    return "\n".join(
        [
            f"run_dir={batch['run_dir']}",
            f"batch_state={batch['state']}",
            f"workflow_mode={batch['workflow_mode']}",
            f"selection_policy={batch['selection_policy']}",
            f"processed_count={batch['processed_count']}",
        ]
    )


def _render_parse_paper(record: dict) -> str:
    lines = [f"parse_status={record['status']}"]
    if record.get("batch_id"):
        lines.append(f"batch_id={record['batch_id']}")
    return "\n".join(lines)


def _select_output(result: dict, selector: str | object) -> object:
    if callable(selector):
        return selector(result)
    value: object = result
    for part in str(selector).split("."):
        if not isinstance(value, dict):
            raise TypeError(f"cannot read {selector!r} from non-object output")
        value = value[part]
    return value


def _render_outputs(result: dict, outputs: tuple[tuple[str, str | object], ...]) -> str:
    return "\n".join(f"{key}={_select_output(result, selector)}" for key, selector in outputs)


_TABLE_DRIVEN_COMMANDS = {
    "ingest-one": {
        "call": lambda args: workflows.run_one_paper_ingest(
            vault_path=args.vault,
            candidate=read_json(args.candidate),
            pdf_path=args.pdf,
            mineru_markdown_path=args.mineru_md,
            mineru_tex_path=args.mineru_tex,
            mineru_images_dir=args.mineru_images,
            workflow_mode=args.mode,
        ),
        "outputs": (("paper_root", "paper_root"), ("staging_root", "staging_root")),
    },
    "acquire-paper": {
        "call": _call_acquire_paper,
        "outputs": (("acquire_status", "record.status"), ("paper_root", "paper_root")),
        "exit_status": lambda result: 0 if result["record"]["status"] == "success" else 1,
    },
    "advance-paper": {
        "call": _call_advance_paper,
        "render": _render_advance_paper,
        "exit_status": lambda result: 0 if not result["state"].endswith("_failed") else 1,
    },
    "advance-batch": {
        "call": _call_advance_batch,
        "render": _render_advance_batch,
        "exit_status": lambda result: 0 if result["state"] != "batch_failed" else 1,
    },
    "advance-ranked": {
        "call": _call_advance_ranked,
        "render": _render_advance_batch,
        "exit_status": lambda result: 0 if result["state"] != "batch_failed" else 1,
    },
    "parse-paper": {
        "call": lambda args: workflows.parse_paper_with_mineru(
            args.vault, args.slug, mineru_command=args.mineru_command, mineru_timeout=args.mineru_timeout
        ),
        "render": _render_parse_paper,
        "exit_status": lambda result: 0 if result["status"] == "success" else 1,
    },
    "config-recover": {
        "call": lambda args: recover_config_candidates(args.vault, backup_root=args.backup_root),
        "render": _render_config_recover,
    },
    "config-restore": {
        "call": lambda args: restore_config_from_file(args.vault, args.source_path, confirmed_by=args.confirmed_by),
        "render": _render_config_restore,
    },
    "wiki-reset": {
        "call": lambda args: reset_wiki_vault(
            args.vault,
            confirmed_by=args.confirmed_by,
            reset_config_confirmed_by=args.reset_config_confirmed_by,
            backup_root=args.backup_root,
            no_backup=args.no_backup,
            preview=args.preview,
        ),
        "render": _render_wiki_reset,
    },
    "evolution-query": {
        "call": lambda args: workflows.query_evolution(args.vault.resolve(), status=args.status, limit=args.limit),
        "render": workflows.render_evolution_query,
    },
    "runs-query": {
        "call": lambda args: workflows.query_runs(
            args.vault.resolve(),
            failed=args.failed,
            human_gate=args.human_gate,
            workflow=args.workflow,
            latest_success=args.latest_success,
            limit=args.limit,
        ),
        "render": workflows.render_runs_query,
    },
    "report": {
        "call": lambda args: load_run_report(args.vault, args.run_id),
        "render": _render_report_result,
    },
    "run-lifecycle": {
        "call": lambda args: workflows.prune_run_lifecycle(
            args.vault.resolve(),
            keep_latest=args.keep_latest,
            keep_per_workflow=args.keep_per_workflow,
            max_age_days=args.max_age_days,
            apply=args.apply,
        ),
        "render": workflows.render_run_lifecycle,
    },
    "paper-source-repository-migrate": {
        "call": lambda args: migrate_legacy_paper_source_roots(args.vault, dry_run=args.preview),
        "render": _render_repository_migrate,
    },
    "paper-source-repository-cleanup": {
        "call": lambda args: cleanup_paper_source_repository(args.vault, dry_run=args.preview),
        "render": _render_repository_cleanup,
    },
    "zotero-sync": {
        "call": lambda args: workflows.sync_zotero_record(
            args.paper_root,
            enabled=args.enabled,
            collection=args.collection,
            item_key=args.item_key,
        ),
        "outputs": (("zotero_status", "status"),),
    },
    "record-feedback": {
        "call": lambda args: workflows.record_feedback(
            args.vault,
            feedback_type=args.type,
            target=args.target,
            message=args.message,
            source=args.source,
        ),
        "outputs": (("feedback_id", "id"),),
    },
    "propose-evolution": {
        "call": lambda args: workflows.propose_evolution(
            args.vault,
            reflection_type=args.reflection_type,
            target_asset=args.target_asset,
            rationale=args.rationale,
            proposed_change=json.loads(args.proposed_change_json),
            evidence=args.evidence,
            evidence_type=args.evidence_type,
            before_metrics=json.loads(args.before_metrics_json) if args.before_metrics_json else None,
            acceptance_gates=json.loads(args.acceptance_gates_json) if args.acceptance_gates_json else None,
            risk_level=args.risk_level,
        ),
        "outputs": (("proposal_id", "id"),),
    },
    "activate-evolution": {
        "call": lambda args: workflows.activate_evolution(
            args.vault,
            args.proposal_id,
            approved=args.approved,
            validation_result=json.loads(args.validation_result_json) if args.validation_result_json else None,
        ),
        "outputs": (("evolution_status", "status"),),
    },
    "research-queue": {
        "call": lambda args: workflows.query_research_queue(
            args.vault.resolve(),
            bucket=args.bucket,
            limit=args.limit,
            include_actions=args.actions,
        ),
        "render": workflows.render_research_queue_query,
    },
    "wiki-query": {
        "call": lambda args: workflows.query_wiki(
            args.vault.resolve(),
            consensus=args.consensus,
            role=args.role,
            verdict=args.verdict,
            warning_reviewer=args.warning_reviewer,
            blocking_lens=args.blocking_lens,
            limit=args.limit,
        ),
        "render": workflows.render_wiki_query,
    },
    "wiki-ask": {
        "call": lambda args: workflows.ask_wiki(
            args.vault.resolve(),
            question=args.question,
            limit=args.limit,
            max_hops=args.max_hops,
        ),
        "render": workflows.render_wiki_ask,
    },
    "wiki-ingest-handoff": {
        "call": lambda args: workflows.build_wiki_ingest_handoff(args.vault.resolve(), args.slug),
        "render": workflows.render_wiki_ingest_handoff,
    },
    "wiki-ingest-trigger": {
        "call": lambda args: workflows.build_wiki_ingest_trigger(args.vault.resolve(), args.slug),
        "render": workflows.render_wiki_ingest_trigger,
        "exit_status": lambda result: 0 if result.get("status") in {"ready", "already_recorded"} else 1,
    },
    "record-human-approval": {
        "call": lambda args: workflows.record_human_approval(
            args.vault.resolve(),
            args.slug,
            approved_by=args.approved_by,
            scope=args.scope,
            notes=args.notes,
            automation_mode=args.automation_mode,
            automation_task_id=args.automation_task_id,
            automation_task_source=args.automation_task_source,
            automation_authorization=args.automation_authorization,
        ),
        "outputs": (
            ("approval_status", "record.status"),
            ("approval_path", "record_path"),
            ("run_dir", "run_dir"),
        ),
    },
    "record-wiki-ingest": {
        "call": lambda args: workflows.record_wiki_ingest(
            args.vault.resolve(),
            args.slug,
            args.page or [],
            approved_by=args.approved_by,
            notes=args.notes,
            source_review_path=args.source_review,
            from_paper_wiki_request=args.from_paper_wiki_request,
        ),
        "outputs": (
            ("record_status", "record.status"),
            ("record_path", "record_path"),
            ("recorded_pages", lambda result: len(result["record"]["page_records"])),
            ("run_dir", "run_dir"),
        ),
    },
    "paper-gate": {
        "call": lambda args: workflows.build_paper_gate(args.vault.resolve(), args.slug),
        "render": workflows.render_paper_gate,
    },
}


def _handle_table_driven(args: argparse.Namespace) -> int:
    spec = _TABLE_DRIVEN_COMMANDS[args.command]
    result = spec["call"](args)
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render = spec.get("render")
        print(render(result) if render else _render_outputs(result, spec["outputs"]))
    exit_status = spec.get("exit_status")
    return int(exit_status(result)) if exit_status else 0


HANDLERS = cli_routes.bind_handlers(globals())


def main(argv: list[str] | None = None) -> int:
    apply_runtime_config()
    args = build_parser().parse_args(argv)
    return cli_routes.dispatch(args, HANDLERS)
