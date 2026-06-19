import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "plugins" / "paper-wiki" / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from paper_wiki.zotero_helper_adapter import ZoteroHelperAdapter, discover_zotero_helper
from zotero_helper_fixture import create_fake_zotero_plugin


def test_paper_wiki_adapter_discovers_official_helper_without_paper_source_runtime(tmp_path):
    plugin = create_fake_zotero_plugin(tmp_path)

    resolution = discover_zotero_helper(extra_roots=[plugin], include_defaults=False)

    assert resolution.helper is not None
    assert resolution.helper["source"] == "configured_root"


def test_paper_wiki_adapter_supports_read_and_write_wrappers(tmp_path):
    plugin = create_fake_zotero_plugin(tmp_path)
    zotero = ZoteroHelperAdapter(extra_roots=[plugin], include_defaults=False)

    selected = zotero.selected_target(required_name="Paper Wiki")
    imported = zotero.import_ris(text="TY  - JOUR", approved=True)

    assert selected["ok"] is True
    assert imported["ok"] is True
    assert imported["data"]["status"] == 200

