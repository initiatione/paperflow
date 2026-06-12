from __future__ import annotations

import argparse
import hashlib
import importlib
import sys
import json
import re
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


SKIP_DIR_NAMES = {
    "formal-page-snapshots",
    "legacy-imports",
    "wiki-rebuild-audits",
    "config-history",
    "invalidated-human-gates",
    "premature-formal-pages",
    "reviews",
    "migrations",
    "raw-cleanup",
    "repository-maintenance",
    "wiki-reset",
    "manual-candidates",
    "record-corrections",
}

ACTIVE_ARTIFACT_TOP_LEVEL_DIRS = {
    "manifest.json",
    "meta",
    "policies",
    "staging",
}

ACTIVE_RUN_FILE_NAMES = {
    "dashboard.md",
    "dashboard-failures.md",
    "dashboard-human-gate.md",
    "dashboard-recent-success.md",
    "index.json",
    "research-queue.json",
    "research-queue.md",
    "run-state.json",
}

ACTIVE_RAW_SIDECAR_FILE_NAMES = {
    "code-verification.json",
    "run-state.json",
    "wiki-ingest-record.json",
}

FORMAL_ROOTS = (
    "references",
    "concepts",
    "derivations",
    "experiments",
    "synthesis",
    "reports",
    "opportunities",
)

RENAME_PATHS = {
    "reports\\auv-control-epi-batch-reading-map.md": "reports\\auv-control-reading-map.md",
    "reports\\auv-planning-and-cooperation-epi-reading-map.md": "reports\\auv-planning-and-cooperation-reading-map.md",
    "opportunities\\auv-control-research-opportunities-from-epi-batch.md": "opportunities\\auv-control-research-opportunities.md",
    "reports/auv-control-epi-batch-reading-map.md": "reports/auv-control-reading-map.md",
    "reports/auv-planning-and-cooperation-epi-reading-map.md": "reports/auv-planning-and-cooperation-reading-map.md",
    "opportunities/auv-control-research-opportunities-from-epi-batch.md": "opportunities/auv-control-research-opportunities.md",
    "reports\\auv-control-epi-batch-reading-map": "reports\\auv-control-reading-map",
    "reports\\auv-planning-and-cooperation-epi-reading-map": "reports\\auv-planning-and-cooperation-reading-map",
    "opportunities\\auv-control-research-opportunities-from-epi-batch": "opportunities\\auv-control-research-opportunities",
    "reports/auv-control-epi-batch-reading-map": "reports/auv-control-reading-map",
    "reports/auv-planning-and-cooperation-epi-reading-map": "reports/auv-planning-and-cooperation-reading-map",
    "opportunities/auv-control-research-opportunities-from-epi-batch": "opportunities/auv-control-research-opportunities",
}

STRING_REPLACEMENTS = (
    ("_epi\\", "_paper_source\\"),
    ("_epi/", "_paper_source/"),
    ("epi-paper-deposition", "paper-source-paper-deposition"),
    ("--from-prw-request", "--from-paper-wiki-request"),
    ("prw-record-request.json", "paper-wiki-record-request.json"),
    ("prw-record-request-v1", "paper-wiki-record-request-v1"),
    ("ready_for_epi_record", "ready_for_paper_source_record"),
    ("epi-wiki-ingest-brief-v1", "paper-source-wiki-ingest-brief-v1"),
    ("epi-wiki-ingest-record-v1", "paper-source-wiki-ingest-record-v1"),
    ("epi-final-source-review-v1", "paper-source-final-source-review-v1"),
    ("epi-final-source-review-contract-v1", "paper-source-final-source-review-contract-v1"),
    ("epi-human-approval-v1", "paper-source-human-approval-v1"),
    ("epi-wiki-agent-trigger-v1", "paper-source-wiki-agent-trigger-v1"),
    ("epi-source-bundle-audit-v1", "paper-source-source-bundle-audit-v1"),
    ("epi-code-verification-v1", "paper-source-code-verification-v1"),
    ("epi-zotero-record-v1", "paper-source-zotero-record-v1"),
    ("epi-wiki-deposition-task-v1", "paper-source-wiki-deposition-task-v1"),
    ("epi-wiki-deposition", "paper-source-paper-deposition"),
    ("awaiting-epi-record-wiki-ingest", "awaiting-paper-source-record-wiki-ingest"),
    ("epi-recorded", "paper-source-recorded"),
    ("draft -> review-needed -> source-reviewed -> under-review -> verified", "draft"),
    ("lifecycle=review-needed", "lifecycle=draft"),
    ("lifecycle remains review-needed", "lifecycle uses draft"),
    ("remain review-needed", "use lifecycle=draft"),
    ("remains review-needed", "uses lifecycle=draft"),
    ("review-needed", "draft"),
    ("codex-epi-config-setup", "codex-paper-source-config-setup"),
    ("qmd ls paper-research-wiki/_epi", "qmd ls paper-research-wiki/_paper_source"),
    ("qmd ls paper-research-wiki/_epi/meta/formal-page-snapshots", "qmd ls paper-research-wiki/_paper_source/meta/formal-page-snapshots"),
    (
        "it must ignore _epi/**, .obsidian/**, and .claude/**.",
        "it must ignore _paper_source/**, legacy _epi/**, .obsidian/**, and .claude/**.",
    ),
    (
        "Use QMD only with the paper-research-wiki qmd collection boundary: formal page families plus AGENTS.md, index.md, hot.md, log.md, and _meta/ contract pages may be indexed; _epi/**, .obsidian/**, and .claude/** must be ignored.",
        "Use QMD only with the paper-research-wiki qmd collection boundary: formal page families plus AGENTS.md, index.md, hot.md, log.md, and _meta/ contract pages may be indexed; _paper_source/**, legacy _epi/**, .obsidian/**, and .claude/** must be ignored.",
    ),
    ("legacy _paper_source/**", "legacy _epi/**"),
    ("legacy _paper_source/", "legacy _epi/"),
    (
        "Final wiki pages are created by wiki skill batch distillation, not by EPI staging.",
        "Final wiki pages are created by wiki skill batch distillation, not by Paper Source staging.",
    ),
    (
        "Markdown vault plus EPI source bundle; QMD/search indexes are retrieval aids only.",
        "Markdown vault plus Paper Source source bundle; QMD/search indexes are retrieval aids only.",
    ),
    (
        "Use the seven EPI research wiki families as appropriate:",
        "Use the seven formal research wiki families as appropriate:",
    ),
    (
        "paper-research-wiki (PRW plugin canonical paper wiki layer)",
        "paper-research-wiki (Paper Wiki canonical paper wiki layer)",
    ),
    (
        "canonical paper wiki workflow layer for EPI source bundles; epi-paper-deposition remains compatibility adapter",
        "canonical paper wiki workflow layer for Paper Source source bundles; paper-source-paper-deposition remains compatibility adapter",
    ),
    (
        "PRW refreshed formal pages/provenance under Paper Wiki 0.2.1 rules. EPI should consume this request with record-wiki-ingest after user approval.",
        "Paper Wiki refreshed formal pages/provenance under current rules. Paper Source should consume this request with record-wiki-ingest after user approval.",
    ),
    ("prw-", "paper-wiki-"),
    (
        "Formal pages are maintained by PRW; this source review records current formal page hashes after the 2026-06-08 graph-aware rebuild pass.",
        "Formal pages are maintained by Paper Wiki; this source review records current formal page hashes after the graph-aware rebuild pass.",
    ),
    (
        "Formal pages are readable Chinese-first wiki pages, not EPI staging reports, raw claim-card dumps, or path inventories.",
        "Formal pages are readable Chinese-first wiki pages, not Paper Source staging reports, raw claim-card dumps, or path inventories.",
    ),
    (
        "User approved batch EPI wiki deposition",
        "User approved batch Paper Source / Paper Wiki wiki deposition",
    ),
    (
        "existing Paper Source / Paper Source human-approval.json",
        "existing Paper Source / legacy human-approval.json",
    ),
    (
        "Default EPI mode for profile-driven paper discovery and ranking.",
        "Default Paper Source mode for profile-driven paper discovery and ranking.",
    ),
    ("# EPI Dry Run", "# Paper Source Dry Run"),
    ("collection: EPI", "collection: Paper Source"),
    ("meta/epi-config.yaml", "meta/paper-source-config.yaml"),
    ("meta/epi-config-state.json", "meta/paper-source-config-state.json"),
)

UPPERCASE_TOKEN_REPLACEMENTS = (
    (re.compile(r"\bPRW\b"), "Paper Wiki"),
    (re.compile(r"\bEPI\b"), "Paper Source"),
)

KEY_RENAMES = {
    "prw_task": "paper_wiki_task",
    "prw_record_request": "paper_wiki_record_request",
    "final_pages_modified_by_epi": "final_pages_modified_by_paper_source",
    "epi_write_scope": "paper_source_write_scope",
    "prw-record-request.json": "paper-wiki-record-request.json",
    "wiki_deposition_task_path": "legacy_wiki_deposition_task_path",
    "wiki_deposition_task": "legacy_wiki_deposition_task",
}

LIFECYCLE_LIST_KEYS = {
    "allowed_lifecycle_values",
    "allowed_states",
    "initial_lifecycle_values",
    "page_lifecycle_states",
}

LIFECYCLE_VALUE_KEYS = {"lifecycle", "status"}

DEDUP_LIST_KEYS = {"protected"}

LEGACY_QMD_FORBIDDEN_EXAMPLES_TO_DROP = (
    "_epi/meta/formal-page-snapshots/",
    "_epi/raw/<slug>/mineru/<slug>.md",
    "_epi/raw/<slug>/mineru/paper.md",
    "_epi/raw/<slug>/mineru/paper.tex",
    "_epi/staging/papers/<slug>/wiki-ingest-brief.json",
)

LEGACY_QMD_VERIFICATION_COMMANDS_TO_DROP = (
    "qmd ls paper-research-wiki/_epi",
)

REQUEST_SLUG_PATTERN = re.compile(
    r"_paper_source[/\\]staging[/\\]papers[/\\](?P<slug>[^/\\]+)[/\\]paper-wiki-record-request\.json",
    re.IGNORECASE,
)

TASK_ARCHIVE_REPLACEMENTS: dict[str, str] = {}


def _replace_known_paths(text: str) -> str:
    updated = text
    for old, new in TASK_ARCHIVE_REPLACEMENTS.items():
        updated = updated.replace(old, new)
    for old, new in STRING_REPLACEMENTS:
        updated = updated.replace(old, new)
    for old, new in RENAME_PATHS.items():
        updated = updated.replace(old, new)
    for pattern, replacement in UPPERCASE_TOKEN_REPLACEMENTS:
        updated = pattern.sub(replacement, updated)
    return updated


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _transform_request_payload(payload: dict[str, Any], *, already_rewritten: bool = False) -> dict[str, Any]:
    request = dict(payload) if already_rewritten else _rewrite_json(payload)
    slug = str(request.get("paper_slug") or "").strip()
    if not slug:
        for key in ("path", "relative_path", "recommended_command"):
            value = request.get(key)
            if not isinstance(value, str):
                continue
            match = REQUEST_SLUG_PATTERN.search(value.replace("--from-paper-wiki-request ", ""))
            if match:
                slug = match.group("slug")
                request["paper_slug"] = slug
                break
    if isinstance(request.get("request_id"), str):
        request_id = str(request["request_id"])
        if request_id.startswith("prw-"):
            request_id = request_id[4:]
        while request_id.startswith("paper-wiki-paper-wiki-"):
            request_id = request_id[len("paper-wiki-") :]
        request["request_id"] = request_id if request_id.startswith("paper-wiki-") else "paper-wiki-" + request_id
    request["schema_version"] = "paper-wiki-record-request-v1"
    request["status"] = "ready_for_paper_source_record"
    if slug:
        request["recommended_command"] = (
            "record-wiki-ingest --from-paper-wiki-request "
            f"_paper_source/staging/papers/{slug}/paper-wiki-record-request.json"
        )
    return request


def _rewrite_json(value: Any) -> Any:
    if isinstance(value, dict):
        rewritten: dict[str, Any] = {}
        for key, item in value.items():
            new_key = KEY_RENAMES.get(key, _replace_known_paths(key)) if isinstance(key, str) else key
            rewritten_item = _rewrite_json(item)
            if isinstance(new_key, str):
                if new_key in LIFECYCLE_LIST_KEYS and isinstance(rewritten_item, list):
                    rewritten_item = ["draft"]
                elif new_key in LIFECYCLE_VALUE_KEYS and rewritten_item == "draft":
                    rewritten_item = "draft"
                elif new_key in DEDUP_LIST_KEYS and isinstance(rewritten_item, list):
                    rewritten_item = _append_unique(rewritten_item, [])
            rewritten[new_key] = rewritten_item
        if (
            rewritten.get("automation_mode") == "ask"
            and (
                "paper_wiki_task" in rewritten
                or rewritten.get("schema_version") in {"prw-record-request-v1", "paper-wiki-record-request-v1"}
            )
            and any(key in rewritten for key in ("paper_slug", "path", "relative_path", "recommended_command"))
        ):
            return _transform_request_payload(rewritten, already_rewritten=True)
        return rewritten
    if isinstance(value, list):
        return [_rewrite_json(item) for item in value]
    if isinstance(value, str):
        return _replace_known_paths(value)
    return value


def _append_unique(items: list[Any], additions: list[Any]) -> list[Any]:
    updated: list[Any] = []
    for item in items:
        if item not in updated:
            updated.append(item)
    for item in additions:
        if item not in updated:
            updated.append(item)
    return updated


def _drop_items(items: list[Any], blocked: tuple[str, ...]) -> list[Any]:
    blocked_set = set(blocked)
    return [item for item in items if item not in blocked_set]


def _preserve_manifest_legacy_markers(payload: dict[str, Any]) -> None:
    qmd_policy = payload.get("qmd_collection_policy")
    if isinstance(qmd_policy, dict):
        ignore_patterns = qmd_policy.get("ignore_patterns")
        if isinstance(ignore_patterns, list):
            qmd_policy["ignore_patterns"] = _append_unique(
                ignore_patterns,
                ["_paper_source/**", "_epi/**", ".obsidian/**", ".claude/**"],
            )
        forbidden_examples = qmd_policy.get("forbidden_examples")
        if isinstance(forbidden_examples, list):
            qmd_policy["forbidden_examples"] = _drop_items(
                forbidden_examples,
                LEGACY_QMD_FORBIDDEN_EXAMPLES_TO_DROP,
            )
        verification_commands = qmd_policy.get("verification_commands")
        if isinstance(verification_commands, list):
            qmd_policy["verification_commands"] = _drop_items(
                verification_commands,
                LEGACY_QMD_VERIFICATION_COMMANDS_TO_DROP,
            )
    if "legacy_internal_root" in payload:
        payload["legacy_internal_root"] = "_epi"


def _preserve_nested_legacy_markers(value: Any) -> None:
    if isinstance(value, dict):
        _preserve_manifest_legacy_markers(value)
        for item in value.values():
            _preserve_nested_legacy_markers(item)
    elif isinstance(value, list):
        for item in value:
            _preserve_nested_legacy_markers(item)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_vault_path(vault: Path, value: str | Path | None) -> Path | None:
    if value is None or not str(value).strip():
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    return vault / path


def _page_lifecycle(page: Path) -> str | None:
    for line in page.read_text(encoding="utf-8").splitlines()[:80]:
        stripped = line.strip()
        if stripped.startswith("lifecycle:"):
            return stripped.partition(":")[2].strip().strip('"').strip("'")
    return None


def _formal_page_records(vault: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for root in FORMAL_ROOTS:
        root_path = vault / root
        if not root_path.exists():
            continue
        for page in sorted(root_path.rglob("*.md")):
            relative = page.relative_to(vault).as_posix()
            records[relative] = {
                "path": str(page),
                "relative_path": relative,
                "page_path": relative,
                "page_family": relative.split("/", 1)[0],
                "sha256": _file_sha256(page),
                "size_bytes": page.stat().st_size,
                "lifecycle": _page_lifecycle(page),
            }
    return records


def _refresh_live_page_references(value: Any, page_records: dict[str, dict[str, Any]]) -> bool:
    changed = False
    if isinstance(value, dict):
        relative = value.get("relative_path") or value.get("page_path")
        if isinstance(relative, str) and relative in page_records:
            record = page_records[relative]
            for key in ("sha256", "size_bytes"):
                if key in value and value.get(key) != record[key]:
                    value[key] = record[key]
                    changed = True
            if "path" in value and value.get("path") != record["path"]:
                current = str(value.get("path") or "").replace("\\", "/")
                if current.endswith(relative) or current == relative:
                    value["path"] = record["path"]
                    changed = True
            if "lifecycle" in value and record.get("lifecycle") and value.get("lifecycle") != record["lifecycle"]:
                value["lifecycle"] = record["lifecycle"]
                changed = True
        for item in value.values():
            changed = _refresh_live_page_references(item, page_records) or changed
    elif isinstance(value, list):
        for item in value:
            changed = _refresh_live_page_references(item, page_records) or changed
    return changed


def _refresh_final_page_hash_maps(payload: Any, page_records: dict[str, dict[str, Any]]) -> bool:
    changed = False
    if isinstance(payload, dict):
        for key in ("input_artifact_hashes", "final_page_hashes"):
            mapping = payload.get(key)
            if isinstance(mapping, dict):
                for hash_key, current_hash in list(mapping.items()):
                    if not isinstance(hash_key, str) or not hash_key.startswith("final_page:"):
                        continue
                    relative = hash_key.split(":", 1)[1]
                    record = page_records.get(relative)
                    if record and current_hash != record["sha256"]:
                        mapping[hash_key] = record["sha256"]
                        changed = True
        for item in payload.values():
            changed = _refresh_final_page_hash_maps(item, page_records) or changed
    elif isinstance(payload, list):
        for item in payload:
            changed = _refresh_final_page_hash_maps(item, page_records) or changed
    return changed


def _refresh_artifact_hash_record(record: dict[str, Any], vault: Path) -> bool:
    path = _resolve_vault_path(vault, record.get("path"))
    if path is None or not path.exists() or not path.is_file():
        return False
    changed = False
    sha256 = _file_sha256(path)
    if record.get("sha256") != sha256:
        record["sha256"] = sha256
        changed = True
    size_bytes = path.stat().st_size
    if "size_bytes" in record and record.get("size_bytes") != size_bytes:
        record["size_bytes"] = size_bytes
        changed = True
    return changed


def _refresh_current_json_file(
    path: Path,
    *,
    vault: Path,
    page_records: dict[str, dict[str, Any]],
    execute: bool,
    extra_refresh=None,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    original = json.loads(json.dumps(payload, ensure_ascii=False))
    _refresh_live_page_references(payload, page_records)
    _refresh_final_page_hash_maps(payload, page_records)
    if extra_refresh is not None:
        extra_refresh(payload)
    if payload == original:
        return None
    if execute:
        _write_json(path, payload)
    return {"action": "rewrite", "path": str(path)}


def _load_stage_wiki_module():
    build_root = str(Path(__file__).resolve().parents[1])
    if build_root not in sys.path:
        sys.path.insert(0, build_root)
    return importlib.import_module("paper_source.stage_wiki")


def _archive_task_destination(legacy_root: Path, task_path: Path, staging_root: Path) -> Path:
    relative = task_path.relative_to(staging_root)
    return legacy_root / relative.with_name("paper-source-wiki-deposition-task-legacy.json")


def _refresh_task_archive_replacements(paper_source_root: Path) -> None:
    TASK_ARCHIVE_REPLACEMENTS.clear()
    staging_root = paper_source_root / "staging" / "papers"
    legacy_imports = paper_source_root / "meta" / "legacy-imports"
    if not legacy_imports.exists():
        return
    for archived in legacy_imports.rglob("paper-source-wiki-deposition-task-legacy.json"):
        slug = archived.parent.name
        legacy_staging_path = staging_root / slug / "wiki_deposition_task.json"
        TASK_ARCHIVE_REPLACEMENTS[str(legacy_staging_path)] = str(archived)
        TASK_ARCHIVE_REPLACEMENTS[
            str(legacy_staging_path).replace(str(paper_source_root.parent) + "\\", "").replace("\\", "/")
        ] = str(archived).replace(str(paper_source_root.parent) + "\\", "").replace("\\", "/")


def _archive_legacy_root_files(paper_source_root: Path, *, execute: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    archive_root = paper_source_root / "meta" / "legacy-imports" / f"{_utc_stamp()}-active-root-legacy"
    candidates = [
        paper_source_root / "README-legacy-1.md",
        paper_source_root / "manifest-legacy-1.json",
        paper_source_root / "meta" / "epi-config.yaml",
        paper_source_root / "meta" / "epi-config-state.json",
        paper_source_root / "meta" / "evidence-index-legacy-1.json",
    ]
    candidates.extend(sorted((paper_source_root / "policies").glob("*-legacy-1.*")))
    candidates.extend(sorted((paper_source_root / "staging" / "wiki-batches" / "pending").glob("*-legacy-1.*")))
    canonical_requirements = {
        paper_source_root / "meta" / "epi-config.yaml": paper_source_root / "meta" / "paper-source-config.yaml",
        paper_source_root / "meta" / "epi-config-state.json": paper_source_root / "meta" / "paper-source-config-state.json",
        paper_source_root / "policies" / "retention-legacy-1.json": paper_source_root / "policies" / "retention.json",
        paper_source_root
        / "staging"
        / "wiki-batches"
        / "pending"
        / "wiki-batch-ingest-brief-legacy-1.json": paper_source_root
        / "staging"
        / "wiki-batches"
        / "pending"
        / "wiki-batch-ingest-brief.json",
    }
    for source in candidates:
        if not source.exists():
            continue
        required = canonical_requirements.get(source)
        if required is not None and not required.exists():
            continue
        destination = archive_root / source.relative_to(paper_source_root)
        actions.append({"action": "move", "from": str(source), "to": str(destination)})
        if execute:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
    return actions


def _regenerate_staging_handoffs(
    paper_source_root: Path,
    *,
    execute: bool,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    staging_root = paper_source_root / "staging" / "papers"
    if not staging_root.exists():
        return actions
    legacy_root = paper_source_root / "meta" / "legacy-imports" / f"{_utc_stamp()}-wiki-deposition-task-files"
    stage_wiki = _load_stage_wiki_module()
    vault = paper_source_root.parent
    for task_path in sorted(staging_root.rglob("wiki_deposition_task.json")):
        paper_stage_root = task_path.parent
        slug = paper_stage_root.name
        paper_root = paper_source_root / "raw" / slug
        if not paper_root.exists():
            continue
        promotion_plan_path = paper_stage_root / "promotion-plan.json"
        workflow_mode = "fast-ingest"
        if promotion_plan_path.exists():
            try:
                workflow_mode = json.loads(promotion_plan_path.read_text(encoding="utf-8")).get("workflow_mode") or workflow_mode
            except json.JSONDecodeError:
                pass
        archive_path = _archive_task_destination(legacy_root, task_path, staging_root)
        actions.append({"action": "move", "from": str(task_path), "to": str(archive_path)})
        if execute:
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            task_payload = json.loads(task_path.read_text(encoding="utf-8"))
            task_payload = _rewrite_json(task_payload)
            _write_json(archive_path, task_payload)
            task_path.unlink()
            stage_wiki.stage_paper(vault, slug, paper_root, workflow_mode=workflow_mode, emit_legacy_deposition_task=False)
    return actions


def _is_active_artifact(path: Path, paper_source_root: Path) -> bool:
    if "legacy-1" in path.name:
        return False
    relative = path.relative_to(paper_source_root)
    if any(part in SKIP_DIR_NAMES for part in relative.parts):
        return False
    if len(relative.parts) >= 3 and relative.parts[0] == "raw":
        return len(relative.parts) == 3 and path.name in ACTIVE_RAW_SIDECAR_FILE_NAMES
    if relative.parts and relative.parts[0] not in ACTIVE_ARTIFACT_TOP_LEVEL_DIRS:
        if relative.parts[0] == "runs" and path.name in ACTIVE_RUN_FILE_NAMES:
            return True
        return False
    return True


def _migrate_root_manifest(vault: Path, *, execute: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    manifest_path = vault / ".manifest.json"
    if not manifest_path.exists():
        return actions
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return actions
    rewritten_payload = _rewrite_json(payload)
    if isinstance(rewritten_payload, dict):
        _preserve_nested_legacy_markers(rewritten_payload)
    if rewritten_payload != payload:
        actions.append({"action": "rewrite", "path": str(manifest_path)})
        if execute:
            _write_json(manifest_path, rewritten_payload)
    return actions


def _refresh_manifest_current_records(
    vault: Path,
    *,
    page_records: dict[str, dict[str, Any]],
    execute: bool,
) -> list[dict[str, Any]]:
    manifest_path = vault / ".manifest.json"
    action = _refresh_current_json_file(
        manifest_path,
        vault=vault,
        page_records=page_records,
        execute=execute,
    )
    return [action] if action else []


def _refresh_staging_record_chain(
    paper_source_root: Path,
    *,
    page_records: dict[str, dict[str, Any]],
    execute: bool,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    vault = paper_source_root.parent
    staging_root = paper_source_root / "staging" / "papers"
    if not staging_root.exists():
        return actions

    for paper_stage_root in sorted(path for path in staging_root.iterdir() if path.is_dir()):
        review_path = paper_stage_root / "final-source-review.json"
        request_path = paper_stage_root / "paper-wiki-record-request.json"
        staging_record_path = paper_stage_root / "wiki-ingest-record.json"
        raw_record_path = paper_source_root / "raw" / paper_stage_root.name / "wiki-ingest-record.json"

        review_action = _refresh_current_json_file(
            review_path,
            vault=vault,
            page_records=page_records,
            execute=execute,
        )
        if review_action:
            actions.append(review_action)

        review_hash = _file_sha256(review_path) if review_path.exists() and execute else None

        def refresh_request(payload: dict[str, Any]) -> None:
            if review_hash is not None and isinstance(payload.get("final_source_review"), dict):
                payload["final_source_review"]["sha256"] = review_hash

        request_action = _refresh_current_json_file(
            request_path,
            vault=vault,
            page_records=page_records,
            execute=execute,
            extra_refresh=refresh_request,
        )
        if request_action:
            actions.append(request_action)

        request_hash = _file_sha256(request_path) if request_path.exists() and execute else None

        def refresh_record(payload: dict[str, Any]) -> None:
            paths = payload.get("paths") if isinstance(payload.get("paths"), dict) else {}
            final_source_review = payload.get("final_source_review")
            if isinstance(final_source_review, dict):
                if review_hash is not None and paths.get("final_source_review"):
                    final_source_review["sha256"] = review_hash
            source_request = payload.get("source_request")
            if isinstance(source_request, dict):
                if request_hash is not None:
                    source_request["sha256"] = request_hash
                source_request["path"] = str(request_path)

        for record_path in (staging_record_path, raw_record_path):
            record_action = _refresh_current_json_file(
                record_path,
                vault=vault,
                page_records=page_records,
                execute=execute,
                extra_refresh=refresh_record,
            )
            if record_action:
                actions.append(record_action)
    return actions


def _refresh_current_record_hashes(vault: Path, *, execute: bool) -> list[dict[str, Any]]:
    paper_source_root = vault / "_paper_source"
    page_records = _formal_page_records(vault)
    actions: list[dict[str, Any]] = []
    actions.extend(_refresh_manifest_current_records(vault, page_records=page_records, execute=execute))
    actions.extend(_refresh_staging_record_chain(paper_source_root, page_records=page_records, execute=execute))
    return actions


def _migrate_config(meta_root: Path, *, execute: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    legacy_config = meta_root / "epi-config.yaml"
    legacy_state = meta_root / "epi-config-state.json"
    canonical_config = meta_root / "paper-source-config.yaml"
    canonical_state = meta_root / "paper-source-config-state.json"

    if legacy_config.exists():
        config_text = _replace_known_paths(legacy_config.read_text(encoding="utf-8"))
        if not canonical_config.exists() or canonical_config.read_text(encoding="utf-8") != config_text:
            actions.append({"action": "write", "path": str(canonical_config)})
            if execute:
                _write_text(canonical_config, config_text)

    if legacy_state.exists():
        state = json.loads(legacy_state.read_text(encoding="utf-8"))
        state = _rewrite_json(state)
        state["config_path"] = str(canonical_config)
        history_entries = sorted((meta_root / "config-history").glob("*.yaml"))
        if history_entries:
            state["history_path"] = str(history_entries[0])
        if not canonical_state.exists() or json.loads(canonical_state.read_text(encoding="utf-8")) != state:
            actions.append({"action": "write", "path": str(canonical_state)})
            if execute:
                _write_json(canonical_state, state)
    return actions


def _migrate_request_files(staging_root: Path, *, execute: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for request_path in staging_root.rglob("prw-record-request.json"):
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        canonical_payload = _transform_request_payload(payload)
        canonical_path = request_path.with_name("paper-wiki-record-request.json")
        current_payload = None
        if canonical_path.exists():
            try:
                current_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                current_payload = None
        if current_payload != canonical_payload:
            actions.append({"action": "write", "path": str(canonical_path)})
            if execute:
                _write_json(canonical_path, canonical_payload)
        actions.append({"action": "remove", "path": str(request_path)})
        if execute and request_path.exists():
            request_path.unlink()
    return actions


def _migrate_active_files(paper_source_root: Path, *, execute: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for path in sorted(paper_source_root.rglob("*")):
        if not path.is_file() or not _is_active_artifact(path, paper_source_root):
            continue
        if path.suffix.lower() not in {".json", ".md", ".yaml", ".yml"}:
            continue
        if path.name in {"paper-source-config.yaml", "paper-source-config-state.json", "prw-record-request.json"}:
            continue

        original = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(original)
            except json.JSONDecodeError:
                payload = None
            if payload is None:
                updated = _replace_known_paths(original)
                if updated != original:
                    actions.append({"action": "rewrite", "path": str(path)})
                    if execute:
                        _write_text(path, updated)
                continue
            rewritten_payload = _rewrite_json(payload)
            if isinstance(rewritten_payload, dict):
                _preserve_nested_legacy_markers(rewritten_payload)
            if rewritten_payload != payload:
                actions.append({"action": "rewrite", "path": str(path)})
                if execute:
                    _write_json(path, rewritten_payload)
        else:
            updated = _replace_known_paths(original)
            if updated != original:
                actions.append({"action": "rewrite", "path": str(path)})
                if execute:
                    _write_text(path, updated)
    return actions


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault = args.vault.resolve()
    paper_source_root = vault / "_paper_source"
    meta_root = paper_source_root / "meta"
    staging_root = paper_source_root / "staging"

    actions: list[dict[str, Any]] = []
    actions.extend(_migrate_root_manifest(vault, execute=args.execute))
    actions.extend(_migrate_config(meta_root, execute=args.execute))
    actions.extend(_regenerate_staging_handoffs(paper_source_root, execute=args.execute))
    _refresh_task_archive_replacements(paper_source_root)
    actions.extend(_migrate_request_files(staging_root, execute=args.execute))
    actions.extend(_migrate_active_files(paper_source_root, execute=args.execute))
    actions.extend(_refresh_current_record_hashes(vault, execute=args.execute))
    actions.extend(_archive_legacy_root_files(paper_source_root, execute=args.execute))
    return {
        "schema_version": "paper-source-active-artifact-migration-v1",
        "mode": "execute" if args.execute else "dry-run",
        "vault": str(vault),
        "actions": actions,
        "action_count": len(actions),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['mode']}: {result['action_count']} action(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
