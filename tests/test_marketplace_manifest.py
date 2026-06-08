from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_marketplace_manifests_expose_paperflow_bundle_with_stage2_machine_names():
    for rel in [".agents/plugins/marketplace.json", "marketplace.json"]:
        payload = _load(ROOT / rel)
        plugin_names = [plugin["name"] for plugin in payload["plugins"]]

        assert payload["name"] == "paperflow"
        assert payload["interface"]["displayName"] == "PaperFlow"
        assert plugin_names == ["paper-source", "paper-wiki"]
        assert "mineru-paper-parser" not in plugin_names


def test_stage2_naming_uses_paperflow_plugin_names_and_paths():
    root_marketplace = _load(ROOT / "marketplace.json")
    agent_marketplace = _load(ROOT / ".agents" / "plugins" / "marketplace.json")

    for payload in [root_marketplace, agent_marketplace]:
        assert payload["name"] == "paperflow"
        assert payload["interface"]["displayName"] == "PaperFlow"
        entries = {plugin["name"]: plugin for plugin in payload["plugins"]}
        assert set(entries) == {"paper-source", "paper-wiki"}
        assert entries["paper-source"]["source"]["path"] == "./plugins/paper-source"
        assert entries["paper-wiki"]["source"]["path"] == "./plugins/paper-wiki"
        assert "epi" not in entries
        assert "prw" not in entries
        assert "ps" not in entries
        assert "pw" not in entries


def test_readme_frames_mineru_as_internal_helper():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "not as a separate marketplace plugin" in text


def test_current_docs_do_not_use_pre_stage2_plugin_paths_as_live_paths():
    excluded = {
        ROOT / "docs" / "superpowers" / "specs" / "2026-06-08-paperflow-stage1-naming-design.md",
        ROOT / "docs" / "superpowers" / "specs" / "2026-06-08-paperflow-stage2-machine-rename-design.md",
    }
    roots = [
        ROOT / "README.md",
        ROOT / "docs",
        ROOT / "plugins",
        ROOT / "tests",
        ROOT / "marketplace.json",
        ROOT / ".agents" / "plugins" / "marketplace.json",
    ]
    pattern = re.compile(r"plugins[\\/](?:epi|PRW)(?=[\\/`\s]|$)")
    offenders = []

    for root in roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file():
                continue
            if path in excluded or "archive" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix.lower() not in {".md", ".json", ".py", ".yaml", ".yml", ".ps1"}:
                continue
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
