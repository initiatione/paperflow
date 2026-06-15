from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from paper_source.artifacts import (
    file_sha256,
    raw_paper_root,
    read_json,
    read_json_dict,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)
from paper_source.report_run import write_report
from paper_source.source_artifacts import canonical_mineru_markdown_relative_path, has_nonempty_mineru_tex

_LOCAL_TOOL_VERSION = "paper-source-local"


def _hash_existing_outputs(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in paths.items():
        if path.exists():
            hashes[name] = file_sha256(path)
    return hashes


def _tool_versions(*tool_names: str) -> dict[str, str]:
    return {tool_name: _LOCAL_TOOL_VERSION for tool_name in tool_names}


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


def _paper_title(vault_path: Path, slug: str) -> str:
    metadata_path = raw_paper_root(vault_path, slug) / "metadata.json"
    if not metadata_path.exists():
        return slug
    metadata = read_json_dict(metadata_path, default=None)
    if metadata is None:
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
        changed_artifacts = [canonical_mineru_markdown_relative_path(slug)]
        if has_nonempty_mineru_tex(raw_paper_root(vault_path, slug)):
            changed_artifacts.append("mineru/paper.tex")
        return (
            {
                "slug": slug,
                "title": _paper_title(vault_path, slug),
                "state": "reparsed",
                "last_action": "redo-parse",
                "next_action": "redo-read",
                "human_gate_required": False,
            },
            changed_artifacts,
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
        critic_report = read_json(critic_report_path)
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
        critic_report = read_json(critic_report_path)
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
    output_paths = {artifact: paper_root / artifact for artifact in changed_artifacts}
    output_paths["redo-records.jsonl"] = paper_root / "redo-records.jsonl"
    output_paths["report.md"] = run_dir / "report.md"
    output_paths["report.json"] = run_dir / "report.json"
    write_json_atomic(
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


def write_repair_routed_report(
    vault_path: Path,
    slug: str,
    record: dict,
    *,
    started_at: str,
    input_artifact_hashes: dict[str, str],
    new_run_dir: Callable[[Path, str | None], tuple[str, Path]],
    paper_run_state: Callable[..., dict],
    write_paper_run_state: Callable[[Path, dict], dict],
    refresh_run_index: Callable[[Path], None],
) -> None:
    workflow_type = record["stage"]
    run_id, run_dir = new_run_dir(vault_path.resolve(), workflow_type)
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
    report_payload = read_json(report_json_path)
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
    write_json_atomic(report_json_path, report_payload)
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
        stage_record = read_json(paper_root / "critic" / "critic-report.json")
    else:
        stage_record = record
    write_paper_run_state(
        paper_root,
        paper_run_state(
            paper_root=paper_root,
            slug=slug,
            state=paper_state["state"],
            last_action=paper_state["last_action"],
            next_action=paper_state["next_action"],
            stage_record=stage_record,
            human_gate_required=paper_state.get("human_gate_required", False),
        ),
    )
    refresh_run_index(vault_path)
