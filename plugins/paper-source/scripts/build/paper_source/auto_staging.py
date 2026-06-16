from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

AUTO_STAGING_PLAN_SCHEMA_VERSION = "paper-source-auto-staging-plan-v1"
DEFAULT_AUTO_STAGING_LIMIT = 3
DEFAULT_REVIEW_SURVEY_LIMIT = 1

_REVIEW_SURVEY_TYPES = {
    "review",
    "survey",
    "systematic-review",
    "systematic_review",
    "meta-analysis",
    "meta_analysis",
    "literature-review",
    "literature_review",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _candidate_key(record: dict[str, Any]) -> tuple[str, str]:
    return (_text(record.get("slug")), _text(record.get("title")).casefold())


def _ranked_by_identity(ranked: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in ranked:
        slug, title = _candidate_key(candidate)
        if slug:
            by_identity[(slug, "")] = candidate
        if title:
            by_identity[("", title)] = candidate
        if slug or title:
            by_identity[(slug, title)] = candidate
    return by_identity


def _match_ranked_candidate(
    item: dict[str, Any],
    by_identity: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    slug, title = _candidate_key(item)
    for key in [(slug, title), (slug, ""), ("", title)]:
        if key in by_identity:
            return by_identity[key]
    return None


def _candidate_pdf_available(item: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if _text(item.get("pdf_status")) == "available":
        return True
    if candidate.get("pdf_url") or candidate.get("citation_pdf_url"):
        return True
    return any(bool(url) for url in candidate.get("candidate_pdf_urls") or [])


def _paper_type(item: dict[str, Any], candidate: dict[str, Any]) -> str:
    classification = item.get("classification")
    classification = classification if isinstance(classification, dict) else {}
    candidate_classification = candidate.get("paper_classification")
    candidate_classification = candidate_classification if isinstance(candidate_classification, dict) else {}
    return _text(
        item.get("paper_type")
        or classification.get("paper_type")
        or classification.get("primary_type")
        or candidate.get("paper_type")
        or candidate_classification.get("primary_type")
    )


def _is_review_survey(item: dict[str, Any], candidate: dict[str, Any]) -> bool:
    paper_type = _paper_type(item, candidate).casefold().replace(" ", "-")
    return paper_type in _REVIEW_SURVEY_TYPES


def _manual_links(item: dict[str, Any]) -> list[dict[str, Any]]:
    manual = item.get("manual_download")
    manual = manual if isinstance(manual, dict) else {}
    links = manual.get("links")
    return list(links) if isinstance(links, list) else []


def _skip_entry(
    item: dict[str, Any],
    *,
    reason: str,
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "slug": item.get("slug") or (candidate or {}).get("slug"),
        "title": item.get("title") or (candidate or {}).get("title"),
        "reason": reason,
        "pdf_status": item.get("pdf_status"),
        "auto_staging_status": f"skipped_{reason}",
    }
    if reason == "needs_manual_pdf":
        payload["manual_download_links"] = _manual_links(item)
    return payload


def _selected_entry(item: dict[str, Any], candidate: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "slug": candidate.get("slug") or item.get("slug"),
        "title": candidate.get("title") or item.get("title"),
        "rank": index,
        "pdf_status": item.get("pdf_status") or "available",
        "paper_type": _paper_type(item, candidate) or None,
        "is_review_survey": _is_review_survey(item, candidate),
        "auto_staging_status": "selected_for_auto_staging",
    }


def build_auto_staging_plan(
    ranked: list[dict[str, Any]],
    session_recommendations: dict[str, Any],
    *,
    auto_limit: int = DEFAULT_AUTO_STAGING_LIMIT,
    review_survey_limit: int = DEFAULT_REVIEW_SURVEY_LIMIT,
    review_survey_requested: bool = False,
    skip_existing_slugs: set[str] | None = None,
) -> dict[str, Any]:
    if auto_limit < 0:
        raise ValueError("auto_limit must be greater than or equal to 0")
    if review_survey_limit < 0:
        raise ValueError("review_survey_limit must be greater than or equal to 0")

    skip_existing_slugs = skip_existing_slugs or set()
    by_identity = _ranked_by_identity(ranked)
    primary = session_recommendations.get("primary_recommendations") or []
    selected: list[dict[str, Any]] = []
    selected_candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    review_survey_selected = 0

    for index, item in enumerate(primary, start=1):
        if len(selected) >= auto_limit:
            skipped.append(_skip_entry(item, reason="auto_limit_reached"))
            continue

        candidate = _match_ranked_candidate(item, by_identity)
        if candidate is None:
            skipped.append(_skip_entry(item, reason="missing_ranked_candidate"))
            continue

        slug = _text(candidate.get("slug") or item.get("slug"))
        if slug in skip_existing_slugs:
            skipped.append(_skip_entry(item, candidate=candidate, reason="already_source_staged"))
            continue

        if not _candidate_pdf_available(item, candidate):
            skipped.append(_skip_entry(item, candidate=candidate, reason="needs_manual_pdf"))
            continue

        is_review_survey = _is_review_survey(item, candidate)
        if is_review_survey and not review_survey_requested and review_survey_selected >= review_survey_limit:
            skipped.append(_skip_entry(item, candidate=candidate, reason="review_survey_cap"))
            continue

        selected.append(_selected_entry(item, candidate, index))
        selected_candidates.append(candidate)
        if is_review_survey:
            review_survey_selected += 1

    reason_counts: dict[str, int] = {}
    for item in skipped:
        reason = _text(item.get("reason")) or "unknown"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "schema_version": AUTO_STAGING_PLAN_SCHEMA_VERSION,
        "auto_limit": auto_limit,
        "review_survey_limit": None if review_survey_requested else review_survey_limit,
        "review_survey_requested": review_survey_requested,
        "selected": selected,
        "selected_candidates": selected_candidates,
        "skipped": skipped,
        "counts": {
            "primary_total": len(primary),
            "selected": len(selected),
            "skipped": len(skipped),
            "skipped_by_reason": reason_counts,
        },
    }


def merge_auto_staging_status(
    session_recommendations: dict[str, Any],
    auto_staging_plan: dict[str, Any],
    *,
    execution_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    merged = deepcopy(session_recommendations)
    primary = merged.get("primary_recommendations")
    if not isinstance(primary, list):
        return merged

    status_by_slug: dict[str, str] = {}
    for item in auto_staging_plan.get("selected") or []:
        slug = _text(item.get("slug"))
        if slug:
            status_by_slug[slug] = _text(item.get("auto_staging_status")) or "selected_for_auto_staging"
    for item in auto_staging_plan.get("skipped") or []:
        slug = _text(item.get("slug"))
        if slug:
            status_by_slug[slug] = _text(item.get("auto_staging_status")) or "not_selected"
    for result in execution_results or []:
        slug = _text(result.get("paper_slug"))
        if slug:
            status_by_slug[slug] = _text(result.get("state")) or "unknown"

    for item in primary:
        if not isinstance(item, dict):
            continue
        slug = _text(item.get("slug"))
        item["auto_staging_status"] = status_by_slug.get(slug, item.get("auto_staging_status") or "not_selected")
    return merged


def _artifact_plan(plan: dict[str, Any]) -> dict[str, Any]:
    payload = dict(plan)
    payload.pop("selected_candidates", None)
    return payload


def _titles_by_slug(candidates: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(candidate["slug"]): str(candidate.get("title") or candidate["slug"])
        for candidate in candidates
        if candidate.get("slug")
    }


def _paper_states(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "paper_slug": result["paper_slug"],
            "state": result["state"],
            "next_action": result.get("next_action"),
        }
        for result in results
    ]


def _report_paper_states(results: list[dict[str, Any]], titles_by_slug: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "slug": result["paper_slug"],
            "paper_slug": result["paper_slug"],
            "title": titles_by_slug.get(result["paper_slug"], result["paper_slug"]),
            "state": result["state"],
            "last_action": result.get("last_action"),
            "next_action": result.get("next_action"),
            "human_gate_required": result.get("human_gate_required", False),
        }
        for result in results
    ]


def auto_stage_recommendations_from_run(
    vault_path: Path,
    run_id: str,
    *,
    mineru_command: str | list[str] | None = None,
    auto_limit: int = DEFAULT_AUTO_STAGING_LIMIT,
    review_survey_limit: int = DEFAULT_REVIEW_SURVEY_LIMIT,
    review_survey_requested: bool = False,
    skip_existing: bool = True,
    mineru_timeout: int | None = None,
    workflow_mode: str = "fast-ingest",
    selection_policy: str = "balanced_high_quality",
) -> dict[str, Any]:
    from paper_source.artifacts import (
        existing_run_dir,
        file_sha256,
        json_sha256,
        read_json,
        runs_root,
        utc_now,
        write_json_atomic,
    )
    from paper_source.orchestrator import (
        _auto_manage_run_lifecycle,
        _cleanup_failed_prepare_raw_results,
        _hash_paper_run_states,
        _has_prepared_source_staging,
        _manual_downloads_from_results,
        _new_run_dir,
        _normalize_selection_policy,
        _prepare_candidate_failure_state,
        _prepare_candidate_until_parsed,
        _refresh_run_index,
    )
    from paper_source.report_run import write_report
    from paper_source.stage_wiki import normalize_ingest_mode

    vault_path = vault_path.resolve()
    workflow_mode = normalize_ingest_mode(workflow_mode)
    selection_policy = _normalize_selection_policy(selection_policy)
    source_run_dir = existing_run_dir(vault_path, run_id)
    rank_path = source_run_dir / "rank.json"
    report_path = source_run_dir / "report.json"
    if not rank_path.exists():
        raise FileNotFoundError(f"missing ranked candidates: {rank_path}")
    if not report_path.exists():
        raise FileNotFoundError(f"missing source report: {report_path}")

    ranked = read_json(rank_path)
    source_report = read_json(report_path)
    session_recommendations = source_report.get("session_recommendations")
    if not isinstance(session_recommendations, dict):
        raise ValueError("source report is missing report.json.session_recommendations")

    skip_existing_slugs = {
        str(candidate["slug"])
        for candidate in ranked
        if skip_existing
        and candidate.get("slug")
        and _has_prepared_source_staging(vault_path, str(candidate["slug"]), workflow_mode)
    }
    plan = build_auto_staging_plan(
        ranked,
        session_recommendations,
        auto_limit=auto_limit,
        review_survey_limit=review_survey_limit,
        review_survey_requested=review_survey_requested,
        skip_existing_slugs=skip_existing_slugs,
    )
    selected_candidates = list(plan.get("selected_candidates") or [])
    artifact_plan = _artifact_plan(plan)
    batch_run_id, batch_run_dir = _new_run_dir(vault_path, "auto-staging")
    started_at = utc_now()

    results: list[dict[str, Any]] = []
    for candidate in selected_candidates:
        try:
            result = _prepare_candidate_until_parsed(
                vault_path,
                candidate,
                mineru_command=mineru_command,
                mineru_timeout=mineru_timeout,
                workflow_mode=workflow_mode,
            )
        except Exception as exc:
            result = _prepare_candidate_failure_state(vault_path, candidate, exc, workflow_mode=workflow_mode)
        results.append(result)

    raw_cleanup_records = _cleanup_failed_prepare_raw_results(vault_path, results)
    failed = any(result["state"].endswith("_failed") for result in results)
    awaiting_wiki_ingest = any(result.get("next_action") == "run-wiki-ingest-agent" for result in results)
    titles = _titles_by_slug(selected_candidates)
    paper_states = _paper_states(results)
    report_paper_states = _report_paper_states(results, titles)
    failed_papers = [state for state in paper_states if state["state"].endswith("_failed")]
    report_failed_papers = [state for state in report_paper_states if state["state"].endswith("_failed")]
    accepted = [
        {"slug": state["slug"], "title": state["title"], "state": state["state"]}
        for state in report_paper_states
        if not state["state"].endswith("_failed")
    ]
    next_actions = list(dict.fromkeys(result["next_action"] for result in results if result.get("next_action")))
    manual_downloads = _manual_downloads_from_results(results)
    merged_session = merge_auto_staging_status(session_recommendations, plan, execution_results=results)

    batch = {
        "stage": "auto-staging",
        "run_id": batch_run_id,
        "workflow_type": "auto-staging",
        "state": "prepared" if not failed else "prepare_failed",
        "status": "waiting_for_human_gate" if awaiting_wiki_ingest and not failed else "success" if not failed else "failed",
        "workflow_mode": workflow_mode,
        "selection_policy": selection_policy,
        "vault_path": str(vault_path),
        "candidate_count": len(ranked),
        "processed_count": len(results),
        "skipped_count": len(ranked) - len(results),
        "source_run_id": run_id,
        "candidate_source": str(rank_path),
        "auto_staging_plan": artifact_plan,
        "skip_existing": skip_existing,
        "compiled_wiki_write": False,
        "human_gate_required": awaiting_wiki_ingest,
        "stops_after": "source-staging",
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 1 if failed else 0,
        "results": results,
        "raw_cleanup": raw_cleanup_records,
        "next_actions": next_actions,
        "session_recommendations": merged_session,
        "input_artifact_hashes": {
            "candidates": json_sha256(selected_candidates),
            "candidate_source": file_sha256(rank_path),
        },
        "output_artifact_hashes": _hash_paper_run_states(vault_path, results),
    }
    write_json_atomic(batch_run_dir / "batch-advance-record.json", batch)
    write_json_atomic(batch_run_dir / "run-state.json", batch)
    write_report(
        batch_run_dir,
        accepted,
        [],
        workflow_type="auto-staging",
        run_id=batch_run_id,
        paper_states=report_paper_states,
        failed_papers=report_failed_papers,
        budget_usage={
            "candidate_count": len(ranked),
            "processed_count": len(results),
            "skipped_count": len(ranked) - len(results),
            "stops_after": "source-staging",
            "workflow_mode": workflow_mode,
            "selection_policy": selection_policy,
            "auto_limit": auto_limit,
            "review_survey_limit": None if review_survey_requested else review_survey_limit,
        },
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=next_actions,
        manual_downloads=manual_downloads,
    )
    report_json_path = batch_run_dir / "report.json"
    report_payload = read_json(report_json_path)
    report_payload["processed_count"] = batch["processed_count"]
    report_payload["skipped_count"] = batch["skipped_count"]
    report_payload["auto_staging_plan"] = artifact_plan
    report_payload["session_recommendations"] = merged_session
    report_payload["skip_existing"] = skip_existing
    report_payload["paper_states"] = paper_states
    report_payload["failed_papers"] = failed_papers
    report_payload["raw_cleanup"] = raw_cleanup_records
    report_payload["manual_downloads"] = manual_downloads
    report_payload["next_actions"] = next_actions
    report_payload["wiki_pages_written"] = []
    report_payload["source_run_id"] = run_id
    report_payload["workflow_mode"] = workflow_mode
    report_payload["stops_after"] = "source-staging"
    write_json_atomic(report_json_path, report_payload)

    lifecycle = _auto_manage_run_lifecycle(vault_path)
    if lifecycle.get("deleted_count"):
        batch["run_lifecycle"] = {
            "auto": True,
            "deleted_count": lifecycle.get("deleted_count", 0),
            "manifest_path": lifecycle.get("manifest_path"),
            "policy": lifecycle.get("policy"),
        }
        write_json_atomic(batch_run_dir / "run-state.json", batch)
    _refresh_run_index(vault_path)
    return batch
