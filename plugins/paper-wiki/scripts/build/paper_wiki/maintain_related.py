from __future__ import annotations

import argparse
import hashlib
import json
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
INTERNAL_LINK_ROOTS = (
    "_paper_source",
    "_epi",
    "_raw",
    "_staging",
    "_runs",
    "_quarantine",
    ".obsidian",
    ".git",
)
INTERNAL_DETACH_ROOTS = (
    "_epi/meta/formal-page-snapshots",
    "_epi/staging",
    "_paper_source/staging",
    "_paper_source/meta/formal-page-snapshots",
)
FRONTMATTER = re.compile(r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n?", re.DOTALL)
RELATIONSHIP_TARGET = re.compile(r"(?m)(?:^|\{|\s)target:\s*(?P<target>\"[^\"]+\"|'[^']+'|\[\[[^\]]+\]\])")
RELATED_SECTION = re.compile(r"(?ms)(?:\n{2,})## Related\s*\n.*?(?=\n## |\Z)")
WIKILINK = re.compile(r"\[\[(?P<body>[^\]\n]+)\]\]")


@dataclass(frozen=True)
class RelatedUpdate:
    page: str
    changed: bool
    targets: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _formal_pages(vault: Path) -> list[Path]:
    pages: list[Path] = []
    for root in FORMAL_ROOTS:
        root_path = vault / root
        if root_path.exists():
            pages.extend(sorted(root_path.rglob("*.md")))
    return pages


def detach_wikilinks(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        body = match.group("body").strip()
        target, _, alias = body.partition("|")
        return (alias or target).strip()

    return WIKILINK.sub(replace, text)


def _snapshot_formal_pages(vault: Path, snapshot_name: str | None, *, execute: bool) -> str | None:
    if not execute:
        return None
    name = snapshot_name or f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-pre-related"
    snapshot = vault / "_paper_source" / "meta" / "formal-page-snapshots" / name
    if (snapshot / "manifest.json").exists():
        return snapshot.relative_to(vault).as_posix() + "/"

    records: list[dict[str, Any]] = []
    for page in _formal_pages(vault):
        relative = page.relative_to(vault)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(detach_wikilinks(page.read_text(encoding="utf-8")), encoding="utf-8")
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
            "reason": "pre-rewrite formal page snapshot before Related section maintenance",
            "roots": list(FORMAL_ROOTS),
            "file_count": len(records),
            "files": records,
        },
    )
    return snapshot.relative_to(vault).as_posix() + "/"


def _strip_scalar(value: str) -> str:
    text = value.strip().rstrip(",")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _frontmatter(text: str) -> str:
    match = FRONTMATTER.match(text)
    return match.group("frontmatter") if match else ""


def _is_internal_target(target: str) -> bool:
    inner = _wikilink_target(target)
    if not inner:
        return False
    first = inner.split("/", 1)[0]
    return first in INTERNAL_LINK_ROOTS


def _wikilink_target(target: str) -> str:
    inner = target.strip()
    if inner.startswith("[[") and inner.endswith("]]"):
        inner = inner[2:-2]
    inner = inner.split("|", 1)[0].strip().replace("\\", "/")
    return inner


def _canonical_formal_wikilink(target: str) -> str | None:
    inner = _wikilink_target(target)
    if not inner:
        return None
    first = inner.split("/", 1)[0]
    if first not in FORMAL_ROOTS:
        return None
    return f"[[{inner}]]"


def _is_formal_target(target: str) -> bool:
    inner = _wikilink_target(target)
    if not inner:
        return False
    first = inner.split("/", 1)[0]
    return first in FORMAL_ROOTS


def relationship_targets(text: str) -> list[str]:
    frontmatter = _frontmatter(text)
    if "relationships" not in frontmatter:
        return []

    targets: list[str] = []
    seen: set[str] = set()
    for match in RELATIONSHIP_TARGET.finditer(frontmatter):
        target = _strip_scalar(match.group("target"))
        if not (target.startswith("[[") and target.endswith("]]")):
            continue
        canonical = _canonical_formal_wikilink(target)
        if _is_internal_target(target) or canonical is None:
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        targets.append(canonical)
    return targets


def formal_outgoing_wikilinks(text: str) -> list[str]:
    body = RELATED_SECTION.sub("", text)
    targets: list[str] = []
    seen: set[str] = set()
    for match in WIKILINK.finditer(body):
        canonical = _canonical_formal_wikilink("[[" + match.group("body") + "]]")
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        targets.append(canonical)
    return targets


def related_targets(text: str) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for target in [*relationship_targets(text), *formal_outgoing_wikilinks(text)]:
        if target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return targets


def render_related(targets: list[str]) -> str:
    if not targets:
        return ""
    entries = "\n".join(f"- {target}" for target in targets)
    return f"## Related\n\n{entries}"


def replace_related_section(text: str, targets: list[str]) -> str:
    body = RELATED_SECTION.sub("", text.rstrip())
    related = render_related(targets)
    if not related:
        return body.rstrip() + "\n"
    return body.rstrip() + "\n\n" + related + "\n"


def update_page(page: Path, *, vault: Path | None = None, execute: bool = False) -> RelatedUpdate:
    text = page.read_text(encoding="utf-8")
    targets = related_targets(text)
    updated = replace_related_section(text, targets)
    changed = updated != text
    if changed and execute:
        _write_text(page, updated)
    display_page = page.relative_to(vault).as_posix() if vault else page.name
    return RelatedUpdate(page=display_page, changed=changed, targets=targets)


def formal_wikilink_issues(vault: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for page in _formal_pages(vault):
        text = page.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in WIKILINK.finditer(line):
                target = "[[" + match.group("body") + "]]"
                if not _is_formal_target(target):
                    issues.append(
                        {
                            "page": page.relative_to(vault).as_posix(),
                            "line": line_number,
                            "target": target,
                        }
                    )
    return issues


def _internal_markdown_pages(vault: Path) -> list[Path]:
    pages: list[Path] = []
    for relative_root in INTERNAL_DETACH_ROOTS:
        root = vault / relative_root
        if root.exists():
            pages.extend(sorted(root.rglob("*.md")))
    return pages


def detach_internal_markdown_links(vault: Path, *, execute: bool = False) -> dict[str, Any]:
    scanned = _internal_markdown_pages(vault)
    changed: list[str] = []
    for page in scanned:
        text = page.read_text(encoding="utf-8", errors="ignore")
        updated = detach_wikilinks(text)
        if updated == text:
            continue
        changed.append(page.relative_to(vault).as_posix())
        if execute:
            _write_text(page, updated)
    return {
        "scanned": [page.relative_to(vault).as_posix() for page in scanned],
        "changed": changed,
    }


def _target_pages(vault: Path, page_args: list[str]) -> list[Path]:
    if not page_args:
        return _formal_pages(vault)
    pages: list[Path] = []
    for value in page_args:
        candidate = Path(value)
        path = candidate if candidate.is_absolute() else vault / candidate
        resolved = path.resolve()
        try:
            resolved.relative_to(vault)
        except ValueError as exc:
            raise ValueError(f"page path must stay inside vault: {value}") from exc
        if not resolved.is_file():
            raise FileNotFoundError(f"missing page: {resolved}")
        if resolved.suffix.lower() != ".md":
            raise ValueError(f"page must be Markdown: {value}")
        pages.append(resolved)
    return pages


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault = args.vault.resolve()
    pages = _target_pages(vault, args.page or [])
    dry_results = [update_page(page, vault=vault, execute=False) for page in pages]
    changed_pages = [vault / result.page for result in dry_results if result.changed]
    snapshot = _snapshot_formal_pages(vault, args.snapshot_name, execute=args.execute and bool(changed_pages))
    page_results = [
        update_page(page, vault=vault, execute=args.execute)
        for page in pages
    ]
    internal_detach = detach_internal_markdown_links(vault, execute=args.execute)
    formal_link_issues = formal_wikilink_issues(vault)
    return {
        "schema_version": "paper-wiki-maintain-related-v1",
        "mode": "execute" if args.execute else "dry-run",
        "snapshot": snapshot,
        "pages_scanned": [page.relative_to(vault).as_posix() for page in pages],
        "pages_changed": [result.page for result in page_results if result.changed],
        "internal_detach": internal_detach,
        "formal_wikilink_issues": formal_link_issues,
        "page_results": [
            {"page": result.page, "changed": result.changed, "targets": result.targets}
            for result in page_results
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, type=Path)
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
