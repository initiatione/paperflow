from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from paper_source.artifacts import (
    LEGACY_EPI_ROOT_NAME,
    PAPER_SOURCE_ROOT_NAME,
    existing_raw_paper_root,
    existing_staging_paper_root,
    legacy_epi_root,
    paper_source_meta_root,
)
from paper_source.run_critic import HARD_RULE
from paper_source.source_bundle_audit import audit_source_bundle
from paper_source.source_artifacts import is_mineru_markdown_artifact
from paper_source.wiki_ingest_approval import (
    HUMAN_APPROVAL_SCOPE,
    human_approval_record_path,
    validate_human_approval_record,
)
from paper_source.wiki_contracts import (
    formal_page_family_names,
    required_wiki_skills,
    page_lifecycle_states,
    research_review_fields,
)


_ALLOWED_COMPILED_TARGET_ROOTS = set(formal_page_family_names())
_PAPER_WIKI_REVIEW_READY_STATUSES = {
    "paper-wiki-reviewed-ready-for-paper-source-record",
    "paper-wiki-reviewed-ready-for-record",
    "ready-for-paper-source-record",
    # Legacy pre-Stage-2 labels accepted for old correction artifacts.
    "prw-reviewed-ready-for-epi-record",
    "prw-reviewed-ready-for-record",
    "ready-for-epi-record",
}
PAPER_SOURCE_WRITE_SCOPE = "internal-underscore-artifacts-only"


def _paper_source_write_scope(payload: dict[str, Any]) -> Any:
    return payload.get("paper_source_write_scope", payload.get("epi_write_scope"))


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
    for key in ["staged_evidence", "staged_concepts", "staged_synthesis", "staged_reports"]:
        paths.extend(Path(path) for path in plan.get(key, []))
    return paths


def _is_agent_handoff_plan(plan: dict[str, Any]) -> bool:
    return (
        plan.get("handoff_type") == "agent-mediated-wiki-ingest"
        or plan.get("wiki_write_model") == "agent-mediated-vault-contract"
        or plan.get("wiki_write_model") == "wiki-skill-batch-distillation"
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
    governance_layers = (
        rule_source_model.get("governance_layers") if isinstance(rule_source_model, dict) else []
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
    governance_layer_text = "\n".join(str(item) for item in governance_layers or [])
    rule_source_policy_text = "\n".join(
        str(item)
        for item in [
            rule_source_model.get("principle") if isinstance(rule_source_model, dict) else "",
            ingest_policy.get("authority") if isinstance(ingest_policy, dict) else "",
        ]
    )
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
    final_source_review_contract = (
        brief.get("final_source_review_contract")
        if isinstance(brief.get("final_source_review_contract"), dict)
        else {}
    )
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
    if _paper_source_write_scope(ingest_policy) != PAPER_SOURCE_WRITE_SCOPE:
        issues.append("brief must restrict Paper Source writes to internal underscore artifacts")
    if ingest_policy.get("formal_routes_suggested") is not False or brief.get("formal_routes_suggested") is not False:
        issues.append("brief must not suggest formal wiki routes")
    if ingest_policy.get("wiki_batch_handoff_required") is not True:
        issues.append("brief must require wiki skill batch handoff")
    required_skill_values = ingest_policy.get("required_wiki_skills") or final_source_review_contract.get("required_wiki_skills") or []
    missing_required_skills = [skill for skill in required_wiki_skills() if skill not in required_skill_values]
    if missing_required_skills:
        issues.append("brief required_wiki_skills are incomplete: " + ", ".join(missing_required_skills))
    page_family_values = brief.get("formal_page_families") or final_source_review_contract.get("formal_page_families") or []
    missing_page_families = [family for family in formal_page_family_names() if family not in page_family_values]
    if missing_page_families:
        issues.append("formal page families are incomplete: " + ", ".join(missing_page_families))
    review_field_values = brief.get("research_review_fields") or final_source_review_contract.get("research_review_fields") or []
    missing_review_fields = [field for field in research_review_fields() if field not in review_field_values]
    if missing_review_fields:
        issues.append("research review fields are incomplete: " + ", ".join(missing_review_fields))
    lifecycle_values = brief.get("page_lifecycle_states") or final_source_review_contract.get("page_lifecycle_states") or []
    if [str(item) for item in lifecycle_values] != page_lifecycle_states():
        issues.append("page lifecycle states are incomplete")
    if brief.get("suggested_routes"):
        issues.append("suggested_routes must be empty for Paper Source internal handoff")
    handoff_artifacts = brief.get("handoff_artifacts")
    if not isinstance(handoff_artifacts, list) or not handoff_artifacts:
        issues.append("handoff_artifacts are missing")
    source_first_policy = str(ingest_policy.get("source_first_policy") or "")
    if "source paper" not in source_first_policy or "not substitutes" not in source_first_policy:
        issues.append("source-first ingest policy is missing")
    if "MinerU Markdown" not in source_first_policy or "Missing native TeX is normal" not in source_first_policy:
        issues.append("source-first formula fallback contract is incomplete")
    required_raw_artifacts = [
        "paper.pdf",
        "metadata.json",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]
    missing_raw_artifacts = [
        artifact for artifact in required_raw_artifacts if artifact not in raw_artifact_text
    ]
    if not any(is_mineru_markdown_artifact(artifact) for artifact in raw_artifacts):
        missing_raw_artifacts.append("mineru/<slug>.md")
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
        execution_agent_policy = (
            rule_source_model.get("execution_agent_policy")
            if isinstance(rule_source_model.get("execution_agent_policy"), dict)
            else {}
        )
        helper_boundary_text = "\n".join(
            str(item)
            for item in [
                resolution_source_text,
                write_requirement_text,
                rule_source_policy_text,
                execution_agent_policy.get("local_skills_role") if isinstance(execution_agent_policy, dict) else "",
            ]
        ).lower()
        allowed_executor_text = "\n".join(
            str(item) for item in execution_agent_policy.get("allowed_executors", [])
        )
        brand_neutrality_text = str(execution_agent_policy.get("brand_neutrality") or "")
        if not execution_agent_policy:
            issues.append("wiki execution agent policy is missing")
        elif "Claude" not in allowed_executor_text or "Codex" not in allowed_executor_text:
            issues.append("wiki execution agent policy must allow Claude and Codex")
        elif "target vault contract" not in brand_neutrality_text:
            issues.append("wiki execution agent policy must require the target vault contract")
        required_rule_sources = [
            "target vault AGENTS.md",
            "_meta/schema.md",
            "paper-research-wiki",
            "Ar9av/obsidian-wiki",
            "kepano/obsidian-skills",
            "initiatione/obsidian-wiki-dev",
        ]
        missing_rule_sources = [
            source for source in required_rule_sources if source not in resolution_source_text
        ]
        if missing_rule_sources:
            issues.append("wiki rule source model is incomplete")
        governance_layer_names = {
            str(item.get("layer"))
            for item in governance_layers
            if isinstance(item, dict)
        }
        required_governance_layers = {
            "obsidian_syntax",
            "paper_wiki_evidence",
            "local_vault_governance",
        }
        if not required_governance_layers.issubset(governance_layer_names):
            issues.append("wiki rule source governance_layers are incomplete")
        elif (
            "kepano/obsidian-skills" not in governance_layer_text
            or "paper-research-wiki" not in governance_layer_text
            or "target vault AGENTS.md and _meta/*" not in governance_layer_text
        ):
            issues.append("wiki rule source governance_layers are incomplete")
        if "helper" not in helper_boundary_text:
            issues.append("external wiki skills must be described as optional helpers or references")
        if "Markdown vault" not in write_requirement_text or "source of truth" not in write_requirement_text:
            issues.append("wiki rule source model must preserve Markdown vault as source of truth")
        if "MinerU Markdown" not in write_requirement_text or "missing native TeX is normal" not in write_requirement_text:
            issues.append("wiki rule source model must preserve MinerU Markdown-first formula fallback")
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
    if plan.get("final_page_authority") not in {
        "target-vault-contract-and-wiki-ingest-agent",
        "wiki-skill-batch-distillation",
    }:
        return _check_run(
            "final-wiki-authority",
            "failure",
            "Final wiki authority must be wiki-skill batch distillation under the target vault contract.",
        )
    if _paper_source_write_scope(plan) != PAPER_SOURCE_WRITE_SCOPE:
        return _check_run(
            "final-wiki-authority",
            "failure",
            "Paper Source staging plans must restrict writes to internal underscore artifacts.",
        )
    if plan.get("formal_routes_suggested") is not False or plan.get("suggested_route_targets"):
        return _check_run(
            "final-wiki-authority",
            "failure",
            "Paper Source staging plans must not suggest formal wiki page routes.",
        )
    if plan.get("wiki_batch_handoff_required") is not True:
        return _check_run(
            "final-wiki-authority",
            "failure",
            "Final wiki pages must be produced through wiki-skill batch deposition.",
        )
    return _check_run(
        "final-wiki-authority",
        "success",
        "Final page paths, schema, taxonomy, links, and staged writes are delegated to wiki-skill batch deposition.",
    )


def _compiled_targets_check(plan: dict[str, Any], staged_paths: list[Path]) -> dict[str, Any]:
    compiled_targets = plan.get("compiled_targets")
    if not isinstance(compiled_targets, list) or not compiled_targets:
        return _check_run(
            "compiled-targets",
            "failure",
            "Promotion plan is legacy compiled-draft shaped; repair staging to an agent-mediated wiki ingest handoff.",
            details={"staged_count": len(staged_paths), "compiled_target_count": 0},
        )

    unsafe_targets = [target for target in compiled_targets if not _compiled_target_is_safe(str(target))]
    issues = []
    if unsafe_targets:
        issues.append("compiled targets include unsafe paths")
    if len(staged_paths) != len(compiled_targets):
        issues.append("compiled target count does not match staged draft count")

    summary = (
        "legacy compiled_targets are deprecated: Paper Source may only write internal underscore artifacts; "
        "use wiki-ingest handoff and wiki-skill batch deposition."
    )
    if issues:
        summary += " " + "; ".join(issues) + "."
    return _check_run(
        "compiled-targets",
        "failure",
        summary,
        details={
            "staged_count": len(staged_paths),
            "compiled_target_count": len(compiled_targets),
            "unsafe_targets": unsafe_targets,
        },
    )


def _source_bundle_check(paper_root: Path) -> dict[str, Any]:
    audit = audit_source_bundle(paper_root)
    if audit["complete"]:
        return _check_run(
            "source-bundle",
            "success",
            "Source bundle is complete on disk for source-first wiki handoff.",
            details=audit,
        )
    return _check_run(
        "source-bundle",
        "failure",
        "source bundle is incomplete on disk; repair or rerun acquisition/MinerU before wiki ingest.",
        details=audit,
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


def _completion_record_check(paper_root: Path) -> dict[str, Any] | None:
    record_path = paper_root / "promotion-record.json"
    record = _read_json(record_path)
    if record:
        human_gate = record.get("human_gate_decision") if isinstance(record.get("human_gate_decision"), dict) else {}
        if record.get("status") == "promoted" and human_gate.get("status") == "approved":
            return _check_run(
                "human-approval",
                "success",
                "Human approval is recorded in the promotion record.",
                details={
                    "path": str(record_path),
                    "approved_by": human_gate.get("approved_by"),
                    "record_type": "promotion-record",
                },
            )
        return _check_run(
            "human-approval",
            "failure",
            "Promotion record exists but does not contain approved human gate metadata.",
            details={"path": str(record_path), "record_type": "promotion-record"},
        )

    wiki_record_path = paper_root / "wiki-ingest-record.json"
    wiki_record = _read_json(wiki_record_path)
    if not wiki_record:
        return None
    human_gate = (
        wiki_record.get("human_gate_decision")
        if isinstance(wiki_record.get("human_gate_decision"), dict)
        else {}
    )
    if wiki_record.get("status") == "recorded" and human_gate.get("status") == "approved":
        return _check_run(
            "human-approval",
            "success",
            "Human approval is recorded in the agent-mediated wiki ingest record.",
            details={
                "path": str(wiki_record_path),
                "approved_by": human_gate.get("approved_by"),
                "record_type": "wiki-ingest-record",
                "page_count": len(wiki_record.get("page_records") or []),
            },
        )
    return _check_run(
        "human-approval",
        "failure",
        "Wiki ingest record exists but does not contain approved human gate metadata.",
        details={"path": str(wiki_record_path), "record_type": "wiki-ingest-record"},
    )


def _normalized_record_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


def _parse_record_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _path_matches_any(path: str, candidates: list[Any]) -> bool:
    normalized = _normalized_record_path(path)
    if not normalized:
        return False
    for candidate in candidates:
        candidate_normalized = _normalized_record_path(candidate)
        if (
            candidate_normalized
            and (
                normalized == candidate_normalized
                or normalized.endswith(candidate_normalized)
                or candidate_normalized.endswith(normalized)
            )
        ):
            return True
    return False


def _correction_ready_for_record(correction: dict[str, Any]) -> bool:
    status_after = (
        correction.get("status_after_correction")
        if isinstance(correction.get("status_after_correction"), dict)
        else {}
    )
    paper_wiki_repair = _paper_wiki_repair_payload(correction)
    return (
        str(status_after.get("wiki_quality_status") or "").strip() in _PAPER_WIKI_REVIEW_READY_STATUSES
        and str(paper_wiki_repair.get("status") or "").strip() == "completed"
    )


def _paper_wiki_repair_payload(correction: dict[str, Any]) -> dict[str, Any]:
    paper_wiki_repair = correction.get("paper_wiki_repair")
    if isinstance(paper_wiki_repair, dict):
        return paper_wiki_repair
    legacy_prw_repair = correction.get("prw_repair")
    return legacy_prw_repair if isinstance(legacy_prw_repair, dict) else {}


def _record_supersedes_correction_repair(wiki_record: dict[str, Any], correction: dict[str, Any]) -> bool:
    paper_wiki_repair = _paper_wiki_repair_payload(correction)
    if not paper_wiki_repair or str(paper_wiki_repair.get("status") or "").strip() != "completed":
        return False
    record_time = _parse_record_time(wiki_record.get("recorded_at"))
    repair_time = _parse_record_time(paper_wiki_repair.get("completed_at"))
    if record_time is None or repair_time is None or record_time <= repair_time:
        return False
    final_source_review = (
        wiki_record.get("final_source_review")
        if isinstance(wiki_record.get("final_source_review"), dict)
        else {}
    )
    if final_source_review.get("status") != "verified":
        return False
    refreshed = paper_wiki_repair.get("final_source_reviews_refreshed")
    if isinstance(refreshed, list) and refreshed:
        return _path_matches_any(str(final_source_review.get("path") or ""), refreshed)
    return True


def _correction_affects_slug(correction: dict[str, Any], slug: str) -> tuple[bool, dict[str, Any]]:
    expected_record_suffixes = {
        f"{PAPER_SOURCE_ROOT_NAME}/raw/{slug}/wiki-ingest-record.json",
        f"{LEGACY_EPI_ROOT_NAME}/raw/{slug}/wiki-ingest-record.json",
    }
    if correction.get("paper_slug") == slug:
        return True, {}
    affected_papers = correction.get("affected_papers")
    if not isinstance(affected_papers, list):
        affected_papers = []
    for affected in affected_papers:
        if not isinstance(affected, dict):
            continue
        premature_record = _normalized_record_path(affected.get("premature_record"))
        if (
            affected.get("slug") == slug
            or affected.get("paper_slug") == slug
            or any(premature_record.endswith(suffix) for suffix in expected_record_suffixes)
        ):
            return True, affected
    return False, {}


def _record_correction_check(vault_path: Path, slug: str, paper_root: Path) -> dict[str, Any] | None:
    correction_roots = [
        paper_source_meta_root(vault_path) / "record-corrections",
        legacy_epi_root(vault_path) / "meta" / "record-corrections",
    ]
    matches: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    correction_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for corrections_root in correction_roots:
        try:
            paths = sorted(corrections_root.glob("*.json"))
        except OSError:
            paths = []
        for path in paths:
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            correction_paths.append(path)
    for path in correction_paths:
        correction = _read_json(path)
        if not correction:
            continue
        if correction.get("correction_type") != "premature-wiki-ingest-record":
            continue
        affects_slug, affected_paper = _correction_affects_slug(correction, slug)
        if affects_slug:
            matches.append((path, correction, affected_paper))
    if not matches:
        return None
    path, correction, affected_paper = matches[-1]
    wiki_record = _read_json(paper_root / "wiki-ingest-record.json") or {}
    if _record_supersedes_correction_repair(wiki_record, correction):
        return None
    status_after = (
        correction.get("status_after_correction")
        if isinstance(correction.get("status_after_correction"), dict)
        else {}
    )
    action_taken = correction.get("action_taken") if isinstance(correction.get("action_taken"), dict) else {}
    paper_wiki_repair = _paper_wiki_repair_payload(correction)
    details = {
        "path": str(path),
        "correction_type": correction.get("correction_type"),
        "wiki_quality_status": status_after.get("wiki_quality_status"),
        "record_status_interpretation": status_after.get("record_status_interpretation"),
    }
    if paper_wiki_repair:
        details["paper_wiki_repair_status"] = paper_wiki_repair.get("status")
        details["paper_wiki_repair_completed_at"] = paper_wiki_repair.get("completed_at")
    staging_location = (
        affected_paper.get("staging_location")
        or correction.get("staging_location")
        or action_taken.get("staging_location")
    )
    if staging_location:
        details["staging_location"] = staging_location
    if len(matches) > 1:
        details["matching_correction_count"] = len(matches)
    if _correction_ready_for_record(correction):
        return _check_run(
            "record-correction",
            "success",
            "Corrected wiki ingest record has completed Paper Wiki review; rerun Paper Source record-wiki-ingest to replace the premature record.",
            details=details,
        )
    return _check_run(
        "record-correction",
        "action_required",
        "Wiki ingest record was corrected as premature; run Paper Wiki review before treating final wiki pages as complete.",
        details=details,
    )


def _prewrite_human_approval_check(vault_path: Path, slug: str) -> dict[str, Any] | None:
    valid, record, issues = validate_human_approval_record(vault_path, slug)
    path = human_approval_record_path(vault_path, slug)
    if record is None:
        return None
    if not valid:
        return _check_run(
            "human-approval",
            "failure",
            "Pre-write human approval record is invalid: " + "; ".join(issues),
            details={"path": str(path), "record_type": "human-approval"},
        )
    return _check_run(
        "human-approval",
        "success",
        "Human approval is recorded before the wiki ingest agent runs.",
        details={
            "path": str(path),
            "approved_by": record.get("approved_by"),
            "record_type": "human-approval",
            "scope": record.get("scope") or HUMAN_APPROVAL_SCOPE,
        },
    )


def build_paper_gate(vault_path: Path, slug: str) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    paper_root = existing_raw_paper_root(vault_path, slug)
    staging_root = existing_staging_paper_root(vault_path, slug)
    metadata = _read_json(paper_root / "metadata.json") or {}
    check_runs: list[dict[str, Any]] = []

    plan_path = staging_root / "promotion-plan.json"
    plan = _read_json(plan_path)
    critic_required = bool(plan.get("critic_required")) if plan else True
    critic_path = paper_root / "critic" / "critic-report.json"
    critic_report = _read_json(critic_path)
    if not critic_report:
        check_runs.append(
            _check_run(
                "critic-report",
                "failure" if critic_required else "success",
                (
                    "Critic report is required but missing."
                    if critic_required
                    else "Critic report not required for this workflow mode."
                ),
                details={"path": str(critic_path), "required": critic_required},
            )
        )
    else:
        check_runs.append(
            _check_run("critic-report", "success", "Critic report exists.", details={"path": str(critic_path)})
        )
    critic_outcome = critic_report.get("outcome") if critic_report else "not-run"
    if critic_report or critic_required:
        check_runs.append(
            _check_run(
                "critic-outcome",
                "success" if critic_report and critic_outcome == "pass" else "failure",
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
            check_runs.append(_source_bundle_check(paper_root))
            check_runs.append(_wiki_ingest_brief_check(plan))
            check_runs.append(_final_wiki_authority_check(plan))
        else:
            check_runs.append(_compiled_targets_check(plan, staged_paths))
    else:
        check_runs.append(
            _check_run(
                "promotion-plan",
                "action_required",
                "Promotion plan is missing; stage the paper before wiki ingest.",
                details={"path": str(plan_path)},
            )
        )

    promotion_check = _completion_record_check(paper_root)
    if promotion_check is not None:
        check_runs.append(promotion_check)
        correction_check = _record_correction_check(vault_path, slug, paper_root)
        if correction_check is not None:
            check_runs.append(correction_check)
    elif (critic_outcome == "pass" or not critic_required) and plan and _suite_conclusion(check_runs) == "success":
        correction_check = None
        prewrite_approval_check = (
            _prewrite_human_approval_check(vault_path, slug)
            if _is_agent_handoff_plan(plan)
            else None
        )
        if prewrite_approval_check is not None:
            check_runs.append(prewrite_approval_check)
        else:
            check_runs.append(
                _check_run(
                    "human-approval",
                    "action_required",
                    "Human approval is required before final wiki ingest or legacy compiled wiki write.",
                )
            )
    else:
        correction_check = None

    conclusion = _suite_conclusion(check_runs)
    next_action = _next_action(critic_report, plan, conclusion, promotion_check, correction_check)
    status = _gate_status(conclusion, next_action, promotion_check, correction_check)
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
    correction_check: dict[str, Any] | None = None,
) -> str:
    if correction_check is not None:
        if correction_check.get("conclusion") == "success":
            if plan and _is_agent_handoff_plan(plan):
                return "run-wiki-ingest-agent"
            return "repair-staging-to-wiki-handoff"
        return "run-paper-wiki-review"
    if promotion_check and promotion_check.get("conclusion") == "success":
        details = promotion_check.get("details") if isinstance(promotion_check.get("details"), dict) else {}
        if details.get("record_type") == "wiki-ingest-record":
            return "review-recorded-wiki-pages"
        return "review-promoted-pages"
    if critic_report and critic_report.get("outcome") != "pass":
        return str(critic_report.get("next_action") or "revise-reader")
    if not plan:
        return "stage-paper"
    if conclusion == "failure":
        return "repair-gate-failures"
    if _is_agent_handoff_plan(plan):
        return "run-wiki-ingest-agent"
    return "repair-staging-to-wiki-handoff"


def _gate_status(
    conclusion: str,
    next_action: str,
    promotion_check: dict[str, Any] | None,
    correction_check: dict[str, Any] | None = None,
) -> str:
    if correction_check is not None:
        if correction_check.get("conclusion") == "success" and next_action == "run-wiki-ingest-agent":
            return "ready_for_wiki_ingest_agent"
        return "wiki_ingest_record_corrected"
    if promotion_check and promotion_check.get("conclusion") == "success":
        details = promotion_check.get("details") if isinstance(promotion_check.get("details"), dict) else {}
        if details.get("record_type") == "wiki-ingest-record":
            return "wiki_ingest_recorded"
        return "promoted"
    if conclusion == "failure":
        return "blocked"
    if next_action == "run-wiki-ingest-agent" and conclusion == "success":
        return "ready_for_wiki_ingest_agent"
    if next_action == "run-wiki-ingest-agent":
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
        "schema_version": "paper-source-paper-gate-v1",
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
            "schema_version": "paper-source-paper-gate-check-suite-v1",
            "status": "completed",
            "conclusion": _suite_conclusion(check_runs),
            "check_runs": check_runs,
        },
    }


def render_paper_gate(gate: dict[str, Any]) -> str:
    lines = [
        f"# Paper Source Paper Gate - {gate.get('paper_slug', '-')}",
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
