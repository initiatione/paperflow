from pathlib import Path

import pytest

from paper_source import config as config_module
from paper_source.config import apply_config_update, init_config, load_config, propose_config_update


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
        "    - openalex\n"
        "ranking:\n"
        "  quality_evidence_terms:\n"
        "    benchmark_terms:\n"
        "      - field endpoint\n"
        "    reproducibility_terms:\n"
        "      - shared protocol\n"
        "    paper_type_rules:\n"
        "      field-study:\n"
        "        - field endpoint\n",
        encoding="utf-8",
    )

    config = load_config(plugin_root=plugin_root, vault_path=tmp_path / "vault", max_results=None)

    assert config.plugin_root == plugin_root
    assert config.vault_path == tmp_path / "vault"
    assert config.runs_dir == tmp_path / "vault" / "_paper_source" / "runs"
    assert config.max_results == 12
    assert config.profile == "robotics_ai_control"
    assert config.positive_keywords == ["humanoid", "sim2real"]
    assert config.negative_keywords == ["biomedical trial"]
    assert config.venue_prior == ["ICRA", "Science Robotics"]
    assert config.paper_search_command == "paper-search"
    assert config.paper_search_sources == ["arxiv", "semantic", "openalex"]
    assert config.quality_evidence_terms == {
        "benchmark_terms": ["field endpoint"],
        "reproducibility_terms": ["shared protocol"],
        "paper_type_rules": {"field-study": ["field endpoint"]},
    }


def test_simple_yaml_single_quotes_unescape_yaml_quote_pairs():
    assert config_module._parse_yaml_scalar("'it''s'") == "it's"


def test_config_init_and_update_surface_unknown_top_level_keys(tmp_path):
    vault = tmp_path / "vault"

    initialized = init_config(
        vault,
        {
            "profile": "robotics",
            "postive_keywords": ["typo"],
            "configured_by": "tester",
        },
    )

    assert initialized["unknown_keys"] == ["postive_keywords"]

    proposal = propose_config_update(
        vault,
        {
            "changes": {
                "domains": ["robotics"],
                "postive_keywords": ["still typo"],
            }
        },
    )
    assert proposal["unknown_keys"] == ["postive_keywords"]

    applied = apply_config_update(
        vault,
        {
            "changes": {
                "positive_keywords": ["control"],
                "postive_keywords": ["ignored typo"],
            }
        },
        confirmed_by="tester",
    )
    assert applied["unknown_keys"] == ["postive_keywords"]
    assert applied["config"]["positive_keywords"] == ["control"]


def test_load_config_defaults_keep_doi_lookup_out_of_broad_sources(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text("profile: general_academic_research\n", encoding="utf-8")

    config = load_config(plugin_root=plugin_root, vault_path=tmp_path / "vault", max_results=None)

    assert config.paper_search_sources == ["arxiv", "semantic", "openalex", "crossref"]
    assert "unpaywall" not in config.paper_search_sources


def test_load_config_defaults_grok_search_to_targeted_gap_domains(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text("profile: general_academic_research\n", encoding="utf-8")

    config = load_config(plugin_root=plugin_root, vault_path=tmp_path / "vault", max_results=None)

    assert config.grok_search.mode == "targeted"
    assert config.grok_search.targeted_query_budget == 5
    assert config.grok_search.parallel_query_budget == 8
    assert config.grok_search.grok_only_recommendation_cap == 5
    assert "ieeexplore.ieee.org" in config.grok_search.academic_domains.effective_domains
    assert "arxiv.org" not in config.grok_search.academic_domains.effective_domains


def test_load_config_grok_domains_append_and_override(tmp_path):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: general_academic_research\n"
        "grok_search:\n"
        "  mode: parallel\n"
        "  targeted_query_budget: 3\n"
        "  parallel_query_budget: 15\n"
        "  grok_only_recommendation_cap: 0\n"
        "  academic_domains:\n"
        "    mode: override\n"
        "    domains:\n"
        "      - https://ieeexplore.ieee.org/document/123\n"
        "      - custom.example.org\n",
        encoding="utf-8",
    )

    config = load_config(plugin_root=plugin_root, vault_path=tmp_path / "vault", max_results=None)

    assert config.grok_search.mode == "parallel"
    assert config.grok_search.targeted_query_budget == 3
    assert config.grok_search.parallel_query_budget == 15
    assert config.grok_search.grok_only_recommendation_cap == 0
    assert config.grok_search.academic_domains.domains == ["ieeexplore.ieee.org", "custom.example.org"]
    assert config.grok_search.academic_domains.effective_domains == ["ieeexplore.ieee.org", "custom.example.org"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", "loud"),
        ("targeted_query_budget", 2),
        ("targeted_query_budget", 11),
        ("parallel_query_budget", 4),
        ("parallel_query_budget", 16),
        ("grok_only_recommendation_cap", 6),
    ],
)
def test_load_config_rejects_invalid_grok_search_values(tmp_path, field, value):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: general_academic_research\n"
        "grok_search:\n"
        f"  {field}: {value}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_config(plugin_root=plugin_root, vault_path=tmp_path / "vault", max_results=None)
