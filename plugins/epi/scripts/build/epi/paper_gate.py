from __future__ import annotations

import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from epi.run_critic import HARD_RULE


_ALLOWED_COMPILED_TARGET_ROOTS = {"references", "concepts", "synthesis", "reports"}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _check_run(name: str, conclusion: str, summary: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    run = {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": name,
            "summary": summary,
        },
    }
    if details:
        run["details"] = details
    return run


def _suite_conclusion(check_runs: list[dict[str, Any]]) -> str:
    conclusions = {run["conclusion"] for run in check_runs}
    if "failure" in conclusions:
        return "failure"
    if "action_required" in conclusions:
        return "action_required"
    return "success"


def _staged_paths_from_plan(plan: dict[str, Any]) -> list[Path]:
    paths = []
    if plan.get("staged_reference"):
        paths.append(Path(plan["staged_reference"]))
    for key in ["staged_concepts", "staged_synthesis", "staged_reports"]:
        paths.extend(Path(path) for path in plan.get(key, []))
    return paths


def _is_agent_handoff_plan(plan: dict[str, Any]) -> bool:
    return (
        plan.get("handoff_type") == "agent-mediated-wiki-ingest"
        or plan.get("wiki_write_model") == "agent-mediated-vault-contract"
    )


def _compiled_target_is_safe(target: str) -> bool:
    normalized = str(target or "").replace("\\", "/").strip()
    target_path = PurePosixPath(normalized)
    return (
        bool(normalized)
        and not Path(str(target)).is_absolute()
        and not target_path.is_absolute()
        and ".." not in target_path.parts
        and bool(target_path.parts)
        and target_path.parts[0] in _ALLOWED_COMPILED_TARGET_ROOTS
    )


def _wiki_ingest_brief_check(plan: dict[str, Any]) -> dict[str, Any]:
    brief_path_value = plan.get("wiki_ingest_brief_path")
    if not brief_path_value:
        return _check_run(
            "wiki-ingest-brief",
            "failure",
            "Promotion plan is missing wiki_ingest_brief_path for agent-mediated wiki ingest.",
        )
    brief_path = Path(brief_path_value)
    brief = _read_json(brief_path)
    if not brief:
        return _check_run(
            "wiki-ingest-brief",
            "failure",
            "Wiki ingest brief is missing or invalid.",
            details={"path": str(brief_path)},
        )
    framework_names = [
        str(item.get("name") or "")
        for item in brief.get("wiki_framework_references", [])
        if isinstance(item, dict)
    ]
    ingest_policy = brief.get("ingest_policy") if isinstance(brief.get("ingest_policy"), dict) else {}
    rule_source_model = (
        brief.get("wiki_rule_source_model") if isinstance(brief.get("wiki_rule_source_model"), dict) else {}
    )
    resolution_order = (
        rule_source_model.get("resolution_order") if isinstance(rule_source_model, dict) else []
    ) or []
    resolution_source_text = "\n".join(
        " ".join(
            [
                str(item.get("source") or ""),
                str(item.get("role") or ""),
            ]
        )
        for item in resolution_order
        if isinstance(item, dict)
    )
    write_requirements = rule_source_model.get("write_contract_requirements") or []
    write_requirement_text = "\n".join(str(item) for item in write_requirements or [])
    source_bundle = brief.get("source_bundle") if isinstance(brief.get("source_bundle"), dict) else {}
    raw_artifacts = [
        str(item)
        for item in source_bundle.get("raw_artifacts", [])
        if isinstance(item, str)
    ]
    raw_artifact_text = "\n".join(raw_artifacts)
    formula_figure_review = (
        source_bundle.get("formula_figure_review")
        if isinstance(source_bundle.get("formula_figure_review"), dict)
        else {}
    )
    formula_figure_text = "\n".join(str(item) for item in formula_figure_review.values())
    required_frameworks = [
        "Ar9av/obsidian-wiki",
        "kepano/obsidian-skills",
        "initiatione/obsidian-wiki-dev",
    ]
    missing_frameworks = [
        name for name in required_frameworks if not any(name in framework for framework in framework_names)
    ]
    issues = []
    if brief.get("handoff_type") != "agent-mediated-wiki-ingest":
        issues.append("handoff_type is not agent-mediated-wiki-ingest")
    if not ingest_policy.get("suggested_routes_only"):
        issues.append("brief must mark suggested routes as non-authoritative")
    source_first_policy = str(ingest_policy.get("source_first_policy") or "")
    if "source paper" not in source_first_policy or "not substitutes" not in source_first_policy:
        issues.append("source-first ingest policy is missing")
    required_raw_artifacts = [
        "paper.pdf",
        "metadata.json",
        "mineru/paper.md",
        "mineru/paper.tex",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]
    missing_raw_artifacts = [
        artifact for artifact in required_raw_artifacts if artifact not in raw_artifact_text
    ]
    if missing_raw_artifacts:
        issues.append("source-first raw artifacts are incomplete")
    formula_figure_lower = formula_figure_text.lower()
    if (
        "formula" not in formula_figure_lower
        or "figure" not in formula_figure_lower
        or "table" not in formula_figure_lower
        or "image" not in formula_figure_lower
    ):
        issues.append("formula/figure/image review requirements are missing")
    if missing_frameworks:
        issues.append("framework references are incomplete")
    if not rule_source_model:
        issues.append("wiki_rule_source_model is missing")
    elif not resolution_order:
        issues.append("wiki rule source resolution_order is missing")
    else:
        required_rule_sources = [
            "target vault AGENTS.md",
            "_meta/schema.md",
            "Ar9av/obsidian-wiki",
            "kepano/obsidian-skills",
            "initiatione/obsidian-wiki-dev",
            "local llm-wiki / wiki-ingest / obsidian-markdown skills",
        ]
        missing_rule_sources = [
            source for source in required_rule_sources if source not in resolution_source_text
        ]
        if missing_rule_sources:
            issues.append("wiki rule source model is incomplete")
        if "adapter" not in resolution_source_text.lower() and "helper" not in resolution_source_text.lower():
            issues.append("local wiki skills must be described as adapters or helpers")
        if "Markdown vault" not in write_requirement_text or "source of truth" not in write_requirement_text:
            issues.append("wiki rule source model must preserve Markdown vault as source of truth")
    if issues:
        return _check_run(
            "wiki-ingest-brief",
            "failure",
            "; ".join(issues) + ".",
            details={"path": str(brief_path), "missing_frameworks": missing_frameworks},
        )
    return _check_run(
        "wiki-ingest-brief",
        "success",
        "Agent-mediated wiki ingest brief is present and delegates final page rules to the vault contract.",
        details={
            "path": str(brief_path),
            "frameworks": framework_names,
            "rule_source_count": len(resolution_order),
        },
    )


def _final_wiki_authority_check(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("final_page_authority") != "target-vault-contract-and-wiki-ingest-agent":
        return _check_run(
            "final-wiki-authority",
            "failure",
            "Final wiki authority must be the target vault contract and wiki ingest agent.",
        )
    return _check_run(
        "final-wiki-authority",
        "success",
        "Final page paths, schema, taxonomy, links, and staged writes are delegated to the target vault contract.",
    )


def _compiled_targets_check(plan: dict[str, Any], staged_paths: list[Path]) -> dict[str, Any]:
    compiled_targets = plan.get("compiled_targets")
    if not isinstance(compiled_targets, list) or not compiled_targets:
        return _check_run(
            "compiled-targets",
            "failure",
            "Promotion plan compiled_targets are missing; compiled wiki targets must come from the staging plan.",
            details={"staged_count": len(staged_paths), "compiled_target_count": 0},
        )

    unsafe_targets = [target for target in compiled_targets if not _compiled_target_is_safe(str(target))]
    issues = []
    if unsafe_targets:
        issues.append("compiled targets include unsafe paths")
    if len(staged_paths) != len(compiled_targets):
        issues.append("compiled target count does not match staged draft count")
    if issues:
        return _check_run(
            "compiled-targets",
            "failure",
            "; ".join(issues) + ".",
            details={
                "staged_count": len(staged_paths),
                "compiled_target_count": len(compiled_targets),
                "unsafe_targets": unsafe_targets,
            },
        )

    return _check_run(
        "compiled-targets",
        "success",
        "Compiled targets are bounded to wiki page roots and aligned with staged drafts.",
        details={"count": len(compiled_targets)},
    )


def _critic_quorum_check(paper_root: Path, critic_report: dict[str, Any]) -> dict[str, Any]:
    quorum_path = Path(critic_report.get("reviewer_quorum_path") or paper_root / "critic" / "critic-quorum.json")
    quorum = _read_json(quorum_path)
    if not quorum:
        return _check_run(
            "critic-quorum",
            "action_required",
            "Critic quorum is missing; run or repair critic before promotion.",
            details={"path": str(quorum_path)},
        )
    final_outcome = quorum.get("final_outcome")
    reviewers = quorum.get("reviewers") or []
    if final_outcome == "pass":
        return _check_run(
            "critic-quorum",
            "success",
            f"Critic quorum passed with {len(reviewers)} reviewer records.",
            details={"path": str(quorum_path), "reviewer_count": len(reviewers)},
        )
    return _check_run(
        "critic-quorum",
        "failure",
        f"Critic quorum outcome is {final_outcome or 'unknown'}.",
        details={"path": str(quorum_path), "reviewer_count": len(reviewers)},
    )


def _promotion_record_check(paper_root: Path) -> dict[str, Any] | None:
    record_path = paper_root / "promotion-record.json"
    record = _read_json(record_path)
    if not record:
        return None
    human_gate = record.get("human_gate_decision") if isinstance(record.get("human_gate_decision"), dict) else {}
    if record.get("status") == "promoted" and human_gate.get("status") == "approved":
        return _check_run(
            "human-approval",
            "success",
            "Human approval is recorded in the promotion record.",
            details={"path": str(record_path), "approved_by": human_gate.get("approved_by")},
        )
    return _check_run(
        "human-approval",
        "failure",
        "Promotion record exists but does not contain approved human gate metadata.",
        details={"path": str(record_path)},
    )


def build_paper_gate(vault_path: Path, slug: str) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    paper_root = vault_path / "_raw" / "papers" / slug
    staging_root = vault_path / "_staging" / "papers" / slug
    metadata = _read_json(paper_root / "metadata.json") or {}
    check_runs: list[dict[str, Any]] = []

    critic_path = paper_root / "critic" / "critic-report.json"
    critic_report = _read_json(critic_path)
    if not critic_report:
        check_runs.append(
            _check_run(
                "critic-report",
                "failure",
                "Missing critic report; no compiled wiki write is allowed.",
                details={"path": str(critic_path)},
            )
        )
        return _paper_gate_payload(
            slug=slug,
            title=metadata.get("title") or slug,
            status="blocked",
            next_action="run-critic",
            check_runs=check_runs,
            paper_root=paper_root,
            staging_root=staging_root,
        )

    check_runs.append(
        _check_run("critic-report", "success", "Critic report exists.", details={"path": str(critic_path)})
    )
    critic_outcome = critic_report.get("outcome")
    check_runs.append(
        _check_run(
            "critic-outcome",
            "success" if critic_outcome == "pass" else "failure",
            f"Critic outcome is {critic_outcome or 'unknown'}.",
        )
    )
    check_runs.append(
        _check_run(
            "hard-rule",
            "success" if critic_report.get("hard_rule") == HARD_RULE else "failure",
            "Hard rule is preserved." if critic_report.get("hard_rule") == HARD_RULE else "Hard rule metadata is missing or changed.",
        )
    )
    check_runs.append(_critic_quorum_check(paper_root, critic_report))

    plan_path = staging_root / "promotion-plan.json"
    plan = _read_json(plan_path)
    if plan:
        check_runs.append(
            _check_run("promotion-plan", "success", "Promotion plan exists.", details={"path": str(plan_path)})
        )
        staged_paths = _staged_paths_from_plan(plan)
        missing_staged = [str(path) for path in staged_paths if not path.exists()]
        check_runs.append(
            _check_run(
                "staged-drafts",
                "success" if not missing_staged else "failure",
                "All staged drafts exist." if not missing_staged else "Some staged drafts are missing.",
                details={"missing": missing_staged} if missing_staged else {"count": len(staged_paths)},
            )
        )
        if _is_agent_handoff_plan(plan):
            check_runs.append(_wiki_ingest_brief_check(plan))
            check_runs.append(_final_wiki_authority_check(plan))
        else:
            check_runs.append(_compiled_targets_check(plan, staged_paths))
    else:
        check_runs.append(
            _check_run(
                "promotion-plan",
                "action_required",
                "Promotion plan is missing; stage the paper after critic pass.",
                details={"path": str(plan_path)},
            )
        )

    promotion_check = _promotion_record_check(paper_root)
    if promotion_check is not None:
        check_runs.append(promotion_check)
    elif critic_outcome == "pass" and plan and _suite_conclusion(check_runs) == "success":
        check_runs.append(
            _check_run(
                "human-approval",
                "action_required",
                "Human approval is required before final wiki ingest or legacy compiled wiki write.",
            )
        )

    conclusion = _suite_conclusion(check_runs)
    next_action = _next_action(critic_report, plan, conclusion, promotion_check)
    status = _gate_status(conclusion, next_action, promotion_check)
    return _paper_gate_payload(
        slug=slug,
        title=metadata.get("title") or slug,
        status=status,
        next_action=next_action,
        check_runs=check_runs,
        paper_root=paper_root,
        staging_root=staging_root,
    )


def _next_action(
    critic_report: dict[str, Any],
    plan: dict[str, Any] | None,
    conclusion: str,
    promotion_check: dict[str, Any] | None,
) -> str:
    if promotion_check and promotion_check.get("conclusion") == "success":
        return "review-promoted-pages"
    if critic_report.get("outcome") != "pass":
        return str(critic_report.get("next_action") or "revise-reader")
    if not plan:
        return "stage-paper"
    if conclusion == "failure":
        return "repair-gate-failures"
    if _is_agent_handoff_plan(plan):
        return "run-wiki-ingest-agent"
    return "promote-to-wiki"


def _gate_status(conclusion: str, next_action: str, promotion_check: dict[str, Any] | None) -> str:
    if promotion_check and promotion_check.get("conclusion") == "success":
        return "promoted"
    if conclusion == "failure":
        return "blocked"
    if next_action in {"promote-to-wiki", "run-wiki-ingest-agent"}:
        return "waiting_for_human_gate"
    return "action_required"


def _paper_gate_payload(
    *,
    slug: str,
    title: str,
    status: str,
    next_action: str,
    check_runs: list[dict[str, Any]],
    paper_root: Path,
    staging_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "epi-paper-gate-v1",
        "paper_slug": slug,
        "title": title,
        "status": status,
        "next_action": next_action,
        "hard_rule": HARD_RULE,
        "paths": {
            "paper_root": str(paper_root),
            "staging_root": str(staging_root),
        },
        "check_suite": {
            "schema_version": "epi-paper-gate-check-suite-v1",
            "status": "completed",
            "conclusion": _suite_conclusion(check_runs),
            "check_runs": check_runs,
        },
    }


def render_paper_gate(gate: dict[str, Any]) -> str:
    lines = [
        f"# EPI Paper Gate - {gate.get('paper_slug', '-')}",
        "",
        "## Summary",
        "",
        f"- status: {gate.get('status', 'unknown')}",
        f"- conclusion: {gate.get('check_suite', {}).get('conclusion', 'unknown')}",
        f"- next: {gate.get('next_action', '-')}",
        "",
        "## Checks",
        "",
    ]
    for run in gate.get("check_suite", {}).get("check_runs", []):
        lines.append(f"- {run.get('name')}: {run.get('conclusion')}")
        summary = (run.get("output") or {}).get("summary")
        if summary:
            lines.append(f"  summary: {summary}")
    lines.append("")
    return "\n".join(lines)
