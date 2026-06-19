from __future__ import annotations

import json
import textwrap
from pathlib import Path


def create_fake_zotero_plugin(
    root: Path,
    *,
    official: bool = True,
    full_help: bool = True,
) -> Path:
    plugin = root / "fake-zotero-plugin"
    helper = plugin / "skills" / "zotero" / "scripts" / "zotero.py"
    helper.parent.mkdir(parents=True)
    (plugin / ".codex-plugin").mkdir()
    (plugin / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "zotero" if official else "not-zotero",
                "interface": {"displayName": "Zotero" if official else "Other"},
            }
        ),
        encoding="utf-8",
    )
    (plugin / "skills" / "zotero" / "SKILL.md").write_text(
        "---\nname: Zotero\n---\n\n# Zotero\n" if official else "---\nname: Other\n---\n\n# Other\n",
        encoding="utf-8",
    )
    commands = (
        "status inventory search export-bibtex import-bibtex import-ris selected-target"
        if full_help
        else "status search"
    )
    helper.write_text(
        textwrap.dedent(
            f"""
            import json
            import os
            import sys
            import time
            from pathlib import Path

            COMMANDS = {commands!r}

            def dump(value):
                print(json.dumps(value))

            if len(sys.argv) == 1 or "--help" in sys.argv:
                print(COMMANDS)
                raise SystemExit(0)

            mode = os.environ.get("FAKE_ZOTERO_MODE", "ok")
            if mode == "sleep":
                time.sleep(2)
                raise SystemExit(0)
            if mode == "invalid_json":
                print("{{")
                raise SystemExit(0)

            command = sys.argv[1]
            if mode == "fail":
                print("connector failed: api_key=abc123 https://proxy.example/?token=secret", file=sys.stderr)
                raise SystemExit(2)

            if command == "status":
                payload = {{
                    "local_api_enabled_pref": mode != "local_api_disabled",
                    "api_running": mode not in ("desktop_unavailable", "local_api_disabled"),
                    "connector_running": mode != "connector_unavailable",
                }}
                dump(payload)
            elif command == "inventory":
                raw = os.environ.get("FAKE_ZOTERO_INVENTORY_JSON")
                dump(json.loads(raw) if raw else [{{"key": "ITEM1", "title": "Inventory Paper"}}])
            elif command == "search":
                raw = os.environ.get("FAKE_ZOTERO_SEARCH_JSON")
                if raw:
                    dump(json.loads(raw))
                else:
                    row = {{"key": "ITEM1", "title": sys.argv[2], "year": "2026"}}
                    if "--with-bibtex-keys" in sys.argv:
                        row["bibtexKey"] = "paper_2026"
                    dump([row])
            elif command == "export-bibtex":
                text = "@article{{paper_2026, title={{Paper}}}}\\n"
                if "--out" in sys.argv:
                    out = Path(sys.argv[sys.argv.index("--out") + 1])
                    out.write_text(text, encoding="utf-8")
                    dump({{"path": str(out), "bibtex_entries": 1}})
                else:
                    print(text)
            elif command == "selected-target":
                dump({{"collection": {{"name": os.environ.get("FAKE_ZOTERO_TARGET", "Paper Wiki")}}}})
            elif command in ("import-bibtex", "import-ris"):
                if "--yes" not in sys.argv:
                    print("Refusing to write to Zotero without --yes.", file=sys.stderr)
                    raise SystemExit(3)
                dump({{"status": 200, "session": "test-session"}})
            else:
                print(f"unknown command {{command}}", file=sys.stderr)
                raise SystemExit(2)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    return plugin
