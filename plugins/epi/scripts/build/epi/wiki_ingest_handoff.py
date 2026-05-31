from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from epi.paper_gate import build_paper_gate


CONTRACT_FILES = [
    "AGENTS.md",
    "_meta/agent-operating-contract.md",
    "_meta/schema.md",
    "_meta/taxonomy.md",
    "_meta/directory-structure.md",
    "index.md",
    "log.md",
    ".manifest.json",
]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _contract_file_status(vault_path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for relative in CONTRACT_FILES:
        path = vault_path / relative
        records[relative] = {
            "present": path.is_file(),
            "path": str(path),
        }
    return records


def _brief_path_from_plan(plan: dict[str, Any], staging_root: Path) -> Path:
    value = plan.get("wiki_ingest_brief_path")
    return Path(value) if value else staging_root / "wiki-ingest-brief.json"


def _agent_checklist(
    *,
    gate: dict[str, Any],
    plan: dict[str, Any],
    brief: dict[str, Any],
) -> list[str]:
    read_before = brief.get("wiki_rule_source_model", {}).get("must_read_before_final_write") or CONTRACT_FILES
    handoff_paths = plan.get("agent_handoff_paths") or []
    source_policy = brief.get("ingest_policy", {}).get("source_first_policy")
    source_bundle = brief.get("source_bundle") or {}
    raw_artifacts = source_bundle.get("raw_artifacts") or []
    primary_order = source_bundle.get("primary_source_reading_order") or []
    formula_figure_review = source_bundle.get("formula_figure_review") or {}
    checklist = [
        "Read target vault contract files before any final wiki write: " + ", ".join(str(item) for item in read_before),
        "Read the EPI evidence handoff: "
        + ", ".join(str(path) for path in handoff_paths)
        + ".",
        "source-first rule: read the source paper artifacts before any final wiki write: "
        + ", ".join(str(item) for item in raw_artifacts or primary_order)
        + ".",
        "Source-first rule: " + str(source_policy or "reader outputs are navigation and quality signals, not substitutes for the source paper."),
        "Review formulas, figures, tables, and images before distilling reusable claims: "
        + ", ".join(
            str(item)
            for item in [
                formula_figure_review.get("formulas"),
                formula_figure_review.get("figures_tables_images"),
                formula_figure_review.get("parse_uncertainty"),
            ]
            if item
        )
        + ".",
        f"Inspect paper-gate status={gate.get('status')} next_action={gate.get('next_action')}; stop on any failure checks.",
        "Search existing wiki pages with index/frontmatter, QMD when configured, and grep before creating a new page.",
        "Merge or update existing notes before creating duplicates.",
        "Preserve source provenance and distinguish extracted, inferred, and ambiguous claims.",
        "Respect vault-local staged writes, link format, language policy, taxonomy, and frontmatter schema.",
        "Do not write final pages from EPI suggested routes directly.",
    ]
    if gate.get("check_suite", {}).get("conclusion") == "action_required":
        checklist.insert(
            3,
            "Record human approval before the wiki ingest agent performs final or staged vault writes.",
        )
    return checklist


def build_wiki_ingest_handoff(vault_path: Path, slug: str) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    staging_root = vault_path / "_staging" / "papers" / slug
    plan_path = staging_root / "promotion-plan.json"
    plan = _read_json(plan_path)
    brief_path = _brief_path_from_plan(plan, staging_root)
    brief = _read_json(brief_path)
    gate = build_paper_gate(vault_path, slug)
    ingest_policy = brief.get("ingest_policy") if isinstance(brief.get("ingest_policy"), dict) else {}
    framework_references = (
        brief.get("wiki_framework_references")
        if isinstance(brief.get("wiki_framework_references"), list)
        else []
    )
    rule_source_model = (
        brief.get("wiki_rule_source_model")
        if isinstance(brief.get("wiki_rule_source_model"), dict)
        else {}
    )
    gate_failure_checks = [
        run.get("name")
        for run in gate.get("check_suite", {}).get("check_runs", [])
        if run.get("conclusion") == "failure"
    ]
    gate_action_required_checks = [
        run.get("name")
        for run in gate.get("check_suite", {}).get("check_runs", [])
        if run.get("conclusion") == "action_required"
    ]
    ready_after_human_approval = (
        gate.get("next_action") == "run-wiki-ingest-agent"
        and not gate_failure_checks
        and gate_action_required_checks == ["human-approval"]
    )
    ready_for_agent = (
        gate.get("next_action") == "run-wiki-ingest-agent"
        and not gate_failure_checks
        and not gate_action_required_checks
    )
    return {
        "title": "EPI Wiki Ingest Handoff",
        "paper_slug": slug,
        "paper_title": brief.get("title") or gate.get("paper_title") or slug,
        "wiki_write_model": plan.get("wiki_write_model") or "agent-mediated-vault-contract",
        "handoff_type": plan.get("handoff_type") or brief.get("handoff_type"),
        "local_skill_policy": "helpers-not-authority",
        "ready_for_agent": ready_for_agent,
        "ready_after_human_approval": ready_after_human_approval,
        "paper_gate": {
            "status": gate.get("status"),
            "next_action": gate.get("next_action"),
            "conclusion": gate.get("check_suite", {}).get("conclusion"),
            "failure_checks": gate_failure_checks,
            "action_required_checks": gate_action_required_checks,
        },
        "paths": {
            "promotion_plan": str(plan_path),
            "wiki_ingest_brief": str(brief_path),
            "agent_handoff_paths": plan.get("agent_handoff_paths") or [],
        },
        "contract_files": _contract_file_status(vault_path),
        "framework_references": framework_references,
        "wiki_rule_source_model": rule_source_model,
        "suggested_routes_only": bool(ingest_policy.get("suggested_routes_only")),
        "suggested_routes": brief.get("suggested_routes") or [],
        "entrypoints": brief.get("entrypoints") or {},
        "trust_status": brief.get("trust_status") or {},
        "agent_checklist": _agent_checklist(gate=gate, plan=plan, brief=brief),
    }


def render_wiki_ingest_handoff(handoff: dict[str, Any]) -> str:
    lines = [
        f"# {handoff.get('title', 'EPI Wiki Ingest Handoff')} - {handoff.get('paper_slug')}",
        "",
        f"title: {handoff.get('paper_title')}",
        f"handoff_type: {handoff.get('handoff_type')}",
        f"wiki_write_model: {handoff.get('wiki_write_model')}",
        f"ready_for_agent: {str(handoff.get('ready_for_agent')).lower()}",
        f"ready_after_human_approval: {str(handoff.get('ready_after_human_approval')).lower()}",
        f"local skills: {handoff.get('local_skill_policy')}",
        "",
        "## Paper Gate",
        "",
        f"- status: {handoff.get('paper_gate', {}).get('status')}",
        f"- next_action: {handoff.get('paper_gate', {}).get('next_action')}",
        f"- conclusion: {handoff.get('paper_gate', {}).get('conclusion')}",
        "",
        "## Contract Files",
        "",
    ]
    for relative, record in handoff.get("contract_files", {}).items():
        state = "present" if record.get("present") else "missing"
        lines.append(f"- {relative}: {state}")
    lines.extend(["", "## Rule Sources", ""])
    for item in handoff.get("wiki_rule_source_model", {}).get("resolution_order") or []:
        source = item.get("source")
        role = item.get("role")
        lines.append(f"- {source}: {role}")
    lines.extend(["", "## Framework References", ""])
    for item in handoff.get("framework_references") or []:
        lines.append(f"- {item.get('name')}")
    lines.extend(["", "## Suggested Routes", ""])
    for item in handoff.get("suggested_routes") or []:
        lines.append(f"- {item.get('page_type')}: {item.get('target')}")
    lines.extend(["", "## Agent Checklist", ""])
    for item in handoff.get("agent_checklist") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
