from __future__ import annotations

from pathlib import Path


MINERU_MARKDOWN_ARTIFACT_LABEL = "mineru/<slug>.md"
LEGACY_MINERU_MARKDOWN_ARTIFACT_LABEL = "mineru/paper.md"


def canonical_mineru_markdown_relative_path(slug: str) -> str:
    return f"mineru/{slug}.md"


def canonical_mineru_markdown_path(paper_root: Path) -> Path:
    return paper_root / canonical_mineru_markdown_relative_path(paper_root.name)


def resolve_mineru_markdown_path(paper_root: Path) -> Path:
    canonical = canonical_mineru_markdown_path(paper_root)
    if canonical.exists():
        return canonical
    return paper_root / "mineru" / "paper.md"


def resolved_mineru_markdown_relative_path(paper_root: Path) -> str:
    return resolve_mineru_markdown_path(paper_root).relative_to(paper_root).as_posix()


def is_mineru_markdown_artifact(value: str) -> bool:
    normalized = str(value or "").replace("\\", "/").strip()
    return normalized.startswith("mineru/") and normalized.endswith(".md")


def source_first_artifacts(paper_root: Path) -> list[str]:
    return [
        "paper.pdf",
        "metadata.json",
        resolved_mineru_markdown_relative_path(paper_root),
        "mineru/paper.tex",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]


def canonical_source_first_artifacts(slug: str) -> list[str]:
    return [
        "paper.pdf",
        "metadata.json",
        canonical_mineru_markdown_relative_path(slug),
        "mineru/paper.tex",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]


def mineru_markdown_artifact_candidates(paper_root: Path) -> list[str]:
    markdown = resolved_mineru_markdown_relative_path(paper_root)
    candidates = [markdown]
    legacy = LEGACY_MINERU_MARKDOWN_ARTIFACT_LABEL
    if legacy != markdown:
        candidates.append(legacy)
    return candidates
