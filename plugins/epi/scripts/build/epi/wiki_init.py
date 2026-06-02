from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from epi.epi_repository import ensure_epi_repository
from epi.wiki_contracts import formal_page_family_names, formal_page_family_paths


FORMAL_PAGE_DIRS = formal_page_family_names()
FORMAL_PAGE_PATHS = formal_page_family_paths()
KNOWLEDGE_GRAPH_DIRS = [*FORMAL_PAGE_DIRS, "entities", "projects", "skills", "journal"]
GRAPH_SEARCH = "path:/^index\\.md$/ OR " + " OR ".join(
    f"path:/^{directory}\\\\//" for directory in KNOWLEDGE_GRAPH_DIRS
)


def _formal_page_taxonomy_lines() -> str:
    roles = {
        "references/": "evidence-grounded single-paper claim/support/evidence pages",
        "concepts/": "reusable method, theory, and terminology pages",
        "derivations/": "formula derivation and theory reconstruction pages",
        "experiments/": "implementation, baseline, metric, cost, and implementability pages",
        "synthesis/": "cross-paper method comparison and contradiction pages",
        "reports/": "low-burden reading entrypoints",
        "opportunities/": "research gap, novelty, and project opportunity pages",
    }
    return "\n".join(f"- `{path}`: {roles[path]}" for path in FORMAL_PAGE_PATHS)


def _formal_page_directory_lines() -> str:
    return "\n".join(
        f"- `{path}`: final wiki page family written by the wiki skill, not by EPI"
        for path in FORMAL_PAGE_PATHS
    )


AGENTS_MD = """# EPI Paper Research Wiki

## Source-first paper ingest

This vault is for source-first academic paper ingest. Final wiki pages are agent-mediated and must be grounded in the source paper artifacts, not reader summaries alone.

EPI writes only the internal `_epi/` repository. Formal graph pages are written by the wiki skill after batch deposition. Obsidian graph views should ignore `_epi/`; `_epi/raw/papers/<slug>/mineru/<slug>.md` remains source material for final writing, not a formal wiki page.

Required reading before final wiki writing:

- `AGENTS.md`
- `_meta/agent-operating-contract.md`
- `_meta/schema.md`
- `_meta/taxonomy.md`
- `_meta/directory-structure.md`
- `_epi/README.md`
- `_epi/staging/papers/<slug>/wiki-ingest-brief.json`
- `mineru/<slug>.md`
- `mineru/paper.tex`
- `mineru/images/*`
- `mineru/mineru-manifest.json`
"""


AGENT_OPERATING_CONTRACT_MD = """# Agent Operating Contract

- Keep Markdown vault files as the source of truth.
- Treat `reader/` and critic outputs as navigation and quality signals, not substitutes for the source paper.
- Review `mineru/<slug>.md`, `mineru/paper.tex`, `mineru/images/*`, and `mineru/mineru-manifest.json` before final wiki writing.
- Preserve central formulas, figures, tables, and image evidence when distilling claims.
- Search existing pages before creating new ones.
"""


SCHEMA_MD = """# Vault Schema

Source-first paper ingest schema:

1. raw paper and MinerU artifacts
2. reader and critic evidence
3. internal staging handoff for wiki skill batch deposition
4. agent-mediated final wiki pages written outside EPI internals

Final wiki content must preserve claims, formulas, figures/tables/images, and image evidence.
"""


TAXONOMY_MD = """# Vault Taxonomy

""" + _formal_page_taxonomy_lines() + """

EPI must not create formal pages in these roots. The wiki skill creates or updates them after reading a batch of source papers. Do not invent new top-level wiki routes without vault approval.
"""


DIRECTORY_STRUCTURE_MD = """# Directory Structure

The paper research vault keeps paper acquisition, staging, and final wiki outputs separate.

- `_epi/`: internal EPI repository with its own navigation, manifest, policy, and lifecycle management
- `_epi/raw/papers/<slug>/`: downloaded source paper artifacts
- `_epi/staging/papers/<slug>/`: per-paper evidence handoff
- `_epi/staging/wiki-batches/<batch-id>/`: multi-paper handoff for wiki skill deposition
- `_epi/runs/`: transient run reports and dashboards, auto-cleaned by repository policy
""" + _formal_page_directory_lines() + """
"""


GRAPH_JSON = json.dumps(
    {
        "collapse-filter": True,
        "search": GRAPH_SEARCH,
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "showOrphans": True,
    },
    ensure_ascii=False,
    indent=2,
) + "\n"


GRAPH_VISIBILITY_MD = """# Graph Visibility Policy

This vault treats the main Obsidian graph as a knowledge-layer view, not a workflow dump.

## Show in the main graph

- `index.md`
""" + "\n".join(f"- `{path}`" for path in [*FORMAL_PAGE_PATHS, "entities/", "projects/", "skills/", "journal/"]) + """

These are the durable, human-readable knowledge nodes. Source paper Markdown under `_epi/raw` is source material for final writing, not a formal graph page.

## Hide from the main graph

- `_epi/`
- `_meta/`
- `.obsidian/`
- `.git/`
- `AGENTS.md`
- `log.md`
- `hot.md`

EPI reader outputs, critic reports, staging briefs, run dashboards, and raw paper artifacts stay under `_epi/` and should not pollute the main knowledge graph.

## Why

- Keep transient acquisition, execution, and audit files out of the graph.
- Keep raw source papers available for source-first ingest without presenting them as finished wiki pages.
- Make the graph reflect stable research knowledge instead of pipeline state.
"""


REQUIRED_DIRS = [
    "_meta",
    *FORMAL_PAGE_DIRS,
    "entities",
    "skills",
    "projects",
    "journal",
    ".obsidian",
]


def _manifest_payload(existing: dict | None = None) -> dict:
    existing = existing if isinstance(existing, dict) else {}
    payload = dict(existing)
    payload.update(
        {
            "vault_type": existing.get("vault_type") or "academic-paper-research",
            "schema": "raw source -> evidence handoff -> agent-mediated wiki -> vault schema",
            "wiki_write_model": "agent-mediated-vault-contract",
            "source_first_wiki_ingest": True,
            "git_repository_required": True,
            "git_auto_init": True,
            "git_initial_commit": False,
            "must_read_source_artifacts": [
                "mineru/<slug>.md",
                "mineru/paper.tex",
                "mineru/images/*",
                "mineru/mineru-manifest.json",
            ],
            "handoff_artifacts": [
                "wiki-ingest-brief.json",
                "_epi/staging/wiki-batches/pending/wiki-batch-ingest-brief.json",
                "promotion-plan.json",
                "reader/evidence-map.json",
            ],
            "epi_internal_root": "_epi",
            "epi_write_scope": "internal-_epi-repository-only",
            "formal_pages_written_by": "wiki-skill-batch-distillation",
            "graph_ignore_internal_dirs": True,
            "raw_paper_markdown_role": "source-material-not-formal-page",
            "wiki_dirs": [*FORMAL_PAGE_DIRS, "entities", "skills", "projects", "journal"],
            "operational_dirs": ["_epi"],
            "papers": existing.get("papers", []),
        }
    )
    return payload


def _write_text_if_missing_or_legacy(path: Path, content: str, created: list[str], relative_file: str, *, current_marker: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")
        created.append(relative_file)
        return
    existing = path.read_text(encoding="utf-8")
    legacy_markers = ("_raw", "_staging", "_runs", "_quarantine", "_evolution", "mineru/<paper-title-or-short-title>.md")
    if current_marker not in existing and any(marker in existing for marker in legacy_markers):
        path.write_text(content, encoding="utf-8")
        created.append(relative_file)


def _sync_manifest(path: Path, created: list[str]) -> None:
    existing: dict | None = None
    if path.exists():
        try:
            existing_payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing_payload, dict):
                existing = existing_payload
        except json.JSONDecodeError:
            existing = None
    payload = _manifest_payload(existing)
    if not path.exists() or payload != existing:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(".manifest.json")


def _sync_graph_json(path: Path, created: list[str]) -> None:
    payload: dict
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            payload = existing if isinstance(existing, dict) else {}
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}
    previous_search = str(payload.get("search") or "")
    payload["collapse-filter"] = True
    payload["search"] = GRAPH_SEARCH
    if not path.exists() or previous_search != GRAPH_SEARCH:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(".obsidian/graph.json")


def initialize_paper_wiki(vault_path: Path) -> list[str]:
    vault_path = vault_path.resolve()
    created: list[str] = []
    git_dir = vault_path / ".git"
    if not git_dir.exists():
        subprocess.run(["git", "init", str(vault_path)], check=True, capture_output=True, text=True)
        created.append(".git")
    for relative_dir in REQUIRED_DIRS:
        path = vault_path / relative_dir
        if not path.exists():
            created.append(relative_dir)
        path.mkdir(parents=True, exist_ok=True)
    created.extend(ensure_epi_repository(vault_path))

    contract_files = {
        "AGENTS.md": (AGENTS_MD, "EPI writes only the internal `_epi/` repository"),
        "_meta/agent-operating-contract.md": (AGENT_OPERATING_CONTRACT_MD, "Review `mineru/<slug>.md`, `mineru/paper.tex`"),
        "_meta/schema.md": (SCHEMA_MD, "internal staging handoff for wiki skill batch deposition"),
        "_meta/taxonomy.md": (TAXONOMY_MD, "EPI must not create formal pages"),
        "_meta/directory-structure.md": (DIRECTORY_STRUCTURE_MD, "_epi/raw/papers/<slug>/"),
        "_meta/graph-visibility.md": (GRAPH_VISIBILITY_MD, "Source paper Markdown under `_epi/raw`"),
    }
    for relative_file, (content, marker) in contract_files.items():
        _write_text_if_missing_or_legacy(vault_path / relative_file, content, created, relative_file, current_marker=marker)

    files = {
        "index.md": "# Paper Research Wiki\n\nThis vault is dedicated to profile-driven academic paper research.\n",
        "log.md": "# Log\n\n## Initialized\n\n- Created dedicated paper research wiki structure.\n",
        "hot.md": "# Hot\n\nNo promoted papers yet.\n",
    }
    for relative_file, content in files.items():
        path = vault_path / relative_file
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(relative_file)
    _sync_manifest(vault_path / ".manifest.json", created)
    _sync_graph_json(vault_path / ".obsidian" / "graph.json", created)
    return created


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Initialize a dedicated academic paper research wiki.")
    parser.add_argument("--vault", type=Path, default=Path(os.environ.get("EPI_VAULT", Path.cwd() / "paper-research-wiki")))
    args = parser.parse_args()
    created = initialize_paper_wiki(args.vault)
    print(f"initialized={args.vault.resolve()}")
    print(f"created_count={len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
