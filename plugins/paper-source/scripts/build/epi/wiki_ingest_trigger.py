from __future__ import annotations

from pathlib import Path
from typing import Any

from epi.artifacts import staging_paper_root, utc_now, write_json_atomic
from epi.wiki_ingest_approval import load_human_approval_record
from epi.wiki_ingest_handoff import build_wiki_ingest_handoff
from epi.wiki_contracts import formal_page_family_paths, page_lifecycle_states, research_review_fields


WIKI_AGENT_TRIGGER_SCHEMA_VERSION = "epi-wiki-agent-trigger-v1"


def wiki_agent_trigger_path(vault_path: Path, slug: str) -> Path:
    return staging_paper_root(vault_path.resolve(), slug) / "wiki-agent-trigger.json"


def _staging_path(staging_root: Path, value: object) -> str | None:
    if not value:
        return None
    candidate = Path(str(value))
    if candidate.is_absolute():
        return str(candidate)
    return str(staging_root / candidate)


def _reading_report_path(handoff: dict[str, Any], staging_root: Path, slug: str) -> str:
    entrypoints = handoff.get("entrypoints") if isinstance(handoff.get("entrypoints"), dict) else {}
    explicit = _staging_path(staging_root, entrypoints.get("reading_report"))
    if explicit:
        return explicit
    paths = handoff.get("paths") if isinstance(handoff.get("paths"), dict) else {}
    for value in paths.get("agent_handoff_paths") or []:
        value_text = str(value)
        if "reading-report" in value_text or value_text.endswith("-report.md"):
            return value_text
    return str(staging_root / "reports" / f"{slug}-reading-report.md")


def _approved_by(vault_path: Path, slug: str) -> str:
    record = load_human_approval_record(vault_path, slug) or {}
    return str(record.get("approved_by") or "<same-approved-by>")


def _family_paths(values: object) -> list[str]:
    records = values if isinstance(values, list) else []
    paths: list[str] = []
    for item in records:
        value = str(item.get("path") or item.get("name") or "") if isinstance(item, dict) else str(item or "")
        value = value.strip()
        if not value:
            continue
        if not value.endswith("/"):
            value += "/"
        paths.append(value)
    return paths or formal_page_family_paths()


def _ready_instruction(
    *,
    slug: str,
    approved_by: str,
    source_review_path: str,
    required_skills: list[str],
    formal_page_families: list[str],
    research_fields: list[str],
) -> str:
    return (
        "Continue by invoking PRW $paper-research-wiki for formal paper wiki writing. "
        "Use wiki-ingest-brief.json as the canonical EPI source/evidence handoff; "
        "keep epi-paper-deposition only as a legacy compatibility adapter. "
        "Apply PRW provenance, tag, language, lint, and post-task-check policies through the PRW writing standard. "
        "EPI artifacts are source/evidence handoff only "
        "and EPI itself may write only internal underscore folders. Follow the source-first rule and re-read the source bundle before writing: "
        "paper.pdf, metadata.json, mineru/<slug>.md, mineru/paper.tex, mineru/images/*, and "
        "mineru/mineru-manifest.json. Compare this paper with the current batch or neighboring EPI source "
        "bundles before creating reusable concept or synthesis pages. Route final knowledge into these page "
        "families when useful: "
        + ", ".join(formal_page_families)
        + ". Preserve support status and evidence-map "
        "addresses in final pages. Reconstruct theory and formulas instead of copying equations blindly, and "
        "record final-source-review research fields: "
        + ", ".join(research_fields)
        + ". Write or stage the final Markdown pages under the target vault contract, "
        "then create "
        + source_review_path
        + " and run record-wiki-ingest --slug "
        + slug
        + " --page <final-page.md> --approved-by "
        + approved_by
        + " --source-review "
        + source_review_path
        + "."
    )


def _base_payload(
    *,
    vault_path: Path,
    slug: str,
    handoff: dict[str, Any],
    trigger_path: Path,
) -> dict[str, Any]:
    staging_root = staging_paper_root(vault_path, slug)
    paths = handoff.get("paths") if isinstance(handoff.get("paths"), dict) else {}
    contract = (
        handoff.get("final_source_review_contract")
        if isinstance(handoff.get("final_source_review_contract"), dict)
        else {}
    )
    source_review_path = staging_root / str(contract.get("suggested_output_path") or "final-source-review.json")
    return {
        "schema_version": WIKI_AGENT_TRIGGER_SCHEMA_VERSION,
        "paper_slug": slug,
        "paper_title": handoff.get("paper_title") or slug,
        "created_at": utc_now(),
        "ready_for_agent": bool(handoff.get("ready_for_agent")),
        "ready_after_human_approval": bool(handoff.get("ready_after_human_approval")),
        "trigger_path": str(trigger_path),
        "paper_gate": handoff.get("paper_gate") or {},
        "paths": {
            "promotion_plan": paths.get("promotion_plan"),
            "wiki_ingest_brief": paths.get("wiki_ingest_brief"),
            "human_approval": paths.get("human_approval"),
            "reading_report": _reading_report_path(handoff, staging_root, slug),
            "final_source_review": str(source_review_path),
            "trigger": str(trigger_path),
        },
        "executor_policy": handoff.get("execution_agent_policy") or {},
        "agent_context_policy": handoff.get("agent_context_policy") or {},
        "epi_write_scope": handoff.get("epi_write_scope"),
        "formal_routes_suggested": bool(handoff.get("formal_routes_suggested")),
        "wiki_batch_handoff_required": bool(handoff.get("wiki_batch_handoff_required")),
        "required_wiki_skills": handoff.get("required_wiki_skills") or [],
        "formal_page_families": handoff.get("formal_page_families") or [],
        "research_review_fields": handoff.get("research_review_fields") or research_review_fields(),
        "page_lifecycle_states": handoff.get("page_lifecycle_states") or page_lifecycle_states(),
        "handoff_artifacts": handoff.get("handoff_artifacts") or [],
        "candidate_topics": handoff.get("candidate_topics") or [],
        "candidate_clusters": handoff.get("candidate_clusters") or [],
        "final_source_review_contract": contract,
        "agent_checklist": list(handoff.get("agent_checklist") or []),
        "writes_final_wiki_pages": False,
        "calls_wiki_skill_for_final_pages": True,
    }


def build_wiki_ingest_trigger(vault_path: Path, slug: str) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    handoff = build_wiki_ingest_handoff(vault_path, slug)
    trigger_path = wiki_agent_trigger_path(vault_path, slug)
    payload = _base_payload(
        vault_path=vault_path,
        slug=slug,
        handoff=handoff,
        trigger_path=trigger_path,
    )
    paper_gate = payload.get("paper_gate") if isinstance(payload.get("paper_gate"), dict) else {}
    next_action = paper_gate.get("next_action")

    if handoff.get("ready_for_agent"):
        approved_by = _approved_by(vault_path, slug)
        payload.update(
            {
                "status": "ready",
                "next_action": "run-current-agent-as-wiki-ingest-agent",
                "instruction": _ready_instruction(
                    slug=slug,
                    approved_by=approved_by,
                    source_review_path=str(payload["paths"]["final_source_review"]),
                    required_skills=[str(item) for item in payload.get("required_wiki_skills") or []],
                    formal_page_families=_family_paths(payload.get("formal_page_families")),
                    research_fields=[str(item) for item in payload.get("research_review_fields") or []],
                ),
            }
        )
        if not payload["executor_policy"].get("allowed_executors"):
            payload["executor_policy"] = {
                **payload["executor_policy"],
                "allowed_executors": ["Claude", "Codex", "other wiki-capable agents"],
            }
        write_json_atomic(trigger_path, payload)
        return payload

    if handoff.get("ready_after_human_approval"):
        payload.update(
            {
                "status": "action_required",
                "next_action": "record-human-approval",
                "instruction": (
                    "Do not start the wiki ingest agent yet. Run record-human-approval "
                    "--scope run-wiki-ingest-agent, then rerun wiki-ingest-trigger."
                ),
            }
        )
        return payload

    if next_action == "review-recorded-wiki-pages":
        payload.update(
            {
                "status": "already_recorded",
                "next_action": "review-recorded-wiki-pages",
                "instruction": "Final wiki pages are already recorded; review wiki-ingest-record.json and the final pages.",
            }
        )
        return payload

    payload.update(
        {
            "status": "blocked",
            "next_action": next_action or "inspect-paper-gate",
            "instruction": "Do not start wiki writing. Inspect paper-gate and repair failures or unresolved checks first.",
        }
    )
    return payload


def render_wiki_ingest_trigger(trigger: dict[str, Any]) -> str:
    paths = trigger.get("paths") if isinstance(trigger.get("paths"), dict) else {}
    lines = [
        f"# EPI Wiki Agent Trigger - {trigger.get('paper_slug')}",
        "",
        f"status: {trigger.get('status')}",
        f"ready_for_agent: {str(trigger.get('ready_for_agent')).lower()}",
        f"ready_after_human_approval: {str(trigger.get('ready_after_human_approval')).lower()}",
        f"next_action: {trigger.get('next_action')}",
        f"trigger_path: {trigger.get('trigger_path')}",
        "",
        "## Paths",
        "",
    ]
    for key in [
        "wiki_ingest_brief",
        "reading_report",
        "human_approval",
        "final_source_review",
    ]:
        lines.append(f"- {key}: {paths.get(key) or '-'}")
    lines.extend(["", "## Wiki Skill Boundary", ""])
    lines.append(f"- epi_write_scope: {trigger.get('epi_write_scope') or '-'}")
    lines.append(f"- wiki_batch_handoff_required: {str(bool(trigger.get('wiki_batch_handoff_required'))).lower()}")
    lines.append("- required_skills: " + (", ".join(str(item) for item in trigger.get("required_wiki_skills") or []) or "-"))
    context_policy = trigger.get("agent_context_policy") if isinstance(trigger.get("agent_context_policy"), dict) else {}
    lines.extend(["", "## Agent Context Policy", ""])
    if context_policy:
        lines.append(f"- delegation_model: {context_policy.get('delegation_model')}")
        lines.append(f"- subagent_policy: {context_policy.get('subagent_policy')}")
        lines.append(f"- codex_permission_note: {context_policy.get('codex_permission_note')}")
        for key in ["main_agent_reads", "main_agent_avoids"]:
            values = ", ".join(str(item) for item in context_policy.get(key) or [])
            lines.append(f"- {key}: {values or '-'}")
    else:
        lines.append("- missing")
    lines.extend(["", "## Formal Page Families", ""])
    for family in _family_paths(trigger.get("formal_page_families")):
        lines.append(f"- {family}")
    lines.extend(["", "## Research Review Fields", ""])
    for field in trigger.get("research_review_fields") or []:
        lines.append(f"- {field}")
    lifecycle_states = trigger.get("page_lifecycle_states") or []
    if lifecycle_states:
        lines.append("")
        lines.append("page_lifecycle: " + " -> ".join(str(state) for state in lifecycle_states))
    lines.extend(["", "## Instruction", "", str(trigger.get("instruction") or "")])
    lines.extend(["", "## Agent Checklist", ""])
    for item in trigger.get("agent_checklist") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
