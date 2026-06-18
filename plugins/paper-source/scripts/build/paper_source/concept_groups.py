from __future__ import annotations

import re
from typing import Any

from paper_source.lexical_match import matched_terms, term_matches_text


REQUIRED_CONCEPT_GROUPS_SCHEMA_VERSION = "paper-source-required-concept-groups-v1"


def unique_nonempty_strings(values: list[object] | tuple[object, ...] | None, *, split_commas: bool = False) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    kept: list[str] = []
    for value in values:
        candidates = str(value).split(",") if split_commas else [str(value)]
        for candidate in candidates:
            item = " ".join(candidate.strip().split())
            normalized = item.lower()
            if not item or normalized in seen:
                continue
            seen.add(normalized)
            kept.append(item)
    return kept


def _strings_from_nested(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return unique_nonempty_strings([value], split_commas=True)
    if isinstance(value, dict):
        terms: list[str] = []
        for key, item in value.items():
            normalized_key = str(key).strip().lower().replace("-", "_")
            if normalized_key in {
                "id",
                "label",
                "name",
                "source",
                "role",
                "required",
                "schema_version",
                "policy",
            }:
                continue
            terms.extend(_strings_from_nested(item))
        return unique_nonempty_strings(terms)
    if isinstance(value, (list, tuple, set)):
        terms: list[str] = []
        for item in value:
            terms.extend(_strings_from_nested(item))
        return unique_nonempty_strings(terms)
    return unique_nonempty_strings([value], split_commas=True)


def _group_id(value: object, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or fallback


def _group_terms(group: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in ("terms", "keywords", "anchors", "synonyms", "phrases", "values"):
        terms.extend(_strings_from_nested(group.get(key)))
    return unique_nonempty_strings(terms)


def normalize_required_concept_groups(value: object, *, source: str | None = None) -> list[dict[str, Any]]:
    raw_groups: list[object] = []
    if isinstance(value, dict):
        if value.get("schema_version") == REQUIRED_CONCEPT_GROUPS_SCHEMA_VERSION and isinstance(value.get("groups"), list):
            raw_groups = list(value.get("groups") or [])
        else:
            for key, item in value.items():
                if key in {"schema_version", "policy"}:
                    continue
                if isinstance(item, dict):
                    raw_groups.append({"id": key, **item})
                else:
                    raw_groups.append({"id": key, "terms": _strings_from_nested(item)})
    elif isinstance(value, list):
        raw_groups = list(value)

    groups: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_group in enumerate(raw_groups, start=1):
        if isinstance(raw_group, str):
            group = {"id": raw_group, "label": raw_group, "terms": [raw_group]}
        elif isinstance(raw_group, dict):
            group = raw_group
        else:
            continue
        terms = _group_terms(group)
        if not terms:
            continue
        group_id = _group_id(group.get("id") or group.get("label") or group.get("name"), f"group_{index}")
        if group_id in seen:
            suffix = 2
            while f"{group_id}_{suffix}" in seen:
                suffix += 1
            group_id = f"{group_id}_{suffix}"
        seen.add(group_id)
        normalized = {
            "id": group_id,
            "label": str(group.get("label") or group.get("name") or group_id).strip() or group_id,
            "required": bool(group.get("required", True)),
            "terms": terms,
        }
        if group.get("source") or source:
            normalized["source"] = str(group.get("source") or source)
        groups.append(normalized)
    return groups


def _term_overlaps_any(term: str, terms: list[str]) -> bool:
    return any(term_matches_text(term, other) or term_matches_text(other, term) for other in terms)


def derive_required_concept_groups(
    *,
    hard_domain_anchors: list[str],
    task_terms: list[str],
    trusted_task_terms: list[str] | None = None,
    topic: str,
    source: str,
) -> list[dict[str, Any]]:
    anchors = unique_nonempty_strings(hard_domain_anchors)
    if not anchors:
        return []
    topic_text = str(topic or "")
    task_candidates: list[str] = []
    for term in unique_nonempty_strings(trusted_task_terms):
        if _term_overlaps_any(term, anchors):
            continue
        task_candidates.append(term)
    for term in unique_nonempty_strings(task_terms):
        if _term_overlaps_any(term, anchors):
            continue
        if _term_overlaps_any(term, task_candidates):
            continue
        if not term_matches_text(term, topic_text):
            continue
        task_candidates.append(term)
    task_candidates = task_candidates[:6]
    if not task_candidates:
        return []
    return [
        {
            "id": "target_object",
            "label": "target object",
            "required": True,
            "terms": anchors,
            "source": source,
        },
        {
            "id": "task_problem",
            "label": "task or problem",
            "required": True,
            "terms": task_candidates,
            "source": source,
        },
    ]


def required_concept_groups_from_query_plan(query_plan: dict | None) -> list[dict[str, Any]]:
    if not isinstance(query_plan, dict):
        return []
    groups = normalize_required_concept_groups(query_plan.get("required_concept_groups"))
    blocks = query_plan.get("concept_blocks") if isinstance(query_plan.get("concept_blocks"), dict) else {}
    groups.extend(normalize_required_concept_groups(blocks.get("required_concept_groups")))
    hard_constraints = query_plan.get("hard_constraints")
    if isinstance(hard_constraints, dict):
        groups.extend(normalize_required_concept_groups(hard_constraints.get("required_concept_groups")))

    seen: set[tuple[str, tuple[str, ...]]] = set()
    unique_groups: list[dict[str, Any]] = []
    for group in groups:
        marker = (str(group.get("id")), tuple(str(term).lower() for term in group.get("terms") or []))
        if marker in seen:
            continue
        seen.add(marker)
        unique_groups.append(group)
    return unique_groups


def required_concept_group_contract(groups: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": REQUIRED_CONCEPT_GROUPS_SCHEMA_VERSION,
        "groups": groups,
        "policy": "Each required group must match title, abstract, venue, or safe metadata before primary recommendation eligibility.",
    }


def evaluate_required_concept_groups(groups: list[dict[str, Any]], haystack: object) -> dict[str, Any]:
    normalized_groups = normalize_required_concept_groups(groups)
    group_results: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for group in normalized_groups:
        terms = [str(term) for term in group.get("terms") or []]
        hits = matched_terms(haystack, terms)
        required = bool(group.get("required", True))
        matched = bool(hits) or not required
        group_id = str(group.get("id") or group.get("label"))
        group_results[group_id] = {
            "label": group.get("label") or group_id,
            "required": required,
            "terms": terms,
            "matched": matched,
            "matched_terms": hits,
        }
        if group.get("source"):
            group_results[group_id]["source"] = group.get("source")
        if required and not hits:
            missing.append(group_id)
    return {
        "schema_version": REQUIRED_CONCEPT_GROUPS_SCHEMA_VERSION,
        "groups": group_results,
        "passed": not missing,
        "missing_required_groups": missing,
    }
