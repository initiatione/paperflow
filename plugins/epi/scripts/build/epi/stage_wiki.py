from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import staging_paper_root, utc_now, write_json_atomic, write_text_atomic


def _frontmatter_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _role_verdict_key(lens: str) -> str:
    return "epi_" + lens.replace("-", "_") + "_verdict"


def _decision_frontmatter_lines(decision: dict) -> list[str]:
    if not decision:
        return []
    panel = decision.get("panel_summary") or {}
    role_verdicts = decision.get("role_verdicts") or {}
    lines = [
        f"epi_recommendation: {_frontmatter_value(decision.get('recommendation', ''))}",
        f"epi_next_action: {_frontmatter_value(decision.get('next_action', ''))}",
        f"epi_panel_consensus: {_frontmatter_value(panel.get('consensus', ''))}",
        f"epi_blocking_lenses: {_frontmatter_value(panel.get('blocking_lenses') or [])}",
        f"epi_warning_reviewers: {_frontmatter_value(panel.get('warning_reviewers') or [])}",
    ]
    for lens, verdict in role_verdicts.items():
        lines.append(f"{_role_verdict_key(str(lens))}: {_frontmatter_value(verdict)}")
    return lines


def _draft_lines(
    *,
    slug: str,
    title: str,
    page_type: str,
    suggested_route_target: str,
    reference_target: str,
    promotion_review_lines: list[str] | None = None,
    decision_frontmatter_lines: list[str] | None = None,
) -> list[str]:
    heading_suffix = "Concept Draft" if page_type == "concept" else "Synthesis Draft"
    lines = [
        "---",
        f"paper_slug: {slug}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "stage: staging",
        f"page_type: {page_type}",
        f"suggested_route_target: {suggested_route_target}",
        f"reference_page: {reference_target}",
        *(decision_frontmatter_lines or []),
        "---",
        "",
        f"# {title} {heading_suffix}",
        "",
        f"Source reference: [{slug}]({reference_target})",
        "",
        f"Minimal {page_type} draft staged for promotion review.",
    ]
    if promotion_review_lines:
        lines.extend(["", *promotion_review_lines])
    return lines


def _load_research_decision(paper_root: Path, critic_report: dict) -> tuple[dict, str | None]:
    decision = critic_report.get("research_decision") if isinstance(critic_report.get("research_decision"), dict) else {}
    decision_path_value = critic_report.get("research_decision_path")
    decision_path = Path(decision_path_value) if decision_path_value else paper_root / "critic" / "research-decision.json"
    if not decision and decision_path.exists():
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
    return decision, str(decision_path) if decision or decision_path.exists() else None


def _load_reproduction_plan(paper_root: Path, critic_report: dict) -> tuple[dict, str | None]:
    plan = critic_report.get("reproduction_plan") if isinstance(critic_report.get("reproduction_plan"), dict) else {}
    plan_path_value = critic_report.get("reproduction_plan_path")
    plan_path = Path(plan_path_value) if plan_path_value else paper_root / "critic" / "reproduction-plan.json"
    if not plan and plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return plan, str(plan_path) if plan or plan_path.exists() else None


def _load_evidence_map(paper_root: Path) -> dict:
    evidence_map_path = paper_root / "reader" / "evidence-map.json"
    if not evidence_map_path.exists():
        return {}
    return json.loads(evidence_map_path.read_text(encoding="utf-8"))


def _research_decision_lines(decision: dict) -> list[str]:
    if not decision:
        return []
    panel = decision.get("panel_summary") or {}
    lines = [
        "## Research Decision",
        "",
        f"- Recommendation: {decision.get('recommendation', '')}",
        f"- Next action: {decision.get('next_action', '')}",
        f"- Consensus: {panel.get('consensus', '')}",
        f"- Blocking lenses: {', '.join(panel.get('blocking_lenses') or []) or 'None'}",
        f"- Warning reviewers: {', '.join(panel.get('warning_reviewers') or []) or 'None'}",
        "",
        "## Role Assessment Matrix",
    ]
    for assessment in decision.get("role_assessments") or []:
        lines.append(f"- {assessment.get('lens')}: {assessment.get('verdict')} -> {assessment.get('action')}")
        if assessment.get("artifact"):
            lines.append(f"  - Artifact: {assessment['artifact']}")
        if assessment.get("responsibility"):
            lines.append(f"  - Responsibility: {assessment['responsibility']}")
        if assessment.get("promotion_blocking"):
            lines.append("  - Promotion blocking: true")
        if assessment.get("primary_evidence"):
            lines.append(f"  - Evidence: {assessment['primary_evidence']}")
    return lines


def _promotion_review_lines(decision: dict) -> list[str]:
    if not decision:
        return []
    panel = decision.get("panel_summary") or {}
    lines = [
        "## Promotion Review Inputs",
        "",
        f"- Recommendation: {decision.get('recommendation', '')}",
        f"- Consensus: {panel.get('consensus', '')}",
    ]
    for assessment in decision.get("role_assessments") or []:
        lines.append(
            f"- {assessment.get('lens')}: {assessment.get('action')} "
            f"({assessment.get('artifact')})"
        )
    return lines


def _first_bullet_after_heading(text: str, heading: str) -> str:
    in_section = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            in_section = stripped == heading
            continue
        if in_section and stripped.startswith("- "):
            return stripped.removeprefix("- ").strip()
    return ""


def _reading_trust_payload(research_decision: dict, reproduction_plan: dict) -> dict:
    panel = research_decision.get("panel_summary") or {}
    blocking_lenses = panel.get("blocking_lenses") or []
    warning_reviewers = panel.get("warning_reviewers") or []
    source_warnings = reproduction_plan.get("source_warnings") or []
    if blocking_lenses:
        status = "blocked-by-critic"
        read_mode = "Do not promote or reuse claims until the blocking critic lenses are repaired."
    elif warning_reviewers or source_warnings or reproduction_plan.get("human_gate_required"):
        status = "accepted-with-caveats"
        read_mode = "Use this report first, then inspect the evidence map and caveats before reusing claims."
    else:
        status = "accepted"
        read_mode = "Use this report as the low-reading-load entrypoint; open the full reader only when needed."
    return {
        "status": status,
        "read_mode": read_mode,
        "blocking_lenses": blocking_lenses,
        "warning_reviewers": warning_reviewers,
        "reproducibility_caveat_count": len(source_warnings),
    }


def _reading_trust_lines(research_decision: dict, reproduction_plan: dict) -> list[str]:
    trust = _reading_trust_payload(research_decision, reproduction_plan)
    return [
        "## Reading Trust Status",
        "",
        f"- Status: {trust['status']}",
        f"- Read mode: {trust['read_mode']}",
        f"- Blocking lenses: {', '.join(trust['blocking_lenses']) or 'None'}",
        f"- Warning reviewers: {', '.join(trust['warning_reviewers']) or 'None'}",
        f"- Reproducibility caveats: {trust['reproducibility_caveat_count']}",
    ]


def _wiki_target_records(
    *,
    reference_target: str,
    concept_target: str,
    synthesis_target: str,
    reading_report_target: str,
) -> list[dict]:
    return [
        {
            "page_type": "reference",
            "target": reference_target,
            "route_status": "suggested-by-epi",
            "purpose": "Evidence-grounded full-paper reader and source reference.",
            "primary_reader": "all",
        },
        {
            "page_type": "concept",
            "target": concept_target,
            "route_status": "suggested-by-epi",
            "purpose": "Atomic concepts worth reusing across the Obsidian/LLM Wiki.",
            "primary_reader": "senior-domain-researcher",
        },
        {
            "page_type": "synthesis",
            "target": synthesis_target,
            "route_status": "suggested-by-epi",
            "purpose": "Cross-paper synthesis hooks and links to related research directions.",
            "primary_reader": "nature-sci-editor",
        },
        {
            "page_type": "reading_report",
            "target": reading_report_target,
            "route_status": "suggested-by-epi",
            "purpose": "Low-reading-burden entrypoint for human review and recall.",
            "primary_reader": "peer-reviewer",
        },
    ]


def _wiki_rule_source_model() -> dict:
    return {
        "principle": (
            "Obsidian/LLM Wiki construction and write rules are resolved from the target vault "
            "contract and framework references; local installed skills are execution helpers."
        ),
        "resolution_order": [
            {
                "priority": 1,
                "source": "current user instruction",
                "role": "Session-specific goal, language, and safety override.",
            },
            {
                "priority": 2,
                "source": "target vault AGENTS.md",
                "role": "Owner-specific conventions, domain vocabulary, writing style, and safety boundaries.",
            },
            {
                "priority": 3,
                "source": "target vault _meta/agent-operating-contract.md",
                "role": "Agent operating rules for this vault when present.",
            },
            {
                "priority": 4,
                "source": "target vault _meta/schema.md, _meta/taxonomy.md, _meta/directory-structure.md",
                "role": "Final routing, page classes, tag vocabulary, link policy, staged writes, and merge rules.",
            },
            {
                "priority": 5,
                "source": "initiatione/obsidian-wiki-dev liuchf/wiki-skills",
                "role": "Personalized multi-vault contract model and QMD/source-of-truth policy.",
            },
            {
                "priority": 6,
                "source": "Ar9av/obsidian-wiki",
                "role": "General agent-mediated LLM Wiki architecture, manifest/index/log, provenance, and merge pattern.",
            },
            {
                "priority": 7,
                "source": "kepano/obsidian-skills",
                "role": "Obsidian syntax, properties, wikilinks, embeds, callouts, bases, and canvas conventions.",
            },
            {
                "priority": 8,
                "source": "local llm-wiki / wiki-ingest / obsidian-markdown skills",
                "role": "Installed execution adapters; they do not replace the target vault contract or framework repos.",
            },
        ],
        "must_read_before_final_write": [
            "target vault AGENTS.md",
            "_meta/agent-operating-contract.md",
            "_meta/schema.md",
            "_meta/taxonomy.md",
            "_meta/directory-structure.md",
            "index.md",
            "log.md",
            ".manifest.json",
        ],
        "write_contract_requirements": [
            "Search existing pages with index/frontmatter, QMD when configured, and grep before creating a new page.",
            "Merge or update existing notes before creating duplicates.",
            "Keep Markdown vault files as the source of truth; QMD and search indexes are retrieval aids.",
            "Preserve source provenance and distinguish extracted, inferred, and ambiguous claims.",
            "Final wiki pages must be grounded in the source paper artifacts, not reader summaries alone.",
            "Review central formulas, figures, tables, and image evidence before distilling reusable wiki claims.",
            "Respect vault-local staged writes, link format, language policy, taxonomy, and frontmatter schema.",
        ],
    }


def _build_wiki_ingest_brief(
    *,
    slug: str,
    title: str,
    reference_target: str,
    concept_target: str,
    synthesis_target: str,
    reading_report_target: str,
    editorial_summary_text: str,
    technical_reading_text: str,
    research_notes_text: str,
    evidence_map: dict,
    research_decision: dict,
    reproduction_plan: dict,
) -> dict:
    claims = evidence_map.get("claims") if isinstance(evidence_map.get("claims"), list) else []
    roles = evidence_map.get("reader_roles") if isinstance(evidence_map.get("reader_roles"), list) else []
    quick_take = (
        _first_bullet_after_heading(editorial_summary_text, "## Central Claim")
        or "Start from the reading report, then open the reference page for details."
    )
    peer_note = (
        _first_bullet_after_heading(technical_reading_text, "## Method Decomposition")
        or "Inspect method, benchmark, and evidence grounding before reusing claims."
    )
    domain_note = (
        _first_bullet_after_heading(research_notes_text, "## Fit To Research Direction")
        or "Use suggested concept and synthesis routes to connect this paper to the research direction."
    )
    experiment_note = (
        _first_bullet_after_heading(research_notes_text, "## Follow-up Experiments")
        or "Treat reproduction as a compact caveat and keep theory/experiment ideas central."
    )
    return {
        "schema_version": "epi-wiki-ingest-brief-v1",
        "handoff_type": "agent-mediated-wiki-ingest",
        "paper_slug": slug,
        "title": title,
        "trust_status": _reading_trust_payload(research_decision, reproduction_plan),
        "wiki_framework_references": [
            {
                "name": "Ar9av/obsidian-wiki",
                "url": "https://github.com/Ar9av/obsidian-wiki",
                "role": "general agent-mediated Obsidian wiki framework",
            },
            {
                "name": "kepano/obsidian-skills",
                "url": "https://github.com/kepano/obsidian-skills",
                "role": "Obsidian syntax and companion skill conventions",
            },
            {
                "name": "initiatione/obsidian-wiki-dev",
                "url": "https://github.com/initiatione/obsidian-wiki-dev/tree/liuchf/wiki-skills",
                "role": "personalized vault-contract and wiki-skill rules",
            },
        ],
        "wiki_rule_source_model": _wiki_rule_source_model(),
        "ingest_policy": {
            "authority": "Resolve the target vault contract first; local skills are helpers, not sole authority.",
            "final_page_authority": "Final wiki pages are created by the wiki-ingest agent, not fixed by EPI staging.",
            "write_model": "Agent-mediated distillation and merge from the EPI evidence bundle.",
            "merge_policy": "Search existing pages first; update or merge before creating duplicates.",
            "staged_writes_policy": "Respect the target vault staged-write convention when present.",
            "provenance_policy": "Keep extracted, inferred, and ambiguous claims distinguishable.",
            "source_of_truth": "Markdown vault plus EPI source bundle; QMD/search indexes are retrieval aids only.",
            "source_first_policy": (
                "Read mineru/paper.md, mineru/paper.tex, mineru/images/*, and mineru/mineru-manifest.json "
                "before final wiki writing; reader and critic outputs are navigation and quality signals, "
                "not substitutes for the source paper."
            ),
            "suggested_routes_only": True,
        },
        "vault_contract_resolution": [
            "target vault AGENTS.md",
            "_meta/agent-operating-contract.md",
            "_meta/schema.md",
            "_meta/taxonomy.md",
            "_meta/directory-structure.md",
            "vault-local staged-write and link-format settings",
            "generic wiki skill guidance",
        ],
        "obsidian_format_hints": {
            "frontmatter": "Use vault-required properties such as title, summary, tags, sources, aliases, and updated.",
            "links": "Prefer vault-configured wikilinks for internal notes; use Markdown links for external URLs.",
            "tags": "Respect the vault taxonomy and aliases before inventing new tags.",
            "callouts": "Use callouts only when they improve reading, not as a fixed page template.",
        },
        "entrypoints": {
            "reading_report": reading_report_target,
            "reference": reference_target,
            "concept": concept_target,
            "synthesis": synthesis_target,
            "wiki_ingest_brief": "wiki-ingest-brief.json",
            "evidence_map": "reader/evidence-map.json",
        },
        "suggested_routes": _wiki_target_records(
            reference_target=reference_target,
            concept_target=concept_target,
            synthesis_target=synthesis_target,
            reading_report_target=reading_report_target,
        ),
        "role_lenses": {
            "nature_sci_editor": quick_take,
            "peer_reviewer": peer_note,
            "senior_domain_researcher": domain_note,
            "theory_and_experiment": experiment_note,
        },
        "source_bundle": {
            "raw_artifacts": [
                "paper.pdf",
                "metadata.json",
                "mineru/paper.md",
                "mineru/paper.tex",
                "mineru/images/*",
                "mineru/mineru-manifest.json",
            ],
            "primary_source_reading_order": [
                "metadata.json",
                "mineru/paper.md",
                "mineru/paper.tex",
                "mineru/images/*",
                "mineru/mineru-manifest.json",
                "reader/evidence-map.json",
                "reader/figures.md",
                "critic/critic-report.json",
                "critic/research-decision.json",
            ],
            "formula_figure_review": {
                "formulas": (
                    "Review central formulas in mineru/paper.md and mineru/paper.tex; preserve important "
                    "definitions, assumptions, derivation steps, and notation rather than reducing them to prose."
                ),
                "figures_tables_images": (
                    "Interpret figures/tables/images from mineru/images/* and reader/figures.md; preserve what "
                    "each visual shows, the task/metric/baseline context, and any uncertainty from the parse."
                ),
                "parse_uncertainty": (
                    "If formulas, tables, or figures appear missing, ambiguous, or parse-limited, inspect paper.pdf "
                    "before treating the content as absent."
                ),
            },
            "reader_artifacts": [
                "reader/reader.md",
                "reader/editorial-summary.md",
                "reader/technical-reading.md",
                "reader/research-notes.md",
                "reader/figures.md",
                "reader/reproducibility.md",
                "reader/implementation-ideas.md",
            ],
            "critic_artifacts": [
                "critic/critic-report.json",
                "critic/critic-quorum.json",
                "critic/research-decision.json",
                "critic/reader-revision-plan.json",
                "critic/reproduction-plan.json",
            ],
            "evidence": {
                "claim_count": len(claims),
                "reader_roles": roles,
                "exact_evidence_artifact": "reader/evidence-map.json",
            },
        },
        "reading_path": [
            reading_report_target,
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/evidence-map.json",
        ],
    }


def _wiki_ingest_brief_report_lines(wiki_ingest_brief: dict) -> list[str]:
    trust = wiki_ingest_brief.get("trust_status") or {}
    source_bundle = wiki_ingest_brief.get("source_bundle") or {}
    evidence = source_bundle.get("evidence") or {}
    targets = wiki_ingest_brief.get("suggested_routes") or []
    target_summary = ", ".join(str(target.get("page_type")) for target in targets) or "None"
    return [
        "## Wiki Ingest Brief",
        "",
        "- Ingest brief: `wiki-ingest-brief.json`",
        f"- Trust status: {trust.get('status', '')}",
        f"- Suggested wiki routes: {target_summary}",
        f"- Evidence claims tracked: {evidence.get('claim_count', 0)}",
        "- Final wiki pages: created by the wiki-ingest agent, not fixed by EPI staging.",
        "- Final routing, frontmatter, tags, links, merge policy, and staged writes come from the target vault contract.",
        "- Wiki write rules are resolved from target vault contracts plus Ar9av/obsidian-wiki, kepano/obsidian-skills, and personalized wiki-skills references; local skills are adapters.",
        "- Use this brief as the evidence handoff from paper reading to Obsidian/LLM Wiki distillation.",
    ]


def _reading_report_lines(
    *,
    slug: str,
    title: str,
    suggested_route_target: str,
    reference_target: str,
    reader_text: str,
    editorial_summary_text: str,
    technical_reading_text: str,
    research_notes_text: str,
    figures_text: str,
    reproducibility_text: str,
    evidence_map: dict,
    research_decision: dict,
    reproduction_plan: dict,
    wiki_ingest_brief: dict,
    decision_frontmatter_lines: list[str] | None = None,
) -> list[str]:
    panel = research_decision.get("panel_summary") or {}
    quick_take = (
        _first_bullet_after_heading(editorial_summary_text, "## Central Claim")
        or _first_bullet_after_heading(reader_text, "## Why it matters")
        or "Use this report as the low-reading-load entrypoint before opening the full reader notes."
    )
    method_take = _first_bullet_after_heading(technical_reading_text, "## Method Decomposition")
    fit_take = _first_bullet_after_heading(research_notes_text, "## Fit To Research Direction")
    experiment_take = _first_bullet_after_heading(research_notes_text, "## Follow-up Experiments")
    figure_take = _first_bullet_after_heading(figures_text, "## Figure Inventory")
    reproducibility_take = _first_bullet_after_heading(reproducibility_text, "## Reproducibility Signals")
    source_warnings = reproduction_plan.get("source_warnings") or []
    claims = evidence_map.get("claims") if isinstance(evidence_map.get("claims"), list) else []
    roles = evidence_map.get("reader_roles") if isinstance(evidence_map.get("reader_roles"), list) else []
    lines = [
        "---",
        f"paper_slug: {slug}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "stage: staging",
        "page_type: reading_report",
        f"suggested_route_target: {suggested_route_target}",
        f"reference_page: {reference_target}",
        *(decision_frontmatter_lines or []),
        "---",
        "",
        f"# {title} Reading Report",
        "",
        f"Source reference: [{slug}]({reference_target})",
        "",
        "## Quick Take",
        "",
        f"- {quick_take}",
        "",
        "## What To Read If You Only Have 5 Minutes",
        "",
        "- Read `Quick Take`, `Reading Trust Status`, `Quality Gates`, and `Suggested Wiki Routes` first.",
        "- Open the full reader only if you need method details, figures, or exact evidence lines.",
        "",
        *_reading_trust_lines(research_decision, reproduction_plan),
        "",
        *_wiki_ingest_brief_report_lines(wiki_ingest_brief),
        "",
        "## Role-Specific Notes",
        "",
        f"- Nature/Sci editor: {_first_bullet_after_heading(editorial_summary_text, '## Why It Matters') or quick_take}",
        f"- Peer reviewer: {method_take or 'Check method, benchmark, and evidence grounding in reader/technical-reading.md.'}",
        f"- Senior domain researcher: {fit_take or 'Check transfer value and knowledge fit in reader/research-notes.md.'}",
        "",
        "## Theory And Experiment Ideas",
        "",
        f"- Theory lens: {fit_take or quick_take}",
        f"- Experiment lens: {experiment_take or method_take or 'Use the reader notes to identify comparisons, ablations, and benchmark-reading questions.'}",
        "- Reproduction is treated as a compact verification note, not the main reading burden.",
        "",
        "## Evidence Map",
        "",
        f"- Evidence claims tracked: {len(claims)}",
        f"- Reader roles covered: {', '.join(str(role) for role in roles) or 'None recorded'}",
        "- Use `reader/evidence-map.json` when you need exact source addresses behind the summary.",
        "",
        "## Suggested Wiki Routes",
        "",
        f"- Suggested reference draft: `{reference_target}`",
        f"- Suggested concept draft: `concepts/{slug}-concept.md`",
        f"- Suggested synthesis draft: `synthesis/{slug}-synthesis.md`",
        "- Final page paths and page types are decided by the target vault contract and wiki ingest agent.",
        "- This report is the lightweight user-facing entrypoint for human review and wiki ingest.",
        "",
        "## Quality Gates",
        "",
        f"- Critic consensus: {panel.get('consensus', research_decision.get('recommendation', ''))}",
        f"- Blocking lenses: {', '.join(panel.get('blocking_lenses') or []) or 'None'}",
        f"- Warning reviewers: {', '.join(panel.get('warning_reviewers') or []) or 'None'}",
    ]
    if figure_take:
        lines.extend(["", "## Figure / Table Skim", "", f"- {figure_take}"])
    lines.extend(["", "## Reproducibility Caveats", ""])
    if reproducibility_take:
        lines.append(f"- {reproducibility_take}")
    if source_warnings:
        lines.extend(f"- {warning}" for warning in source_warnings)
    if not reproducibility_take and not source_warnings:
        lines.append("- No blocking caveat was promoted into this lightweight report.")
    lines.append("")
    return lines


def stage_paper(vault_path: Path, slug: str, paper_root: Path) -> Path:
    critic_report = json.loads((paper_root / "critic" / "critic-report.json").read_text(encoding="utf-8"))
    outcome = critic_report.get("outcome")
    if outcome != "pass":
        raise ValueError(f"critic outcome must be pass before staging, got {outcome}")

    staging_root = staging_paper_root(vault_path, slug)
    reference_dir = staging_root / "references"
    concept_dir = staging_root / "concepts"
    synthesis_dir = staging_root / "synthesis"
    reports_dir = staging_root / "reports"
    reader_text = (paper_root / "reader" / "reader.md").read_text(encoding="utf-8")
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
    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    title = metadata.get("title", "")
    reference_target = f"references/{slug}.md"
    concept_target = f"concepts/{slug}-concept.md"
    synthesis_target = f"synthesis/{slug}-synthesis.md"
    reading_report_target = f"reports/{slug}-reading-report.md"
    reference_path = reference_dir / f"{slug}.md"
    concept_path = concept_dir / f"{slug}-concept.md"
    synthesis_path = synthesis_dir / f"{slug}-synthesis.md"
    reading_report_path = reports_dir / f"{slug}-reading-report.md"
    wiki_ingest_brief_path = staging_root / "wiki-ingest-brief.json"
    research_decision, research_decision_path = _load_research_decision(paper_root, critic_report)
    reproduction_plan, reproduction_plan_path = _load_reproduction_plan(paper_root, critic_report)
    evidence_map = _load_evidence_map(paper_root)
    decision_frontmatter_lines = _decision_frontmatter_lines(research_decision)
    research_decision_lines = _research_decision_lines(research_decision)
    promotion_review_lines = _promotion_review_lines(research_decision)
    wiki_ingest_brief = _build_wiki_ingest_brief(
        slug=slug,
        title=title,
        reference_target=reference_target,
        concept_target=concept_target,
        synthesis_target=synthesis_target,
        reading_report_target=reading_report_target,
        editorial_summary_text=editorial_summary_text,
        technical_reading_text=technical_reading_text,
        research_notes_text=research_notes_text,
        evidence_map=evidence_map,
        research_decision=research_decision,
        reproduction_plan=reproduction_plan,
    )
    reference = [
        "---",
        f"paper_slug: {slug}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "stage: staging",
        *decision_frontmatter_lines,
        "---",
        "",
        reader_text,
    ]
    if research_decision_lines:
        reference.extend(["", *research_decision_lines, ""])
    write_text_atomic(reference_path, "\n".join(reference))
    write_text_atomic(
        concept_path,
        "\n".join(
            _draft_lines(
                slug=slug,
                title=title,
                page_type="concept",
                suggested_route_target=concept_target,
                reference_target=reference_target,
                promotion_review_lines=promotion_review_lines,
                decision_frontmatter_lines=decision_frontmatter_lines,
            )
        ),
    )
    write_text_atomic(
        synthesis_path,
        "\n".join(
            _draft_lines(
                slug=slug,
                title=title,
                page_type="synthesis",
                suggested_route_target=synthesis_target,
                reference_target=reference_target,
                promotion_review_lines=promotion_review_lines,
                decision_frontmatter_lines=decision_frontmatter_lines,
            )
        ),
    )
    write_json_atomic(wiki_ingest_brief_path, wiki_ingest_brief)
    write_text_atomic(
        reading_report_path,
        "\n".join(
            _reading_report_lines(
                slug=slug,
                title=title,
                suggested_route_target=reading_report_target,
                reference_target=reference_target,
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
                decision_frontmatter_lines=decision_frontmatter_lines,
            )
        ),
    )
    agent_handoff_paths = [
        str(wiki_ingest_brief_path),
        str(reading_report_path),
        str(reference_path),
        str(concept_path),
        str(synthesis_path),
    ]
    plan = {
        "paper_slug": slug,
        "created_at": utc_now(),
        "critic_outcome": outcome,
        "handoff_type": "agent-mediated-wiki-ingest",
        "wiki_write_model": "agent-mediated-vault-contract",
        "final_page_authority": "target-vault-contract-and-wiki-ingest-agent",
        "staged_reference": str(reference_path),
        "staged_concepts": [str(concept_path)],
        "staged_synthesis": [str(synthesis_path)],
        "staged_reports": [str(reading_report_path)],
        "wiki_ingest_brief_path": str(wiki_ingest_brief_path),
        "agent_handoff_paths": agent_handoff_paths,
        "suggested_route_targets": [reference_target, concept_target, synthesis_target, reading_report_target],
    }
    if reproduction_plan:
        plan["reproduction_plan_path"] = reproduction_plan_path
    if research_decision:
        plan["research_decision_path"] = research_decision_path
        plan["recommendation"] = research_decision.get("recommendation")
        plan["next_action"] = research_decision.get("next_action")
        plan["panel_summary"] = research_decision.get("panel_summary", {})
        plan["role_verdicts"] = research_decision.get("role_verdicts", {})
        plan["role_assessments"] = research_decision.get("role_assessments", [])
    write_json_atomic(staging_root / "promotion-plan.json", plan)
    return staging_root
