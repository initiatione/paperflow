from __future__ import annotations

import json
import os
from pathlib import Path


AGENTS_MD = """# EPI Paper Research Wiki

## Source-first paper ingest

This vault is for source-first academic paper ingest. Final wiki pages are agent-mediated and must be grounded in the source paper artifacts, not reader summaries alone.

Required reading before final wiki writing:

- `AGENTS.md`
- `_meta/agent-operating-contract.md`
- `_meta/schema.md`
- `_meta/taxonomy.md`
- `_meta/directory-structure.md`
- `_staging/papers/<slug>/wiki-ingest-brief.json`
- `mineru/paper.md`
- `mineru/paper.tex`
- `mineru/images/*`
- `mineru/mineru-manifest.json`
"""


AGENT_OPERATING_CONTRACT_MD = """# Agent Operating Contract

- Keep Markdown vault files as the source of truth.
- Treat `reader/` and critic outputs as navigation and quality signals, not substitutes for the source paper.
- Review `mineru/paper.md`, `mineru/paper.tex`, `mineru/images/*`, and `mineru/mineru-manifest.json` before final wiki writing.
- Preserve central formulas, figures, tables, and image evidence when distilling claims.
- Search existing pages before creating new ones.
"""


SCHEMA_MD = """# Vault Schema

Source-first paper ingest schema:

1. raw paper and MinerU artifacts
2. reader and critic evidence
3. staging drafts and wiki-ingest handoff
4. agent-mediated final wiki pages

Final wiki content must preserve claims, formulas, figures/tables/images, and image evidence.
"""


TAXONOMY_MD = """# Vault Taxonomy

- `references/`: evidence-grounded source pages
- `concepts/`: reusable atomic ideas
- `synthesis/`: cross-paper relationships
- `reports/`: low-burden reading entrypoints

Do not invent new top-level wiki routes without vault approval.
"""


DIRECTORY_STRUCTURE_MD = """# Directory Structure

The paper research vault keeps paper acquisition, staging, and final wiki outputs separate.

- `_raw/papers/<slug>/`: downloaded source paper artifacts
- `_staging/papers/<slug>/`: review drafts and wiki handoff
- `references/`, `concepts/`, `synthesis/`, `reports/`: final wiki page families when approved by the vault contract
"""


REQUIRED_DIRS = [
    "_raw/papers",
    "_staging/papers",
    "_quarantine/papers",
    "_runs",
    "_evolution/proposals",
    "_evolution/pending",
    "_evolution/active",
    "_evolution/archive",
    "_evolution/rejected",
    "_meta",
    "references",
    "concepts",
    "synthesis",
    "entities",
    "skills",
    "projects",
    "journal",
    ".obsidian",
]


def initialize_paper_wiki(vault_path: Path) -> list[str]:
    vault_path = vault_path.resolve()
    created: list[str] = []
    for relative_dir in REQUIRED_DIRS:
        path = vault_path / relative_dir
        if not path.exists():
            created.append(relative_dir)
        path.mkdir(parents=True, exist_ok=True)

    files = {
        "AGENTS.md": AGENTS_MD,
        "_meta/agent-operating-contract.md": AGENT_OPERATING_CONTRACT_MD,
        "_meta/schema.md": SCHEMA_MD,
        "_meta/taxonomy.md": TAXONOMY_MD,
        "_meta/directory-structure.md": DIRECTORY_STRUCTURE_MD,
        "index.md": "# Paper Research Wiki\n\nThis vault is dedicated to profile-driven academic paper research.\n",
        "log.md": "# Log\n\n## Initialized\n\n- Created dedicated paper research wiki structure.\n",
        "hot.md": "# Hot\n\nNo promoted papers yet.\n",
        ".manifest.json": json.dumps(
            {
                "vault_type": "academic-paper-research",
                "schema": "raw source -> evidence handoff -> agent-mediated wiki -> vault schema",
                "wiki_write_model": "agent-mediated-vault-contract",
                "source_first_wiki_ingest": True,
                "must_read_source_artifacts": [
                    "mineru/paper.md",
                    "mineru/paper.tex",
                    "mineru/images/*",
                    "mineru/mineru-manifest.json",
                ],
                "handoff_artifacts": [
                    "wiki-ingest-brief.json",
                    "promotion-plan.json",
                    "reader/evidence-map.json",
                ],
                "suggested_draft_dirs": ["references", "concepts", "synthesis", "reports"],
                "wiki_dirs": ["references", "concepts", "synthesis", "entities", "skills", "projects", "journal"],
                "operational_dirs": ["_raw", "_staging", "_quarantine", "_runs", "_evolution", "_meta"],
                "papers": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    }
    for relative_file, content in files.items():
        path = vault_path / relative_file
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(relative_file)
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
