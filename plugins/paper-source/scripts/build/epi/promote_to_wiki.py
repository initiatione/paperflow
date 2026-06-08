from __future__ import annotations

import json
import shutil
from pathlib import Path
from pathlib import PurePosixPath

from epi.artifacts import raw_paper_root, staging_paper_root, utc_now, write_json_atomic, write_text_atomic
from epi.run_critic import HARD_RULE
from epi.wiki_contracts import formal_page_family_names, formal_page_family_paths


_ALLOWED_COMPILED_TARGET_ROOTS = set(formal_page_family_names())


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _paper_root(vault_path: Path, slug: str) -> Path:
    return raw_paper_root(vault_path, slug)


def _staging_root(vault_path: Path, slug: str) -> Path:
    return staging_paper_root(vault_path, slug)


def _manifest_path(vault_path: Path) -> Path:
    return vault_path.resolve() / ".manifest.json"


def _log_path(vault_path: Path) -> Path:
    return vault_path.resolve() / "log.md"


def _index_path(vault_path: Path) -> Path:
    return vault_path.resolve() / "index.md"


def _hot_path(vault_path: Path) -> Path:
    return vault_path.resolve() / "hot.md"


def _compiled_target_path(vault_path: Path, target: str) -> Path:
    normalized = str(target or "").replace("\\", "/").strip()
    target_path = PurePosixPath(normalized)
    if (
        not normalized
        or Path(str(target)).is_absolute()
        or target_path.is_absolute()
        or ".." in target_path.parts
        or not target_path.parts
        or target_path.parts[0] not in _ALLOWED_COMPILED_TARGET_ROOTS
    ):
        raise ValueError(
            "compiled target must be a relative path under " + ", ".join(formal_page_family_paths())
        )
    compiled_path = (vault_path.resolve() / Path(*target_path.parts)).resolve()
    try:
        compiled_path.relative_to(vault_path.resolve())
    except ValueError as exc:
        raise ValueError("compiled target must stay inside the vault") from exc
    return compiled_path


def _promotion_record_compiled_path(vault_path: Path, raw_path: str) -> Path:
    vault_path = vault_path.resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = vault_path / candidate
    compiled_path = candidate.resolve()
    try:
        relative_path = compiled_path.relative_to(vault_path)
    except ValueError as exc:
        raise ValueError("promotion record compiled path must stay inside the vault") from exc
    if not relative_path.parts or relative_path.parts[0] not in _ALLOWED_COMPILED_TARGET_ROOTS:
        raise ValueError("promotion record compiled path must be under an allowed wiki page root")
    return compiled_path


def _promotion_record_snapshot_path(paper_root: Path, raw_path: str) -> Path:
    backup_root = (paper_root / "promotion-backups").resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = paper_root / candidate
    snapshot_path = candidate.resolve()
    try:
        snapshot_path.relative_to(backup_root)
    except ValueError as exc:
        raise ValueError("promotion record snapshot path must stay under paper promotion-backups") from exc
    return snapshot_path


def _backup_path_for_target(
    backup_dir: Path,
    vault_path: Path,
    compiled_path: Path,
    backup_stamp: str,
) -> Path:
    relative_name = "__".join(compiled_path.relative_to(vault_path).parts)
    return backup_dir / f"{relative_name}.{backup_stamp}.bak"


def _page_transactions(vault_path: Path, staging_root: Path, slug: str) -> list[dict]:
    plan = _read_json(staging_root / "promotion-plan.json")
    staged_paths = [Path(plan.get("staged_reference") or (staging_root / "references" / f"{slug}.md"))]
    staged_paths.extend(Path(path) for path in plan.get("staged_concepts", []))
    staged_paths.extend(Path(path) for path in plan.get("staged_synthesis", []))
    staged_paths.extend(Path(path) for path in plan.get("staged_reports", []))
    staged_paths.extend(Path(path) for path in plan.get("staged_reproduction", []))
    compiled_targets = plan.get("compiled_targets")
    if not isinstance(compiled_targets, list) or not compiled_targets:
        if (
            plan.get("handoff_type") == "agent-mediated-wiki-ingest"
            or plan.get("wiki_write_model") == "agent-mediated-vault-contract"
        ):
            raise ValueError(
                "agent-mediated wiki ingest plans do not provide compiled_targets; "
                "run the wiki ingest agent from wiki-ingest-brief.json"
            )
        raise ValueError("promotion-plan compiled_targets must be present and non-empty")
    if len(staged_paths) != len(compiled_targets):
        raise ValueError("promotion-plan staged paths and compiled_targets are out of sync")
    return [
        {
            "staged_path": str(staged_path),
            "compiled_path": str(_compiled_target_path(vault_path, compiled_target)),
        }
        for staged_path, compiled_target in zip(staged_paths, compiled_targets)
    ]


def _load_promotion_plan(staging_root: Path) -> dict:
    return _read_json(staging_root / "promotion-plan.json")


def _load_research_decision_summary(paper_root: Path, staging_root: Path) -> tuple[dict | None, list[dict]]:
    plan = _load_promotion_plan(staging_root)
    if plan.get("panel_summary") or plan.get("role_verdicts"):
        panel = plan.get("panel_summary") or {}
        return (
            {
                "recommendation": plan.get("recommendation"),
                "next_action": plan.get("next_action"),
                "panel_consensus": panel.get("consensus"),
                "blocking_lenses": panel.get("blocking_lenses") or [],
                "warning_reviewers": panel.get("warning_reviewers") or [],
                "role_verdicts": plan.get("role_verdicts") or {},
            },
            list(plan.get("role_assessments") or []),
        )

    critic_report = _read_json(paper_root / "critic" / "critic-report.json")
    decision = critic_report.get("research_decision") if isinstance(critic_report.get("research_decision"), dict) else {}
    decision_path = critic_report.get("research_decision_path")
    if not decision and decision_path and Path(decision_path).exists():
        decision = _read_json(Path(decision_path))
    if not decision:
        fallback_path = paper_root / "critic" / "research-decision.json"
        if fallback_path.exists():
            decision = _read_json(fallback_path)
    if not decision:
        return None, []

    panel = decision.get("panel_summary") or {}
    return (
        {
            "recommendation": decision.get("recommendation"),
            "next_action": decision.get("next_action"),
            "panel_consensus": panel.get("consensus"),
            "blocking_lenses": panel.get("blocking_lenses") or [],
            "warning_reviewers": panel.get("warning_reviewers") or [],
            "role_verdicts": decision.get("role_verdicts") or {},
        },
        list(decision.get("role_assessments") or []),
    )


def _role_verdict_key(lens: str) -> str:
    return "epi_" + lens.replace("-", "_") + "_verdict"


def _frontmatter_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _research_decision_frontmatter_lines(summary: dict) -> list[str]:
    lines = [
        f"epi_recommendation: {_frontmatter_value(summary.get('recommendation', ''))}",
        f"epi_next_action: {_frontmatter_value(summary.get('next_action', ''))}",
        f"epi_panel_consensus: {_frontmatter_value(summary.get('panel_consensus', ''))}",
        f"epi_blocking_lenses: {_frontmatter_value(summary.get('blocking_lenses') or [])}",
        f"epi_warning_reviewers: {_frontmatter_value(summary.get('warning_reviewers') or [])}",
    ]
    for lens, verdict in (summary.get("role_verdicts") or {}).items():
        lines.append(f"{_role_verdict_key(str(lens))}: {_frontmatter_value(verdict)}")
    return lines


def _ensure_reference_frontmatter(path: Path, summary: dict | None) -> None:
    if summary is None or not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "epi_panel_consensus:" in text:
        return
    lines = text.splitlines()
    frontmatter_lines = _research_decision_frontmatter_lines(summary)
    if lines and lines[0] == "---":
        try:
            closing_index = lines.index("---", 1)
        except ValueError:
            closing_index = -1
        if closing_index > 0:
            updated = lines[:closing_index] + frontmatter_lines + lines[closing_index:]
            write_text_atomic(path, "\n".join(updated) + ("\n" if text.endswith("\n") else ""))
            return
    write_text_atomic(path, "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n" + text)


def _load_manifest(vault_path: Path) -> dict:
    path = _manifest_path(vault_path)
    if path.exists():
        manifest = _read_json(path)
    else:
        manifest = {"vault_type": "academic-paper-research", "papers": []}
    manifest.setdefault("papers", [])
    return manifest


def _upsert_paper(manifest: dict, entry: dict) -> None:
    papers = manifest.setdefault("papers", [])
    for index, paper in enumerate(papers):
        if paper.get("slug") == entry["slug"]:
            papers[index] = {**paper, **entry}
            return
    papers.append(entry)


def _append_log(vault_path: Path, line: str) -> None:
    log_path = _log_path(vault_path)
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Log\n"
    if not existing.endswith("\n"):
        existing += "\n"
    write_text_atomic(log_path, existing + line + "\n")


def _replace_managed_section(existing: str, start_marker: str, end_marker: str, body: str) -> str:
    if not existing.endswith("\n"):
        existing += "\n"
    section = f"{start_marker}\n{body.rstrip()}\n{end_marker}\n"
    start_index = existing.find(start_marker)
    end_index = existing.find(end_marker)
    if start_index != -1 and end_index != -1 and end_index > start_index:
        end_index += len(end_marker)
        return existing[:start_index] + section.rstrip("\n") + existing[end_index:]
    return existing + "\n" + section


def _paper_link(paper: dict) -> str:
    slug = paper["slug"]
    title = paper.get("title") or slug
    return f"[[references/{slug}|{title}]]"


def _decision_summary_suffix(paper: dict) -> str:
    decision = paper.get("research_decision")
    if not isinstance(decision, dict):
        return ""
    role_verdicts = decision.get("role_verdicts") or {}
    role_summary = ", ".join(
        [
            f"editor={role_verdicts.get('nature-sci-editor', '-')}",
            f"reviewer={role_verdicts.get('peer-reviewer', '-')}",
            f"domain={role_verdicts.get('senior-domain-researcher', '-')}",
        ]
    )
    parts = [
        f"decision: {decision.get('panel_consensus') or decision.get('recommendation') or '-'}",
        f"roles: {role_summary}",
    ]
    blocking_lenses = decision.get("blocking_lenses") or []
    warning_reviewers = decision.get("warning_reviewers") or []
    if blocking_lenses:
        parts.append("blocking: " + ", ".join(str(item) for item in blocking_lenses))
    if warning_reviewers:
        parts.append("warnings: " + ", ".join(str(item) for item in warning_reviewers))
    return " - " + "; ".join(parts)


def _render_index_section(manifest: dict) -> str:
    papers = [
        paper
        for paper in manifest.get("papers", [])
        if paper.get("promotion_status") == "promoted" and paper.get("slug")
    ]
    if not papers:
        return "## Promoted Papers\n\nNo promoted papers yet."
    lines = ["## Promoted Papers", ""]
    for paper in sorted(papers, key=lambda item: (item.get("title") or item["slug"]).lower()):
        suffix = f" (DOI: {paper['doi']})" if paper.get("doi") else ""
        lines.append(f"- {_paper_link(paper)}{suffix}{_decision_summary_suffix(paper)}")
    return "\n".join(lines)


def _render_hot_section(manifest: dict) -> str:
    papers = [
        paper
        for paper in manifest.get("papers", [])
        if paper.get("promotion_status") == "promoted" and paper.get("slug")
    ]
    if not papers:
        return "## Hot Papers\n\nNo promoted papers yet."
    lines = ["## Hot Papers", ""]
    for paper in sorted(papers, key=lambda item: item.get("promoted_at") or "", reverse=True)[:10]:
        promoted_at = f" - promoted at {paper['promoted_at']}" if paper.get("promoted_at") else ""
        lines.append(f"- {_paper_link(paper)}{promoted_at}{_decision_summary_suffix(paper)}")
    return "\n".join(lines)


def _refresh_index_and_hot(vault_path: Path, manifest: dict) -> None:
    index_path = _index_path(vault_path)
    hot_path = _hot_path(vault_path)
    index_existing = (
        index_path.read_text(encoding="utf-8")
        if index_path.exists()
        else "# Paper Research Wiki\n\nThis vault is dedicated to profile-driven academic paper research.\n"
    )
    hot_existing = hot_path.read_text(encoding="utf-8") if hot_path.exists() else "# Hot\n\nNo promoted papers yet.\n"
    write_text_atomic(
        index_path,
        _replace_managed_section(
            index_existing,
            "<!-- EPI:PROMOTED-PAPERS:START -->",
            "<!-- EPI:PROMOTED-PAPERS:END -->",
            _render_index_section(manifest),
        ),
    )
    write_text_atomic(
        hot_path,
        _replace_managed_section(
            hot_existing,
            "<!-- EPI:HOT-PAPERS:START -->",
            "<!-- EPI:HOT-PAPERS:END -->",
            _render_hot_section(manifest),
        ),
    )


def _snapshot_state_file(source_path: Path, backup_dir: Path, backup_name: str, default_text: str) -> str:
    backup_path = backup_dir / backup_name
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.exists():
        shutil.copyfile(source_path, backup_path)
    else:
        backup_path.write_text(default_text, encoding="utf-8")
    return str(backup_path)


def promote_paper(vault_path: Path, slug: str, approved_by: str | None = None) -> dict:
    vault_path = vault_path.resolve()
    paper_root = _paper_root(vault_path, slug)
    staging_root = _staging_root(vault_path, slug)
    critic_report = _read_json(paper_root / "critic" / "critic-report.json")
    outcome = critic_report.get("outcome")
    if outcome != "pass":
        raise ValueError(f"critic outcome must be pass before promotion, got {outcome}")
    if critic_report.get("hard_rule") != HARD_RULE:
        raise ValueError("critic report does not preserve the hard gate invariant")
    if not approved_by:
        raise ValueError("human gate approval required before promotion")
    raise ValueError(
        "promote-to-wiki is deprecated: EPI may only write internal underscore artifacts. "
        "Use wiki-ingest-handoff, record-human-approval, wiki-ingest-trigger, then the wiki-ingest skill "
        "for batch deposition and record-wiki-ingest."
    )

    page_transactions = _page_transactions(vault_path, staging_root, slug)
    staged_reference = Path(page_transactions[0]["staged_path"])
    if not staged_reference.exists():
        raise FileNotFoundError(f"missing staged reference draft: {staged_reference}")

    compiled_reference = Path(page_transactions[0]["compiled_path"])
    backup_dir = paper_root / "promotion-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_stamp = utc_now().replace(":", "").replace("+", "Z")
    state_backup_dir = backup_dir / "state" / backup_stamp
    previous_state_snapshot_paths = {
        "manifest": _snapshot_state_file(
            _manifest_path(vault_path),
            state_backup_dir,
            "manifest.json",
            json.dumps({"vault_type": "academic-paper-research", "papers": []}, indent=2) + "\n",
        ),
        "log": _snapshot_state_file(_log_path(vault_path), state_backup_dir, "log.md", "# Log\n"),
        "index": _snapshot_state_file(
            _index_path(vault_path),
            state_backup_dir,
            "index.md",
            "# Paper Research Wiki\n\nThis vault is dedicated to profile-driven academic paper research.\n",
        ),
        "hot": _snapshot_state_file(
            _hot_path(vault_path),
            state_backup_dir,
            "hot.md",
            "# Hot\n\nNo promoted papers yet.\n",
        ),
    }
    backup_paths: list[str] = []
    for page in page_transactions:
        staged_path = Path(page["staged_path"])
        compiled_path = Path(page["compiled_path"])
        if not staged_path.exists():
            raise FileNotFoundError(f"missing staged draft: {staged_path}")
        previous_snapshot_path = None
        if compiled_path.exists():
            backup_path = _backup_path_for_target(backup_dir, vault_path, compiled_path, backup_stamp)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(compiled_path, backup_path)
            previous_snapshot_path = str(backup_path)
            backup_paths.append(previous_snapshot_path)
        page["previous_snapshot_path"] = previous_snapshot_path

    for page in page_transactions:
        compiled_path = Path(page["compiled_path"])
        compiled_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(page["staged_path"], compiled_path)

    metadata = _read_json(paper_root / "metadata.json")
    manifest = _load_manifest(vault_path)
    promoted_at = utc_now()
    research_decision_summary, role_assessments = _load_research_decision_summary(paper_root, staging_root)
    _ensure_reference_frontmatter(compiled_reference, research_decision_summary)
    human_gate_decision = {
        "status": "approved",
        "approved_by": approved_by,
        "approved_at": promoted_at,
    }
    manifest_entry = {
        "slug": slug,
        "title": metadata.get("title", ""),
        "doi": metadata.get("doi"),
        "promotion_status": "promoted",
        "promoted_at": promoted_at,
        "compiled_reference": str(compiled_reference),
        "critic_report": str(paper_root / "critic" / "critic-report.json"),
    }
    if research_decision_summary is not None:
        manifest_entry["research_decision"] = research_decision_summary
        manifest_entry["role_assessments"] = role_assessments
    _upsert_paper(
        manifest,
        manifest_entry,
    )
    write_json_atomic(_manifest_path(vault_path), manifest)
    _refresh_index_and_hot(vault_path, manifest)
    _append_log(vault_path, f"- Promoted {slug} at {promoted_at}.")
    manifest_update_summary = {
        "paper_slug": slug,
        "manifest_path": str(_manifest_path(vault_path)),
        "log_path": str(_log_path(vault_path)),
        "index_path": str(_index_path(vault_path)),
        "hot_path": str(_hot_path(vault_path)),
        "operation": "upsert-promoted-paper-refresh-index-hot-and-append-log",
    }

    record = {
        "stage": "promote-to-wiki",
        "status": "promoted",
        "paper_slug": slug,
        "promoted_at": promoted_at,
        "critic_outcome": outcome,
        "staged_draft_paths": [page["staged_path"] for page in page_transactions],
        "promoted_page_paths": [page["compiled_path"] for page in page_transactions],
        "previous_page_snapshot_paths": backup_paths,
        "page_transactions": page_transactions,
        "previous_state_snapshot_paths": previous_state_snapshot_paths,
        "manifest_update_summary": manifest_update_summary,
        "backup_paths": backup_paths,
        "hard_rule": HARD_RULE,
        "human_gate_decision": human_gate_decision,
    }
    if research_decision_summary is not None:
        record["research_decision"] = research_decision_summary
        record["role_assessments"] = role_assessments
    write_json_atomic(paper_root / "promotion-record.json", record)
    return record


def rollback_promotion(vault_path: Path, slug: str) -> dict:
    vault_path = vault_path.resolve()
    paper_root = _paper_root(vault_path, slug)
    record = _read_json(paper_root / "promotion-record.json")
    page_transactions = record.get("page_transactions") or []
    if not page_transactions:
        compiled_paths = [Path(path) for path in record.get("promoted_page_paths", [])]
        backup_paths = [Path(path) for path in record.get("previous_page_snapshot_paths", [])]
        page_transactions = []
        for index, compiled_path in enumerate(compiled_paths):
            snapshot_path = str(backup_paths[index]) if index < len(backup_paths) else None
            page_transactions.append(
                {
                    "compiled_path": str(compiled_path),
                    "previous_snapshot_path": snapshot_path,
                }
            )
    state_snapshot_paths = record.get("previous_state_snapshot_paths", {})
    restored_paths: list[str] = []
    removed_paths: list[str] = []
    restored_state_paths: dict[str, str] = {}

    for page in page_transactions:
        compiled_path = _promotion_record_compiled_path(vault_path, page["compiled_path"])
        snapshot_path = page.get("previous_snapshot_path")
        if snapshot_path:
            backup_path = _promotion_record_snapshot_path(paper_root, snapshot_path)
            compiled_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(backup_path, compiled_path)
            restored_paths.append(str(compiled_path))
        elif compiled_path.exists():
            compiled_path.unlink()
            removed_paths.append(str(compiled_path))

    rolled_back_at = utc_now()
    manifest_snapshot = state_snapshot_paths.get("manifest")
    if manifest_snapshot:
        shutil.copyfile(_promotion_record_snapshot_path(paper_root, manifest_snapshot), _manifest_path(vault_path))
        restored_state_paths["manifest"] = str(_manifest_path(vault_path))
    else:
        manifest = _load_manifest(vault_path)
        _upsert_paper(
            manifest,
            {
                "slug": slug,
                "promotion_status": "rolled_back",
                "rolled_back_at": rolled_back_at,
            },
        )
        write_json_atomic(_manifest_path(vault_path), manifest)
        restored_state_paths["manifest"] = str(_manifest_path(vault_path))
    log_snapshot = state_snapshot_paths.get("log")
    if log_snapshot:
        shutil.copyfile(_promotion_record_snapshot_path(paper_root, log_snapshot), _log_path(vault_path))
        restored_state_paths["log"] = str(_log_path(vault_path))
    index_snapshot = state_snapshot_paths.get("index")
    if index_snapshot:
        shutil.copyfile(_promotion_record_snapshot_path(paper_root, index_snapshot), _index_path(vault_path))
        restored_state_paths["index"] = str(_index_path(vault_path))
    hot_snapshot = state_snapshot_paths.get("hot")
    if hot_snapshot:
        shutil.copyfile(_promotion_record_snapshot_path(paper_root, hot_snapshot), _hot_path(vault_path))
        restored_state_paths["hot"] = str(_hot_path(vault_path))
    _append_log(vault_path, f"- Rolled back {slug} at {rolled_back_at}.")

    rollback_record = {
        "stage": "rollback",
        "status": "rolled_back",
        "paper_slug": slug,
        "rolled_back_at": rolled_back_at,
        "restored_paths": restored_paths,
        "removed_paths": removed_paths,
        "restored_state_paths": restored_state_paths,
    }
    write_json_atomic(paper_root / "rollback-record.json", rollback_record)
    return rollback_record
