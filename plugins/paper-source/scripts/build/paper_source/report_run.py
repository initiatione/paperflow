from __future__ import annotations

from pathlib import Path

from paper_source.artifacts import existing_run_dir, read_json_dict, write_json_atomic, write_text_atomic
from paper_source.recommendation_output import build_session_recommendations


def load_run_report(vault_path: Path, run_id: str) -> dict:
    run_dir = existing_run_dir(vault_path, run_id)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"missing Paper Source run directory: {run_dir}")

    report_json_path = run_dir / "report.json"
    report_md_path = run_dir / "report.md"
    run_state_path = run_dir / "run-state.json"

    report_payload = read_json_dict(report_json_path, default=None)
    run_state_payload = read_json_dict(run_state_path, default=None) or {}
    markdown = report_md_path.read_text(encoding="utf-8") if report_md_path.exists() else ""
    if report_payload is None and not markdown:
        raise FileNotFoundError(f"missing report artifacts for Paper Source run: {run_dir}")

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "artifacts": {
            "report": str(report_md_path) if report_md_path.exists() else None,
            "report_json": str(report_json_path) if report_json_path.exists() else None,
            "run_state": str(run_state_path) if run_state_path.exists() else None,
        },
        "run_state": run_state_payload,
        "report": report_payload or {},
        "markdown": markdown,
    }


def _research_queue(ranked: list[dict]) -> dict[str, list[dict]]:
    queue = {
        "advance_candidates": [],
        "review_candidates": [],
        "unknown_decision": [],
    }
    for paper in ranked:
        decision = (paper.get("ranking_protocol") or {}).get("decision")
        if decision == "advance-candidate":
            queue["advance_candidates"].append(paper)
        elif decision == "review-candidate":
            queue["review_candidates"].append(paper)
        else:
            queue["unknown_decision"].append(paper)
    return queue


def _append_queue_section(report: list[str], title: str, papers: list[dict]) -> None:
    report.append(f"### {title}")
    if not papers:
        report.append("- None.")
        return
    for index, paper in enumerate(papers, start=1):
        protocol = paper.get("ranking_protocol") or {}
        reasons = "; ".join(protocol.get("reasons") or [])
        cautions = "; ".join(protocol.get("cautions") or [])
        report.append(f"{index}. {paper.get('title')} - score {paper.get('score')}")
        classification = paper.get("paper_classification") or {}
        if classification:
            report.append(
                f"   - paper_type: {classification.get('primary_type')} "
                f"(confidence={classification.get('confidence')})"
            )
        if paper.get("quality_tier"):
            report.append(f"   - quality_tier: {paper['quality_tier']}")
        if paper.get("ranking_confidence") or (paper.get("ranking_rubric") or {}).get("ranking_confidence"):
            confidence = paper.get("ranking_confidence") or (paper.get("ranking_rubric") or {}).get("ranking_confidence")
            report.append(f"   - ranking_confidence: {confidence}")
        if reasons:
            report.append(f"   - reasons: {reasons}")
        if cautions:
            report.append(f"   - cautions: {cautions}")
        rationale = paper.get("ranking_rationale") or {}
        if rationale.get("one_sentence"):
            report.append(f"   - rationale: {rationale['one_sentence']}")
        role_views = rationale.get("role_views") if isinstance(rationale.get("role_views"), dict) else {}
        role_labels = {
            "nature_sci_editor": "nature-sci-editor",
            "peer_reviewer": "peer-reviewer",
            "senior_domain_researcher": "senior-domain-researcher",
        }
        for role_key, role_label in role_labels.items():
            role_view = role_views.get(role_key) or {}
            if role_view.get("take"):
                report.append(f"   - {role_label}: {role_view['take']}")


def _append_research_decision_section(report: list[str], decisions: list[dict]) -> None:
    report.append("## Research Decisions")
    if not decisions:
        report.append("- None.")
        return
    for index, decision in enumerate(decisions, start=1):
        title = decision.get("title") or decision.get("slug")
        recommendation = decision.get("recommendation")
        next_action = decision.get("next_action")
        report.append(f"{index}. {title} - {recommendation}")
        if next_action:
            report.append(f"   - next_action: {next_action}")
        role_verdicts = decision.get("role_verdicts") or {}
        for lens, verdict in role_verdicts.items():
            report.append(f"   - {lens}: {verdict}")
        for item in decision.get("action_items") or []:
            lens = item.get("lens")
            action = item.get("action")
            if lens and action:
                report.append(f"   - {lens} -> {action}")


def _append_reader_revision_plan_section(report: list[str], plans: list[dict]) -> None:
    report.append("## Reader Revision Plans")
    if not plans:
        report.append("- None.")
        return
    for index, plan in enumerate(plans, start=1):
        title = plan.get("title") or plan.get("slug")
        next_action = plan.get("next_action") or "-"
        report.append(f"{index}. {title} - {next_action}")
        if plan.get("plan_path"):
            report.append(f"   - plan: {plan['plan_path']}")
        report.append(f"   - blocking repairs: {plan.get('blocking_count', 0)}")
        report.append(f"   - warning follow-ups: {plan.get('warning_count', 0)}")


def _append_reproduction_plan_section(report: list[str], plans: list[dict]) -> None:
    report.append("## Reproducibility Caveats")
    if not plans:
        report.append("- None.")
        return
    for index, plan in enumerate(plans, start=1):
        title = plan.get("title") or plan.get("slug")
        report.append(f"{index}. {title} - review-reproducibility-caveats")
        if plan.get("plan_path"):
            report.append(f"   - plan: {plan['plan_path']}")
        report.append(f"   - missing checklist items: {plan.get('missing_count', 0)}")
        report.append(f"   - human_gate_required: {plan.get('human_gate_required')}")
        report.append("   - note: keep reproduction as a short verification cue unless the user asks for a full run.")


def _append_zotero_section(report: list[str], zotero_results: dict) -> None:
    status = zotero_results.get("status")
    if status in {None, "not_run"}:
        return
    report.append("")
    report.append("## Zotero")
    report.append(f"- status: {status}")
    if zotero_results.get("reason"):
        report.append(f"- reason: {zotero_results['reason']}")
    if zotero_results.get("collection"):
        report.append(f"- collection: {zotero_results['collection']}")
    if zotero_results.get("item_key"):
        report.append(f"- item_key: {zotero_results['item_key']}")
    wiki_ingest = zotero_results.get("wiki_ingest") if isinstance(zotero_results.get("wiki_ingest"), dict) else {}
    final_pages = wiki_ingest.get("final_wiki_pages") if isinstance(wiki_ingest.get("final_wiki_pages"), list) else []
    if final_pages:
        report.append(f"- final_wiki_pages: {len(final_pages)}")


def _append_easyscholar_section(report: list[str], easyscholar: dict) -> None:
    if not easyscholar:
        return
    report.append("")
    report.append("## EasyScholar Enrichment")
    report.append(f"- enabled: {easyscholar.get('enabled')}")
    if easyscholar.get("record_path"):
        report.append(f"- record_path: {easyscholar['record_path']}")
    summary = easyscholar.get("summary") if isinstance(easyscholar.get("summary"), dict) else {}
    if summary:
        report.append("- summary:")
        for status, count in sorted(summary.items()):
            report.append(f"  - {status}: {count}")


def _append_source_coverage_section(report: list[str], source_coverage: dict) -> None:
    if not source_coverage:
        return
    report.append("")
    report.append("## Source Coverage")
    for key in ("raw_total", "deduped_total", "query_count"):
        if source_coverage.get(key) is not None:
            report.append(f"- {key}: {source_coverage.get(key)}")
    for key in ("timeout_budget_seconds", "search_duration_ms"):
        if source_coverage.get(key) is not None:
            report.append(f"- {key}: {source_coverage.get(key)}")
    source_results = source_coverage.get("source_results")
    source_results = source_results if isinstance(source_results, dict) else {}
    source_errors = source_coverage.get("errors")
    source_errors = source_errors if isinstance(source_errors, dict) else {}
    sources_used = source_coverage.get("sources_used")
    if not isinstance(sources_used, list) or not sources_used:
        sources_used = sorted(set(source_results) | set(source_errors))
    for source in sources_used:
        source_name = str(source)
        count = source_results.get(source_name, 0)
        error = source_errors.get(source_name)
        suffix = f" (error: {error})" if error else ""
        report.append(f"- {source_name}: {count}{suffix}")
    capabilities = source_coverage.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    if capabilities:
        report.append("- capabilities:")
        for source in sources_used:
            source_name = str(source)
            capability = capabilities.get(source_name)
            if not isinstance(capability, dict):
                continue
            download = capability.get("download", "unknown")
            read = capability.get("read", "unknown")
            report.append(f"  - {source_name} capability: download={download}, read={read}")
    source_health = source_coverage.get("source_health")
    source_health = source_health if isinstance(source_health, dict) else {}
    if source_health:
        report.append("- source_health:")
        for source in sources_used:
            source_name = str(source)
            state = source_health.get(source_name)
            if not isinstance(state, dict):
                continue
            status = state.get("status", "unknown")
            result_count = state.get("result_count", 0)
            timeout_seconds = state.get("timeout_budget_seconds")
            parts = [f"{source_name}: {status}", f"results={result_count}"]
            if timeout_seconds is not None:
                parts.append(f"timeout={timeout_seconds}s")
            duration_ms = state.get("duration_ms")
            if duration_ms is not None:
                parts.append(f"duration_ms={duration_ms}")
            if state.get("error"):
                parts.append(f"error={state['error']}")
            report.append("  - " + ", ".join(parts))
    provider_readiness = source_coverage.get("provider_readiness")
    provider_readiness = provider_readiness if isinstance(provider_readiness, dict) else {}
    if provider_readiness:
        report.append("- provider_readiness:")
        for provider, state in sorted(provider_readiness.items()):
            if not isinstance(state, dict):
                continue
            status = state.get("status", "unknown")
            env_name = state.get("env")
            suffix = f" ({env_name})" if env_name else ""
            report.append(f"  - {provider}: {status}{suffix}")


def _append_source_routing_section(report: list[str], discovery_context: dict) -> None:
    source_coverage = discovery_context.get("source_coverage") if isinstance(discovery_context, dict) else {}
    source_coverage = source_coverage if isinstance(source_coverage, dict) else {}
    source_routing = source_coverage.get("source_routing")
    source_routing = source_routing if isinstance(source_routing, dict) else {}
    if not source_routing:
        return
    report.append("")
    report.append("## Source Routing")
    selected_sources = source_routing.get("selected_sources")
    if isinstance(selected_sources, list):
        report.append("- selected_sources: " + (", ".join(str(source) for source in selected_sources) or "None"))
    demoted_sources = source_routing.get("demoted_sources")
    if isinstance(demoted_sources, list) and demoted_sources:
        for item in demoted_sources:
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            reason = item.get("reason")
            if source:
                suffix = f" ({reason})" if reason else ""
                report.append(f"- demoted: {source}{suffix}")
    provider_risks = source_routing.get("provider_risks")
    if isinstance(provider_risks, list) and provider_risks:
        for item in provider_risks:
            if not isinstance(item, dict):
                continue
            provider = item.get("provider")
            status = item.get("status")
            env_name = item.get("env")
            if provider and status:
                suffix = f" ({env_name})" if env_name else ""
                report.append(f"- risk: {provider} {status}{suffix}")


def _append_grok_search_section(report: list[str], discovery_context: dict) -> None:
    grok = discovery_context.get("grok_search") if isinstance(discovery_context, dict) else {}
    grok = grok if isinstance(grok, dict) else {}
    provider_records = discovery_context.get("provider_records") if isinstance(discovery_context, dict) else {}
    provider_records = provider_records if isinstance(provider_records, dict) else {}
    grok_provider = provider_records.get("grok_search")
    grok_provider = grok_provider if isinstance(grok_provider, dict) else {}
    if not grok and not grok_provider:
        return
    report.append("")
    report.append("## Grok Supplemental Search")
    for key in (
        "mode",
        "status",
        "reason",
        "record_count",
        "failure_stage",
        "retryable",
        "retry_outcome",
        "contributed_count",
        "raw_response_path",
        "evidence_path",
    ):
        value = grok_provider.get(key, grok.get(key))
        if value is not None:
            report.append(f"- {key}: {value}")
    diagnostics = grok_provider.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    if diagnostics:
        diagnostic_keys = (
            "returned_count",
            "usable_count",
            "evidence_only_count",
            "quarantined_count",
            "elapsed_ms",
        )
        for key in diagnostic_keys:
            if diagnostics.get(key) is not None:
                report.append(f"- {key}: {diagnostics[key]}")
    contribution = grok_provider.get("contribution")
    contribution = contribution if isinstance(contribution, dict) else {}
    if contribution:
        report.append("- contribution_counts:")
        for key in (
            "merged_count",
            "normalized_count",
            "filtered_kept_count",
            "filtered_rejected_count",
            "ranked_count",
            "accepted_count",
        ):
            report.append(f"  - {key}: {contribution.get(key, 0)}")
    retry_attempts = diagnostics.get("retry_attempts")
    if isinstance(retry_attempts, list) and retry_attempts:
        report.append("- retry_attempts:")
        for item in retry_attempts:
            if not isinstance(item, dict):
                continue
            report.append(
                "  - "
                + "; ".join(
                    f"{key}={item.get(key)}"
                    for key in ("attempt", "reason", "status", "usable_count", "elapsed_ms")
                    if item.get(key) is not None
                )
            )
    warnings = grok_provider.get("warnings")
    if isinstance(warnings, list) and warnings:
        report.append("- warnings: " + "; ".join(str(item) for item in warnings))


def _append_manual_downloads_section(report: list[str], manual_downloads: list[dict]) -> None:
    if not manual_downloads:
        return
    report.append("")
    report.append("## Manual Downloads")
    for index, card in enumerate(manual_downloads, start=1):
        title = card.get("title") or card.get("slug") or "Untitled paper"
        report.append(f"{index}. {title} - manual-download-required")
        doi_url = card.get("doi_url")
        if doi_url:
            report.append(f"   - doi: {doi_url}")
        elif card.get("doi"):
            report.append(f"   - doi: {card['doi']}")
        for item in card.get("candidate_manual_urls") or []:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not url or url == doi_url:
                continue
            report.append(f"   - manual link: {url}")
        action = card.get("preferred_next_step") or card.get("recommended_action")
        if action:
            report.append(f"   - recommended_action: {action}")


def _markdown_cell(value: object) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text.replace("|", "\\|") or "-"


def _existing_library_status(item: dict) -> str:
    source_type = str(item.get("existing_source_type") or "")
    reason = str(item.get("reason") or "")
    if source_type == "wiki_reference_index" or reason.startswith("already_in_wiki:"):
        return "已在 wiki"
    if source_type == "raw_library" or reason.startswith("already_in_library:"):
        return "已在 raw library"
    return "已在 wiki/raw library"


def _existing_library_entry(item: dict) -> str:
    return (
        item.get("existing_page")
        or item.get("existing_slug")
        or item.get("existing_source_id")
        or item.get("reason")
        or "-"
    )


def _existing_library_doi(item: dict) -> str:
    doi = item.get("doi_url") or item.get("doi")
    if doi in {"未核实", "缺失", "missing", "unverified"}:
        return "-"
    return str(doi or "-")


def _append_session_recommendations_section(report: list[str], session_recommendations: dict) -> None:
    report.append("")
    report.append("## Session Recommendations")
    report.append(f"- schema: {session_recommendations.get('schema_version')}")
    overflow = session_recommendations.get("overflow") or {}
    report.append(f"- primary_total: {overflow.get('primary_total', 0)}")
    report.append(f"- primary_shown: {len(session_recommendations.get('primary_recommendations') or [])}")
    report.append(f"- hidden_primary: {overflow.get('hidden_count', 0)}")
    report.append("- Chinese summaries: generated by the calling agent from original_abstract.")
    doi_policy = session_recommendations.get("doi_required_policy") or {}
    if doi_policy:
        report.append(f"- doi_required_for: {', '.join(doi_policy.get('required_for') or [])}")
    doi_filtered = session_recommendations.get("doi_filtered_summary") or {}
    if doi_filtered:
        report.append(f"- missing_required_doi: {doi_filtered.get('total', 0)}")
    doi_resolution = session_recommendations.get("doi_resolution_summary") or {}
    if doi_resolution:
        total = doi_resolution.get("total") or {}
        report.append(
            f"- doi_resolution: success={total.get('success', 0)}, "
            f"failed={total.get('failed', 0)}, considered={total.get('considered', 0)}"
        )
    doi_recovery = session_recommendations.get("doi_recovery_summary") or {}
    if doi_recovery:
        report.append(
            f"- doi_recovery: status={doi_recovery.get('status')}, "
            f"recovered={doi_recovery.get('recovered_count', 0)}, "
            f"failed={doi_recovery.get('failed_count', 0)}"
        )
    no_primary = session_recommendations.get("no_primary_recommendations_summary") or {}
    if no_primary:
        report.append(f"- primary_status: {no_primary.get('status')}")
        if no_primary.get("status") == "no_primary_recommendations":
            reasons = ", ".join(str(reason) for reason in no_primary.get("reasons") or [])
            report.append(f"- no_primary_reasons: {reasons or 'unknown'}")
            if no_primary.get("dominant_blocking_reason"):
                report.append(f"- dominant_blocking_reason: {no_primary.get('dominant_blocking_reason')}")
            if no_primary.get("secondary_candidate_status"):
                report.append(f"- secondary_candidate_status: {no_primary.get('secondary_candidate_status')}")
            counts = no_primary.get("counts") if isinstance(no_primary.get("counts"), dict) else {}
            report.append(
                "- no_primary_counts: "
                f"ranked={counts.get('ranked', no_primary.get('ranked_count', 0))}, "
                f"quality_reject={counts.get('quality_reject', no_primary.get('quality_reject_count', 0))}, "
                f"missing_doi={counts.get('missing_doi', no_primary.get('missing_doi_count', 0))}, "
                f"review_appendix={counts.get('review_appendix', no_primary.get('review_appendix_count', 0))}, "
                f"existing_library={counts.get('existing_library', no_primary.get('existing_library_saturation_count', 0))}, "
                f"required_concept_group_failure={counts.get('required_concept_group_failure', 0)}"
            )

    primary = session_recommendations.get("primary_recommendations") or []
    report.append("### Primary Recommendations")
    if not primary:
        report.append("- None.")
        if no_primary.get("recommended_next_actions"):
            report.append("- why empty:")
            for action in no_primary.get("recommended_next_actions") or []:
                report.append(f"  - {action}")
        blocked = no_primary.get("top_blocked_candidates")
        if isinstance(blocked, list) and blocked:
            report.append("- top_blocked_candidates:")
            for item in blocked[:5]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("slug") or "Untitled paper"
                blockers = ", ".join(str(reason) for reason in item.get("blocking_reasons") or []) or "unknown"
                identity = item.get("doi") or item.get("arxiv_id") or "no DOI/arXiv"
                report.append(
                    f"  - {title} ({item.get('surface')}, tier={item.get('quality_tier') or 'unknown'}, "
                    f"score={item.get('score')}, identity={identity}, blockers={blockers})"
                )
    for index, item in enumerate(primary, start=1):
        report.append(f"{index}. {item.get('title')}")
        doi_line = item.get("doi")
        if item.get("doi_url"):
            doi_line = f"{doi_line} ({item.get('doi_url')})"
        report.append(f"   - doi: {doi_line}")
        report.append(f"   - primary_url: {item.get('primary_url')}")
        citation_count = item.get("citation_count")
        citation_status = item.get("citation_count_status")
        citation_source = item.get("citation_count_source")
        report.append(
            f"   - citations: {citation_count if citation_count is not None else '未核实'} "
            f"(status={citation_status}, source={citation_source or '未核实'})"
        )
        warnings = item.get("verification_warnings") or []
        if warnings:
            report.append(f"   - verification_warnings: {', '.join(warnings)}")
        report.append(f"   - quality_tier: {item.get('quality_tier')}")
        report.append(f"   - pdf_status: {item.get('pdf_status')}")
        report.append(f"   - auto_staging_status: {item.get('auto_staging_status')}")

    verification_summary = session_recommendations.get("verification_summary")
    verification_summary = verification_summary if isinstance(verification_summary, dict) else {}
    if verification_summary:
        citation = verification_summary.get("citation_count") or {}
        venue = verification_summary.get("venue_metrics") or {}
        quality_risk = verification_summary.get("quality_risk") or {}
        report.append("### Verification Summary")
        report.append(
            f"- citation_count: verified={citation.get('verified', 0)}, "
            f"unverified={citation.get('unverified', 0)}"
        )
        report.append(
            f"- venue_metrics: verified={venue.get('verified', 0)}, "
            f"unverified={venue.get('unverified', 0)}"
        )
        if quality_risk:
            report.append(
                f"- quality_risk: verified={quality_risk.get('verified', 0)}, "
                f"suspected={quality_risk.get('suspected', 0)}, "
                f"unverified={quality_risk.get('unverified', 0)}"
            )

    if doi_resolution or doi_filtered:
        report.append("### DOI Resolution Summary")
        doi_recovery = session_recommendations.get("doi_recovery_summary") or {}
        if doi_recovery:
            report.append(
                f"- recovery: status={doi_recovery.get('status')}, reason={doi_recovery.get('reason')}, "
                f"candidates={doi_recovery.get('candidate_count', 0)}, "
                f"recovered={doi_recovery.get('recovered_count', 0)}, failed={doi_recovery.get('failed_count', 0)}"
            )
        for key, label in [("primary_recommendations", "primary"), ("review_appendix", "review_appendix")]:
            bucket = doi_resolution.get(key) or {}
            if bucket:
                report.append(
                    f"- {label}: success={bucket.get('success', 0)}, "
                    f"failed={bucket.get('failed', 0)}, considered={bucket.get('considered', 0)}"
                )
        filtered_items = doi_filtered.get("items") or []
        if filtered_items:
            report.append("- filtered_candidates:")
            for item in filtered_items[:10]:
                title = item.get("title") or item.get("slug") or "Untitled paper"
                report.append(
                    f"  - {title} ({item.get('surface')}, tier={item.get('quality_tier') or 'unknown'}, "
                    f"score={item.get('score')}, arxiv={item.get('arxiv_id') or 'none'})"
                )

    existing = session_recommendations.get("existing_library_appendix") or []
    report.append("### Already In Library Or Wiki")
    if not existing:
        report.append("- None.")
    else:
        report.append("These papers are already present in the wiki/raw library and are not new recommendations.")
        report.append("| Paper | Year | Status | Entry | DOI |")
        report.append("|---|---:|---|---|---|")
        for item in existing:
            report.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(item.get("title") or item.get("slug")),
                        _markdown_cell(item.get("year")),
                        _markdown_cell(_existing_library_status(item)),
                        _markdown_cell(_existing_library_entry(item)),
                        _markdown_cell(_existing_library_doi(item)),
                    ]
                )
                + " |"
            )

    appendix = session_recommendations.get("review_appendix") or []
    report.append("### Review Appendix")
    if not appendix:
        report.append("- None.")
    for index, item in enumerate(appendix, start=1):
        report.append(f"{index}. {item.get('title')} - {item.get('appendix_reason')}")

    quality_reject_debug = session_recommendations.get("quality_reject_debug") or {}
    if quality_reject_debug:
        report.append("### Quality Reject Debug")
        report.append(f"- total: {quality_reject_debug.get('total', 0)}")
        for item in quality_reject_debug.get("reason_counts") or []:
            report.append(f"- {item.get('reason')}: {item.get('count')}")
        debug_items = quality_reject_debug.get("items") or []
        if debug_items:
            report.append("- examples:")
            for item in debug_items[:10]:
                title = item.get("title") or item.get("slug") or "Untitled paper"
                blockers = ", ".join(str(reason) for reason in item.get("blocking_reasons") or []) or "unknown"
                report.append(
                    f"  - {title} (tier={item.get('quality_tier')}, score={item.get('score')}, "
                    f"blockers={blockers}, arxiv={item.get('arxiv_id') or 'none'})"
                )

    rejected_summary = session_recommendations.get("rejected_summary") or {}
    report.append("### Rejected Summary")
    report.append(f"- total: {rejected_summary.get('total', 0)}")
    for item in rejected_summary.get("reason_counts") or []:
        report.append(f"- {item.get('reason')}: {item.get('count')}")


def write_report(
    run_dir: Path,
    ranked: list[dict],
    errors: list[str],
    *,
    workflow_type: str = "dry-run",
    run_id: str | None = None,
    rejected: list[dict] | None = None,
    quarantined: list[dict] | None = None,
    critic_failures: list[dict] | None = None,
    paper_states: list[dict] | None = None,
    failed_papers: list[dict] | None = None,
    budget_usage: dict | None = None,
    wiki_pages_written: list[str] | None = None,
    zotero_results: dict | None = None,
    next_actions: list[str] | None = None,
    human_gate: dict | None = None,
    restored_paths: list[str] | None = None,
    removed_paths: list[str] | None = None,
    changed_artifacts: list[str] | None = None,
    research_decisions: list[dict] | None = None,
    reader_revision_plans: list[dict] | None = None,
    reproduction_plans: list[dict] | None = None,
    discovery_context: dict | None = None,
    manual_downloads: list[dict] | None = None,
) -> None:
    rejected = rejected or []
    quarantined = quarantined or []
    critic_failures = critic_failures or []
    paper_states = paper_states or []
    failed_papers = failed_papers or []
    budget_usage = budget_usage or {}
    wiki_pages_written = wiki_pages_written or []
    zotero_results = zotero_results or {"status": "not_run", "records": []}
    next_actions = next_actions or []
    restored_paths = restored_paths or []
    removed_paths = removed_paths or []
    changed_artifacts = changed_artifacts or []
    research_decisions = research_decisions or []
    reader_revision_plans = reader_revision_plans or []
    reproduction_plans = reproduction_plans or []
    discovery_context = discovery_context or {}
    manual_downloads = manual_downloads or []
    easyscholar_context = discovery_context.get("easyscholar") if isinstance(discovery_context, dict) else {}
    easyscholar_context = easyscholar_context if isinstance(easyscholar_context, dict) else {}
    research_queue = _research_queue(ranked)
    session_recommendations = build_session_recommendations(
        ranked,
        rejected,
        discovery_context=discovery_context,
        manual_downloads=manual_downloads,
        run_id=run_id,
    )

    if workflow_type in {"dry-run", "paper-discovery-dry-run"}:
        report = ["# Paper Source Dry Run", ""]
        if run_id:
            report.append(f"Run ID: {run_id}")
        report.append(f"Accepted candidates: {len(ranked)}")
        report.append(f"Rejected candidates: {len(rejected)}")
        report.append(f"Quarantined candidates: {len(quarantined)}")
        report.append(f"Critic failures: {len(critic_failures)}")
        if budget_usage:
            report.append("")
            report.append("## Budget Usage")
            for key, value in budget_usage.items():
                report.append(f"- {key}: {value}")
        if discovery_context:
            report.append("")
            report.append("## Discovery Context")
            research_mode = discovery_context.get("research_mode") or {}
            if isinstance(research_mode, dict) and research_mode.get("mode"):
                report.append(
                    f"- research_mode: {research_mode.get('mode')} "
                    f"(oversight={research_mode.get('oversight')})"
                )
            query_plan = discovery_context.get("query_plan") or {}
            if query_plan:
                report.append(f"- query_strategy: {discovery_context.get('query_strategy')}")
                report.append(f"- query_plan.domain: {query_plan.get('domain')}")
                report.append(f"- query_plan.variants: {len(query_plan.get('query_variants') or [])}")
            request_constraints = discovery_context.get("request_constraints") or {}
            if request_constraints:
                report.append(
                    "- request_constraints: "
                    + ", ".join(f"{key}={value}" for key, value in request_constraints.items())
                )
            recommendation_filter = discovery_context.get("recommendation_filter") or {}
            if recommendation_filter:
                report.append(
                    "- recommendation_filter: "
                    + ", ".join(f"{key}={value}" for key, value in recommendation_filter.items())
                )
            existing_library = discovery_context.get("existing_library") or {}
            if existing_library:
                report.append(
                    "- existing_library: "
                    + ", ".join(
                        f"{key}={value}"
                        for key, value in existing_library.items()
                        if key in {"wiki_count", "raw_count", "reference_index_status"}
                    )
                )
            if discovery_context.get("diagnostics_path"):
                report.append(f"- diagnostics: {discovery_context['diagnostics_path']}")
            recall_gap = discovery_context.get("recall_gap") or {}
            if recall_gap:
                summary = recall_gap.get("summary") or {}
                filter_summary = recall_gap.get("filter_summary") or {}
                report.append(
                    "- recall_gap: "
                    + ", ".join(
                        f"{key}={value}"
                        for key, value in {
                            "attempted": summary.get("attempted", 0),
                            "recovered": summary.get("recovered", 0),
                            "recommendable": filter_summary.get("recommendable", 0),
                        }.items()
                    )
                )
            quality_risk = discovery_context.get("quality_risk") or {}
            if quality_risk:
                summary = quality_risk.get("summary") or {}
                report.append(
                    "- quality_risk: "
                    + ", ".join(
                        f"{key}={value}"
                        for key, value in {
                            "verified": summary.get("verified", 0),
                            "suspected": summary.get("suspected", 0),
                            "unverified": summary.get("unverified", 0),
                        }.items()
                    )
                )
            candidate_pool = discovery_context.get("candidate_pool") or {}
            if candidate_pool:
                report.append(
                    "- candidate_pool: "
                    + ", ".join(f"{key}={value}" for key, value in candidate_pool.items())
                )
            query_records = discovery_context.get("query_records") or []
            if query_records:
                report.append(f"- query_records: {len(query_records)}")
            source_coverage = discovery_context.get("source_coverage") or {}
            if source_coverage:
                _append_source_coverage_section(report, source_coverage)
            _append_source_routing_section(report, discovery_context)
            _append_grok_search_section(report, discovery_context)
        _append_easyscholar_section(report, easyscholar_context)
        review_session = discovery_context.get("review_session") if isinstance(discovery_context, dict) else {}
        review_session = review_session if isinstance(review_session, dict) else {}
        if review_session:
            report.append("")
            report.append("## Review Session")
            for key in ("review_id", "resumed", "provider_call_skipped", "refreshed", "resume_reason"):
                if key in review_session:
                    report.append(f"- {key}: {review_session[key]}")
            artifacts = review_session.get("artifacts")
            artifacts = artifacts if isinstance(artifacts, dict) else {}
            for key in ("candidates", "shortlist", "fetch_plan", "coverage"):
                if artifacts.get(key):
                    report.append(f"- {key}: {artifacts[key]}")
        report.append("")
        report.append("## Next Actions")
        if next_actions:
            for action in next_actions:
                report.append(f"- {action}")
        else:
            report.append("- No follow-up actions recorded.")
        if errors:
            report.append("")
            report.append("## Errors")
            for error in errors:
                report.append(f"- {error}")
        _append_session_recommendations_section(report, session_recommendations)
        _append_zotero_section(report, zotero_results)
        report.append("")
        report.append("## Research Queue")
        _append_queue_section(report, "Advance Candidates", research_queue["advance_candidates"])
        _append_queue_section(report, "Review Candidates", research_queue["review_candidates"])
        _append_queue_section(report, "Unknown Decision", research_queue["unknown_decision"])
        report.append("")
        report.append("## Ranked Papers")
        for index, paper in enumerate(ranked, start=1):
            report.append(f"{index}. {paper.get('title')} - score {paper.get('score')}")
            if paper.get("paper_type"):
                report.append(f"   - paper_type: {paper.get('paper_type')}")
            if paper.get("quality_tier"):
                report.append(f"   - quality_tier: {paper.get('quality_tier')}")
            report.append(f"   - venue: {paper.get('venue')}")
            report.append(f"   - year: {paper.get('year')}")
            report.append(f"   - pdf: {paper.get('pdf_url')}")
            report.append(f"   - code: {paper.get('code_url')}")
        if rejected:
            report.append("")
            report.append("## Rejected Candidates")
            for index, paper in enumerate(rejected, start=1):
                reasons = ", ".join(paper.get("filter_reasons") or [])
                report.append(f"{index}. {paper.get('title')}")
                report.append(f"   - reasons: {reasons}")
    else:
        report = ["# Paper Source Routed Run", ""]
        report.append(f"Workflow type: {workflow_type}")
        if run_id:
            report.append(f"Run ID: {run_id}")
        report.append(f"Accepted papers: {len(ranked)}")
        report.append(f"Failed papers: {len(failed_papers)}")
        report.append(f"Quarantined papers: {len(quarantined)}")
        report.append(f"Critic failures: {len(critic_failures)}")
        if budget_usage:
            report.append("")
            report.append("## Budget Usage")
            for key, value in budget_usage.items():
                report.append(f"- {key}: {value}")
        report.append("")
        report.append("## Next Actions")
        if next_actions:
            for action in next_actions:
                report.append(f"- {action}")
        else:
            report.append("- No follow-up actions recorded.")
        if errors:
            report.append("")
            report.append("## Errors")
            for error in errors:
                report.append(f"- {error}")
        report.append("")
        report.append("## Paper States")
        for index, paper in enumerate(paper_states, start=1):
            report.append(f"{index}. {paper.get('title') or paper.get('slug')} - {paper.get('state')}")
            report.append(f"   - slug: {paper.get('slug')}")
            report.append(f"   - last_action: {paper.get('last_action')}")
            report.append(f"   - next_action: {paper.get('next_action')}")
            report.append(f"   - human_gate_required: {paper.get('human_gate_required')}")
        report.append("")
        report.append("## Failed Papers")
        if failed_papers:
            for index, paper in enumerate(failed_papers, start=1):
                report.append(f"{index}. {paper.get('title') or paper.get('slug')} - {paper.get('state')}")
                report.append(f"   - next_action: {paper.get('next_action')}")
        else:
            report.append("- No failed papers recorded.")
        _append_manual_downloads_section(report, manual_downloads)
        _append_source_routing_section(report, discovery_context)
        if wiki_pages_written:
            report.append("")
            report.append("## Wiki Pages Written")
            for path in wiki_pages_written:
                report.append(f"- {path}")
        if changed_artifacts:
            report.append("")
            report.append("## Changed Artifacts")
            for path in changed_artifacts:
                report.append(f"- {path}")
        report.append("")
        _append_research_decision_section(report, research_decisions)
        report.append("")
        _append_reader_revision_plan_section(report, reader_revision_plans)
        report.append("")
        _append_reproduction_plan_section(report, reproduction_plans)
        _append_zotero_section(report, zotero_results)
        if human_gate:
            report.append("")
            report.append("## Human Gate")
            for key, value in human_gate.items():
                report.append(f"- {key}: {value}")
        if restored_paths:
            report.append("")
            report.append("## Restored Paths")
            for path in restored_paths:
                report.append(f"- {path}")
        if removed_paths:
            report.append("")
            report.append("## Removed Paths")
            for path in removed_paths:
                report.append(f"- {path}")

    write_text_atomic(run_dir / "report.md", "\n".join(report) + "\n")
    write_json_atomic(
        run_dir / "report.json",
        {
            "workflow_type": workflow_type,
            "run_id": run_id,
            "accepted": ranked,
            "rejected": rejected,
            "quarantined": quarantined,
            "critic_failures": critic_failures,
            "paper_states": paper_states,
            "failed_papers": failed_papers,
            "budget_usage": budget_usage,
            "wiki_pages_written": wiki_pages_written,
            "zotero_results": zotero_results,
            "next_actions": next_actions,
            "human_gate": human_gate,
            "restored_paths": restored_paths,
            "removed_paths": removed_paths,
            "changed_artifacts": changed_artifacts,
            "research_decisions": research_decisions,
            "reader_revision_plans": reader_revision_plans,
            "reproduction_plans": reproduction_plans,
            "discovery_context": discovery_context,
            "session_recommendations": session_recommendations,
            "manual_downloads": manual_downloads,
            "easyscholar": easyscholar_context,
            "research_queue": research_queue,
            "accepted_count": len(ranked),
            "errors": errors,
            "ranked": ranked,
        },
    )
