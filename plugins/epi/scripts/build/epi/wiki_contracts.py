from __future__ import annotations


REQUIRED_WIKI_SKILLS: tuple[str, ...] = (
    "epi-wiki-deposition",
    "wiki-ingest",
    "wiki-provenance",
    "tag-taxonomy",
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


def required_wiki_skills() -> list[str]:
    return list(REQUIRED_WIKI_SKILLS)


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


def final_source_review_must_record() -> list[str]:
    fields = ", ".join(RESEARCH_REVIEW_FIELDS)
    states = " -> ".join(PAGE_LIFECYCLE_STATES)
    skills = ", ".join(REQUIRED_WIKI_SKILLS)
    return [
        "reviewed_artifacts[] with status=reviewed and sha256/file_count for source artifacts",
        f"wiki_batch_ingest with status=completed, wiki_skill_used including {skills}, and paper_slugs[]",
        "formula_review with status=reviewed and summary",
        "figure_table_image_review with status=reviewed and summary",
        "pdf_fallback_review with status=reviewed or not-needed and summary",
        "final_page_provenance[] mapping every final wiki page to source_grounded=true",
        "formal_content_quality with audit_pages_excluded=true",
        f"research review sections: {fields}",
        f"page_lifecycle with status=verified, allowed states {states}, and verified requirements",
    ]
