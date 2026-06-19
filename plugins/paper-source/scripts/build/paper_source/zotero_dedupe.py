from __future__ import annotations

import difflib
import os
import re
from collections import Counter
from typing import Any

from paper_source.schemas import canonical_key
from paper_source.zotero_helper_adapter import ZoteroHelperAdapter


SCHEMA_VERSION = "paper-source-zotero-dedupe-v1"
DISABLE_ENV = "PAPER_SOURCE_ZOTERO_DEDUPE"

CANDIDATE_ALREADY_IN_WIKI = "already_in_wiki"
CANDIDATE_ALREADY_IN_ZOTERO = "already_in_zotero_not_wiki"
CANDIDATE_POSSIBLE_DUPLICATE = "possible_zotero_duplicate"
CANDIDATE_NEW = "new_candidate"
CANDIDATE_UNAVAILABLE = "zotero_unavailable"
CANDIDATE_NOT_CHECKED = "not_checked"

WIKI_IN_WIKI = "in_wiki"
WIKI_IN_RAW_LIBRARY = "in_raw_library"
WIKI_NOT_IN_WIKI = "not_in_wiki"

ZOTERO_EXACT = "exact_match"
ZOTERO_HIGH_CONFIDENCE = "high_confidence_match"
ZOTERO_POSSIBLE = "possible_duplicate"
ZOTERO_NOT_FOUND = "not_found"
ZOTERO_UNAVAILABLE = "unavailable"
ZOTERO_NOT_CHECKED = "not_checked"


def zotero_dedupe_enabled(config_enabled: bool | None = None, env: dict[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    raw = values.get(DISABLE_ENV)
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}
    return bool(config_enabled)


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalize_doi(value: object) -> str | None:
    text = _text(value).lower()
    if not text:
        return None
    text = re.sub(r"^doi:\s*", "", text)
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = text.strip().rstrip(".,;)")
    return text or None


def _normalize_arxiv_base_id(value: object) -> str | None:
    text = _text(value).lower()
    if not text:
        return None
    text = re.sub(r"^arxiv:\s*", "", text)
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text)
    text = text.removesuffix(".pdf").strip().rstrip(".,;)")
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", text)
    if match:
        return match.group(1)
    match = re.search(r"([a-z-]+(?:\.[a-z-]+)?/\d{7})(?:v\d+)?", text)
    if match:
        return match.group(1)
    return re.sub(r"v\d+$", "", text) or None


def _normalize_title(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _year(value: object) -> str | None:
    text = _text(value)
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return match.group(0) if match else None


def _creator_names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    names: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or " ".join(
                    part for part in [item.get("firstName"), item.get("lastName")] if part
                )
                if name:
                    names.append(str(name))
    return names


def _first_author(value: Any) -> str | None:
    names = _creator_names(value)
    if not names:
        return None
    first = names[0].lower()
    parts = [part for part in re.split(r"[^a-z0-9]+", first) if part]
    return parts[-1] if parts else None


def _item_key(item: dict[str, Any]) -> str | None:
    for key in ("key", "itemKey", "item_key", "zotero_item_key"):
        value = _text(item.get(key))
        if value:
            return value
    return None


def _item_doi(item: dict[str, Any]) -> str | None:
    for key in ("doi", "DOI"):
        value = _normalize_doi(item.get(key))
        if value:
            return value
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    return _normalize_doi(data.get("DOI") or data.get("doi"))


def _item_arxiv(item: dict[str, Any]) -> str | None:
    for key in ("arxiv_id", "arxivId", "arXiv", "arxiv"):
        value = _normalize_arxiv_base_id(item.get(key))
        if value:
            return value
    for key in ("url", "URL"):
        value = _normalize_arxiv_base_id(item.get(key))
        if value and "." in value:
            return value
    return None


def _item_title(item: dict[str, Any]) -> str:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    return _text(item.get("title") or data.get("title"))


def _item_year(item: dict[str, Any]) -> str | None:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    for key in ("year", "date", "publicationYear"):
        value = _year(item.get(key))
        if value:
            return value
    return _year(data.get("year") or data.get("date"))


def _item_first_author(item: dict[str, Any]) -> str | None:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    return _first_author(item.get("creators") or item.get("authors") or data.get("creators") or data.get("authors"))


def _items_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "records", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _candidate_identity(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "doi": _normalize_doi(candidate.get("doi")),
        "arxiv": _normalize_arxiv_base_id(candidate.get("arxiv_base_id") or candidate.get("arxiv_id") or candidate.get("url")),
        "title": _normalize_title(candidate.get("title")),
        "year": _year(candidate.get("year")),
        "first_author": _first_author(candidate.get("authors") or candidate.get("creators")),
    }


def _match_candidate(candidate: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any] | None:
    identity = _candidate_identity(candidate)
    best_possible: tuple[float, dict[str, Any]] | None = None
    for item in items:
        item_title = _item_title(item)
        item_key = _item_key(item)
        if identity["doi"] and identity["doi"] == _item_doi(item):
            return _match_payload(item, item_key, item_title, "exact_match", "doi", "exact")
        if identity["arxiv"] and identity["arxiv"] == _item_arxiv(item):
            return _match_payload(item, item_key, item_title, "exact_match", "arxiv", "exact")

        candidate_title = identity["title"]
        item_title_norm = _normalize_title(item_title)
        if candidate_title and item_title_norm:
            ratio = difflib.SequenceMatcher(None, candidate_title, item_title_norm).ratio()
            same_year = bool(identity["year"] and identity["year"] == _item_year(item))
            same_author = bool(identity["first_author"] and identity["first_author"] == _item_first_author(item))
            if ratio >= 0.94 and same_year and same_author:
                return _match_payload(item, item_key, item_title, "high_confidence_match", "title_author_year", "high")
            if ratio >= 0.86:
                payload = _match_payload(item, item_key, item_title, "possible_duplicate", "title_similarity", "possible")
                payload["zotero_match_confidence_score"] = round(ratio, 4)
                if best_possible is None or ratio > best_possible[0]:
                    best_possible = (ratio, payload)
    return best_possible[1] if best_possible else None


def _match_payload(
    item: dict[str, Any],
    item_key: str | None,
    title: str,
    zotero_status: str,
    identity_basis: str,
    confidence: str,
) -> dict[str, Any]:
    return {
        "zotero_status": zotero_status,
        "identity_basis": identity_basis,
        "zotero_item_key": item_key,
        "zotero_match_confidence": confidence,
        "matched_title": title or None,
        "matched_year": _item_year(item),
        "bibtex_key": item.get("bibtexKey") or item.get("bibtex_key"),
    }


def _dedupe_payload(
    *,
    wiki_status: str,
    zotero_status: str,
    candidate_status: str,
    identity_basis: str | None = None,
    zotero_item_key: str | None = None,
    zotero_match_confidence: str | None = None,
    dedupe_warning: str | None = None,
    matched_title: str | None = None,
    matched_year: str | None = None,
    recommended_action: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "wiki_status": wiki_status,
        "zotero_status": zotero_status,
        "candidate_status": candidate_status,
        "identity_basis": identity_basis or "unknown",
        "zotero_item_key": zotero_item_key,
        "zotero_match_confidence": zotero_match_confidence,
        "dedupe_warning": dedupe_warning,
        "matched_title": matched_title,
        "matched_year": matched_year,
        "recommended_action": recommended_action,
    }
    if extra:
        payload.update(extra)
    return payload


def _action_for_status(candidate_status: str) -> str:
    if candidate_status == CANDIDATE_ALREADY_IN_ZOTERO:
        return "Run Paper Wiki Zotero sync/apply to link or deposit this item."
    if candidate_status == CANDIDATE_POSSIBLE_DUPLICATE:
        return "Review the possible Zotero duplicate before staging with Paper Source."
    if candidate_status == CANDIDATE_UNAVAILABLE:
        return "Open/enable Zotero and rerun discovery if Zotero dedupe is required."
    if candidate_status == CANDIDATE_NOT_CHECKED:
        return "Enable Paper Source Zotero dedupe to check the local Zotero library."
    return "Eligible for ordinary Paper Source recommendation after ranking."


class PaperSourceZoteroDedupe:
    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter or ZoteroHelperAdapter()
        self._inventory_items: list[dict[str, Any]] | None = None
        self._search_cache: dict[str, list[dict[str, Any]]] = {}

    def preflight(self) -> dict[str, Any]:
        return self.adapter.status()

    def _inventory(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        if self._inventory_items is not None:
            return self._inventory_items, None
        result = self.adapter.inventory()
        if not result.get("ok"):
            return [], result
        self._inventory_items = _items_from_payload(result.get("data"))
        return self._inventory_items, None

    def _search(self, query: str) -> list[dict[str, Any]]:
        if query in self._search_cache:
            return self._search_cache[query]
        result = self.adapter.search(query, with_bibtex_keys=True)
        items = _items_from_payload(result.get("data")) if result.get("ok") else []
        self._search_cache[query] = items
        return items

    def lookup(self, candidate: dict[str, Any]) -> dict[str, Any]:
        items, error = self._inventory()
        if error is not None:
            return unavailable_payload(error)
        match = _match_candidate(candidate, items)
        if match is None:
            identity = _candidate_identity(candidate)
            for query in [identity["doi"], identity["arxiv"], candidate.get("title")]:
                query_text = _text(query)
                if not query_text:
                    continue
                match = _match_candidate(candidate, self._search(query_text))
                if match is not None:
                    break
        if match is None:
            return _dedupe_payload(
                wiki_status=WIKI_NOT_IN_WIKI,
                zotero_status=ZOTERO_NOT_FOUND,
                candidate_status=CANDIDATE_NEW,
                identity_basis="unknown",
                recommended_action=_action_for_status(CANDIDATE_NEW),
            )
        candidate_status = (
            CANDIDATE_POSSIBLE_DUPLICATE
            if match["zotero_status"] == ZOTERO_POSSIBLE
            else CANDIDATE_ALREADY_IN_ZOTERO
        )
        return _dedupe_payload(
            wiki_status=WIKI_NOT_IN_WIKI,
            zotero_status=match["zotero_status"],
            candidate_status=candidate_status,
            identity_basis=match.get("identity_basis"),
            zotero_item_key=match.get("zotero_item_key"),
            zotero_match_confidence=match.get("zotero_match_confidence"),
            matched_title=match.get("matched_title"),
            matched_year=match.get("matched_year"),
            recommended_action=_action_for_status(candidate_status),
            extra={key: value for key, value in match.items() if key not in {"zotero_status"}},
        )


def unavailable_payload(result: dict[str, Any]) -> dict[str, Any]:
    gate = _text(result.get("gate")) or "zotero_unavailable"
    return _dedupe_payload(
        wiki_status=WIKI_NOT_IN_WIKI,
        zotero_status=ZOTERO_UNAVAILABLE,
        candidate_status=CANDIDATE_UNAVAILABLE,
        dedupe_warning=gate,
        recommended_action=_action_for_status(CANDIDATE_UNAVAILABLE),
        extra={"gate": gate, "message": result.get("message"), "helper": result.get("helper")},
    )


def not_checked_payload(reason: str = "zotero_dedupe_disabled") -> dict[str, Any]:
    return _dedupe_payload(
        wiki_status=WIKI_NOT_IN_WIKI,
        zotero_status=ZOTERO_NOT_CHECKED,
        candidate_status=CANDIDATE_NOT_CHECKED,
        dedupe_warning=reason,
        recommended_action=_action_for_status(CANDIDATE_NOT_CHECKED),
    )


def apply_zotero_dedupe_to_filter_report(
    filter_report: dict[str, Any],
    *,
    enabled: bool,
    adapter: Any | None = None,
) -> dict[str, Any]:
    kept = [item for item in filter_report.get("kept") or [] if isinstance(item, dict)]
    record = {
        "schema_version": SCHEMA_VERSION,
        "enabled": bool(enabled),
        "status": "disabled" if not enabled else "ok",
        "summary": {},
        "warnings": [],
        "groups": {
            CANDIDATE_ALREADY_IN_ZOTERO: [],
            CANDIDATE_POSSIBLE_DUPLICATE: [],
            CANDIDATE_NEW: [],
            CANDIDATE_UNAVAILABLE: [],
            CANDIDATE_NOT_CHECKED: [],
        },
    }
    if not kept:
        record["summary"] = _summary_from_candidates([])
        filter_report["zotero_dedupe"] = record
        return filter_report

    dedupe = PaperSourceZoteroDedupe(adapter)
    unavailable: dict[str, Any] | None = None
    if enabled:
        status = dedupe.preflight()
        record["helper_status"] = status
        if not status.get("ok"):
            unavailable = unavailable_payload(status)
            record["status"] = "unavailable"
            record["warnings"].append(unavailable.get("dedupe_warning") or "zotero_unavailable")

    next_kept: list[dict[str, Any]] = []
    zotero_rejected: list[dict[str, Any]] = []
    for candidate in kept:
        annotated = dict(candidate)
        if not enabled:
            payload = not_checked_payload()
        elif unavailable is not None:
            payload = dict(unavailable)
        else:
            payload = dedupe.lookup(candidate)
        annotated["zotero_dedupe"] = payload
        candidate_status = payload.get("candidate_status")
        record["groups"].setdefault(str(candidate_status), []).append(_group_card(annotated))
        if candidate_status in {CANDIDATE_ALREADY_IN_ZOTERO, CANDIDATE_POSSIBLE_DUPLICATE}:
            item_key = payload.get("zotero_item_key") or "unknown"
            reason = f"{candidate_status}:{item_key}"
            annotated["filter_reasons"] = [reason]
            annotated["recommendation_filter_status"] = "rejected"
            annotated["filter_status"] = "rejected"
            zotero_rejected.append(annotated)
        else:
            next_kept.append(annotated)

    kept_by_key = {canonical_key(candidate): candidate for candidate in next_kept}
    filter_report["kept"] = next_kept
    filter_report["recommendable"] = next_kept
    filter_report["staging_ready"] = _replace_with_kept(filter_report.get("staging_ready") or [], kept_by_key)
    filter_report["needs_pdf"] = _replace_with_kept(filter_report.get("needs_pdf") or [], kept_by_key)
    filter_report["rejected"] = [*(filter_report.get("rejected") or []), *zotero_rejected]
    record["summary"] = _summary_from_candidates([*next_kept, *zotero_rejected])
    unavailable_warnings = sorted(
        {
            _text(candidate.get("zotero_dedupe", {}).get("dedupe_warning"))
            for candidate in [*next_kept, *zotero_rejected]
            if isinstance(candidate.get("zotero_dedupe"), dict)
            and candidate["zotero_dedupe"].get("candidate_status") == CANDIDATE_UNAVAILABLE
            and _text(candidate["zotero_dedupe"].get("dedupe_warning"))
        }
    )
    if unavailable_warnings:
        record["status"] = "unavailable"
        record["warnings"] = sorted(set([*record["warnings"], *unavailable_warnings]))
    filter_report["zotero_dedupe"] = record
    return filter_report


def _replace_with_kept(candidates: list[dict[str, Any]], kept_by_key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    replaced: list[dict[str, Any]] = []
    for candidate in candidates:
        key = canonical_key(candidate)
        if key in kept_by_key:
            replaced.append(kept_by_key[key])
    return replaced


def _summary_from_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    for candidate in candidates:
        dedupe = candidate.get("zotero_dedupe") if isinstance(candidate.get("zotero_dedupe"), dict) else {}
        counts[_text(dedupe.get("candidate_status")) or "unknown"] += 1
    return {
        "counts": dict(sorted(counts.items())),
        "already_in_zotero_not_wiki": counts.get(CANDIDATE_ALREADY_IN_ZOTERO, 0),
        "possible_zotero_duplicate": counts.get(CANDIDATE_POSSIBLE_DUPLICATE, 0),
        "new_candidate": counts.get(CANDIDATE_NEW, 0),
        "zotero_unavailable": counts.get(CANDIDATE_UNAVAILABLE, 0),
        "not_checked": counts.get(CANDIDATE_NOT_CHECKED, 0),
    }


def _group_card(candidate: dict[str, Any]) -> dict[str, Any]:
    dedupe = candidate.get("zotero_dedupe") if isinstance(candidate.get("zotero_dedupe"), dict) else {}
    return {
        "slug": candidate.get("slug"),
        "title": candidate.get("title"),
        "year": candidate.get("year"),
        "doi": candidate.get("doi"),
        "arxiv_id": candidate.get("arxiv_id"),
        "zotero_item_key": dedupe.get("zotero_item_key"),
        "identity_basis": dedupe.get("identity_basis"),
        "zotero_status": dedupe.get("zotero_status"),
        "candidate_status": dedupe.get("candidate_status"),
        "matched_title": dedupe.get("matched_title"),
        "matched_year": dedupe.get("matched_year"),
        "dedupe_warning": dedupe.get("dedupe_warning"),
        "recommended_action": dedupe.get("recommended_action"),
    }
