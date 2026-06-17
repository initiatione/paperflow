from pathlib import Path
import json
import re
import subprocess


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


def test_plugin_manifest_keywords_do_not_expose_legacy_plugin_names():
    for rel in [
        Path("plugins") / "paper-source" / ".codex-plugin" / "plugin.json",
        Path("plugins") / "paper-wiki" / ".codex-plugin" / "plugin.json",
    ]:
        payload = _load(ROOT / rel)
        keywords = {keyword.lower() for keyword in payload.get("keywords", [])}

        assert "epi" not in keywords
        assert "prw" not in keywords


def test_readme_frames_mineru_as_internal_helper():
    readme_zh = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8")

    assert "不是独立 marketplace 插件" in readme_zh
    assert "not as a separate marketplace plugin" in readme_en


def test_current_docs_do_not_use_pre_stage2_plugin_paths_as_live_paths():
    roots = [
        ROOT / "README.md",
        ROOT / "README.en.md",
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
            if "archive" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix.lower() not in {".md", ".json", ".py", ".yaml", ".yml", ".ps1"}:
                continue
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_paper_source_runtime_package_uses_current_directory_name_without_legacy_import_package():
    source_root = ROOT / "plugins" / "paper-source"

    assert (source_root / "scripts" / "build" / "paper_source" / "__init__.py").is_file()
    assert (source_root / "scripts" / "build" / "paper_source" / "paper_source_repository.py").is_file()
    assert not (source_root / "scripts" / "build" / "epi").exists()
    assert not (ROOT / "tests" / "epi").exists()
    assert (ROOT / "tests" / "paper_source").is_dir()


def test_current_file_and_directory_names_do_not_use_legacy_plugin_names():
    allowed_legacy_paths: set[Path] = set()
    scanned_roots = [
        ROOT / "docs" / "assets",
        ROOT / "docs" / "audits",
        ROOT / "docs" / "superpowers" / "plans",
        ROOT / "docs" / "superpowers" / "specs",
        ROOT / "plugins",
        ROOT / "scripts",
        ROOT / "tests",
    ]
    offenders = []

    for scanned_root in scanned_roots:
        if not scanned_root.exists():
            continue
        paths = [scanned_root] if scanned_root.is_file() else scanned_root.rglob("*")
        for path in paths:
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT)
            if any(part in {"archive", "completed", "superseded"} for part in relative.parts):
                continue
            if relative in allowed_legacy_paths:
                continue
            name = path.name.lower()
            if "epi" in name or "prw" in name:
                offenders.append(str(relative).replace("\\", "/"))

    assert offenders == []


def test_active_design_docs_do_not_preserve_retired_alias_contracts():
    scanned_roots = [
        ROOT / "docs" / "audits",
        ROOT / "docs" / "superpowers" / "plans",
        ROOT / "docs" / "superpowers" / "specs",
    ]
    banned = re.compile(
        r"from-prw|prw-record|epi-repository|EPI_|scripts[\\/]build[\\/]epi|"
        r"\bfrom\s+epi\b|\bimport\s+epi\b|compatibility adapter|"
        r"compatibility package|remain readable|fallback checks|legacy shim",
        re.IGNORECASE,
    )
    offenders = []

    for scanned_root in scanned_roots:
        if not scanned_root.exists():
            continue
        for path in scanned_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in {"archive", "completed", "superseded"} for part in relative.parts):
                continue
            text = path.read_text(encoding="utf-8")
            if banned.search(text):
                offenders.append(str(relative).replace("\\", "/"))

    assert offenders == []


def test_plugin_packages_do_not_track_python_cache_files():
    result = subprocess.run(
        ["git", "ls-files", "plugins/paper-source", "plugins/paper-wiki"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    bad = [
        path
        for path in result.stdout.splitlines()
        if "__pycache__" in Path(path).parts or path.endswith(".pyc")
    ]

    assert bad == []
