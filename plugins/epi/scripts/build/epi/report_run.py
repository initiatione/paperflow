from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import write_json_atomic, write_text_atomic


def write_report(
    run_dir: Path,
    ranked: list[dict],
    errors: list[str],
    *,
    workflow_type: str = "dry-run",
    run_id: str | None = None,
    rejected: list[dict] | None = None,
    quarantined: list[dict] | None = None,
    critic_failures: list[dict] | None = None,
    paper_states: list[dict] | None = None,
    failed_papers: list[dict] | None = None,
    budget_usage: dict | None = None,
    wiki_pages_written: list[str] | None = None,
    zotero_results: dict | None = None,
    next_actions: list[str] | None = None,
    human_gate: dict | None = None,
    restored_paths: list[str] | None = None,
    removed_paths: list[str] | None = None,
    changed_artifacts: list[str] | None = None,
) -> None:
    rejected = rejected or []
    quarantined = quarantined or []
    critic_failures = critic_failures or []
    paper_states = paper_states or []
    failed_papers = failed_papers or []
    budget_usage = budget_usage or {}
    wiki_pages_written = wiki_pages_written or []
    zotero_results = zotero_results or {"status": "not_run", "records": []}
    next_actions = next_actions or []
    restored_paths = restored_paths or []
    removed_paths = removed_paths or []
    changed_artifacts = changed_artifacts or []

    if workflow_type == "dry-run":
        report = ["# EPI Dry Run", ""]
        report.append(f"Accepted candidates: {len(ranked)}")
        report.append(f"Rejected candidates: {len(rejected)}")
        report.append(f"Quarantined candidates: {len(quarantined)}")
        report.append(f"Critic failures: {len(critic_failures)}")
        if budget_usage:
            report.append("")
            report.append("## Budget Usage")
            for key, value in budget_usage.items():
                report.append(f"- {key}: {value}")
        report.append("")
        report.append("## Next Actions")
        if next_actions:
            for action in next_actions:
                report.append(f"- {action}")
        else:
            report.append("- No follow-up actions recorded.")
        if errors:
            report.append("")
            report.append("## Errors")
            for error in errors:
                report.append(f"- {error}")
        report.append("")
        report.append("## Ranked Papers")
        for index, paper in enumerate(ranked, start=1):
            report.append(f"{index}. {paper.get('title')} - score {paper.get('score')}")
            report.append(f"   - venue: {paper.get('venue')}")
            report.append(f"   - year: {paper.get('year')}")
            report.append(f"   - pdf: {paper.get('pdf_url')}")
        if rejected:
            report.append("")
            report.append("## Rejected Candidates")
            for index, paper in enumerate(rejected, start=1):
                reasons = ", ".join(paper.get("filter_reasons") or [])
                report.append(f"{index}. {paper.get('title')}")
                report.append(f"   - reasons: {reasons}")
    else:
        report = ["# EPI Routed Run", ""]
        report.append(f"Workflow type: {workflow_type}")
        if run_id:
            report.append(f"Run ID: {run_id}")
        report.append(f"Accepted papers: {len(ranked)}")
        report.append(f"Failed papers: {len(failed_papers)}")
        report.append(f"Quarantined papers: {len(quarantined)}")
        report.append(f"Critic failures: {len(critic_failures)}")
        if budget_usage:
            report.append("")
            report.append("## Budget Usage")
            for key, value in budget_usage.items():
                report.append(f"- {key}: {value}")
        report.append("")
        report.append("## Next Actions")
        if next_actions:
            for action in next_actions:
                report.append(f"- {action}")
        else:
            report.append("- No follow-up actions recorded.")
        if errors:
            report.append("")
            report.append("## Errors")
            for error in errors:
                report.append(f"- {error}")
        report.append("")
        report.append("## Paper States")
        for index, paper in enumerate(paper_states, start=1):
            report.append(f"{index}. {paper.get('title') or paper.get('slug')} - {paper.get('state')}")
            report.append(f"   - slug: {paper.get('slug')}")
            report.append(f"   - last_action: {paper.get('last_action')}")
            report.append(f"   - next_action: {paper.get('next_action')}")
            report.append(f"   - human_gate_required: {paper.get('human_gate_required')}")
        report.append("")
        report.append("## Failed Papers")
        if failed_papers:
            for index, paper in enumerate(failed_papers, start=1):
                report.append(f"{index}. {paper.get('title') or paper.get('slug')} - {paper.get('state')}")
                report.append(f"   - next_action: {paper.get('next_action')}")
        else:
            report.append("- No failed papers recorded.")
        if wiki_pages_written:
            report.append("")
            report.append("## Wiki Pages Written")
            for path in wiki_pages_written:
                report.append(f"- {path}")
        if changed_artifacts:
            report.append("")
            report.append("## Changed Artifacts")
            for path in changed_artifacts:
                report.append(f"- {path}")
        if human_gate:
            report.append("")
            report.append("## Human Gate")
            for key, value in human_gate.items():
                report.append(f"- {key}: {value}")
        if restored_paths:
            report.append("")
            report.append("## Restored Paths")
            for path in restored_paths:
                report.append(f"- {path}")
        if removed_paths:
            report.append("")
            report.append("## Removed Paths")
            for path in removed_paths:
                report.append(f"- {path}")

    write_text_atomic(run_dir / "report.md", "\n".join(report) + "\n")
    write_json_atomic(
        run_dir / "report.json",
        {
            "workflow_type": workflow_type,
            "run_id": run_id,
            "accepted": ranked,
            "rejected": rejected,
            "quarantined": quarantined,
            "critic_failures": critic_failures,
            "paper_states": paper_states,
            "failed_papers": failed_papers,
            "budget_usage": budget_usage,
            "wiki_pages_written": wiki_pages_written,
            "zotero_results": zotero_results,
            "next_actions": next_actions,
            "human_gate": human_gate,
            "restored_paths": restored_paths,
            "removed_paths": removed_paths,
            "changed_artifacts": changed_artifacts,
            "accepted_count": len(ranked),
            "errors": errors,
            "ranked": ranked,
        },
    )
