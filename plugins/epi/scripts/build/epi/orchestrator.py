from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from epi.acquire_papers import acquire_paper, acquire_paper_from_url
from epi.artifacts import (
    file_sha256,
    json_sha256,
    raw_paper_root,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)
from epi.config import load_config, load_wiki_config
from epi.feedback import record_feedback
from epi.evaluation_loop import build_improvement_brief, render_improvement_brief, write_improvement_brief
from epi.filter_candidates import default_discovery_exclusion_terms, filter_candidates, filter_candidates_with_report
from epi.generate_reader import generate_reader_outputs
from epi.normalize_candidates import normalize_candidates
from epi.paper_gate import build_paper_gate, render_paper_gate
from epi.paper_library import load_existing_paper_index
from epi.paper_search_adapter import discover
from epi.promote_to_wiki import promote_paper, rollback_promotion
from epi.query_planner import build_query_plan, infer_research_mode, topic_focus_terms
from epi.rank_papers import rank_candidates
from epi.redo import redo_acquire, redo_parse, redo_read, redo_read_recritic, recritic
from epi.report_run import write_report
from epi.run_index import (
    auto_prune_run_lifecycle,
    prune_run_lifecycle,
    query_research_queue,
    query_runs,
    refresh_run_index,
    render_research_queue_query,
    render_run_lifecycle,
    render_runs_query,
)
from epi.run_critic import run_critics
from epi.run_mineru_parse import materialize_mineru_fixture, run_mineru_command
from epi.skill_aware_evolve import activate_evolution, propose_evolution, query_evolution, render_evolution_query
from epi.stage_wiki import stage_paper
from epi.wiki_ingest_approval import create_human_approval_record, human_approval_record_path
from epi.wiki_ingest_handoff import build_wiki_ingest_handoff, render_wiki_ingest_handoff
from epi.wiki_ingest_record import create_wiki_ingest_record
from epi.wiki_query import query_wiki, render_wiki_query
from epi.wiki_init import initialize_paper_wiki
from epi.zotero_sync import sync_zotero_record

_LOCAL_TOOL_VERSION = "epi-local"


def _write_json(path: Path, payload: object) -> None:
    write_json_atomic(path, payload)


def _refresh_run_index(vault_path: Path) -> None:
    refresh_run_index(vault_path.resolve())


def _auto_manage_run_lifecycle(vault_path: Path) -> dict:
    return auto_prune_run_lifecycle(
        vault_path.resolve(),
        keep_latest=15,
        keep_per_workflow=2,
    )


def _hash_existing_outputs(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in paths.items():
        if path.exists():
            hashes[name] = file_sha256(path)
    return hashes


def _zotero_record_only(vault_path: Path, paper_root: Path) -> dict:
    config = load_wiki_config(vault_path) or {}
    zotero_config = config.get("zotero") if isinstance(config.get("zotero"), dict) else {}
    enabled = bool(zotero_config.get("enabled", False))
    collection = str(zotero_config.get("collection") or "EPI")
    reason = "zotero_not_configured" if not config else "zotero_disabled"
    return sync_zotero_record(
        paper_root,
        enabled=enabled,
        collection=collection,
        mode="record-only",
        reason=reason,
    )


def _tool_versions(*tool_names: str) -> dict[str, str]:
    return {tool_name: _LOCAL_TOOL_VERSION for tool_name in tool_names}


def _new_run_dir(vault_path: Path, prefix: str | None = None) -> tuple[str, Path]:
    runs_dir = vault_path.resolve() / "_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{prefix}-{timestamp}" if prefix else timestamp
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _build_dry_run_query_plan(query: str, *, domain: str, max_queries: int, config) -> dict:
    return build_query_plan(
        topic=query,
        domain=domain,
        max_queries=max(1, max_queries),
        profile=config.profile,
        domains=config.domains,
        positive_keywords=config.positive_keywords,
        negative_keywords=config.negative_keywords,
        venue_prior=config.venue_prior,
    )


def _ranking_keywords_from_profile(config, query: str, query_plan: dict | None) -> list[str]:
    keywords: list[str] = []
    keywords.extend(config.positive_keywords)
    keywords.extend(config.domains)
    keywords.extend(topic_focus_terms(query))
    if not keywords:
        keywords.extend(
            word
            for word in query.replace("-", " ").replace("/", " ").split()
            if len(word) > 2 and word.lower() not in {"latest", "recent", "paper", "papers", "quality"}
        )

    seen: set[str] = set()
    unique_keywords: list[str] = []
    for keyword in keywords:
        normalized = " ".join(str(keyword).lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_keywords.append(str(keyword))
    return unique_keywords


def _venue_tiers_from_profile(config, query_plan: dict | None) -> dict[str, float]:
    venues: list[str] = []
    venues.extend(config.venue_prior)
    if query_plan:
        recall = query_plan.get("recall_gap_checks") or {}
        venue_families = recall.get("venue_families") or []
        if isinstance(venue_families, list):
            venues.extend(
                str(venue)
                for venue in venue_families
                if "configured" not in str(venue).lower() and "field-specific" not in str(venue).lower()
            )

    tiers: dict[str, float] = {}
    for index, venue in enumerate(venues):
        normalized = str(venue).lower()
        if not normalized or normalized in tiers:
            continue
        tiers[normalized] = max(0.75, 1.0 - index * 0.02)
    return tiers


def _filter_domains_from_profile(config, query_plan: dict | None) -> list[str]:
    if query_plan:
        blocks = query_plan.get("concept_blocks") or {}
        domain_focus_terms = blocks.get("domain_focus_terms") or []
        if isinstance(domain_focus_terms, list) and domain_focus_terms:
            return [str(term) for term in domain_focus_terms]
        domain_terms = blocks.get("domain_terms") or []
        if isinstance(domain_terms, list):
            return [str(term) for term in domain_terms]
    if config.domains:
        return config.domains
    return []


def _annotate_query_records(records: list[dict], *, query_variant: str, query_variant_index: int) -> list[dict]:
    annotated: list[dict] = []
    for record in records:
        enriched = dict(record)
        enriched["query_variant"] = query_variant
        enriched["query_variant_index"] = query_variant_index
        annotated.append(enriched)
    return annotated


def _merged_source_mode(query_records: list[dict]) -> str:
    modes = sorted({str(record.get("source_mode") or "unknown") for record in query_records})
    if not modes:
        return "query_plan_multi_query"
    if len(modes) == 1:
        return modes[0]
    return "query_plan_mixed"


def _run_query_plan_discovery(
    *,
    query: str,
    query_plan: dict | None,
    max_results: int,
    fixture_path: Path | None,
    command: str | None,
    sources: list[str],
    run_dir: Path,
) -> dict:
    if fixture_path is not None or not query_plan:
        search_record = discover(
            query=query,
            max_results=max_results,
            fixture_path=fixture_path,
            command=command,
            sources=sources,
            raw_response_path=run_dir / "paper-search-raw.json",
        )
        if query_plan:
            search_record["query_plan"] = query_plan
            search_record["query_strategy"] = "fixture_single_query" if fixture_path is not None else "single_query"
        return search_record

    query_variants = query_plan.get("query_variants") or [query]
    query_records: list[dict] = []
    combined_records: list[dict] = []
    query_errors: list[str] = []
    for index, query_variant in enumerate(query_variants, start=1):
        raw_path = run_dir / f"paper-search-raw-{index:02d}.json"
        search_record = discover(
            query=query_variant,
            max_results=max_results,
            fixture_path=None,
            command=command,
            sources=sources,
            raw_response_path=raw_path,
        )
        if search_record.get("error"):
            query_errors.append(f"{query_variant}: {search_record['error']}")
        query_records.append(
            {
                "index": index,
                "query": query_variant,
                "source_mode": search_record.get("source_mode"),
                "record_count": len(search_record.get("records") or []),
                "raw_response_path": search_record.get("raw_response_path"),
                "error": search_record.get("error"),
                "upstream": search_record.get("upstream", {}),
            }
        )
        combined_records.extend(
            _annotate_query_records(
                search_record.get("records") or [],
                query_variant=query_variant,
                query_variant_index=index,
            )
        )

    aggregate_raw_path = run_dir / "paper-search-raw.json"
    _write_json(
        aggregate_raw_path,
        {
            "query": query,
            "query_strategy": "query_plan_multi_query",
            "query_plan": query_plan,
            "query_records": query_records,
            "raw_candidate_count": len(combined_records),
        },
    )
    combined = {
        "query": query,
        "max_results": max_results,
        "source_mode": _merged_source_mode(query_records),
        "query_strategy": "query_plan_multi_query",
        "query_plan": query_plan,
        "query_records": query_records,
        "raw_response_path": str(aggregate_raw_path),
        "records": combined_records,
    }
    if query_errors and not combined_records:
        combined["error"] = "; ".join(query_errors)
    elif query_errors:
        combined["warnings"] = query_errors
    return combined


def _append_report_sections(
    report_md_path: Path,
    *,
    human_gate: dict | None = None,
    wiki_pages_written: list[str] | None = None,
    restored_paths: list[str] | None = None,
    removed_paths: list[str] | None = None,
) -> None:
    existing = report_md_path.read_text(encoding="utf-8").rstrip()
    sections: list[str] = []
    if human_gate is not None:
        sections.extend(
            [
                "## Human Gate",
                f"- status: {human_gate.get('status')}",
                f"- approved_by: {human_gate.get('approved_by')}",
                f"- approved_at: {human_gate.get('approved_at')}",
            ]
        )
    if wiki_pages_written is not None:
        sections.append("## Wiki Pages Written")
        if wiki_pages_written:
            sections.extend(f"- {path}" for path in wiki_pages_written)
        else:
            sections.append("- None.")
    if restored_paths is not None:
        sections.append("## Restored Paths")
        if restored_paths:
            sections.extend(f"- {path}" for path in restored_paths)
        else:
            sections.append("- None.")
    if removed_paths is not None:
        sections.append("## Removed Paths")
        if removed_paths:
            sections.extend(f"- {path}" for path in removed_paths)
        else:
            sections.append("- None.")
    if sections:
        write_text_atomic(report_md_path, existing + "\n\n" + "\n".join(sections) + "\n")


def _append_revision_delta_section(report_md_path: Path, revision_delta: dict | None) -> None:
    if not revision_delta:
        return
    existing = report_md_path.read_text(encoding="utf-8").rstrip()
    before = revision_delta.get("before") or {}
    after = revision_delta.get("after") or {}
    lines = [
        "## Revision Delta",
        f"- before blocking repairs: {before.get('blocking_count', 0)}",
        f"- before warning follow-ups: {before.get('warning_count', 0)}",
        f"- after blocking repairs: {after.get('blocking_count', 0)}",
        f"- after warning follow-ups: {after.get('warning_count', 0)}",
        "- resolved blocking checks: "
        + (", ".join(revision_delta.get("resolved_blocking_checks") or []) or "None"),
        "- remaining blocking checks: "
        + (", ".join(revision_delta.get("remaining_blocking_checks") or []) or "None"),
        "- remaining warning checks: "
        + (", ".join(revision_delta.get("remaining_warning_checks") or []) or "None"),
    ]
    write_text_atomic(report_md_path, existing + "\n\n" + "\n".join(lines) + "\n")


def _write_promotion_or_rollback_run_state(
    run_dir: Path,
    *,
    run_id: str,
    workflow_type: str,
    vault_path: Path,
    slug: str,
    started_at: str,
    finished_at: str,
    input_artifact_hashes: dict[str, str],
    output_artifact_hashes: dict[str, str],
    zotero_results: dict | None = None,
) -> None:
    state = {
        "stage": workflow_type,
        "run_id": run_id,
        "workflow_type": workflow_type,
        "state": "reported",
        "status": "success",
        "paper_slug": slug,
        "vault_path": str(vault_path),
        "compiled_wiki_write": True,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_status": 0,
        "tool_versions": _tool_versions("orchestrator", "report_run", "promote_to_wiki"),
        "input_artifact_hashes": input_artifact_hashes,
        "output_artifact_hashes": output_artifact_hashes,
    }
    if zotero_results is not None:
        state["zotero_results"] = zotero_results
    _write_json(run_dir / "run-state.json", state)


def _write_wiki_ingest_record_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    record: dict,
    zotero_results: dict,
) -> None:
    next_actions = ["review-recorded-wiki-pages"]
    page_paths = record.get("relative_page_paths") or record.get("page_paths") or []
    human_gate = record.get("human_gate_decision") or {}
    changed_artifacts = [
        f"_raw/papers/{slug}/wiki-ingest-record.json",
        f"_staging/papers/{slug}/wiki-ingest-record.json",
    ]
    report_paper_states = [
        {
            "slug": slug,
            "paper_slug": slug,
            "title": record.get("title") or slug,
            "state": "wiki_ingest_recorded",
            "last_action": "record-wiki-ingest",
            "next_action": next_actions[0],
            "human_gate_required": False,
        }
    ]
    write_report(
        run_dir,
        [{"slug": slug, "title": record.get("title") or slug, "state": "wiki_ingest_recorded"}],
        [],
        workflow_type="record-wiki-ingest",
        run_id=run_id,
        paper_states=report_paper_states,
        failed_papers=[],
        budget_usage={"paper_count": 1, "recorded_page_count": len(page_paths)},
        wiki_pages_written=page_paths,
        zotero_results=zotero_results,
        next_actions=next_actions,
        human_gate=human_gate,
        changed_artifacts=changed_artifacts,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {"paper_slug": slug, "state": "wiki_ingest_recorded", "next_action": next_actions[0]}
    ]
    report_payload["failed_papers"] = []
    report_payload["wiki_pages_written"] = page_paths
    report_payload["changed_artifacts"] = changed_artifacts
    report_payload["human_gate"] = human_gate
    report_payload["next_actions"] = next_actions
    report_payload["wiki_ingest_record"] = record
    report_payload["page_records"] = record.get("page_records") or []
    report_payload["zotero_results"] = zotero_results
    _write_json(report_json_path, report_payload)


def _write_human_approval_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    record: dict,
) -> None:
    report_md_path = run_dir / "report.md"
    report_json_path = run_dir / "report.json"
    lines = [
        f"# EPI Human Approval - {slug}",
        "",
        f"- run_id: {run_id}",
        "- workflow_type: record-human-approval",
        f"- status: {record.get('status')}",
        f"- approved_by: {record.get('approved_by')}",
        f"- scope: {record.get('scope')}",
        f"- approval_path: {record.get('record_path')}",
        "",
    ]
    write_text_atomic(report_md_path, "\n".join(lines))
    _write_json(
        report_json_path,
        {
            "schema_version": "epi-human-approval-report-v1",
            "run_id": run_id,
            "workflow_type": "record-human-approval",
            "paper_slug": slug,
            "status": record.get("status"),
            "human_approval_record": record,
        },
    )


def record_human_approval(
    vault_path: Path,
    slug: str,
    *,
    approved_by: str,
    scope: str,
    notes: str | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    gate = build_paper_gate(vault_path, slug)
    record = create_human_approval_record(
        vault_path,
        slug,
        approved_by=approved_by,
        scope=scope,
        notes=notes,
        gate=gate,
    )
    record_path = human_approval_record_path(vault_path, slug)
    record["record_path"] = str(record_path)
    run_id, run_dir = _new_run_dir(vault_path, "record-human-approval")
    _write_human_approval_report(run_dir, run_id=run_id, slug=slug, record=record)
    _write_json(
        run_dir / "run-state.json",
        {
            "stage": "record-human-approval",
            "run_id": run_id,
            "workflow_type": "record-human-approval",
            "state": "human_approved_for_wiki_ingest",
            "status": "success",
            "paper_slug": slug,
            "vault_path": str(vault_path),
            "compiled_wiki_write": False,
            "record_only": True,
            "finished_at": utc_now(),
            "tool_versions": _tool_versions("orchestrator", "wiki_ingest_approval"),
            "output_artifact_hashes": _hash_existing_outputs(
                {
                    "human-approval.json": record_path,
                    "report.md": run_dir / "report.md",
                    "report.json": run_dir / "report.json",
                }
            ),
        },
    )
    paper_root = raw_paper_root(vault_path, slug)
    _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="human_approved_for_wiki_ingest",
            last_action="record-human-approval",
            next_action="run-wiki-ingest-agent",
            stage_record=record,
            human_gate_required=False,
        ),
    )
    _refresh_run_index(vault_path)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "record": record,
        "record_path": str(record_path),
    }


def record_wiki_ingest(
    vault_path: Path,
    slug: str,
    pages: list[str],
    *,
    approved_by: str,
    notes: str | None = None,
    source_review_path: str | Path | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    run_id, run_dir = _new_run_dir(vault_path, "record-wiki-ingest")
    started_at = utc_now()
    record = create_wiki_ingest_record(
        vault_path,
        slug,
        pages,
        approved_by=approved_by,
        notes=notes,
        source_review_path=source_review_path,
    )
    paper_root = raw_paper_root(vault_path, slug)
    staging_root = vault_path / "_staging" / "papers" / slug
    raw_record_path = paper_root / "wiki-ingest-record.json"
    staging_record_path = staging_root / "wiki-ingest-record.json"
    plan_path = staging_root / "promotion-plan.json"
    brief_path = Path(record.get("paths", {}).get("wiki_ingest_brief") or staging_root / "wiki-ingest-brief.json")
    final_source_review_value = record.get("paths", {}).get("final_source_review")
    final_source_review_path = Path(final_source_review_value) if final_source_review_value else None
    final_page_hashes = {
        f"final_page:{page['relative_path']}": page["sha256"]
        for page in record.get("page_records") or []
    }
    input_artifacts = {
        "promotion-plan.json": plan_path,
        "wiki-ingest-brief.json": brief_path,
        **{
            f"final_page:{page['relative_path']}": Path(page["path"])
            for page in record.get("page_records") or []
        },
    }
    if final_source_review_path is not None:
        input_artifacts["final-source-review.json"] = final_source_review_path
    zotero_results = _zotero_record_only(vault_path, paper_root)
    _write_wiki_ingest_record_report(
        run_dir,
        run_id=run_id,
        slug=slug,
        record=record,
        zotero_results=zotero_results,
    )
    _write_json(
        run_dir / "run-state.json",
        {
            "stage": "record-wiki-ingest",
            "run_id": run_id,
            "workflow_type": "record-wiki-ingest",
            "state": "wiki_ingest_recorded",
            "status": "success",
            "paper_slug": slug,
            "vault_path": str(vault_path),
            "compiled_wiki_write": False,
            "record_only": True,
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_status": 0,
            "tool_versions": _tool_versions("orchestrator", "wiki_ingest_record", "report_run"),
            "input_artifact_hashes": _hash_existing_outputs(input_artifacts),
            "final_page_hashes": final_page_hashes,
            "output_artifact_hashes": _hash_existing_outputs(
                {
                    "wiki-ingest-record.raw.json": raw_record_path,
                    "wiki-ingest-record.staging.json": staging_record_path,
                    "zotero-record.json": paper_root / "zotero-record.json",
                    "report.md": run_dir / "report.md",
                    "report.json": run_dir / "report.json",
                }
            ),
            "zotero_results": zotero_results,
        },
    )
    _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="wiki_ingest_recorded",
            last_action="record-wiki-ingest",
            next_action="review-recorded-wiki-pages",
            stage_record=record,
            human_gate_required=False,
        ),
    )
    _refresh_run_index(vault_path)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "record": record,
        "record_path": str(raw_record_path),
        "staging_record_path": str(staging_record_path),
        "zotero_results": zotero_results,
        "zotero_record_path": str(paper_root / "zotero-record.json"),
    }


def _write_promotion_routed_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    promoted_page_paths: list[str],
    human_gate: dict,
    zotero_results: dict,
) -> None:
    next_actions = ["review-promoted-pages"]
    report_paper_states = [
        {
            "slug": slug,
            "paper_slug": slug,
            "title": slug,
            "state": "promoted",
            "last_action": "promote-to-wiki",
            "next_action": next_actions[0],
            "human_gate_required": False,
        }
    ]
    write_report(
        run_dir,
        [{"slug": slug, "title": slug, "state": "promoted"}],
        [],
        workflow_type="promote-to-wiki",
        run_id=run_id,
        paper_states=report_paper_states,
        failed_papers=[],
        budget_usage={},
        wiki_pages_written=promoted_page_paths,
        zotero_results=zotero_results,
        next_actions=next_actions,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {"paper_slug": slug, "state": "promoted", "next_action": next_actions[0]}
    ]
    report_payload["failed_papers"] = []
    report_payload["wiki_pages_written"] = promoted_page_paths
    report_payload["human_gate"] = human_gate
    report_payload["next_actions"] = next_actions
    report_payload["zotero_results"] = zotero_results
    _write_json(report_json_path, report_payload)
    _append_report_sections(
        run_dir / "report.md",
        human_gate=human_gate,
        wiki_pages_written=promoted_page_paths,
    )


def _write_rollback_routed_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    human_gate: dict | None,
    restored_paths: list[str],
    removed_paths: list[str],
) -> None:
    next_actions = ["re-review-before-repromote"]
    report_paper_states = [
        {
            "slug": slug,
            "paper_slug": slug,
            "title": slug,
            "state": "rolled_back",
            "last_action": "rollback-promotion",
            "next_action": next_actions[0],
            "human_gate_required": False,
        }
    ]
    write_report(
        run_dir,
        [],
        [],
        workflow_type="rollback-promotion",
        run_id=run_id,
        paper_states=report_paper_states,
        failed_papers=[],
        budget_usage={},
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {"paper_slug": slug, "state": "rolled_back", "next_action": next_actions[0]}
    ]
    report_payload["failed_papers"] = []
    report_payload["wiki_pages_written"] = []
    report_payload["restored_paths"] = restored_paths
    report_payload["removed_paths"] = removed_paths
    report_payload["next_actions"] = next_actions
    if human_gate is not None:
        report_payload["human_gate"] = human_gate
    _write_json(report_json_path, report_payload)
    _append_report_sections(
        run_dir / "report.md",
        human_gate=human_gate,
        wiki_pages_written=[],
        restored_paths=restored_paths,
        removed_paths=removed_paths,
    )


def _paper_title(vault_path: Path, slug: str) -> str:
    metadata_path = raw_paper_root(vault_path, slug) / "metadata.json"
    if not metadata_path.exists():
        return slug
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return slug
    return metadata.get("title") or slug


def _repair_report_contract(vault_path: Path, slug: str, record: dict) -> tuple[dict, list[str], list[str]]:
    stage = record["stage"]
    if stage == "redo-acquire":
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reacquired",
                "last_action": "redo-acquire",
                "next_action": "redo-parse",
                "human_gate_required": False,
            },
            ["paper.pdf"],
            ["redo-parse the reacquired PDF"],
        )
    if stage == "redo-parse":
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reparsed",
                "last_action": "redo-parse",
                "next_action": "redo-read",
                "human_gate_required": False,
            },
            ["mineru/paper.md", "mineru/paper.tex"],
            ["redo-read the reparsed paper"],
        )
    if stage == "redo-read":
        changed_artifacts = [
            "reader/reader.md",
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/figures.md",
            "reader/reproducibility.md",
            "reader/implementation-ideas.md",
        ]
        guidance_path = raw_paper_root(vault_path, slug) / "reader" / "revision-guidance.md"
        if guidance_path.exists():
            changed_artifacts.append("reader/revision-guidance.md")
        changed_artifacts.append("reader/evidence-map.json")
        changed_artifacts.append("reader/claim-support.json")
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reader_regenerated",
                "last_action": "redo-read",
                "next_action": "recritic",
                "human_gate_required": False,
            },
            changed_artifacts,
            ["recritic the regenerated reader outputs"],
        )
    if stage == "recritic":
        critic_report_path = raw_paper_root(vault_path, slug) / "critic" / "critic-report.json"
        critic_report = json.loads(critic_report_path.read_text(encoding="utf-8"))
        next_action = critic_report.get("next_action", "stage")
        state = "critic_passed" if next_action == "stage" else "critic_failed"
        next_actions = (
            ["stage the paper for promotion review"]
            if next_action == "stage"
            else ["revise the reader outputs before another critic pass"]
        )
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": state,
                "last_action": "recritic",
                "next_action": next_action,
                "human_gate_required": False,
            },
            ["critic/critic-report.json"],
            next_actions,
        )
    if stage == "redo-read-recritic":
        critic_report_path = raw_paper_root(vault_path, slug) / "critic" / "critic-report.json"
        critic_report = json.loads(critic_report_path.read_text(encoding="utf-8"))
        next_action = critic_report.get("next_action", "stage")
        state = "critic_passed" if next_action == "stage" else "critic_failed"
        next_actions = (
            ["stage the paper for promotion review"]
            if next_action == "stage"
            else ["revise the reader outputs before another critic pass"]
        )
        changed_artifacts = [
            "reader/reader.md",
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/figures.md",
            "reader/reproducibility.md",
            "reader/implementation-ideas.md",
            "reader/revision-guidance.md",
            "reader/evidence-map.json",
            "reader/claim-support.json",
            "critic/critic-report.json",
            "critic/critic-quorum.json",
            "critic/research-decision.json",
            "critic/research-decision.md",
            "critic/reader-revision-plan.json",
            "critic/reader-revision-plan.md",
        ]
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": state,
                "last_action": "redo-read-recritic",
                "next_action": next_action,
                "human_gate_required": False,
            },
            changed_artifacts,
            next_actions,
        )
    raise ValueError(f"unsupported repair stage: {stage}")


def _write_repair_run_state(
    run_dir: Path,
    *,
    run_id: str,
    workflow_type: str,
    vault_path: Path,
    slug: str,
    state: str,
    status: str,
    started_at: str,
    input_artifact_hashes: dict[str, str],
    changed_artifacts: list[str],
) -> None:
    paper_root = raw_paper_root(vault_path, slug)
    output_paths = {
        artifact: paper_root / artifact
        for artifact in changed_artifacts
    }
    output_paths["redo-records.jsonl"] = paper_root / "redo-records.jsonl"
    output_paths["report.md"] = run_dir / "report.md"
    output_paths["report.json"] = run_dir / "report.json"
    _write_json(
        run_dir / "run-state.json",
        {
            "stage": workflow_type,
            "run_id": run_id,
            "workflow_type": workflow_type,
            "state": state,
            "status": status,
            "paper_slug": slug,
            "vault_path": str(vault_path.resolve()),
            "compiled_wiki_write": False,
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_status": 0 if status == "success" else 1,
            "tool_versions": _tool_versions("orchestrator", "report_run", "redo"),
            "input_artifact_hashes": input_artifact_hashes,
            "output_artifact_hashes": _hash_existing_outputs(output_paths),
        },
    )


def _write_repair_routed_report(
    vault_path: Path,
    slug: str,
    record: dict,
    *,
    started_at: str,
    input_artifact_hashes: dict[str, str],
) -> None:
    workflow_type = record["stage"]
    run_id, run_dir = _new_run_dir(vault_path.resolve(), workflow_type)
    paper_state, changed_artifacts, next_actions = _repair_report_contract(vault_path, slug, record)
    write_report(
        run_dir,
        [],
        [],
        workflow_type=workflow_type,
        run_id=run_id,
        paper_states=[paper_state],
        failed_papers=[],
        budget_usage={"paper_count": 1},
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        changed_artifacts=changed_artifacts,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["paper_states"] = [
        {
            "paper_slug": slug,
            "state": paper_state["state"],
            "next_action": paper_state["next_action"],
        }
    ]
    report_payload["failed_papers"] = []
    report_payload["changed_artifacts"] = changed_artifacts
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    if record.get("revision_delta"):
        report_payload["revision_delta"] = record["revision_delta"]
    _write_json(report_json_path, report_payload)
    _append_revision_delta_section(run_dir / "report.md", record.get("revision_delta"))
    _write_repair_run_state(
        run_dir,
        run_id=run_id,
        workflow_type=workflow_type,
        vault_path=vault_path,
        slug=slug,
        state=paper_state["state"],
        status=record.get("status", "success"),
        started_at=started_at,
        input_artifact_hashes=input_artifact_hashes,
        changed_artifacts=changed_artifacts,
    )
    paper_root = raw_paper_root(vault_path.resolve(), slug)
    if workflow_type in {"recritic", "redo-read-recritic"}:
        stage_record = json.loads((paper_root / "critic" / "critic-report.json").read_text(encoding="utf-8"))
    else:
        stage_record = record
    _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state=paper_state["state"],
            last_action=paper_state["last_action"],
            next_action=paper_state["next_action"],
            stage_record=stage_record,
            human_gate_required=paper_state.get("human_gate_required", False),
        ),
    )
    _refresh_run_index(vault_path)


def run_dry_run(
    plugin_root: Path,
    vault_path: Path,
    query: str,
    max_results: int | None,
    fixture_path: Path | None = None,
    paper_search_command: str | None = None,
    sources: list[str] | None = None,
    use_query_plan: bool = True,
    query_plan_domain: str = "auto",
    query_plan_max_queries: int = 6,
) -> Path:
    config = load_config(plugin_root=plugin_root, vault_path=vault_path, max_results=max_results)
    configured_paper_search_command = (
        config.paper_search_command if config.paper_search_command not in {None, "", "paper-search"} else None
    )
    effective_paper_search_command = paper_search_command or configured_paper_search_command
    effective_sources = sources or config.paper_search_sources
    run_id, run_dir = _new_run_dir(config.vault_path)
    started_at = utc_now()
    query_plan = (
        _build_dry_run_query_plan(
            query,
            domain=query_plan_domain,
            max_queries=query_plan_max_queries,
            config=config,
        )
        if use_query_plan
        else None
    )
    research_mode = (query_plan or {}).get("research_mode") or infer_research_mode(query)
    if query_plan:
        _write_json(run_dir / "query-plan.json", query_plan)

    state = {
        "stage": "paper-discovery-dry-run",
        "run_id": run_id,
        "workflow_type": "paper-discovery-dry-run",
        "state": "configured",
        "status": "running",
        "dry_run": True,
        "query": query,
        "research_mode": research_mode,
        "query_strategy": "query_plan_multi_query" if query_plan and fixture_path is None else "single_query",
        "profile": config.profile,
        "vault_path": str(config.vault_path),
        "started_at": started_at,
        "tool_versions": _tool_versions(
            "orchestrator",
            "paper_search_adapter",
            "normalize_candidates",
            "filter_candidates",
            "rank_candidates",
            "report_run",
        ),
    }
    if query_plan:
        state["query_plan"] = {
            "domain": query_plan.get("domain"),
            "query_variant_count": len(query_plan.get("query_variants") or []),
            "path": str(run_dir / "query-plan.json"),
        }
    _write_json(run_dir / "run-state.json", state)

    search_record = _run_query_plan_discovery(
        query=query,
        query_plan=query_plan,
        max_results=config.max_results,
        fixture_path=fixture_path,
        command=effective_paper_search_command,
        sources=effective_sources,
        run_dir=run_dir,
    )
    _write_json(run_dir / "search-record.json", search_record)
    state["state"] = "discovered"
    _write_json(run_dir / "run-state.json", state)

    normalized = normalize_candidates(search_record.get("records", []))
    _write_json(run_dir / "normalized.json", normalized)
    state["state"] = "normalized"
    _write_json(run_dir / "run-state.json", state)

    query_exclude_terms = default_discovery_exclusion_terms(query)
    existing_library_index = load_existing_paper_index(config.vault_path)
    filter_report = filter_candidates_with_report(
        normalized,
        domains=_filter_domains_from_profile(config, query_plan),
        require_pdf=True,
        exclude_terms=query_exclude_terms,
        existing_library_index=existing_library_index,
    )
    filter_report["existing_library"] = {
        "papers_root": existing_library_index.get("papers_root"),
        "count": existing_library_index.get("count", 0),
    }
    filtered = filter_report["kept"]
    rejected = filter_report["rejected"]
    _write_json(run_dir / "filter-report.json", filter_report)
    state["state"] = "filtered"
    _write_json(run_dir / "run-state.json", state)

    ranked_pool = rank_candidates(
        filtered,
        positive_keywords=_ranking_keywords_from_profile(config, query, query_plan),
        negative_keywords=config.negative_keywords,
        venue_tiers=_venue_tiers_from_profile(config, query_plan),
    )
    ranked = ranked_pool[: config.max_results]
    _write_json(run_dir / "rank.json", ranked)
    state["state"] = "ranked"
    _write_json(run_dir / "run-state.json", state)

    errors = [search_record["error"]] if search_record.get("error") else []
    budget_usage = {
        "max_results": config.max_results,
        "raw_candidate_pool_count": len(search_record.get("records", [])),
        "discovered_count": len(normalized),
        "filtered_candidate_pool_count": len(filtered),
        "ranked_candidate_pool_count": len(ranked_pool),
        "accepted_count": len(ranked),
        "rejected_count": len(rejected),
    }
    if query_plan:
        budget_usage["query_variant_count"] = len(query_plan.get("query_variants") or [])
    discovery_context = {
        "research_mode": research_mode,
        "query_strategy": search_record.get("query_strategy", state.get("query_strategy")),
        "query_plan": query_plan or {},
        "candidate_pool": {
            "raw": len(search_record.get("records", [])),
            "normalized": len(normalized),
            "filtered": len(filtered),
            "ranked": len(ranked_pool),
            "accepted": len(ranked),
            "rejected": len(rejected),
        },
        "query_records": search_record.get("query_records", []),
        "warnings": search_record.get("warnings", []),
    }
    next_actions = ["Review accepted dry-run candidates before advancing ranked papers."]
    if rejected:
        next_actions.append("Refine the query or domain profile if too many candidates were rejected.")
    else:
        next_actions.append("Run the paper advance workflow on the top dry-run candidates when ready.")
    write_report(
        run_dir,
        ranked,
        errors,
        workflow_type=state["workflow_type"],
        run_id=run_id,
        rejected=rejected,
        quarantined=[],
        critic_failures=[],
        budget_usage=budget_usage,
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        discovery_context=discovery_context,
    )
    state["state"] = "reported"
    state["status"] = "failed" if errors else "success"
    state["finished_at"] = utc_now()
    state["exit_status"] = 1 if errors else 0
    input_hashes = {
        "request": json_sha256(
            {
                "query": query,
                "max_results": config.max_results,
                "sources": effective_sources,
                "profile": config.profile,
                "query_plan": query_plan,
            }
        )
    }
    if fixture_path is not None and fixture_path.exists():
        input_hashes["fixture.json"] = file_sha256(fixture_path)
    state["input_artifact_hashes"] = input_hashes
    state["output_artifact_hashes"] = _hash_existing_outputs(
        {
            "search-record.json": run_dir / "search-record.json",
            "normalized.json": run_dir / "normalized.json",
            "filter-report.json": run_dir / "filter-report.json",
            "rank.json": run_dir / "rank.json",
            "report.md": run_dir / "report.md",
            "paper-search-raw.json": run_dir / "paper-search-raw.json",
            "query-plan.json": run_dir / "query-plan.json",
        }
    )
    _write_json(run_dir / "run-state.json", state)
    lifecycle = _auto_manage_run_lifecycle(config.vault_path)
    if lifecycle.get("deleted_count"):
        state["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        _write_json(run_dir / "run-state.json", state)
    _refresh_run_index(config.vault_path)
    return run_dir


def run_one_paper_ingest(
    vault_path: Path,
    candidate: dict,
    pdf_path: Path,
    mineru_markdown_path: Path,
    mineru_tex_path: Path | None = None,
    mineru_images_dir: Path | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)

    acquire_record = acquire_paper(candidate, pdf_path, paper_root)
    parse_record = materialize_mineru_fixture(
        paper_root,
        markdown_path=mineru_markdown_path,
        tex_path=mineru_tex_path,
        images_dir=mineru_images_dir,
    )
    reader_record = generate_reader_outputs(paper_root)
    critic_report = run_critics(paper_root)
    staging_root = stage_paper(vault_path, slug, paper_root)

    run_manifest = {
        "stage": "one-paper-ingest",
        "state": "staged",
        "paper_slug": slug,
        "dry_run": False,
        "compiled_wiki_write": False,
        "acquire_record": acquire_record,
        "parse_record": parse_record,
        "reader_record": reader_record,
        "critic_outcome": critic_report["outcome"],
        "paper_root": str(paper_root),
        "staging_root": str(staging_root),
    }
    _write_json(paper_root / "run-manifest.json", run_manifest)
    return {
        "paper_root": paper_root,
        "staging_root": staging_root,
        "critic_report": critic_report,
        "run_manifest": run_manifest,
    }


def acquire_paper_from_candidate(vault_path: Path, candidate: dict) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    paper_root = raw_paper_root(vault_path, candidate["slug"])
    return acquire_paper_from_url(candidate, paper_root)


def parse_paper_with_mineru(
    vault_path: Path,
    slug: str,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
) -> dict:
    paper_root = raw_paper_root(vault_path.resolve(), slug)
    if not paper_root.exists():
        raise FileNotFoundError(f"missing raw paper root: {paper_root}")
    return run_mineru_command(paper_root, command=mineru_command, timeout_seconds=mineru_timeout)


def _write_paper_run_state(paper_root: Path, state: dict) -> dict:
    _write_json(paper_root / "run-state.json", state)
    return state


def _paper_run_state(
    *,
    paper_root: Path,
    slug: str,
    state: str,
    last_action: str,
    next_action: str | None,
    stage_record: dict | None = None,
    human_gate_required: bool = False,
) -> dict:
    payload = {
        "paper_slug": slug,
        "state": state,
        "last_action": last_action,
        "next_action": next_action,
        "paper_root": str(paper_root),
        "compiled_wiki_write": False,
        "human_gate_required": human_gate_required,
    }
    if stage_record is not None:
        payload["stage_record"] = stage_record
    return payload


def advance_paper_once(
    vault_path: Path,
    candidate: dict,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)
    paper_pdf = paper_root / "paper.pdf"
    reader_md = paper_root / "reader" / "reader.md"
    critic_report_path = paper_root / "critic" / "critic-report.json"
    promotion_plan = vault_path / "_staging" / "papers" / slug / "promotion-plan.json"

    if not paper_pdf.exists():
        record = acquire_paper_from_candidate(vault_path, candidate)
        state = "acquired" if record["status"] == "success" else "acquire_failed"
        next_action = "parse" if record["status"] == "success" else None
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state=state,
                last_action="acquire",
                next_action=next_action,
                stage_record=record,
            ),
        )

    if not _has_complete_mineru_parse(paper_root):
        record = parse_paper_with_mineru(
            vault_path, slug, mineru_command=mineru_command, mineru_timeout=mineru_timeout
        )
        state = "parsed" if record["status"] == "success" else "parse_failed"
        next_action = "read" if record["status"] == "success" else None
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state=state,
                last_action="parse",
                next_action=next_action,
                stage_record=record,
            ),
        )

    if not reader_md.exists():
        record = generate_reader_outputs(paper_root)
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="read",
                last_action="read",
                next_action="critic",
                stage_record=record,
            ),
        )

    if not critic_report_path.exists():
        record = run_critics(paper_root)
        state = "critic_passed" if record["outcome"] == "pass" else "critic_failed"
        next_action = "staging" if record["outcome"] == "pass" else record.get("next_action")
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state=state,
                last_action="critic",
                next_action=next_action,
                stage_record=record,
            ),
        )

    critic_report = json.loads(critic_report_path.read_text(encoding="utf-8"))
    if critic_report.get("outcome") != "pass":
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="critic_failed",
                last_action="awaiting-critic-resolution",
                next_action=critic_report.get("next_action"),
                stage_record=critic_report,
            ),
        )

    if not promotion_plan.exists():
        staging_root = stage_paper(vault_path, slug, paper_root)
        record = {
            "stage": "staging",
            "status": "success",
            "staging_root": str(staging_root),
            "promotion_plan": str(promotion_plan),
        }
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state="staged",
                last_action="staging",
                next_action="run-wiki-ingest-agent",
                stage_record=record,
                human_gate_required=True,
            ),
        )

    return _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="staged",
            last_action="awaiting-wiki-ingest",
            next_action="run-wiki-ingest-agent",
            human_gate_required=True,
        ),
    )


def _research_decision_from_result(result: dict, *, title: str) -> dict | None:
    stage_record = result.get("stage_record")
    if not isinstance(stage_record, dict):
        return None
    decision = stage_record.get("research_decision")
    if not isinstance(decision, dict):
        return None
    payload = dict(decision)
    payload["slug"] = result["paper_slug"]
    payload["title"] = title
    if stage_record.get("research_decision_path"):
        payload["decision_path"] = stage_record["research_decision_path"]
    return payload


def _reader_revision_plan_from_result(result: dict, *, title: str) -> dict | None:
    stage_record = result.get("stage_record")
    if not isinstance(stage_record, dict):
        return None
    plan = stage_record.get("reader_revision_plan")
    if not isinstance(plan, dict):
        return None
    payload = {
        "slug": result["paper_slug"],
        "title": title,
        "recommendation": plan.get("recommendation"),
        "next_action": plan.get("next_action"),
        "blocking_count": len(plan.get("blocking_repairs") or []),
        "warning_count": len(plan.get("warning_followups") or []),
    }
    if stage_record.get("reader_revision_plan_path"):
        payload["plan_path"] = stage_record["reader_revision_plan_path"]
    return payload


def _reproduction_plan_from_result(result: dict, *, title: str) -> dict | None:
    stage_record = result.get("stage_record")
    if not isinstance(stage_record, dict):
        return None
    plan = stage_record.get("reproduction_plan")
    if not isinstance(plan, dict):
        return None
    if plan.get("next_action") == "none":
        return None
    checklist = plan.get("checklist") or []
    payload = {
        "slug": result["paper_slug"],
        "title": title,
        "next_action": plan.get("next_action"),
        "missing_count": len([item for item in checklist if item.get("status") == "missing"]),
        "human_gate_required": bool(plan.get("human_gate_required")),
    }
    if stage_record.get("reproduction_plan_path"):
        payload["plan_path"] = stage_record["reproduction_plan_path"]
    return payload


def advance_paper_batch(
    vault_path: Path,
    candidates: list[dict],
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = None,
    source_run_id: str | None = None,
    candidate_source: Path | None = None,
    workflow_type: str = "advance-batch",
    source_candidate_count: int | None = None,
    skipped_ranked_candidates: list[dict] | None = None,
    rank_decision_filter: list[str] | None = None,
    mineru_timeout: int | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    if max_papers is not None and max_papers < 0:
        raise ValueError("max_papers must be greater than or equal to 0")
    skipped_ranked_candidates = skipped_ranked_candidates or []
    source_candidate_count = source_candidate_count if source_candidate_count is not None else len(candidates)

    selected_candidates = candidates[:max_papers] if max_papers is not None else candidates
    run_id, run_dir = _new_run_dir(vault_path, "batch-advance")
    started_at = utc_now()
    results = [
        advance_paper_once(vault_path, candidate, mineru_command=mineru_command, mineru_timeout=mineru_timeout)
        for candidate in selected_candidates
    ]
    failed = any(result["state"].endswith("_failed") for result in results)
    awaiting_promotion = any(
        result.get("human_gate_required")
        and result.get("next_action") in {"promote-to-wiki", "run-wiki-ingest-agent"}
        for result in results
    )
    if failed:
        batch_state = "batch_failed"
        status = "failed"
    elif awaiting_promotion:
        batch_state = "awaiting_promotion"
        status = "waiting_for_human_gate"
    else:
        batch_state = "batch_advanced"
        status = "success"

    titles_by_slug = {
        candidate["slug"]: candidate.get("title", candidate["slug"])
        for candidate in selected_candidates
        if candidate.get("slug")
    }
    paper_states = [
        {
            "paper_slug": result["paper_slug"],
            "state": result["state"],
            "next_action": result.get("next_action"),
        }
        for result in results
    ]
    report_paper_states = [
        {
            "slug": result["paper_slug"],
            "paper_slug": result["paper_slug"],
            "title": titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            "state": result["state"],
            "last_action": result.get("last_action"),
            "next_action": result.get("next_action"),
            "human_gate_required": result.get("human_gate_required", False),
        }
        for result in results
    ]
    research_decisions = [
        decision
        for result in results
        for decision in [
            _research_decision_from_result(
                result,
                title=titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            )
        ]
        if decision is not None
    ]
    reader_revision_plans = [
        plan
        for result in results
        for plan in [
            _reader_revision_plan_from_result(
                result,
                title=titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            )
        ]
        if plan is not None
    ]
    reproduction_plans = [
        plan
        for result in results
        for plan in [
            _reproduction_plan_from_result(
                result,
                title=titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            )
        ]
        if plan is not None
    ]
    failed_papers = [
        state
        for state in paper_states
        if state["state"].endswith("_failed")
    ]
    report_failed_papers = [
        state
        for state in report_paper_states
        if state["state"].endswith("_failed")
    ]
    critic_failures = [
        state
        for state in report_paper_states
        if state["state"] == "critic_failed"
    ]
    quarantined = [
        state
        for state in report_paper_states
        if state["state"] == "quarantined"
    ]
    accepted = [
        {
            "slug": state["slug"],
            "title": state["title"],
            "state": state["state"],
        }
        for state in report_paper_states
        if not state["state"].endswith("_failed")
    ]
    next_actions = list(
        dict.fromkeys(
            result["next_action"]
            for result in results
            if result.get("next_action")
        )
    )
    budget_usage = {
        "candidate_count": source_candidate_count,
        "processed_count": len(results),
        "skipped_count": source_candidate_count - len(results),
        "max_papers": max_papers,
    }

    batch = {
        "stage": "batch-advance",
        "run_id": run_id,
        "workflow_type": workflow_type,
        "state": batch_state,
        "status": status,
        "vault_path": str(vault_path),
        "candidate_count": source_candidate_count,
        "processed_count": len(results),
        "skipped_count": source_candidate_count - len(results),
        "max_papers": max_papers,
        "skipped_ranked_candidates": skipped_ranked_candidates,
        "compiled_wiki_write": False,
        "human_gate_required": awaiting_promotion,
        "started_at": started_at,
        "tool_versions": _tool_versions("orchestrator", "advance_paper_batch", "advance_paper_once"),
        "results": results,
        "research_decisions": research_decisions,
        "reader_revision_plans": reader_revision_plans,
        "reproduction_plans": reproduction_plans,
    }
    if source_run_id is not None:
        batch["source_run_id"] = source_run_id
    if candidate_source is not None:
        batch["candidate_source"] = str(candidate_source)
    if rank_decision_filter is not None:
        batch["rank_decision_filter"] = rank_decision_filter
    batch["finished_at"] = utc_now()
    batch["exit_status"] = 1 if failed else 0
    input_hashes = {
        "candidates": json_sha256(selected_candidates),
    }
    if candidate_source is not None and candidate_source.exists():
        input_hashes["candidate_source"] = file_sha256(candidate_source)
    batch["input_artifact_hashes"] = input_hashes
    batch["output_artifact_hashes"] = {
        f"paper:{result['paper_slug']}:run-state.json": file_sha256(raw_paper_root(vault_path, result["paper_slug"]) / "run-state.json")
        for result in results
    }
    _write_json(run_dir / "batch-advance-record.json", batch)
    _write_json(run_dir / "run-state.json", batch)
    write_report(
        run_dir,
        accepted,
        [],
        workflow_type=workflow_type,
        run_id=run_id,
        quarantined=quarantined,
        critic_failures=critic_failures,
        paper_states=report_paper_states,
        failed_papers=report_failed_papers,
        budget_usage=budget_usage,
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        research_decisions=research_decisions,
        reader_revision_plans=reader_revision_plans,
        reproduction_plans=reproduction_plans,
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["processed_count"] = batch["processed_count"]
    report_payload["skipped_count"] = batch["skipped_count"]
    report_payload["skipped_ranked_candidates"] = skipped_ranked_candidates
    if rank_decision_filter is not None:
        report_payload["rank_decision_filter"] = rank_decision_filter
    report_payload["paper_states"] = paper_states
    report_payload["failed_papers"] = failed_papers
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    report_payload["reader_revision_plans"] = reader_revision_plans
    report_payload["reproduction_plans"] = reproduction_plans
    if source_run_id is not None:
        report_payload["source_run_id"] = source_run_id
    _write_json(report_json_path, report_payload)
    lifecycle = _auto_manage_run_lifecycle(vault_path)
    if lifecycle.get("deleted_count"):
        batch["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        _write_json(run_dir / "run-state.json", batch)
    _refresh_run_index(vault_path)
    return batch


def _rank_decision(candidate: dict) -> str | None:
    protocol = candidate.get("ranking_protocol")
    if not isinstance(protocol, dict):
        return None
    decision = protocol.get("decision")
    return str(decision) if decision else None


def _select_ranked_candidates(
    candidates: list[dict],
    *,
    include_review_candidates: bool,
) -> tuple[list[dict], list[dict], list[str]]:
    allowed = ["advance-candidate"]
    if include_review_candidates:
        allowed.append("review-candidate")
    selected: list[dict] = []
    skipped: list[dict] = []
    for candidate in candidates:
        decision = _rank_decision(candidate)
        if decision in allowed:
            selected.append(candidate)
            continue
        skipped.append(
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "decision": decision,
                "reason": "decision_not_selected",
            }
        )
    return selected, skipped, allowed


def advance_paper_batch_from_run(
    vault_path: Path,
    run_id: str,
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = None,
    include_review_candidates: bool = False,
    mineru_timeout: int | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    rank_path = vault_path / "_runs" / run_id / "rank.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    candidates = json.loads(rank_path.read_text(encoding="utf-8"))
    selected_candidates, skipped_ranked_candidates, rank_decision_filter = _select_ranked_candidates(
        candidates,
        include_review_candidates=include_review_candidates,
    )
    return advance_paper_batch(
        vault_path,
        selected_candidates,
        mineru_command=mineru_command,
        max_papers=max_papers,
        source_run_id=run_id,
        candidate_source=rank_path,
        workflow_type="advance-ranked",
        source_candidate_count=len(candidates),
        skipped_ranked_candidates=skipped_ranked_candidates,
        rank_decision_filter=rank_decision_filter,
        mineru_timeout=mineru_timeout,
    )


def _prepare_candidate_until_parsed(
    vault_path: Path,
    candidate: dict,
    *,
    mineru_command: str | list[str] | None = None,
    mineru_timeout: int | None = None,
) -> dict:
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)
    paper_pdf = paper_root / "paper.pdf"
    mineru_dir = paper_root / "mineru"
    mineru_md = mineru_dir / "paper.md"
    mineru_tex = mineru_dir / "paper.tex"
    mineru_manifest = mineru_dir / "mineru-manifest.json"
    mineru_images = mineru_dir / "images"

    if not paper_pdf.exists():
        acquire_record = acquire_paper_from_candidate(vault_path, candidate)
        if acquire_record["status"] != "success":
            return _write_paper_run_state(
                paper_root,
                _paper_run_state(
                    paper_root=paper_root,
                    slug=slug,
                    state="acquire_failed",
                    last_action="acquire",
                    next_action=None,
                    stage_record=acquire_record,
                ),
            )

    parse_complete = _has_complete_mineru_parse(paper_root)
    if not parse_complete:
        parse_record = parse_paper_with_mineru(
            vault_path, slug, mineru_command=mineru_command, mineru_timeout=mineru_timeout
        )
        state = "parsed" if parse_record["status"] == "success" else "parse_failed"
        next_action = "read" if parse_record["status"] == "success" else None
        return _write_paper_run_state(
            paper_root,
            _paper_run_state(
                paper_root=paper_root,
                slug=slug,
                state=state,
                last_action="parse",
                next_action=next_action,
                stage_record=parse_record,
            ),
        )

    return _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="parsed",
            last_action="already-parsed",
            next_action="read",
            human_gate_required=False,
        ),
    )


def _parse_record_status(paper_root: Path) -> str | None:
    record_path = paper_root / "parse-record.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if isinstance(record, dict) and record.get("status") is not None:
        return str(record.get("status"))
    return None


def _has_complete_mineru_parse(paper_root: Path) -> bool:
    paper_pdf = paper_root / "paper.pdf"
    mineru_dir = paper_root / "mineru"
    mineru_md = mineru_dir / "paper.md"
    mineru_tex = mineru_dir / "paper.tex"
    mineru_manifest = mineru_dir / "mineru-manifest.json"
    mineru_images = mineru_dir / "images"
    files_complete = (
        paper_pdf.exists()
        and mineru_md.exists()
        and mineru_md.stat().st_size > 0
        and mineru_tex.exists()
        and mineru_tex.stat().st_size > 0
        and mineru_manifest.exists()
        and mineru_images.is_dir()
    )
    if not files_complete:
        return False
    # A complete parse must also carry a success parse-record. This guards against
    # a crash/kill between writing mineru/ files and parse-record.json, and against
    # corrupted/leftover outputs being silently skipped by --skip-existing.
    return _parse_record_status(paper_root) == "success"


def _prepare_candidate_failure_state(vault_path: Path, candidate: dict, exc: Exception) -> dict:
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)
    paper_root.mkdir(parents=True, exist_ok=True)
    record = {
        "stage": "prepare",
        "status": "failed",
        "started_at": utc_now(),
        "finished_at": utc_now(),
        "exit_status": 1,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    return _write_paper_run_state(
        paper_root,
        _paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state="prepare_failed",
            last_action="prepare",
            next_action=None,
            stage_record=record,
        ),
    )


def prepare_ranked_papers_from_run(
    vault_path: Path,
    run_id: str,
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = 1,
    include_review_candidates: bool = False,
    skip_existing: bool = False,
    mineru_timeout: int | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    rank_path = vault_path / "_runs" / run_id / "rank.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    candidates = json.loads(rank_path.read_text(encoding="utf-8"))
    selected_candidates, skipped_ranked_candidates, rank_decision_filter = _select_ranked_candidates(
        candidates,
        include_review_candidates=include_review_candidates,
    )
    source_candidate_count = len(candidates)
    skipped_existing_candidates: list[dict] = []
    if skip_existing:
        remaining_candidates = []
        for candidate in selected_candidates:
            slug = candidate.get("slug")
            if slug and _has_complete_mineru_parse(raw_paper_root(vault_path, slug)):
                skipped_existing_candidates.append(
                    {
                        "slug": slug,
                        "title": candidate.get("title", slug),
                        "reason": "already_parsed",
                    }
                )
                continue
            remaining_candidates.append(candidate)
        selected_candidates = remaining_candidates
    selected_candidates = selected_candidates[:max_papers] if max_papers is not None else selected_candidates
    batch_run_id, batch_run_dir = _new_run_dir(vault_path, "prepare-ranked")
    started_at = utc_now()
    results = []
    for candidate in selected_candidates:
        try:
            result = _prepare_candidate_until_parsed(
                vault_path, candidate, mineru_command=mineru_command, mineru_timeout=mineru_timeout
            )
        except Exception as exc:
            result = _prepare_candidate_failure_state(vault_path, candidate, exc)
        results.append(result)
    failed = any(result["state"].endswith("_failed") for result in results)
    titles_by_slug = {
        candidate["slug"]: candidate.get("title", candidate["slug"])
        for candidate in selected_candidates
        if candidate.get("slug")
    }
    paper_states = [
        {
            "paper_slug": result["paper_slug"],
            "state": result["state"],
            "next_action": result.get("next_action"),
        }
        for result in results
    ]
    report_paper_states = [
        {
            "slug": result["paper_slug"],
            "paper_slug": result["paper_slug"],
            "title": titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            "state": result["state"],
            "last_action": result.get("last_action"),
            "next_action": result.get("next_action"),
            "human_gate_required": False,
        }
        for result in results
    ]
    failed_papers = [state for state in paper_states if state["state"].endswith("_failed")]
    report_failed_papers = [state for state in report_paper_states if state["state"].endswith("_failed")]
    accepted = [
        {
            "slug": state["slug"],
            "title": state["title"],
            "state": state["state"],
        }
        for state in report_paper_states
        if not state["state"].endswith("_failed")
    ]
    next_actions = list(dict.fromkeys(result["next_action"] for result in results if result.get("next_action")))
    batch = {
        "stage": "prepare-ranked",
        "run_id": batch_run_id,
        "workflow_type": "prepare-ranked",
        "state": "prepared" if not failed else "prepare_failed",
        "status": "success" if not failed else "failed",
        "vault_path": str(vault_path),
        "candidate_count": source_candidate_count,
        "processed_count": len(results),
        "skipped_count": source_candidate_count - len(results),
        "max_papers": max_papers,
        "source_run_id": run_id,
        "candidate_source": str(rank_path),
        "skipped_ranked_candidates": skipped_ranked_candidates,
        "skipped_existing_candidates": skipped_existing_candidates,
        "rank_decision_filter": rank_decision_filter,
        "skip_existing": skip_existing,
        "compiled_wiki_write": False,
        "human_gate_required": False,
        "stops_after": "parse",
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 1 if failed else 0,
        "tool_versions": _tool_versions("orchestrator", "prepare_ranked_papers_from_run", "run_mineru_parse"),
        "results": results,
        "next_actions": next_actions,
        "input_artifact_hashes": {
            "candidates": json_sha256(selected_candidates),
            "candidate_source": file_sha256(rank_path),
        },
        "output_artifact_hashes": {
            f"paper:{result['paper_slug']}:run-state.json": file_sha256(
                raw_paper_root(vault_path, result["paper_slug"]) / "run-state.json"
            )
            for result in results
        },
    }
    _write_json(batch_run_dir / "batch-advance-record.json", batch)
    _write_json(batch_run_dir / "run-state.json", batch)
    write_report(
        batch_run_dir,
        accepted,
        [],
        workflow_type="prepare-ranked",
        run_id=batch_run_id,
        paper_states=report_paper_states,
        failed_papers=report_failed_papers,
        budget_usage={
            "candidate_count": source_candidate_count,
            "processed_count": len(results),
            "skipped_count": source_candidate_count - len(results),
            "max_papers": max_papers,
            "skip_existing": skip_existing,
            "skipped_existing_count": len(skipped_existing_candidates),
            "stops_after": "parse",
        },
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
    )
    report_json_path = batch_run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["processed_count"] = batch["processed_count"]
    report_payload["skipped_count"] = batch["skipped_count"]
    report_payload["skipped_ranked_candidates"] = skipped_ranked_candidates
    report_payload["skipped_existing_candidates"] = skipped_existing_candidates
    report_payload["skip_existing"] = skip_existing
    report_payload["rank_decision_filter"] = rank_decision_filter
    report_payload["paper_states"] = paper_states
    report_payload["failed_papers"] = failed_papers
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    report_payload["source_run_id"] = run_id
    report_payload["stops_after"] = "parse"
    _write_json(report_json_path, report_payload)
    lifecycle = _auto_manage_run_lifecycle(vault_path)
    if lifecycle.get("deleted_count"):
        batch["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        _write_json(batch_run_dir / "run-state.json", batch)
    _refresh_run_index(vault_path)
    return batch


def main() -> int:
    from epi.cli import main as cli_main

    return cli_main()

if __name__ == "__main__":
    raise SystemExit(main())
