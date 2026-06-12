from __future__ import annotations

import argparse
import hashlib
import json
import re
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

FRONTMATTER = re.compile(r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n?", re.DOTALL)
WIKILINK = re.compile(r"\[\[(?P<body>[^\]\n]+)\]\]")
ENCODED_RAW_SLUG = re.compile(r"_(?:paper_source|epi)%2Fraw%2F(?P<slug>[^%/]+)%2Fpaper\.pdf", re.IGNORECASE)
PLAIN_RAW_SLUG = re.compile(r"(?:_paper_source|_epi)/raw/(?P<slug>[^/\s`'\"]+)/paper\.pdf", re.IGNORECASE)
PAPER_SOURCE_PDF_MARKDOWN_LINK = re.compile(
    r"\[(?P<label>[^\]\n]+)\]\((?P<uri>obsidian://open\?[^)\n]*file=_paper_source%2Fraw%2F(?P<slug>[^%/)]+)%2Fpaper\.pdf(?:[&#][^)\n]*)?)\)",
    re.IGNORECASE,
)
ANY_PDF_MARKDOWN_LINK = re.compile(
    r"\[(?P<label>[^\]\n]+)\]\((?P<uri>obsidian://open\?[^)\n]*file=_(?:paper_source|epi)%2Fraw%2F(?P<slug>[^%/)]+)%2Fpaper\.pdf(?:[&#][^)\n]*)?)\)",
    re.IGNORECASE,
)

REPLACEMENTS = (
    ("_epi%2Fraw%2F", "_paper_source%2Fraw%2F"),
    ("_epi%2Fstaging%2F", "_paper_source%2Fstaging%2F"),
    ("_epi%2Fmeta%2Fformal-page-snapshots%2F", "_paper_source%2Fmeta%2Fformal-page-snapshots%2F"),
    ("../_epi/raw/", "../_paper_source/raw/"),
    ("../_epi/staging/", "../_paper_source/staging/"),
    ("_epi/raw/", "_paper_source/raw/"),
    ("_epi/staging/", "_paper_source/staging/"),
    ("_epi/meta/formal-page-snapshots/", "_paper_source/meta/formal-page-snapshots/"),
    ("EPI source bundle", "Paper Source source bundle"),
    ("EPI metadata", "Paper Source metadata"),
)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _formal_pages(vault: Path) -> list[Path]:
    pages: list[Path] = []
    for root in FORMAL_ROOTS:
        root_path = vault / root
        if root_path.exists():
            pages.extend(sorted(root_path.rglob("*.md")))
    return pages


def _detach_wikilinks(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        body = match.group("body").strip()
        target, _, alias = body.partition("|")
        return (alias or target).strip()

    return WIKILINK.sub(replace, text)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _snapshot_formal_pages(vault: Path, snapshot_name: str | None, *, execute: bool) -> str | None:
    if not execute:
        return None
    name = snapshot_name or f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-pre-governance-migration"
    snapshot = vault / "_paper_source" / "meta" / "formal-page-snapshots" / name
    manifest = snapshot / "manifest.json"
    if manifest.exists():
        return snapshot.relative_to(vault).as_posix() + "/"

    records: list[dict[str, Any]] = []
    for page in _formal_pages(vault):
        relative = page.relative_to(vault)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        original_text = page.read_text(encoding="utf-8")
        snapshot_text = _detach_wikilinks(original_text)
        destination.write_text(snapshot_text, encoding="utf-8")
        records.append(
            {
                "path": relative.as_posix(),
                "snapshot_path": destination.relative_to(vault).as_posix(),
                "original_bytes": len(original_text.encode("utf-8")),
                "snapshot_bytes": len(snapshot_text.encode("utf-8")),
                "original_sha256": _sha256_text(original_text),
                "snapshot_sha256": _sha256_text(snapshot_text),
                "wikilinks_detached": original_text != snapshot_text,
            }
        )
    _write_json(
        manifest,
        {
            "schema_version": "paper-wiki-formal-page-snapshot-v1",
            "created_at": _utc_now(),
            "vault": str(vault),
            "reason": "pre-governance formal page migration",
            "file_count": len(records),
            "files": records,
        },
    )
    return snapshot.relative_to(vault).as_posix() + "/"


def _split_inline_list(value: str) -> list[str]:
    text = value.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return [text]
    inner = text[1:-1].strip()
    if not inner:
        return []
    parts: list[str] = []
    token: list[str] = []
    quote: str | None = None
    escaped = False
    for char in inner:
        if quote:
            if escaped:
                token.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
                continue
            token.append(char)
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == ",":
            part = "".join(token).strip()
            if part:
                parts.append(part)
            token = []
            continue
        token.append(char)
    final = "".join(token).strip()
    if final:
        parts.append(final)
    return parts


def _strip_yaml_scalar(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _frontmatter_title(lines: list[str]) -> str | None:
    for line in lines:
        if line.strip() == "---":
            continue
        if line.startswith("title:"):
            _, _, value = line.partition(":")
            return _strip_yaml_scalar(value)
    return None


def _source_title_map(vault: Path) -> dict[str, str]:
    titles: dict[str, str] = {}
    for root_name in ("_paper_source", "_epi"):
        raw_root = vault / root_name / "raw"
        if not raw_root.exists():
            continue
        for metadata_path in raw_root.glob("*/metadata.json"):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            title = str(metadata.get("title") or "").strip()
            if title:
                titles[metadata_path.parent.name] = title
    return titles


def _fallback_title_for_slug(slug: str, *, page_title: str | None, source_titles: dict[str, str]) -> str:
    title = source_titles.get(slug)
    if title:
        return title
    if page_title:
        return page_title
    return slug


def _source_slug(entry: str) -> str:
    for pattern in (ENCODED_RAW_SLUG, PLAIN_RAW_SLUG):
        match = pattern.search(entry)
        if match:
            return match.group("slug")
    link = ANY_PDF_MARKDOWN_LINK.search(entry)
    if link:
        return link.group("slug")
    cleaned = _strip_yaml_scalar(entry)
    return cleaned


def _source_entry_title(entry: str) -> str | None:
    link = ANY_PDF_MARKDOWN_LINK.search(entry)
    if not link:
        return None
    label = link.group("label").strip()
    if not label or label == "原论文 PDF":
        return None
    return label


def _source_pdf_link(vault_name: str, slug: str, title: str) -> str:
    return (
        f"[{title}]("
        f"obsidian://open?vault={vault_name}&file=_paper_source%2Fraw%2F{slug}%2Fpaper.pdf)"
    )


def _rewrite_sources_line(
    line: str,
    *,
    vault_name: str,
    page_title: str | None,
    source_titles: dict[str, str],
) -> tuple[str, list[tuple[str, str]]]:
    _, _, value = line.partition(":")
    entries = _split_inline_list(value)
    return _rewrite_sources_entries(
        entries,
        vault_name=vault_name,
        page_title=page_title,
        source_titles=source_titles,
    )


def _rewrite_sources_entries(
    entries: list[str],
    *,
    vault_name: str,
    page_title: str | None,
    source_titles: dict[str, str],
) -> tuple[str, list[tuple[str, str]]]:
    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entry in entries:
        slug = _source_slug(entry)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        title = source_titles.get(slug) or _source_entry_title(entry) or _fallback_title_for_slug(
            slug,
            page_title=page_title,
            source_titles=source_titles,
        )
        sources.append((slug, title))
    links = [_source_pdf_link(vault_name, slug, title) for slug, title in sources]
    rewritten = "sources: " + json.dumps(links, ensure_ascii=False)
    return rewritten, sources


def _normalize_source_pdf_link_display(text: str, source_titles: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        slug = match.group("slug")
        title = source_titles.get(slug) or match.group("label")
        return f"[{title}]({match.group('uri')})"

    return PAPER_SOURCE_PDF_MARKDOWN_LINK.sub(replace, text)


def _ensure_source_entry_section(
    lines: list[str],
    *,
    vault_name: str,
    sources: list[tuple[str, str]],
) -> tuple[list[str], bool]:
    if not sources:
        return lines, False
    if any(line.strip() == "## 原文与证据入口" for line in lines):
        return lines, False

    section = ["## 原文与证据入口", ""]
    for slug, title in sources:
        section.append(f"- 原论文 PDF：{_source_pdf_link(vault_name, slug, title)}")
    section.append("")

    insert_at = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in {"## Provenance", "## Related"}:
            insert_at = index
            break
    updated = lines[:insert_at]
    if updated and updated[-1].strip():
        updated.append("")
    updated.extend(section)
    updated.extend(lines[insert_at:])
    return updated, True


def migrate_page(
    page: Path,
    *,
    vault_name: str = "paper-research-wiki",
    source_titles: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_titles = source_titles or {}
    original = page.read_text(encoding="utf-8")
    updated = original
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)
    lines = updated.splitlines()
    changed = False
    lifecycle_changed = False
    page_title = _frontmatter_title(lines)
    sources: list[tuple[str, str]] = []
    filtered: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("review_status:"):
            changed = True
            index += 1
            continue
        if line.startswith("sources: "):
            rewritten, source_records = _rewrite_sources_line(
                line,
                vault_name=vault_name,
                page_title=page_title,
                source_titles=source_titles,
            )
            if rewritten != line:
                changed = True
            sources = source_records
            filtered.append(rewritten)
            index += 1
            continue
        if line.strip() == "sources:":
            entries: list[str] = []
            end_index = index + 1
            while end_index < len(lines):
                list_match = re.match(r"^\s+-\s+(.*)$", lines[end_index])
                if not list_match:
                    break
                entries.append(list_match.group(1))
                end_index += 1
            if entries:
                rewritten, source_records = _rewrite_sources_entries(
                    entries,
                    vault_name=vault_name,
                    page_title=page_title,
                    source_titles=source_titles,
                )
                changed = True
                sources = source_records
                filtered.append(rewritten)
                index = end_index
                continue
            filtered.append(line)
            index += 1
            continue
        normalized_line = _normalize_source_pdf_link_display(line, source_titles)
        if normalized_line != line:
            changed = True
        line = normalized_line
        if line.startswith("lifecycle:") and "review-needed" in line:
            filtered.append("lifecycle: draft")
            changed = True
            lifecycle_changed = True
            index += 1
            continue
        filtered.append(line)
        index += 1

    if updated != original:
        changed = True
    updated_lines = filtered
    today = _today()
    if changed:
        for index, line in enumerate(updated_lines):
            if line.startswith("updated:"):
                updated_lines[index] = f"updated: {today}"
                break
        if lifecycle_changed:
            for index, line in enumerate(updated_lines):
                if line.startswith("lifecycle_changed:"):
                    updated_lines[index] = f"lifecycle_changed: {today}"
                    break
    updated_lines, inserted_source_section = _ensure_source_entry_section(
        updated_lines,
        vault_name=vault_name,
        sources=sources,
    )
    if inserted_source_section:
        changed = True

    updated_text = "\n".join(updated_lines)
    return {
        "page": page,
        "changed": updated_text.rstrip() != original.rstrip(),
        "text": updated_text,
        "source_labels": [slug for slug, _ in sources],
        "lifecycle_changed": lifecycle_changed,
        "inserted_source_section": inserted_source_section,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault = args.vault.resolve()
    pages = _formal_pages(vault)
    snapshot = _snapshot_formal_pages(vault, args.snapshot_name, execute=args.execute)
    source_titles = _source_title_map(vault)
    results = [migrate_page(page, vault_name=vault.name, source_titles=source_titles) for page in pages]
    changed_pages = [result for result in results if result["changed"]]
    if args.execute:
        for result in changed_pages:
            _write_text(result["page"], result["text"])
    return {
        "schema_version": "paper-wiki-formal-page-contract-migration-v1",
        "mode": "execute" if args.execute else "dry-run",
        "vault": str(vault),
        "snapshot": snapshot,
        "pages_scanned": len(results),
        "pages_changed": len(changed_pages),
        "changed_pages": [result["page"].relative_to(vault).as_posix() for result in changed_pages],
        "lifecycle_changed_pages": [
            result["page"].relative_to(vault).as_posix()
            for result in changed_pages
            if result["lifecycle_changed"]
        ],
        "source_entry_sections_added": [
            result["page"].relative_to(vault).as_posix()
            for result in changed_pages
            if result["inserted_source_section"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--snapshot-name", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['mode']}: changed {result['pages_changed']} page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
