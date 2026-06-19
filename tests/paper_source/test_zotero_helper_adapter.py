from paper_source import zotero_helper_adapter as adapter
from paper_source.zotero_helper_adapter import ZoteroHelperAdapter
from zotero_helper_fixture import create_fake_zotero_plugin


def test_discovers_trusted_fake_official_helper(tmp_path):
    plugin = create_fake_zotero_plugin(tmp_path)

    resolution = adapter.discover_zotero_helper(
        extra_roots=[plugin],
        include_defaults=False,
    )

    assert resolution.helper is not None
    assert resolution.helper["source"] == "configured_root"
    assert resolution.candidates[0]["validated"] is True
    assert resolution.gate is None


def test_rejects_incompatible_or_non_official_helpers(tmp_path):
    plugin = create_fake_zotero_plugin(tmp_path, official=False)

    resolution = adapter.discover_zotero_helper(
        extra_roots=[plugin],
        include_defaults=False,
    )

    assert resolution.helper is None
    assert resolution.gate == "zotero_helper_incompatible"
    assert resolution.candidates[0]["rejection_reason"] in {
        "skill_identity_mismatch",
        "plugin_identity_mismatch",
    }


def test_rejects_missing_command_surface(tmp_path):
    plugin = create_fake_zotero_plugin(tmp_path, full_help=False)

    resolution = adapter.discover_zotero_helper(
        extra_roots=[plugin],
        include_defaults=False,
    )

    assert resolution.helper is None
    assert resolution.gate == "zotero_helper_incompatible"
    assert resolution.candidates[0]["rejection_reason"] == "required_commands_missing"
    assert "import-bibtex" in resolution.candidates[0]["details"]["missing_commands"]


def test_adapter_operations_use_helper_commands(tmp_path, monkeypatch):
    plugin = create_fake_zotero_plugin(tmp_path)
    zotero = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False)

    status = zotero.status()
    inventory = zotero.inventory()
    search = zotero.search("Paper Title", with_bibtex_keys=True)
    bibtex = zotero.export_item_bibtex("ITEM1")

    assert status["ok"] is True
    assert inventory["data"][0]["key"] == "ITEM1"
    assert search["data"][0]["bibtexKey"] == "paper_2026"
    assert "@article" in bibtex["data"]
    assert "search" in search["command"]


def test_status_payload_maps_unavailable_gates(tmp_path, monkeypatch):
    plugin = create_fake_zotero_plugin(tmp_path)
    zotero = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False)

    monkeypatch.setenv("FAKE_ZOTERO_MODE", "local_api_disabled")
    result = zotero.status()

    assert result["ok"] is False
    assert result["gate"] == "local_api_disabled"


def test_selected_target_mismatch_is_structured_gate(tmp_path, monkeypatch):
    plugin = create_fake_zotero_plugin(tmp_path)
    zotero = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False)

    monkeypatch.setenv("FAKE_ZOTERO_TARGET", "My Library")
    result = zotero.selected_target(required_name="Paper Wiki")

    assert result["ok"] is False
    assert result["gate"] == "selected_target_mismatch"


def test_import_requires_explicit_adapter_approval(tmp_path):
    plugin = create_fake_zotero_plugin(tmp_path)
    zotero = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False)

    denied = zotero.import_bibtex(text="@article{x}", approved=False)
    approved = zotero.import_bibtex(text="@article{x}", approved=True)

    assert denied["ok"] is False
    assert denied["gate"] == "write_not_authorized"
    assert approved["ok"] is True
    assert approved["data"]["status"] == 200


def test_invalid_json_and_timeout_are_structured(tmp_path, monkeypatch):
    plugin = create_fake_zotero_plugin(tmp_path)
    zotero = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False, timeout_seconds=1)

    monkeypatch.setenv("FAKE_ZOTERO_MODE", "invalid_json")
    invalid = zotero.status()
    monkeypatch.setenv("FAKE_ZOTERO_MODE", "sleep")
    timed_out = zotero.status()

    assert invalid["gate"] == "zotero_invalid_json"
    assert timed_out["gate"] == "zotero_timeout"


def test_failure_diagnostics_are_redacted(tmp_path, monkeypatch):
    plugin = create_fake_zotero_plugin(tmp_path)
    zotero = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False)

    monkeypatch.setenv("FAKE_ZOTERO_MODE", "fail")
    result = zotero.inventory()
    serialized = str(result)

    assert result["ok"] is False
    assert result["gate"] == "connector_unavailable"
    assert "abc123" not in serialized
    assert "token=secret" not in serialized
    assert "<redacted" in serialized


def test_no_broad_recursive_search_for_extra_roots(tmp_path):
    plugin = tmp_path / "not-a-plugin-root"
    nested = plugin / "deep" / "skills" / "zotero" / "scripts"
    nested.mkdir(parents=True)
    (nested / "zotero.py").write_text("print('should not be found')", encoding="utf-8")

    candidates = adapter.collect_helper_candidates(extra_roots=[plugin], include_defaults=False)

    assert len(candidates) == 1
    assert candidates[0].path == plugin / adapter.HELPER_RELATIVE_PATH
    assert "deep" not in str(candidates[0].path)


def test_env_override_is_exact_helper_file(tmp_path, monkeypatch):
    plugin = create_fake_zotero_plugin(tmp_path)
    helper = plugin / adapter.HELPER_RELATIVE_PATH
    monkeypatch.setenv(adapter.HELPER_ENV, str(helper))

    resolution = adapter.discover_zotero_helper(include_defaults=False)

    assert resolution.helper is not None
    assert resolution.helper["path"] == str(helper.resolve())
