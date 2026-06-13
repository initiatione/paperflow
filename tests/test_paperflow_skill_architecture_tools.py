import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def run_json(script: str, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args, "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(result.stdout)


def test_route_health_accepts_paperflow_plugin_layouts():
    source = run_json("paperflow_route_health.py", "plugins/paper-source")
    wiki = run_json("paperflow_route_health.py", "plugins/paper-wiki")

    assert source["plugin"] == "paper-source"
    assert wiki["plugin"] == "paper-wiki"
    assert source["routing_path"] == "plugins/paper-source/skills/routing.yaml"
    assert wiki["routing_path"] == "plugins/paper-wiki/skills/routing.yaml"
    assert source["route_count"] >= 10
    assert wiki["route_count"] >= 6
    assert not [w for w in source["warnings"] if w["kind"] == "missing-skill"]
    assert not [w for w in wiki["warnings"] if w["kind"] == "missing-skill"]


def test_route_health_reports_only_unacknowledged_overlap_warnings():
    source = run_json("paperflow_route_health.py", "plugins/paper-source")
    wiki = run_json("paperflow_route_health.py", "plugins/paper-wiki")

    assert not [w for w in source["warnings"] if w["kind"] == "overlap"]
    assert not [w for w in wiki["warnings"] if w["kind"] == "overlap"]
    assert source["acknowledged_overlaps"] == []
    assert wiki["acknowledged_overlaps"] == [
        {
            "kind": "overlap",
            "routes": ["redo_extraction", "maintain_figures"],
            "tokens": ["evidence", "figure", "formula"],
            "reason": (
                "maintain_figures repairs figure/formula evidence artifacts, while redo_extraction "
                "performs broader source-map-grounded extraction."
            ),
        }
    ]


def test_footprint_reports_always_read_and_route_costs():
    source = run_json("paperflow_footprint.py", "plugins/paper-source")
    wiki = run_json("paperflow_footprint.py", "plugins/paper-wiki")

    assert source["plugin"] == "paper-source"
    assert wiki["plugin"] == "paper-wiki"
    assert source["always_read_lines"] > 0
    assert wiki["always_read_lines"] > 0
    assert "paper_ingest" in source["routes"]
    assert "extract_papers" in wiki["routes"]
    assert source["routes"]["paper_ingest"]["lines"] > 0
    assert wiki["routes"]["extract_papers"]["lines"] > 0
    assert source["top_files"]
    assert wiki["top_files"]


def test_routing_manifests_record_external_reference_urls_without_versions():
    for plugin in ["paper-source", "paper-wiki"]:
        routing = yaml.safe_load(
            (ROOT / "plugins" / plugin / "skills" / "routing.yaml").read_text(encoding="utf-8")
        )
        refs = routing["external_references"]
        assert refs["skill_architecture"]["url"] == "https://github.com/WoJiSama/skill-based-architecture"
        assert refs["skill_architecture"]["role"] == "structure reference"
        assert refs["obsidian_skills"]["url"] == "https://github.com/kepano/obsidian-skills"
        assert refs["obsidian_skills"]["role"] == "Obsidian syntax authority"
        assert refs["freshness_policy"]["rule"]
        assert set(refs["skill_architecture"]) == {"url", "role", "local_adaptation"}
        assert set(refs["obsidian_skills"]) == {"url", "role", "local_adaptation"}


def test_release_checks_generate_plugin_eval_coverage_artifacts_transiently():
    source_script = (ROOT / "scripts" / "release_check_paper_source.ps1").read_text(encoding="utf-8")
    wiki_script = (ROOT / "scripts" / "release_check_paper_wiki.ps1").read_text(encoding="utf-8")

    assert 'CoverageSource = "plugins/paper-source/scripts/build"' in source_script
    assert 'CoverageSource = "plugins/paper-wiki/scripts"' in wiki_script
    for script in [source_script, wiki_script]:
        assert 'Join-Path $PluginRoot ".plugin-eval"' in script
        assert '"coverage.xml"' in script
        assert "python -m coverage run" in script
        assert "python -m coverage xml" in script
        assert "RunStamp" in script
        assert "--basetemp=$baseTemp" in script
        assert "--basetemp=$coverageBaseTemp" in script
        assert "try {" in script
        assert "finally {" in script
        assert "Clear-PluginGeneratedArtifacts" in script
        assert "paperflow_audit.py package-hygiene $PluginRoot --clean --json" in script


def test_paper_wiki_top_level_scripts_are_thin_wrappers():
    script_root = ROOT / "plugins" / "paper-wiki" / "scripts"
    build_root = script_root / "build" / "paper_wiki"

    for name in ["maintain_figures.py", "maintain_related.py", "migrate_formal_page_contract.py"]:
        wrapper = (script_root / name).read_text(encoding="utf-8")
        implementation = build_root / name

        assert implementation.is_file()
        assert len(wrapper.splitlines()) <= 20
        assert "from paper_wiki import" in wrapper
        assert "globals().update" in wrapper


def test_paperflow_plugin_packages_do_not_ship_repo_contract_tests():
    for plugin in ["paper-source", "paper-wiki"]:
        test_dir = ROOT / "plugins" / plugin / "tests"
        if not test_dir.exists():
            continue
        shipped_tests = sorted(test_dir.rglob("test_*.py"))
        assert shipped_tests == []

    assert (ROOT / "tests" / "paper_source" / "test_skill_bundle_contract.py").is_file()
