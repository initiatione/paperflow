from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from paper_wiki.bibtex import bibtex_entry_key, compose_wiki_scoped_bibtex
from paper_wiki.frontmatter import parse_frontmatter, replace_frontmatter
from paper_wiki.reference_index import refresh_reference_index
from paper_wiki.zotero_helper_adapter import ZoteroHelperAdapter
from paper_wiki.zotero_report import build_zotero_sync_report, sanitize, utc_now
from paper_wiki.zotero_status import PLAN_SCHEMA_VERSION, TARGET_COLLECTION, build_zotero_status_plan


APPLY_SCHEMA_VERSION = "paper-wiki-zotero-apply-plan-v1"
APPROVAL_SCOPE = "paper-wiki-zotero-apply-current-plan"
SYNC_REPORT_ROOT = Path("_meta") / "zotero-sync"
SNAPSHOT_ROOT = Path("_paper_source") / "meta" / "formal-page-snapshots"
ALLOWED_METADATA_FIELDS = ("doi", "arxiv_id", "year", "venue", "url", "authors")


MetadataProvider = Callable[[dict[str, Any]], dict[str, Any] | None]
MetadataValidator = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _json_stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _file_set(vault: Path) -> set[str]:
    if not vault.exists():
        return set()
    return {path.relative_to(vault).as_posix() for path in vault.rglob("*") if path.is_file()}


def _plan_hash_payload(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": plan.get("schema_version"),
        "mode": plan.get("mode"),
        "vault": plan.get("vault"),
        "target_collection": plan.get("target_collection"),
        "items": plan.get("items", []),
        "write_summary": plan.get("write_summary", {}),
        "gates": plan.get("gates", []),
    }


def plan_hash(plan: dict[str, Any]) -> str:
    return "sha256:" + _sha256_text(_json_stable(_plan_hash_payload(plan)))


def _write_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "formal_page_updates": 0,
        "metadata_overwrites": 0,
        "snapshots": 0,
        "zotero_imports": 0,
        "reference_index_refresh": 0,
        "references_bib_refresh": 0,
        "sync_report_writes": 2,
    }
    for item in items:
        action = item.get("planned_action")
        if action in {"link_existing", "ready_for_import", "needs_metadata_supplementation"}:
            summary["formal_page_updates"] += 1
        if action in {"ready_for_import", "needs_metadata_supplementation"}:
            summary["zotero_imports"] += 1
        if action == "needs_metadata_supplementation":
            summary["metadata_overwrites"] += 1
            summary["snapshots"] += 1
    if summary["formal_page_updates"]:
        summary["reference_index_refresh"] = 1
        summary["references_bib_refresh"] = 1
    return summary


def build_zotero_apply_plan(
    vault_path: Path | str,
    *,
    adapter: Any | None = None,
    helper_path: Path | str | None = None,
    extra_roots: list[Path | str] | None = None,
    include_defaults: bool = True,
    zotero_only_limit: int = 20,
    expand_zotero_only: bool = False,
) -> dict[str, Any]:
    plan = build_zotero_status_plan(
        vault_path,
        mode="dry-run",
        adapter=adapter,
        helper_path=helper_path,
        extra_roots=extra_roots,
        include_defaults=include_defaults,
        zotero_only_limit=zotero_only_limit,
        expand_zotero_only=expand_zotero_only,
    )
    plan["schema_version"] = APPLY_SCHEMA_VERSION
    plan["source_plan_schema_version"] = PLAN_SCHEMA_VERSION
    plan["mode"] = "apply"
    plan["write_summary"] = _write_summary(plan.get("items", []))
    plan["writes_performed"] = False
    plan["plan_hash"] = plan_hash(plan)
    return sanitize(plan)


def make_apply_approval(
    plan: dict[str, Any],
    *,
    approved_by: str = "user",
    approved_at: str | None = None,
) -> dict[str, Any]:
    return {
        "approved": True,
        "approved_by": approved_by,
        "approved_at": approved_at or utc_now(),
        "plan_hash": plan.get("plan_hash") or plan_hash(plan),
        "scope": APPROVAL_SCOPE,
    }


def _approval_issue(plan: dict[str, Any], approval: dict[str, Any] | None) -> dict[str, Any] | None:
    if not approval or approval.get("approved") is not True:
        return {"gate": "write_not_authorized", "message": "Paper Wiki Zotero apply requires explicit approval."}
    if approval.get("scope") != APPROVAL_SCOPE:
        return {"gate": "write_not_authorized", "message": "Approval scope does not match Paper Wiki Zotero apply."}
    expected = plan.get("plan_hash") or plan_hash(plan)
    if approval.get("plan_hash") != expected:
        return {"gate": "stale_plan_approval", "message": "Approval is not bound to the current apply plan."}
    return None


def _result_without_writes(plan: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "gate": gate["gate"],
        "message": gate["message"],
        "plan_hash": plan.get("plan_hash") or plan_hash(plan),
        "writes_performed": False,
        "report": None,
    }


def _page_path(vault: Path, item: dict[str, Any]) -> Path:
    return vault / str(item["page"])


def _read_page(vault: Path, item: dict[str, Any]) -> tuple[Path, str, dict[str, Any]]:
    path = _page_path(vault, item)
    text = path.read_text(encoding="utf-8")
    document = parse_frontmatter(text)
    return path, text, dict(document.frontmatter)


def _changed_fields(frontmatter: dict[str, Any], updates: dict[str, Any]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for field, new_value in updates.items():
        old_value = frontmatter.get(field)
        if old_value != new_value:
            diffs.append({"field": field, "old": old_value, "new": new_value})
    return diffs


def _has_value(value: Any) -> bool:
    return value not in {None, ""} if not isinstance(value, list) else bool(value)


def _needs_snapshot(frontmatter: dict[str, Any], diffs: list[dict[str, Any]]) -> bool:
    for diff in diffs:
        if diff["field"] not in ALLOWED_METADATA_FIELDS:
            continue
        old = diff.get("old")
        if _has_value(old):
            return True
    return False


def _create_snapshot(vault: Path, page_path: Path, *, run_id: str, reason: str) -> dict[str, Any]:
    relative = page_path.relative_to(vault)
    snapshot_dir = vault / SNAPSHOT_ROOT / f"{run_id}-pre-zotero-sync"
    snapshot_path = snapshot_dir / relative
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(page_path, snapshot_path)
    record = {
        "schema_version": "paper-wiki-formal-page-snapshot-v1",
        "created_at": utc_now(),
        "reason": reason,
        "original_path": relative.as_posix(),
        "snapshot_path": snapshot_path.relative_to(vault).as_posix(),
        "original_sha256": _sha256_file(page_path),
        "snapshot_sha256": _sha256_file(snapshot_path),
        "bytes": snapshot_path.stat().st_size,
    }
    manifest_path = snapshot_dir / "manifest.json"
    existing: dict[str, Any]
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing.setdefault("files", []).append(record)
    else:
        existing = {
            "schema_version": "paper-wiki-formal-page-snapshot-manifest-v1",
            "created_at": utc_now(),
            "reason": reason,
            "files": [record],
        }
    manifest_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def _write_page_frontmatter(
    vault: Path,
    item: dict[str, Any],
    updates: dict[str, Any],
    *,
    run_id: str,
    snapshots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    path, text, frontmatter = _read_page(vault, item)
    diffs = _changed_fields(frontmatter, updates)
    if not diffs:
        return [], False
    if _needs_snapshot(frontmatter, diffs):
        snapshots.append(
            _create_snapshot(vault, path, run_id=run_id, reason="pre-zotero-sync-bibliographic-overwrite")
        )
    for diff in diffs:
        frontmatter[diff["field"]] = diff["new"]
    path.write_text(replace_frontmatter(text, frontmatter), encoding="utf-8")
    return diffs, True


def _zotero_metadata(
    *,
    status: str,
    item_key: str,
    bibtex_key: str | None,
    identity_basis: str | None,
) -> dict[str, Any]:
    now = utc_now()
    metadata = {
        "sync_status": status,
        "item_key": item_key,
        "collection": TARGET_COLLECTION,
        "identity_basis": identity_basis or "unknown",
        "synced_at": now,
        "last_checked_at": now,
    }
    if bibtex_key:
        metadata["bibtex_key"] = bibtex_key
    return metadata


def _result_data(result: dict[str, Any]) -> Any:
    return result.get("data") if isinstance(result, dict) else None


def _item_key(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("item_key", "itemKey", "key", "zotero_key"):
        if item.get(key):
            return str(item[key])
    return None


def _item_bibtex_key(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("bibtexKey") or item.get("bibtex_key")
    return str(value) if value else None


def _search_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    data = _result_data(result)
    rows = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _bibtex_text(result: dict[str, Any]) -> str:
    data = _result_data(result)
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("bibtex", "text", "content"):
            if data.get(key):
                return str(data[key])
    return ""


def _generate_bibtex(page: dict[str, Any], metadata: dict[str, Any]) -> str:
    title = str(metadata.get("title") or page.get("title") or "Untitled")
    key_source = metadata.get("doi") or metadata.get("arxiv_id") or title
    key = re.sub(r"[^A-Za-z0-9]+", "_", str(key_source)).strip("_").lower() or "paper_wiki_item"
    fields = {"title": title}
    for field, target in [("year", "year"), ("doi", "doi"), ("arxiv_id", "eprint"), ("url", "url")]:
        value = metadata.get(field) or page.get(field)
        if value:
            fields[target] = str(value)
    authors = metadata.get("authors") or page.get("authors") or []
    if authors:
        fields["author"] = " and ".join(str(author) for author in authors)
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields.items())
    return f"@article{{{key},\n{body}\n}}\n"


def _verify_import(adapter: Any, item: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    for query in [metadata.get("doi"), metadata.get("arxiv_id"), item.get("title")]:
        if not query:
            continue
        result = adapter.search(str(query), with_bibtex_keys=True)
        if not result.get("ok"):
            continue
        for row in _search_rows(result):
            key = _item_key(row)
            if key:
                return {"ok": True, "item_key": key, "bibtex_key": _item_bibtex_key(row), "row": row}
    return {"ok": False, "gate": "import_verification_failed", "message": "Imported Zotero item key could not be verified."}


def _default_metadata_validator(page: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("doi") or candidate.get("arxiv_id"):
        return {
            "decision": "accepted",
            "confidence": candidate.get("confidence") or "provided",
            "rationale": "Candidate includes a stable bibliographic identity.",
            "accepted_fields": [field for field in ALLOWED_METADATA_FIELDS if candidate.get(field) not in {None, ""}],
        }
    return {"decision": "needs_review", "confidence": "low", "rationale": "No stable DOI/arXiv identity."}


def _run_metadata_supplementation(
    item: dict[str, Any],
    *,
    metadata_provider: MetadataProvider | None,
    metadata_validator: MetadataValidator,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if metadata_provider is None:
        return None, {
            "decision": "needs_review",
            "confidence": "not_checked",
            "rationale": "No metadata supplementation provider was configured.",
        }
    candidate = metadata_provider(item)
    if not candidate:
        return None, {
            "decision": "needs_review",
            "confidence": "not_found",
            "rationale": "Metadata supplementation did not return a candidate.",
        }
    validation = metadata_validator(item, candidate)
    return candidate, validation


def _summary_from_items(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"linked": 0, "imported": 0, "skipped": 0, "conflict": 0, "failed": 0, "unavailable": 0}
    for item in items:
        outcome = item.get("outcome")
        if outcome in summary:
            summary[outcome] += 1
    return summary


def _write_sync_report(vault: Path, report: dict[str, Any]) -> dict[str, Any]:
    run_id = str(report["run_id"])
    run_path = vault / SYNC_REPORT_ROOT / "runs" / f"{run_id}.json"
    index_path = vault / SYNC_REPORT_ROOT / "index.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"schema_version": "paper-wiki-zotero-sync-index-v1", "runs": []}
    entry = {
        "run_id": run_id,
        "created_at": report.get("created_at"),
        "mode": report.get("mode"),
        "path": run_path.relative_to(vault).as_posix(),
        "summary": report.get("summary", {}),
    }
    index["runs"] = [row for row in index.get("runs", []) if row.get("run_id") != run_id]
    index["runs"].insert(0, entry)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"run_report": str(run_path), "index": str(index_path)}


def _post_task_check(vault: Path, changed_pages: list[str]) -> dict[str, Any]:
    reference_index = vault / "_meta" / "reference-index.json"
    references_bib = vault / "references.bib"
    return {
        "status": "targeted_checks_recorded",
        "changed_pages": changed_pages,
        "reference_index_exists": reference_index.exists(),
        "references_bib_exists": references_bib.exists(),
        "qmd": "skipped_not_invoked_by_apply_helper",
        "paper_source_record_readiness": "not_applicable_zotero_sync",
    }


def apply_zotero_plan(
    vault_path: Path | str,
    *,
    plan: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    adapter: Any | None = None,
    helper_path: Path | str | None = None,
    extra_roots: list[Path | str] | None = None,
    include_defaults: bool = True,
    metadata_provider: MetadataProvider | None = None,
    metadata_validator: MetadataValidator | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    vault = Path(vault_path).resolve()
    zotero = adapter or ZoteroHelperAdapter(
        helper_path=helper_path,
        extra_roots=extra_roots,
        include_defaults=include_defaults,
    )
    current_plan = plan or build_zotero_apply_plan(vault, adapter=zotero)
    current_plan.setdefault("plan_hash", plan_hash(current_plan))
    issue = _approval_issue(current_plan, approval)
    if issue:
        return _result_without_writes(current_plan, issue)

    before_files = _file_set(vault)
    run_id = run_id or f"zotero-apply-{_utc_compact()}"
    validator = metadata_validator or _default_metadata_validator
    items: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    metadata_provenance: list[dict[str, Any]] = []
    validation_records: list[dict[str, Any]] = []
    overwrite_diffs: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    import_records: list[dict[str, Any]] = []
    changed_pages: list[str] = []
    bibtex_records: list[dict[str, Any]] = []

    needs_import = any(
        item.get("planned_action") in {"ready_for_import", "needs_metadata_supplementation"}
        for item in current_plan.get("items", [])
    )
    selected_target = None
    if needs_import:
        selected_target = zotero.selected_target(required_name=TARGET_COLLECTION)
        if not selected_target.get("ok"):
            gate = {
                "gate": selected_target.get("gate") or "selected_target_mismatch",
                "message": selected_target.get("message") or "Selected Zotero target mismatch.",
                "severity": "error",
            }
            gates.append(gate)
            report_items = [
                {
                    **item,
                    "outcome": "failed" if item.get("planned_action") in {"ready_for_import", "needs_metadata_supplementation"} else item.get("outcome"),
                    "gate": gate["gate"] if item.get("planned_action") in {"ready_for_import", "needs_metadata_supplementation"} else item.get("gate"),
                }
                for item in current_plan.get("items", [])
            ]
            report = build_zotero_sync_report(
                run_id=run_id,
                mode="apply",
                vault=vault,
                zotero_helper=current_plan.get("zotero_helper"),
                summary=_summary_from_items(report_items),
                items=report_items,
                gates=gates,
                snapshots=[],
                bibtex={"path": None, "entry_count": 0, "diagnostics": {}},
            )
            report["plan_hash"] = current_plan["plan_hash"]
            report["approval"] = approval
            report["selected_target"] = selected_target
            report["writes_performed"] = True
            paths = _write_sync_report(vault, report)
            return {"ok": False, "gate": gate["gate"], "writes_performed": True, "report": report, "paths": paths}

    for item in current_plan.get("items", []):
        action = item.get("planned_action")
        if action in {None, "none"}:
            items.append({**item, "outcome": item.get("outcome") or "linked"})
            if item.get("zotero_item_key"):
                exported = zotero.export_item_bibtex(item["zotero_item_key"])
                bibtex_records.append(
                    {
                        "page": item.get("page"),
                        "sync_status": item.get("outcome") or "linked",
                        "item_key": item["zotero_item_key"],
                        "bibtex_key": item.get("bibtex_key"),
                        "bibtex": _bibtex_text(exported),
                    }
                )
            continue
        if action == "link_existing" and item.get("zotero_item_key"):
            updates = {
                "zotero": _zotero_metadata(
                    status="linked",
                    item_key=str(item["zotero_item_key"]),
                    bibtex_key=item.get("bibtex_key"),
                    identity_basis=item.get("identity_basis"),
                )
            }
            diffs, changed = _write_page_frontmatter(vault, item, updates, run_id=run_id, snapshots=snapshots)
            if changed:
                changed_pages.append(str(item["page"]))
            exported = zotero.export_item_bibtex(item["zotero_item_key"])
            bibtex = _bibtex_text(exported)
            bibtex_records.append(
                {
                    "page": item.get("page"),
                    "sync_status": "linked",
                    "item_key": item["zotero_item_key"],
                    "bibtex_key": item.get("bibtex_key") or bibtex_entry_key(bibtex),
                    "bibtex": bibtex,
                }
            )
            items.append({**item, "outcome": "linked", "frontmatter_diffs": diffs})
            continue
        if action in {"ready_for_import", "needs_metadata_supplementation"}:
            metadata = {
                "title": item.get("title"),
                "doi": item.get("doi"),
                "arxiv_id": item.get("arxiv_base_id"),
                "year": item.get("year"),
                "authors": item.get("authors") or [],
            }
            validation: dict[str, Any] | None = None
            provenance: dict[str, Any] | None = None
            if action == "needs_metadata_supplementation":
                candidate, validation = _run_metadata_supplementation(
                    item, metadata_provider=metadata_provider, metadata_validator=validator
                )
                validation_records.append({"page": item.get("page"), "validation": validation, "candidate": candidate})
                if not candidate or validation.get("decision") != "accepted":
                    items.append(
                        {
                            **item,
                            "outcome": "skipped",
                            "reason": "needs_review_before_import",
                            "metadata_validation": validation,
                        }
                    )
                    continue
                metadata.update({field: candidate[field] for field in ALLOWED_METADATA_FIELDS if _has_value(candidate.get(field))})
                provenance = {
                    "page": item.get("page"),
                    "source": candidate.get("source") or "metadata_provider",
                    "query": candidate.get("query"),
                    "confidence": candidate.get("confidence"),
                    "fields": {field: metadata.get(field) for field in ALLOWED_METADATA_FIELDS if _has_value(metadata.get(field))},
                }
                metadata_provenance.append(provenance)
            if not (metadata.get("doi") or metadata.get("arxiv_id")):
                items.append({**item, "outcome": "skipped", "reason": "skipped_missing_bibliographic_identity"})
                continue
            import_text = _generate_bibtex(item, metadata)
            import_result = zotero.import_bibtex(text=import_text, session=run_id, approved=True)
            import_records.append({"page": item.get("page"), "result": import_result})
            if not import_result.get("ok"):
                items.append({**item, "outcome": "failed", "gate": import_result.get("gate"), "reason": "zotero_import_failed"})
                continue
            verified = _verify_import(zotero, item, metadata)
            if not verified.get("ok"):
                items.append({**item, "outcome": "failed", "gate": verified.get("gate"), "reason": "import_verification_failed"})
                continue
            item_key = str(verified["item_key"])
            bibtex_key = verified.get("bibtex_key")
            updates = {field: metadata[field] for field in ALLOWED_METADATA_FIELDS if _has_value(metadata.get(field))}
            updates["zotero"] = _zotero_metadata(
                status="imported",
                item_key=item_key,
                bibtex_key=bibtex_key,
                identity_basis="doi" if metadata.get("doi") else "arxiv",
            )
            diffs, changed = _write_page_frontmatter(vault, item, updates, run_id=run_id, snapshots=snapshots)
            if changed:
                changed_pages.append(str(item["page"]))
            overwrite_diffs.append({"page": item.get("page"), "diffs": diffs, "provenance": provenance, "validation": validation})
            exported = zotero.export_item_bibtex(item_key)
            bibtex = _bibtex_text(exported)
            bibtex_records.append(
                {
                    "page": item.get("page"),
                    "sync_status": "imported",
                    "item_key": item_key,
                    "bibtex_key": bibtex_key or bibtex_entry_key(bibtex),
                    "bibtex": bibtex,
                }
            )
            items.append(
                {
                    **item,
                    "outcome": "imported",
                    "zotero_item_key": item_key,
                    "bibtex_key": bibtex_key,
                    "frontmatter_diffs": diffs,
                    "metadata_validation": validation,
                }
            )
            continue
        items.append(item)

    bibtex_payload = compose_wiki_scoped_bibtex(bibtex_records)
    bibtex_path = None
    if bibtex_records:
        path = vault / "references.bib"
        path.write_text(bibtex_payload["content"], encoding="utf-8")
        bibtex_path = str(path)
    reference_index_result = refresh_reference_index(vault) if changed_pages else None
    post_task = _post_task_check(vault, changed_pages)
    report = build_zotero_sync_report(
        run_id=run_id,
        mode="apply",
        vault=vault,
        zotero_helper=current_plan.get("zotero_helper"),
        summary=_summary_from_items(items),
        items=items,
        gates=gates,
        metadata_provenance=metadata_provenance,
        snapshots=snapshots,
        bibtex={
            "path": bibtex_path,
            "entry_count": bibtex_payload["diagnostics"]["counts"]["included"],
            "diagnostics": bibtex_payload["diagnostics"],
        },
    )
    report["plan_hash"] = current_plan["plan_hash"]
    report["approval"] = approval
    report["selected_target"] = selected_target
    report["metadata_validation"] = validation_records
    report["overwrite_diffs"] = overwrite_diffs
    report["zotero_imports"] = import_records
    report["reference_index_refresh"] = reference_index_result
    report["post_task_check"] = post_task
    after_files = _file_set(vault)
    report["file_delta"] = {"created": sorted(after_files - before_files)}
    report["writes_performed"] = bool(after_files != before_files or changed_pages)
    paths = _write_sync_report(vault, report)
    return {"ok": not gates and report["summary"].get("failed", 0) == 0, "writes_performed": True, "report": report, "paths": paths}
