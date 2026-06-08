from __future__ import annotations

from pathlib import Path
from typing import Any

from epi.artifacts import write_text_atomic
from epi.reader_protocol import claim_record, evidence_line, first_section
from epi.reader_revision_guidance import render_role_revision_focus_section
from epi.source_artifacts import MINERU_MARKDOWN_ARTIFACT_LABEL


def _sources_text(metadata: dict) -> str:
    sources = metadata.get("sources", [])
    if isinstance(sources, list):
        return ", ".join(str(source) for source in sources)
    return str(sources)


def _claim_id(index: int) -> str:
    return f"reader-claim-{index:03d}"


def _tex_evidence_cue(tex_text: str) -> str:
    if "\\begin{equation" in tex_text:
        return "equation"
    if "\\[" in tex_text or "\\begin{align" in tex_text:
        return "display-math"
    if "$" in tex_text:
        return "math"
    return "tex-source-available"


def _manifest_outputs(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        return []
    return [item for item in manifest.get("outputs") or [] if isinstance(item, dict)]


def _manifest_output_name(output: dict[str, Any]) -> str:
    for field in ("file_name", "name", "output", "markdown_path", "pdf_path", "path"):
        value = str(output.get(field) or "").replace("\\", "/").strip()
        if value:
            return value.rsplit("/", 1)[-1]
    return "output"


def _primary_manifest_output(manifest: dict[str, Any] | None) -> tuple[str, dict[str, Any]] | None:
    outputs = _manifest_outputs(manifest)
    for output in outputs:
        if _manifest_output_name(output) == "paper.pdf":
            return "paper.pdf", output
    if outputs:
        output = outputs[0]
        return _manifest_output_name(output), output
    return None


def write_role_reader_outputs(
    *,
    reader_dir: Path,
    metadata: dict,
    sections: list[tuple[str, str]],
    first_claim_index: int,
    mineru_markdown_source: str = MINERU_MARKDOWN_ARTIFACT_LABEL,
    revision_guidance: str = "",
    paper_tex_text: str = "",
    mineru_manifest: dict[str, Any] | None = None,
) -> list[dict]:
    claims: list[dict] = []

    def add_claim(
        *,
        reader_role: str,
        reader_artifact: str,
        claim: str,
        source: str,
        locator: dict[str, str],
    ) -> None:
        claims.append(
            claim_record(
                claim_id=_claim_id(first_claim_index + len(claims)),
                reader_role=reader_role,
                reader_artifact=reader_artifact,
                claim=claim,
                source=source,
                locator=locator,
            )
        )

    abstract_heading, abstract_claim = first_section(sections, "Abstract", 0)
    method_heading, method_claim = first_section(sections, "Method", 1)
    venue = metadata.get("venue", "")
    sources_text = _sources_text(metadata)

    editorial = [
        "# Editorial Summary",
        "",
        "## Central Claim",
        f"- {abstract_claim}",
        f"  {evidence_line(mineru_markdown_source, 'heading', abstract_heading)}",
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
    add_claim(
        reader_role="nature-sci-editor",
        reader_artifact="reader/editorial-summary.md",
        claim=abstract_claim,
        source=mineru_markdown_source,
        locator={"heading": abstract_heading},
    )
    add_claim(
        reader_role="nature-sci-editor",
        reader_artifact="reader/editorial-summary.md",
        claim=f"Venue/context: {venue or 'unspecified'}",
        source="metadata.json",
        locator={"field": "venue"},
    )
    add_claim(
        reader_role="nature-sci-editor",
        reader_artifact="reader/editorial-summary.md",
        claim="Treat scope and novelty as provisional until critic checks benchmarks and limitations.",
        source="inference",
        locator={"basis": "editorial-caveat"},
    )

    technical = [
        "# Technical Reading",
        "",
        "## Method Decomposition",
        f"- {method_claim}",
        f"  {evidence_line(mineru_markdown_source, 'heading', method_heading)}",
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
    source_first_claims: list[tuple[str, str, dict[str, str]]] = []
    if paper_tex_text:
        tex_cue = _tex_evidence_cue(paper_tex_text)
        tex_claim = "MinerU TeX source is available for formula and notation checks."
        technical.extend(
            [
                "## Source Bundle Review",
                f"- {tex_claim}",
                f"  {evidence_line('mineru/paper.tex', 'cue', tex_cue)}",
                "",
            ]
        )
        source_first_claims.append((tex_claim, "mineru/paper.tex", {"cue": tex_cue}))

    manifest_output = _primary_manifest_output(mineru_manifest)
    if manifest_output:
        output_name, output_record = manifest_output
        if "state" in output_record:
            state_claim = f"MinerU parse output {output_name} state: {output_record.get('state')}."
            technical.extend(
                [
                    f"- {state_claim}",
                    f"  Evidence: source=mineru/mineru-manifest.json; output={output_name}; field=state",
                ]
            )
            source_first_claims.append(
                (
                    state_claim,
                    "mineru/mineru-manifest.json",
                    {"output": output_name, "field": "state"},
                )
            )
    warnings = mineru_manifest.get("warnings") if isinstance(mineru_manifest, dict) else None
    if warnings:
        warning_count = len(warnings) if isinstance(warnings, list) else 1
        warning_claim = f"MinerU manifest records {warning_count} parse warning(s)."
        technical.extend(
            [
                f"- {warning_claim}",
                f"  {evidence_line('mineru/mineru-manifest.json', 'field', 'warnings')}",
                "",
            ]
        )
        source_first_claims.append(
            (
                warning_claim,
                "mineru/mineru-manifest.json",
                {"field": "warnings"},
            )
        )
    technical.extend(render_role_revision_focus_section(revision_guidance, "Peer Reviewer"))
    write_text_atomic(reader_dir / "technical-reading.md", "\n".join(technical))
    add_claim(
        reader_role="peer-reviewer",
        reader_artifact="reader/technical-reading.md",
        claim=method_claim,
        source=mineru_markdown_source,
        locator={"heading": method_heading},
    )
    add_claim(
        reader_role="peer-reviewer",
        reader_artifact="reader/technical-reading.md",
        claim=f"Code/data/model/config references: {sources_text or 'unspecified'}",
        source="metadata.json",
        locator={"field": "sources"},
    )
    add_claim(
        reader_role="peer-reviewer",
        reader_artifact="reader/technical-reading.md",
        claim="Verify baselines, metrics, tasks, and ablations before accepting performance claims.",
        source="inference",
        locator={"basis": "technical-review-checkpoint"},
    )
    for claim, source, locator in source_first_claims:
        add_claim(
            reader_role="peer-reviewer",
            reader_artifact="reader/technical-reading.md",
            claim=claim,
            source=source,
            locator=locator,
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
    add_claim(
        reader_role="senior-domain-researcher",
        reader_artifact="reader/research-notes.md",
        claim="Evaluate whether this paper advances the user's configured research profile, methods, tasks, or implementation practice.",
        source="inference",
        locator={"basis": "research-fit"},
    )
    add_claim(
        reader_role="senior-domain-researcher",
        reader_artifact="reader/research-notes.md",
        claim="Turn useful methods into theory comparisons, ablation ideas, benchmark-reading notes, or small verification checks.",
        source="inference",
        locator={"basis": "follow-up-experiments"},
    )
    return claims
