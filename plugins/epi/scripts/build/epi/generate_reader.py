from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import file_sha256, utc_now, write_text_atomic


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if current_heading and current_body:
                sections.append((current_heading, current_body[0]))
            current_heading = line.lstrip("#").strip()
            current_body = []
            continue
        current_body.append(line)

    if current_heading and current_body:
        sections.append((current_heading, current_body[0]))
    return sections


def _evidence_line(source: str, key: str, value: str) -> str:
    return f"Evidence: source={source}; {key}={value}"


def generate_reader_outputs(paper_root: Path) -> dict:
    started_at = utc_now()
    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    mineru_text = (paper_root / "mineru" / "paper.md").read_text(encoding="utf-8")
    sections = _markdown_sections(mineru_text)
    title = metadata.get("title", "Untitled Paper")
    reader_dir = paper_root / "reader"
    reader_dir.mkdir(parents=True, exist_ok=True)

    reader = [
        f"# {title}",
        "",
        "## 核心阅读",
    ]
    for index, (heading, claim_text) in enumerate(sections[:2], start=1):
        reader.append(f"- Claim {index}: {claim_text}")
        reader.append(f"  {_evidence_line('mineru/paper.md', 'heading', heading)}")
    reader.append("")
    reader.append("## Metadata")
    reader.append(f"- Venue: {metadata.get('venue', '')}")
    reader.append(f"  {_evidence_line('metadata.json', 'field', 'venue')}")
    write_text_atomic(reader_dir / "reader.md", "\n".join(reader) + "\n")

    image_dir = paper_root / "mineru" / "images"
    images = sorted(path.name for path in image_dir.iterdir() if path.is_file()) if image_dir.exists() else []
    figures = ["# Figures And Tables", ""]
    if images:
        for image_name in images:
            figures.append(f"- Detected figure asset: {image_name}")
            figures.append(f"  {_evidence_line('mineru/images', 'image', image_name)}")
    else:
        figures.append("No figures were detected in mineru/images.")
    figures.append("")
    write_text_atomic(reader_dir / "figures.md", "\n".join(figures))

    sources = metadata.get("sources", [])
    if isinstance(sources, list):
        sources_text = ", ".join(str(source) for source in sources)
    else:
        sources_text = str(sources)
    reproducibility_text = (
        "# Reproducibility\n\n"
        f"Code and data availability references: {sources_text or 'unspecified'}.\n\n"
        f"{_evidence_line('metadata.json', 'field', 'sources')}\n"
    )
    write_text_atomic(
        reader_dir / "reproducibility.md",
        reproducibility_text,
    )
    ideas_text = (
        "# Implementation Ideas\n\n"
        "- Inference: evaluate whether the control pipeline can transfer to local robotics projects.\n"
        f"  {_evidence_line('inference', 'basis', 'implementation-ideas')}\n"
    )
    write_text_atomic(
        reader_dir / "implementation-ideas.md",
        ideas_text,
    )
    return {
        "reader_dir": str(reader_dir),
        "evidence_count": len(sections[:2]) + len(images) + 2,
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 0,
        "input_artifact_hashes": {
            "metadata.json": file_sha256(paper_root / "metadata.json"),
            "mineru/paper.md": file_sha256(paper_root / "mineru" / "paper.md"),
        },
        "output_artifact_hashes": {
            "reader.md": file_sha256(reader_dir / "reader.md"),
            "figures.md": file_sha256(reader_dir / "figures.md"),
            "reproducibility.md": file_sha256(reader_dir / "reproducibility.md"),
            "implementation-ideas.md": file_sha256(reader_dir / "implementation-ideas.md"),
        },
    }
