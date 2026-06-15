from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from paper_source.artifacts import read_json, utc_now, write_json_atomic, write_text_atomic


SCHEMA_VERSION = "paper-source-improvement-brief-v1"
BENCHMARK_SCHEMA_VERSION = "paper-source-benchmark-v1"
QUALITY_LOOP_STEPS = [
    "plugin-eval",
    "paper-source-quality-gates",
    "benchmark",
    "compare-before-after",
    "improvement-brief",
    "skill-aware-evolve-proposal",
]
QUALITY_GATE_SOURCE_KIND = "paper_source_quality_gates"
REQUIRED_QUALITY_SOURCES = ["plugin_eval", QUALITY_GATE_SOURCE_KIND, "benchmark"]
NON_REGRESSION_METRICS = [
    "plugin_eval_score",
    "coverage_percent",
    "paper-source-quality-gate-pass-rate",
    "benchmark_pass_rate",
]
BENCHMARK_CASE_STATUSES = {"pass", "fail", "skip", "warning"}
# Retired metric ids are ignored so historical reports cannot satisfy current gates.
RETIRED_METRIC_NAMES = {
    "epi-quality-gate-pass-rate",
    "epi_quality_gate_pass_rate",
}


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _normalize_metric_name(name: str) -> str | None:
    normalized = name.strip().replace(" ", "_")
    if normalized in RETIRED_METRIC_NAMES:
        return None
    return normalized


def _collect_metric(metrics: dict[str, Any], name: str, value: Any) -> None:
    number = _coerce_number(value)
    normalized_name = _normalize_metric_name(name)
    if normalized_name is not None and number is not None:
        metrics[normalized_name] = number


def extract_metrics(payload: dict[str, Any], *, source_kind: str = "generic") -> dict[str, float]:
    metrics: dict[str, float] = {}
    if not payload:
        return metrics

    for key in ["plugin_eval_score", "coverage_percent", "benchmark_pass_rate"]:
        if key in payload:
            _collect_metric(metrics, key, payload[key])

    if source_kind == "plugin_eval":
        for key in ["score", "overall_score"]:
            if key in payload:
                _collect_metric(metrics, "plugin_eval_score", payload[key])
        summary = payload.get("summary")
        if isinstance(summary, dict):
            for key in ["score", "overall_score"]:
                if key in summary:
                    _collect_metric(metrics, "plugin_eval_score", summary[key])

    nested_metrics = payload.get("metrics")
    if isinstance(nested_metrics, dict):
        for key, value in nested_metrics.items():
            _collect_metric(metrics, str(key), value)
    elif isinstance(nested_metrics, list):
        for item in nested_metrics:
            if not isinstance(item, dict):
                continue
            metric_id = item.get("id") or item.get("name") or item.get("metric")
            if metric_id:
                _collect_metric(metrics, str(metric_id), item.get("value"))

    cases = payload.get("cases")
    if isinstance(cases, list) and cases:
        passed = 0
        total = 0
        for case in cases:
            if not isinstance(case, dict):
                continue
            total += 1
            if case.get("passed") is True or case.get("status") == "pass":
                passed += 1
        if total:
            metrics.setdefault("benchmark_pass_rate", round(passed / total, 4))

    return metrics


def _merge_metrics(*metric_groups: dict[str, Any] | None) -> dict[str, float]:
    merged: dict[str, float] = {}
    for group in metric_groups:
        if not group:
            continue
        for key, value in group.items():
            _collect_metric(merged, str(key), value)
    return merged


def _metric_comparisons(before_metrics: dict[str, float], after_metrics: dict[str, float]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for metric in sorted(set(before_metrics) & set(after_metrics)):
        before = before_metrics[metric]
        after = after_metrics[metric]
        delta = round(after - before, 6)
        if delta > 0:
            trend = "improved"
        elif delta < 0:
            trend = "regressed"
        else:
            trend = "unchanged"
        comparisons.append(
            {
                "metric": metric,
                "before": before,
                "after": after,
                "delta": delta,
                "trend": trend,
                "assumption": "higher_is_better",
            }
        )
    return comparisons


def _gate_id(metric: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", metric).strip("_").lower()
    return f"{safe}_non_regression"


def default_acceptance_gates(before_metrics: dict[str, float]) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = [{"id": "human_approval", "required": True}]
    for metric in NON_REGRESSION_METRICS:
        if metric in before_metrics:
            gates.append(
                {
                    "id": _gate_id(metric),
                    "metric": metric,
                    "operator": ">=",
                    "value": before_metrics[metric],
                    "required": True,
                }
            )
    return gates


def _source_record(path: Path | None, source_kind: str) -> dict[str, Any]:
    payload = read_json(path, default={}) if path is not None else {}
    payload = payload if isinstance(payload, dict) else {}
    record = {
        "kind": source_kind,
        "path": str(path) if path else None,
        "present": bool(path and path.exists()),
        "metrics": extract_metrics(payload, source_kind=source_kind),
    }
    if source_kind == "benchmark":
        record["benchmark_contract"] = validate_benchmark_contract(payload)
    return record


def validate_benchmark_contract(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if not payload:
        return {
            "schema_version": None,
            "valid": False,
            "case_count": 0,
            "metric_count": 0,
            "issues": ["benchmark JSON is missing or empty"],
        }

    schema_version = payload.get("schema_version")
    if schema_version != BENCHMARK_SCHEMA_VERSION:
        issues.append(f"schema_version must be {BENCHMARK_SCHEMA_VERSION}")
    if not str(payload.get("benchmark_id") or "").strip():
        issues.append("benchmark_id is required")

    cases = payload.get("cases")
    if cases is not None and not isinstance(cases, list):
        issues.append("cases must be a list when present")
        cases = []
    case_count = len(cases or [])
    for index, case in enumerate(cases or [], start=1):
        if not isinstance(case, dict):
            issues.append(f"cases[{index}] must be an object")
            continue
        if not str(case.get("id") or case.get("name") or "").strip():
            issues.append(f"cases[{index}] must include id or name")
        status = str(case.get("status") or "").strip().lower()
        if status not in BENCHMARK_CASE_STATUSES:
            issues.append(
                f"cases[{index}] status must be one of {', '.join(sorted(BENCHMARK_CASE_STATUSES))}"
            )

    metric_count = 0
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        metric_count = len(metrics)
    elif isinstance(metrics, list):
        metric_count = len([item for item in metrics if isinstance(item, dict)])
    elif metrics is not None:
        issues.append("metrics must be an object or list when present")

    if case_count == 0 and metric_count == 0:
        issues.append("benchmark must include cases[] or metrics")

    return {
        "schema_version": schema_version,
        "valid": not issues,
        "case_count": case_count,
        "metric_count": metric_count,
        "issues": issues,
    }


def _source_completeness(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing_sources = [
        source_name
        for source_name in REQUIRED_QUALITY_SOURCES
        if not sources.get(source_name, {}).get("present")
    ]
    invalid_sources = [
        source_name
        for source_name in REQUIRED_QUALITY_SOURCES
        if sources.get(source_name, {}).get("present")
        and sources.get(source_name, {}).get("benchmark_contract", {}).get("valid") is False
    ]
    return {
        "required_sources": REQUIRED_QUALITY_SOURCES,
        "present_sources": [
            source_name
            for source_name in REQUIRED_QUALITY_SOURCES
            if sources.get(source_name, {}).get("present")
        ],
        "missing_sources": missing_sources,
        "invalid_sources": invalid_sources,
        "complete": not missing_sources and not invalid_sources,
    }


def build_improvement_brief(
    *,
    target_asset: str,
    rationale: str,
    proposed_change: dict[str, Any],
    before_metrics: dict[str, Any] | None = None,
    after_metrics: dict[str, Any] | None = None,
    plugin_eval_path: Path | None = None,
    metric_pack_path: Path | None = None,
    benchmark_path: Path | None = None,
    evidence: list[str] | None = None,
    reflection_type: str = "OPTIMIZATION",
    evidence_type: str = "plugin_eval_warning",
    brief_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(proposed_change, dict) or not proposed_change:
        raise ValueError("proposed_change must be a non-empty object")

    sources = {
        "plugin_eval": _source_record(plugin_eval_path, "plugin_eval"),
        QUALITY_GATE_SOURCE_KIND: _source_record(metric_pack_path, "metric_pack"),
        "benchmark": _source_record(benchmark_path, "benchmark"),
    }
    before = _merge_metrics(before_metrics)
    after = _merge_metrics(
        sources["plugin_eval"]["metrics"],
        sources[QUALITY_GATE_SOURCE_KIND]["metrics"],
        sources["benchmark"]["metrics"],
        after_metrics,
    )
    evidence_items = list(evidence or [])
    for source in sources.values():
        if source["present"]:
            evidence_items.append(source["path"])

    source_completeness = _source_completeness(sources)
    gates = default_acceptance_gates(before)
    if not source_completeness["complete"]:
        gates.append(
            {
                "id": "quality_loop_sources_complete",
                "required": True,
                "status": "missing",
                "missing_sources": source_completeness["missing_sources"],
                "invalid_sources": source_completeness["invalid_sources"],
            }
        )
    comparisons = _metric_comparisons(before, after)
    next_action = (
        "propose-evolution"
        if source_completeness["complete"]
        else "collect-missing-quality-evidence"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "id": brief_id or f"brief-{uuid.uuid4().hex[:12]}",
        "created_at": utc_now(),
        "quality_loop": QUALITY_LOOP_STEPS,
        "target_asset": target_asset,
        "rationale": rationale,
        "proposed_change": proposed_change,
        "sources": sources,
        "source_completeness": source_completeness,
        "before_metrics": before,
        "after_metrics": after,
        "metric_comparisons": comparisons,
        "improvement_summary": {
            "regressed_metrics": [
                item["metric"] for item in comparisons if item["trend"] == "regressed"
            ],
            "improved_metrics": [
                item["metric"] for item in comparisons if item["trend"] == "improved"
            ],
            "next_action": next_action,
        },
        "proposed_evolution": {
            "reflection_type": reflection_type,
            "evidence_type": evidence_type,
            "target_asset": target_asset,
            "rationale": rationale,
            "proposed_change": proposed_change,
            "evidence": evidence_items,
            "before_metrics": before,
            "acceptance_gates": gates,
        },
    }


def render_improvement_brief(brief: dict[str, Any]) -> str:
    lines = [
        f"# Paper Source Improvement Brief - {brief.get('id')}",
        "",
        f"schema_version: {brief.get('schema_version')}",
        f"target_asset: {brief.get('target_asset')}",
        f"next_action: {brief.get('improvement_summary', {}).get('next_action')}",
        "",
        "## Quality Loop",
        "",
    ]
    lines.extend(f"- {step}" for step in brief.get("quality_loop", []))
    completeness = brief.get("source_completeness") or {}
    lines.extend(["", "## Source Completeness", ""])
    lines.append(f"- complete: {completeness.get('complete')}")
    missing_sources = completeness.get("missing_sources") or []
    invalid_sources = completeness.get("invalid_sources") or []
    if missing_sources:
        lines.append(f"- missing_sources: {', '.join(missing_sources)}")
    else:
        lines.append("- missing_sources: none")
    if invalid_sources:
        lines.append(f"- invalid_sources: {', '.join(invalid_sources)}")
    else:
        lines.append("- invalid_sources: none")
    lines.extend(["", "## Metric Comparison", ""])
    comparisons = brief.get("metric_comparisons") or []
    if comparisons:
        lines.append("| Metric | Before | After | Delta | Trend |")
        lines.append("| --- | ---: | ---: | ---: | --- |")
        for item in comparisons:
            lines.append(
                f"| {item['metric']} | {item['before']} | {item['after']} | {item['delta']} | {item['trend']} |"
            )
    else:
        lines.append("- No comparable before/after metrics were provided.")
    lines.extend(["", "## Proposed Evolution", ""])
    proposed = brief.get("proposed_evolution") or {}
    lines.append(f"- reflection_type: {proposed.get('reflection_type')}")
    lines.append(f"- evidence_type: {proposed.get('evidence_type')}")
    lines.append(f"- target_asset: {proposed.get('target_asset')}")
    lines.append(f"- rationale: {brief.get('rationale')}")
    lines.append("- acceptance_gates:")
    for gate in proposed.get("acceptance_gates") or []:
        metric = gate.get("metric")
        if metric:
            lines.append(f"  - {gate.get('id')}: {metric} {gate.get('operator')} {gate.get('value')}")
        else:
            lines.append(f"  - {gate.get('id')}")
    lines.append("")
    return "\n".join(lines)


def write_improvement_brief(output_dir: Path, brief: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{brief['id']}.json"
    markdown_path = output_dir / f"{brief['id']}.md"
    write_json_atomic(json_path, brief)
    write_text_atomic(markdown_path, render_improvement_brief(brief))
    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
