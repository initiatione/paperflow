from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import write_text_atomic


REVISION_GUIDANCE_BASIS = "critic-revision-guidance"


def _read_plan(plan_path: Path) -> dict | None:
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return plan if isinstance(plan, dict) else None


def _render_repair_items(items: list[dict]) -> list[str]:
    if not items:
        return ["- None"]
    lines: list[str] = []
    for item in items:
        check = item.get("check", "critic_check")
        instruction = item.get("instruction", "Revise the reader artifact using critic evidence.")
        evidence = item.get("evidence", "")
        target_artifacts = ", ".join(item.get("target_artifacts") or [])
        lines.append(f"- {check}: {instruction}")
        if target_artifacts:
            lines.append(f"  - Target artifacts: {target_artifacts}")
        if evidence:
            lines.append(f"  - Evidence: {evidence}")
    return lines


def render_revision_guidance(plan: dict) -> str:
    lines = [
        "# Reader Revision Guidance",
        "",
        f"Recommendation: {plan.get('recommendation', '')}",
        f"Next action: {plan.get('next_action', '')}",
        f"Hard rule: {plan.get('hard_rule', '')}",
        "",
        "Use this file as the input brief for the next reader pass.",
        "",
    ]
    for role in plan.get("role_worklist") or []:
        heading = role.get("heading") or role.get("lens") or "Reader Role"
        target_artifacts = ", ".join(role.get("target_artifacts") or [])
        lines.extend(
            [
                f"## {heading}",
                f"Lens: {role.get('lens', '')}",
                f"Responsibility: {role.get('responsibility', '')}",
                f"Target artifacts: {target_artifacts}",
                "",
                "Blocking repairs:",
            ]
        )
        lines.extend(_render_repair_items(role.get("blocking_repairs") or []))
        lines.append("Warning follow-ups:")
        lines.extend(_render_repair_items(role.get("warning_followups") or []))
        lines.append("")
    return "\n".join(lines)


def _role_block(guidance_text: str, heading: str) -> list[str]:
    lines = guidance_text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            start = index + 1
            break
    if start is None:
        return []
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return lines[start:end]


def _role_focus_items(guidance_text: str, heading: str) -> list[str]:
    block = _role_block(guidance_text, heading)
    if not block:
        return []

    items: list[str] = []
    for line in block:
        if line.startswith("Responsibility:"):
            responsibility = line.split(":", 1)[1].strip()
            if responsibility:
                items.append(f"role_focus: {responsibility}")
        elif line.startswith("- ") and line.strip() != "- None":
            items.append(line.removeprefix("- ").strip())
    return items


def render_role_revision_focus_section(guidance_text: str, heading: str) -> list[str]:
    items = _role_focus_items(guidance_text, heading)
    if not items:
        return []
    lines = ["", "## Critic Revision Focus"]
    for item in items:
        lines.append(f"- {item}")
        lines.append(f"  Evidence: source=inference; basis={REVISION_GUIDANCE_BASIS}")
    return lines


def write_revision_guidance_from_plan(paper_root: Path) -> dict | None:
    plan_path = paper_root / "critic" / "reader-revision-plan.json"
    plan = _read_plan(plan_path)
    if plan is None:
        return None
    reader_dir = paper_root / "reader"
    guidance_path = reader_dir / "revision-guidance.md"
    write_text_atomic(guidance_path, render_revision_guidance(plan))
    return {
        "revision_plan_path": str(plan_path),
        "revision_guidance_path": str(guidance_path),
        "revision_blocking_count": len(plan.get("blocking_repairs") or []),
        "revision_warning_count": len(plan.get("warning_followups") or []),
    }
