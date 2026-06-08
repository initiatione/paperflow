from __future__ import annotations

import re
from pathlib import Path

from epi.artifacts import write_json_atomic, write_text_atomic


REPRO_ITEMS = ("code", "data", "model", "config", "simulator", "hardware")


def _warning_text(reviewers: list[dict]) -> list[str]:
    warnings: list[str] = []
    for reviewer in reviewers:
        warnings.extend(str(warning) for warning in reviewer.get("warnings") or [])
    return warnings


def _missing_items(warnings: list[str], metadata: dict) -> set[str]:
    missing: set[str] = set()
    for warning in warnings:
        if "engineering_reproducibility" not in warning:
            continue
        match = re.search(r"missing\s+(.+)$", warning)
        if match:
            missing.update(
                item.strip().lower().replace(" ", "_")
                for item in re.split(r"[,;]", match.group(1))
                if item.strip()
            )
    if metadata.get("code_url") or metadata.get("repository_url"):
        missing.discard("code")
    if metadata.get("data_url") or metadata.get("dataset_url"):
        missing.discard("data")
    return {item for item in missing if item in REPRO_ITEMS}


def _checklist(missing: set[str], metadata: dict) -> list[dict]:
    checklist: list[dict] = []
    for item in REPRO_ITEMS:
        status = "missing" if item in missing else "present-or-not-flagged"
        if item == "code" and (metadata.get("code_url") or metadata.get("repository_url")):
            status = "present"
        if item == "data" and (metadata.get("data_url") or metadata.get("dataset_url")):
            status = "present"
        checklist.append(
            {
                "item": item,
                "status": status,
                "evidence_needed": f"Record {item} source, version, and local reproduction notes.",
            }
        )
    return checklist


def build_reproduction_plan(final_outcome: str, reviewers: list[dict], *, metadata: dict, hard_rule: str) -> dict:
    warnings = _warning_text(reviewers)
    missing = _missing_items(warnings, metadata)
    checklist = _checklist(missing, metadata)
    next_action = "prepare-reproduction-plan" if missing else "none"
    return {
        "schema_version": "epi-reproduction-plan-v1",
        "paper_slug": metadata.get("slug"),
        "paper_title": metadata.get("title"),
        "owner_lens": "senior-domain-researcher",
        "final_outcome": final_outcome,
        "next_action": next_action,
        "human_gate_required": bool(missing),
        "hard_rule": hard_rule,
        "source_warnings": [warning for warning in warnings if "engineering_reproducibility" in warning],
        "checklist": checklist,
        "tasks": [
            {
                "task": f"Collect and verify {item}.",
                "item": item,
                "target_artifact": "critic/reproduction-plan.md",
            }
            for item in REPRO_ITEMS
            if item in missing
        ],
    }


def render_reproduction_plan_markdown(plan: dict) -> str:
    lines = [
        "# Reproduction Plan",
        "",
        f"Paper: {plan.get('paper_title') or plan.get('paper_slug') or '-'}",
        f"Next action: {plan['next_action']}",
        f"Owner lens: {plan['owner_lens']}",
        f"Human gate required: {str(plan['human_gate_required']).lower()}",
        "",
        "## Senior Domain Researcher Reproduction Tasks",
    ]
    if plan["tasks"]:
        for task in plan["tasks"]:
            lines.append(f"- {task['item']}: {task['task']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Checklist"])
    for item in plan["checklist"]:
        lines.append(f"- {item['item']}: {item['status']}")
        lines.append(f"  - Evidence needed: {item['evidence_needed']}")
    if plan["source_warnings"]:
        lines.extend(["", "## Source Warnings"])
        lines.extend(f"- {warning}" for warning in plan["source_warnings"])
    lines.extend(["", f"Hard rule: {plan['hard_rule']}", ""])
    return "\n".join(lines)


def write_reproduction_plan(
    critic_dir: Path,
    final_outcome: str,
    reviewers: list[dict],
    *,
    metadata: dict,
    hard_rule: str,
) -> dict:
    plan = build_reproduction_plan(final_outcome, reviewers, metadata=metadata, hard_rule=hard_rule)
    write_json_atomic(critic_dir / "reproduction-plan.json", plan)
    write_text_atomic(critic_dir / "reproduction-plan.md", render_reproduction_plan_markdown(plan))
    return plan
