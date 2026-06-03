from __future__ import annotations


EPI_DEPOSITION_SKILL = "epi-paper-deposition"

DEPOSITION_SKILL_COMPATIBILITY_ALIASES: tuple[str, ...] = (
    "epi-wiki-deposition",
)

REQUIRED_WIKI_SKILLS: tuple[str, ...] = (
    EPI_DEPOSITION_SKILL,
    "llm-wiki",
    "wiki-ingest",
    "wiki-context-pack",
    "wiki-lint",
    "wiki-stage-commit",
    "wiki-status",
    "wiki-query",
    "wiki-provenance",
    "tag-taxonomy",
)

QUALITY_ENHANCEMENT_WIKI_SKILLS: tuple[str, ...] = (
    "wiki-synthesize",
    "wiki-dedup",
    "cross-linker",
    "tag-taxonomy",
)

OPTIONAL_WIKI_SKILLS: tuple[str, ...] = (
    "wiki-dashboard",
    "wiki-digest",
    "wiki-export",
)

FORMAL_PAGE_FAMILIES: tuple[dict[str, str], ...] = (
    {
        "name": "references",
        "path": "references/",
        "role": "single-paper evidence page",
        "purpose": "Preserve claim/support/evidence for one source paper.",
    },
    {
        "name": "concepts",
        "path": "concepts/",
        "role": "method, theory, or term page",
        "purpose": "Maintain reusable scientific concepts across papers.",
    },
    {
        "name": "derivations",
        "path": "derivations/",
        "role": "theory and formula reconstruction page",
        "purpose": "Rebuild assumptions, notation, derivation chain, and skipped steps.",
    },
    {
        "name": "experiments",
        "path": "experiments/",
        "role": "implementation and reproducibility page",
        "purpose": "Judge baselines, metrics, cost, difficulty, and reproducibility risk.",
    },
    {
        "name": "synthesis",
        "path": "synthesis/",
        "role": "cross-paper comparison page",
        "purpose": "Compare methods, claims, contradictions, and evidence clusters.",
    },
    {
        "name": "reports",
        "path": "reports/",
        "role": "low-burden reading entrypoint",
        "purpose": "Give humans a compact route into a paper or topic.",
    },
    {
        "name": "opportunities",
        "path": "opportunities/",
        "role": "research opportunity page",
        "purpose": "Separate author-claimed novelty from EPI-confirmed gaps and project ideas.",
    },
)

RESEARCH_REVIEW_FIELDS: tuple[str, ...] = (
    "theory_reconstruction",
    "formula_derivation",
    "figure_table_evidence",
    "novelty_type",
    "implementability",
    "reproducibility_risk",
    "research_gap",
    "cost_level",
)

PAGE_LIFECYCLE_STATES: tuple[str, ...] = (
    "draft",
    "source-reviewed",
    "under-review",
    "verified",
)

VERIFIED_PAGE_REQUIREMENTS: tuple[str, ...] = (
    "source_reread",
    "formula_figure_review",
    "evidence_path_complete",
    "final_source_review_complete",
)

FORMAL_FRONTMATTER_REQUIRED_FIELDS: tuple[str, ...] = (
    "title",
    "category",
    "page_family",
    "tags",
    "aliases",
    "sources",
    "summary",
    "provenance",
    "base_confidence",
    "lifecycle",
    "lifecycle_changed",
    "tier",
    "created",
    "updated",
)

PROVENANCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "extracted",
    "inferred",
    "ambiguous",
)

INITIAL_LIFECYCLE_VALUES: tuple[str, ...] = (
    "draft",
    "review-needed",
)

WIKI_DEPOSITION_QUALITY_GATES: dict[str, object] = {
    "frontmatter_required": True,
    "compiled_knowledge_required": True,
    "formula_derivation_required": True,
    "human_stage_review_required": True,
    "lint_required": True,
    "stage_commit_required": True,
    "sources_required": True,
    "provenance_required": True,
    "wikilinks_required": True,
    "forbidden_fenced_formula_languages": ["math", "tex", "latex"],
    "internal_roots_forbidden_in_formal_graph": ["_epi", "_raw", "_staging", "_runs", "_quarantine"],
}


def required_wiki_skills() -> list[str]:
    return list(REQUIRED_WIKI_SKILLS)


def deposition_skill_compatibility_aliases() -> list[str]:
    return list(DEPOSITION_SKILL_COMPATIBILITY_ALIASES)


def quality_enhancement_wiki_skills() -> list[str]:
    return list(QUALITY_ENHANCEMENT_WIKI_SKILLS)


def optional_wiki_skills() -> list[str]:
    return list(OPTIONAL_WIKI_SKILLS)


def formal_page_family_names() -> list[str]:
    return [item["name"] for item in FORMAL_PAGE_FAMILIES]


def formal_page_family_paths() -> list[str]:
    return [item["path"] for item in FORMAL_PAGE_FAMILIES]


def formal_page_family_records() -> list[dict[str, str]]:
    return [dict(item) for item in FORMAL_PAGE_FAMILIES]


def research_review_fields() -> list[str]:
    return list(RESEARCH_REVIEW_FIELDS)


def page_lifecycle_states() -> list[str]:
    return list(PAGE_LIFECYCLE_STATES)


def verified_page_requirements() -> list[str]:
    return list(VERIFIED_PAGE_REQUIREMENTS)


def formal_frontmatter_schema() -> dict[str, object]:
    return {
        "required_fields": list(FORMAL_FRONTMATTER_REQUIRED_FIELDS),
        "provenance_required_fields": list(PROVENANCE_REQUIRED_FIELDS),
        "category_must_match_page_family": True,
        "initial_lifecycle_values": list(INITIAL_LIFECYCLE_VALUES),
        "allowed_lifecycle_values": list(PAGE_LIFECYCLE_STATES),
    }


def wiki_deposition_quality_gates() -> dict[str, object]:
    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in WIKI_DEPOSITION_QUALITY_GATES.items()
    }


def final_source_review_must_record() -> list[str]:
    fields = ", ".join(RESEARCH_REVIEW_FIELDS)
    states = " -> ".join(PAGE_LIFECYCLE_STATES)
    skills = ", ".join(REQUIRED_WIKI_SKILLS)
    frontmatter = ", ".join(FORMAL_FRONTMATTER_REQUIRED_FIELDS)
    return [
        "reviewed_artifacts[] with status=reviewed and sha256/file_count for source artifacts",
        f"wiki_batch_ingest with status=completed, wiki_skill_used including {skills}, and paper_slugs[]",
        f"formal page frontmatter fields: {frontmatter}",
        "formal page body language defaults to Chinese; English is kept for titles, terms, abbreviations, evidence fields, paths, code, formulas, and metrics",
        "formal page provenance.extracted, provenance.inferred, and provenance.ambiguous",
        "formula_review with status=reviewed and summary",
        "figure_table_image_review with status=reviewed and summary",
        "pdf_fallback_review with status=reviewed or not-needed and summary",
        "final_page_provenance[] mapping every final wiki page to source_grounded=true",
        "formal_content_quality with audit_pages_excluded=true and language_policy.chinese_body_default=true",
        f"research review sections: {fields}",
        f"page_lifecycle with status=verified, allowed states {states}, and verified requirements",
    ]
