from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from paper_source.artifacts import json_sha256, paper_source_root, utc_now, write_json_atomic, write_text_atomic

SCHEMA_VERSION = "paper-source-research-brief-v1"
STATUS_VALUES = {"draft", "confirmed", "superseded"}
REVIEW_POLICY_VALUES = {"exclude", "include", "mixed"}
OUTPUT_GOAL_VALUES = {
    "reading_priority_list",
    "source_staging_candidates",
    "literature_review_seed",
    "topic_tracking_seed",
    "fact_check_sources",
}
SOURCE_SCOPE_VALUES = {
    "paper_search_mcp_default",
    "paper_search_mcp_oa_priority",
    "known_paper_lookup",
    "venue_or_publisher_targeted",
    "manual_sources_provided",
}

_SLUG_RE = re.compile(r"^\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*$")
_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")
_REQUIRED_TEXT_FIELDS = ("slug", "title", "task", "domain_scope")
_REQUIRED_LIST_FIELDS = ("specific_questions", "keywords")
_OPTIONAL_LIST_FIELDS = ("exclusions", "unknowns")


class ResearchBriefValidationError(ValueError):
    """Raised when a Research Brief payload is incomplete or unsafe."""


def research_briefs_root(vault_path: Path) -> Path:
    return paper_source_root(Path(vault_path)) / "research-briefs"


def validate_slug(slug: str) -> str:
    value = str(slug or "").strip()
    if not value:
        raise ResearchBriefValidationError("slug is required")
    if not _SLUG_RE.fullmatch(value):
        raise ResearchBriefValidationError(
            f"slug must follow YYYYMMDD-<topic> lowercase ASCII kebab-case with single hyphen separators: {value}"
        )
    return value


def _require_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ResearchBriefValidationError(f"{field} is required")
    return value


def _require_list(payload: dict[str, Any], field: str, *, allow_empty: bool = False) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list):
        raise ResearchBriefValidationError(f"{field} must be a list")
    normalized = [str(item).strip() for item in value if str(item).strip()]
    if not allow_empty and not normalized:
        raise ResearchBriefValidationError(f"{field} must not be empty")
    return normalized


def _require_typed_mapping(
    payload: dict[str, Any],
    field: str,
    *,
    allowed_values: set[str],
) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ResearchBriefValidationError(f"{field} must be an object")
    type_value = str(value.get("type") or "").strip()
    if type_value not in allowed_values:
        raise ResearchBriefValidationError(f"{field}.type must be one of {sorted(allowed_values)}")
    normalized = copy.deepcopy(value)
    normalized["type"] = type_value
    if "notes" in normalized:
        normalized["notes"] = str(normalized.get("notes") or "")
    return normalized


def _content_hash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    content = copy.deepcopy(payload)
    content.pop("content_hash", None)
    return content


def _with_content_hash(payload: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result["content_hash"] = json_sha256(_content_hash_payload(result))
    return result


def validate_research_brief_payload(payload: dict[str, Any], *, formal_use: bool = False) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ResearchBriefValidationError("payload must be an object")

    normalized = copy.deepcopy(payload)
    if normalized.get("schema_version") not in (None, SCHEMA_VERSION):
        raise ResearchBriefValidationError("schema_version is not supported")
    normalized["slug"] = validate_slug(normalized.get("slug", ""))

    for field in _REQUIRED_TEXT_FIELDS:
        if field == "slug":
            continue
        normalized[field] = _require_text(normalized, field)

    status = str(normalized.get("status") or "").strip()
    if status not in STATUS_VALUES:
        raise ResearchBriefValidationError(f"status must be one of {sorted(STATUS_VALUES)}")
    if formal_use and status != "confirmed":
        raise ResearchBriefValidationError("status must be confirmed for formal use")
    normalized["status"] = status

    for field in _REQUIRED_LIST_FIELDS:
        normalized[field] = _require_list(normalized, field)
    for field in _OPTIONAL_LIST_FIELDS:
        normalized[field] = _require_list(normalized, field, allow_empty=True)

    normalized["review_policy"] = _require_typed_mapping(
        normalized,
        "review_policy",
        allowed_values=REVIEW_POLICY_VALUES,
    )
    normalized["source_scope"] = _require_typed_mapping(
        normalized,
        "source_scope",
        allowed_values=SOURCE_SCOPE_VALUES,
    )
    normalized["output_goal"] = _require_typed_mapping(
        normalized,
        "output_goal",
        allowed_values=OUTPUT_GOAL_VALUES,
    )

    field_sources = normalized.get("field_sources")
    if not isinstance(field_sources, dict):
        raise ResearchBriefValidationError("field_sources must be an object")
    normalized["field_sources"] = copy.deepcopy(field_sources)

    if "content_hash" in normalized:
        expected_hash = json_sha256(_content_hash_payload(normalized))
        if normalized["content_hash"] != expected_hash:
            raise ResearchBriefValidationError("content_hash does not match payload")

    return normalized


def _validate_persisted_research_brief_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ResearchBriefValidationError("payload must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ResearchBriefValidationError(f"schema_version must be {SCHEMA_VERSION}")

    content_hash = payload.get("content_hash")
    if not isinstance(content_hash, str) or not content_hash:
        raise ResearchBriefValidationError("content_hash is required")
    expected_hash = json_sha256(_content_hash_payload(payload))
    if content_hash != expected_hash:
        raise ResearchBriefValidationError("content_hash does not match payload")

    return validate_research_brief_payload(payload)


def _new_payload(answers: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
    validated = validate_research_brief_payload(answers)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": validated["status"],
        "slug": validated["slug"],
        "title": validated["title"],
        "task": validated["task"],
        "domain_scope": validated["domain_scope"],
        "specific_questions": validated["specific_questions"],
        "keywords": validated["keywords"],
        "exclusions": validated["exclusions"],
        "review_policy": validated["review_policy"],
        "source_scope": validated["source_scope"],
        "output_goal": validated["output_goal"],
        "unknowns": validated["unknowns"],
        "field_sources": validated["field_sources"],
        "revision_number": 1,
        "created_at": timestamp,
        "updated_at": timestamp,
        "supersedes_hash": None,
    }
    return _with_content_hash(payload)


def _revised_payload(
    current: dict[str, Any],
    answers: dict[str, Any],
    *,
    timestamp: str,
) -> dict[str, Any]:
    validated = validate_research_brief_payload(answers)
    if validated["slug"] != current["slug"]:
        raise ResearchBriefValidationError("slug cannot change during revision")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": validated["status"],
        "slug": validated["slug"],
        "title": validated["title"],
        "task": validated["task"],
        "domain_scope": validated["domain_scope"],
        "specific_questions": validated["specific_questions"],
        "keywords": validated["keywords"],
        "exclusions": validated["exclusions"],
        "review_policy": validated["review_policy"],
        "source_scope": validated["source_scope"],
        "output_goal": validated["output_goal"],
        "unknowns": validated["unknowns"],
        "field_sources": validated["field_sources"],
        "revision_number": int(current.get("revision_number") or 1) + 1,
        "created_at": current["created_at"],
        "updated_at": timestamp,
        "supersedes_hash": current["content_hash"],
    }
    return _with_content_hash(payload)


def _safe_timestamp_for_filename(value: str) -> str:
    return _FILENAME_SAFE_RE.sub("-", value).strip("-")


def _render_research_brief_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['title']}",
        "",
        f"状态：{payload['status']}",
        f"标识：{payload['slug']}",
        f"修订版本：{payload['revision_number']}",
        "",
        "## 任务",
        payload["task"],
        "",
        "## 领域范围",
        payload["domain_scope"],
        "",
        "## 具体问题",
    ]
    lines.extend(f"- {question}" for question in payload["specific_questions"])
    lines.extend(["", "## 关键词"])
    lines.extend(f"- {keyword}" for keyword in payload["keywords"])
    if payload["exclusions"]:
        lines.extend(["", "## 排除项"])
        lines.extend(f"- {exclusion}" for exclusion in payload["exclusions"])
    if payload["unknowns"]:
        lines.extend(["", "## 未确认事项"])
        lines.extend(f"- {unknown}" for unknown in payload["unknowns"])
    lines.extend(["", "## 策略", f"- 评审策略：{payload['review_policy']['type']}"])
    lines.append(f"- 来源范围：{payload['source_scope']['type']}")
    lines.append(f"- 输出目标：{payload['output_goal']['type']}")
    lines.append("")
    return "\n".join(lines)


def _render_agent_brief_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Research Brief",
        "",
        f"Title: {payload['title']}",
        f"Status: {payload['status']}",
        f"Task: {payload['task']}",
        f"Domain scope: {payload['domain_scope']}",
        "",
        "## Use",
        "- Treat this as a Paper Source task-scoped artifact.",
        "- Do not treat this as a Paper Wiki handoff or Research Profile.",
        "",
    ]
    return "\n".join(lines)


def research_brief_metadata(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    json_path = Path(path)
    formal_use_eligible = payload.get("status") == "confirmed"
    return {
        "json_path": str(json_path),
        "brief_dir": str(json_path.parent),
        "slug": payload.get("slug"),
        "status": payload.get("status"),
        "revision_number": payload.get("revision_number"),
        "hash": payload.get("content_hash"),
        "formal_use_eligible": formal_use_eligible,
    }


def _write_research_brief_artifacts(brief_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    revisions_dir = brief_dir / "revisions"
    json_path = brief_dir / "research-brief.json"
    markdown_path = brief_dir / "research-brief.md"
    agent_brief_path = brief_dir / "agent-brief.md"

    revisions_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(json_path, payload)
    write_text_atomic(markdown_path, _render_research_brief_markdown(payload))
    write_text_atomic(agent_brief_path, _render_agent_brief_markdown(payload))

    metadata = research_brief_metadata(json_path, payload)
    metadata.update(
        {
            "markdown_path": str(markdown_path),
            "agent_brief_path": str(agent_brief_path),
            "revisions_dir": str(revisions_dir),
            "payload": payload,
        }
    )
    return metadata


def create_research_brief(vault_path: Path, answers: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or utc_now()
    payload = _new_payload(answers, timestamp=timestamp)
    brief_dir = research_briefs_root(Path(vault_path)) / payload["slug"]
    if (brief_dir / "research-brief.json").exists():
        raise ResearchBriefValidationError(f"research brief already exists: {brief_dir / 'research-brief.json'}")
    return _write_research_brief_artifacts(brief_dir, payload)


def load_research_brief(path: Path, *, allow_draft: bool = False) -> dict[str, Any]:
    json_path = Path(path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    validated = _validate_persisted_research_brief_payload(payload)
    status = validated["status"]
    if status == "draft":
        if not allow_draft:
            raise ResearchBriefValidationError("draft research brief requires allow_draft=True")
    elif status != "confirmed":
        raise ResearchBriefValidationError("status must be confirmed for formal use")
    metadata = research_brief_metadata(json_path, validated)
    metadata.update({"payload": validated, "allow_draft": allow_draft})
    return metadata


def revise_research_brief(path: Path, answers: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or utc_now()
    json_path = Path(path)
    current = load_research_brief(json_path, allow_draft=True)["payload"]
    revised = _revised_payload(current, answers, timestamp=timestamp)

    revisions_dir = json_path.parent / "revisions"
    snapshot_name = (
        f"{_safe_timestamp_for_filename(timestamp)}-"
        f"r{current['revision_number']:03d}-research-brief.json"
    )
    write_json_atomic(revisions_dir / snapshot_name, current)
    return _write_research_brief_artifacts(json_path.parent, revised)
