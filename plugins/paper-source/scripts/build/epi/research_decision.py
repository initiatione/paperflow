from __future__ import annotations

from pathlib import Path

from epi.artifacts import write_json_atomic, write_text_atomic


ROLE_LENSES = ("nature-sci-editor", "peer-reviewer", "senior-domain-researcher")


def _reviewer_lens(reviewer: dict) -> str:
    protocol = reviewer.get("review_protocol") or {}
    return str(protocol.get("lens") or reviewer.get("name") or "")


def _role_reviewers(reviewers: list[dict]) -> list[dict]:
    by_lens = {_reviewer_lens(reviewer): reviewer for reviewer in reviewers}
    return [by_lens[lens] for lens in ROLE_LENSES if lens in by_lens]


def _recommendation(final_outcome: str) -> tuple[str, str]:
    if final_outcome == "pass":
        return "stage-for-promotion-review", "stage"
    return "revise-reader", "revise-reader"


def _action_for_reviewer(reviewer: dict) -> dict:
    lens = _reviewer_lens(reviewer)
    verdict = reviewer.get("verdict", "fail")
    evidence = list(reviewer.get("evidence") or [])
    warnings = list(reviewer.get("warnings") or [])
    if verdict == "pass":
        action = "preserve"
        rationale = f"{lens} reviewer accepted the current reader artifact."
    else:
        action = "revise"
        rationale = f"{lens} reviewer requires reader repair before promotion."
    return {
        "lens": lens,
        "reviewer": reviewer.get("name"),
        "verdict": verdict,
        "action": action,
        "rationale": rationale,
        "evidence": evidence,
        "warnings": warnings,
    }


def _role_assessment_for_reviewer(reviewer: dict) -> dict:
    action_item = _action_for_reviewer(reviewer)
    protocol = reviewer.get("review_protocol") or {}
    verdict = reviewer.get("verdict", "fail")
    evidence = list(reviewer.get("evidence") or [])
    return {
        "lens": action_item["lens"],
        "reviewer": action_item["reviewer"],
        "responsibility": reviewer.get("scope", ""),
        "artifact": protocol.get("consumes"),
        "required_sections": list(protocol.get("required_sections") or []),
        "verdict": verdict,
        "action": action_item["action"],
        "promotion_blocking": verdict != "pass",
        "primary_evidence": evidence[0] if evidence else "",
        "warnings": list(reviewer.get("warnings") or []),
    }


def _panel_summary(
    final_outcome: str,
    *,
    hard_rule: str,
    role_assessments: list[dict],
    warning_reviewers: list[str],
) -> dict:
    blocking_lenses = [
        assessment["lens"]
        for assessment in role_assessments
        if assessment["promotion_blocking"]
    ]
    consensus = "approve-for-staging" if final_outcome == "pass" and not blocking_lenses else "revise-before-staging"
    return {
        "consensus": consensus,
        "blocking_lenses": blocking_lenses,
        "warning_reviewers": warning_reviewers,
        "hard_rule": hard_rule,
    }


def build_research_decision(final_outcome: str, reviewers: list[dict], *, hard_rule: str) -> dict:
    recommendation, next_action = _recommendation(final_outcome)
    role_reviewers = _role_reviewers(reviewers)
    role_verdicts = {_reviewer_lens(reviewer): reviewer.get("verdict", "fail") for reviewer in role_reviewers}
    failed_reviewers = [
        reviewer.get("name")
        for reviewer in reviewers
        if reviewer.get("verdict") != "pass"
    ]
    warning_reviewers = [
        reviewer.get("name")
        for reviewer in reviewers
        if reviewer.get("warnings")
    ]
    role_assessments = [_role_assessment_for_reviewer(reviewer) for reviewer in role_reviewers]
    return {
        "schema_version": "epi-research-decision-v1",
        "recommendation": recommendation,
        "next_action": next_action,
        "decision_inputs": {
            "final_outcome": final_outcome,
            "hard_rule": hard_rule,
            "failed_reviewers": failed_reviewers,
            "warning_reviewers": warning_reviewers,
        },
        "role_verdicts": role_verdicts,
        "panel_summary": _panel_summary(
            final_outcome,
            hard_rule=hard_rule,
            role_assessments=role_assessments,
            warning_reviewers=warning_reviewers,
        ),
        "role_assessments": role_assessments,
        "action_items": [_action_for_reviewer(reviewer) for reviewer in role_reviewers],
    }


def render_research_decision_markdown(decision: dict) -> str:
    lines = [
        "# Research Decision",
        "",
        f"Recommendation: {decision['recommendation']}",
        f"Next action: {decision['next_action']}",
        "",
        "## Panel Summary",
    ]
    panel = decision.get("panel_summary") or {}
    lines.append(f"- Consensus: {panel.get('consensus', '')}")
    lines.append(f"- Blocking lenses: {', '.join(panel.get('blocking_lenses') or []) or 'None'}")
    lines.append(f"- Warning reviewers: {', '.join(panel.get('warning_reviewers') or []) or 'None'}")
    lines.extend(
        [
            "",
            "## Role Assessment Matrix",
        ]
    )
    for assessment in decision.get("role_assessments") or []:
        lines.append(
            f"- {assessment['lens']}: {assessment['verdict']} -> {assessment['action']} "
            f"({assessment['artifact']})"
        )
        lines.append(f"  - Responsibility: {assessment['responsibility']}")
        if assessment.get("promotion_blocking"):
            lines.append("  - Promotion blocking: true")
        if assessment.get("primary_evidence"):
            lines.append(f"  - Evidence: {assessment['primary_evidence']}")
    lines.extend(
        [
            "",
            "## Role Verdicts",
        ]
    )
    for lens, verdict in decision["role_verdicts"].items():
        lines.append(f"- {lens}: {verdict}")
    lines.extend(["", "## Action Items"])
    for item in decision["action_items"]:
        lines.append(f"- {item['lens']}: {item['action']} ({item['reviewer']})")
        if item["evidence"]:
            lines.append(f"  - Evidence: {item['evidence'][0]}")
        if item["warnings"]:
            lines.append(f"  - Warning: {item['warnings'][0]}")
    lines.extend(["", "## Decision Inputs"])
    inputs = decision["decision_inputs"]
    lines.append(f"- Final outcome: {inputs['final_outcome']}")
    lines.append(f"- Hard rule: {inputs['hard_rule']}")
    if inputs["failed_reviewers"]:
        lines.append(f"- Failed reviewers: {', '.join(inputs['failed_reviewers'])}")
    if inputs["warning_reviewers"]:
        lines.append(f"- Warning reviewers: {', '.join(inputs['warning_reviewers'])}")
    lines.append("")
    return "\n".join(lines)


def write_research_decision(critic_dir: Path, final_outcome: str, reviewers: list[dict], *, hard_rule: str) -> dict:
    decision = build_research_decision(final_outcome, reviewers, hard_rule=hard_rule)
    write_json_atomic(critic_dir / "research-decision.json", decision)
    write_text_atomic(critic_dir / "research-decision.md", render_research_decision_markdown(decision))
    return decision
