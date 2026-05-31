import json
import subprocess
from pathlib import Path


def test_epi_metric_pack_checks_core_workflow_contracts(tmp_path):
    plugin_root = tmp_path / "epi"
    docs = plugin_root / "docs"
    scripts = plugin_root / "scripts"
    docs.mkdir(parents=True)
    scripts.mkdir(parents=True)
    (docs / "workflow.md").write_text(
        "The orchestrator writes run-state.json. "
        "No critic pass, no compiled wiki write. "
        "The critic gate must pass before promote-to-wiki. "
        "Raw artifacts include paper.pdf and metadata.json. "
        "Plugin Eval runs with the epi-quality-gates metric pack, then evaluation-brief creates "
        "the improvement brief for propose-evolution. "
        "The brief records source_completeness, a quality_loop_sources_complete gate, "
        "and collect-missing-quality-evidence when evidence is incomplete. "
        "The benchmark evidence uses epi-benchmark-v1, benchmark_contract, and invalid_sources "
        "to prevent a loose JSON blob from masquerading as a real benchmark.",
        encoding="utf-8",
    )
    script = (
        Path(__file__).resolve().parents[2]
        / "plugins"
        / "epi"
        / "metric-packs"
        / "epi-quality-gates"
        / "emit-epi-quality-gates.js"
    )

    result = subprocess.run(
        ["node", str(script), str(plugin_root), "plugin"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["epi-run-state-contract"]["status"] == "pass"
    assert checks["epi-critic-gate-contract"]["status"] == "pass"
    assert checks["epi-no-critic-no-wiki-write"]["status"] == "pass"
    assert checks["epi-raw-artifact-retention"]["status"] == "pass"
    assert checks["epi-development-quality-loop"]["status"] == "pass"
    assert checks["epi-quality-loop-sources-complete"]["status"] == "pass"
    assert checks["epi-benchmark-contract"]["status"] == "pass"
    assert payload["metrics"][0]["value"] == 1
