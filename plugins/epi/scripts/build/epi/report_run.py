from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import existing_run_dir, write_json_atomic, write_text_atomic


def _load_dict_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def load_run_report(vault_path: Path, run_id: str) -> dict:
    run_dir = existing_run_dir(vault_path, run_id)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"missing EPI run directory: {run_dir}")

    report_json_path = run_dir / "report.json"
    report_md_path = run_dir / "report.md"
    run_state_path = run_dir / "run-state.json"

    report_payload = _load_dict_json(report_json_path)
    run_state_payload = _load_dict_json(run_state_path) or {}
    markdown = report_md_path.read_text(encoding="utf-8") if report_md_path.exists() else ""
    if report_payload is None and not markdown:
        raise FileNotFoundError(f"missing report artifacts for EPI run: {run_dir}")

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
    research_queue = _research_queue(ranked)

    if workflow_type in {"dry-run", "paper-discovery-dry-run"}:
        report = ["# EPI Dry Run", ""]
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
            candidate_pool = discovery_context.get("candidate_pool") or {}
            if candidate_pool:
                report.append(
                    "- candidate_pool: "
                    + ", ".join(f"{key}={value}" for key, value in candidate_pool.items())
                )
            query_records = discovery_context.get("query_records") or []
            if query_records:
                report.append(f"- query_records: {len(query_records)}")
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
        if rejected:
            report.append("")
            report.append("## Rejected Candidates")
            for index, paper in enumerate(rejected, start=1):
                reasons = ", ".join(paper.get("filter_reasons") or [])
                report.append(f"{index}. {paper.get('title')}")
                report.append(f"   - reasons: {reasons}")
    else:
        report = ["# EPI Routed Run", ""]
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
            "research_queue": research_queue,
            "accepted_count": len(ranked),
            "errors": errors,
            "ranked": ranked,
        },
    )
