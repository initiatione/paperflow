from __future__ import annotations

from pathlib import Path

from epi.artifacts import write_text_atomic
from epi.reader_protocol import claim_record, evidence_line, first_section
from epi.reader_revision_guidance import render_role_revision_focus_section


def _sources_text(metadata: dict) -> str:
    sources = metadata.get("sources", [])
    if isinstance(sources, list):
        return ", ".join(str(source) for source in sources)
    return str(sources)


def _claim_id(index: int) -> str:
    return f"reader-claim-{index:03d}"


def write_role_reader_outputs(
    *,
    reader_dir: Path,
    metadata: dict,
    sections: list[tuple[str, str]],
    first_claim_index: int,
    revision_guidance: str = "",
) -> list[dict]:
    claims: list[dict] = []
    abstract_heading, abstract_claim = first_section(sections, "Abstract", 0)
    method_heading, method_claim = first_section(sections, "Method", 1)
    venue = metadata.get("venue", "")
    sources_text = _sources_text(metadata)

    editorial = [
        "# Editorial Summary",
        "",
        "## Central Claim",
        f"- {abstract_claim}",
        f"  {evidence_line('mineru/paper.md', 'heading', abstract_heading)}",
        "",
        "## Why It Matters",
        f"- Venue/context: {venue or 'unspecified'}",
        f"  {evidence_line('metadata.json', 'field', 'venue')}",
        "",
        "## Editorial Caveat",
        "- Inference: treat scope and novelty as provisional until critic checks benchmarks and limitations.",
        f"  {evidence_line('inference', 'basis', 'editorial-caveat')}",
        "",
    ]
    editorial.extend(render_role_revision_focus_section(revision_guidance, "Nature Sci Editor"))
    write_text_atomic(reader_dir / "editorial-summary.md", "\n".join(editorial))
    claims.extend(
        [
            claim_record(
                claim_id=_claim_id(first_claim_index),
                reader_role="nature-sci-editor",
                reader_artifact="reader/editorial-summary.md",
                claim=abstract_claim,
                source="mineru/paper.md",
                locator={"heading": abstract_heading},
            ),
            claim_record(
                claim_id=_claim_id(first_claim_index + 1),
                reader_role="nature-sci-editor",
                reader_artifact="reader/editorial-summary.md",
                claim=f"Venue/context: {venue or 'unspecified'}",
                source="metadata.json",
                locator={"field": "venue"},
            ),
            claim_record(
                claim_id=_claim_id(first_claim_index + 2),
                reader_role="nature-sci-editor",
                reader_artifact="reader/editorial-summary.md",
                claim="Treat scope and novelty as provisional until critic checks benchmarks and limitations.",
                source="inference",
                locator={"basis": "editorial-caveat"},
            ),
        ]
    )

    technical = [
        "# Technical Reading",
        "",
        "## Method Decomposition",
        f"- {method_claim}",
        f"  {evidence_line('mineru/paper.md', 'heading', method_heading)}",
        "",
        "## Reproducibility Hooks",
        f"- Code/data/model/config references: {sources_text or 'unspecified'}",
        f"  {evidence_line('metadata.json', 'field', 'sources')}",
        "",
        "## Reviewer Checkpoint",
        "- Inference: verify baselines, metrics, tasks, and ablations before accepting performance claims.",
        f"  {evidence_line('inference', 'basis', 'technical-review-checkpoint')}",
        "",
    ]
    technical.extend(render_role_revision_focus_section(revision_guidance, "Peer Reviewer"))
    write_text_atomic(reader_dir / "technical-reading.md", "\n".join(technical))
    claims.extend(
        [
            claim_record(
                claim_id=_claim_id(first_claim_index + 3),
                reader_role="peer-reviewer",
                reader_artifact="reader/technical-reading.md",
                claim=method_claim,
                source="mineru/paper.md",
                locator={"heading": method_heading},
            ),
            claim_record(
                claim_id=_claim_id(first_claim_index + 4),
                reader_role="peer-reviewer",
                reader_artifact="reader/technical-reading.md",
                claim=f"Code/data/model/config references: {sources_text or 'unspecified'}",
                source="metadata.json",
                locator={"field": "sources"},
            ),
            claim_record(
                claim_id=_claim_id(first_claim_index + 5),
                reader_role="peer-reviewer",
                reader_artifact="reader/technical-reading.md",
                claim="Verify baselines, metrics, tasks, and ablations before accepting performance claims.",
                source="inference",
                locator={"basis": "technical-review-checkpoint"},
            ),
        ]
    )

    research_notes = [
        "# Research Notes",
        "",
        "## Fit To Research Direction",
        "- Inference: evaluate whether this paper advances the user's configured research profile, methods, tasks, or implementation practice.",
        f"  {evidence_line('inference', 'basis', 'research-fit')}",
        "",
        "## Follow-up Experiments",
        "- Inference: turn useful methods into theory comparisons, ablation ideas, benchmark-reading notes, or small verification checks.",
        f"  {evidence_line('inference', 'basis', 'follow-up-experiments')}",
        "",
    ]
    research_notes.extend(render_role_revision_focus_section(revision_guidance, "Senior Domain Researcher"))
    write_text_atomic(reader_dir / "research-notes.md", "\n".join(research_notes))
    claims.extend(
        [
            claim_record(
                claim_id=_claim_id(first_claim_index + 6),
                reader_role="senior-domain-researcher",
                reader_artifact="reader/research-notes.md",
                claim="Evaluate whether this paper advances the user's configured research profile, methods, tasks, or implementation practice.",
                source="inference",
                locator={"basis": "research-fit"},
            ),
            claim_record(
                claim_id=_claim_id(first_claim_index + 7),
                reader_role="senior-domain-researcher",
                reader_artifact="reader/research-notes.md",
                claim="Turn useful methods into theory comparisons, ablation ideas, benchmark-reading notes, or small verification checks.",
                source="inference",
                locator={"basis": "follow-up-experiments"},
            ),
        ]
    )
    return claims
