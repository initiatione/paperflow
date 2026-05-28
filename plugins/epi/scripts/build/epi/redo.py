from __future__ import annotations

import json
from pathlib import Path

from epi.acquire_papers import acquire_paper
from epi.artifacts import raw_paper_root, utc_now
from epi.generate_reader import generate_reader_outputs
from epi.run_critic import run_critics
from epi.run_mineru_parse import materialize_mineru_fixture


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_redo_event(paper_root: Path, event: dict) -> dict:
    event = {
        "recorded_at": utc_now(),
        **event,
    }
    records_path = paper_root / "redo-records.jsonl"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    with records_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def _paper_root(vault_path: Path, slug: str) -> Path:
    paper_root = raw_paper_root(vault_path, slug)
    if not paper_root.exists():
        raise FileNotFoundError(f"missing raw paper root: {paper_root}")
    return paper_root


def redo_acquire(vault_path: Path, slug: str, pdf_path: Path, reason: str | None = None) -> dict:
    paper_root = _paper_root(vault_path, slug)
    metadata = _read_json(paper_root / "metadata.json")
    metadata.setdefault("slug", slug)
    acquire_record = acquire_paper(metadata, pdf_path, paper_root, redo=True)
    return _append_redo_event(
        paper_root,
        {
            "stage": "redo-acquire",
            "status": "success",
            "reason": reason or "",
            "output_path": acquire_record["output_path"],
            "size_bytes": acquire_record["size_bytes"],
        },
    )


def redo_parse(
    vault_path: Path,
    slug: str,
    markdown_path: Path,
    tex_path: Path | None = None,
    images_dir: Path | None = None,
    reason: str | None = None,
) -> dict:
    paper_root = _paper_root(vault_path, slug)
    parse_record = materialize_mineru_fixture(
        paper_root,
        markdown_path=markdown_path,
        tex_path=tex_path,
        images_dir=images_dir,
    )
    return _append_redo_event(
        paper_root,
        {
            "stage": "redo-parse",
            "status": "success",
            "reason": reason or "",
            "markdown_path": parse_record["markdown_path"],
            "tex_path": parse_record["tex_path"],
            "image_count": parse_record["image_count"],
        },
    )


def redo_read(vault_path: Path, slug: str, reason: str | None = None) -> dict:
    paper_root = _paper_root(vault_path, slug)
    reader_record = generate_reader_outputs(paper_root)
    return _append_redo_event(
        paper_root,
        {
            "stage": "redo-read",
            "status": "success",
            "reason": reason or "",
            "reader_dir": reader_record["reader_dir"],
            "evidence_count": reader_record["evidence_count"],
        },
    )


def recritic(vault_path: Path, slug: str, reason: str | None = None) -> dict:
    paper_root = _paper_root(vault_path, slug)
    critic_report = run_critics(paper_root)
    return _append_redo_event(
        paper_root,
        {
            "stage": "recritic",
            "status": "success",
            "reason": reason or "",
            "critic_outcome": critic_report["outcome"],
            "critic_report": str(paper_root / "critic" / "critic-report.json"),
        },
    )
