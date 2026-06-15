from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from paper_source.artifacts import json_sha256, read_json, review_root, reviews_root, utc_now, write_json_atomic
from paper_source.fetch_plan import build_fetch_plan
from paper_source.schemas import slugify_title

SCHEMA_VERSION = "paper-source-review-session-v1"


def _clean_signature_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _clean_signature_value(value[key])
            for key in sorted(value)
            if key not in {"created_at", "updated_at", "started_at", "finished_at", "run_id"}
        }
    if isinstance(value, list):
        return [_clean_signature_value(item) for item in value]
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def build_review_signature(inputs: dict[str, Any]) -> dict[str, Any]:
    cleaned = _clean_signature_value(inputs)
    return {
        "schema_version": "paper-source-review-signature-v1",
        "signature": json_sha256(cleaned),
        "signature_inputs": cleaned,
    }


def _review_id(topic: str, signature: str) -> str:
    slug = slugify_title(topic or "review")
    slug = re.sub(r"-+", "-", slug).strip("-") or "review"
    return f"{slug[:64]}-{signature[:12]}"


def _read_review_artifact(path: Path) -> Any:
    try:
        return read_json(path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"corrupt review session artifact: {path}") from exc


def _read_review_artifact_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return _read_review_artifact(path)


def _provider_cache_records(search_record: dict[str, Any]) -> list[dict[str, Any]]:
    query_records = search_record.get("query_records")
    if isinstance(query_records, list) and query_records:
        records = []
        all_records = search_record.get("records") or []
        for item in query_records:
            if not isinstance(item, dict):
                continue
            query = item.get("query")
            matching_records = [
                record
                for record in all_records
                if record.get("query_variant") == query or len(query_records) == 1
            ]
            records.append(
                {
                    "schema_version": "paper-source-provider-cache-record-v1",
                    "query_index": item.get("index"),
                    "query": query,
                    "source_mode": item.get("source_mode"),
                    "record_count": item.get("record_count", len(matching_records)),
                    "records": matching_records,
                    "upstream": item.get("upstream", {}),
                    "error": item.get("error"),
                    "warnings": [],
                    "created_at": utc_now(),
                    "provider_call": {"called": True, "reason": "refresh_or_cache_miss"},
                }
            )
        return records
    return [
        {
            "schema_version": "paper-source-provider-cache-record-v1",
            "query_index": 1,
            "query": search_record.get("query"),
            "source_mode": search_record.get("source_mode"),
            "record_count": len(search_record.get("records") or []),
            "records": search_record.get("records") or [],
            "upstream": search_record.get("upstream", {}),
            "error": search_record.get("error"),
            "warnings": search_record.get("warnings", []),
            "created_at": utc_now(),
            "provider_call": {"called": True, "reason": "refresh_or_cache_miss"},
        }
    ]


def persist_provider_cache_records(root: Path, search_record: dict[str, Any], review_id: str) -> list[str]:
    cache_root = root / "provider-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, record in enumerate(_provider_cache_records(search_record), start=1):
        payload = dict(record)
        payload["review_id"] = review_id
        path = cache_root / f"query-{index:02d}.json"
        write_json_atomic(path, payload)
        paths.append(path.relative_to(root).as_posix())
    return paths


def _candidate_counts(
    records: list[dict],
    normalized: list[dict],
    filter_report: dict,
    ranked_pool: list[dict],
    accepted: list[dict],
) -> dict:
    return {
        "raw": len(records),
        "normalized": len(normalized),
        "filtered": len(filter_report.get("kept") or []),
        "ranked": len(ranked_pool),
        "accepted": len(accepted),
        "rejected": len(filter_report.get("rejected") or []),
    }


def create_or_update_review_session(
    vault_path: Path,
    *,
    topic: str,
    signature: dict[str, Any],
    query_plan: dict[str, Any] | None,
    search_record: dict[str, Any],
    normalized: list[dict],
    filter_report: dict,
    easyscholar_record: dict,
    ranked_pool: list[dict],
    accepted: list[dict],
    coverage: dict,
    run_id: str,
    refreshed: bool,
) -> dict[str, Any]:
    review_id = _review_id(topic, signature["signature"])
    root = review_root(vault_path, review_id)
    root.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    existing_state = _read_review_artifact_if_exists(root / "state.json") or {}
    run_ids = list(existing_state.get("run_ids") or [])
    if run_id not in run_ids:
        run_ids.append(run_id)
    provider_paths = persist_provider_cache_records(root, search_record, review_id)
    write_json_atomic(root / "signature-inputs.json", signature["signature_inputs"])
    if query_plan:
        write_json_atomic(root / "query-plan.json", query_plan)
    candidates = {
        "schema_version": "paper-source-review-candidates-v1",
        "review_id": review_id,
        "records": search_record.get("records") or [],
        "normalized": normalized,
        "source_record_paths": provider_paths,
        "record_count": len(search_record.get("records") or []),
        "normalized_count": len(normalized),
    }
    shortlist = {
        "schema_version": "paper-source-review-shortlist-v1",
        "review_id": review_id,
        "kept": filter_report.get("kept") or [],
        "rejected": filter_report.get("rejected") or [],
        "ranked_pool": ranked_pool,
        "accepted": accepted,
        "filter_report_path": "filter-report.json",
        "easyscholar_record": easyscholar_record,
    }
    write_json_atomic(root / "candidates.json", candidates)
    write_json_atomic(root / "filter-report.json", filter_report)
    write_json_atomic(root / "shortlist.json", shortlist)
    write_json_atomic(root / "fetch_plan.json", build_fetch_plan(accepted))
    write_json_atomic(root / "coverage.json", {"schema_version": "paper-source-review-coverage-v1", "review_id": review_id, **coverage})
    write_json_atomic(root / "runs" / f"{run_id}.json", {"run_id": run_id, "recorded_at": now, "refreshed": refreshed})
    state = {
        "schema_version": SCHEMA_VERSION,
        "review_id": review_id,
        "topic": topic,
        "normalized_topic": " ".join(topic.lower().split()),
        "signature": signature["signature"],
        "signature_inputs_path": "signature-inputs.json",
        "status": "active",
        "phase": "ranked",
        "created_at": existing_state.get("created_at") or now,
        "updated_at": now,
        "last_run_id": run_id,
        "run_ids": run_ids,
        "resume_count": int(existing_state.get("resume_count") or 0),
        "refresh_count": int(existing_state.get("refresh_count") or 0) + (1 if refreshed else 0),
        "candidate_counts": _candidate_counts(
            search_record.get("records") or [],
            normalized,
            filter_report,
            ranked_pool,
            accepted,
        ),
        "artifacts": {
            "query_plan": "query-plan.json" if query_plan else None,
            "candidates": "candidates.json",
            "shortlist": "shortlist.json",
            "fetch_plan": "fetch_plan.json",
            "coverage": "coverage.json",
        },
    }
    write_json_atomic(root / "state.json", state)
    return {"review_id": review_id, "review_dir": str(root), "state": state}


def find_matching_review_session(vault_path: Path, signature: str) -> dict[str, Any] | None:
    root = reviews_root(vault_path)
    if not root.exists():
        return None
    for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
        state = _read_review_artifact_if_exists(candidate / "state.json")
        if isinstance(state, dict) and state.get("status") == "active" and state.get("signature") == signature:
            return {"review_id": state["review_id"], "review_dir": str(candidate), "state": state}
    return None


def load_review_session_for_resume(vault_path: Path, signature: str) -> dict[str, Any]:
    match = find_matching_review_session(vault_path, signature)
    if not match:
        raise FileNotFoundError("no matching review session")
    root = Path(match["review_dir"])
    candidates = _read_review_artifact_if_exists(root / "candidates.json")
    shortlist = _read_review_artifact_if_exists(root / "shortlist.json")
    coverage = _read_review_artifact_if_exists(root / "coverage.json")
    provider_cache_paths = sorted((root / "provider-cache").glob("query-*.json"))
    provider_cache = [_read_review_artifact(path) for path in provider_cache_paths]
    if shortlist is not None and candidates is not None:
        phase = "shortlist"
    elif candidates is not None:
        phase = "candidates"
    elif provider_cache:
        phase = "provider-cache"
    else:
        raise ValueError(f"corrupt review session: {root}")
    return {
        **match,
        "root": root,
        "candidates": candidates,
        "shortlist": shortlist,
        "coverage": coverage,
        "provider_cache": provider_cache,
        "resume_phase": phase,
    }


def mark_review_resumed(session: dict[str, Any], run_id: str) -> dict[str, Any]:
    root = Path(session["review_dir"])
    state = dict(session["state"])
    run_ids = list(state.get("run_ids") or [])
    if run_id not in run_ids:
        run_ids.append(run_id)
    state["run_ids"] = run_ids
    state["last_run_id"] = run_id
    state["resume_count"] = int(state.get("resume_count") or 0) + 1
    state["updated_at"] = utc_now()
    write_json_atomic(root / "state.json", state)
    write_json_atomic(
        root / "runs" / f"{run_id}.json",
        {"run_id": run_id, "recorded_at": state["updated_at"], "resumed": True},
    )
    session["state"] = state
    return state


def rehydrate_search_record_from_review(session: dict[str, Any]) -> dict[str, Any]:
    if session.get("candidates") and isinstance(session["candidates"], dict):
        records = session["candidates"].get("records") or []
    else:
        records = []
        for cache_record in session.get("provider_cache") or []:
            records.extend(cache_record.get("records") or [])
    query_records = []
    for cache_record in session.get("provider_cache") or []:
        query_records.append(
            {
                "index": cache_record.get("query_index"),
                "query": cache_record.get("query"),
                "source_mode": cache_record.get("source_mode"),
                "record_count": cache_record.get("record_count", len(cache_record.get("records") or [])),
                "error": cache_record.get("error"),
                "upstream": cache_record.get("upstream", {}),
            }
        )
    return {
        "source_mode": "review-session",
        "query_strategy": "review_session_resume",
        "records": records,
        "query_records": query_records,
        "warnings": [],
        "resumed": True,
        "resumed_from_review_id": session["review_id"],
        "provider_call_skipped": True,
        "upstream": {},
    }


def review_artifact_paths(session: dict[str, Any]) -> dict[str, str]:
    root = Path(session["review_dir"])
    return {
        "state": str(root / "state.json"),
        "candidates": str(root / "candidates.json"),
        "shortlist": str(root / "shortlist.json"),
        "fetch_plan": str(root / "fetch_plan.json"),
        "coverage": str(root / "coverage.json"),
    }
