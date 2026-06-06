from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_marketplace_manifests_expose_epi_and_prw():
    for rel in [".agents/plugins/marketplace.json", "marketplace.json"]:
        payload = _load(ROOT / rel)
        plugin_names = [plugin["name"] for plugin in payload["plugins"]]

        assert plugin_names == ["epi", "prw"]
        assert "mineru-paper-parser" not in plugin_names


def test_readme_frames_mineru_as_internal_helper():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "not as a separate marketplace plugin" in text
