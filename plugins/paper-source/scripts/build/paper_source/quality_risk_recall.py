from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from paper_source.schemas import canonical_key

RECALL_GAP_RECORD_SCHEMA_VERSION = "paper-source-recall-gap-record-v1"
RECALL_EXPANSION_SCHEMA_VERSION = "paper-source-recall-expansion-v1"
QUALITY_RISK_SCHEMA_VERSION = "paper-source-quality-risk-v1"
QUALITY_RISK_RECORD_SCHEMA_VERSION = "paper-source-quality-risk-record-v1"

OFFICIAL_VERSION_FIELDS = (
    "official_version",
    "official_versions",
    "journal_version",
    "published_version",
    "publisher_version",
    "version_of_record",
)
RELATED_PAPER_FIELDS = (
    "related_papers",
    "related",
    "related_works",
    "recommended_papers",
    "recommendations",
)
CITATION_GRAPH_FIELDS = (
    "cited_by",
    "cited_by_papers",
    "references",
    "reference_papers",
)

RISK_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "retracted": ("retracted", "retraction", "is_retracted", "retraction_notice"),
    "withdrawn": ("withdrawn", "withdrawal", "is_withdrawn"),
    "expression_of_concern": (
        "expression_of_concern",
        "has_expression_of_concern",
        "eoc",
    ),
    "paper_mill": ("paper_mill", "paper_mill_evidence", "papermill"),
    "predatory_venue": ("predatory_venue", "predatory_journal", "predatory"),
}
RISK_TYPE_ORDER = tuple(RISK_FIELD_ALIASES)


def _text(value: object) -> str:
    return str(value or "").strip()


def _record_source(record: dict[str, Any]) -> str:
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    return _text(record.get("source") or raw_record.get("source") or record.get("provider") or "provider_metadata")


def _record_provider(record: dict[str, Any]) -> str | None:
    provider = _text(record.get("provider"))
    if provider:
        return provider
    source = _record_source(record)
    return "grok_search" if source == "grok_search" else "paper_search"


def _candidate_key(candidate: dict[str, Any]) -> str:
    return canonical_key(candidate)


def _candidate_identity(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": candidate.get("slug"),
        "title": candidate.get("title"),
        "doi": candidate.get("doi"),
        "arxiv_id": candidate.get("arxiv_id"),
        "source": candidate.get("source") or _record_source(candidate),
    }


def _compact_value(value: object) -> object:
    if isinstance(value, dict):
        compact: dict[str, object] = {}
        for key in ("title", "doi", "arxiv_id", "year", "venue", "source", "status", "url"):
            if value.get(key) not in (None, ""):
                compact[key] = value.get(key)
        return compact or {"keys": sorted(str(key) for key in value)[:12]}
    if isinstance(value, list):
        return {"count": len(value)}
    return value


def _iter_record_contexts(candidate: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    yield "candidate", candidate
    for index, raw_record in enumerate(candidate.get("raw_records") or []):
        if not isinstance(raw_record, dict):
            continue
        yield f"raw_records[{index}]", raw_record
        nested = raw_record.get("raw_record")
        if isinstance(nested, dict):
            yield f"raw_records[{index}].raw_record", nested


def _expansion_kind_for_field(field: str) -> str:
    if field in OFFICIAL_VERSION_FIELDS:
        return "official_version"
    if field in RELATED_PAPER_FIELDS:
        return "related_paper"
    if field in {"cited_by", "cited_by_papers"}:
        return "cited_by"
    return "reference"


def _iter_expansion_values(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def _has_candidate_identity(record: dict[str, Any]) -> bool:
    return bool(record.get("title") or record.get("doi") or record.get("arxiv_id"))


def _recall_expansion_payload(
    *,
    seed: dict[str, Any],
    candidate_key: str,
    expansion_kind: str,
    source_field: str,
    source_record: dict[str, Any],
    value: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": RECALL_EXPANSION_SCHEMA_VERSION,
        "status": "recovered",
        "expansion_kind": expansion_kind,
        "confidence": "provider_explicit",
        "candidate_key": candidate_key,
        "source_candidate": _candidate_identity(seed),
        "provider": _record_provider(source_record),
        "source": _record_source(source_record),
        "source_field": source_field,
        "evidence": [
            {
                "source": _record_source(source_record),
                "provider": _record_provider(source_record),
                "source_field": source_field,
                "value": _compact_value(value),
            }
        ],
    }


def build_recall_gap_record(
    candidates: list[dict[str, Any]],
    *,
    existing_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract provider-supplied recall expansions from already discovered candidates."""

    existing_keys = {_candidate_key(candidate) for candidate in (existing_candidates or candidates)}
    seen_keys = set(existing_keys)
    attempts: list[dict[str, Any]] = []
    expansion_records: list[dict[str, Any]] = []
    field_names = (*OFFICIAL_VERSION_FIELDS, *RELATED_PAPER_FIELDS, *CITATION_GRAPH_FIELDS)

    for seed in candidates:
        for context_path, record in _iter_record_contexts(seed):
            for field in field_names:
                if field not in record:
                    continue
                source_field = f"{context_path}.{field}"
                for value in _iter_expansion_values(record.get(field)):
                    expansion_kind = _expansion_kind_for_field(field)
                    if not _has_candidate_identity(value):
                        attempts.append(
                            {
                                "status": "insufficient_identity",
                                "expansion_kind": expansion_kind,
                                "source_field": source_field,
                                "source_candidate": _candidate_identity(seed),
                                "evidence": [{"source_field": source_field, "value": _compact_value(value)}],
                            }
                        )
                        continue
                    candidate_key = _candidate_key(value)
                    if candidate_key in seen_keys:
                        attempts.append(
                            {
                                "status": "duplicate_existing_candidate",
                                "candidate_key": candidate_key,
                                "title": value.get("title"),
                                "doi": value.get("doi"),
                                "expansion_kind": expansion_kind,
                                "source_field": source_field,
                                "source_candidate": _candidate_identity(seed),
                            }
                        )
                        continue
                    seen_keys.add(candidate_key)
                    expansion = _recall_expansion_payload(
                        seed=seed,
                        candidate_key=candidate_key,
                        expansion_kind=expansion_kind,
                        source_field=source_field,
                        source_record=record,
                        value=value,
                    )
                    recovered = dict(value)
                    recovered.setdefault("source", _record_source(value) if value.get("source") else "provider_metadata")
                    recovered.setdefault("provider", _record_provider(record))
                    recovered["recall_expansion"] = expansion
                    expansion_records.append(recovered)
                    attempts.append(
                        {
                            "status": "recovered",
                            "candidate_key": candidate_key,
                            "title": recovered.get("title"),
                            "doi": recovered.get("doi"),
                            "expansion_kind": expansion_kind,
                            "source_field": source_field,
                            "source_candidate": _candidate_identity(seed),
                            "evidence": expansion["evidence"],
                        }
                    )

    recovered_count = len(expansion_records)
    return {
        "schema_version": RECALL_GAP_RECORD_SCHEMA_VERSION,
        "policy": (
            "Provider metadata can recover official versions, related papers, cited-by papers, "
            "or references; generic web search is not a primary recall path."
        ),
        "summary": {
            "seed_count": len(candidates),
            "attempted": len(attempts),
            "recovered": recovered_count,
            "duplicates": len([item for item in attempts if item.get("status") == "duplicate_existing_candidate"]),
            "insufficient_identity": len([item for item in attempts if item.get("status") == "insufficient_identity"]),
        },
        "attempts": attempts,
        "expansion_records": expansion_records,
    }


def annotate_recall_expansion_candidates(
    candidates: list[dict[str, Any]],
    recall_record: dict[str, Any],
) -> list[dict[str, Any]]:
    expansions: dict[str, dict[str, Any]] = {}
    for record in recall_record.get("expansion_records") or []:
        if not isinstance(record, dict):
            continue
        key = _candidate_key(record)
        expansion = record.get("recall_expansion")
        if isinstance(expansion, dict):
            expansions[key] = expansion
    annotated: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        expansion = expansions.get(_candidate_key(item))
        if expansion:
            item["recall_expansion"] = expansion
        annotated.append(item)
    return annotated


def _truthy_risk_value(value: object, risk_type: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, dict):
        for key in ("status", "state", "value", "verified"):
            if key in value and _truthy_risk_value(value.get(key), risk_type):
                return True
        return False
    text = _text(value).lower()
    if not text:
        return False
    if text in {"false", "no", "none", "null", "clear", "clean", "not_retracted", "not retracted"}:
        return False
    risk_tokens = {
        "retracted": ("retracted", "retraction"),
        "withdrawn": ("withdrawn", "withdrawal"),
        "expression_of_concern": ("expression of concern", "eoc"),
        "paper_mill": ("paper mill", "papermill"),
        "predatory_venue": ("predatory",),
    }
    return any(token in text for token in risk_tokens[risk_type]) or text in {"true", "yes", "verified", "confirmed"}


def _risk_type_from_text(text: str) -> str | None:
    normalized = text.lower()
    for risk_type in RISK_TYPE_ORDER:
        if _truthy_risk_value(normalized, risk_type):
            return risk_type
    return None


def _risk_evidence_from_existing_quality_risk(
    *,
    record: dict[str, Any],
    field_path: str,
    value: dict[str, Any],
) -> list[dict[str, Any]]:
    risk_types = value.get("risk_types")
    if isinstance(risk_types, str):
        risk_types = [risk_types]
    if not isinstance(risk_types, list):
        risk_type = _risk_type_from_text(" ".join(str(item) for item in value.values()))
        risk_types = [risk_type] if risk_type else []
    status = _text(value.get("status")).lower()
    confidence = _text(value.get("confidence")).lower() or "medium"
    verified = status == "verified" or confidence == "high"
    return [
        {
            "risk_type": str(risk_type),
            "status": "verified" if verified else "suspected",
            "confidence": "high" if verified else confidence,
            "source": _record_source(record),
            "provider": _record_provider(record),
            "field": field_path,
            "value": _compact_value(value),
        }
        for risk_type in risk_types
        if risk_type
    ]


def _collect_risk_evidence(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for context_path, record in _iter_record_contexts(candidate):
        existing = record.get("quality_risk")
        if isinstance(existing, dict):
            evidence.extend(
                _risk_evidence_from_existing_quality_risk(
                    record=record,
                    field_path=f"{context_path}.quality_risk",
                    value=existing,
                )
            )
        for risk_type, aliases in RISK_FIELD_ALIASES.items():
            for alias in aliases:
                if alias not in record:
                    continue
                value = record.get(alias)
                if not _truthy_risk_value(value, risk_type):
                    continue
                evidence.append(
                    {
                        "risk_type": risk_type,
                        "status": "verified",
                        "confidence": "high",
                        "source": _record_source(record),
                        "provider": _record_provider(record),
                        "field": f"{context_path}.{alias}",
                        "value": _compact_value(value),
                    }
                )
        for flags_field in ("risk_flags", "risk", "risks", "integrity_flags"):
            flags = record.get(flags_field)
            if flags is None:
                continue
            values = flags if isinstance(flags, list) else [flags]
            for flag in values:
                text = " ".join(str(item) for item in flag.values()) if isinstance(flag, dict) else _text(flag)
                risk_type = _risk_type_from_text(text)
                if not risk_type:
                    continue
                lowered = text.lower()
                verified = any(marker in lowered for marker in ("verified", "confirmed", "retracted", "withdrawn"))
                evidence.append(
                    {
                        "risk_type": risk_type,
                        "status": "verified" if verified else "suspected",
                        "confidence": "high" if verified else "medium",
                        "source": _record_source(record),
                        "provider": _record_provider(record),
                        "field": f"{context_path}.{flags_field}",
                        "value": _compact_value(flag),
                    }
                )
    return evidence


def _quality_risk_from_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = _collect_risk_evidence(candidate)
    if not evidence:
        return {
            "schema_version": QUALITY_RISK_SCHEMA_VERSION,
            "status": "unverified",
            "severity": "unknown",
            "confidence": "none",
            "risk_types": [],
            "evidence": [],
            "source": "not_available",
            "cautions": ["quality_risk_unverified"],
            "policy": "Missing provider risk evidence is unverified, not proof of safety.",
        }

    verified = [item for item in evidence if item.get("status") == "verified"]
    status = "verified" if verified else "suspected"
    risk_types: list[str] = []
    for risk_type in RISK_TYPE_ORDER:
        if any(item.get("risk_type") == risk_type for item in evidence):
            risk_types.append(risk_type)
    severe = bool(verified)
    cautions = [
        f"verified_quality_risk:{risk_type}" if status == "verified" else f"unverified_quality_risk_hint:{risk_type}"
        for risk_type in risk_types
    ]
    return {
        "schema_version": QUALITY_RISK_SCHEMA_VERSION,
        "status": status,
        "severity": "severe" if severe else "warning",
        "confidence": "high" if verified else "medium",
        "risk_types": risk_types,
        "evidence": evidence[:10],
        "source": "provider_metadata",
        "cautions": cautions,
        "policy": "Verified severe risk evidence lowers ranking eligibility; weak or missing evidence creates cautions only.",
    }


def enrich_candidates_with_quality_risk(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        risk = _quality_risk_from_evidence(candidate)
        item = dict(candidate)
        item["quality_risk"] = risk
        enriched.append(item)
        items.append(
            {
                "slug": item.get("slug"),
                "title": item.get("title"),
                "doi": item.get("doi"),
                "arxiv_id": item.get("arxiv_id"),
                "quality_risk": risk,
            }
        )
    summary = {
        "total": len(items),
        "verified": len([item for item in items if item["quality_risk"].get("status") == "verified"]),
        "suspected": len([item for item in items if item["quality_risk"].get("status") == "suspected"]),
        "unverified": len([item for item in items if item["quality_risk"].get("status") == "unverified"]),
        "severe": len([item for item in items if item["quality_risk"].get("severity") == "severe"]),
    }
    return enriched, {
        "schema_version": QUALITY_RISK_RECORD_SCHEMA_VERSION,
        "policy": "Missing risk metadata remains unverified; verified severe provider evidence lowers recommendation eligibility.",
        "summary": summary,
        "items": items,
    }
