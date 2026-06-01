from __future__ import annotations

import re
from pathlib import Path

from epi.artifacts import write_json_atomic, write_text_atomic


ROLE_SPECS = [
    {
        "lens": "nature-sci-editor",
        "heading": "Nature Sci Editor",
        "responsibility": "Tighten title identity, novelty framing, significance, and scope discipline.",
        "target_artifacts": ["reader/editorial-summary.md"],
        "handles_checks": {"paper_identity", "claim_support", "scope_overclaim", "role_artifact_contract"},
    },
    {
        "lens": "peer-reviewer",
        "heading": "Peer Reviewer",
        "responsibility": "Audit methods, evidence addresses, benchmark claims, and reproducibility hooks.",
        "target_artifacts": ["reader/technical-reading.md", "reader/reproducibility.md"],
        "handles_checks": {
            "claim_support",
            "benchmark_integrity",
            "engineering_reproducibility",
            "parse_vs_paper_failure",
            "reader_evidence_traceability",
            "parse_materialization",
            "role_artifact_contract",
        },
    },
    {
        "lens": "senior-domain-researcher",
        "heading": "Senior Domain Researcher",
        "responsibility": "Judge domain fit, transfer value, experiment follow-ups, and overclaim risk.",
        "target_artifacts": ["reader/research-notes.md", "reader/implementation-ideas.md"],
        "handles_checks": {
            "scope_overclaim",
            "engineering_reproducibility",
            "role_artifact_contract",
        },
    },
]

CHECK_TARGETS = {
    "paper_identity": ["metadata.json", "reader/reader.md", "reader/editorial-summary.md"],
    "claim_support": [
        "reader/reader.md",
        "reader/editorial-summary.md",
        "reader/technical-reading.md",
        "reader/research-notes.md",
    ],
    "benchmark_integrity": ["reader/technical-reading.md", "reader/reproducibility.md"],
    "engineering_reproducibility": ["reader/reproducibility.md", "reader/technical-reading.md"],
    "scope_overclaim": ["reader/editorial-summary.md", "reader/research-notes.md"],
    "parse_vs_paper_failure": ["paper.pdf", "reader/figures.md", "reader/technical-reading.md"],
    "reader_evidence_traceability": ["reader/*.md", "reader/evidence-map.json"],
    "parse_materialization": ["mineru/<slug>.md"],
}

CHECK_INSTRUCTIONS = {
    "paper_identity": "Add a stable paper identity: title plus source URL, DOI, arXiv ID, or venue.",
    "claim_support": "Add local structured Evidence lines under every core contribution, performance, SOTA, or generalization claim.",
    "benchmark_integrity": "For outperform/SOTA language, add baseline, metric, dataset/task, and experiment-setting context.",
    "engineering_reproducibility": "Record code, data, model, config, simulator, and hardware availability as explicit reproducibility hooks.",
    "scope_overclaim": "Rewrite deployment or generalization language so it matches the actual simulation, demo, or small-scale evidence.",
    "parse_vs_paper_failure": "Inspect the PDF before treating missing figures or formulas in MinerU output as absent from the paper.",
    "reader_evidence_traceability": "Repair Evidence addresses so each reader claim resolves to metadata, parsed paper text, parsed images, or inference basis.",
    "parse_materialization": "Rerun parsing or attach the canonical MinerU markdown at mineru/<slug>.md before critic review can trust reader artifacts.",
    "role_artifact_contract": "Restore the role-specific required sections and structured Evidence lines for the target reader artifact.",
}

ROLE_REVIEWER_LENSES = {
    "editorial-significance-critic": "nature-sci-editor",
    "peer-review-methods-critic": "peer-reviewer",
    "domain-fit-critic": "senior-domain-researcher",
}


def _reviewer_lens(reviewer: dict) -> str:
    protocol = reviewer.get("review_protocol") or {}
    return str(protocol.get("lens") or ROLE_REVIEWER_LENSES.get(str(reviewer.get("name")), "") or reviewer.get("name") or "")


def _consumed_artifacts(reviewer: dict) -> list[str]:
    consumes = (reviewer.get("review_protocol") or {}).get("consumes")
    if isinstance(consumes, list):
        return [str(item) for item in consumes]
    if isinstance(consumes, str):
        return [consumes]
    return []


def _check_from_evidence(reviewer: dict, evidence: str) -> str:
    reviewer_name = str(reviewer.get("name") or "")
    if reviewer_name == "paper-quality-critic":
        match = re.match(r"^([a-z_]+):", evidence)
        return match.group(1) if match else "paper_quality"
    if reviewer_name == "reader-quality-critic":
        return "reader_evidence_traceability"
    if reviewer_name == "parse-quality-critic":
        return "parse_materialization"
    if (reviewer.get("review_protocol") or {}).get("required_sections"):
        return "role_artifact_contract"
    return reviewer_name.removesuffix("-critic").replace("-", "_") or "critic_review"


def _target_artifacts(reviewer: dict, check: str) -> list[str]:
    if check in CHECK_TARGETS:
        return CHECK_TARGETS[check]
    consumed = _consumed_artifacts(reviewer)
    return consumed or ["reader/reader.md"]


def _repair_item(reviewer: dict, evidence: str, *, promotion_blocking: bool) -> dict:
    check = _check_from_evidence(reviewer, evidence)
    return {
        "reviewer": reviewer.get("name"),
        "lens": _reviewer_lens(reviewer),
        "check": check,
        "severity": "blocker" if promotion_blocking else "warning",
        "promotion_blocking": promotion_blocking,
        "target_artifacts": _target_artifacts(reviewer, check),
        "instruction": CHECK_INSTRUCTIONS.get(check, "Revise the reader artifact using the critic evidence."),
        "evidence": evidence,
    }


def _blocking_repairs(reviewers: list[dict]) -> list[dict]:
    repairs: list[dict] = []
    for reviewer in reviewers:
        if reviewer.get("verdict") == "pass":
            continue
        for evidence in reviewer.get("evidence") or []:
            repairs.append(_repair_item(reviewer, str(evidence), promotion_blocking=True))
    return repairs


def _warning_followups(reviewers: list[dict]) -> list[dict]:
    followups: list[dict] = []
    for reviewer in reviewers:
        for warning in reviewer.get("warnings") or []:
            followups.append(_repair_item(reviewer, str(warning), promotion_blocking=False))
    return followups


def _role_matches_item(role: dict, item: dict) -> bool:
    if item["lens"] == role["lens"]:
        return True
    return item["check"] in role["handles_checks"]


def _role_worklist(blocking_repairs: list[dict], warning_followups: list[dict]) -> list[dict]:
    worklist: list[dict] = []
    for role in ROLE_SPECS:
        role_blocking = [item for item in blocking_repairs if _role_matches_item(role, item)]
        role_warnings = [item for item in warning_followups if _role_matches_item(role, item)]
        worklist.append(
            {
                "lens": role["lens"],
                "heading": role["heading"],
                "responsibility": role["responsibility"],
                "target_artifacts": role["target_artifacts"],
                "blocking_repairs": role_blocking,
                "warning_followups": role_warnings,
            }
        )
    return worklist


def build_reader_revision_plan(
    final_outcome: str,
    reviewers: list[dict],
    *,
    hard_rule: str,
) -> dict:
    blocking_repairs = _blocking_repairs(reviewers)
    warning_followups = _warning_followups(reviewers)
    if blocking_repairs:
        recommendation = "revise-reader"
        next_action = "revise-reader"
    elif warning_followups:
        recommendation = "preserve-reader-with-warning-followups"
        next_action = "stage" if final_outcome == "pass" else "revise-reader"
    else:
        recommendation = "preserve-reader"
        next_action = "stage" if final_outcome == "pass" else "revise-reader"
    return {
        "schema_version": "epi-reader-revision-plan-v1",
        "recommendation": recommendation,
        "next_action": next_action,
        "hard_rule": hard_rule,
        "blocking_repairs": blocking_repairs,
        "warning_followups": warning_followups,
        "role_worklist": _role_worklist(blocking_repairs, warning_followups),
    }


def _render_item(item: dict) -> list[str]:
    lines = [
        f"- [{item['reviewer']}] {item['check']} -> {', '.join(item['target_artifacts'])}",
        f"  - Lens: {item['lens']}",
        f"  - Instruction: {item['instruction']}",
        f"  - Evidence: {item['evidence']}",
    ]
    return lines


def render_reader_revision_plan_markdown(plan: dict) -> str:
    lines = [
        "# Reader Revision Plan",
        "",
        f"Recommendation: {plan['recommendation']}",
        f"Next action: {plan['next_action']}",
        f"Hard rule: {plan['hard_rule']}",
        "",
        "## Blocking Repairs",
    ]
    if plan["blocking_repairs"]:
        for item in plan["blocking_repairs"]:
            lines.extend(_render_item(item))
    else:
        lines.append("- None")

    lines.extend(["", "## Warning Follow-ups"])
    if plan["warning_followups"]:
        for item in plan["warning_followups"]:
            lines.extend(_render_item(item))
    else:
        lines.append("- None")

    lines.extend(["", "## Role Worklist"])
    for role in plan["role_worklist"]:
        lines.extend(
            [
                "",
                f"## {role['heading']}",
                f"Responsibility: {role['responsibility']}",
                f"Target artifacts: {', '.join(role['target_artifacts'])}",
                "",
                "Blocking repairs:",
            ]
        )
        if role["blocking_repairs"]:
            for item in role["blocking_repairs"]:
                lines.append(f"- {item['check']}: {item['instruction']}")
                lines.append(f"  - Evidence: {item['evidence']}")
        else:
            lines.append("- None")
        lines.append("Warning follow-ups:")
        if role["warning_followups"]:
            for item in role["warning_followups"]:
                lines.append(f"- {item['check']}: {item['instruction']}")
                lines.append(f"  - Evidence: {item['evidence']}")
        else:
            lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_reader_revision_plan(
    critic_dir: Path,
    final_outcome: str,
    reviewers: list[dict],
    *,
    hard_rule: str,
) -> dict:
    plan = build_reader_revision_plan(final_outcome, reviewers, hard_rule=hard_rule)
    write_json_atomic(critic_dir / "reader-revision-plan.json", plan)
    write_text_atomic(critic_dir / "reader-revision-plan.md", render_reader_revision_plan_markdown(plan))
    return plan
