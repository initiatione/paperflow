from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from epi.artifacts import file_sha256, raw_paper_root, staging_paper_root, utc_now, write_json_atomic
from epi.paper_gate import build_paper_gate
from epi.source_artifacts import is_mineru_markdown_artifact, source_first_artifacts
from epi.wiki_language import formal_page_language_issues, language_policy_is_reviewed
from epi.wiki_ingest_approval import human_approval_record_path, validate_human_approval_record
from epi.wiki_contracts import (
    formal_frontmatter_schema,
    formal_page_family_names,
    page_lifecycle_states,
    required_wiki_skills,
    research_review_fields,
    wiki_deposition_quality_gates,
)


_INTERNAL_VAULT_ROOTS = {"_epi", "_raw", "_staging", "_runs", "_quarantine", ".git", ".obsidian"}
FINAL_SOURCE_REVIEW_SCHEMA_VERSION = "epi-final-source-review-v1"
_AUDIT_PAGE_MARKERS = [
    "Source-Grounded Claim Cards",
    "Support status summary",
    "reader/claim-support.json",
    "reader/evidence-map.json",
    "Evidence claims tracked:",
    "Suggested Wiki Routes",
    "Wiki Ingest Brief",
    "stage: staging",
    "formal_page: false",
]
_OBSIDIAN_WIKILINK_SOURCE_PDF_PATTERN = re.compile(
    r"\[\[_epi/raw/(?P<slug>[^/\]\|]+)/paper\.pdf\|(?P<alias>[^\]]+)\]\]",
    re.IGNORECASE,
)
_OBSIDIAN_URI_SOURCE_PDF_PATTERN = re.compile(
    r"\[[^\]]+\]\(obsidian://open\?[^)]*file=_epi%2Fraw%2F(?P<slug>[^%/)]+)%2Fpaper\.pdf(?:[&#][^)]*)?\)",
    re.IGNORECASE,
)
PRW_RECORD_REQUEST_SCHEMA_VERSION = "prw-record-request-v1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _gate_check_names(gate: dict[str, Any], conclusion: str) -> list[str]:
    return [
        str(run.get("name"))
        for run in gate.get("check_suite", {}).get("check_runs", [])
        if run.get("conclusion") == conclusion
    ]


def _gate_check(gate: dict[str, Any], name: str) -> dict[str, Any]:
    for run in gate.get("check_suite", {}).get("check_runs", []):
        if run.get("name") == name:
            return run if isinstance(run, dict) else {}
    return {}


def _ensure_gate_allows_record(gate: dict[str, Any]) -> None:
    failure_checks = _gate_check_names(gate, "failure")
    if failure_checks:
        raise ValueError("paper gate has failure checks: " + ", ".join(failure_checks))

    next_action = gate.get("next_action")
    if next_action not in {"run-wiki-ingest-agent", "review-recorded-wiki-pages"}:
        raise ValueError(
            "record-wiki-ingest requires paper-gate next_action=run-wiki-ingest-agent; "
            f"got {next_action or 'unknown'}"
        )

    action_required = _gate_check_names(gate, "action_required")
    unresolved = [name for name in action_required if name != "human-approval"]
    if unresolved:
        raise ValueError("paper gate has unresolved action-required checks: " + ", ".join(unresolved))


def _is_agent_mediated_plan(plan: dict[str, Any]) -> bool:
    return (
        plan.get("handoff_type") == "agent-mediated-wiki-ingest"
        or plan.get("wiki_write_model") == "agent-mediated-vault-contract"
        or plan.get("wiki_write_model") == "wiki-skill-batch-distillation"
    )


def _resolve_page(vault_path: Path, page: str) -> dict[str, Any]:
    value = str(page or "").strip()
    if not value:
        raise ValueError("page path must not be empty")

    normalized = value.replace("\\", "/")
    parsed = PurePosixPath(normalized)
    if ".." in parsed.parts:
        raise ValueError(f"page path must not contain '..': {page}")

    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (vault_path / candidate).resolve()
    try:
        relative_path = resolved.relative_to(vault_path)
    except ValueError as exc:
        raise ValueError(f"page path must stay inside vault: {page}") from exc

    if not relative_path.parts:
        raise ValueError("page path must point to a file inside the vault")
    if relative_path.parts[0] in _INTERNAL_VAULT_ROOTS:
        raise ValueError(f"recorded final wiki page must not be under {relative_path.parts[0]}: {page}")
    if resolved.suffix.lower() != ".md":
        raise ValueError(f"recorded final wiki page must be a Markdown file: {page}")
    if not resolved.is_file():
        raise FileNotFoundError(f"recorded final wiki page does not exist: {resolved}")
    text = resolved.read_text(encoding="utf-8", errors="ignore")
    _validate_formal_page_shape(relative_path.as_posix(), text)

    return {
        "path": str(resolved),
        "relative_path": relative_path.as_posix(),
        "sha256": file_sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _slug_pseudo_route_patterns(slug: str) -> set[str]:
    return {
        f"concepts/{slug}-concept.md",
        f"synthesis/{slug}-synthesis.md",
        f"reports/{slug}-reading-report.md",
    }


def _frontmatter_block(text: str) -> tuple[dict[str, Any], str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end_index = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return None
    frontmatter: dict[str, Any] = {}
    current_map_key: str | None = None
    current_nested_key: str | None = None
    for raw_line in lines[1:end_index]:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  ") and current_map_key:
            nested = raw_line.strip()
            if raw_line.startswith("    ") and current_nested_key:
                if nested.startswith("- "):
                    nested_map = frontmatter.get(current_map_key)
                    if not isinstance(nested_map, dict):
                        nested_map = {}
                        frontmatter[current_map_key] = nested_map
                    current_value = nested_map.get(current_nested_key)
                    if not isinstance(current_value, list):
                        current_value = []
                        nested_map[current_nested_key] = current_value
                    current_value.append(_strip_frontmatter_scalar(nested[2:].strip()))
                    continue
            if nested.startswith("- "):
                value = _strip_frontmatter_scalar(nested[2:].strip())
                current_value = frontmatter.get(current_map_key)
                if not isinstance(current_value, list):
                    current_value = []
                    frontmatter[current_map_key] = current_value
                current_value.append(value)
                continue
            if ":" in nested:
                key, value = nested.split(":", 1)
                nested_map = frontmatter.get(current_map_key)
                if not isinstance(nested_map, dict):
                    nested_map = {}
                    frontmatter[current_map_key] = nested_map
                if isinstance(nested_map, dict):
                    nested_key = key.strip()
                    nested_value = value.strip()
                    nested_map[nested_key] = nested_value
                    current_nested_key = nested_key if not nested_value else None
            continue
        if ":" not in raw_line or raw_line[0].isspace():
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        frontmatter[key] = value
        current_map_key = key if not value else None
        current_nested_key = None
    body = "\n".join(lines[end_index + 1 :])
    return frontmatter, body


def _frontmatter_value_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return False
    text = str(value).strip()
    return text in {"", "[]", "{}", "null", "None"}


def _frontmatter_value_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _strip_frontmatter_scalar(value: str) -> str:
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _split_inline_frontmatter_list(value: str) -> list[str]:
    text = str(value).strip()
    if not (text.startswith("[") and text.endswith("]")):
        return [_strip_frontmatter_scalar(text)]
    if text.startswith("[[") and text.endswith("]]"):
        return [_strip_frontmatter_scalar(text)]

    inner = text[1:-1].strip()
    if not inner:
        return []
    entries: list[str] = []
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
            entry = _strip_frontmatter_scalar("".join(token))
            if entry:
                entries.append(entry)
            token = []
            continue
        token.append(char)
    entry = _strip_frontmatter_scalar("".join(token))
    if entry:
        entries.append(entry)
    return entries


def _frontmatter_source_entries(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_strip_frontmatter_scalar(str(item)) for item in value if _strip_frontmatter_scalar(str(item))]
    return _split_inline_frontmatter_list(str(value))


def _formal_source_pdf_link_issues(value: Any) -> list[str]:
    entries = _frontmatter_source_entries(value)
    if not entries:
        return [
            "formal page frontmatter sources must include an Obsidian source PDF link"
        ]

    valid = [
        entry
        for entry in entries
        if _OBSIDIAN_WIKILINK_SOURCE_PDF_PATTERN.fullmatch(entry)
        or _OBSIDIAN_URI_SOURCE_PDF_PATTERN.fullmatch(entry)
    ]
    invalid_non_pdf = [
        entry
        for entry in entries
        if not _OBSIDIAN_WIKILINK_SOURCE_PDF_PATTERN.fullmatch(entry)
        and not _OBSIDIAN_URI_SOURCE_PDF_PATTERN.fullmatch(entry)
    ]

    issues: list[str] = []
    if not valid:
        issues.append(
            "formal page frontmatter sources must include an Obsidian source PDF link"
        )
    if invalid_non_pdf:
        issues.append(
            "formal page frontmatter sources must contain only Obsidian source PDF links"
        )
    return issues


def _validate_formal_frontmatter(relative_path: str, text: str) -> list[str]:
    parsed = _frontmatter_block(text)
    if parsed is None:
        return ["formal page frontmatter is missing"]
    frontmatter, _body = parsed
    schema = formal_frontmatter_schema()
    required_fields = [str(field) for field in schema.get("required_fields") or []]
    missing = [field for field in required_fields if field not in frontmatter]
    issues: list[str] = []
    if missing:
        issues.append("formal page frontmatter is missing required fields: " + ", ".join(missing))
    non_empty_required = [
        "title",
        "category",
        "page_family",
        "tags",
        "sources",
        "summary",
        "provenance",
        "base_confidence",
        "lifecycle",
        "lifecycle_changed",
        "tier",
        "created",
        "updated",
    ]
    empty = [
        field
        for field in non_empty_required
        if field in frontmatter and _frontmatter_value_is_empty(frontmatter.get(field))
    ]
    if empty:
        issues.append("formal page frontmatter has empty required fields: " + ", ".join(empty))
    if "sources" in frontmatter and not _frontmatter_value_is_empty(frontmatter.get("sources")):
        issues.extend(_formal_source_pdf_link_issues(frontmatter.get("sources")))
    provenance = frontmatter.get("provenance") if isinstance(frontmatter.get("provenance"), dict) else {}
    missing_provenance = [
        field
        for field in schema.get("provenance_required_fields") or []
        if field not in provenance
    ]
    if missing_provenance:
        issues.append("formal page frontmatter provenance is incomplete: " + ", ".join(missing_provenance))
    family = relative_path.replace("\\", "/").split("/", 1)[0]
    if family not in formal_page_family_names():
        issues.append("formal page must be under one EPI page family: " + ", ".join(formal_page_family_names()))
    for field in ["category", "page_family"]:
        if str(frontmatter.get(field) or "").strip().strip('"') != family:
            issues.append(f"formal page frontmatter {field} must match page family {family}")
    lifecycle = str(frontmatter.get("lifecycle") or "").strip().strip('"')
    allowed_lifecycles = [str(item) for item in schema.get("allowed_lifecycle_values") or []]
    allowed_initial = [str(item) for item in schema.get("initial_lifecycle_values") or []]
    if lifecycle and lifecycle not in set(allowed_lifecycles).union(allowed_initial):
        issues.append("formal page frontmatter lifecycle is not allowed: " + lifecycle)
    return issues


def _validate_family_content(relative_path: str, text: str) -> list[str]:
    normalized = relative_path.replace("\\", "/")
    family = normalized.split("/", 1)[0]
    lower_text = text.lower()
    issues: list[str] = []
    gates = wiki_deposition_quality_gates()
    forbidden_languages = gates.get("forbidden_fenced_formula_languages") or []
    for language in forbidden_languages:
        if f"```{language}" in lower_text:
            issues.append(f"formal page uses forbidden fenced formula block: ```{language}")
    if "[[" not in text and gates.get("wikilinks_required"):
        issues.append("formal page must use Obsidian wikilinks for internal knowledge")
    if family == "derivations":
        if "variable" not in lower_text and "变量" not in text:
            issues.append("derivations page must include variable definitions")
        if "derivation" not in lower_text and "推导" not in text:
            issues.append("derivations page must include a derivation chain")
    if family == "references":
        required_topics = {
            "model_or_method": ("model", "method", "模型", "方法"),
            "formula": ("formula", "equation", "公式"),
            "experiment_or_metric": ("experiment", "metric", "实验", "指标"),
            "limitations": ("limitation", "caveat", "限制", "局限"),
        }
        missing_topics = [
            name
            for name, needles in required_topics.items()
            if not any(needle in lower_text or needle in text for needle in needles)
        ]
        if missing_topics:
            issues.append("references page must include model/method, formula, experiment/metric, and limitations")
    if family == "synthesis" and "matrix" not in lower_text and "矩阵" not in text and "|" not in text:
        issues.append("synthesis page must include a cross-paper comparison matrix")
    return issues


def _validate_formal_page_shape(relative_path: str, text: str) -> None:
    normalized = relative_path.replace("\\", "/")
    marker_hits = [marker for marker in _AUDIT_PAGE_MARKERS if marker in text]
    if marker_hits:
        raise ValueError(
            "recorded final wiki page looks like an EPI audit/staging artifact: "
            + normalized
            + " markers="
            + ", ".join(marker_hits[:3])
        )
    if normalized.startswith("reports/") and normalized.endswith("-reading-report.md"):
        raise ValueError("recorded final wiki page must not be an EPI reading report: " + normalized)
    if normalized.startswith("concepts/") and normalized.endswith("-concept.md"):
        raise ValueError("recorded final wiki page must not be an EPI per-paper routes or pseudo concept page: " + normalized)
    if normalized.startswith("synthesis/") and normalized.endswith("-synthesis.md"):
        raise ValueError("recorded final wiki page must not be an EPI per-paper routes or pseudo synthesis page: " + normalized)
    issues = [
        *_validate_formal_frontmatter(normalized, text),
        *_validate_family_content(normalized, text),
        *formal_page_language_issues(text),
    ]
    if issues:
        raise ValueError("formal page validation failed for " + normalized + ": " + "; ".join(issues))


def _source_first_confirmed(brief: dict[str, Any]) -> bool:
    source_bundle = brief.get("source_bundle") if isinstance(brief.get("source_bundle"), dict) else {}
    raw_artifacts = "\n".join(str(item) for item in source_bundle.get("raw_artifacts") or [])
    formula_figure_review = (
        source_bundle.get("formula_figure_review")
        if isinstance(source_bundle.get("formula_figure_review"), dict)
        else {}
    )
    formula_figure_text = "\n".join(str(item) for item in formula_figure_review.values()).lower()
    return any(is_mineru_markdown_artifact(artifact) for artifact in source_bundle.get("raw_artifacts") or []) and all(
        artifact in raw_artifacts
        for artifact in [
            "mineru/paper.tex",
            "mineru/images/*",
            "mineru/mineru-manifest.json",
        ]
    ) and all(token in formula_figure_text for token in ["formula", "figure", "image"])


def _resolve_review_candidate(value: str, *, vault_path: Path, staging_root: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] in {"_epi", "_staging", "_raw"}:
        return vault_path / candidate
    staging_candidate = staging_root / candidate
    if staging_candidate.exists() or len(candidate.parts) == 1:
        return staging_candidate
    return vault_path / candidate


def _resolve_final_source_review_path(
    *,
    vault_path: Path,
    staging_root: Path,
    contract: dict[str, Any],
    source_review_path: str | Path | None,
) -> Path | None:
    if source_review_path:
        return _resolve_review_candidate(str(source_review_path), vault_path=vault_path, staging_root=staging_root)

    suggested = str(contract.get("suggested_output_path") or "").strip()
    candidates = []
    if suggested:
        candidates.append(_resolve_review_candidate(suggested, vault_path=vault_path, staging_root=staging_root))
    candidates.append(staging_root / "final-source-review.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _resolve_vault_file(vault_path: Path, value: str | Path, *, description: str) -> tuple[Path, str]:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{description} path must not be empty")
    candidate = Path(text)
    resolved = candidate.resolve() if candidate.is_absolute() else (vault_path / candidate).resolve()
    try:
        relative_path = resolved.relative_to(vault_path).as_posix()
    except ValueError as exc:
        raise ValueError(f"{description} path must stay inside vault: {value}") from exc
    return resolved, relative_path


def _load_prw_record_request(vault_path: Path, request_path: str | Path) -> tuple[dict[str, Any], Path, str]:
    resolved, relative_path = _resolve_vault_file(vault_path, request_path, description="PRW record request")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"missing PRW record request: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"PRW record request is invalid JSON: {resolved}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"PRW record request must be a JSON object: {resolved}")
    return payload, resolved, relative_path


def _request_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"PRW record request must include {key} object")
    return value


def _request_string(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"PRW record request must include {key}")
    return value


def _validate_prw_request_pages(vault_path: Path, payload: dict[str, Any]) -> list[str]:
    final_pages = payload.get("final_pages")
    if not isinstance(final_pages, list) or not final_pages:
        raise ValueError("PRW record request must include final_pages[]")
    pages: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(final_pages, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"PRW record request final_pages[{index}] must be an object")
        relative_path = str(item.get("relative_path") or item.get("path") or "").replace("\\", "/").strip()
        if not relative_path:
            raise ValueError(f"PRW record request final_pages[{index}] must include relative_path")
        expected_hash = str(item.get("sha256") or "").strip()
        if not expected_hash:
            raise ValueError(f"PRW record request final_pages[{index}] must include sha256")
        page_record = _resolve_page(vault_path, relative_path)
        if page_record["relative_path"] in seen:
            raise ValueError("PRW record request duplicate final page: " + page_record["relative_path"])
        seen.add(page_record["relative_path"])
        if page_record["sha256"] != expected_hash:
            raise ValueError("PRW record request final page sha256 mismatch: " + page_record["relative_path"])
        pages.append(page_record["relative_path"])
    return pages


def _validate_prw_request_source_review(
    *,
    vault_path: Path,
    staging_root: Path,
    payload: dict[str, Any],
) -> Path:
    final_source_review = _request_dict(payload, "final_source_review")
    source_review_path = _resolve_review_candidate(
        str(final_source_review.get("path") or ""),
        vault_path=vault_path,
        staging_root=staging_root,
    )
    if not source_review_path.is_file():
        raise FileNotFoundError(f"missing PRW record request final source review: {source_review_path}")
    expected_hash = str(final_source_review.get("sha256") or "").strip()
    if not expected_hash:
        raise ValueError("PRW record request final_source_review must include sha256")
    actual_hash = file_sha256(source_review_path)
    if actual_hash != expected_hash:
        raise ValueError("PRW record request final-source-review sha256 mismatch: " + str(source_review_path))
    return source_review_path


def _prw_source_request_metadata(
    *,
    payload: dict[str, Any],
    request_path: Path,
    relative_path: str,
) -> dict[str, Any]:
    metadata = {
        "schema_version": payload.get("schema_version"),
        "request_id": payload.get("request_id"),
        "status": payload.get("status"),
        "automation_mode": payload.get("automation_mode") or "ask",
        "path": str(request_path),
        "relative_path": relative_path,
        "sha256": file_sha256(request_path),
    }
    for key in ["recommended_command", "correction_id"]:
        if payload.get(key):
            metadata[key] = payload.get(key)
    if isinstance(payload.get("prw_task"), dict):
        metadata["prw_task"] = payload.get("prw_task")
    return metadata


def create_wiki_ingest_record_from_prw_request(
    vault_path: Path,
    request_path: str | Path,
    *,
    notes: str | None = None,
) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    payload, resolved_request_path, relative_request_path = _load_prw_record_request(vault_path, request_path)
    if payload.get("schema_version") != PRW_RECORD_REQUEST_SCHEMA_VERSION:
        raise ValueError("PRW record request has unsupported schema_version")
    if payload.get("status") != "ready_for_epi_record":
        raise ValueError("PRW record request status must be ready_for_epi_record")
    slug = _request_string(payload, "paper_slug")
    staging_root = staging_paper_root(vault_path, slug)
    pages = _validate_prw_request_pages(vault_path, payload)
    source_review_path = _validate_prw_request_source_review(
        vault_path=vault_path,
        staging_root=staging_root,
        payload=payload,
    )
    human_approval = _request_dict(payload, "human_approval")
    approved_by = str(human_approval.get("approved_by") or "").strip()
    if not approved_by:
        raise ValueError("PRW record request human_approval must include approved_by")
    source_request = _prw_source_request_metadata(
        payload=payload,
        request_path=resolved_request_path,
        relative_path=relative_request_path,
    )
    return create_wiki_ingest_record(
        vault_path,
        slug,
        pages,
        approved_by=approved_by,
        notes=notes,
        source_review_path=source_review_path,
        source_request=source_request,
    )


def _read_required_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"missing final source review: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"final source review is invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"final source review must be a JSON object: {path}")
    return payload


def _review_records_by_artifact(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records = payload.get("reviewed_artifacts")
    if not isinstance(records, list):
        return {}, ["final source review must include reviewed_artifacts[]"]
    by_artifact: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            failures.append(f"reviewed_artifacts[{index}] must be an object")
            continue
        artifact = str(record.get("artifact") or "").strip()
        if not artifact:
            failures.append(f"reviewed_artifacts[{index}] is missing artifact")
            continue
        if artifact in by_artifact:
            failures.append(f"duplicate final source review artifact: {artifact}")
            continue
        by_artifact[artifact] = record
    return by_artifact, failures


def _validate_review_status(record: dict[str, Any], artifact: str, failures: list[str]) -> None:
    if record.get("status") != "reviewed":
        failures.append(f"final source review artifact must be status=reviewed: {artifact}")


def _validate_file_artifact(
    *,
    paper_root: Path,
    artifact: str,
    record: dict[str, Any],
    failures: list[str],
) -> None:
    _validate_review_status(record, artifact, failures)
    artifact_path = paper_root / artifact
    if not artifact_path.is_file():
        failures.append(f"required source artifact is missing on disk: {artifact}")
        return
    actual_hash = file_sha256(artifact_path)
    if record.get("sha256") != actual_hash:
        failures.append(f"final source review sha256 mismatch: {artifact}")


def _validate_image_artifact(
    *,
    paper_root: Path,
    record: dict[str, Any],
    failures: list[str],
) -> None:
    artifact = "mineru/images/*"
    _validate_review_status(record, artifact, failures)
    image_dir = paper_root / "mineru" / "images"
    image_files = sorted(path for path in image_dir.rglob("*") if path.is_file()) if image_dir.exists() else []
    if record.get("file_count") != len(image_files):
        failures.append("final source review image file_count does not match mineru/images")
    reviewed_files = record.get("files") if isinstance(record.get("files"), list) else []
    reviewed_by_path = {
        str(item.get("relative_path") or item.get("path") or "").replace("\\", "/"): item
        for item in reviewed_files
        if isinstance(item, dict)
    }
    for image_path in image_files:
        relative = image_path.relative_to(paper_root).as_posix()
        reviewed = reviewed_by_path.get(relative)
        if not reviewed:
            failures.append(f"final source review missing image hash: {relative}")
            continue
        if reviewed.get("sha256") != file_sha256(image_path):
            failures.append(f"final source review image sha256 mismatch: {relative}")


def _validate_review_section(payload: dict[str, Any], key: str, failures: list[str]) -> None:
    section = payload.get(key) if isinstance(payload.get(key), dict) else {}
    if section.get("status") != "reviewed":
        failures.append(f"final source review {key} must be status=reviewed")
    if not str(section.get("summary") or "").strip():
        failures.append(f"final source review {key} must include a summary")


def _validate_pdf_fallback_section(payload: dict[str, Any], failures: list[str]) -> None:
    section = payload.get("pdf_fallback_review") if isinstance(payload.get("pdf_fallback_review"), dict) else {}
    if section.get("status") not in {"reviewed", "not-needed"}:
        failures.append("final source review pdf_fallback_review must be status=reviewed or not-needed")
    if not str(section.get("summary") or "").strip():
        failures.append("final source review pdf_fallback_review must include a summary")


def _validate_final_page_provenance(
    *,
    payload: dict[str, Any],
    page_records: list[dict[str, Any]],
    failures: list[str],
) -> None:
    provenance = payload.get("final_page_provenance")
    if not isinstance(provenance, list):
        failures.append("final source review must include final_page_provenance[]")
        return
    provenance_by_path = {
        str(item.get("relative_path") or "").replace("\\", "/"): item
        for item in provenance
        if isinstance(item, dict)
    }
    for page in page_records:
        relative_path = str(page.get("relative_path") or "").replace("\\", "/")
        item = provenance_by_path.get(relative_path)
        if not item:
            failures.append(f"final source review missing final page provenance: {relative_path}")
            continue
        if item.get("source_grounded") is not True:
            failures.append(f"final page provenance must be source_grounded=true: {relative_path}")
        if item.get("sha256") and item.get("sha256") != page.get("sha256"):
            failures.append(f"final page provenance sha256 mismatch: {relative_path}")


def _validate_wiki_batch_ingest_section(payload: dict[str, Any], slug: str, failures: list[str]) -> None:
    section = payload.get("wiki_batch_ingest") if isinstance(payload.get("wiki_batch_ingest"), dict) else {}
    if section.get("status") != "completed":
        failures.append("final source review wiki_batch_ingest must be status=completed")
    skills = "\n".join(str(item) for item in section.get("wiki_skill_used") or section.get("skills_used") or [])
    for skill in required_wiki_skills():
        if skill not in skills:
            failures.append(f"final source review wiki_batch_ingest must record {skill} skill usage")
    optional_helpers = section.get("optional_helpers_used") or []
    if optional_helpers and not isinstance(optional_helpers, list):
        failures.append("final source review wiki_batch_ingest optional_helpers_used must be a list")
    paper_slugs = [str(item) for item in section.get("paper_slugs") or []]
    if slug not in paper_slugs:
        failures.append("final source review wiki_batch_ingest must include the recorded paper slug")


def _validate_research_review_sections(payload: dict[str, Any], failures: list[str]) -> None:
    for field in research_review_fields():
        _validate_review_section(payload, field, failures)
    lifecycle = payload.get("page_lifecycle") if isinstance(payload.get("page_lifecycle"), dict) else {}
    status = str(lifecycle.get("status") or "").strip()
    if status not in page_lifecycle_states():
        failures.append("final source review page_lifecycle status must be an allowed lifecycle state")
    allowed_states = [str(item) for item in lifecycle.get("allowed_states") or []]
    if allowed_states != page_lifecycle_states():
        failures.append("final source review page_lifecycle must record allowed lifecycle states")
    if not str(lifecycle.get("summary") or "").strip():
        failures.append("final source review page_lifecycle must include a summary")


def _validate_formal_content_quality_section(payload: dict[str, Any], failures: list[str]) -> None:
    section = (
        payload.get("formal_content_quality")
        if isinstance(payload.get("formal_content_quality"), dict)
        else {}
    )
    if section.get("status") != "reviewed":
        failures.append("final source review formal_content_quality must be status=reviewed")
    if section.get("audit_pages_excluded") is not True:
        failures.append("final source review formal_content_quality must set audit_pages_excluded=true")
    if not language_policy_is_reviewed(section):
        failures.append(
            "final source review formal_content_quality must include language_policy.chinese_body_default=true"
        )
    if not str(section.get("summary") or "").strip():
        failures.append("final source review formal_content_quality must include a summary")


def _validate_final_source_review(
    *,
    source_review_path: Path,
    paper_root: Path,
    slug: str,
    page_records: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = _read_required_json(source_review_path)
    failures: list[str] = []
    expected_source_artifacts = source_first_artifacts(paper_root)
    if payload.get("schema_version") != FINAL_SOURCE_REVIEW_SCHEMA_VERSION:
        failures.append("final source review has unsupported schema_version")
    if payload.get("paper_slug") and payload.get("paper_slug") != slug:
        failures.append("final source review paper_slug does not match record slug")

    by_artifact, artifact_failures = _review_records_by_artifact(payload)
    failures.extend(artifact_failures)
    for artifact in expected_source_artifacts:
        record = by_artifact.get(artifact)
        if not record:
            failures.append(f"final source review missing required artifact: {artifact}")
            continue
        if artifact == "mineru/images/*":
            _validate_image_artifact(paper_root=paper_root, record=record, failures=failures)
        else:
            _validate_file_artifact(
                paper_root=paper_root,
                artifact=artifact,
                record=record,
                failures=failures,
            )

    _validate_review_section(payload, "formula_review", failures)
    _validate_review_section(payload, "figure_table_image_review", failures)
    _validate_pdf_fallback_section(payload, failures)
    _validate_wiki_batch_ingest_section(payload, slug, failures)
    _validate_research_review_sections(payload, failures)
    _validate_formal_content_quality_section(payload, failures)
    _validate_final_page_provenance(payload=payload, page_records=page_records, failures=failures)

    if failures:
        raise ValueError("final source review failed validation: " + "; ".join(failures))
    return payload


def create_wiki_ingest_record(
    vault_path: Path,
    slug: str,
    pages: list[str],
    *,
    approved_by: str,
    notes: str | None = None,
    source_review_path: str | Path | None = None,
    source_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    if not str(approved_by or "").strip():
        raise ValueError("human gate approval is required for record-wiki-ingest")
    if not pages:
        raise ValueError("at least one final wiki page must be recorded")
    pseudo_routes = _slug_pseudo_route_patterns(slug)
    requested_relative_pages = {
        str(page).replace("\\", "/").strip()
        for page in pages
        if str(page).replace("\\", "/").strip()
    }
    blocked_requested_routes = sorted(pseudo_routes.intersection(requested_relative_pages))
    if blocked_requested_routes:
        raise ValueError(
            "recorded final wiki pages must come from wiki-skill batch deposition, not EPI per-paper routes: "
            + ", ".join(blocked_requested_routes)
        )

    paper_root = raw_paper_root(vault_path, slug)
    staging_root = staging_paper_root(vault_path, slug)
    plan_path = staging_root / "promotion-plan.json"
    plan = _read_json(plan_path)
    if not plan:
        raise FileNotFoundError(f"missing promotion plan: {plan_path}")
    if not _is_agent_mediated_plan(plan):
        raise ValueError("record-wiki-ingest only supports agent-mediated wiki ingest plans")

    brief_path = Path(plan.get("wiki_ingest_brief_path") or staging_root / "wiki-ingest-brief.json")
    brief = _read_json(brief_path)
    if not brief:
        raise FileNotFoundError(f"missing wiki ingest brief: {brief_path}")

    gate = build_paper_gate(vault_path, slug)
    _ensure_gate_allows_record(gate)
    approval_valid, approval_record, approval_issues = validate_human_approval_record(
        vault_path,
        slug,
        approved_by=approved_by,
        require_existing=True,
    )
    if not approval_valid:
        raise ValueError("; ".join(approval_issues))
    assert approval_record is not None

    page_records = [_resolve_page(vault_path, page) for page in pages]
    blocked_resolved_routes = sorted(
        pseudo_routes.intersection(str(record["relative_path"]).replace("\\", "/") for record in page_records)
    )
    if blocked_resolved_routes:
        raise ValueError(
            "recorded final wiki pages must come from wiki-skill batch deposition, not EPI per-paper routes: "
            + ", ".join(blocked_resolved_routes)
        )
    seen: set[str] = set()
    duplicates = []
    for record in page_records:
        relative = record["relative_path"]
        if relative in seen:
            duplicates.append(relative)
        seen.add(relative)
    if duplicates:
        raise ValueError("duplicate final wiki page records: " + ", ".join(duplicates))

    source_review_contract = (
        brief.get("final_source_review_contract")
        if isinstance(brief.get("final_source_review_contract"), dict)
        else {}
    )
    resolved_source_review_path = _resolve_final_source_review_path(
        vault_path=vault_path,
        staging_root=staging_root,
        contract=source_review_contract,
        source_review_path=source_review_path,
    )
    source_review_payload: dict[str, Any] | None = None
    if resolved_source_review_path and resolved_source_review_path.exists():
        source_review_payload = _validate_final_source_review(
            source_review_path=resolved_source_review_path,
            paper_root=paper_root,
            slug=slug,
            page_records=page_records,
        )
    elif source_review_contract.get("required"):
        raise ValueError(
            "final source review is required before record-wiki-ingest: "
            + str(resolved_source_review_path or staging_root / "final-source-review.json")
        )
    source_first_verified_by_source_review = source_review_payload is not None
    source_bundle_gate = _gate_check(gate, "source-bundle")
    source_bundle_audit = (
        source_bundle_gate.get("details")
        if isinstance(source_bundle_gate.get("details"), dict)
        else {}
    )
    source_bundle_verified_by_gate = (
        source_bundle_gate.get("conclusion") == "success"
        and source_bundle_audit.get("complete") is True
    )
    if source_first_verified_by_source_review:
        source_first_verification_method = "final-source-review-json"
    elif source_bundle_verified_by_gate:
        source_first_verification_method = "paper-gate-source-bundle-audit"
    else:
        source_first_verification_method = "brief-contract-only"

    recorded_at = utc_now()
    failure_checks = _gate_check_names(gate, "failure")
    action_required_checks = _gate_check_names(gate, "action_required")
    human_gate_decision = {
        "status": "approved",
        "approved_by": str(approval_record.get("approved_by") or approved_by).strip(),
        "approved_at": approval_record.get("approved_at") or recorded_at,
        "approval_scope": approval_record.get("scope") or "run-wiki-ingest-agent",
        "prewrite_approval_record": str(human_approval_record_path(vault_path, slug)),
    }
    if notes:
        human_gate_decision["notes"] = notes
    elif approval_record.get("notes"):
        human_gate_decision["notes"] = approval_record.get("notes")

    if source_review_payload is not None:
        final_source_review_record: dict[str, Any] = {
            "status": "verified",
            "path": str(resolved_source_review_path),
            "schema_version": source_review_payload.get("schema_version"),
            "reviewed_artifacts": source_review_payload.get("reviewed_artifacts") or [],
            "formula_review": source_review_payload.get("formula_review") or {},
            "figure_table_image_review": source_review_payload.get("figure_table_image_review") or {},
            "pdf_fallback_review": source_review_payload.get("pdf_fallback_review") or {},
            "wiki_batch_ingest": source_review_payload.get("wiki_batch_ingest") or {},
            "formal_content_quality": source_review_payload.get("formal_content_quality") or {},
            "final_page_provenance": source_review_payload.get("final_page_provenance") or [],
            "page_lifecycle": source_review_payload.get("page_lifecycle") or {},
        }
        for field in research_review_fields():
            final_source_review_record[field] = source_review_payload.get(field) or {}
    else:
        final_source_review_record = {
            "status": "missing",
            "required": bool(source_review_contract.get("required")),
        }

    record_payload = {
        "schema_version": "epi-wiki-ingest-record-v1",
        "stage": "record-wiki-ingest",
        "status": "recorded",
        "paper_slug": slug,
        "title": brief.get("title") or gate.get("title") or slug,
        "recorded_at": recorded_at,
        "vault_path": str(vault_path),
        "compiled_wiki_write": False,
        "record_only": True,
        "final_pages_modified_by_epi": False,
        "wiki_write_model": plan.get("wiki_write_model") or "agent-mediated-vault-contract",
        "handoff_type": plan.get("handoff_type") or brief.get("handoff_type"),
        "final_page_authority": plan.get("final_page_authority"),
        "source_first_confirmed": (
            source_first_verified_by_source_review
            or source_bundle_verified_by_gate
            or _source_first_confirmed(brief)
        ),
        "source_first_verification_method": source_first_verification_method,
        "final_source_review": final_source_review_record,
        "human_gate_decision": human_gate_decision,
        "paper_gate": {
            "status": gate.get("status"),
            "next_action": gate.get("next_action"),
            "conclusion": gate.get("check_suite", {}).get("conclusion"),
            "failure_checks": failure_checks,
            "action_required_checks": action_required_checks,
            "source_bundle": source_bundle_audit,
        },
        "paths": {
            "paper_root": str(paper_root),
            "staging_root": str(staging_root),
            "promotion_plan": str(plan_path),
            "wiki_ingest_brief": str(brief_path),
            "human_approval": str(human_approval_record_path(vault_path, slug)),
            "agent_handoff_paths": plan.get("agent_handoff_paths") or [],
        },
        "page_records": page_records,
        "page_paths": [record["path"] for record in page_records],
        "relative_page_paths": [record["relative_path"] for record in page_records],
        "ingest_policy": brief.get("ingest_policy") if isinstance(brief.get("ingest_policy"), dict) else {},
        "source_bundle": brief.get("source_bundle") if isinstance(brief.get("source_bundle"), dict) else {},
        "wiki_rule_source_model": (
            brief.get("wiki_rule_source_model")
            if isinstance(brief.get("wiki_rule_source_model"), dict)
            else {}
        ),
    }
    if source_review_payload is not None and resolved_source_review_path is not None:
        record_payload["paths"]["final_source_review"] = str(resolved_source_review_path)
    if notes:
        record_payload["notes"] = notes
    if source_request is not None:
        record_payload["source_request"] = source_request

    raw_record_path = paper_root / "wiki-ingest-record.json"
    staging_record_path = staging_root / "wiki-ingest-record.json"
    record_payload["record_paths"] = {
        "raw": str(raw_record_path),
        "staging": str(staging_record_path),
    }
    write_json_atomic(raw_record_path, record_payload)
    write_json_atomic(staging_record_path, record_payload)
    return record_payload
