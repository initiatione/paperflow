from __future__ import annotations

import json
from pathlib import Path


REQUIRED_DIRS = [
    "_raw/papers",
    "_staging/papers",
    "_quarantine/papers",
    "_runs",
    "_evolution/proposals",
    "_evolution/active",
    "_evolution/archive",
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
        "index.md": "# Paper Research Wiki\n\nThis vault is dedicated to engineering paper research.\n",
        "log.md": "# Log\n\n## Initialized\n\n- Created dedicated paper research wiki structure.\n",
        "hot.md": "# Hot\n\nNo promoted papers yet.\n",
        ".manifest.json": json.dumps(
            {
                "vault_type": "engineering-paper-research",
                "schema": "raw source -> compiled wiki -> schema",
                "compiled_dirs": ["references", "concepts", "synthesis", "entities", "skills", "projects", "journal"],
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

    parser = argparse.ArgumentParser(description="Initialize a dedicated engineering paper research wiki.")
    parser.add_argument("--vault", type=Path, default=Path(r"D:\paper-research-wiki"))
    args = parser.parse_args()
    created = initialize_paper_wiki(args.vault)
    print(f"initialized={args.vault.resolve()}")
    print(f"created_count={len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
