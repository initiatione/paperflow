from __future__ import annotations

import re


def slugify_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:96] or "untitled-paper"


def canonical_key(record: dict) -> str:
    doi = str(record.get("doi") or "").lower().strip()
    if doi:
        return f"doi:{doi}"
    arxiv_id = str(record.get("arxiv_id") or "").lower().strip()
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    return f"title:{slugify_title(str(record.get('title') or 'untitled-paper'))}"
