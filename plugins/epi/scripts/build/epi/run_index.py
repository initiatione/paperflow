import json
import shutil
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta, timezone

from epi.paper_gate import build_paper_gate


_SUCCESS_STATUSES = {"success", "succeeded", "waiting_for_human_gate"}
_TERMINAL_CLEANUP_STATUSES = {"success", "succeeded", "skipped", "neutral", "failed", "failure", "error"}
_PROTECTED_CLEANUP_STATUSES = {"running", "waiting_for_human_gate"}
_STALE_RUNNING_AFTER = timedelta(hours=6)
_HUMAN_GATE_PENDING = {"pending", "required"}
_RESEARCH_QUEUE_BUCKETS = [
    "ready_to_promote",
    "needs_reader_repair",
    "warning_only",
    "reproducibility_caveats",
]
RESEARCH_QUEUE_BUCKETS = tuple(_RESEARCH_QUEUE_BUCKETS)
_ROLE_DISPLAY_NAMES = {
    "nature-sci-editor": "Nature/Sci Editor",
    "peer-reviewer": "Peer Reviewer",
    "senior-domain-researcher": "Senior Domain Researcher",
}


def _runs_root(vault_path):
    return Path(vault_path) / "_runs"


def _lifecycle_root(vault_path):
    return Path(vault_path) / "_meta" / "run-lifecycle"


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _normalize_run_entry(run_dir):
    run_state = _load_json(run_dir / "run-state.json")
    if not isinstance(run_state, dict):
        return None

    report = _load_json(run_dir / "report.json")
    if not isinstance(report, dict):
        report = {}

    entry = {
        "run_id": run_state.get("run_id", run_dir.name),
        "workflow_type": run_state.get("workflow_type", "unknown"),
        "state": run_state.get("state", "unknown"),
        "status": run_state.get("status", "unknown"),
        "paper_slug": run_state.get("paper_slug"),
        "started_at": run_state.get("started_at"),
        "finished_at": run_state.get("finished_at"),
        "next_actions": report.get("next_actions", []),
        "human_gate": report.get("human_gate"),
    }
    zotero_results = report.get("zotero_results")
    if not isinstance(zotero_results, dict):
        zotero_results = run_state.get("zotero_results")
    if isinstance(zotero_results, dict):
        entry["zotero_results"] = zotero_results
    research_decisions = report.get("research_decisions") or []
    if research_decisions:
        entry["research_decisions"] = research_decisions
    reader_revision_plans = report.get("reader_revision_plans") or []
    if reader_revision_plans:
        entry["reader_revision_plans"] = reader_revision_plans
    reproduction_plans = report.get("reproduction_plans") or []
    if reproduction_plans:
        entry["reproduction_plans"] = reproduction_plans
    revision_delta = report.get("revision_delta")
    if isinstance(revision_delta, dict):
        entry["revision_delta"] = revision_delta
    return entry


def _sort_key(entry):
    return (
        entry.get("finished_at") or "",
        entry.get("started_at") or "",
        entry.get("run_id") or "",
    )


def _human_gate_status(entry):
    human_gate = entry.get("human_gate")
    if not isinstance(human_gate, dict):
        return None
    return human_gate.get("status")


def _needs_attention(entry):
    status = entry.get("status", "unknown")
    if status not in _SUCCESS_STATUSES:
        return True
    if _human_gate_status(entry) in _HUMAN_GATE_PENDING:
        return True
    return bool(entry.get("next_actions"))


def _build_summary(entries):
    workflow_counts = Counter()
    status_counts = Counter()
    human_gate_pending_count = 0
    failed_run_count = 0

    for entry in entries:
        workflow_counts[entry.get("workflow_type", "unknown")] += 1
        status = entry.get("status", "unknown")
        status_counts[status] += 1
        if _human_gate_status(entry) in _HUMAN_GATE_PENDING:
            human_gate_pending_count += 1
        if status not in _SUCCESS_STATUSES:
            failed_run_count += 1

    return {
        "total_runs": len(entries),
        "workflow_counts": dict(sorted(workflow_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "human_gate_pending_count": human_gate_pending_count,
        "failed_run_count": failed_run_count,
    }


def _build_grouped_summaries(entries):
    latest_failures = [
        entry for entry in entries if entry.get("status") not in _SUCCESS_STATUSES
    ]
    latest_human_gate_pending = [
        entry for entry in entries if _human_gate_status(entry) in _HUMAN_GATE_PENDING
    ]

    latest_success_by_workflow = {}
    for entry in entries:
        workflow_type = entry.get("workflow_type", "unknown")
        if entry.get("status") not in _SUCCESS_STATUSES:
            continue
        if workflow_type in latest_success_by_workflow:
            continue
        latest_success_by_workflow[workflow_type] = entry

    return {
        "latest_failures": latest_failures,
        "latest_human_gate_pending": latest_human_gate_pending,
        "latest_success_by_workflow": {
            workflow_type: latest_success_by_workflow[workflow_type]
            for workflow_type in sorted(latest_success_by_workflow)
        },
    }


def _queue_item(entry, *, paper_slug=None, title=None, reason=None, checks=None, source=None):
    item = {
        "paper_slug": paper_slug or entry.get("paper_slug") or "-",
        "run_id": entry.get("run_id", "-"),
        "workflow_type": entry.get("workflow_type", "unknown"),
        "state": entry.get("state", "unknown"),
        "status": entry.get("status", "unknown"),
    }
    if title:
        item["title"] = title
    if reason:
        item["reason"] = reason
    if checks:
        item["checks"] = list(checks)
    if source:
        item["source"] = source
    return item


def _paper_gate_summary(vault_path, slug):
    if not slug or slug == "-":
        return None
    try:
        gate = build_paper_gate(Path(vault_path), slug)
    except Exception as exc:
        return {
            "status": "unknown",
            "conclusion": "unknown",
            "next_action": "inspect-paper-gate",
            "action_required_checks": [],
            "failure_checks": [],
            "error": str(exc),
        }
    check_suite = gate.get("check_suite")
    if not isinstance(check_suite, dict):
        return {
            "status": gate.get("status") or "unknown",
            "conclusion": "unknown",
            "next_action": gate.get("next_action") or "inspect-paper-gate",
            "action_required_checks": [],
            "failure_checks": [],
        }
    check_runs = check_suite.get("check_runs")
    if not isinstance(check_runs, list):
        return {
            "status": gate.get("status") or "unknown",
            "conclusion": check_suite.get("conclusion") or "unknown",
            "next_action": gate.get("next_action") or "inspect-paper-gate",
            "action_required_checks": [],
            "failure_checks": [],
        }
    return {
        "status": gate.get("status"),
        "conclusion": check_suite.get("conclusion"),
        "next_action": gate.get("next_action"),
        "action_required_checks": [
            run.get("name")
            for run in check_runs
            if run.get("conclusion") == "action_required" and run.get("name")
        ],
        "failure_checks": [
            run.get("name")
            for run in check_runs
            if run.get("conclusion") == "failure" and run.get("name")
        ],
    }


def _ready_to_promote_reason(gate_summary):
    if not gate_summary:
        return "paper gate status unknown"
    if gate_summary.get("failure_checks") or gate_summary.get("conclusion") == "failure":
        return "paper gate blocked by failed checks"
    if gate_summary.get("conclusion") == "action_required":
        if gate_summary.get("next_action") == "run-wiki-ingest-agent":
            return "wiki ingest handoff is ready"
        return "promotion gate is ready"
    if (
        gate_summary.get("conclusion") == "success"
        and gate_summary.get("next_action") == "run-wiki-ingest-agent"
    ):
        return "wiki ingest agent is approved and ready"
    if gate_summary.get("next_action") == "review-recorded-wiki-pages":
        return "wiki ingest has already been recorded"
    return "paper gate status unknown"


def _next_actions(entry):
    return [
        str(action).strip().lower()
        for action in (entry.get("next_actions") or [])
        if str(action).strip()
    ]


def _is_ready_to_promote(entry):
    if entry.get("status") not in _SUCCESS_STATUSES:
        return False
    revision_delta = entry.get("revision_delta") or {}
    after = revision_delta.get("after") if isinstance(revision_delta, dict) else None
    if isinstance(after, dict) and after.get("warning_count", 0):
        return False
    return any(
        action in {"promote-to-wiki", "promote-after-approval", "run-wiki-ingest-agent"}
        for action in _next_actions(entry)
    )


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _entry_time(entry):
    parsed = _parse_dt(entry.get("finished_at")) or _parse_dt(entry.get("started_at"))
    if parsed is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_stale_running_entry(entry, *, now=None):
    if entry.get("status") != "running":
        return False
    now = now or datetime.now(timezone.utc)
    return _entry_time(entry) < now - _STALE_RUNNING_AFTER


def _build_research_queue(entries, vault_path):
    queue = {bucket: [] for bucket in _RESEARCH_QUEUE_BUCKETS}

    for entry in entries:
        if _is_ready_to_promote(entry):
            item = _queue_item(entry, source="run")
            gate_summary = _paper_gate_summary(vault_path, item.get("paper_slug"))
            item["reason"] = _ready_to_promote_reason(gate_summary)
            if gate_summary:
                item["paper_gate"] = gate_summary
            queue["ready_to_promote"].append(item)

        for plan in entry.get("reader_revision_plans") or []:
            blocking_count = plan.get("blocking_count", 0) or 0
            next_action = str(plan.get("next_action") or "").lower()
            if blocking_count > 0 or next_action == "revise-reader":
                queue["needs_reader_repair"].append(
                    _queue_item(
                        entry,
                        paper_slug=plan.get("slug"),
                        title=plan.get("title"),
                        reason=f"reader revision plan has {blocking_count} blocking repairs",
                        source=plan.get("plan_path") or "reader_revision_plan",
                    )
                )

        for decision in entry.get("research_decisions") or []:
            recommendation = str(decision.get("recommendation") or "").lower()
            next_action = str(decision.get("next_action") or "").lower()
            if recommendation == "revise-reader" or next_action == "revise-reader":
                slug = decision.get("slug") or entry.get("paper_slug")
                already_queued = any(item.get("paper_slug") == slug for item in queue["needs_reader_repair"])
                if not already_queued:
                    queue["needs_reader_repair"].append(
                        _queue_item(
                            entry,
                            paper_slug=slug,
                            title=decision.get("title"),
                            reason="research decision requests reader revision",
                            source="research_decision",
                        )
                    )

        for plan in entry.get("reproduction_plans") or []:
            next_action = str(plan.get("next_action") or "").lower()
            missing_count = plan.get("missing_count", 0) or 0
            if next_action == "prepare-reproduction-plan" or missing_count > 0:
                queue["reproducibility_caveats"].append(
                    _queue_item(
                        entry,
                        paper_slug=plan.get("slug"),
                        title=plan.get("title"),
                        reason="reproducibility caveats need evidence review",
                        checks=["engineering_reproducibility"],
                        source=plan.get("plan_path") or "reproduction_plan",
                    )
                )

        revision_delta = entry.get("revision_delta") or {}
        after = revision_delta.get("after") if isinstance(revision_delta, dict) else None
        if not isinstance(after, dict):
            continue

        blocking_count = after.get("blocking_count", 0) or 0
        warning_count = after.get("warning_count", 0) or 0
        warning_checks = (
            revision_delta.get("remaining_warning_checks")
            or after.get("warning_checks")
            or []
        )
        if blocking_count == 0 and warning_count > 0:
            queue["warning_only"].append(
                _queue_item(
                    entry,
                    reason="critic has warnings but no blocking checks",
                    checks=warning_checks,
                    source="revision_delta",
                )
            )
        if "engineering_reproducibility" in warning_checks:
            queue["reproducibility_caveats"].append(
                _queue_item(
                    entry,
                    reason="engineering reproducibility evidence is incomplete",
                    checks=warning_checks,
                    source="revision_delta",
                )
            )

    return queue


def _render_run_line(entry):
    paper_slug = entry.get("paper_slug") or "-"
    return "- {run_id} | {workflow_type} | {status} / {state} | {paper_slug}".format(
        run_id=entry.get("run_id", "-"),
        workflow_type=entry.get("workflow_type", "unknown"),
        status=entry.get("status", "unknown"),
        state=entry.get("state", "unknown"),
        paper_slug=paper_slug,
    )


def _render_next_line(entry):
    next_actions = entry.get("next_actions") or []
    if not next_actions:
        return None
    return f"  next: {next_actions[0]}"


def _render_decision_lines(entry):
    lines = []
    for decision in entry.get("research_decisions") or []:
        slug = decision.get("slug") or entry.get("paper_slug") or "-"
        recommendation = decision.get("recommendation") or "-"
        next_action = decision.get("next_action") or "-"
        lines.append(f"  decision: {slug} -> {recommendation} / {next_action}")
    return lines


def _render_revision_plan_lines(entry):
    lines = []
    for plan in entry.get("reader_revision_plans") or []:
        slug = plan.get("slug") or entry.get("paper_slug") or "-"
        next_action = plan.get("next_action") or "-"
        blocking_count = plan.get("blocking_count", 0)
        warning_count = plan.get("warning_count", 0)
        lines.append(
            f"  revision-plan: {slug} -> {next_action} "
            f"(blocking={blocking_count}, warnings={warning_count})"
        )
    return lines


def _render_zotero_line(entry):
    zotero_results = entry.get("zotero_results")
    if not isinstance(zotero_results, dict):
        return None
    status = zotero_results.get("status")
    if status in {None, "not_run"}:
        return None
    parts = [f"  zotero: {status}"]
    if zotero_results.get("collection"):
        parts.append(f"collection={zotero_results['collection']}")
    if zotero_results.get("reason"):
        parts.append(f"reason={zotero_results['reason']}")
    if zotero_results.get("item_key"):
        parts.append(f"item_key={zotero_results['item_key']}")
    return " | ".join(parts)


def _append_run_detail_lines(lines, entry):
    next_line = _render_next_line(entry)
    if next_line:
        lines.append(next_line)
    zotero_line = _render_zotero_line(entry)
    if zotero_line:
        lines.append(zotero_line)
    lines.extend(_render_decision_lines(entry))
    lines.extend(_render_revision_plan_lines(entry))


def _render_research_queue(queue):
    lines = ["# EPI Research Queue", ""]
    for bucket in _RESEARCH_QUEUE_BUCKETS:
        title = bucket.replace("_", " ").title()
        lines.extend([f"## {title}", ""])
        items = queue.get(bucket) or []
        if not items:
            lines.extend(["No papers in this bucket.", ""])
            continue
        for item in items:
            lines.append(
                "- {paper_slug} | {status} / {state} | {run_id}".format(
                    paper_slug=item.get("paper_slug", "-"),
                    status=item.get("status", "unknown"),
                    state=item.get("state", "unknown"),
                    run_id=item.get("run_id", "-"),
                )
            )
            if item.get("title"):
                lines.append(f"  title: {item['title']}")
            if item.get("reason"):
                lines.append(f"  reason: {item['reason']}")
            if item.get("checks"):
                lines.append(f"  checks: {', '.join(item['checks'])}")
        lines.append("")
    return "\n".join(lines)


def _render_research_queue_item(item):
    lines = [
        "- {paper_slug} | {status} / {state} | {run_id}".format(
            paper_slug=item.get("paper_slug", "-"),
            status=item.get("status", "unknown"),
            state=item.get("state", "unknown"),
            run_id=item.get("run_id", "-"),
        )
    ]
    if item.get("title"):
        lines.append(f"  title: {item['title']}")
    if item.get("reason"):
        lines.append(f"  reason: {item['reason']}")
    if item.get("checks"):
        lines.append(f"  checks: {', '.join(item['checks'])}")
    for action in item.get("recommended_actions") or []:
        lines.append(f"  action: {action.get('action', '-')}")
        if action.get("command"):
            lines.append(f"  command: {action['command']}")
        if action.get("checklist"):
            lines.append(f"  checklist: {', '.join(action['checklist'])}")
        if action.get("human_gate_required"):
            lines.append("  human_gate_required: true")
    return lines


def _action_command(vault_path, *parts):
    subcommand = parts[0]
    args = ["python", r"scripts\orchestrator.py", subcommand, "--vault", str(Path(vault_path).resolve()), *parts[1:]]
    return " ".join(args)


def _paper_gate_action_command(vault_path, slug):
    args = [
        "python",
        r"scripts\orchestrator.py",
        "paper-gate",
        "--slug",
        slug,
        "--vault",
        str(Path(vault_path).resolve()),
    ]
    return " ".join(args)


def _wiki_ingest_handoff_action_command(vault_path, slug):
    args = [
        "python",
        r"scripts\orchestrator.py",
        "wiki-ingest-handoff",
        "--slug",
        slug,
        "--vault",
        str(Path(vault_path).resolve()),
    ]
    return " ".join(args)


def _wiki_ingest_trigger_action_command(vault_path, slug):
    args = [
        "python",
        r"scripts\orchestrator.py",
        "wiki-ingest-trigger",
        "--slug",
        slug,
        "--vault",
        str(Path(vault_path).resolve()),
    ]
    return " ".join(args)


def _record_human_approval_action_command(vault_path, slug):
    args = [
        "python",
        r"scripts\orchestrator.py",
        "record-human-approval",
        "--slug",
        slug,
        "--approved-by",
        "<name>",
        "--scope",
        "run-wiki-ingest-agent",
        "--vault",
        str(Path(vault_path).resolve()),
    ]
    return " ".join(args)


def _promote_action_command(vault_path, slug):
    args = [
        "python",
        r"scripts\orchestrator.py",
        "promote-to-wiki",
        "--slug",
        slug,
        "--approved-by",
        "<name>",
        "--vault",
        str(Path(vault_path).resolve()),
    ]
    return " ".join(args)


def _paper_gate_allows_promotion(item):
    gate_summary = item.get("paper_gate")
    if not isinstance(gate_summary, dict):
        return False
    action_required_checks = set(gate_summary.get("action_required_checks") or [])
    return (
        gate_summary.get("conclusion") == "action_required"
        and gate_summary.get("next_action") == "promote-to-wiki"
        and not gate_summary.get("failure_checks")
        and action_required_checks == {"human-approval"}
    )


def _paper_gate_allows_wiki_ingest(item):
    gate_summary = item.get("paper_gate")
    if not isinstance(gate_summary, dict):
        return False
    action_required_checks = set(gate_summary.get("action_required_checks") or [])
    return (
        gate_summary.get("conclusion") == "action_required"
        and gate_summary.get("next_action") == "run-wiki-ingest-agent"
        and not gate_summary.get("failure_checks")
        and action_required_checks == {"human-approval"}
    )


def _paper_gate_ready_for_wiki_ingest(item):
    gate_summary = item.get("paper_gate")
    if not isinstance(gate_summary, dict):
        return False
    return (
        gate_summary.get("conclusion") == "success"
        and gate_summary.get("next_action") == "run-wiki-ingest-agent"
        and not gate_summary.get("failure_checks")
        and not gate_summary.get("action_required_checks")
    )


def _recommended_actions(bucket, item, vault_path):
    slug = item.get("paper_slug")
    if not slug or slug == "-":
        return []
    if bucket == "needs_reader_repair":
        return [
            {
                "action": "redo-read-recritic",
                "command": _action_command(
                    vault_path,
                    "redo-read",
                    "--slug",
                    slug,
                    "--from-revision-plan",
                    "--recritic",
                ),
                "human_gate_required": False,
                "uses": item.get("source"),
            }
        ]
    if bucket == "reproducibility_caveats":
        return [
            {
                "action": "review-reproducibility-caveats",
                "checklist": ["code", "data", "model", "config", "simulator", "hardware"],
                "human_gate_required": True,
                "reason": "keep this as a short evidence-review cue unless the user asks for a reproduction run",
            }
        ]
    if bucket == "ready_to_promote":
        actions = [
            {
                "action": "inspect-paper-gate",
                "command": _paper_gate_action_command(vault_path, slug),
                "human_gate_required": True,
            }
        ]
        if _paper_gate_allows_promotion(item):
            actions.append(
                {
                    "action": "promote-to-wiki",
                    "command": _promote_action_command(vault_path, slug),
                    "human_gate_required": True,
                }
            )
        if _paper_gate_allows_wiki_ingest(item):
            actions.append(
                {
                    "action": "wiki-ingest-handoff",
                    "command": _wiki_ingest_handoff_action_command(vault_path, slug),
                    "human_gate_required": True,
                    "uses": "wiki-ingest-brief.json",
                    "checklist": [
                        "read target vault AGENTS.md and _meta/*",
                        "merge existing pages before creating new ones",
                        "respect vault frontmatter, tags, links, and staged writes",
                    ],
                }
            )
            actions.append(
                {
                    "action": "record-human-approval",
                    "command": _record_human_approval_action_command(vault_path, slug),
                    "human_gate_required": True,
                    "uses": "human-approval.json",
                    "checklist": [
                        "record approval before the wiki ingest agent writes final or staged vault pages",
                        "use the same approved-by value later for record-wiki-ingest",
                    ],
                }
            )
        if _paper_gate_ready_for_wiki_ingest(item):
            actions.append(
                {
                    "action": "wiki-ingest-handoff",
                    "command": _wiki_ingest_handoff_action_command(vault_path, slug),
                    "human_gate_required": False,
                    "uses": "wiki-ingest-brief.json",
                    "checklist": [
                        "confirm ready_for_agent=true",
                        "read target vault AGENTS.md and _meta/*",
                        "keep final page provenance source-grounded",
                    ],
                }
            )
            actions.append(
                {
                    "action": "wiki-ingest-trigger",
                    "command": _wiki_ingest_trigger_action_command(vault_path, slug),
                    "human_gate_required": False,
                    "uses": "wiki-agent-trigger.json",
                    "checklist": [
                        "create the trigger package for the current Claude, Codex, or wiki-capable agent",
                        "write or stage final pages under the target vault contract",
                        "create final-source-review.json, then run record-wiki-ingest",
                    ],
                }
            )
        return actions
    if bucket == "warning_only":
        return [
            {
                "action": "inspect-warning",
                "checklist": item.get("checks") or [],
                "human_gate_required": True,
            }
        ]
    return []


def _with_recommended_actions(bucket, items, vault_path):
    enriched = []
    for item in items:
        payload = dict(item)
        if bucket == "ready_to_promote":
            gate_summary = _paper_gate_summary(vault_path, payload.get("paper_slug"))
            payload["reason"] = _ready_to_promote_reason(gate_summary)
            if gate_summary:
                payload["paper_gate"] = gate_summary
            else:
                payload.pop("paper_gate", None)
        payload["recommended_actions"] = _recommended_actions(bucket, payload, vault_path)
        enriched.append(payload)
    return enriched


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _render_dashboard(entries, summary, research_queue=None):
    research_queue = research_queue or {bucket: [] for bucket in _RESEARCH_QUEUE_BUCKETS}
    lines = ["# EPI Run Dashboard", ""]
    if not entries:
        lines.extend(
            [
                "## Summary",
                "",
                "- total runs: 0",
                "- failed runs: 0",
                "- human gate pending: 0",
                "",
                "## Needs Attention",
                "",
                "No runs need attention.",
                "",
                "## Research Queue",
                "",
                *[f"- {bucket}: 0" for bucket in _RESEARCH_QUEUE_BUCKETS],
                "",
                "## Recent Failures",
                "",
                "No failed runs.",
                "",
                "## Pending Human Gate",
                "",
                "No runs waiting on a human gate.",
                "",
                "## Latest Success By Workflow",
                "",
                "No successful runs yet.",
                "",
                "## Runs By Workflow",
                "",
                "No runs indexed yet.",
                "",
                "## Recent Runs",
                "",
                "No runs indexed yet.",
                "",
            ]
        )
        return "\n".join(lines)

    grouped = _build_grouped_summaries(entries)
    lines.extend(
        [
            "## Summary",
            "",
            f"- total runs: {summary['total_runs']}",
            f"- failed runs: {summary['failed_run_count']}",
            f"- human gate pending: {summary['human_gate_pending_count']}",
            "",
            "## Needs Attention",
            "",
        ]
    )

    attention_entries = [entry for entry in entries if _needs_attention(entry)]
    if attention_entries:
        for entry in attention_entries:
            lines.append(_render_run_line(entry))
            _append_run_detail_lines(lines, entry)
    else:
        lines.append("No runs need attention.")

    lines.extend(["", "## Research Queue", ""])
    for bucket in _RESEARCH_QUEUE_BUCKETS:
        lines.append(f"- {bucket}: {len(research_queue.get(bucket) or [])}")

    lines.extend(["", "## Recent Failures", ""])
    if grouped["latest_failures"]:
        for entry in grouped["latest_failures"]:
            lines.append(_render_run_line(entry))
            _append_run_detail_lines(lines, entry)
    else:
        lines.append("No failed runs.")

    lines.extend(["", "## Pending Human Gate", ""])
    if grouped["latest_human_gate_pending"]:
        for entry in grouped["latest_human_gate_pending"]:
            lines.append(_render_run_line(entry))
            _append_run_detail_lines(lines, entry)
    else:
        lines.append("No runs waiting on a human gate.")

    lines.extend(["", "## Latest Success By Workflow", ""])
    if grouped["latest_success_by_workflow"]:
        for workflow_type, entry in grouped["latest_success_by_workflow"].items():
            lines.append(f"- {workflow_type}: {entry.get('run_id', '-')}")
            lines.append(f"  {entry.get('status', 'unknown')} / {entry.get('state', 'unknown')} | {entry.get('paper_slug') or '-'}")
            _append_run_detail_lines(lines, entry)
    else:
        lines.append("No successful runs yet.")

    lines.extend(["", "## Runs By Workflow", ""])
    for workflow_type, count in summary["workflow_counts"].items():
        lines.append(f"- {workflow_type}: {count}")

    lines.extend(["", "## Recent Runs", ""])
    for entry in entries:
        lines.append(_render_run_line(entry))
        _append_run_detail_lines(lines, entry)
    lines.append("")
    return "\n".join(lines)


def _render_filtered_dashboard(title, entries, empty_text):
    lines = [f"# {title}", ""]
    if not entries:
        lines.extend([empty_text, ""])
        return "\n".join(lines)

    for entry in entries:
        lines.append(_render_run_line(entry))
        _append_run_detail_lines(lines, entry)
    lines.append("")
    return "\n".join(lines)


def refresh_run_index(vault_path):
    runs_root = _runs_root(vault_path)
    runs_root.mkdir(parents=True, exist_ok=True)

    entries = []
    for child in runs_root.iterdir():
        if not child.is_dir():
            continue
        entry = _normalize_run_entry(child)
        if entry is None:
            continue
        entries.append(entry)

    entries.sort(key=_sort_key, reverse=True)

    summary = _build_summary(entries)
    grouped = _build_grouped_summaries(entries)
    research_queue = _build_research_queue(entries, vault_path)
    index_payload = {
        "summary": summary,
        "research_queue": research_queue,
        "latest_failures": grouped["latest_failures"],
        "latest_human_gate_pending": grouped["latest_human_gate_pending"],
        "latest_success_by_workflow": grouped["latest_success_by_workflow"],
        "runs": entries,
    }
    _write_json(runs_root / "index.json", index_payload)
    _write_json(runs_root / "research-queue.json", research_queue)
    for stale_path in [runs_root / "research-agenda.json", runs_root / "research-agenda.md"]:
        if stale_path.exists():
            stale_path.unlink()
    (runs_root / "research-queue.md").write_text(_render_research_queue(research_queue), encoding="utf-8")
    (runs_root / "dashboard.md").write_text(
        _render_dashboard(entries, summary, research_queue),
        encoding="utf-8",
    )
    failures = [entry for entry in entries if entry.get("status") not in _SUCCESS_STATUSES]
    human_gate_pending = [entry for entry in entries if _human_gate_status(entry) in _HUMAN_GATE_PENDING]
    recent_success = [entry for entry in entries if entry.get("status") in _SUCCESS_STATUSES]
    (runs_root / "dashboard-failures.md").write_text(
        _render_filtered_dashboard("EPI Failed Runs", failures, "No failed runs."),
        encoding="utf-8",
    )
    (runs_root / "dashboard-human-gate.md").write_text(
        _render_filtered_dashboard("EPI Human Gate Runs", human_gate_pending, "No runs waiting on a human gate."),
        encoding="utf-8",
    )
    (runs_root / "dashboard-recent-success.md").write_text(
        _render_filtered_dashboard("EPI Recent Successful Runs", recent_success, "No successful runs yet."),
        encoding="utf-8",
    )
    return index_payload


def _write_lifecycle_manifest(vault_path, manifest):
    lifecycle_root = _lifecycle_root(vault_path)
    lifecycle_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = lifecycle_root / f"{timestamp}-run-lifecycle.json"
    _write_json(path, manifest)
    return path


def prune_run_lifecycle(
    vault_path,
    *,
    keep_latest=15,
    keep_per_workflow=2,
    max_age_days=None,
    apply=False,
):
    runs_root = _runs_root(vault_path)
    runs_root.mkdir(parents=True, exist_ok=True)

    entries = []
    skipped = []
    for child in runs_root.iterdir():
        if not child.is_dir():
            continue
        entry = _normalize_run_entry(child)
        if entry is None:
            entry = {
                "run_id": child.name,
                "workflow_type": "unknown",
                "state": "invalid",
                "status": "failed",
                "started_at": datetime.fromtimestamp(child.stat().st_mtime, timezone.utc).isoformat(),
                "finished_at": datetime.fromtimestamp(child.stat().st_mtime, timezone.utc).isoformat(),
                "path": str(child),
                "invalid_run_state": True,
            }
        else:
            entry = dict(entry)
            entry["path"] = str(child)
        entries.append(entry)

    entries.sort(key=_sort_key, reverse=True)
    now = datetime.now(timezone.utc)
    cleanup_eligible_entries = [
        entry
        for entry in entries
        if (
            entry.get("status", "unknown") in _TERMINAL_CLEANUP_STATUSES
            or _is_stale_running_entry(entry, now=now)
        )
        and _human_gate_status(entry) not in _HUMAN_GATE_PENDING
    ]
    retention_entries = [
        entry
        for entry in cleanup_eligible_entries
        if not entry.get("invalid_run_state")
        and not _is_stale_running_entry(entry, now=now)
    ]
    protected_ids = {entry["run_id"] for entry in retention_entries[: max(0, keep_latest)]}
    by_workflow = {}
    for entry in retention_entries:
        by_workflow.setdefault(entry.get("workflow_type", "unknown"), []).append(entry)
    for workflow_entries in by_workflow.values():
        protected_ids.update(entry["run_id"] for entry in workflow_entries[: max(0, keep_per_workflow)])

    cutoff = None
    if max_age_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    candidates = []
    protected = []
    for entry in entries:
        run_id = entry["run_id"]
        status = entry.get("status", "unknown")
        stale_running = _is_stale_running_entry(entry, now=now)
        if _human_gate_status(entry) in _HUMAN_GATE_PENDING:
            protected.append({"run_id": run_id, "reason": "active_or_human_gate_pending"})
            continue
        if status in _PROTECTED_CLEANUP_STATUSES and not stale_running:
            protected.append({"run_id": run_id, "reason": "active_or_human_gate_pending"})
            continue
        if status not in _TERMINAL_CLEANUP_STATUSES and not stale_running:
            protected.append({"run_id": run_id, "reason": f"non_cleanup_status:{status}"})
            continue
        if run_id in protected_ids:
            protected.append({"run_id": run_id, "reason": "retention_floor"})
            continue
        if cutoff is not None and _entry_time(entry) >= cutoff:
            protected.append({"run_id": run_id, "reason": "younger_than_max_age"})
            continue
        candidates.append(
            {
                "run_id": run_id,
                "workflow_type": entry.get("workflow_type"),
                "status": status,
                "cleanup_reason": "stale_running" if stale_running else (
                    "invalid_run_state" if entry.get("invalid_run_state") else "retention_overflow"
                ),
                "started_at": entry.get("started_at"),
                "finished_at": entry.get("finished_at"),
                "path": entry["path"],
            }
        )

    deleted = []
    if apply:
        for candidate in candidates:
            path = Path(candidate["path"])
            if path.parent.resolve() != runs_root.resolve():
                skipped.append({"run_id": candidate["run_id"], "reason": "path_outside_runs_root"})
                continue
            shutil.rmtree(path)
            deleted.append(candidate)
        refresh_run_index(vault_path)

    manifest = {
        "dry_run": not apply,
        "vault_path": str(Path(vault_path)),
        "runs_root": str(runs_root),
        "policy": {
            "keep_latest": keep_latest,
            "keep_per_workflow": keep_per_workflow,
            "max_age_days": max_age_days,
            "eligible_statuses": sorted(_TERMINAL_CLEANUP_STATUSES),
            "protected_statuses": sorted(_PROTECTED_CLEANUP_STATUSES),
            "stale_running_after_hours": _STALE_RUNNING_AFTER.total_seconds() / 3600,
        },
        "total_run_dirs": len(entries),
        "candidate_count": len(candidates),
        "deleted_count": len(deleted),
        "candidates": candidates,
        "deleted": deleted,
        "protected": protected,
        "skipped": skipped,
    }
    if apply or candidates:
        manifest_path = _write_lifecycle_manifest(vault_path, manifest)
        manifest["manifest_path"] = str(manifest_path)
    return manifest


def auto_prune_run_lifecycle(
    vault_path,
    *,
    keep_latest=15,
    keep_per_workflow=2,
    max_age_days=None,
):
    runs_root = _runs_root(vault_path)
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir_count = sum(1 for child in runs_root.iterdir() if child.is_dir())
    if run_dir_count <= keep_latest:
        return {
            "dry_run": False,
            "auto": True,
            "skipped": True,
            "reason": "below_threshold",
            "runs_root": str(runs_root),
            "total_run_dirs": run_dir_count,
            "policy": {
                "keep_latest": keep_latest,
                "keep_per_workflow": keep_per_workflow,
                "max_age_days": max_age_days,
            },
            "candidate_count": 0,
            "deleted_count": 0,
            "deleted": [],
        }
    result = prune_run_lifecycle(
        vault_path,
        keep_latest=keep_latest,
        keep_per_workflow=keep_per_workflow,
        max_age_days=max_age_days,
        apply=True,
    )
    result["auto"] = True
    result["skipped"] = False
    return result


def render_run_lifecycle(result):
    action = "Dry run" if result.get("dry_run") else "Applied"
    lines = [
        f"EPI Run Lifecycle - {action}",
        "",
        f"- runs_root: {result.get('runs_root')}",
        f"- total_run_dirs: {result.get('total_run_dirs')}",
        f"- candidates: {result.get('candidate_count')}",
        f"- deleted: {result.get('deleted_count')}",
    ]
    if result.get("manifest_path"):
        lines.append(f"- manifest: {result['manifest_path']}")
    candidates = result.get("candidates") or []
    if candidates:
        lines.extend(["", "## Candidates"])
        for candidate in candidates[:20]:
            lines.append(
                f"- {candidate['run_id']} ({candidate.get('workflow_type')}, {candidate.get('status')})"
            )
        if len(candidates) > 20:
            lines.append(f"- ... {len(candidates) - 20} more")
    lines.append("")
    return "\n".join(lines)


def load_run_index(vault_path):
    runs_root = _runs_root(vault_path)
    index_path = runs_root / "index.json"
    payload = _load_json(index_path)
    if isinstance(payload, dict):
        return payload
    return refresh_run_index(vault_path)


def query_research_queue(vault_path, *, bucket=None, limit=10, include_actions=False):
    index_payload = load_run_index(vault_path)
    if not isinstance(index_payload.get("research_queue"), dict):
        index_payload = refresh_run_index(vault_path)
    queue = {
        queue_bucket: list(index_payload.get("research_queue", {}).get(queue_bucket) or [])
        for queue_bucket in _RESEARCH_QUEUE_BUCKETS
    }

    if bucket:
        items = queue.get(bucket, [])[:limit]
        if include_actions:
            items = _with_recommended_actions(bucket, items, vault_path)
        return {
            "title": f"EPI Research Queue - {bucket}",
            "bucket": bucket,
            "items": items,
        }

    return {
        "title": "EPI Research Queue",
        "bucket": None,
        "queue": {
            queue_bucket: (
                _with_recommended_actions(queue_bucket, items[:limit], vault_path)
                if include_actions
                else items[:limit]
            )
            for queue_bucket, items in queue.items()
        },
    }


def render_research_queue_query(query_result):
    lines = [query_result["title"], ""]

    if query_result.get("bucket"):
        items = query_result.get("items") or []
        if not items:
            lines.extend(["No papers in this bucket.", ""])
            return "\n".join(lines)
        for item in items:
            lines.extend(_render_research_queue_item(item))
        lines.append("")
        return "\n".join(lines)

    queue = query_result.get("queue") or {}
    for bucket in _RESEARCH_QUEUE_BUCKETS:
        lines.extend([f"## {bucket}", ""])
        items = queue.get(bucket) or []
        if not items:
            lines.extend(["No papers in this bucket.", ""])
            continue
        for item in items:
            lines.extend(_render_research_queue_item(item))
        lines.append("")
    return "\n".join(lines)


def query_runs(
    vault_path,
    *,
    failed=False,
    human_gate=False,
    workflow=None,
    latest_success=None,
    limit=10,
):
    index_payload = load_run_index(vault_path)
    runs = list(index_payload.get("runs", []))

    if latest_success:
        entry = index_payload.get("latest_success_by_workflow", {}).get(latest_success)
        matches = [entry] if entry else []
        title = f"EPI Runs Query - latest success for {latest_success}"
    else:
        matches = runs
        title = "EPI Runs Query"
        if failed:
            matches = [entry for entry in matches if entry.get("status") not in _SUCCESS_STATUSES]
            title = "EPI Runs Query - failed runs"
        elif human_gate:
            matches = [entry for entry in matches if _human_gate_status(entry) in _HUMAN_GATE_PENDING]
            title = "EPI Runs Query - human gate runs"

        if workflow:
            matches = [entry for entry in matches if entry.get("workflow_type") == workflow]
            title = f"{title} ({workflow})"

        matches = matches[:limit]

    return {
        "title": title,
        "runs": matches,
    }


def render_runs_query(query_result):
    lines = [query_result["title"], ""]
    runs = query_result.get("runs", [])
    if not runs:
        lines.extend(["No matching runs.", ""])
        return "\n".join(lines)

    for entry in runs:
        lines.append(_render_run_line(entry))
        next_line = _render_next_line(entry)
        if next_line:
            lines.append(next_line)
        lines.extend(_render_decision_lines(entry))
    lines.append("")
    return "\n".join(lines)
