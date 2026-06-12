import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "paper-source" / "scripts" / "build" / "paper_source" / "migrate_active_internal_artifacts.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("paper_source_migrate_active_internal_artifacts", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_transform_request_payload_canonicalizes_request_shape():
    module = _load_module()
    payload = {
        "schema_version": "prw-record-request-v1",
        "request_id": "prw-fixture-request",
        "status": "ready_for_epi_record",
        "paper_slug": "fixture-paper",
        "recommended_command": "record-wiki-ingest --from-prw-request _epi/staging/papers/fixture-paper/prw-record-request.json",
        "final_pages": [
            {"relative_path": "reports/auv-control-epi-batch-reading-map.md"},
            {"relative_path": "opportunities/auv-control-research-opportunities-from-epi-batch.md"},
        ],
        "final_source_review": {
            "path": "_epi/staging/papers/fixture-paper/final-source-review.json",
        },
        "prw_task": {
            "route": "update_wiki",
            "summary": "PRW refreshed formal pages/provenance under Paper Wiki 0.2.1 rules. EPI should consume this request with record-wiki-ingest after user approval.",
            "snapshot": "_epi/meta/formal-page-snapshots/example/",
        },
    }

    result = module._transform_request_payload(payload)

    assert result["schema_version"] == "paper-wiki-record-request-v1"
    assert result["status"] == "ready_for_paper_source_record"
    assert result["request_id"] == "paper-wiki-fixture-request"
    assert result["recommended_command"] == (
        "record-wiki-ingest --from-paper-wiki-request "
        "_paper_source/staging/papers/fixture-paper/paper-wiki-record-request.json"
    )
    assert "paper_wiki_task" in result
    assert "prw_task" not in result
    assert result["paper_wiki_task"]["snapshot"] == "_paper_source/meta/formal-page-snapshots/example/"
    assert result["final_pages"][0]["relative_path"] == "reports/auv-control-reading-map.md"
    assert result["final_pages"][1]["relative_path"] == "opportunities/auv-control-research-opportunities.md"


def test_transform_request_payload_does_not_duplicate_paper_wiki_prefix():
    module = _load_module()
    payload = {
        "schema_version": "prw-record-request-v1",
        "request_id": "prw-paper-wiki-021-rebuild-20260608-fixture",
        "status": "ready_for_epi_record",
        "paper_slug": "fixture-paper",
    }

    result = module._transform_request_payload(payload)

    assert result["request_id"] == "paper-wiki-021-rebuild-20260608-fixture"


def test_rewrite_json_normalizes_embedded_request_like_object():
    module = _load_module()
    payload = {
        "source_request": {
            "schema_version": "paper-wiki-record-request-v1",
            "request_id": "paper-wiki-paper-wiki-021-rebuild-20260608-fixture",
            "status": "ready_for_paper_source_record",
            "automation_mode": "ask",
            "paper_slug": "fixture-paper",
            "recommended_command": "record-wiki-ingest --from-paper-wiki-request _epi/staging/papers/fixture-paper/paper-wiki-record-request.json",
            "paper_wiki_task": {
                "snapshot": "_epi/meta/formal-page-snapshots/example/",
            },
        }
    }

    result = module._rewrite_json(payload)

    assert result["source_request"]["request_id"] == "paper-wiki-021-rebuild-20260608-fixture"
    assert result["source_request"]["paper_wiki_task"]["snapshot"] == "_paper_source/meta/formal-page-snapshots/example/"
    assert result["source_request"]["recommended_command"] == (
        "record-wiki-ingest --from-paper-wiki-request "
        "_paper_source/staging/papers/fixture-paper/paper-wiki-record-request.json"
    )
    assert result["source_request"]["paper_slug"] == "fixture-paper"


def test_rewrite_json_replaces_legacy_schema_names():
    module = _load_module()
    payload = {
        "schema_version": "epi-wiki-ingest-record-v1",
        "brief": {"schema_version": "epi-wiki-ingest-brief-v1"},
        "final_source_review": {
            "schema_version": "epi-final-source-review-v1",
            "contract": {"schema_version": "epi-final-source-review-contract-v1"},
        },
        "human_approval": {"schema_version": "epi-human-approval-v1"},
        "agent_trigger": {"schema_version": "epi-wiki-agent-trigger-v1"},
        "source_audit": {"schema_version": "epi-source-bundle-audit-v1"},
        "code_verification": {"schema_version": "epi-code-verification-v1"},
        "zotero": {"schema_version": "epi-zotero-record-v1"},
        "required_wiki_skills": ["paper-research-wiki", "epi-wiki-deposition"],
        "configured_by": "codex-epi-config-setup",
        "recording_status": "awaiting-epi-record-wiki-ingest",
        "completed_status": "epi-recorded",
    }

    result = module._rewrite_json(payload)

    assert result["schema_version"] == "paper-source-wiki-ingest-record-v1"
    assert result["brief"]["schema_version"] == "paper-source-wiki-ingest-brief-v1"
    assert result["final_source_review"]["schema_version"] == "paper-source-final-source-review-v1"
    assert result["final_source_review"]["contract"]["schema_version"] == "paper-source-final-source-review-contract-v1"
    assert result["human_approval"]["schema_version"] == "paper-source-human-approval-v1"
    assert result["agent_trigger"]["schema_version"] == "paper-source-wiki-agent-trigger-v1"
    assert result["source_audit"]["schema_version"] == "paper-source-source-bundle-audit-v1"
    assert result["code_verification"]["schema_version"] == "paper-source-code-verification-v1"
    assert result["zotero"]["schema_version"] == "paper-source-zotero-record-v1"
    assert result["required_wiki_skills"] == ["paper-research-wiki", "paper-source-paper-deposition"]
    assert result["configured_by"] == "codex-paper-source-config-setup"
    assert result["recording_status"] == "awaiting-paper-source-record-wiki-ingest"
    assert result["completed_status"] == "paper-source-recorded"


def test_rewrite_json_replaces_windows_formal_page_renames():
    module = _load_module()
    payload = {
        "final_pages": [
            {"path": "D:\\paper-research-wiki\\reports\\auv-control-epi-batch-reading-map.md"},
            {"path": "D:\\paper-research-wiki\\reports\\auv-planning-and-cooperation-epi-reading-map.md"},
            {"path": "D:\\paper-research-wiki\\opportunities\\auv-control-research-opportunities-from-epi-batch.md"},
        ],
        "wikilink": "[[reports/auv-control-epi-batch-reading-map]] and [[opportunities/auv-control-research-opportunities-from-epi-batch]]",
    }

    result = module._rewrite_json(payload)

    paths = [item["path"] for item in result["final_pages"]]
    assert paths == [
        "D:\\paper-research-wiki\\reports\\auv-control-reading-map.md",
        "D:\\paper-research-wiki\\reports\\auv-planning-and-cooperation-reading-map.md",
        "D:\\paper-research-wiki\\opportunities\\auv-control-research-opportunities.md",
    ]
    assert "auv-control-epi-batch" not in result["wikilink"]
    assert "opportunities/auv-control-research-opportunities" in result["wikilink"]


def test_rewrite_json_replaces_legacy_formal_page_paths_in_dict_keys():
    module = _load_module()
    payload = {
        "hashes": {
            "final_page:reports/auv-control-epi-batch-reading-map.md": "abc123",
            "final_page:opportunities/auv-control-research-opportunities-from-epi-batch.md": "def456",
        }
    }

    result = module._rewrite_json(payload)

    assert "final_page:reports/auv-control-reading-map.md" in result["hashes"]
    assert "final_page:opportunities/auv-control-research-opportunities.md" in result["hashes"]
    assert "final_page:reports/auv-control-epi-batch-reading-map.md" not in result["hashes"]
    assert "final_page:opportunities/auv-control-research-opportunities-from-epi-batch.md" not in result["hashes"]


def test_rewrite_json_renames_prw_request_hash_key():
    module = _load_module()
    payload = {
        "input_artifact_hashes": {
            "prw-record-request.json": "abc123",
        }
    }

    result = module._rewrite_json(payload)

    assert "paper-wiki-record-request.json" in result["input_artifact_hashes"]
    assert "prw-record-request.json" not in result["input_artifact_hashes"]


def test_rewrite_json_normalizes_lifecycle_contract_fields():
    module = _load_module()
    payload = {
        "allowed_states": ["draft", "review-needed", "source-reviewed", "under-review", "verified"],
        "page_lifecycle_states": ["review-needed"],
        "lifecycle": "review-needed",
        "status": "review-needed",
        "summary": "page_lifecycle with a status in allowed states draft -> review-needed -> source-reviewed -> under-review -> verified",
    }

    result = module._rewrite_json(payload)

    assert result["allowed_states"] == ["draft"]
    assert result["page_lifecycle_states"] == ["draft"]
    assert result["lifecycle"] == "draft"
    assert result["status"] == "draft"
    assert result["summary"] == "page_lifecycle with a status in allowed states draft"


def test_rewrite_json_canonicalizes_retention_policy_protected_paths():
    module = _load_module()
    payload = {
        "protected": [
            "raw",
            "meta/epi-config.yaml",
            "meta/epi-config-state.json",
            "meta/paper-source-config.yaml",
        ]
    }

    result = module._rewrite_json(payload)

    assert result["protected"] == [
        "raw",
        "meta/paper-source-config.yaml",
        "meta/paper-source-config-state.json",
    ]


def test_migrate_root_manifest_keeps_legacy_ignore_but_drops_legacy_qmd_examples(tmp_path):
    module = _load_module()
    manifest = tmp_path / ".manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "lifecycle": "review-needed",
                "recording_status": "awaiting-epi-record-wiki-ingest",
                "prw_record_request": "_paper_source/staging/papers/example/prw-record-request.json",
                "qmd_collection_policy": {
                    "ignore_patterns": ["_paper_source/**", "_epi/**"],
                    "forbidden_examples": ["_epi/raw/<slug>/mineru/paper.md"],
                    "verification_commands": ["qmd ls paper-research-wiki/_epi"],
                },
                "legacy_internal_root": "_epi",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    actions = module._migrate_root_manifest(tmp_path, execute=True)

    assert actions == [{"action": "rewrite", "path": str(manifest)}]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["lifecycle"] == "draft"
    assert payload["recording_status"] == "awaiting-paper-source-record-wiki-ingest"
    assert payload["paper_wiki_record_request"] == "_paper_source/staging/papers/example/paper-wiki-record-request.json"
    assert payload["legacy_internal_root"] == "_epi"
    assert "_epi/**" in payload["qmd_collection_policy"]["ignore_patterns"]
    assert "_paper_source/**" in payload["qmd_collection_policy"]["ignore_patterns"]
    assert "_epi/raw/<slug>/mineru/paper.md" not in payload["qmd_collection_policy"]["forbidden_examples"]
    assert "qmd ls paper-research-wiki/_epi" not in payload["qmd_collection_policy"]["verification_commands"]


def test_refresh_current_record_hashes_updates_live_sidecars_but_skips_run_history(tmp_path):
    module = _load_module()
    vault = tmp_path / "vault"
    page = vault / "references" / "fixture.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\nlifecycle: draft\n---\n\n# Fixture\n\nUpdated body.\n",
        encoding="utf-8",
    )
    live_hash = module._file_sha256(page)
    live_size = page.stat().st_size
    slug = "fixture-paper"
    stale_hash = "0" * 64
    staging = vault / "_paper_source" / "staging" / "papers" / slug
    raw = vault / "_paper_source" / "raw" / slug
    run_history = vault / "_paper_source" / "runs" / "record-wiki-ingest-old" / "report.json"
    staging.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    run_history.parent.mkdir(parents=True, exist_ok=True)

    manifest = vault / ".manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "last_graph_sync": {
                    "final_page_records": [
                        {
                            "relative_path": "references/fixture.md",
                            "sha256": stale_hash,
                            "size_bytes": 1,
                            "lifecycle": "review-needed",
                        }
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    review_path = staging / "final-source-review.json"
    review_path.write_text(
        json.dumps(
            {
                "schema_version": "paper-source-final-source-review-v1",
                "final_page_records": [
                    {"relative_path": "references/fixture.md", "sha256": stale_hash, "size_bytes": 1}
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    request_path = staging / "paper-wiki-record-request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "paper-wiki-record-request-v1",
                "final_pages": [
                    {"relative_path": "references/fixture.md", "sha256": stale_hash, "size_bytes": 1}
                ],
                "final_source_review": {"path": str(review_path), "sha256": stale_hash},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for record_path in (staging / "wiki-ingest-record.json", raw / "wiki-ingest-record.json"):
        record_path.write_text(
            json.dumps(
                {
                    "schema_version": "paper-source-wiki-ingest-record-v1",
                    "page_records": [
                        {"relative_path": "references/fixture.md", "sha256": stale_hash, "size_bytes": 1}
                    ],
                    "input_artifact_hashes": {"final_page:references/fixture.md": stale_hash},
                    "final_page_hashes": {"final_page:references/fixture.md": stale_hash},
                    "final_source_review": {"path": str(review_path), "sha256": stale_hash},
                    "source_request": {"path": str(request_path), "sha256": stale_hash},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    run_history.write_text(
        json.dumps(
            {
                "page_records": [
                    {"relative_path": "references/fixture.md", "sha256": stale_hash, "size_bytes": 1}
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    actions = module._refresh_current_record_hashes(vault, execute=True)

    assert {Path(action["path"]).name for action in actions} == {
        ".manifest.json",
        "final-source-review.json",
        "paper-wiki-record-request.json",
        "wiki-ingest-record.json",
    }
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_record = manifest_payload["last_graph_sync"]["final_page_records"][0]
    assert manifest_record["sha256"] == live_hash
    assert manifest_record["size_bytes"] == live_size
    assert manifest_record["lifecycle"] == "draft"
    review_payload = json.loads(review_path.read_text(encoding="utf-8"))
    assert review_payload["final_page_records"][0]["sha256"] == live_hash
    request_payload = json.loads(request_path.read_text(encoding="utf-8"))
    assert request_payload["final_pages"][0]["sha256"] == live_hash
    assert request_payload["final_source_review"]["sha256"] == module._file_sha256(review_path)
    for record_path in (staging / "wiki-ingest-record.json", raw / "wiki-ingest-record.json"):
        record_payload = json.loads(record_path.read_text(encoding="utf-8"))
        assert record_payload["page_records"][0]["sha256"] == live_hash
        assert record_payload["input_artifact_hashes"]["final_page:references/fixture.md"] == live_hash
        assert record_payload["final_page_hashes"]["final_page:references/fixture.md"] == live_hash
        assert record_payload["source_request"]["sha256"] == module._file_sha256(request_path)
    history_payload = json.loads(run_history.read_text(encoding="utf-8"))
    assert history_payload["page_records"][0]["sha256"] == stale_hash


def test_migrate_active_files_skips_raw_and_internal_audit_copies(tmp_path):
    module = _load_module()
    root = tmp_path / "_paper_source"
    raw_file = root / "raw" / "example" / "mineru" / "paper.md"
    raw_record = root / "raw" / "example" / "wiki-ingest-record.json"
    raw_run_state = root / "raw" / "example" / "run-state.json"
    raw_code_verification = root / "raw" / "example" / "code-verification.json"
    raw_metadata = root / "raw" / "example" / "metadata.json"
    premature_file = root / "staging" / "premature-formal-pages" / "example.md"
    run_report = root / "runs" / "record-wiki-ingest-20260608T120259801168Z" / "report.json"
    run_state = root / "runs" / "record-wiki-ingest-20260608T120259801168Z" / "run-state.json"
    active_file = root / "staging" / "papers" / "example" / "wiki-ingest-brief.json"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_record.parent.mkdir(parents=True, exist_ok=True)
    premature_file.parent.mkdir(parents=True, exist_ok=True)
    run_report.parent.mkdir(parents=True, exist_ok=True)
    active_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("source path _epi/raw/example/paper.pdf", encoding="utf-8")
    raw_record.write_text(json.dumps({"lifecycle": "review-needed"}), encoding="utf-8")
    raw_run_state.write_text(json.dumps({"lifecycle": "review-needed"}), encoding="utf-8")
    raw_code_verification.write_text(json.dumps({"schema_version": "epi-code-verification-v1"}), encoding="utf-8")
    raw_metadata.write_text(json.dumps({"temp_path": "C:/Temp/epi-paper-search/example.pdf"}), encoding="utf-8")
    premature_file.write_text("lifecycle: review-needed", encoding="utf-8")
    run_report.write_text(json.dumps({"lifecycle": "review-needed"}), encoding="utf-8")
    run_state.write_text(json.dumps({"lifecycle": "review-needed"}), encoding="utf-8")
    active_file.write_text(json.dumps({"lifecycle": "review-needed"}), encoding="utf-8")

    actions = module._migrate_active_files(root, execute=True)

    assert {action["path"] for action in actions if action["action"] == "rewrite"} == {
        str(raw_code_verification),
        str(raw_record),
        str(raw_run_state),
        str(run_state),
        str(active_file),
    }
    assert raw_file.read_text(encoding="utf-8") == "source path _epi/raw/example/paper.pdf"
    assert json.loads(raw_record.read_text(encoding="utf-8"))["lifecycle"] == "draft"
    assert json.loads(raw_run_state.read_text(encoding="utf-8"))["lifecycle"] == "draft"
    assert json.loads(raw_code_verification.read_text(encoding="utf-8"))["schema_version"] == "paper-source-code-verification-v1"
    assert json.loads(raw_metadata.read_text(encoding="utf-8"))["temp_path"] == "C:/Temp/epi-paper-search/example.pdf"
    assert premature_file.read_text(encoding="utf-8") == "lifecycle: review-needed"
    assert json.loads(run_report.read_text(encoding="utf-8"))["lifecycle"] == "review-needed"
    assert json.loads(run_state.read_text(encoding="utf-8"))["lifecycle"] == "draft"
    assert json.loads(active_file.read_text(encoding="utf-8"))["lifecycle"] == "draft"


def test_migrate_active_files_keeps_nested_legacy_ignore_but_drops_legacy_qmd_examples(tmp_path):
    module = _load_module()
    root = tmp_path / "_paper_source"
    active_file = root / "staging" / "papers" / "example" / "wiki-ingest-brief.json"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    active_file.write_text(
        json.dumps(
            {
                "wiki_rule_source_model": {
                    "qmd_collection_policy": {
                        "ignore_patterns": ["_paper_source/**", "_paper_source/**"],
                        "qmd_collection_contract": "it must ignore _paper_source/**, legacy _paper_source/**, .obsidian/**, and .claude/**.",
                        "verification_commands": ["qmd ls paper-research-wiki/_paper_source"],
                    }
                },
                "lifecycle": "review-needed",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    actions = module._migrate_active_files(root, execute=True)

    assert actions == [{"action": "rewrite", "path": str(active_file)}]
    payload = json.loads(active_file.read_text(encoding="utf-8"))
    qmd_policy = payload["wiki_rule_source_model"]["qmd_collection_policy"]
    assert payload["lifecycle"] == "draft"
    assert qmd_policy["ignore_patterns"] == ["_paper_source/**", "_epi/**", ".obsidian/**", ".claude/**"]
    assert "legacy _epi/**" in qmd_policy["qmd_collection_contract"]
    assert "legacy _paper_source/**" not in qmd_policy["qmd_collection_contract"]
    assert "qmd ls paper-research-wiki/_epi" not in qmd_policy["verification_commands"]


def test_migrate_config_writes_canonical_paper_source_files(tmp_path):
    module = _load_module()
    meta_root = tmp_path / "_paper_source" / "meta"
    config_history = meta_root / "config-history"
    config_history.mkdir(parents=True, exist_ok=True)
    (config_history / "20260530-init-config.yaml").write_text("profile: demo\n", encoding="utf-8")
    (meta_root / "epi-config.yaml").write_text("zotero:\n  collection: EPI\n", encoding="utf-8")
    (meta_root / "epi-config-state.json").write_text(
        json.dumps(
            {
                "configured": True,
                "config_path": "D:\\paper-research-wiki\\_epi\\meta\\epi-config.yaml",
                "history_path": "D:\\paper-research-wiki\\_epi\\meta\\config-history\\20260530-init-config.yaml",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    actions = module._migrate_config(meta_root, execute=True)

    canonical_config = meta_root / "paper-source-config.yaml"
    canonical_state = meta_root / "paper-source-config-state.json"
    assert canonical_config.exists()
    assert canonical_state.exists()
    assert "collection: Paper Source" in canonical_config.read_text(encoding="utf-8")
    state = json.loads(canonical_state.read_text(encoding="utf-8"))
    assert state["config_path"] == str(canonical_config)
    assert state["history_path"].endswith("20260530-init-config.yaml")
    assert len(actions) == 2


def test_archive_legacy_root_files_moves_legacy_copies_out_of_active_root(tmp_path):
    module = _load_module()
    root = tmp_path / "_paper_source"
    meta = root / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (root / "README-legacy-1.md").write_text("legacy readme", encoding="utf-8")
    (root / "manifest-legacy-1.json").write_text("{}", encoding="utf-8")
    (meta / "epi-config.yaml").write_text("zotero:\n  collection: EPI\n", encoding="utf-8")
    (meta / "epi-config-state.json").write_text("{}", encoding="utf-8")
    (meta / "evidence-index-legacy-1.json").write_text("{}", encoding="utf-8")
    (meta / "paper-source-config.yaml").write_text("zotero:\n  collection: Paper Source\n", encoding="utf-8")
    (meta / "paper-source-config-state.json").write_text("{}", encoding="utf-8")
    (root / "policies").mkdir(parents=True, exist_ok=True)
    (root / "policies" / "retention.json").write_text("{}", encoding="utf-8")
    (root / "policies" / "retention-legacy-1.json").write_text("{}", encoding="utf-8")
    pending = root / "staging" / "wiki-batches" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    (pending / "wiki-batch-ingest-brief.json").write_text("{}", encoding="utf-8")
    (pending / "wiki-batch-ingest-brief-legacy-1.json").write_text("{}", encoding="utf-8")

    actions = module._archive_legacy_root_files(root, execute=True)

    assert not (root / "README-legacy-1.md").exists()
    assert not (root / "manifest-legacy-1.json").exists()
    assert not (meta / "epi-config.yaml").exists()
    assert not (meta / "epi-config-state.json").exists()
    assert not (meta / "evidence-index-legacy-1.json").exists()
    assert not (root / "policies" / "retention-legacy-1.json").exists()
    assert not (pending / "wiki-batch-ingest-brief-legacy-1.json").exists()
    archive_dirs = list((meta / "legacy-imports").iterdir())
    assert len(archive_dirs) == 1
    archive = archive_dirs[0]
    assert (archive / "README-legacy-1.md").exists()
    assert (archive / "manifest-legacy-1.json").exists()
    assert (archive / "meta" / "epi-config.yaml").exists()
    assert (archive / "policies" / "retention-legacy-1.json").exists()
    assert (archive / "staging" / "wiki-batches" / "pending" / "wiki-batch-ingest-brief-legacy-1.json").exists()
    assert len(actions) == 7


def test_regenerate_staging_handoffs_archives_legacy_task_and_calls_stage_paper(tmp_path, monkeypatch):
    module = _load_module()
    root = tmp_path / "_paper_source"
    staging_paper = root / "staging" / "papers" / "fixture-paper"
    raw_paper = root / "raw" / "fixture-paper"
    staging_paper.mkdir(parents=True, exist_ok=True)
    raw_paper.mkdir(parents=True, exist_ok=True)
    task_path = staging_paper / "wiki_deposition_task.json"
    task_path.write_text(json.dumps({"schema_version": "paper-source-wiki-deposition-task-v1"}), encoding="utf-8")
    (staging_paper / "promotion-plan.json").write_text(json.dumps({"workflow_mode": "reviewed-ingest"}), encoding="utf-8")

    calls = []

    def fake_stage_paper(vault, slug, paper_root, workflow_mode="fast-ingest", emit_legacy_deposition_task=False):
        calls.append(
            {
                "vault": str(vault),
                "slug": slug,
                "paper_root": str(paper_root),
                "workflow_mode": workflow_mode,
                "emit_legacy_deposition_task": emit_legacy_deposition_task,
            }
        )

    monkeypatch.setattr(module, "_load_stage_wiki_module", lambda: SimpleNamespace(stage_paper=fake_stage_paper))
    monkeypatch.setattr(module, "_utc_stamp", lambda: "20260611T080000Z")

    actions = module._regenerate_staging_handoffs(root, execute=True)

    archived = root / "meta" / "legacy-imports" / "20260611T080000Z-wiki-deposition-task-files" / "fixture-paper" / "paper-source-wiki-deposition-task-legacy.json"
    assert archived.exists()
    assert not task_path.exists()
    assert calls == [
        {
            "vault": str(tmp_path),
            "slug": "fixture-paper",
            "paper_root": str(raw_paper),
            "workflow_mode": "reviewed-ingest",
            "emit_legacy_deposition_task": False,
        }
    ]
    assert actions[0]["to"] == str(archived)
