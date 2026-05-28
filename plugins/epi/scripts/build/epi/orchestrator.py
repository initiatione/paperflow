from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from epi.acquire_papers import acquire_paper, acquire_paper_from_url
from epi.artifacts import file_sha256, json_sha256, raw_paper_root, utc_now, write_json_atomic, write_text_atomic
from epi.config import load_config
from epi.feedback import record_feedback
from epi.filter_candidates import filter_candidates, filter_candidates_with_report
from epi.generate_reader import generate_reader_outputs
from epi.normalize_candidates import normalize_candidates
from epi.paper_search_adapter import discover
from epi.promote_to_wiki import promote_paper, rollback_promotion
from epi.rank_papers import rank_candidates
from epi.redo import redo_acquire, redo_parse, redo_read, recritic
from epi.report_run import write_report
from epi.run_index import query_runs, refresh_run_index, render_runs_query
from epi.run_critic import run_critics
from epi.run_mineru_parse import materialize_mineru_fixture, run_mineru_command
from epi.skill_aware_evolve import activate_evolution, propose_evolution
from epi.stage_wiki import stage_paper
from epi.wiki_init import initialize_paper_wiki
from epi.zotero_sync import sync_zotero_record

_LOCAL_TOOL_VERSION = "epi-local"


def _write_json(path: Path, payload: object) -> None:
    write_json_atomic(path, payload)


def _refresh_run_index(vault_path: Path) -> None:
    refresh_run_index(vault_path.resolve())


def _hash_existing_outputs(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in paths.items():
        if path.exists():
            hashes[name] = file_sha256(path)
    return hashes


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
) -> None:
    _write_json(
        run_dir / "run-state.json",
        {
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
        },
    )


def _write_promotion_routed_report(
    run_dir: Path,
    *,
    run_id: str,
    slug: str,
    promoted_page_paths: list[str],
    human_gate: dict,
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
        zotero_results={"status": "not_run", "records": []},
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
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reader_regenerated",
                "last_action": "redo-read",
                "next_action": "recritic",
                "human_gate_required": False,
            },
            [
                "reader/reader.md",
                "reader/figures.md",
                "reader/reproducibility.md",
                "reader/implementation-ideas.md",
            ],
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
    _write_json(report_json_path, report_payload)
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
    _refresh_run_index(vault_path)


def run_dry_run(
    plugin_root: Path,
    vault_path: Path,
    query: str,
    max_results: int | None,
    fixture_path: Path | None = None,
    paper_search_command: str | None = None,
    sources: list[str] | None = None,
) -> Path:
    config = load_config(plugin_root=plugin_root, vault_path=vault_path, max_results=max_results)
    initialize_paper_wiki(config.vault_path)
    run_id, run_dir = _new_run_dir(config.vault_path)
    started_at = utc_now()

    state = {
        "stage": "paper-discovery-dry-run",
        "run_id": run_id,
        "workflow_type": "paper-discovery-dry-run",
        "state": "configured",
        "status": "running",
        "dry_run": True,
        "query": query,
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
    _write_json(run_dir / "run-state.json", state)

    search_record = discover(
        query=query,
        max_results=config.max_results,
        fixture_path=fixture_path,
        command=paper_search_command,
        sources=sources,
        raw_response_path=run_dir / "paper-search-raw.json",
    )
    _write_json(run_dir / "search-record.json", search_record)
    state["state"] = "discovered"
    _write_json(run_dir / "run-state.json", state)

    normalized = normalize_candidates(search_record.get("records", []))
    _write_json(run_dir / "normalized.json", normalized)
    state["state"] = "normalized"
    _write_json(run_dir / "run-state.json", state)

    filter_report = filter_candidates_with_report(normalized, domains=config.domains, require_pdf=True)
    filtered = filter_report["kept"]
    rejected = filter_report["rejected"]
    _write_json(run_dir / "filter-report.json", filter_report)
    state["state"] = "filtered"
    _write_json(run_dir / "run-state.json", state)

    ranked = rank_candidates(
        filtered,
        positive_keywords=["robot", "humanoid", "embodied", "control", "navigation"],
        venue_tiers={"icra": 1.0, "iros": 0.95, "rss": 1.0, "corl": 0.98, "neurips": 1.0, "iclr": 1.0, "icml": 1.0},
    )
    _write_json(run_dir / "rank.json", ranked)
    state["state"] = "ranked"
    _write_json(run_dir / "run-state.json", state)

    errors = [search_record["error"]] if search_record.get("error") else []
    budget_usage = {
        "max_results": config.max_results,
        "discovered_count": len(normalized),
        "accepted_count": len(ranked),
        "rejected_count": len(rejected),
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
                "sources": sources or [],
                "profile": config.profile,
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
        }
    )
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


def parse_paper_with_mineru(vault_path: Path, slug: str, mineru_command: str | list[str] | None = None) -> dict:
    paper_root = raw_paper_root(vault_path.resolve(), slug)
    if not paper_root.exists():
        raise FileNotFoundError(f"missing raw paper root: {paper_root}")
    return run_mineru_command(paper_root, command=mineru_command)


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


def advance_paper_once(vault_path: Path, candidate: dict, mineru_command: str | list[str] | None = None) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    slug = candidate["slug"]
    paper_root = raw_paper_root(vault_path, slug)
    paper_pdf = paper_root / "paper.pdf"
    mineru_md = paper_root / "mineru" / "paper.md"
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

    if not mineru_md.exists():
        record = parse_paper_with_mineru(vault_path, slug, mineru_command=mineru_command)
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
                next_action="promote-to-wiki",
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
            last_action="awaiting-promotion",
            next_action="promote-to-wiki",
            human_gate_required=True,
        ),
    )


def advance_paper_batch(
    vault_path: Path,
    candidates: list[dict],
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = None,
    source_run_id: str | None = None,
    candidate_source: Path | None = None,
    workflow_type: str = "advance-batch",
) -> dict:
    vault_path = vault_path.resolve()
    initialize_paper_wiki(vault_path)
    if max_papers is not None and max_papers < 0:
        raise ValueError("max_papers must be greater than or equal to 0")

    selected_candidates = candidates[:max_papers] if max_papers is not None else candidates
    run_id, run_dir = _new_run_dir(vault_path, "batch-advance")
    started_at = utc_now()
    results = [
        advance_paper_once(vault_path, candidate, mineru_command=mineru_command)
        for candidate in selected_candidates
    ]
    failed = any(result["state"].endswith("_failed") for result in results)
    awaiting_promotion = any(
        result.get("human_gate_required") and result.get("next_action") == "promote-to-wiki"
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
        "candidate_count": len(candidates),
        "processed_count": len(results),
        "skipped_count": len(candidates) - len(results),
        "max_papers": max_papers,
    }

    batch = {
        "stage": "batch-advance",
        "run_id": run_id,
        "workflow_type": workflow_type,
        "state": batch_state,
        "status": status,
        "vault_path": str(vault_path),
        "candidate_count": len(candidates),
        "processed_count": len(results),
        "skipped_count": len(candidates) - len(results),
        "max_papers": max_papers,
        "compiled_wiki_write": False,
        "human_gate_required": awaiting_promotion,
        "started_at": started_at,
        "tool_versions": _tool_versions("orchestrator", "advance_paper_batch", "advance_paper_once"),
        "results": results,
    }
    if source_run_id is not None:
        batch["source_run_id"] = source_run_id
    if candidate_source is not None:
        batch["candidate_source"] = str(candidate_source)
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
    )
    report_json_path = run_dir / "report.json"
    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_payload["processed_count"] = batch["processed_count"]
    report_payload["skipped_count"] = batch["skipped_count"]
    report_payload["paper_states"] = paper_states
    report_payload["failed_papers"] = failed_papers
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    if source_run_id is not None:
        report_payload["source_run_id"] = source_run_id
    _write_json(report_json_path, report_payload)
    _refresh_run_index(vault_path)
    return batch


def advance_paper_batch_from_run(
    vault_path: Path,
    run_id: str,
    mineru_command: str | list[str] | None = None,
    max_papers: int | None = None,
) -> dict:
    vault_path = vault_path.resolve()
    rank_path = vault_path / "_runs" / run_id / "rank.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    candidates = json.loads(rank_path.read_text(encoding="utf-8"))
    return advance_paper_batch(
        vault_path,
        candidates,
        mineru_command=mineru_command,
        max_papers=max_papers,
        source_run_id=run_id,
        candidate_source=rank_path,
        workflow_type="advance-ranked",
    )


def main() -> int:
    from epi.cli import main as cli_main

    return cli_main()

if __name__ == "__main__":
    raise SystemExit(main())
