import json
from datetime import datetime, timezone

from epi.run_index import auto_prune_run_lifecycle, prune_run_lifecycle


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_run(vault, run_id, workflow="paper-discovery-dry-run", status="success"):
    run_dir = vault / "_runs" / run_id
    _write_json(
        run_dir / "run-state.json",
        {
            "run_id": run_id,
            "workflow_type": workflow,
            "status": status,
            "state": "done",
            "started_at": f"2026-05-29T00:00:0{run_id[-1]}+00:00",
            "finished_at": f"2026-05-29T00:00:1{run_id[-1]}+00:00" if status != "running" else None,
        },
    )
    _write_json(run_dir / "report.json", {"next_actions": []})
    return run_dir


def _seed_stale_running_run(vault, run_id):
    run_dir = vault / "_runs" / run_id
    _write_json(
        run_dir / "run-state.json",
        {
            "run_id": run_id,
            "workflow_type": "paper-discovery-dry-run",
            "status": "running",
            "state": "configured",
            "started_at": "2026-05-28T00:00:00+00:00",
        },
    )
    return run_dir


def _seed_active_running_run(vault, run_id):
    run_dir = vault / "_runs" / run_id
    _write_json(
        run_dir / "run-state.json",
        {
            "run_id": run_id,
            "workflow_type": "paper-discovery-dry-run",
            "status": "running",
            "state": "configured",
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return run_dir


def test_run_lifecycle_dry_run_keeps_files_and_reports_candidates(tmp_path):
    vault = tmp_path / "vault"
    old_run = _seed_run(vault, "run-1")
    _seed_run(vault, "run-2")
    _seed_run(vault, "run-3")

    result = prune_run_lifecycle(vault, keep_latest=1, keep_per_workflow=0, apply=False)

    assert result["dry_run"] is True
    assert result["candidate_count"] == 2
    assert old_run.exists()
    assert (vault / "_meta" / "run-lifecycle").is_dir()


def test_run_lifecycle_apply_removes_only_terminal_candidates_and_refreshes_index(tmp_path):
    vault = tmp_path / "vault"
    removable = _seed_run(vault, "run-1")
    kept_recent = _seed_run(vault, "run-2")
    protected = _seed_active_running_run(vault, "run-3")

    result = prune_run_lifecycle(vault, keep_latest=1, keep_per_workflow=0, apply=True)

    assert result["dry_run"] is False
    assert result["deleted_count"] == 1
    assert not removable.exists()
    assert kept_recent.exists()
    assert protected.exists()
    index = json.loads((vault / "_runs" / "index.json").read_text(encoding="utf-8"))
    assert index["summary"]["total_runs"] == 2


def test_auto_run_lifecycle_skips_until_threshold_then_applies(tmp_path):
    vault = tmp_path / "vault"
    for index in range(15):
        _seed_run(vault, f"run-{index:02d}")

    skipped = auto_prune_run_lifecycle(vault, keep_latest=15, keep_per_workflow=0)

    assert skipped["skipped"] is True
    assert skipped["deleted_count"] == 0
    assert len([path for path in (vault / "_runs").iterdir() if path.is_dir()]) == 15

    oldest_run = vault / "_runs" / "run-00"
    newest_run = _seed_run(vault, "run-99")
    applied = auto_prune_run_lifecycle(vault, keep_latest=15, keep_per_workflow=0)

    assert applied["auto"] is True
    assert applied["skipped"] is False
    assert applied["deleted_count"] == 1
    assert not oldest_run.exists()
    assert newest_run.exists()
    assert (vault / "_meta" / "run-lifecycle").is_dir()


def test_run_lifecycle_can_prune_failed_invalid_and_stale_running_runs(tmp_path):
    vault = tmp_path / "vault"
    failed = _seed_run(vault, "run-failed", status="failed")
    invalid = vault / "_runs" / "run-invalid"
    invalid.mkdir(parents=True)
    stale_running = _seed_stale_running_run(vault, "run-stale-running")
    active = _seed_active_running_run(vault, "run-active")
    protected = _seed_run(vault, "run-success")

    result = prune_run_lifecycle(vault, keep_latest=1, keep_per_workflow=0, apply=True)

    deleted_ids = {item["run_id"] for item in result["deleted"]}
    assert {"run-failed", "run-invalid", "run-stale-running"}.issubset(deleted_ids)
    assert not failed.exists()
    assert not invalid.exists()
    assert not stale_running.exists()
    assert active.exists()
    assert protected.exists()
