from __future__ import annotations

import re
from typing import Any

from paper_wiki.zotero_contract import BIBTEX_ELIGIBLE_STATUSES


BIBTEX_KEY = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.MULTILINE)


def bibtex_entry_key(text: str) -> str | None:
    match = BIBTEX_KEY.search(text or "")
    return match.group(1).strip() if match else None


def compose_wiki_scoped_bibtex(records: list[dict[str, Any]]) -> dict[str, Any]:
    entries: list[str] = []
    seen: set[str] = set()
    diagnostics: dict[str, Any] = {
        "included": [],
        "skipped": [],
        "duplicates": [],
        "counts": {"included": 0, "skipped": 0, "duplicates": 0},
    }
    for record in records:
        status = str(record.get("sync_status") or "")
        item_key = str(record.get("item_key") or "").strip()
        bibtex = str(record.get("bibtex") or "").strip()
        page = record.get("page")
        if status not in BIBTEX_ELIGIBLE_STATUSES:
            diagnostics["skipped"].append(
                {"page": page, "item_key": item_key or None, "reason": "sync_status_not_eligible"}
            )
            continue
        if not item_key:
            diagnostics["skipped"].append({"page": page, "reason": "missing_item_key"})
            continue
        if not bibtex:
            diagnostics["skipped"].append(
                {"page": page, "item_key": item_key, "reason": "missing_bibtex"}
            )
            continue
        key = bibtex_entry_key(bibtex) or str(record.get("bibtex_key") or "").strip() or item_key
        if key in seen:
            diagnostics["duplicates"].append({"page": page, "item_key": item_key, "key": key})
            continue
        seen.add(key)
        entries.append(bibtex)
        diagnostics["included"].append({"page": page, "item_key": item_key, "key": key})
    diagnostics["counts"] = {
        "included": len(diagnostics["included"]),
        "skipped": len(diagnostics["skipped"]),
        "duplicates": len(diagnostics["duplicates"]),
    }
    content = "\n\n".join(entries)
    if content:
        content += "\n"
    return {"content": content, "diagnostics": diagnostics}
