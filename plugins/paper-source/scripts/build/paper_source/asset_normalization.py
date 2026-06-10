from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paper_source.artifacts import file_sha256, utc_now, write_json_atomic, write_text_atomic
from paper_source.source_artifacts import has_nonempty_mineru_tex, resolve_mineru_markdown_path


SCHEMA_VERSION = "paper-source-asset-normalization-v1"
FIGURE_INDEX_SCHEMA = "paper-source-figure-index-v1"
FORMULA_INDEX_SCHEMA = "paper-source-formula-index-v1"

IMAGE_REF = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")
FIGURE_LABEL = re.compile(
    r"\b(?:(?:Fig(?:ure)?\.?)|图)\s*(?P<number>\d+)(?P<suffix>[a-z](?:\s*[-–]\s*[a-z])?)?",
    re.IGNORECASE,
)
EQUATION_LABEL = re.compile(r"\b(?:Eq(?:uation)?\.?|公式)\s*\(?(?P<number>\d+[A-Za-z]?)\)?", re.IGNORECASE)
HASH_LIKE_STEM = re.compile(r"^[0-9a-f]{24,}$", re.IGNORECASE)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
LATEX_BLOCK = re.compile(
    r"\\begin\{(?:equation|align|gather|multline)\*?\}[\s\S]*?\\end\{(?:equation|align|gather|multline)\*?\}"
    r"|\\\[[\s\S]*?\\\]"
    r"|\\\([\s\S]*?\\\)"
    r"|\$\$[\s\S]*?\$\$",
    re.S,
)
INLINE_LATEX = re.compile(r"\$([^$\n]{2,})\$")


@dataclass(frozen=True)
class ImageReference:
    line_index: int
    raw_path: str
    normalized_raw_path: str
    alt_text: str


@dataclass(frozen=True)
class FigureAssignment:
    caption_text: str
    caption_line: int
    figure_match: re.Match[str]
    subfigure_suffix: str | None = None


def _posix(path: Path) -> str:
    return path.as_posix()


def _safe_slug(value: str, *, max_words: int = 5) -> str:
    value = FIGURE_LABEL.sub(" ", value, count=1)
    words = re.findall(r"[A-Za-z0-9]+", value.lower())
    stop = {
        "figure",
        "fig",
        "shows",
        "shown",
        "illustrates",
        "the",
        "and",
        "for",
        "with",
        "from",
        "diagram",
    }
    useful = [word for word in words if word not in stop and not re.fullmatch(r"[a-z]", word)]
    return "-".join(useful[:max_words]) or "evidence"


def _figure_id(match: re.Match[str]) -> str:
    number = int(match.group("number"))
    suffix = (match.group("suffix") or "").replace(" ", "").replace("–", "-").lower()
    if suffix and "-" not in suffix:
        return f"fig-{number:03d}{suffix}"
    return f"fig-{number:03d}"


def _figure_label(match: re.Match[str]) -> str:
    number = int(match.group("number"))
    suffix = (match.group("suffix") or "").replace(" ", "").replace("–", "-")
    return f"Fig. {number}{suffix}"


def _figure_id_with_suffix(match: re.Match[str], suffix: str | None = None) -> str:
    base = _figure_id(match)
    if not suffix:
        return base
    if re.search(r"[a-z]$", base):
        return base
    return f"{base}{suffix.lower()}"


def _figure_label_with_suffix(match: re.Match[str], suffix: str | None = None) -> str:
    label = _figure_label(match)
    if not suffix:
        return label
    if re.search(r"[a-z]$", label):
        return label
    return f"{label}({suffix.lower()})"


def _extract_image_refs(markdown_text: str) -> list[ImageReference]:
    refs: list[ImageReference] = []
    for index, line in enumerate(markdown_text.splitlines()):
        for match in IMAGE_REF.finditer(line):
            raw_path = match.group("path").strip()
            clean_path = raw_path.split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
            refs.append(
                ImageReference(
                    line_index=index,
                    raw_path=raw_path,
                    normalized_raw_path=clean_path,
                    alt_text=match.group("alt").strip(),
                )
            )
    return refs


def _context_window(lines: list[str], line_index: int, *, before: int = 5, after: int = 8) -> list[tuple[int, str]]:
    start = max(0, line_index - before)
    end = min(len(lines), line_index + after + 1)
    return [(index, lines[index]) for index in range(start, end)]


CAPTION_PREFIX = re.compile(
    r"^\s*(?:[-*]\s*)?(?:[*_`~\s]*)?(?:\([a-z]\)\s*)?(?:(?:Fig(?:ure)?\.?)|图)\s*\d+",
    re.IGNORECASE,
)
SUBFIGURE_TOKEN = re.compile(r"\(([a-z])\)", re.IGNORECASE)
SUBFIGURE_STANDALONE = re.compile(r"^\s*\(([a-z])\)\s*$", re.IGNORECASE)
BODY_START = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:abstract\b|abstract[—-]|i\.?\s+introduction\b|1\.?\s+introduction\b|"
    r"introduction\b|摘要\b|引言\b)",
    re.IGNORECASE,
)
SECTION_HEADING = re.compile(r"^\s*#{1,6}\s+\S+")


def _caption_match(line: str) -> re.Match[str] | None:
    if not CAPTION_PREFIX.search(line):
        return None
    return FIGURE_LABEL.search(line)


def _extract_caption_lines(lines: list[str]) -> list[tuple[int, str, re.Match[str]]]:
    captions: list[tuple[int, str, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = _caption_match(line)
        if match:
            captions.append((index, line.strip(), match))
    return captions


def _body_start_before(lines: list[str], line_index: int) -> int:
    best = 0
    for index, line in enumerate(lines[:line_index]):
        if BODY_START.search(line):
            best = index
    return best


def _image_refs_between(refs: list[ImageReference], start_line: int, end_line: int) -> list[ImageReference]:
    return [ref for ref in refs if start_line <= ref.line_index < end_line]


def _tail_figure_group(
    lines: list[str],
    refs: list[ImageReference],
    *,
    start_line: int,
    caption_line: int,
) -> list[ImageReference]:
    candidates = _image_refs_between(refs, start_line, caption_line)
    if not candidates:
        return []

    # Keep the final image block before the caption. MinerU often inserts long
    # <details> tables after each panel, so distance alone is not a reliable
    # split point; section headings and earlier caption lines are.
    group_start = candidates[0].line_index
    for index in range(candidates[-1].line_index - 1, start_line - 1, -1):
        if SECTION_HEADING.match(lines[index]) or _caption_match(lines[index]):
            group_start = index + 1
            break
    return [ref for ref in candidates if ref.line_index >= group_start]


def _head_figure_group(
    lines: list[str],
    refs: list[ImageReference],
    *,
    caption_line: int,
    next_caption_line: int | None,
) -> list[ImageReference]:
    end_line = next_caption_line if next_caption_line is not None else len(lines)
    candidates = _image_refs_between(refs, caption_line + 1, end_line)
    if not candidates:
        return []

    first_ref = candidates[0]
    for index in range(caption_line + 1, first_ref.line_index):
        line = lines[index]
        if SECTION_HEADING.match(line) or _caption_match(line):
            return []
        if line.strip():
            return []

    group: list[ImageReference] = []
    for ref in candidates:
        blocked = False
        for index in range(caption_line + 1 if not group else group[-1].line_index + 1, ref.line_index):
            line = lines[index]
            if SECTION_HEADING.match(line) or _caption_match(line):
                blocked = True
                break
        if blocked:
            break
        group.append(ref)
    return group


def _subfigure_suffix_after_ref(lines: list[str], ref: ImageReference, end_line: int) -> str | None:
    for line in lines[ref.line_index + 1 : end_line + 1]:
        standalone = SUBFIGURE_STANDALONE.match(line)
        if standalone:
            return standalone.group(1).lower()
        caption = _caption_match(line)
        if caption:
            prefix = line[: caption.start()]
            token = SUBFIGURE_TOKEN.search(prefix)
            if token:
                return token.group(1).lower()
            return None
    return None


def _caption_subfigure_tokens(caption_text: str) -> list[str]:
    tokens: list[str] = []
    for token in SUBFIGURE_TOKEN.findall(caption_text):
        normalized = token.lower()
        if normalized not in tokens:
            tokens.append(normalized)
    return tokens


def _alphabetic_suffixes(count: int) -> list[str]:
    return [chr(ord("a") + index) for index in range(count)]


def _build_figure_assignments(lines: list[str], refs: list[ImageReference]) -> dict[ImageReference, FigureAssignment]:
    assignments: dict[ImageReference, FigureAssignment] = {}
    captions = _extract_caption_lines(lines)
    previous_caption_line: int | None = None

    for offset, (caption_line, caption_text, figure_match) in enumerate(captions):
        next_caption_line = captions[offset + 1][0] if offset + 1 < len(captions) else None
        start_line = previous_caption_line + 1 if previous_caption_line is not None else _body_start_before(lines, caption_line)
        group = [ref for ref in _tail_figure_group(lines, refs, start_line=start_line, caption_line=caption_line) if ref not in assignments]
        if group:
            suffixes: list[str | None] = [None] * len(group)
            for index, ref in enumerate(group):
                next_line = group[index + 1].line_index if index + 1 < len(group) else caption_line
                suffixes[index] = _subfigure_suffix_after_ref(lines, ref, next_line)

            caption_tokens = _caption_subfigure_tokens(caption_text)
            if len(group) > 1 and any(suffix is None for suffix in suffixes):
                inferred = caption_tokens if len(caption_tokens) >= len(group) else _alphabetic_suffixes(len(group))
                suffixes = [suffix or inferred[index] for index, suffix in enumerate(suffixes)]

            for ref, suffix in zip(group, suffixes, strict=True):
                assignments[ref] = FigureAssignment(
                    caption_text=caption_text,
                    caption_line=caption_line + 1,
                    figure_match=figure_match,
                    subfigure_suffix=suffix,
                )
        else:
            head_group = [
                ref
                for ref in _head_figure_group(lines, refs, caption_line=caption_line, next_caption_line=next_caption_line)
                if ref not in assignments
            ]
            if head_group:
                suffixes: list[str | None] = [None] * len(head_group)
                caption_tokens = _caption_subfigure_tokens(caption_text)
                if len(head_group) > 1:
                    inferred = caption_tokens if len(caption_tokens) >= len(head_group) else _alphabetic_suffixes(len(head_group))
                    suffixes = inferred
                for ref, suffix in zip(head_group, suffixes, strict=True):
                    assignments[ref] = FigureAssignment(
                        caption_text=caption_text,
                        caption_line=caption_line + 1,
                        figure_match=figure_match,
                        subfigure_suffix=suffix,
                    )

        previous_caption_line = caption_line

    return assignments


def _caption_context(lines: list[str], ref: ImageReference) -> tuple[str, int | None, re.Match[str] | None]:
    candidates = _context_window(lines, ref.line_index)
    best: tuple[str, int | None, re.Match[str] | None] = ("", None, None)
    best_distance = 999
    for index, line in candidates:
        match = _caption_match(line)
        if not match:
            continue
        distance = abs(index - ref.line_index)
        # Prefer labels after the image because MinerU commonly emits image then caption.
        if index >= ref.line_index:
            distance -= 1
        if distance < best_distance:
            best = (line.strip(), index + 1, match)
            best_distance = distance
    return best


def _markdown_has_latex_near(lines: list[str], line_index: int) -> bool:
    return _extract_markdown_latex_near(lines, line_index) is not None


def _tex_has_formula(tex_path: Path | None) -> bool:
    return _extract_tex_latex(tex_path) is not None


def _extract_markdown_latex_near(lines: list[str], line_index: int) -> str | None:
    context = "\n".join(line for _, line in _context_window(lines, line_index, before=4, after=4))
    block = LATEX_BLOCK.search(context)
    if block:
        return block.group(0).strip()
    inline = INLINE_LATEX.search(context)
    if inline:
        return inline.group(1).strip()
    return None


def _extract_tex_latex(tex_path: Path | None) -> str | None:
    if not tex_path or not tex_path.exists():
        return None
    try:
        text = tex_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    block = LATEX_BLOCK.search(text)
    if block:
        return block.group(0).strip()
    inline = INLINE_LATEX.search(text)
    if inline:
        return inline.group(1).strip()
    return None


def _equation_label_near(lines: list[str], line_index: int) -> str | None:
    for _, line in _context_window(lines, line_index, before=4, after=4):
        match = EQUATION_LABEL.search(line)
        if match:
            token = match.group(0).strip()
            return token if token.startswith("公式") else f"Eq. ({match.group('number')})"
    return None


def _looks_like_formula_context(lines: list[str], ref: ImageReference, tex_path: Path | None) -> bool:
    context = "\n".join(line.lower() for _, line in _context_window(lines, ref.line_index, before=3, after=3))
    if FIGURE_LABEL.search(context):
        return False
    strong_formula_words = ["equation", "formula", "公式", "eq."]
    weak_formula_words = ["where ", "denote", "denotes"]
    has_markdown_latex = _markdown_has_latex_near(lines, ref.line_index)
    _ = tex_path
    if any(word in context for word in strong_formula_words):
        return has_markdown_latex
    return any(word in context for word in weak_formula_words) and has_markdown_latex


def _resolve_image_path(markdown_path: Path, ref: ImageReference) -> Path:
    path = Path(ref.normalized_raw_path)
    if path.is_absolute():
        return path
    return (markdown_path.parent / path).resolve()


def _unique_path(target: Path, used: set[Path]) -> Path:
    if target not in used and not target.exists():
        used.add(target)
        return target
    stem = target.stem
    suffix = target.suffix
    for index in range(2, 1000):
        candidate = target.with_name(f"{stem}-part-{index:03d}{suffix}")
        if candidate not in used and not candidate.exists():
            used.add(candidate)
            return candidate
    raise RuntimeError(f"could not choose unique normalized image path for {target}")


def _relative_image_path(markdown_path: Path, image_path: Path) -> str:
    try:
        return _posix(image_path.resolve().relative_to(markdown_path.parent.resolve()))
    except ValueError:
        return _posix(image_path)


def _replace_image_ref(line: str, old_raw_path: str, new_raw_path: str) -> str:
    return line.replace(f"]({old_raw_path})", f"]({new_raw_path})", 1)


def _remove_image_ref(line: str, old_raw_path: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return "" if match.group("path").strip() == old_raw_path else match.group(0)

    return IMAGE_REF.sub(replace, line).strip()


def _remove_image_refs_from_text(text: str, old_raw_paths: set[str]) -> str:
    updated_lines: list[str] = []
    for line in text.splitlines():
        updated_line = line
        for old_raw_path in old_raw_paths:
            updated_line = _remove_image_ref(updated_line, old_raw_path)
        updated_lines.append(updated_line)
    return _normalize_markdown_output("\n".join(updated_lines), final_newline=text.endswith("\n"))


def _normalize_markdown_output(text: str, *, final_newline: bool | None = None) -> str:
    keep_final_newline = text.endswith("\n") if final_newline is None else final_newline
    normalized = "\n".join(line.rstrip(" \t") for line in text.splitlines())
    return normalized + ("\n" if keep_final_newline else "")


def _hash_if_file(path: Path) -> str | None:
    return file_sha256(path) if path.is_file() else None


def _record_output_hashes(paths: list[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            hashes[path.name] = file_sha256(path)
    return hashes


def normalize_mineru_assets(paper_root: Path, *, execute: bool = False) -> dict[str, Any]:
    """Normalize MinerU image assets for a raw Paper Source bundle.

    The function is intentionally conservative. It only renames Markdown-referenced
    image files and only assigns a `fig-*` name when nearby text contains a figure
    label. Ambiguous references stay as `unmapped-*`.
    """

    started_at = utc_now()
    paper_root = paper_root.resolve()
    mineru_dir = paper_root / "mineru"
    markdown_path = resolve_mineru_markdown_path(paper_root)
    tex_path = mineru_dir / "paper.tex"
    manifest_path = mineru_dir / "mineru-manifest.json"
    if not markdown_path.exists():
        raise FileNotFoundError(f"missing MinerU Markdown: {markdown_path}")

    markdown_text = markdown_path.read_text(encoding="utf-8")
    lines = markdown_text.splitlines()
    refs = _extract_image_refs(markdown_text)
    figure_assignments = _build_figure_assignments(lines, refs)
    input_paths = [markdown_path, tex_path, manifest_path]
    input_hashes = {path.name: file_sha256(path) for path in input_paths if path.exists()}

    figure_records: list[dict[str, Any]] = []
    formula_records: list[dict[str, Any]] = []
    rename_plan: list[dict[str, Any]] = []
    dropped_formula_images: list[dict[str, Any]] = []
    warnings: list[str] = []
    rewritten_lines = list(lines)
    used_targets: set[Path] = set()
    markdown_replacements: dict[str, str] = {}
    markdown_removals: set[str] = set()

    for ordinal, ref in enumerate(refs, start=1):
        source_path = _resolve_image_path(markdown_path, ref)
        old_relative = _relative_image_path(markdown_path, source_path)
        if not source_path.is_file():
            warnings.append(f"missing image referenced by Markdown: {ref.normalized_raw_path}")
            figure_records.append(
                {
                    "figure_id": f"missing-{ordinal:03d}",
                    "original_label": None,
                    "normalized_path": old_relative,
                    "old_path": old_relative,
                    "caption_text": "",
                    "caption_locator": None,
                    "markdown_image_locator": f"{markdown_path.name}:L{ref.line_index + 1}",
                    "sha256": None,
                    "status": "missing",
                    "warnings": ["image file does not exist"],
                }
            )
            continue

        if source_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        if _looks_like_formula_context(lines, ref, tex_path):
            status = "dropped" if execute else "would_drop"
            markdown_latex = _extract_markdown_latex_near(lines, ref.line_index)
            tex_latex = _extract_tex_latex(tex_path)
            formula_record = {
                "equation_label": _equation_label_near(lines, ref.line_index),
                "latex": markdown_latex or tex_latex,
                "source": "mineru-markdown" if markdown_latex else "mineru-tex",
                "markdown_locator": f"{markdown_path.name}:L{ref.line_index + 1}",
                "tex_locator": "paper.tex" if has_nonempty_mineru_tex(paper_root) else None,
                "dropped_image_refs": [old_relative],
                "confidence": "high" if markdown_latex else "medium",
                "warnings": ["formula-like image has LaTeX evidence and is excluded from evidence figures"],
            }
            formula_records.append(formula_record)
            dropped = {
                "old_path": old_relative,
                "target_path": None,
                "sha256": file_sha256(source_path),
                "status": status,
            }
            dropped_formula_images.append(dropped)
            if execute:
                source_path.unlink()
                markdown_removals.add(ref.raw_path)
                rewritten_lines[ref.line_index] = _remove_image_ref(rewritten_lines[ref.line_index], ref.raw_path)
            continue

        assignment = figure_assignments.get(ref)
        if assignment:
            caption_text = assignment.caption_text
            caption_line = assignment.caption_line
            figure_match = assignment.figure_match
            figure_id = _figure_id_with_suffix(figure_match, assignment.subfigure_suffix)
            original_label = _figure_label_with_suffix(figure_match, assignment.subfigure_suffix)
            name_suffix = _safe_slug(caption_text)
            status = "mapped"
        else:
            caption_text, caption_line, figure_match = _caption_context(lines, ref)
            if figure_match:
                figure_id = _figure_id(figure_match)
                original_label = _figure_label(figure_match)
                name_suffix = _safe_slug(caption_text)
                status = "mapped"
            else:
                short_hash = file_sha256(source_path)[:12]
                figure_id = f"unmapped-{ordinal:03d}"
                original_label = None
                name_suffix = short_hash
                status = "unmapped"
                warnings.append(f"could not map image to figure label: {old_relative}")

        if HASH_LIKE_STEM.match(source_path.stem) or figure_match:
            target_name = f"{figure_id}-{name_suffix}{source_path.suffix.lower()}"
            target_candidate = source_path.parent / target_name
            if target_candidate.resolve() == source_path.resolve():
                target_path = source_path
                used_targets.add(target_path)
            else:
                target_path = _unique_path(target_candidate, used_targets)
        else:
            target_path = source_path
            used_targets.add(target_path)

        new_relative = _relative_image_path(markdown_path, target_path)
        record_warnings = [] if figure_match else ["no nearby figure label found"]
        figure_records.append(
            {
                "figure_id": figure_id,
                "original_label": original_label,
                "normalized_path": new_relative,
                "old_path": old_relative,
                "caption_text": caption_text,
                "caption_locator": f"{markdown_path.name}:L{caption_line}" if caption_line else None,
                "markdown_image_locator": f"{markdown_path.name}:L{ref.line_index + 1}",
                "sha256": file_sha256(source_path),
                "status": status,
                "warnings": record_warnings,
            }
        )
        if target_path != source_path:
            rename_plan.append(
                {
                    "old_path": old_relative,
                    "new_path": new_relative,
                    "figure_id": figure_id,
                    "original_label": original_label,
                    "status": "planned" if not execute else "renamed",
                }
            )
            if execute:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source_path), str(target_path))
                markdown_replacements[ref.raw_path] = new_relative
                rewritten_lines[ref.line_index] = _replace_image_ref(
                    rewritten_lines[ref.line_index],
                    ref.raw_path,
                    new_relative,
                )

    rewritten_files: list[str] = []
    if execute and rewritten_lines != lines:
        write_text_atomic(
            markdown_path,
            _normalize_markdown_output("\n".join(rewritten_lines), final_newline=markdown_text.endswith("\n")),
        )
        rewritten_files.append(markdown_path.relative_to(paper_root).as_posix())
    if execute and (markdown_replacements or markdown_removals):
        for sibling_markdown in sorted(path for path in mineru_dir.glob("*.md") if path.resolve() != markdown_path):
            try:
                sibling_text = sibling_markdown.read_text(encoding="utf-8")
            except OSError:
                continue
            updated_text = sibling_text
            for old_ref, new_ref in markdown_replacements.items():
                updated_text = updated_text.replace(f"]({old_ref})", f"]({new_ref})")
            if markdown_removals:
                updated_text = _remove_image_refs_from_text(updated_text, markdown_removals)
            if updated_text != sibling_text:
                write_text_atomic(
                    sibling_markdown,
                    _normalize_markdown_output(updated_text, final_newline=sibling_text.endswith("\n")),
                )
                rewritten_files.append(sibling_markdown.relative_to(paper_root).as_posix())

    figure_index = {
        "schema_version": FIGURE_INDEX_SCHEMA,
        "paper_slug": paper_root.name,
        "created_at": started_at,
        "updated_at": utc_now(),
        "source_markdown": markdown_path.relative_to(paper_root).as_posix(),
        "figures": figure_records,
        "warnings": warnings,
    }
    formula_index = {
        "schema_version": FORMULA_INDEX_SCHEMA,
        "paper_slug": paper_root.name,
        "created_at": started_at,
        "updated_at": utc_now(),
        "source_markdown": markdown_path.relative_to(paper_root).as_posix(),
        "source_tex": tex_path.relative_to(paper_root).as_posix() if tex_path.exists() else None,
        "formulas": formula_records,
        "warnings": [item for record in formula_records for item in record.get("warnings", [])],
    }

    if execute:
        write_json_atomic(paper_root / "figure-index.json", figure_index)
        write_json_atomic(paper_root / "formula-index.json", formula_index)

    record = {
        "schema_version": SCHEMA_VERSION,
        "paper_slug": paper_root.name,
        "mode": "execute" if execute else "dry-run",
        "started_at": started_at,
        "finished_at": utc_now(),
        "input_hashes": input_hashes,
        "rename_plan": rename_plan,
        "rewritten_files": rewritten_files,
        "dropped_formula_images": dropped_formula_images,
        "needs_review": [
            figure for figure in figure_records if figure.get("status") in {"unmapped", "missing", "needs_review"}
        ],
        "warnings": warnings,
        "figure_index": figure_index,
        "formula_index": formula_index,
        "output_hashes": {},
    }

    if execute:
        record_path = paper_root / "asset-normalization-record.json"
        write_json_atomic(record_path, record)
        record["output_hashes"] = _record_output_hashes(
            [markdown_path, paper_root / "figure-index.json", paper_root / "formula-index.json"]
        )
        write_json_atomic(record_path, record)

    return record


def count_preserved_images(paper_root: Path) -> int:
    images_dir = paper_root / "mineru" / "images"
    if not images_dir.exists():
        return 0
    return sum(
        1
        for path in images_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and "formula-review" not in path.parts
    )
