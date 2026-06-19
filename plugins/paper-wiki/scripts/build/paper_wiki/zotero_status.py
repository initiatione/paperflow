from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paper_wiki.frontmatter import parse_frontmatter
from paper_wiki.zotero_contract import normalize_zotero_metadata
from paper_wiki.zotero_helper_adapter import ZoteroHelperAdapter
from paper_wiki.zotero_report import sanitize


PLAN_SCHEMA_VERSION = "paper-wiki-zotero-dry-run-v1"
TARGET_COLLECTION = "Paper Wiki"
REFERENCE_ROOT = "references"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _normalize_doi(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^doi:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    text = text.strip().rstrip(".,;)")
    if text.lower() in {"null", "none", "未核实", "缺失"}:
        return None
    return text.lower()


def _normalize_arxiv_base_id(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^arxiv:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text, flags=re.IGNORECASE)
    text = text.removesuffix(".pdf").strip().rstrip(".,;)")
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", text)
    if match:
        return match.group(1)
    return text or None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if item not in {None, ""}]
    if value in {None, ""}:
        return []
    return [value]


def _first_author(authors: list[Any]) -> str | None:
    if not authors:
        return None
    first = authors[0]
    if isinstance(first, dict):
        for key in ("lastName", "last", "name", "creator", "author"):
            if first.get(key):
                return str(first[key])
        if first.get("firstName") or first.get("lastName"):
            return " ".join(str(first.get(key) or "") for key in ("firstName", "lastName")).strip()
    return str(first)


def _extract_doi(frontmatter: dict[str, Any], text: str) -> str | None:
    doi = _normalize_doi(frontmatter.get("doi"))
    if doi:
        return doi
    match = re.search(r"https?://(?:dx\.)?doi\.org/(?P<doi>10\.\S+)", text, flags=re.I)
    return _normalize_doi(match.group("doi")) if match else None


def _extract_arxiv(frontmatter: dict[str, Any], text: str) -> tuple[str | None, str | None]:
    arxiv_id = str(frontmatter.get("arxiv_id") or frontmatter.get("arxiv") or "").strip() or None
    if not arxiv_id:
        match = re.search(r"arxiv\.org/(?:abs|pdf)/(?P<arxiv>\d{4}\.\d{4,5})(?:v\d+)?", text, flags=re.I)
        arxiv_id = match.group("arxiv") if match else None
    return arxiv_id, _normalize_arxiv_base_id(arxiv_id)


def _extract_source_pdf(frontmatter: dict[str, Any], text: str) -> str | None:
    sources = " ".join(str(item) for item in _as_list(frontmatter.get("sources")))
    match = re.search(r"obsidian://open\?[^)\s]+_paper_source%2Fraw%2F[^)\s]+%2Fpaper\.pdf", sources) or re.search(
        r"obsidian://open\?[^)\s]+_paper_source%2Fraw%2F[^)\s]+%2Fpaper\.pdf", text
    )
    return match.group(0) if match else None


def scan_reference_pages(vault_path: Path | str) -> list[dict[str, Any]]:
    vault = Path(vault_path).resolve()
    references = vault / REFERENCE_ROOT
    pages: list[dict[str, Any]] = []
    if not references.exists():
        return pages
    for page in sorted(references.glob("*.md")):
        text = page.read_text(encoding="utf-8")
        document = parse_frontmatter(text)
        frontmatter = document.frontmatter
        title = str(frontmatter.get("title") or page.stem.replace("-", " ")).strip()
        authors = _as_list(frontmatter.get("authors"))
        arxiv_id, arxiv_base_id = _extract_arxiv(frontmatter, text)
        zotero, zotero_issues = normalize_zotero_metadata(frontmatter.get("zotero"))
        pages.append(
            {
                "page": page.relative_to(vault).as_posix(),
                "path": str(page),
                "title": title,
                "normalized_title": _normalize_text(frontmatter.get("normalized_title") or title),
                "doi": _extract_doi(frontmatter, text),
                "arxiv_id": arxiv_id,
                "arxiv_base_id": arxiv_base_id,
                "year": frontmatter.get("year"),
                "authors": authors,
                "first_author": _first_author(authors),
                "source_pdf": _extract_source_pdf(frontmatter, text),
                "zotero": zotero,
                "frontmatter_issues": document.issues + zotero_issues,
            }
        )
    return pages


def _result_data(result: dict[str, Any]) -> Any:
    return result.get("data") if isinstance(result, dict) else None


def _item_key(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("item_key", "itemKey", "key", "zotero_key"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def _item_title(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("title") or item.get("name") or "")


def _item_authors(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return []
    for key in ("creators", "authors", "author"):
        value = item.get(key)
        if value:
            return _as_list(value)
    return []


def _item_year(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("year", "date", "publicationYear"):
        value = item.get(key)
        if value:
            match = re.search(r"\d{4}", str(value))
            return match.group(0) if match else str(value)
    return None


def _item_doi(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    return _normalize_doi(item.get("doi") or item.get("DOI"))


def _item_arxiv_base(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    return _normalize_arxiv_base_id(item.get("arxiv_id") or item.get("arxiv") or item.get("url"))


def _bibtex_text(result: dict[str, Any]) -> str:
    data = _result_data(result)
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("bibtex", "text", "content"):
            if data.get(key):
                return str(data[key])
    return ""


def _bibtex_matches_page(bibtex: str, page: dict[str, Any], basis: str) -> bool:
    lowered = bibtex.lower()
    if basis == "doi" and page.get("doi"):
        return str(page["doi"]).lower() in lowered
    if basis == "arxiv" and page.get("arxiv_base_id"):
        return str(page["arxiv_base_id"]).lower() in lowered
    if basis == "title":
        title = _normalize_text(page.get("title"))
        return bool(title and title in _normalize_text(bibtex))
    return False


def _candidate_basis(item: dict[str, Any], page: dict[str, Any]) -> str | None:
    if page.get("doi") and _item_doi(item) == page.get("doi"):
        return "doi"
    if page.get("arxiv_base_id") and _item_arxiv_base(item) == page.get("arxiv_base_id"):
        return "arxiv"
    title_matches = _normalize_text(_item_title(item)) == page.get("normalized_title")
    year_matches = not page.get("year") or str(page.get("year")) == str(_item_year(item) or "")
    first_author = _normalize_text(page.get("first_author"))
    item_first_author = _normalize_text(_first_author(_item_authors(item)) or "")
    if title_matches and year_matches and (not first_author or first_author == item_first_author):
        return "title_year_first_author"
    if title_matches:
        return "title_similarity"
    return None


def _search_zotero(adapter: Any, page: dict[str, Any]) -> list[dict[str, Any]]:
    queries = [page.get("doi"), page.get("arxiv_base_id"), page.get("title")]
    by_key: dict[str, dict[str, Any]] = {}
    for query in [str(item) for item in queries if item]:
        result = adapter.search(query, with_bibtex_keys=True)
        if not result.get("ok"):
            continue
        data = _result_data(result)
        rows = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = "|".join(
                [
                    _item_key(row) or "",
                    _item_doi(row) or "",
                    _item_arxiv_base(row) or "",
                    _normalize_text(_item_title(row)),
                ]
            )
            key = key or f"title:{_item_title(row)}"
            by_key[key] = row
    return list(by_key.values())


def _validated_candidate(adapter: Any, page: dict[str, Any], item: dict[str, Any], basis: str) -> bool:
    if basis in {"doi", "arxiv"}:
        key = _item_key(item)
        if not key:
            return False
        exported = adapter.export_item_bibtex(key)
        return bool(exported.get("ok") and _bibtex_matches_page(_bibtex_text(exported), page, basis))
    return basis == "title_year_first_author"


def _gate_record(result: dict[str, Any], *, severity: str = "warning") -> dict[str, Any]:
    gate = result.get("gate") or "zotero_helper_failed"
    return {
        "gate": gate,
        "severity": severity,
        "message": result.get("message") or gate,
        "next_action": _next_action_for_gate(gate),
    }


def _next_action_for_gate(gate: str) -> str:
    return {
        "zotero_plugin_missing": "Install or enable the official Zotero plugin helper.",
        "zotero_helper_incompatible": "Use a compatible official Zotero plugin helper.",
        "zotero_desktop_unavailable": "Open Zotero Desktop and retry the read-only status check.",
        "local_api_disabled": "Enable Zotero local API, then restart Zotero Desktop.",
        "connector_unavailable": "Start or repair the Zotero Connector endpoint before apply.",
        "selected_target_mismatch": "Select the Paper Wiki collection in Zotero before apply.",
        "zotero_timeout": "Retry after Zotero responds, or reduce the requested scope.",
        "zotero_invalid_json": "Check the official Zotero helper output and retry.",
    }.get(gate, "Inspect the Zotero helper diagnostics and retry.")


def _local_item(page: dict[str, Any], *, action: str, outcome: str, reason: str, **extra: Any) -> dict[str, Any]:
    item = {
        "page": page["page"],
        "title": page["title"],
        "doi": page.get("doi"),
        "arxiv_base_id": page.get("arxiv_base_id"),
        "year": page.get("year"),
        "authors": page.get("authors", []),
        "existing_zotero": page.get("zotero"),
        "planned_action": action,
        "outcome": outcome,
        "reason": reason,
    }
    item.update(extra)
    return item


def _plan_page(adapter: Any, page: dict[str, Any], zotero_available: bool) -> dict[str, Any]:
    if page["frontmatter_issues"]:
        return _local_item(
            page,
            action="repair_invalid_zotero_metadata",
            outcome="failed",
            reason="invalid_frontmatter_or_zotero_metadata",
            issues=page["frontmatter_issues"],
        )
    metadata = page.get("zotero")
    if metadata and metadata.get("item_key"):
        exported = adapter.export_item_bibtex(metadata["item_key"]) if zotero_available else {"ok": False, "gate": "zotero_unavailable"}
        if zotero_available and not exported.get("ok"):
            return _local_item(
                page,
                action="repair_broken_zotero_link",
                outcome="failed",
                reason="existing_zotero_item_key_did_not_validate",
                zotero_item_key=metadata["item_key"],
                gate=exported.get("gate"),
            )
        return _local_item(
            page,
            action="none",
            outcome=metadata.get("sync_status", "linked"),
            reason="existing_zotero_metadata_present",
            zotero_item_key=metadata["item_key"],
            identity_basis=metadata.get("identity_basis"),
        )
    if not zotero_available:
        return _local_item(
            page,
            action="wait_for_zotero",
            outcome="unavailable",
            reason="zotero_unavailable",
        )

    candidates = _search_zotero(adapter, page)
    validated: list[tuple[dict[str, Any], str]] = []
    review: list[dict[str, Any]] = []
    for candidate in candidates:
        basis = _candidate_basis(candidate, page)
        if basis is None:
            continue
        if basis == "title_similarity":
            review.append(candidate)
            continue
        if _validated_candidate(adapter, page, candidate, basis):
            validated.append((candidate, basis))
    if len(validated) > 1:
        return _local_item(
            page,
            action="review_conflict",
            outcome="conflict",
            reason="conflict_multiple_zotero_items",
            candidates=[_public_zotero_item(item, basis=basis) for item, basis in validated],
        )
    if len(validated) == 1:
        candidate, basis = validated[0]
        return _local_item(
            page,
            action="link_existing",
            outcome="linked",
            reason="validated_zotero_match",
            zotero_item_key=_item_key(candidate),
            bibtex_key=candidate.get("bibtexKey") or candidate.get("bibtex_key"),
            identity_basis=basis,
        )
    if review:
        return _local_item(
            page,
            action="review_conflict",
            outcome="conflict",
            reason="title_only_or_low_confidence_match",
            candidates=[_public_zotero_item(item, basis="title_similarity") for item in review],
        )
    if page.get("doi") or page.get("arxiv_base_id"):
        return _local_item(
            page,
            action="ready_for_import",
            outcome="skipped",
            reason="wiki_only_with_stable_identity",
            identity_basis="doi" if page.get("doi") else "arxiv",
        )
    return _local_item(
        page,
        action="needs_metadata_supplementation",
        outcome="skipped",
        reason="missing_stable_bibliographic_identity",
    )


def _public_zotero_item(item: dict[str, Any], *, basis: str | None = None) -> dict[str, Any]:
    return {
        "item_key": _item_key(item),
        "title": _item_title(item),
        "authors": _item_authors(item),
        "year": _item_year(item),
        "identity_basis": basis or _item_doi(item) and "doi" or _item_arxiv_base(item) and "arxiv" or "title",
        "doi": _item_doi(item),
        "arxiv_base_id": _item_arxiv_base(item),
        "bibtex_key": item.get("bibtexKey") or item.get("bibtex_key"),
    }


def _mark_multiple_wiki_page_conflicts(items: list[dict[str, Any]]) -> None:
    by_key: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = item.get("zotero_item_key")
        if key and item.get("outcome") in {"linked", "imported"}:
            by_key.setdefault(str(key), []).append(item)
    for key, matches in by_key.items():
        if len(matches) <= 1:
            continue
        pages = [item["page"] for item in matches]
        for item in matches:
            item["planned_action"] = "review_conflict"
            item["outcome"] = "conflict"
            item["reason"] = "conflict_multiple_wiki_pages"
            item["conflict_pages"] = pages
            item["zotero_item_key"] = key


def _inventory_items(adapter: Any, zotero_available: bool) -> list[dict[str, Any]]:
    if not zotero_available:
        return []
    result = adapter.inventory()
    if not result.get("ok"):
        return []
    data = _result_data(result)
    rows = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    return [row for row in rows if isinstance(row, dict) and not row.get("parentItem") and row.get("itemType") != "attachment"]


def _zotero_only_items(
    inventory: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    planned_items: list[dict[str, Any]],
    *,
    limit: int,
    expand: bool,
) -> dict[str, Any]:
    matched_keys = {str(item.get("zotero_item_key")) for item in planned_items if item.get("zotero_item_key")}
    page_dois = {page.get("doi") for page in pages if page.get("doi")}
    page_arxiv = {page.get("arxiv_base_id") for page in pages if page.get("arxiv_base_id")}
    page_titles = {page.get("normalized_title") for page in pages if page.get("normalized_title")}
    rows: list[dict[str, Any]] = []
    for item in inventory:
        key = _item_key(item)
        if key and key in matched_keys:
            continue
        if _item_doi(item) and _item_doi(item) in page_dois:
            continue
        if _item_arxiv_base(item) and _item_arxiv_base(item) in page_arxiv:
            continue
        if _normalize_text(_item_title(item)) in page_titles:
            continue
        rows.append(
            {
                **_public_zotero_item(item),
                "status": "zotero_only_not_in_paper_wiki",
                "recommended_next_action": "Review for Paper Wiki deposition or leave as Zotero-only.",
            }
        )
    rows.sort(key=lambda item: (str(item.get("year") or ""), str(item.get("title") or "")), reverse=True)
    shown = rows if expand else rows[:limit]
    return {"total": len(rows), "shown": shown, "truncated": len(shown) < len(rows)}


def _summary(items: list[dict[str, Any]], zotero_only: dict[str, Any], gates: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "reference_pages": len(items),
        "linked": 0,
        "imported": 0,
        "unlinked": 0,
        "ready_for_import": 0,
        "needs_metadata_supplementation": 0,
        "conflict": 0,
        "failed": 0,
        "unavailable": 0,
        "zotero_only_total": zotero_only["total"],
        "zotero_only_shown": len(zotero_only["shown"]),
        "gates": len(gates),
    }
    for item in items:
        outcome = item.get("outcome")
        action = item.get("planned_action")
        if outcome in {"linked", "imported", "conflict", "failed", "unavailable"}:
            summary[outcome] += 1
        if action == "ready_for_import":
            summary["ready_for_import"] += 1
        elif action == "needs_metadata_supplementation":
            summary["needs_metadata_supplementation"] += 1
        elif outcome == "skipped":
            summary["unlinked"] += 1
    return summary


def build_zotero_status_plan(
    vault_path: Path | str,
    *,
    mode: str = "status",
    adapter: Any | None = None,
    helper_path: Path | str | None = None,
    extra_roots: list[Path | str] | None = None,
    include_defaults: bool = True,
    zotero_only_limit: int = 20,
    expand_zotero_only: bool = False,
) -> dict[str, Any]:
    if mode not in {"status", "dry-run"}:
        raise ValueError(f"mode must be 'status' or 'dry-run'; got {mode!r}")
    vault = Path(vault_path).resolve()
    pages = scan_reference_pages(vault)
    zotero = adapter or ZoteroHelperAdapter(
        helper_path=helper_path,
        extra_roots=extra_roots,
        include_defaults=include_defaults,
    )
    status = zotero.status()
    gates: list[dict[str, Any]] = []
    zotero_available = bool(status.get("ok"))
    if not zotero_available:
        gates.append(_gate_record(status))

    items = [_plan_page(zotero, page, zotero_available) for page in pages]
    _mark_multiple_wiki_page_conflicts(items)
    inventory = _inventory_items(zotero, zotero_available)
    zotero_only = _zotero_only_items(
        inventory,
        pages,
        items,
        limit=zotero_only_limit,
        expand=expand_zotero_only,
    )
    if zotero_available and any(item.get("planned_action") == "ready_for_import" for item in items):
        target = zotero.selected_target(required_name=TARGET_COLLECTION)
        if not target.get("ok"):
            gates.append(_gate_record(target))

    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "mode": mode,
        "vault": str(vault),
        "target_collection": TARGET_COLLECTION,
        "generated_at": _utc_now(),
        "zotero_helper": status,
        "summary": _summary(items, zotero_only, gates),
        "items": items,
        "zotero_only": zotero_only,
        "gates": gates,
        "writes_performed": False,
    }
    return sanitize(plan)


def render_zotero_status_summary(plan: dict[str, Any]) -> str:
    summary = plan.get("summary", {})
    lines: list[str] = []
    if plan.get("gates"):
        lines.append("Zotero warnings:")
        for gate in plan["gates"]:
            lines.append(f"- {gate.get('gate')}: {gate.get('message')} Next: {gate.get('next_action')}")
        lines.append("")
    lines.append(f"Paper Wiki Zotero {plan.get('mode')} summary")
    lines.append(f"- Reference pages scanned: {summary.get('reference_pages', 0)}")
    lines.append(
        "- States: "
        f"linked={summary.get('linked', 0)}, imported={summary.get('imported', 0)}, "
        f"ready_for_import={summary.get('ready_for_import', 0)}, "
        f"needs_metadata={summary.get('needs_metadata_supplementation', 0)}, "
        f"conflict={summary.get('conflict', 0)}, unavailable={summary.get('unavailable', 0)}"
    )
    actionable = [
        item
        for item in plan.get("items", [])
        if item.get("planned_action") not in {None, "none"}
    ]
    if actionable:
        lines.append("Action groups:")
        for item in actionable[:10]:
            lines.append(f"- {item.get('planned_action')}: {item.get('page')} ({item.get('reason')})")
        if len(actionable) > 10:
            lines.append(f"- ... {len(actionable) - 10} more action items omitted")
    zotero_only = plan.get("zotero_only") or {}
    lines.append(
        f"Zotero-only library items: {zotero_only.get('total', 0)} total, "
        f"{len(zotero_only.get('shown') or [])} shown"
    )
    for item in (zotero_only.get("shown") or [])[:20]:
        lines.append(
            f"- {item.get('title') or '(untitled)'}; {item.get('year') or 'n.d.'}; "
            f"key={item.get('item_key')}; action={item.get('recommended_next_action')}"
        )
    if zotero_only.get("truncated"):
        lines.append("Full Zotero-only output requires an explicit expand/export request.")
    return "\n".join(lines).strip() + "\n"


def write_zotero_diagnostic_report(plan: dict[str, Any], output_path: Path | str) -> dict[str, Any]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path), "schema_version": plan.get("schema_version"), "mode": plan.get("mode")}
