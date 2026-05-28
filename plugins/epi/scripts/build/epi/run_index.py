import json
from pathlib import Path
from collections import Counter


_SUCCESS_STATUSES = {"success", "succeeded"}
_HUMAN_GATE_PENDING = {"pending", "required"}


def _runs_root(vault_path):
    return Path(vault_path) / "_runs"


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

    return {
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


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _render_dashboard(entries, summary):
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
            next_line = _render_next_line(entry)
            if next_line:
                lines.append(next_line)
    else:
        lines.append("No runs need attention.")

    lines.extend(["", "## Recent Failures", ""])
    if grouped["latest_failures"]:
        for entry in grouped["latest_failures"]:
            lines.append(_render_run_line(entry))
            next_line = _render_next_line(entry)
            if next_line:
                lines.append(next_line)
    else:
        lines.append("No failed runs.")

    lines.extend(["", "## Pending Human Gate", ""])
    if grouped["latest_human_gate_pending"]:
        for entry in grouped["latest_human_gate_pending"]:
            lines.append(_render_run_line(entry))
            next_line = _render_next_line(entry)
            if next_line:
                lines.append(next_line)
    else:
        lines.append("No runs waiting on a human gate.")

    lines.extend(["", "## Latest Success By Workflow", ""])
    if grouped["latest_success_by_workflow"]:
        for workflow_type, entry in grouped["latest_success_by_workflow"].items():
            lines.append(f"- {workflow_type}: {entry.get('run_id', '-')}")
            lines.append(f"  {entry.get('status', 'unknown')} / {entry.get('state', 'unknown')} | {entry.get('paper_slug') or '-'}")
            next_line = _render_next_line(entry)
            if next_line:
                lines.append(next_line)
    else:
        lines.append("No successful runs yet.")

    lines.extend(["", "## Runs By Workflow", ""])
    for workflow_type, count in summary["workflow_counts"].items():
        lines.append(f"- {workflow_type}: {count}")

    lines.extend(["", "## Recent Runs", ""])
    for entry in entries:
        lines.append(_render_run_line(entry))
        next_line = _render_next_line(entry)
        if next_line:
            lines.append(next_line)
    lines.append("")
    return "\n".join(lines)


def _render_filtered_dashboard(title, entries, empty_text):
    lines = [f"# {title}", ""]
    if not entries:
        lines.extend([empty_text, ""])
        return "\n".join(lines)

    for entry in entries:
        lines.append(_render_run_line(entry))
        next_line = _render_next_line(entry)
        if next_line:
            lines.append(next_line)
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
    index_payload = {
        "summary": summary,
        "latest_failures": grouped["latest_failures"],
        "latest_human_gate_pending": grouped["latest_human_gate_pending"],
        "latest_success_by_workflow": grouped["latest_success_by_workflow"],
        "runs": entries,
    }
    _write_json(runs_root / "index.json", index_payload)
    (runs_root / "dashboard.md").write_text(_render_dashboard(entries, summary), encoding="utf-8")
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


def load_run_index(vault_path):
    runs_root = _runs_root(vault_path)
    index_path = runs_root / "index.json"
    payload = _load_json(index_path)
    if isinstance(payload, dict):
        return payload
    return refresh_run_index(vault_path)


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
    lines.append("")
    return "\n".join(lines)
