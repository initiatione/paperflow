from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import file_sha256, utc_now, write_json_atomic, write_text_atomic
from epi.claim_support import build_claim_support_map
from epi.reader_protocol import (
    READER_ROLES,
    REQUIRED_ARTIFACTS,
    claim_record,
    evidence_line,
    markdown_sections,
)
from epi.reader_outputs import write_role_reader_outputs
from epi.reader_revision_guidance import render_role_revision_focus_section
from epi.source_artifacts import resolve_mineru_markdown_path, resolved_mineru_markdown_relative_path


def _revision_guidance_text(reader_dir: Path) -> str:
    guidance_path = reader_dir / "revision-guidance.md"
    return guidance_path.read_text(encoding="utf-8") if guidance_path.exists() else ""


def _read_optional_json_object(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def generate_reader_outputs(paper_root: Path) -> dict:
    started_at = utc_now()
    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    mineru_markdown_path = resolve_mineru_markdown_path(paper_root)
    mineru_text = mineru_markdown_path.read_text(encoding="utf-8")
    paper_pdf_path = paper_root / "paper.pdf"
    paper_tex_path = paper_root / "mineru" / "paper.tex"
    mineru_manifest_path = paper_root / "mineru" / "mineru-manifest.json"
    paper_tex_text = paper_tex_path.read_text(encoding="utf-8", errors="ignore") if paper_tex_path.exists() else ""
    mineru_manifest = _read_optional_json_object(mineru_manifest_path)
    sections = markdown_sections(mineru_text)
    title = metadata.get("title", "Untitled Paper")
    reader_dir = paper_root / "reader"
    reader_dir.mkdir(parents=True, exist_ok=True)
    revision_guidance = _revision_guidance_text(reader_dir)
    claims: list[dict] = []
    mineru_markdown_source = resolved_mineru_markdown_relative_path(paper_root)

    reader = [
        f"# {title}",
        "",
        "## 核心阅读",
    ]
    for index, (heading, claim_text) in enumerate(sections[:2], start=1):
        reader.append(f"- Claim {index}: {claim_text}")
        reader.append(f"  {evidence_line(mineru_markdown_source, 'heading', heading)}")
        claims.append(
            claim_record(
                claim_id=f"reader-claim-{index:03d}",
                reader_role="nature-sci-editor" if index == 1 else "peer-reviewer",
                reader_artifact="reader/reader.md",
                claim=claim_text,
                source=mineru_markdown_source,
                locator={"heading": heading},
            )
        )
    reader.append("")
    reader.append("## Metadata")
    reader.append(f"- Venue: {metadata.get('venue', '')}")
    reader.append(f"  {evidence_line('metadata.json', 'field', 'venue')}")
    claims.append(
        claim_record(
            claim_id=f"reader-claim-{len(claims) + 1:03d}",
            reader_role="nature-sci-editor",
            reader_artifact="reader/reader.md",
            claim=f"Venue: {metadata.get('venue', '')}",
            source="metadata.json",
            locator={"field": "venue"},
        )
    )
    write_text_atomic(reader_dir / "reader.md", "\n".join(reader) + "\n")

    sources = metadata.get("sources", [])
    if isinstance(sources, list):
        sources_text = ", ".join(str(source) for source in sources)
    else:
        sources_text = str(sources)
    claims.extend(
        write_role_reader_outputs(
            reader_dir=reader_dir,
            metadata=metadata,
            sections=sections,
            first_claim_index=len(claims) + 1,
            mineru_markdown_source=mineru_markdown_source,
            revision_guidance=revision_guidance,
            paper_tex_text=paper_tex_text,
            mineru_manifest=mineru_manifest,
        )
    )

    image_dir = paper_root / "mineru" / "images"
    images = sorted(path.name for path in image_dir.iterdir() if path.is_file()) if image_dir.exists() else []
    figures = ["# Figures And Tables", ""]
    if images:
        for image_name in images:
            figures.append(f"- Detected figure asset: {image_name}")
            figures.append(f"  {evidence_line('mineru/images', 'image', image_name)}")
            claims.append(
                claim_record(
                    claim_id=f"reader-claim-{len(claims) + 1:03d}",
                    reader_role="peer-reviewer",
                    reader_artifact="reader/figures.md",
                    claim=f"Detected figure asset: {image_name}",
                    source="mineru/images",
                    locator={"image": image_name},
                )
            )
    else:
        figures.append("No figures were detected in mineru/images.")
    figures.append("")
    write_text_atomic(reader_dir / "figures.md", "\n".join(figures))

    reproducibility_lines = [
        "# Reproducibility",
        "",
        f"Code and data availability references: {sources_text or 'unspecified'}.",
        "",
        evidence_line("metadata.json", "field", "sources"),
    ]
    if paper_pdf_path.exists():
        reproducibility_lines.extend(
            [
                "",
                "## PDF Fallback",
                "",
                "- PDF fallback artifact is available for parse checks.",
                f"  {evidence_line('paper.pdf', 'field', 'available')}",
            ]
        )
    reproducibility_lines.extend(render_role_revision_focus_section(revision_guidance, "Peer Reviewer"))
    write_text_atomic(
        reader_dir / "reproducibility.md",
        "\n".join(reproducibility_lines) + "\n",
    )
    claims.append(
        claim_record(
            claim_id=f"reader-claim-{len(claims) + 1:03d}",
            reader_role="peer-reviewer",
            reader_artifact="reader/reproducibility.md",
            claim=f"Code and data availability references: {sources_text or 'unspecified'}",
            source="metadata.json",
            locator={"field": "sources"},
        )
    )
    if paper_pdf_path.exists():
        claims.append(
            claim_record(
                claim_id=f"reader-claim-{len(claims) + 1:03d}",
                reader_role="peer-reviewer",
                reader_artifact="reader/reproducibility.md",
                claim="PDF fallback artifact is available for parse checks.",
                source="paper.pdf",
                locator={"field": "available"},
            )
        )
    ideas_lines = [
        "# Implementation Ideas",
        "",
        "- Inference: evaluate whether the paper's method can transfer to the user's configured research profile.",
        f"  {evidence_line('inference', 'basis', 'implementation-ideas')}",
    ]
    ideas_lines.extend(render_role_revision_focus_section(revision_guidance, "Senior Domain Researcher"))
    write_text_atomic(
        reader_dir / "implementation-ideas.md",
        "\n".join(ideas_lines) + "\n",
    )
    claims.append(
        claim_record(
            claim_id=f"reader-claim-{len(claims) + 1:03d}",
            reader_role="senior-domain-researcher",
            reader_artifact="reader/implementation-ideas.md",
            claim="Evaluate whether the paper's method can transfer to the user's configured research profile.",
            source="inference",
            locator={"basis": "implementation-ideas"},
        )
    )
    write_json_atomic(
        reader_dir / "evidence-map.json",
        {
            "schema_version": "epi-reader-evidence-map-v1",
            "paper_title": title,
            "reader_roles": READER_ROLES,
            "required_artifacts": REQUIRED_ARTIFACTS,
            "claims": claims,
        },
    )
    write_json_atomic(
        reader_dir / "claim-support.json",
        build_claim_support_map(paper_title=title, claims=claims),
    )
    input_artifact_hashes = {
        "metadata.json": file_sha256(paper_root / "metadata.json"),
        mineru_markdown_source: file_sha256(mineru_markdown_path),
    }
    optional_inputs = {
        "paper.pdf": paper_pdf_path,
        "mineru/paper.tex": paper_tex_path,
        "mineru/mineru-manifest.json": mineru_manifest_path,
    }
    for label, path in optional_inputs.items():
        if path.exists():
            input_artifact_hashes[label] = file_sha256(path)

    return {
        "reader_dir": str(reader_dir),
        "evidence_count": len(claims),
        "claim_support_count": len(claims),
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 0,
        "input_artifact_hashes": input_artifact_hashes,
        "output_artifact_hashes": {
            "reader.md": file_sha256(reader_dir / "reader.md"),
            "editorial-summary.md": file_sha256(reader_dir / "editorial-summary.md"),
            "technical-reading.md": file_sha256(reader_dir / "technical-reading.md"),
            "research-notes.md": file_sha256(reader_dir / "research-notes.md"),
            "figures.md": file_sha256(reader_dir / "figures.md"),
            "reproducibility.md": file_sha256(reader_dir / "reproducibility.md"),
            "implementation-ideas.md": file_sha256(reader_dir / "implementation-ideas.md"),
            "evidence-map.json": file_sha256(reader_dir / "evidence-map.json"),
            "claim-support.json": file_sha256(reader_dir / "claim-support.json"),
        },
    }
