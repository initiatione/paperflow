from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from epi.artifacts import staging_paper_root
from epi.paper_gate import build_paper_gate
from epi.wiki_ingest_approval import human_approval_record_path
from epi.wiki_contracts import (
    formal_page_family_names,
    formal_page_family_paths,
    page_lifecycle_states,
    qmd_collection_policy,
    required_wiki_skills,
    research_review_fields,
)
from epi.wiki_handoff_contracts import agent_context_policy as default_agent_context_policy


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


def _family_paths(values: object) -> list[str]:
    records = values if isinstance(values, list) else []
    paths: list[str] = []
    for item in records:
        if isinstance(item, dict):
            value = str(item.get("path") or item.get("name") or "").strip()
        else:
            value = str(item or "").strip()
        if not value:
            continue
        if not value.endswith("/"):
            value += "/"
        paths.append(value)
    return paths or formal_page_family_paths()


def _agent_context_policy(brief: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        brief.get("agent_context_policy"),
        (
            brief.get("wiki_skill_handoff", {}).get("agent_context_policy")
            if isinstance(brief.get("wiki_skill_handoff"), dict)
            else None
        ),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return dict(candidate)
    return default_agent_context_policy()


def _agent_checklist(
    *,
    gate: dict[str, Any],
    plan: dict[str, Any],
    brief: dict[str, Any],
) -> list[str]:
    rule_source_model = brief.get("wiki_rule_source_model", {}) if isinstance(brief.get("wiki_rule_source_model"), dict) else {}
    execution_agent_policy = (
        rule_source_model.get("execution_agent_policy")
        if isinstance(rule_source_model.get("execution_agent_policy"), dict)
        else {}
    )
    read_before = rule_source_model.get("must_read_before_final_write") or CONTRACT_FILES
    handoff_paths = plan.get("agent_handoff_paths") or []
    source_policy = brief.get("ingest_policy", {}).get("source_first_policy")
    source_bundle = brief.get("source_bundle") or {}
    raw_artifacts = source_bundle.get("raw_artifacts") or []
    primary_order = source_bundle.get("primary_source_reading_order") or []
    evidence_bundle = source_bundle.get("evidence", {}) if isinstance(source_bundle.get("evidence"), dict) else {}
    claim_support_artifact = evidence_bundle.get("claim_support_artifact")
    evidence_map_artifact = evidence_bundle.get("exact_evidence_artifact")
    full_text_evidence_index = evidence_bundle.get("full_text_evidence_index")
    optional_evidence_aids = source_bundle.get("optional_evidence_aids") or []
    formula_figure_review = source_bundle.get("formula_figure_review") or {}
    final_source_review_contract = (
        brief.get("final_source_review_contract")
        if isinstance(brief.get("final_source_review_contract"), dict)
        else {}
    )
    final_source_review_path = final_source_review_contract.get("suggested_output_path") or "final-source-review.json"
    families = _family_paths(
        brief.get("formal_page_family_records")
        or brief.get("formal_page_families")
        or final_source_review_contract.get("formal_page_families")
    )
    review_fields = (
        brief.get("research_review_fields")
        or final_source_review_contract.get("research_review_fields")
        or research_review_fields()
    )
    checklist = [
        "Execution agent is neutral: Claude, Codex, or another wiki-capable agent may perform the final write if it follows the same handoff, approval, provenance, and vault-contract gates.",
        "Read target vault contract files before any final wiki write: " + ", ".join(str(item) for item in read_before),
        "Read the EPI evidence handoff: "
        + ", ".join(str(path) for path in handoff_paths)
        + ".",
        "Invoke PRW $paper-research-wiki for formal wiki writing; use wiki-ingest-brief.json as the canonical source/evidence handoff.",
        "External wiki skills such as llm-wiki, wiki-ingest, wiki-provenance, tag-taxonomy, and wiki-lint are optional helpers or internalized PRW policies, not required runtime dependencies.",
        "Batch deposition rule: compare this paper with the current batch or neighboring EPI source bundles before creating reusable concept or synthesis pages.",
        "source-first rule: read the source paper artifacts before any final wiki write: "
        + ", ".join(str(item) for item in raw_artifacts or primary_order)
        + ".",
        "Source-first rule: " + str(source_policy or "reader outputs are navigation and quality signals, not substitutes for the source paper."),
        (
            "Use reader evidence aids to separate source-grounded, metadata-only, and inferred claims: "
            + ", ".join(str(item) for item in [evidence_map_artifact, claim_support_artifact] if item)
            + "."
            if evidence_map_artifact or claim_support_artifact
            else "No reader claim map is required for this workflow mode; derive support status directly from paper.pdf, metadata, MinerU Markdown/TeX, images, and manifest."
        ),
        "Optional reader/critic aids actually present: "
        + (", ".join(str(item) for item in optional_evidence_aids) if optional_evidence_aids else "none; this is source-only fast-ingest.")
        + ".",
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
        "Route formal research knowledge into the seven EPI page families when useful: "
        + ", ".join(families)
        + ".",
        "Before record-wiki-ingest, write "
        + str(final_source_review_path)
        + " using schema "
        + str(final_source_review_contract.get("record_schema_version") or "epi-final-source-review-v1")
        + "; record artifact hashes, formula review, figure/image review, PDF fallback decision, final page provenance, and research fields "
        + ", ".join(str(field) for field in review_fields)
        + ".",
        f"Inspect paper-gate status={gate.get('status')} next_action={gate.get('next_action')}; stop on any failure checks.",
        "Search existing wiki pages with index/frontmatter, QMD when configured, and grep before creating a new page.",
        "Merge or update existing notes before creating duplicates.",
        "Preserve source provenance and distinguish extracted, inferred, and ambiguous claims.",
        "Respect vault-local staged writes, link format, language policy, taxonomy, and frontmatter schema.",
        "Do not write final pages from EPI suggested routes directly; EPI must only write internal underscore artifacts.",
    ]
    if full_text_evidence_index:
        checklist.insert(
            8,
            "Use full-text evidence-index locator aid "
            + str(full_text_evidence_index)
            + " to find page/section/chunk evidence, then verify important claims against MinerU Markdown, TeX, images, manifest, and paper.pdf before final prose.",
        )
    brand_neutrality = execution_agent_policy.get("brand_neutrality")
    if brand_neutrality:
        checklist.insert(1, "Executor policy: " + str(brand_neutrality))
    human_approval_run = next(
        (
            run
            for run in gate.get("check_suite", {}).get("check_runs", [])
            if run.get("name") == "human-approval"
        ),
        {},
    )
    if gate.get("check_suite", {}).get("conclusion") == "action_required":
        checklist.insert(
            3,
            "Record human approval before the wiki ingest agent performs final or staged vault writes.",
        )
    elif human_approval_run.get("conclusion") == "success":
        details = human_approval_run.get("details") if isinstance(human_approval_run.get("details"), dict) else {}
        checklist.insert(
            3,
            "Human approval is recorded at "
            + str(details.get("path") or "human-approval.json")
            + "; the wiki ingest agent may proceed if no failure checks appear.",
        )
    return checklist


def build_wiki_ingest_handoff(vault_path: Path, slug: str) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    staging_root = staging_paper_root(vault_path, slug)
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
    approval_path = human_approval_record_path(vault_path, slug)
    source_review_contract = (
        brief.get("final_source_review_contract")
        if isinstance(brief.get("final_source_review_contract"), dict)
        else {}
    )
    source_bundle = brief.get("source_bundle") if isinstance(brief.get("source_bundle"), dict) else {}
    evidence_bundle = (
        source_bundle.get("evidence")
        if isinstance(source_bundle.get("evidence"), dict)
        else {}
    )
    return {
        "title": "EPI Wiki Ingest Handoff",
        "paper_slug": slug,
        "paper_title": brief.get("title") or gate.get("paper_title") or slug,
        "wiki_write_model": plan.get("wiki_write_model") or "agent-mediated-vault-contract",
        "handoff_type": plan.get("handoff_type") or brief.get("handoff_type"),
        "local_skill_policy": "helpers-not-authority",
        "epi_write_scope": plan.get("epi_write_scope") or ingest_policy.get("epi_write_scope"),
        "formal_routes_suggested": bool(brief.get("formal_routes_suggested", True)),
        "formal_page_families": (
            brief.get("formal_page_families")
            or source_review_contract.get("formal_page_families")
            or plan.get("formal_page_families")
            or formal_page_family_names()
        ),
        "research_review_fields": (
            brief.get("research_review_fields")
            or source_review_contract.get("research_review_fields")
            or plan.get("research_review_fields")
            or research_review_fields()
        ),
        "page_lifecycle_states": (
            brief.get("page_lifecycle_states")
            or source_review_contract.get("page_lifecycle_states")
            or plan.get("page_lifecycle_states")
            or page_lifecycle_states()
        ),
        "wiki_batch_handoff_required": bool(
            plan.get("wiki_batch_handoff_required") or ingest_policy.get("wiki_batch_handoff_required")
        ),
        "required_wiki_skills": (
            ingest_policy.get("required_wiki_skills")
            or source_review_contract.get("required_wiki_skills")
            or plan.get("required_wiki_skills")
            or required_wiki_skills()
        ),
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
            "human_approval": str(approval_path),
            "agent_handoff_paths": plan.get("agent_handoff_paths") or [],
        },
        "final_source_review_contract": source_review_contract,
        "evidence_index": {
            "paper": evidence_bundle.get("full_text_evidence_index"),
            "vault": evidence_bundle.get("vault_evidence_index"),
            "chunk_count": evidence_bundle.get("full_text_chunk_count", 0),
            "input_hashes": evidence_bundle.get("full_text_input_hashes", {}),
            "warnings": evidence_bundle.get("full_text_warnings", []),
        },
        "contract_files": _contract_file_status(vault_path),
        "framework_references": framework_references,
        "wiki_rule_source_model": rule_source_model,
        "execution_agent_policy": (
            rule_source_model.get("execution_agent_policy")
            if isinstance(rule_source_model.get("execution_agent_policy"), dict)
            else {}
        ),
        "suggested_routes": brief.get("suggested_routes") or [],
        "handoff_artifacts": brief.get("handoff_artifacts") or [],
        "candidate_topics": brief.get("candidate_topics") or [],
        "candidate_clusters": brief.get("candidate_clusters") or [],
        "wiki_skill_handoff": brief.get("wiki_skill_handoff") or {},
        "qmd_collection_policy": (
            brief.get("qmd_collection_policy")
            if isinstance(brief.get("qmd_collection_policy"), dict)
            else qmd_collection_policy()
        ),
        "agent_context_policy": _agent_context_policy(brief),
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
        f"epi_write_scope: {handoff.get('epi_write_scope')}",
        f"wiki_batch_handoff_required: {str(bool(handoff.get('wiki_batch_handoff_required'))).lower()}",
        f"formal_routes_suggested: {str(bool(handoff.get('formal_routes_suggested'))).lower()}",
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
    execution_policy = handoff.get("execution_agent_policy") or {}
    lines.extend(["", "## Execution Agent Policy", ""])
    if execution_policy:
        allowed = ", ".join(str(item) for item in execution_policy.get("allowed_executors") or [])
        lines.append(f"- allowed_executors: {allowed}")
        lines.append(f"- brand_neutrality: {execution_policy.get('brand_neutrality')}")
        lines.append(f"- local_skills_role: {execution_policy.get('local_skills_role')}")
    else:
        lines.append("- missing")
    qmd_policy = handoff.get("qmd_collection_policy") if isinstance(handoff.get("qmd_collection_policy"), dict) else {}
    lines.extend(["", "## QMD Collection Boundary", ""])
    if qmd_policy:
        lines.append(f"- collection: {qmd_policy.get('collection_name')}")
        lines.append(f"- pattern: {qmd_policy.get('pattern')}")
        allowed = ", ".join(str(item) for item in qmd_policy.get("allowed_index_scope") or [])
        ignored = ", ".join(str(item) for item in qmd_policy.get("ignore_patterns") or [])
        forbidden = ", ".join(str(item) for item in qmd_policy.get("forbidden_examples") or [])
        lines.append(f"- allowed_index_scope: {allowed}")
        lines.append(f"- ignore_patterns: {ignored}")
        lines.append(f"- forbidden_examples: {forbidden}")
        for command in qmd_policy.get("verification_commands") or []:
            lines.append(f"- verify: {command}")
    else:
        lines.append("- missing")
    context_policy = handoff.get("agent_context_policy") if isinstance(handoff.get("agent_context_policy"), dict) else {}
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
    lines.extend(["", "## Framework References", ""])
    for item in handoff.get("framework_references") or []:
        lines.append(f"- {item.get('name')}")
    lines.extend(["", "## Internal Handoff Artifacts", ""])
    for item in handoff.get("handoff_artifacts") or []:
        lines.append(f"- {item.get('artifact_type')}: {item.get('target')}")
    if not handoff.get("handoff_artifacts"):
        lines.append("- missing")
    lines.extend(["", "## Formal Routes", ""])
    if handoff.get("suggested_routes"):
        for item in handoff.get("suggested_routes") or []:
            lines.append(f"- blocked legacy route: {item.get('page_type')}: {item.get('target')}")
    else:
        lines.append("- none; wiki skill decides final pages after batch distillation")
    lines.extend(["", "## Required Wiki Skills", ""])
    for skill in handoff.get("required_wiki_skills") or []:
        lines.append(f"- {skill}")
    lines.extend(["", "## Formal Page Families", ""])
    for family in _family_paths(handoff.get("formal_page_families")):
        lines.append(f"- {family}")
    lines.extend(["", "## Research Review Fields", ""])
    for field in handoff.get("research_review_fields") or []:
        lines.append(f"- {field}")
    lifecycle_states = handoff.get("page_lifecycle_states") or []
    if lifecycle_states:
        lines.append("")
        lines.append("page_lifecycle: " + " -> ".join(str(state) for state in lifecycle_states))
    contract = handoff.get("final_source_review_contract") or {}
    paths = handoff.get("paths") if isinstance(handoff.get("paths"), dict) else {}
    lines.extend(["", "## Human Approval", ""])
    lines.append(f"- path: {paths.get('human_approval') or '-'}")
    lines.extend(["", "## Final Source Review", ""])
    lines.append(f"- required: {str(bool(contract.get('required'))).lower()}")
    lines.append(f"- suggested_output_path: {contract.get('suggested_output_path') or 'final-source-review.json'}")
    lines.append(f"- schema: {contract.get('record_schema_version') or 'epi-final-source-review-v1'}")
    lines.extend(["", "## Agent Checklist", ""])
    for item in handoff.get("agent_checklist") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
