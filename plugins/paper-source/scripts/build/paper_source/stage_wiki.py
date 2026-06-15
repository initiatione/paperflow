from __future__ import annotations

import json
from pathlib import Path

from paper_source.artifacts import (
    read_json,
    staging_paper_root,
    utc_now,
    wiki_batch_pending_root,
    write_json_atomic,
    write_text_atomic,
)
from paper_source.source_artifacts import has_nonempty_mineru_tex
from paper_source.stage_wiki_brief import (
    AUDITED_INGEST_MODE,
    FAST_INGEST_MODE,
    INGEST_MODES,
    REVIEWED_INGEST_MODE,
    _build_wiki_ingest_brief,
    _decision_frontmatter_lines,
    _deposition_value,
    _method_idea,
    _promotion_review_lines,
    _reading_report_lines,
    _required_wiki_skill_loading_clause,
    _research_decision_lines,
    _source_first_artifacts,
    _source_markdown_artifact,
    critic_required_for_mode,
    normalize_ingest_mode,
    reader_required_for_mode,
)
from paper_source.wiki_contracts import (
    PAPER_WIKI_CANONICAL_SKILL,
    deposition_skill_compatibility_aliases,
    formal_frontmatter_schema,
    formal_page_family_names,
    formal_page_family_paths,
    formal_page_family_records,
    page_lifecycle_states,
    quality_enhancement_wiki_skills,
    qmd_collection_policy,
    required_wiki_skills,
    research_review_fields,
    optional_wiki_skills,
    wiki_deposition_quality_gates,
)
from paper_source.wiki_handoff_contracts import agent_context_policy

WIKI_BATCH_INGEST_BRIEF_SCHEMA_VERSION = "paper-source-wiki-batch-ingest-brief-v1"
ACCEPTED_WIKI_BATCH_INGEST_BRIEF_SCHEMA_VERSIONS = {
    WIKI_BATCH_INGEST_BRIEF_SCHEMA_VERSION,
}
# Contract anchor: Stage Wiki handoffs must load PAPER_WIKI_CANONICAL_SKILL
# "first as the canonical paper wiki layer"; the helper lives in stage_wiki_brief.

def _load_research_decision(paper_root: Path, critic_report: dict) -> tuple[dict, str | None]:
    decision = critic_report.get("research_decision") if isinstance(critic_report.get("research_decision"), dict) else {}
    decision_path_value = critic_report.get("research_decision_path")
    decision_path = Path(decision_path_value) if decision_path_value else paper_root / "critic" / "research-decision.json"
    if not decision and decision_path.exists():
        decision = read_json(decision_path)
    return decision, str(decision_path) if decision or decision_path.exists() else None


def _load_reproduction_plan(paper_root: Path, critic_report: dict) -> tuple[dict, str | None]:
    plan = critic_report.get("reproduction_plan") if isinstance(critic_report.get("reproduction_plan"), dict) else {}
    plan_path_value = critic_report.get("reproduction_plan_path")
    plan_path = Path(plan_path_value) if plan_path_value else paper_root / "critic" / "reproduction-plan.json"
    if not plan and plan_path.exists():
        plan = read_json(plan_path)
    return plan, str(plan_path) if plan or plan_path.exists() else None


def _load_evidence_map(paper_root: Path) -> dict:
    evidence_map_path = paper_root / "reader" / "evidence-map.json"
    if not evidence_map_path.exists():
        return {}
    return read_json(evidence_map_path)


def _load_full_text_evidence_index(paper_root: Path) -> dict:
    path = paper_root / "evidence-index.json"
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
    except (json.JSONDecodeError, OSError):
        return {"status": "unreadable", "path": "evidence-index.json"}
    return {
        "status": "available",
        "path": "evidence-index.json",
        "chunk_count": len(payload.get("chunks") or []),
        "input_hashes": payload.get("input_hashes") or {},
        "warnings": payload.get("warnings") or [],
    }


def _existing_artifacts(paper_root: Path, candidates: list[str]) -> list[str]:
    artifacts: list[str] = []
    for relative in candidates:
        path = paper_root / relative
        if path.exists():
            artifacts.append(relative)
    return artifacts


def _reader_artifacts(paper_root: Path) -> list[str]:
    return _existing_artifacts(
        paper_root,
        [
            "reader/reader.md",
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/figures.md",
            "reader/reproducibility.md",
            "reader/implementation-ideas.md",
            "reader/evidence-map.json",
            "reader/claim-support.json",
        ],
    )


def _critic_artifacts(paper_root: Path) -> list[str]:
    return _existing_artifacts(
        paper_root,
        [
            "critic/critic-report.json",
            "critic/critic-quorum.json",
            "critic/research-decision.json",
            "critic/reader-revision-plan.json",
            "critic/reproduction-plan.json",
        ],
    )


def _source_handoff_body(*, slug: str, title: str, workflow_mode: str, reader_text: str) -> str:
    if reader_text.strip():
        return reader_text
    source_lines = [
        "# Source-First Handoff",
        "",
        f"- Paper slug: {slug}",
        f"- Title: {title}",
        f"- Workflow mode: {workflow_mode}",
        "- Reader/Critic: not run in fast-ingest mode.",
        "- Required source artifacts for final wiki writing:",
        *[f"  - {artifact}" for artifact in _source_first_artifacts(slug)],
        "",
        "Final wiki pages must be written by wiki-ingest from the source paper and MinerU Markdown first; use images, manifest, figure/formula indexes, and PDF fallback only for visual evidence or Markdown gaps/conflicts. This file is an internal navigator, not a final wiki page.",
    ]
    return "\n".join(source_lines)


def _write_batch_handoff(
    *,
    vault_path: Path,
    slug: str,
    title: str,
    staging_root: Path,
    wiki_ingest_brief_path: Path,
    wiki_deposition_task_path: Path | None,
    reading_report_path: Path,
    source_reader_path: Path,
    wiki_ingest_brief: dict,
) -> Path:
    batch_root = wiki_batch_pending_root(vault_path)
    batch_path = batch_root / "wiki-batch-ingest-brief.json"
    try:
        existing = read_json(batch_path)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        existing = {}
    if (
        not isinstance(existing, dict)
        or existing.get("schema_version") not in ACCEPTED_WIKI_BATCH_INGEST_BRIEF_SCHEMA_VERSIONS
    ):
        existing = {
            "schema_version": WIKI_BATCH_INGEST_BRIEF_SCHEMA_VERSION,
            "batch_id": "pending",
            "created_at": utc_now(),
            "handoff_type": "wiki-skill-batch-distillation",
            "formal_routes_suggested": False,
            "required_wiki_skills": required_wiki_skills(),
            "quality_enhancement_wiki_skills": quality_enhancement_wiki_skills(),
            "optional_wiki_skills": optional_wiki_skills(),
            "formal_page_families": formal_page_family_names(),
            "formal_frontmatter_schema": formal_frontmatter_schema(),
            "quality_gates": wiki_deposition_quality_gates(),
            "research_review_fields": research_review_fields(),
            "page_lifecycle_states": page_lifecycle_states(),
            "paper_slugs": [],
            "papers": [],
        }
    existing["schema_version"] = WIKI_BATCH_INGEST_BRIEF_SCHEMA_VERSION
    existing.pop("epi_write_scope", None)
    existing["paper_source_write_scope"] = "internal-underscore-artifacts-only"
    existing["required_wiki_skills"] = required_wiki_skills()
    existing["quality_enhancement_wiki_skills"] = quality_enhancement_wiki_skills()
    existing["optional_wiki_skills"] = optional_wiki_skills()
    existing["formal_page_families"] = formal_page_family_names()
    existing["formal_frontmatter_schema"] = formal_frontmatter_schema()
    existing["quality_gates"] = wiki_deposition_quality_gates()
    existing["research_review_fields"] = research_review_fields()
    existing["page_lifecycle_states"] = page_lifecycle_states()
    papers = [
        item
        for item in existing.get("papers", [])
        if isinstance(item, dict) and item.get("paper_slug") != slug
    ]
    papers.append(
        {
            "paper_slug": slug,
            "title": title,
            "staging_root": str(staging_root),
            "wiki_ingest_brief": str(wiki_ingest_brief_path),
            "legacy_wiki_deposition_task": str(wiki_deposition_task_path) if wiki_deposition_task_path else None,
            "reading_report": str(reading_report_path),
            "source_reader": str(source_reader_path),
            "source_bundle": wiki_ingest_brief.get("source_bundle", {}),
            "candidate_topics": wiki_ingest_brief.get("candidate_topics", []),
            "candidate_clusters": wiki_ingest_brief.get("candidate_clusters", []),
        }
    )
    papers.sort(key=lambda item: str(item.get("paper_slug", "")))
    existing["updated_at"] = utc_now()
    existing["paper_slugs"] = [str(item["paper_slug"]) for item in papers]
    existing["papers"] = papers
    existing["wiki_skill_instruction"] = (
        _required_wiki_skill_loading_clause("Load")
        + ". Distill formal "
        "pages across references/, concepts/, derivations/, experiments/, synthesis/, reports/, and "
        "opportunities/ from the source papers, formulas, figures, images, and compact Paper Source evidence "
        "aids. Do not promote Paper Source staging reports or per-paper audit pages as formal wiki pages."
    )
    write_json_atomic(batch_path, existing)
    return batch_path


def _paper_deposition_paths(
    *,
    slug: str,
    paper_root: Path,
    staging_root: Path,
    wiki_ingest_brief_path: Path,
    reading_report_path: Path,
    source_reader_path: Path,
    reader_artifacts: list[str],
    critic_artifacts: list[str],
) -> dict[str, object]:
    source_markdown = _source_markdown_artifact(slug)
    return {
        "slug": slug,
        "metadata": str(paper_root / "metadata.json"),
        "paper_pdf": str(paper_root / "paper.pdf"),
        "paper_md": str(paper_root / source_markdown),
        "paper_tex": str(paper_root / "mineru" / "paper.tex") if has_nonempty_mineru_tex(paper_root) else None,
        "images": str(paper_root / "mineru" / "images"),
        "mineru_manifest": str(paper_root / "mineru" / "mineru-manifest.json"),
        "formula_index": str(paper_root / "formula-index.json"),
        "figure_index": str(paper_root / "figure-index.json"),
        "table_index": str(paper_root / "table-index.json"),
        "brief": str(wiki_ingest_brief_path),
        "reading_report": str(reading_report_path),
        "source_reader": str(source_reader_path),
        "staging_root": str(staging_root),
        "reader_artifacts": [str(paper_root / artifact) for artifact in reader_artifacts],
        "critic_artifacts": [str(paper_root / artifact) for artifact in critic_artifacts],
    }


def _build_wiki_deposition_task(
    *,
    vault_path: Path,
    slug: str,
    title: str,
    workflow_mode: str,
    paper_root: Path,
    staging_root: Path,
    wiki_ingest_brief_path: Path,
    reading_report_path: Path,
    source_reader_path: Path,
    reader_artifacts: list[str],
    critic_artifacts: list[str],
    wiki_ingest_brief: dict,
) -> dict:
    return {
        "schema_version": "paper-source-wiki-deposition-task-v1",
        "task_type": "wiki_deposition",
        "vault_schema": "paper-source-paper-research",
        "created_at": utc_now(),
        "vault_path": str(vault_path),
        "workflow_mode": workflow_mode,
        "handoff_boundary": {
            "paper_source_core_role": "source-bundle-and-audit-only",
            "formal_writer_role": "obsidian-wiki-skill-layer",
            "paper_source_must_not_write_formal_pages": True,
            "canonical_internal_roots": ["_paper_source/"],
            "legacy_internal_roots": ["_epi/"],
        },
        "page_families": formal_page_family_names(),
        "page_family_records": formal_page_family_records(),
        "required_skills": required_wiki_skills(),
        "compatibility_aliases": deposition_skill_compatibility_aliases(),
        "quality_enhancement_skills": quality_enhancement_wiki_skills(),
        "optional_skills": optional_wiki_skills(),
        "formal_frontmatter_schema": formal_frontmatter_schema(),
        "quality_gates": wiki_deposition_quality_gates(),
        "qmd_collection_policy": qmd_collection_policy(),
        "wiki_rule_source_model": wiki_ingest_brief.get("wiki_rule_source_model", {}),
        "final_source_review_contract": wiki_ingest_brief.get("final_source_review_contract", {}),
        "agent_context_policy": agent_context_policy(),
        "papers": [
            {
                "title": title,
                **_paper_deposition_paths(
                    slug=slug,
                    paper_root=paper_root,
                    staging_root=staging_root,
                    wiki_ingest_brief_path=wiki_ingest_brief_path,
                    reading_report_path=reading_report_path,
                    source_reader_path=source_reader_path,
                    reader_artifacts=reader_artifacts,
                    critic_artifacts=critic_artifacts,
                ),
            }
        ],
    }


def stage_paper(
    vault_path: Path,
    slug: str,
    paper_root: Path,
    workflow_mode: str = FAST_INGEST_MODE,
    *,
    emit_legacy_deposition_task: bool = False,
) -> Path:
    workflow_mode = normalize_ingest_mode(workflow_mode)
    reader_required = reader_required_for_mode(workflow_mode)
    critic_required = critic_required_for_mode(workflow_mode)
    critic_report_path = paper_root / "critic" / "critic-report.json"
    critic_report = read_json(critic_report_path) if critic_report_path.exists() else {}
    outcome = critic_report.get("outcome") if critic_report else "not-run"
    if critic_required and not critic_report:
        raise ValueError("critic report is required before audited-ingest staging")
    if critic_report and outcome != "pass":
        raise ValueError(f"critic outcome must be pass before staging, got {outcome}")

    staging_root = staging_paper_root(vault_path, slug)
    evidence_dir = staging_root / "evidence"
    briefs_dir = staging_root / "briefs"
    reader_path = paper_root / "reader" / "reader.md"
    if reader_required and not reader_path.exists():
        raise ValueError(f"reader output is required before {workflow_mode} staging")
    reader_text = reader_path.read_text(encoding="utf-8") if reader_path.exists() else ""
    editorial_summary_path = paper_root / "reader" / "editorial-summary.md"
    technical_reading_path = paper_root / "reader" / "technical-reading.md"
    research_notes_path = paper_root / "reader" / "research-notes.md"
    figures_path = paper_root / "reader" / "figures.md"
    reproducibility_path = paper_root / "reader" / "reproducibility.md"
    editorial_summary_text = editorial_summary_path.read_text(encoding="utf-8") if editorial_summary_path.exists() else ""
    technical_reading_text = technical_reading_path.read_text(encoding="utf-8") if technical_reading_path.exists() else ""
    research_notes_text = research_notes_path.read_text(encoding="utf-8") if research_notes_path.exists() else ""
    figures_text = figures_path.read_text(encoding="utf-8") if figures_path.exists() else ""
    reproducibility_text = reproducibility_path.read_text(encoding="utf-8") if reproducibility_path.exists() else ""
    metadata = read_json(paper_root / "metadata.json")
    title = metadata.get("title", "")
    reader_artifacts = _reader_artifacts(paper_root)
    critic_artifacts = _critic_artifacts(paper_root)
    source_reader_target = "evidence/source-reader.md"
    reading_report_target = "briefs/reading-report.md"
    source_reader_path = evidence_dir / "source-reader.md"
    reading_report_path = briefs_dir / "reading-report.md"
    wiki_ingest_brief_path = staging_root / "wiki-ingest-brief.json"
    wiki_deposition_task_path = staging_root / "wiki_deposition_task.json"
    research_decision, research_decision_path = _load_research_decision(paper_root, critic_report)
    reproduction_plan, reproduction_plan_path = _load_reproduction_plan(paper_root, critic_report)
    evidence_map = _load_evidence_map(paper_root)
    full_text_evidence_index = _load_full_text_evidence_index(paper_root)
    decision_frontmatter_lines = _decision_frontmatter_lines(research_decision)
    research_decision_lines = _research_decision_lines(research_decision)
    promotion_review_lines = _promotion_review_lines(research_decision)
    wiki_ingest_brief = _build_wiki_ingest_brief(
        slug=slug,
        title=title,
        workflow_mode=workflow_mode,
        source_reader_target=source_reader_target,
        reading_report_target=reading_report_target,
        wiki_deposition_task_path=str(wiki_deposition_task_path) if emit_legacy_deposition_task else None,
        editorial_summary_text=editorial_summary_text,
        technical_reading_text=technical_reading_text,
        research_notes_text=research_notes_text,
        evidence_map=evidence_map,
        research_decision=research_decision,
        reproduction_plan=reproduction_plan,
        reader_artifacts=reader_artifacts,
        critic_artifacts=critic_artifacts,
        full_text_evidence_index=full_text_evidence_index,
        paper_root=paper_root,
    )
    wiki_deposition_task = None
    if emit_legacy_deposition_task:
        wiki_deposition_task = _build_wiki_deposition_task(
            vault_path=vault_path,
            slug=slug,
            title=title,
            workflow_mode=workflow_mode,
            paper_root=paper_root,
            staging_root=staging_root,
            wiki_ingest_brief_path=wiki_ingest_brief_path,
            reading_report_path=reading_report_path,
            source_reader_path=source_reader_path,
            reader_artifacts=reader_artifacts,
            critic_artifacts=critic_artifacts,
            wiki_ingest_brief=wiki_ingest_brief,
        )
    source_handoff_text = _source_handoff_body(
        slug=slug,
        title=title,
        workflow_mode=workflow_mode,
        reader_text=reader_text,
    )
    source_reader = [
        "---",
        f"paper_slug: {slug}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"workflow_mode: {workflow_mode}",
        "stage: staging",
        "formal_page: false",
        "artifact_type: source_reader",
        *decision_frontmatter_lines,
        "---",
        "",
        source_handoff_text,
    ]
    if research_decision_lines:
        source_reader.extend(["", *research_decision_lines, ""])
    if promotion_review_lines:
        source_reader.extend(["", *promotion_review_lines, ""])
    write_text_atomic(source_reader_path, "\n".join(source_reader))
    if wiki_deposition_task is not None:
        write_json_atomic(wiki_deposition_task_path, wiki_deposition_task)
    elif wiki_deposition_task_path.exists():
        wiki_deposition_task_path.unlink()
    write_json_atomic(wiki_ingest_brief_path, wiki_ingest_brief)
    write_text_atomic(
        reading_report_path,
        "\n".join(
            _reading_report_lines(
                slug=slug,
                title=title,
                workflow_mode=workflow_mode,
                source_reader_target=source_reader_target,
                reader_text=reader_text,
                editorial_summary_text=editorial_summary_text,
                technical_reading_text=technical_reading_text,
                research_notes_text=research_notes_text,
                figures_text=figures_text,
                reproducibility_text=reproducibility_text,
                evidence_map=evidence_map,
                research_decision=research_decision,
                reproduction_plan=reproduction_plan,
                wiki_ingest_brief=wiki_ingest_brief,
                metadata=metadata,
                decision_frontmatter_lines=decision_frontmatter_lines,
            )
        ),
    )
    batch_handoff_path = _write_batch_handoff(
        vault_path=vault_path,
        slug=slug,
        title=title,
        staging_root=staging_root,
        wiki_ingest_brief_path=wiki_ingest_brief_path,
        wiki_deposition_task_path=wiki_deposition_task_path if emit_legacy_deposition_task else None,
        reading_report_path=reading_report_path,
        source_reader_path=source_reader_path,
        wiki_ingest_brief=wiki_ingest_brief,
    )
    agent_handoff_paths = [
        str(wiki_ingest_brief_path),
        str(batch_handoff_path),
        str(reading_report_path),
        str(source_reader_path),
    ]
    if emit_legacy_deposition_task:
        agent_handoff_paths.insert(1, str(wiki_deposition_task_path))
    plan = {
        "paper_slug": slug,
        "created_at": utc_now(),
        "workflow_mode": workflow_mode,
        "reader_required": reader_required,
        "critic_required": critic_required,
        "reader_critic_policy": wiki_ingest_brief["ingest_policy"]["reader_critic_policy"],
        "critic_outcome": outcome,
        "handoff_type": "agent-mediated-wiki-ingest",
        "wiki_write_model": "wiki-skill-batch-distillation",
        "final_page_authority": "wiki-skill-batch-distillation",
        "paper_source_write_scope": "internal-underscore-artifacts-only",
        "formal_routes_suggested": False,
        "wiki_batch_handoff_required": True,
        "required_wiki_skills": required_wiki_skills(),
        "formal_page_families": formal_page_family_names(),
        "research_review_fields": research_review_fields(),
        "page_lifecycle_states": page_lifecycle_states(),
        "staged_evidence": [str(source_reader_path)],
        "staged_reports": [str(reading_report_path)],
        "wiki_ingest_brief_path": str(wiki_ingest_brief_path),
        "wiki_batch_ingest_brief_path": str(batch_handoff_path),
        "final_source_review_contract": wiki_ingest_brief["final_source_review_contract"],
        "formal_frontmatter_schema": formal_frontmatter_schema(),
        "wiki_deposition_quality_gates": wiki_deposition_quality_gates(),
        "suggested_final_source_review_path": str(staging_root / "final-source-review.json"),
        "agent_handoff_paths": agent_handoff_paths,
        "suggested_route_targets": [],
        "candidate_topics": wiki_ingest_brief["candidate_topics"],
        "candidate_clusters": wiki_ingest_brief["candidate_clusters"],
    }
    if reproduction_plan:
        plan["reproduction_plan_path"] = reproduction_plan_path
    if emit_legacy_deposition_task:
        plan["legacy_wiki_deposition_task_path"] = str(wiki_deposition_task_path)
    if research_decision:
        plan["research_decision_path"] = research_decision_path
        plan["recommendation"] = research_decision.get("recommendation")
        plan["next_action"] = research_decision.get("next_action")
        plan["panel_summary"] = research_decision.get("panel_summary", {})
        plan["role_verdicts"] = research_decision.get("role_verdicts", {})
        plan["role_assessments"] = research_decision.get("role_assessments", [])
    write_json_atomic(staging_root / "promotion-plan.json", plan)
    return staging_root
