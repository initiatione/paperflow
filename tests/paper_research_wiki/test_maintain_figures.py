import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "paper-wiki" / "scripts" / "maintain_figures.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("paper_wiki_maintain_figures", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repair_page_replaces_multi_figure_block_without_source_line_drift(tmp_path):
    module = _load_module()
    slug = "fixture-paper"
    vault = tmp_path / "vault"
    raw_root = vault / "_epi" / "raw" / slug
    images_dir = raw_root / "mineru" / "images"
    page = vault / "references" / "fixture.md"
    images_dir.mkdir(parents=True)
    page.parent.mkdir(parents=True)
    for name in (
        "fig-020a-controller-response.jpg",
        "fig-020b-controller-response.jpg",
        "fig-020c-controller-response.jpg",
    ):
        (images_dir / name).write_bytes(name.encode("utf-8"))
    (raw_root / "figure-index.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "status": "mapped",
                        "figure_id": "fig-020a",
                        "original_label": "Fig. 20(a)",
                        "normalized_path": "images/fig-020a-controller-response.jpg",
                    },
                    {
                        "status": "mapped",
                        "figure_id": "fig-020b",
                        "original_label": "Fig. 20(b)",
                        "normalized_path": "images/fig-020b-controller-response.jpg",
                    },
                    {
                        "status": "mapped",
                        "figure_id": "fig-020c",
                        "original_label": "Fig. 20(c)",
                        "normalized_path": "images/fig-020c-controller-response.jpg",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    page.write_text(
        "\n".join(
            [
                "---",
                "updated: 2026-06-01",
                "---",
                "",
                '<a id="F20"></a>',
                "**原文 Fig. 20.** Controller response evidence.",
                "<p>",
                f'<img src="../_epi/raw/{slug}/mineru/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg" alt="old" width="32%">',
                f'<img src="../_epi/raw/{slug}/mineru/images/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.jpg" alt="old" width="32%">',
                "</p>",
                "**Source:** old hash image evidence.",
                "",
                "Next paragraph.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    entries = module._figure_entries(raw_root)
    result = module.repair_page(
        page,
        vault=vault,
        slug=slug,
        raw_root=raw_root,
        entries_by_number=entries,
        dropped_formula_names=set(),
        execute=True,
    )

    text = page.read_text(encoding="utf-8")
    assert result["changed"] is True
    assert "updated:" in text
    assert text.count('width="32%"') == 3
    assert "fig-020a-controller-response.jpg" in text
    assert "fig-020b-controller-response.jpg" in text
    assert "fig-020c-controller-response.jpg" in text
    assert "**Source:** MinerU Markdown Fig. 20 caption；`figure-index.json` assets `fig-020a` 至 `fig-020c`。" in text
    assert text.index("</p>") < text.index("**Source:** MinerU Markdown Fig. 20")
    assert "Next paragraph." in text


def test_repair_page_does_not_change_updated_date_without_evidence_patch(tmp_path):
    module = _load_module()
    slug = "fixture-paper"
    vault = tmp_path / "vault"
    raw_root = vault / "_epi" / "raw" / slug
    page = vault / "concepts" / "fixture.md"
    raw_root.mkdir(parents=True)
    page.parent.mkdir(parents=True)
    page.write_text(
        "\n".join(
            [
                "---",
                "updated: 2026-06-01",
                "---",
                "",
                f"Source bundle: ../_epi/raw/{slug}/paper.pdf",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = page.read_text(encoding="utf-8")

    result = module.repair_page(
        page,
        vault=vault,
        slug=slug,
        raw_root=raw_root,
        entries_by_number={},
        dropped_formula_names=set(),
        execute=True,
    )

    assert result["changed"] is False
    assert page.read_text(encoding="utf-8") == before


def test_repair_page_handles_plain_figure_heading_with_old_hash_path(tmp_path):
    module = _load_module()
    slug = "fixture-paper"
    vault = tmp_path / "vault"
    raw_root = vault / "_epi" / "raw" / slug
    images_dir = raw_root / "mineru" / "images"
    page = vault / "references" / "fixture.md"
    images_dir.mkdir(parents=True)
    page.parent.mkdir(parents=True)
    (images_dir / "fig-004-algorithmic-structure.jpg").write_bytes(b"figure")
    (raw_root / "figure-index.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "status": "mapped",
                        "figure_id": "fig-004",
                        "original_label": "Fig. 4",
                        "old_path": "images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg",
                        "normalized_path": "images/fig-004-algorithmic-structure.jpg",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    page.write_text(
        "\n".join(
            [
                "---",
                "updated: 2026-06-01",
                "---",
                "",
                "原文 Fig. 4 展示算法结构。",
                f'<img src="../_epi/raw/{slug}/mineru/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg" alt="Evidence image">',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    entries = module._figure_entries(raw_root)
    result = module.repair_page(
        page,
        vault=vault,
        slug=slug,
        raw_root=raw_root,
        entries_by_number=entries,
        dropped_formula_names=set(),
        execute=True,
    )

    text = page.read_text(encoding="utf-8")
    assert result["changed"] is True
    assert "fig-004-algorithmic-structure.jpg" in text
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg" not in text


def test_repair_page_does_not_patch_foreign_raw_images_when_slug_is_mentioned(tmp_path):
    module = _load_module()
    slug = "fixture-paper"
    foreign_slug = "other-paper"
    vault = tmp_path / "vault"
    raw_root = vault / "_epi" / "raw" / slug
    images_dir = raw_root / "mineru" / "images"
    page = vault / "references" / "fixture.md"
    images_dir.mkdir(parents=True)
    page.parent.mkdir(parents=True)
    (images_dir / "fig-004-algorithmic-structure.jpg").write_bytes(b"figure")
    (raw_root / "figure-index.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "status": "mapped",
                        "figure_id": "fig-004",
                        "original_label": "Fig. 4",
                        "old_path": "images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg",
                        "normalized_path": "images/fig-004-algorithmic-structure.jpg",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    page.write_text(
        "\n".join(
            [
                "---",
                "updated: 2026-06-01",
                "---",
                "",
                f"This page mentions _epi/raw/{slug}/paper.pdf as background.",
                "",
                "原文 Fig. 4 展示另一个来源的图。",
                f'<img src="../_epi/raw/{foreign_slug}/mineru/images/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.jpg" alt="Foreign image">',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = page.read_text(encoding="utf-8")

    entries = module._figure_entries(raw_root)
    result = module.repair_page(
        page,
        vault=vault,
        slug=slug,
        raw_root=raw_root,
        entries_by_number=entries,
        dropped_formula_names=set(),
        execute=True,
    )

    assert result["changed"] is False
    assert page.read_text(encoding="utf-8") == before


def test_repair_page_replaces_stale_slug_image_path_without_figure_heading(tmp_path):
    module = _load_module()
    slug = "fixture-paper"
    vault = tmp_path / "vault"
    raw_root = vault / "_epi" / "raw" / slug
    images_dir = raw_root / "mineru" / "images"
    page = vault / "references" / "fixture.md"
    images_dir.mkdir(parents=True)
    page.parent.mkdir(parents=True)
    (images_dir / "fig-012-success-rate.jpg").write_bytes(b"figure")
    (raw_root / "figure-index.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "status": "mapped",
                        "figure_id": "fig-012",
                        "original_label": "Fig. 12",
                        "old_path": "images/cccccccccccccccccccccccccccccccc.jpg",
                        "normalized_path": "images/fig-012-success-rate.jpg",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    page.write_text(
        "\n".join(
            [
                "---",
                "updated: 2026-06-01",
                "---",
                "",
                "正文说明 Figure 12 的 success rate 变化。",
                f'<img src="../_epi/raw/{slug}/mineru/images/cccccccccccccccccccccccccccccccc.jpg" alt="Evidence image">',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    entries = module._figure_entries(raw_root)
    result = module.repair_page(
        page,
        vault=vault,
        slug=slug,
        raw_root=raw_root,
        entries_by_number=entries,
        dropped_formula_names=set(),
        execute=True,
    )

    text = page.read_text(encoding="utf-8")
    assert result["changed"] is True
    assert any(action["action"] == "replace_stale_image_path" for action in result["actions"])
    assert "fig-012-success-rate.jpg" in text
    assert "cccccccccccccccccccccccccccccccc.jpg" not in text


def test_repair_page_keeps_later_section_images_out_of_plain_figure_block(tmp_path):
    module = _load_module()
    slug = "fixture-paper"
    vault = tmp_path / "vault"
    raw_root = vault / "_epi" / "raw" / slug
    images_dir = raw_root / "mineru" / "images"
    page = vault / "references" / "fixture.md"
    images_dir.mkdir(parents=True)
    page.parent.mkdir(parents=True)
    (images_dir / "fig-008-task.jpg").write_bytes(b"fig8")
    (images_dir / "fig-012-success-rate.jpg").write_bytes(b"fig12")
    (raw_root / "figure-index.json").write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "status": "mapped",
                        "figure_id": "fig-008",
                        "original_label": "Fig. 8",
                        "old_path": "images/88888888888888888888888888888888.jpg",
                        "normalized_path": "images/fig-008-task.jpg",
                    },
                    {
                        "status": "mapped",
                        "figure_id": "fig-012",
                        "original_label": "Fig. 12",
                        "old_path": "images/12121212121212121212121212121212.jpg",
                        "normalized_path": "images/fig-012-success-rate.jpg",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    page.write_text(
        "\n".join(
            [
                "---",
                "updated: 2026-06-01",
                "---",
                "",
                "原文 Fig. 8 给出任务结构：",
                f'<img src="../_epi/raw/{slug}/mineru/images/88888888888888888888888888888888.jpg" alt="Fig 8">',
                "",
                "### Current strength robustness",
                "",
                "正文说明 Figure 12 的 success rate 变化。",
                f'<img src="../_epi/raw/{slug}/mineru/images/12121212121212121212121212121212.jpg" alt="Fig 12">',
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    entries = module._figure_entries(raw_root)
    result = module.repair_page(
        page,
        vault=vault,
        slug=slug,
        raw_root=raw_root,
        entries_by_number=entries,
        dropped_formula_names=set(),
        execute=True,
    )

    text = page.read_text(encoding="utf-8")
    assert result["changed"] is True
    assert "### Current strength robustness" in text
    assert "正文说明 Figure 12" in text
    assert "fig-008-task.jpg" in text
    assert "fig-012-success-rate.jpg" in text
    assert "12121212121212121212121212121212.jpg" not in text


def test_snapshot_formal_pages_writes_canonical_paper_source_snapshot_root(tmp_path):
    module = _load_module()
    vault = tmp_path / "vault"
    page = vault / "references" / "fixture.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Fixture with [[concepts/example]]\n", encoding="utf-8")

    snapshot = module._snapshot_formal_pages(vault, "snapshot-test", execute=True)

    assert snapshot == "_paper_source/meta/formal-page-snapshots/snapshot-test/"
    snapshot_text = (
        vault
        / "_paper_source"
        / "meta"
        / "formal-page-snapshots"
        / "snapshot-test"
        / "references"
        / "fixture.md"
    ).read_text(encoding="utf-8")
    assert "[[concepts/example]]" in snapshot_text


def test_refresh_sidecars_updates_canonical_paper_wiki_record_request(tmp_path):
    module = _load_module()
    slug = "fixture-paper"
    vault = tmp_path / "vault"
    raw_root = vault / "_paper_source" / "raw" / slug
    mineru_dir = raw_root / "mineru"
    images_dir = mineru_dir / "images"
    staging = vault / "_paper_source" / "staging" / "papers" / slug
    page = vault / "references" / "fixture.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)

    (mineru_dir / f"{slug}.md").write_text("# Fixture\n", encoding="utf-8")
    (images_dir / "fig-001-example.jpg").write_bytes(b"figure")
    (raw_root / "figure-index.json").write_text(json.dumps({"figures": []}), encoding="utf-8")
    (raw_root / "formula-index.json").write_text(json.dumps({"formulas": []}), encoding="utf-8")
    (raw_root / "asset-normalization-record.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    page.write_text(
        "\n".join(
            [
                "---",
                "updated: 2026-06-01",
                "---",
                "",
                "# Fixture",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    review_path = staging / "final-source-review.json"
    review_path.write_text(
        json.dumps(
            {
                "reviewed_artifacts": [
                    {"artifact": "mineru/images/*", "status": "reviewed", "files": [], "file_count": 0}
                ],
                "final_page_provenance": [
                    {
                        "relative_path": "references/fixture.md",
                        "sha256": "stale",
                        "source_grounded": True,
                    }
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
                    {
                        "relative_path": "references/fixture.md",
                        "sha256": "stale",
                    }
                ],
                "final_source_review": {
                    "path": str(review_path),
                    "sha256": "stale-review",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = module.refresh_sidecars(
        vault=vault,
        slug=slug,
        raw_root=raw_root,
        changed_pages=[page],
        snapshot="_paper_source/meta/formal-page-snapshots/test/",
        execute=True,
    )

    review = json.loads(review_path.read_text(encoding="utf-8"))
    request = json.loads(request_path.read_text(encoding="utf-8"))

    assert result["changed"] is True
    assert result["paper_wiki_record_request_changed"] is True
    assert result["legacy_prw_record_request_changed"] is False
    assert request["paper_wiki_task"]["route"] == "maintain_figures"
    assert request["paper_wiki_task"]["snapshot"] == "_paper_source/meta/formal-page-snapshots/test/"
    assert request["final_pages"][0]["sha256"] != "stale"
    assert request["final_source_review"]["sha256"] == result["final_source_review_sha256"]
    assert review["final_page_provenance"][0]["sha256"] != "stale"
