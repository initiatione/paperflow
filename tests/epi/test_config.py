from pathlib import Path

from epi.config import load_config


def test_load_config_uses_relative_defaults(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "positive_keywords:\n"
        "  - humanoid\n"
        "  - sim2real\n"
        "negative_keywords:\n"
        "  - biomedical trial\n"
        "venue_prior:\n"
        "  - ICRA\n"
        "  - Science Robotics\n"
        "budget:\n"
        "  max_results: 12\n"
        "paper_search:\n"
        "  command: paper-search\n"
        "  sources:\n"
        "    - arxiv\n"
        "    - semantic\n"
        "    - openalex\n",
        encoding="utf-8",
    )

    config = load_config(plugin_root=plugin_root, vault_path=tmp_path / "vault", max_results=None)

    assert config.plugin_root == plugin_root
    assert config.vault_path == tmp_path / "vault"
    assert config.runs_dir == tmp_path / "vault" / "_epi" / "runs"
    assert config.max_results == 12
    assert config.profile == "robotics_ai_control"
    assert config.positive_keywords == ["humanoid", "sim2real"]
    assert config.negative_keywords == ["biomedical trial"]
    assert config.venue_prior == ["ICRA", "Science Robotics"]
    assert config.paper_search_command == "paper-search"
    assert config.paper_search_sources == ["arxiv", "semantic", "openalex"]
