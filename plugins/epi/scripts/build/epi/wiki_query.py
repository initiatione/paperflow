from __future__ import annotations

import json
from pathlib import Path


ROLE_LABELS = {
    "nature-sci-editor": "editor",
    "peer-reviewer": "reviewer",
    "senior-domain-researcher": "domain",
}


def _manifest_path(vault_path: Path) -> Path:
    return Path(vault_path).resolve() / ".manifest.json"


def _load_manifest(vault_path: Path) -> dict:
    path = _manifest_path(vault_path)
    if not path.exists():
        return {"vault_type": "academic-paper-research", "papers": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"vault_type": "academic-paper-research", "papers": []}
    if not isinstance(payload, dict):
        return {"vault_type": "academic-paper-research", "papers": []}
    payload.setdefault("papers", [])
    return payload


def _decision(paper: dict) -> dict:
    decision = paper.get("research_decision")
    return decision if isinstance(decision, dict) else {}


def _role_verdicts(paper: dict) -> dict:
    verdicts = _decision(paper).get("role_verdicts")
    return verdicts if isinstance(verdicts, dict) else {}


def _matches(
    paper: dict,
    *,
    consensus: str | None,
    role: str | None,
    verdict: str | None,
    warning_reviewer: str | None,
    blocking_lens: str | None,
) -> bool:
    decision = _decision(paper)
    if paper.get("promotion_status") != "promoted":
        return False
    if consensus and decision.get("panel_consensus") != consensus:
        return False
    if role and verdict and _role_verdicts(paper).get(role) != verdict:
        return False
    if warning_reviewer and warning_reviewer not in (decision.get("warning_reviewers") or []):
        return False
    if blocking_lens and blocking_lens not in (decision.get("blocking_lenses") or []):
        return False
    return True


def _normalize_paper(paper: dict) -> dict:
    decision = _decision(paper)
    return {
        "slug": paper.get("slug"),
        "title": paper.get("title") or paper.get("slug"),
        "compiled_reference": paper.get("compiled_reference"),
        "decision": decision,
        "role_verdicts": _role_verdicts(paper),
        "role_assessments": paper.get("role_assessments") or [],
    }


def query_wiki(
    vault_path: Path,
    *,
    consensus: str | None = None,
    role: str | None = None,
    verdict: str | None = None,
    warning_reviewer: str | None = None,
    blocking_lens: str | None = None,
    limit: int = 20,
) -> dict:
    manifest = _load_manifest(vault_path)
    promoted = [
        paper
        for paper in manifest.get("papers", [])
        if isinstance(paper, dict) and paper.get("promotion_status") == "promoted"
    ]
    matches = [
        _normalize_paper(paper)
        for paper in promoted
        if _matches(
            paper,
            consensus=consensus,
            role=role,
            verdict=verdict,
            warning_reviewer=warning_reviewer,
            blocking_lens=blocking_lens,
        )
    ][:limit]
    return {
        "title": "EPI Wiki Query",
        "filters": {
            "consensus": consensus,
            "role": role,
            "verdict": verdict,
            "warning_reviewer": warning_reviewer,
            "blocking_lens": blocking_lens,
            "limit": limit,
        },
        "summary": {
            "matched_count": len(matches),
            "total_promoted_count": len(promoted),
        },
        "papers": matches,
    }


def _roles_line(role_verdicts: dict) -> str:
    parts = [
        f"{label}={role_verdicts.get(role, '-')}"
        for role, label in ROLE_LABELS.items()
    ]
    return "roles: " + ", ".join(parts)


def render_wiki_query(result: dict) -> str:
    lines = [
        result.get("title", "EPI Wiki Query"),
        "",
        f"matched: {result.get('summary', {}).get('matched_count', 0)} / promoted: {result.get('summary', {}).get('total_promoted_count', 0)}",
        "",
    ]
    papers = result.get("papers") or []
    if not papers:
        lines.extend(["No matching promoted papers.", ""])
        return "\n".join(lines)
    for paper in papers:
        decision = paper.get("decision") or {}
        lines.append(f"- {paper.get('slug')} | {paper.get('title')}")
        if paper.get("compiled_reference"):
            lines.append(f"  reference: {paper['compiled_reference']}")
        lines.append(f"  decision: {decision.get('panel_consensus') or decision.get('recommendation') or '-'}")
        lines.append(f"  {_roles_line(paper.get('role_verdicts') or {})}")
        if decision.get("blocking_lenses"):
            lines.append("  blocking: " + ", ".join(str(item) for item in decision["blocking_lenses"]))
        if decision.get("warning_reviewers"):
            lines.append("  warnings: " + ", ".join(str(item) for item in decision["warning_reviewers"]))
    lines.append("")
    return "\n".join(lines)
