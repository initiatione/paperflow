from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import file_sha256, utc_now, write_json_atomic, write_text_atomic
from epi.critic_contracts import critic_protocol
from epi.paper_quality import review_paper_quality
from epi.reader_evidence import validate_claim_support_map, validate_evidence_map, validate_reader_evidence
from epi.reader_revision_plan import write_reader_revision_plan
from epi.reproduction_plan import write_reproduction_plan
from epi.research_decision import write_research_decision
from epi.role_critics import role_check_key, role_reviewer_paths, review_role_artifacts


HARD_RULE = "No critic pass, no compiled wiki write."
TOOL_VERSIONS = {
    "critic_pipeline": "epi-local-static-v1",
}


def _reviewer_record(
    name: str,
    scope: str,
    passed: bool,
    evidence: list[str],
    warnings: list[str] | None = None,
    review_protocol: dict | None = None,
) -> dict:
    record = {
        "name": name,
        "mode": "local",
        "scope": scope,
        "verdict": "pass" if passed else "fail",
        "evidence": evidence,
        "warnings": warnings or [],
    }
    if review_protocol:
        record["review_protocol"] = review_protocol
    return record


def _artifact_hashes(artifacts: dict[str, Path]) -> dict[str, str]:
    return {
        name: file_sha256(path)
        for name, path in artifacts.items()
        if path.exists()
    }


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _image_count(images_dir: Path) -> int:
    if not images_dir.exists():
        return 0
    return sum(1 for path in images_dir.rglob("*") if path.is_file())


def _review_parse_materialization(paper_root: Path) -> dict:
    mineru_dir = paper_root / "mineru"
    markdown_path = mineru_dir / "paper.md"
    tex_path = mineru_dir / "paper.tex"
    manifest_path = mineru_dir / "mineru-manifest.json"
    images_dir = mineru_dir / "images"
    parse_record_path = paper_root / "parse-record.json"
    parse_record = _load_json(parse_record_path)
    strict_success = parse_record.get("status") == "success"
    parse_record_present = bool(parse_record)

    failures: list[str] = []
    evidence: list[str] = []
    warnings: list[str] = []

    if markdown_path.exists() and markdown_path.stat().st_size > 0:
        evidence.append("mineru/paper.md exists and is non-empty")
    else:
        failures.append("mineru_paper_markdown_exists: mineru/paper.md missing or empty")

    if parse_record_present:
        status = parse_record.get("status", "unknown")
        evidence.append(f"parse-record.json status={status}")
        if status != "success":
            failures.append(f"parse_record_success: parse-record.json status={status}")

    if tex_path.exists() and tex_path.stat().st_size > 0:
        evidence.append("mineru/paper.tex exists and is non-empty for formula/notation review")
    elif strict_success:
        failures.append("mineru_paper_tex_ready: successful parse lacks non-empty mineru/paper.tex")
    elif parse_record_present:
        warnings.append("mineru_paper_tex_missing: formula/notation review may require PDF fallback")

    if manifest_path.exists() and manifest_path.stat().st_size > 0:
        evidence.append("mineru/mineru-manifest.json exists for parse provenance")
    elif strict_success:
        failures.append("mineru_manifest_ready: successful parse lacks mineru/mineru-manifest.json")
    elif parse_record_present:
        warnings.append("mineru_manifest_missing: parse provenance is incomplete")

    images = _image_count(images_dir)
    evidence.append(f"mineru/images file_count={images}")
    if not images_dir.exists():
        if parse_record_present:
            warnings.append("mineru_images_missing: image review must use paper.pdf fallback if figures/tables are expected")
    elif images == 0:
        if parse_record_present:
            warnings.append("mineru_images_empty: confirm the source paper has no extractable figures/tables/images")

    return {
        "passed": not failures,
        "evidence": failures or evidence,
        "warnings": warnings,
        "checks": {
            "mineru_paper_markdown_exists": markdown_path.exists() and markdown_path.stat().st_size > 0,
            "parse_record_success": not parse_record or parse_record.get("status") == "success",
            "mineru_paper_tex_ready": tex_path.exists() and tex_path.stat().st_size > 0,
            "mineru_manifest_ready": manifest_path.exists() and manifest_path.stat().st_size > 0,
            "mineru_image_file_count": images,
        },
    }


def _write_reviewer_markdown(path: Path, reviewer: dict) -> None:
    lines = [
        f"# {reviewer['name']}",
        "",
        f"Outcome: {reviewer['verdict']}",
        "",
        "## Scope",
        reviewer["scope"],
        "",
        "## Evidence",
    ]
    lines.extend(f"- {item}" for item in reviewer["evidence"])
    if reviewer["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in reviewer["warnings"])
    if reviewer.get("review_protocol"):
        lines.extend(["", "## Review Protocol"])
        protocol = reviewer["review_protocol"]
        lines.append(f"- Lens: {protocol['lens']}")
        lines.append(f"- Consumes: {protocol['consumes']}")
        if protocol.get("required_sections"):
            lines.append(f"- Required sections: {', '.join(protocol['required_sections'])}")
        if protocol.get("hard_fail_checks"):
            lines.append(f"- Hard fail checks: {', '.join(protocol['hard_fail_checks'])}")
        if protocol.get("warning_checks"):
            lines.append(f"- Warning checks: {', '.join(protocol['warning_checks'])}")
        if protocol.get("decision_boundary"):
            lines.append(f"- Decision boundary: {protocol['decision_boundary']}")
    lines.extend(["", f"Hard rule: {HARD_RULE}", ""])
    write_text_atomic(path, "\n".join(lines))


def run_critics(paper_root: Path) -> dict:
    started_at = utc_now()
    critic_dir = paper_root / "critic"
    critic_dir.mkdir(parents=True, exist_ok=True)
    reader_path = paper_root / "reader" / "reader.md"
    editorial_summary_path = paper_root / "reader" / "editorial-summary.md"
    technical_reading_path = paper_root / "reader" / "technical-reading.md"
    research_notes_path = paper_root / "reader" / "research-notes.md"
    figures_path = paper_root / "reader" / "figures.md"
    reproducibility_path = paper_root / "reader" / "reproducibility.md"
    implementation_ideas_path = paper_root / "reader" / "implementation-ideas.md"
    evidence_map_path = paper_root / "reader" / "evidence-map.json"
    claim_support_path = paper_root / "reader" / "claim-support.json"
    metadata_path = paper_root / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        metadata = {}
    reader_text = reader_path.read_text(encoding="utf-8") if reader_path.exists() else ""
    editorial_summary_text = (
        editorial_summary_path.read_text(encoding="utf-8") if editorial_summary_path.exists() else ""
    )
    technical_reading_text = technical_reading_path.read_text(encoding="utf-8") if technical_reading_path.exists() else ""
    research_notes_text = research_notes_path.read_text(encoding="utf-8") if research_notes_path.exists() else ""
    figures_text = figures_path.read_text(encoding="utf-8") if figures_path.exists() else ""
    reproducibility_text = reproducibility_path.read_text(encoding="utf-8") if reproducibility_path.exists() else ""
    implementation_ideas_text = (
        implementation_ideas_path.read_text(encoding="utf-8") if implementation_ideas_path.exists() else ""
    )
    paper_quality_review = review_paper_quality(
        paper_root,
        reader_text=reader_text,
        additional_reader_texts=[
            editorial_summary_text,
            technical_reading_text,
            research_notes_text,
            implementation_ideas_text,
        ],
        figures_text=figures_text,
        reproducibility_text=reproducibility_text,
    )
    parse_quality_review = _review_parse_materialization(paper_root)
    reader_quality = False
    if reader_path.exists():
        text_reader_quality, text_reader_evidence = validate_reader_evidence(
            paper_root,
            {
                "reader/reader.md": reader_text,
                "reader/editorial-summary.md": editorial_summary_text,
                "reader/technical-reading.md": technical_reading_text,
                "reader/research-notes.md": research_notes_text,
                "reader/figures.md": figures_text,
                "reader/reproducibility.md": reproducibility_text,
                "reader/implementation-ideas.md": implementation_ideas_text,
            },
        )
        map_reader_quality, map_reader_evidence = validate_evidence_map(paper_root)
        claim_support_quality, claim_support_evidence = validate_claim_support_map(paper_root)
        reader_quality = text_reader_quality and map_reader_quality and claim_support_quality
        reader_evidence = text_reader_evidence + map_reader_evidence + claim_support_evidence
    else:
        reader_evidence = ["reader/reader.md missing"]
    role_reviewers = review_role_artifacts(paper_root)
    role_checks = {role_check_key(reviewer["name"]): reviewer["verdict"] == "pass" for reviewer in role_reviewers}
    checks = {
        "paper_quality": paper_quality_review["passed"],
        "parse_quality": parse_quality_review["passed"],
        "reader_quality": reader_quality,
        **role_checks,
    }
    outcome = "pass" if all(checks.values()) else "revise-reader"
    reviewers = [
        _reviewer_record(
            "paper-quality-critic",
            "academic paper reliability: identity, supported claims, benchmark context, scope, reproducibility, and parse limitations",
            checks["paper_quality"],
            paper_quality_review["evidence"],
            paper_quality_review["warnings"],
            critic_protocol("paper-quality-critic"),
        ),
        _reviewer_record(
            "parse-quality-critic",
            "MinerU parse materialization and source-first companion artifacts",
            checks["parse_quality"],
            parse_quality_review["evidence"],
            parse_quality_review["warnings"],
            review_protocol=critic_protocol("parse-quality-critic"),
        ),
        _reviewer_record(
            "reader-quality-critic",
            "reader output source grounding",
            checks["reader_quality"],
            reader_evidence,
            review_protocol=critic_protocol("reader-quality-critic"),
        ),
        *role_reviewers,
    ]
    disagreement = len({reviewer["verdict"] for reviewer in reviewers}) > 1
    exit_status = 0 if outcome == "pass" else 1
    reviewer_paths = {
        "paper-quality-critic.md": critic_dir / "paper-quality-critic.md",
        "parse-quality-critic.md": critic_dir / "parse-quality-critic.md",
        "reader-quality-critic.md": critic_dir / "reader-quality-critic.md",
        **role_reviewer_paths(critic_dir),
        "research-decision.json": critic_dir / "research-decision.json",
        "research-decision.md": critic_dir / "research-decision.md",
        "reader-revision-plan.json": critic_dir / "reader-revision-plan.json",
        "reader-revision-plan.md": critic_dir / "reader-revision-plan.md",
        "reproduction-plan.json": critic_dir / "reproduction-plan.json",
        "reproduction-plan.md": critic_dir / "reproduction-plan.md",
    }
    research_decision = write_research_decision(critic_dir, outcome, reviewers, hard_rule=HARD_RULE)
    reader_revision_plan = write_reader_revision_plan(critic_dir, outcome, reviewers, hard_rule=HARD_RULE)
    reproduction_plan = write_reproduction_plan(
        critic_dir,
        outcome,
        reviewers,
        metadata=metadata,
        hard_rule=HARD_RULE,
    )
    quorum = {
        "stage": "critic-quorum",
        "critic_at": utc_now(),
        "mode": "local",
        "tool_versions": TOOL_VERSIONS,
        "reviewers": reviewers,
        "reviewer_count": len(reviewers),
        "disagreement": disagreement,
        "final_outcome": outcome,
        "hard_rule": HARD_RULE,
        "paper_quality_checks": paper_quality_review["checks"],
        "parse_quality_checks": parse_quality_review["checks"],
        "research_decision_path": str(critic_dir / "research-decision.json"),
        "research_decision": research_decision,
        "reader_revision_plan_path": str(critic_dir / "reader-revision-plan.json"),
        "reader_revision_plan": reader_revision_plan,
        "reproduction_plan_path": str(critic_dir / "reproduction-plan.json"),
        "reproduction_plan": reproduction_plan,
    }
    quorum_path = critic_dir / "critic-quorum.json"
    reviewer_markdown_paths = {
        key: path
        for key, path in reviewer_paths.items()
        if key.endswith("-critic.md")
    }
    for filename, reviewer in zip(reviewer_markdown_paths, reviewers):
        _write_reviewer_markdown(critic_dir / filename, reviewer)
    input_hashes = _artifact_hashes(
        {
            "paper.pdf": paper_root / "paper.pdf",
            "metadata.json": paper_root / "metadata.json",
            "mineru/paper.md": paper_root / "mineru" / "paper.md",
            "mineru/paper.tex": paper_root / "mineru" / "paper.tex",
            "mineru/mineru-manifest.json": paper_root / "mineru" / "mineru-manifest.json",
            "parse-record.json": paper_root / "parse-record.json",
            "reader/reader.md": reader_path,
            "reader/editorial-summary.md": editorial_summary_path,
            "reader/technical-reading.md": technical_reading_path,
            "reader/research-notes.md": research_notes_path,
            "reader/figures.md": figures_path,
            "reader/reproducibility.md": reproducibility_path,
            "reader/implementation-ideas.md": implementation_ideas_path,
            "reader/evidence-map.json": evidence_map_path,
            "reader/claim-support.json": claim_support_path,
        }
    )
    finished_at = utc_now()
    quorum["started_at"] = started_at
    quorum["finished_at"] = finished_at
    quorum["exit_status"] = exit_status
    quorum["input_artifact_hashes"] = input_hashes
    quorum["output_artifact_hashes"] = _artifact_hashes(reviewer_paths)
    write_json_atomic(quorum_path, quorum)
    report = {
        "stage": "critic",
        "critic_at": finished_at,
        "outcome": outcome,
        "checks": checks,
        "paper_quality_checks": paper_quality_review["checks"],
        "parse_quality_checks": parse_quality_review["checks"],
        "hard_rule": HARD_RULE,
        "tool_versions": TOOL_VERSIONS,
        "reviewer_quorum_path": str(quorum_path),
        "reviewer_count": len(reviewers),
        "disagreement": disagreement,
        "next_action": "stage" if outcome == "pass" else "revise-reader",
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_status": exit_status,
        "input_artifact_hashes": input_hashes,
        "output_artifact_hashes": {
            **_artifact_hashes(reviewer_paths),
            "critic-quorum.json": file_sha256(quorum_path),
        },
        "research_decision_path": str(critic_dir / "research-decision.json"),
        "research_decision": research_decision,
        "reader_revision_plan_path": str(critic_dir / "reader-revision-plan.json"),
        "reader_revision_plan": reader_revision_plan,
        "reproduction_plan_path": str(critic_dir / "reproduction-plan.json"),
        "reproduction_plan": reproduction_plan,
    }
    write_json_atomic(critic_dir / "critic-report.json", report)
    return report
