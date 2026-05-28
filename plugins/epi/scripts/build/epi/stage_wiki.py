from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import staging_paper_root, utc_now, write_json_atomic, write_text_atomic


def _draft_lines(
    *,
    slug: str,
    title: str,
    page_type: str,
    compiled_target: str,
    reference_target: str,
) -> list[str]:
    heading_suffix = "Concept Draft" if page_type == "concept" else "Synthesis Draft"
    return [
        "---",
        f"paper_slug: {slug}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "stage: staging",
        f"page_type: {page_type}",
        f"compiled_target: {compiled_target}",
        f"reference_page: {reference_target}",
        "---",
        "",
        f"# {title} {heading_suffix}",
        "",
        f"Source reference: [{slug}]({reference_target})",
        "",
        f"Minimal {page_type} draft staged for promotion review.",
    ]


def stage_paper(vault_path: Path, slug: str, paper_root: Path) -> Path:
    critic_report = json.loads((paper_root / "critic" / "critic-report.json").read_text(encoding="utf-8"))
    outcome = critic_report.get("outcome")
    if outcome != "pass":
        raise ValueError(f"critic outcome must be pass before staging, got {outcome}")

    staging_root = staging_paper_root(vault_path, slug)
    reference_dir = staging_root / "references"
    concept_dir = staging_root / "concepts"
    synthesis_dir = staging_root / "synthesis"
    reader_text = (paper_root / "reader" / "reader.md").read_text(encoding="utf-8")
    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    title = metadata.get("title", "")
    reference_target = f"references/{slug}.md"
    concept_target = f"concepts/{slug}-concept.md"
    synthesis_target = f"synthesis/{slug}-synthesis.md"
    reference_path = reference_dir / f"{slug}.md"
    concept_path = concept_dir / f"{slug}-concept.md"
    synthesis_path = synthesis_dir / f"{slug}-synthesis.md"
    reference = [
        "---",
        f"paper_slug: {slug}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "stage: staging",
        "---",
        "",
        reader_text,
    ]
    write_text_atomic(reference_path, "\n".join(reference))
    write_text_atomic(
        concept_path,
        "\n".join(
            _draft_lines(
                slug=slug,
                title=title,
                page_type="concept",
                compiled_target=concept_target,
                reference_target=reference_target,
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
                compiled_target=synthesis_target,
                reference_target=reference_target,
            )
        ),
    )
    plan = {
        "paper_slug": slug,
        "created_at": utc_now(),
        "critic_outcome": outcome,
        "staged_reference": str(reference_path),
        "staged_concepts": [str(concept_path)],
        "staged_synthesis": [str(synthesis_path)],
        "compiled_targets": [reference_target, concept_target, synthesis_target],
    }
    write_json_atomic(staging_root / "promotion-plan.json", plan)
    return staging_root
