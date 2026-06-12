from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORMAL_ROOTS = (
    "references",
    "concepts",
    "derivations",
    "experiments",
    "synthesis",
    "reports",
    "opportunities",
)

FIGURE_HEADING = re.compile(r"(?:\*\*)?原文\s+Fig\.?\s*(?P<number>\d+)", re.IGNORECASE)
FIGURE_ANCHOR = re.compile(r'<a\s+id="F(?P<number>\d+)"\s*></a>')
FIGURE_LABEL = re.compile(r"Fig\.\s*(?P<number>\d+)(?:\((?P<suffix>[a-z])\))?", re.IGNORECASE)
HTML_IMG = re.compile(r'<img\s+[^>]*src="(?P<src>[^"]+)"[^>]*>')
MARKDOWN_IMG = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)")
SOURCE_LINE = re.compile(r"^\*\*Source:\*\*")
FRONTMATTER_UPDATED = re.compile(r"(?m)^updated:\s*\d{4}-\d{2}-\d{2}\s*$")


@dataclass(frozen=True)
class FigureEntry:
    figure_id: str
    original_label: str
    normalized_path: str
    old_path: str = ""

    @property
    def file_name(self) -> str:
        return Path(self.normalized_path).name


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _raw_root(vault: Path, slug: str) -> Path:
    for root_name in ("_paper_source", "_epi"):
        candidate = vault / root_name / "raw" / slug
        if candidate.exists():
            return candidate
    return vault / "_paper_source" / "raw" / slug


def _staging_root(vault: Path, slug: str) -> Path:
    for root_name in ("_paper_source", "_epi"):
        candidate = vault / root_name / "staging" / "papers" / slug
        if candidate.exists():
            return candidate
    return vault / "_paper_source" / "staging" / "papers" / slug


def _formal_pages(vault: Path) -> list[Path]:
    pages: list[Path] = []
    for root in FORMAL_ROOTS:
        root_path = vault / root
        if root_path.exists():
            pages.extend(sorted(root_path.rglob("*.md")))
    return pages


def _snapshot_formal_pages(vault: Path, snapshot_name: str | None, *, execute: bool) -> str | None:
    if not execute:
        return None
    name = snapshot_name or f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-pre-rewrite"
    snapshot = vault / "_paper_source" / "meta" / "formal-page-snapshots" / name
    if (snapshot / "manifest.json").exists():
        return snapshot.relative_to(vault).as_posix() + "/"

    records: list[dict[str, Any]] = []
    for page in _formal_pages(vault):
        relative = page.relative_to(vault)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(page, destination)
        records.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(page),
                "bytes": page.stat().st_size,
            }
        )
    _write_json(
        snapshot / "manifest.json",
        {
            "schema_version": "paper-wiki-formal-page-snapshot-v1",
            "created_at": _utc_now(),
            "vault": str(vault),
            "reason": "pre-rewrite formal page snapshot before figure maintenance",
            "roots": list(FORMAL_ROOTS),
            "file_count": len(records),
            "files": records,
        },
    )
    return snapshot.relative_to(vault).as_posix() + "/"


def _figure_number(label: str | None) -> int | None:
    if not label:
        return None
    match = FIGURE_LABEL.search(label)
    return int(match.group("number")) if match else None


def _figure_entries(raw_root: Path) -> dict[int, list[FigureEntry]]:
    index_path = raw_root / "figure-index.json"
    if not index_path.exists():
        return {}
    payload = _read_json(index_path)
    entries: dict[int, list[FigureEntry]] = {}
    for item in payload.get("figures", []):
        if item.get("status") != "mapped":
            continue
        number = _figure_number(item.get("original_label"))
        if number is None:
            continue
        entries.setdefault(number, []).append(
            FigureEntry(
                figure_id=str(item.get("figure_id") or ""),
                original_label=str(item.get("original_label") or ""),
                normalized_path=str(item.get("normalized_path") or ""),
                old_path=str(item.get("old_path") or ""),
            )
        )
    for number in entries:
        entries[number].sort(key=lambda entry: entry.figure_id)
    return entries


def _dropped_formula_image_names(raw_root: Path) -> set[str]:
    index_path = raw_root / "formula-index.json"
    if not index_path.exists():
        return set()
    payload = _read_json(index_path)
    names: set[str] = set()
    for item in payload.get("formulas", []):
        for ref in item.get("dropped_image_refs", []) or []:
            names.add(Path(str(ref).replace("\\", "/")).name)
    return names


def _target_pages(vault: Path, slug: str, explicit_pages: list[str]) -> list[Path]:
    if explicit_pages:
        return [(vault / page).resolve() if not Path(page).is_absolute() else Path(page).resolve() for page in explicit_pages]
    needle = f"/{slug}/"
    matches: list[Path] = []
    for page in _formal_pages(vault):
        try:
            text = page.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if slug in text or needle in text:
            matches.append(page)
    return matches


def _src_basename(line: str) -> str | None:
    match = HTML_IMG.search(line) or MARKDOWN_IMG.search(line)
    if not match:
        return None
    src = match.group("src").replace("\\", "/").split("?", 1)[0].split("#", 1)[0]
    if src.startswith("file:///"):
        src = src.replace("file:///", "", 1)
    return Path(src).name


def _src_value(line: str) -> str | None:
    match = HTML_IMG.search(line) or MARKDOWN_IMG.search(line)
    if not match:
        return None
    return match.group("src").replace("\\", "/").split("?", 1)[0].split("#", 1)[0]


def _entry_image_names(entries_by_number: dict[int, list[FigureEntry]], dropped_formula_names: set[str]) -> set[str]:
    names = set(dropped_formula_names)
    for entries in entries_by_number.values():
        for entry in entries:
            if entry.normalized_path:
                names.add(Path(entry.normalized_path.replace("\\", "/")).name)
            if entry.old_path:
                names.add(Path(entry.old_path.replace("\\", "/")).name)
    return names


def _figure_path_replacements(entries_by_number: dict[int, list[FigureEntry]]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for entries in entries_by_number.values():
        for entry in entries:
            if not entry.old_path or not entry.normalized_path:
                continue
            old_name = Path(entry.old_path.replace("\\", "/")).name
            replacements[old_name] = entry.normalized_path
    return replacements


def _block_image_basenames(block: list[str], image_indexes: list[int]) -> set[str]:
    names = {_src_basename(block[index]) for index in image_indexes}
    names.discard(None)
    return {name for name in names if name}


def _block_uses_raw_bundle(
    block: list[str],
    *,
    slug: str,
    image_indexes: list[int],
    allowed_image_names: set[str],
) -> bool:
    basenames = _block_image_basenames(block, image_indexes)
    if basenames & allowed_image_names:
        return True
    slug_marker = f"/{slug}/mineru/images/"
    for index in image_indexes:
        src = _src_value(block[index])
        if src and slug_marker in src:
            return True
    return False


def _replace_src(line: str, new_src: str) -> str:
    html = HTML_IMG.search(line)
    if html:
        start, end = html.span("src")
        return line[:start] + new_src + line[end:]
    markdown = MARKDOWN_IMG.search(line)
    if markdown:
        start, end = markdown.span("src")
        return line[:start] + new_src + line[end:]
    return line


def _replace_stale_image_paths(
    lines: list[str],
    *,
    page: Path,
    raw_root: Path,
    slug: str,
    replacements: dict[str, str],
) -> tuple[list[str], list[dict[str, Any]]]:
    if not replacements:
        return lines, []
    updated = list(lines)
    actions: list[dict[str, Any]] = []
    slug_marker = f"/{slug}/mineru/images/"
    for index, line in enumerate(lines):
        src = _src_value(line)
        if not src or slug_marker not in src:
            continue
        basename = Path(src).name
        normalized_path = replacements.get(basename)
        if not normalized_path:
            continue
        new_src = _relative_image_src(page, raw_root, normalized_path)
        updated[index] = _replace_src(line, new_src)
        if updated[index] != line:
            actions.append(
                {
                    "line": index + 1,
                    "action": "replace_stale_image_path",
                    "old_image": basename,
                    "new_image": Path(normalized_path).name,
                }
            )
    return updated, actions


def _image_line(line: str) -> bool:
    stripped = line.strip()
    return bool(HTML_IMG.search(stripped) or MARKDOWN_IMG.search(stripped) or stripped in {"<p>", "</p>"})


def _first_image_group(block: list[str], image_indexes: list[int]) -> list[int]:
    if not image_indexes:
        return []
    group = [image_indexes[0]]
    previous = image_indexes[0]
    for index in image_indexes[1:]:
        between = block[previous + 1 : index]
        if all(not line.strip() or _image_line(line) for line in between):
            group.append(index)
            previous = index
            continue
        break
    return group


def _relative_image_src(page: Path, raw_root: Path, normalized_path: str) -> str:
    target = raw_root / "mineru" / normalized_path
    return Path(os.path.relpath(target, start=page.parent)).as_posix()


def _replacement_image_lines(page: Path, raw_root: Path, entries: list[FigureEntry]) -> list[str]:
    if len(entries) == 1:
        entry = entries[0]
        src = _relative_image_src(page, raw_root, entry.normalized_path)
        return [f'<img src="{src}" alt="{entry.original_label}">']
    lines = ["<p>"]
    for entry in entries:
        src = _relative_image_src(page, raw_root, entry.normalized_path)
        lines.append(f'<img src="{src}" alt="{entry.original_label}" width="32%">')
    lines.append("</p>")
    return lines


def _source_line_for(number: int, entries: list[FigureEntry]) -> str:
    if len(entries) == 1:
        entry = entries[0]
        return f"**Source:** MinerU Markdown Fig. {number} caption；`figure-index.json` asset `{entry.file_name}`。"
    first = entries[0].figure_id
    last = entries[-1].figure_id
    return f"**Source:** MinerU Markdown Fig. {number} caption；`figure-index.json` assets `{first}` 至 `{last}`。"


def _no_asset_source_line(number: int) -> str:
    return (
        f"**Source:** MinerU Markdown Fig. {number} caption；`figure-index.json` "
        f"未生成 `fig-{number:03d}` 图片资产；旧截图若存在则按 `formula-index.json` 或 source Markdown 处理。"
    )


def _block_ranges(lines: list[str]) -> list[tuple[int, int, int]]:
    starts: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        anchor = FIGURE_ANCHOR.search(line)
        heading = FIGURE_HEADING.search(line)
        match = anchor or heading
        if match:
            starts.append((index, int(match.group("number"))))
    ranges: list[tuple[int, int, int]] = []
    for offset, (start, number) in enumerate(starts):
        end = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        ranges.append((start, end, number))
    return ranges


def _patch_evidence_block(
    block: list[str],
    *,
    image_indexes: list[int],
    replacement: list[str],
    source_line: str | None,
) -> list[str]:
    first_image = image_indexes[0]
    last_image = image_indexes[-1]
    removed_count = last_image - first_image + 1
    patched = block[:first_image] + replacement + block[last_image + 1 :]

    if source_line is None:
        return patched

    source_indexes = [index for index, line in enumerate(block) if SOURCE_LINE.match(line.strip())]
    if not source_indexes:
        return patched

    source_index = source_indexes[0]
    if source_index < first_image:
        adjusted_source_index = source_index
    elif source_index > last_image:
        adjusted_source_index = source_index + len(replacement) - removed_count
    else:
        adjusted_source_index = first_image + len(replacement)
        patched.insert(adjusted_source_index, source_line)
        return patched

    patched[adjusted_source_index] = source_line
    return patched


def repair_page(
    page: Path,
    *,
    vault: Path,
    slug: str,
    raw_root: Path,
    entries_by_number: dict[int, list[FigureEntry]],
    dropped_formula_names: set[str],
    allowed_image_names: set[str] | None = None,
    path_replacements: dict[str, str] | None = None,
    execute: bool,
) -> dict[str, Any]:
    original = page.read_text(encoding="utf-8")
    lines = original.splitlines()
    actions: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []
    allowed_image_names = allowed_image_names or _entry_image_names(entries_by_number, dropped_formula_names)
    path_replacements = path_replacements or _figure_path_replacements(entries_by_number)

    for start, end, number in reversed(_block_ranges(lines)):
        block = lines[start:end]
        image_indexes = [offset for offset, line in enumerate(block) if _image_line(line)]
        if not image_indexes:
            continue
        image_indexes = _first_image_group(block, image_indexes)
        if not image_indexes:
            continue
        if not _block_uses_raw_bundle(
            block,
            slug=slug,
            image_indexes=image_indexes,
            allowed_image_names=allowed_image_names,
        ):
            continue

        entries = entries_by_number.get(number, [])

        if entries:
            replacement = _replacement_image_lines(page, raw_root, entries)
            lines[start:end] = _patch_evidence_block(
                block,
                image_indexes=image_indexes,
                replacement=replacement,
                source_line=_source_line_for(number, entries),
            )
            actions.append({"figure": f"Fig. {number}", "action": "replace_images", "count": len(entries)})
            continue

        basenames = _block_image_basenames(block, image_indexes)
        if basenames and basenames.issubset(dropped_formula_names | {""}):
            lines[start:end] = _patch_evidence_block(
                block,
                image_indexes=image_indexes,
                replacement=[],
                source_line=_no_asset_source_line(number),
            )
            actions.append({"figure": f"Fig. {number}", "action": "remove_formula_image", "count": len(basenames)})
            continue

        needs_review.append(
            {
                "page": page.relative_to(vault).as_posix(),
                "figure": f"Fig. {number}",
                "reason": "no matching figure-index entry for existing image block",
                "image_names": sorted(name for name in basenames if name),
            }
        )

    lines, path_actions = _replace_stale_image_paths(
        lines,
        page=page,
        raw_root=raw_root,
        slug=slug,
        replacements=path_replacements,
    )
    actions.extend(path_actions)

    updated = "\n".join(lines)
    changed = updated.rstrip() != original.rstrip()
    if changed:
        updated = FRONTMATTER_UPDATED.sub(f"updated: {_today()}", updated, count=1)
        changed = updated.rstrip() != original.rstrip()
    if execute and changed:
        _write_text(page, updated)
    return {
        "page": page.relative_to(vault).as_posix(),
        "changed": changed,
        "actions": actions,
        "needs_review": needs_review,
    }


def _file_record(artifact: str, path: Path) -> dict[str, Any]:
    return {
        "artifact": artifact,
        "status": "reviewed",
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _page_record(page: Path, vault: Path) -> dict[str, Any]:
    return {
        "relative_path": page.relative_to(vault).as_posix(),
        "sha256": _sha256(page),
        "size_bytes": page.stat().st_size,
    }


def _refresh_review_artifacts(review: dict[str, Any], raw_root: Path, slug: str) -> None:
    updated: list[dict[str, Any]] = []
    seen = set()
    main_md = raw_root / "mineru" / f"{slug}.md"
    paper_md = raw_root / "mineru" / "paper.md"
    images_dir = raw_root / "mineru" / "images"
    for artifact in review.get("reviewed_artifacts", []) or []:
        name = artifact.get("artifact")
        if name == f"mineru/{slug}.md" and main_md.exists():
            updated.append(_file_record(name, main_md))
            seen.add(name)
        elif name == "mineru/paper.md" and paper_md.exists():
            updated.append(_file_record(name, paper_md))
            seen.add(name)
        elif name == "mineru/images/*" and images_dir.exists():
            files = [
                {
                    "relative_path": f"mineru/images/{path.name}",
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in sorted(images_dir.iterdir())
                if path.is_file()
            ]
            artifact["file_count"] = len(files)
            artifact["files"] = files
            artifact["summary"] = (
                "MinerU image assets were normalized by figure-index.json names; "
                "formula-like screenshots are recorded in formula-index.json and excluded from evidence figures."
            )
            updated.append(artifact)
            seen.add(name)
        elif name in {"figure-index.json", "formula-index.json", "asset-normalization-record.json"}:
            continue
        else:
            updated.append(artifact)
    if main_md.exists() and f"mineru/{slug}.md" not in seen:
        updated.append(_file_record(f"mineru/{slug}.md", main_md))
    if paper_md.exists() and "mineru/paper.md" not in seen:
        updated.append(_file_record("mineru/paper.md", paper_md))
    for name in ("figure-index.json", "formula-index.json", "asset-normalization-record.json"):
        path = raw_root / name
        if path.exists():
            updated.append(_file_record(name, path))
    review["reviewed_artifacts"] = updated


def _refresh_page_hashes(payload: Any, page_records: dict[str, dict[str, Any]]) -> None:
    if isinstance(payload, dict):
        relative = payload.get("relative_path") or payload.get("page_path")
        if isinstance(relative, str) and relative in page_records:
            record = page_records[relative]
            payload["sha256"] = record["sha256"]
            payload["size_bytes"] = record["size_bytes"]
        for value in payload.values():
            _refresh_page_hashes(value, page_records)
    elif isinstance(payload, list):
        for value in payload:
            _refresh_page_hashes(value, page_records)


def refresh_sidecars(
    *,
    vault: Path,
    slug: str,
    raw_root: Path,
    changed_pages: list[Path],
    snapshot: str | None,
    execute: bool,
) -> dict[str, Any]:
    if not execute or not changed_pages:
        return {"changed": False}
    staging = _staging_root(vault, slug)
    review_path = staging / "final-source-review.json"
    request_path = staging / "paper-wiki-record-request.json"
    legacy_request_path = staging / "prw-record-request.json"
    if not review_path.exists():
        return {"changed": False, "warning": "missing final-source-review.json"}

    page_records = {record["relative_path"]: record for record in (_page_record(page, vault) for page in changed_pages)}
    review = _read_json(review_path)
    review["reviewed_at"] = _utc_now()
    _refresh_review_artifacts(review, raw_root, slug)
    _refresh_page_hashes(review, page_records)
    review["figure_maintenance_repair"] = {
        "status": "reviewed",
        "updated_at": _utc_now(),
        "snapshot": snapshot,
        "asset_normalization_record": f"{raw_root.relative_to(vault).as_posix()}/asset-normalization-record.json",
        "summary": "Figure evidence links were refreshed from figure-index.json/formula-index.json.",
    }
    _write_json(review_path, review)
    review_hash = _sha256(review_path)

    request_changed = False
    legacy_request_changed = False
    if request_path.exists():
        request = _read_json(request_path)
        _refresh_page_hashes(request, page_records)
        task = request.setdefault("paper_wiki_task", {})
        task["route"] = "maintain_figures"
        task["snapshot"] = snapshot
        task["refreshed_at"] = _utc_now()
        task["summary"] = (
            "Paper Wiki refreshed normalized raw figure evidence links; "
            "Paper Source can consume this request with record-wiki-ingest if recording is desired."
        )
        request.setdefault("final_source_review", {})["sha256"] = review_hash
        _write_json(request_path, request)
        request_changed = True
    if legacy_request_path.exists():
        legacy_request = _read_json(legacy_request_path)
        _refresh_page_hashes(legacy_request, page_records)
        task = legacy_request.setdefault("prw_task", {})
        task["route"] = "maintain_figures"
        task["snapshot"] = snapshot
        task["refreshed_at"] = _utc_now()
        task["summary"] = (
            "Legacy PRW request refreshed during figure maintenance; regenerate the canonical "
            "paper-wiki-record-request.json when the staging bundle is migrated."
        )
        legacy_request.setdefault("final_source_review", {})["sha256"] = review_hash
        _write_json(legacy_request_path, legacy_request)
        legacy_request_changed = True

    return {
        "changed": True,
        "final_source_review": str(review_path),
        "final_source_review_sha256": review_hash,
        "paper_wiki_record_request_changed": request_changed,
        "legacy_prw_record_request_changed": legacy_request_changed,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault = args.vault.resolve()
    raw_root = _raw_root(vault, args.slug)
    if not raw_root.exists():
        raise FileNotFoundError(f"missing raw paper root: {raw_root}")
    entries_by_number = _figure_entries(raw_root)
    dropped_formula_names = _dropped_formula_image_names(raw_root)
    allowed_image_names = _entry_image_names(entries_by_number, dropped_formula_names)
    path_replacements = _figure_path_replacements(entries_by_number)
    pages = _target_pages(vault, args.slug, args.page or [])
    snapshot = _snapshot_formal_pages(vault, args.snapshot_name, execute=args.execute)

    page_results = [
        repair_page(
            page,
            vault=vault,
            slug=args.slug,
            raw_root=raw_root,
            entries_by_number=entries_by_number,
            dropped_formula_names=dropped_formula_names,
            allowed_image_names=allowed_image_names,
            path_replacements=path_replacements,
            execute=args.execute,
        )
        for page in pages
    ]
    changed_pages = [vault / result["page"] for result in page_results if result["changed"]]
    sidecars = refresh_sidecars(
        vault=vault,
        slug=args.slug,
        raw_root=raw_root,
        changed_pages=changed_pages,
        snapshot=snapshot,
        execute=args.execute,
    )
    return {
        "schema_version": "paper-wiki-maintain-figures-v1",
        "mode": "execute" if args.execute else "dry-run",
        "paper_slug": args.slug,
        "snapshot": snapshot,
        "pages_scanned": [page.relative_to(vault).as_posix() for page in pages],
        "pages_changed": [page.relative_to(vault).as_posix() for page in changed_pages],
        "page_results": page_results,
        "sidecars": sidecars,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--page", action="append", default=[])
    parser.add_argument("--snapshot-name", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['mode']}: {len(result['pages_changed'])} page(s) changed")
        for page in result["pages_changed"]:
            print(f"- {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
