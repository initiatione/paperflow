import json
import sys

from epi.orchestrator import main
from epi.wiki_query import ask_wiki, query_wiki, render_wiki_ask, render_wiki_query


def _write_manifest(vault, papers):
    vault.mkdir(parents=True, exist_ok=True)
    (vault / ".manifest.json").write_text(
        json.dumps(
            {
                "vault_type": "academic-paper-research",
                "papers": papers,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_formal_page(vault, relative_path, title, body, *, aliases=None, tags=None, sources=None):
    path = vault / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    aliases = aliases or []
    tags = tags or []
    if sources is None:
        sources = ['"[[_epi/raw/example/paper.pdf|原论文 PDF]]"']
    path.write_text(
        "\n".join(
            [
                "---",
                f'title: "{title}"',
                "aliases:",
                *[f'  - "{alias}"' for alias in aliases],
                "tags:",
                *[f'  - "{tag}"' for tag in tags],
                "sources:",
                *[f"  - {source}" for source in sources],
                "---",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _paper(slug, *, consensus, role_verdicts, warnings=None, blocking=None):
    return {
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "promotion_status": "promoted",
        "compiled_reference": f"references/{slug}.md",
        "research_decision": {
            "recommendation": "stage-for-promotion-review" if consensus == "approve-for-staging" else "revise-reader",
            "next_action": "stage" if consensus == "approve-for-staging" else "revise-reader",
            "panel_consensus": consensus,
            "blocking_lenses": blocking or [],
            "warning_reviewers": warnings or [],
            "role_verdicts": role_verdicts,
        },
    }


def _run_orchestrator_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def test_ask_wiki_uses_formal_graph_backlinks_colinks_and_reports_correction_candidates(tmp_path):
    vault = tmp_path / "vault"
    raw_root = vault / "_epi" / "raw" / "example"
    (raw_root / "mineru" / "images").mkdir(parents=True, exist_ok=True)
    (raw_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (raw_root / "metadata.json").write_text('{"title": "fixture"}\n', encoding="utf-8")
    (raw_root / "mineru" / "example.md").write_text("mineru markdown\n", encoding="utf-8")
    (raw_root / "mineru" / "paper.tex").write_text("tex\n", encoding="utf-8")
    _write_formal_page(
        vault,
        "references/auv-adrc-strong-current.md",
        "AUV ADRC Strong Current",
        (
            "AUV attitude control under strong current disturbance uses "
            "[[Disturbance Observer]] and [[Robust Control Baseline]]. "
            "This page also references [[Missing Evidence Node]] and "
            "[[_epi/raw/example/paper.pdf|source PDF]]."
        ),
        aliases=["AUV ADRC Strong Current"],
        tags=["auv", "attitude-control"],
    )
    _write_formal_page(
        vault,
        "references/auv-ai-residual-strong-current.md",
        "AUV AI Residual Strong Current",
        (
            "AI residual learning for AUV strong current control should stay "
            "connected to [[Disturbance Observer]] before claiming full autonomy."
        ),
        aliases=["AUV AI Residual Strong Current"],
        tags=["auv", "ai-control"],
    )
    _write_formal_page(
        vault,
        "concepts/disturbance-observer.md",
        "Disturbance Observer",
        "Observer page for estimating external disturbance forces.",
        aliases=["Disturbance Observer"],
    )
    _write_formal_page(
        vault,
        "concepts/robust-control-baseline.md",
        "Robust Control Baseline",
        "Sliding mode, ADRC, and MPC baseline comparison.",
        aliases=["Robust Control Baseline"],
    )
    _write_formal_page(
        vault,
        "synthesis/first-step-auv-research-plan.md",
        "First Step AUV Research Plan",
        (
            "The first research step should compare [[AUV ADRC Strong Current]] "
            "with [[AUV AI Residual Strong Current]]."
        ),
        aliases=["First Step AUV Research Plan"],
    )
    (vault / "log.md").write_text("do not change this log\n", encoding="utf-8")

    result = ask_wiki(
        vault,
        question="AUV strong current attitude control with AI algorithm first research step",
        limit=8,
    )

    assert result["mode"] == "read-only"
    assert result["write_performed"] is False
    assert result["retrieval"]["primary"] == "formal_graph"
    assert result["retrieval"]["source_evidence"]["root"] == "_epi/raw"
    assert result["retrieval"]["source_evidence"]["formal_graph_node"] is False
    assert result["retrieval"]["qmd"]["role"] == "optional_accelerator"

    pages = {page["path"]: page for page in result["pages"]}
    assert "references/auv-adrc-strong-current.md" in pages
    assert "concepts/disturbance-observer.md" in pages
    assert "synthesis/first-step-auv-research-plan.md" in pages
    assert "outlink" in pages["concepts/disturbance-observer.md"]["reasons"]
    assert "co-linked" in pages["concepts/disturbance-observer.md"]["reasons"]
    assert "backlink" in pages["synthesis/first-step-auv-research-plan.md"]["reasons"]
    source_evidence = pages["references/auv-adrc-strong-current.md"]["source_evidence"][0]
    assert source_evidence["path"] == "_epi/raw/example/paper.pdf"
    assert source_evidence["exists"] is True
    assert source_evidence["formal_graph_node"] is False
    assert source_evidence["artifacts"]["mineru_markdown"] is True

    assert any(
        candidate["kind"] == "broken_wikilink" and candidate["target"] == "Missing Evidence Node"
        for candidate in result["correction_candidates"]
    )
    assert not any(
        candidate["kind"] == "forbidden_internal_graph_link"
        and candidate["target"] == "_epi/raw/example/paper.pdf"
        for candidate in result["correction_candidates"]
    )
    assert (vault / "log.md").read_text(encoding="utf-8") == "do not change this log\n"


def test_render_wiki_ask_labels_evidence_synthesis_inference_uncertainty_and_correction_loop(tmp_path):
    vault = tmp_path / "vault"
    _write_formal_page(
        vault,
        "references/auv-adrc-strong-current.md",
        "AUV ADRC Strong Current",
        "AUV strong current attitude control uses [[Missing Evidence Node]].",
        aliases=["AUV ADRC Strong Current"],
    )

    output = render_wiki_ask(
        ask_wiki(
            vault,
            question="AUV strong current attitude control with AI algorithm first research step",
            limit=5,
        )
    )

    for label in ["【Wiki 证据】", "【综合判断】", "【推断】", "【边界/不确定】"]:
        assert label in output
    assert "## 使用的 Wiki 图谱" in output
    assert "## 回答" in output
    assert "formal graph 的主要锚点" in output
    assert "基于当前图谱，可把第一步收敛" in output
    assert "## 发现的 Wiki 问题 / 纠错候选" in output
    assert "Missing Evidence Node" in output
    assert "是否需要我根据这些纠错候选继续修复" in output
    assert "read-only" in output


def test_ask_wiki_marks_alias_and_tag_seed_matches(tmp_path):
    vault = tmp_path / "vault"
    _write_formal_page(
        vault,
        "concepts/method-registry.md",
        "Method Registry",
        "A neutral method registry page.",
        aliases=["强扰流姿态控制"],
        tags=["水下机器人"],
        sources=[],
    )

    result = ask_wiki(
        vault,
        question="强扰流姿态控制 水下机器人",
        limit=5,
    )

    page = result["pages"][0]
    assert page["path"] == "concepts/method-registry.md"
    assert "alias" in page["reasons"]
    assert "tag" in page["reasons"]


def test_ask_wiki_retrieves_chinese_research_questions_without_exact_phrase_match(tmp_path):
    vault = tmp_path / "vault"
    _write_formal_page(
        vault,
        "concepts/strong-disturbance-attitude-control.md",
        "强扰流姿态控制",
        "强扰流、姿态、控制是水下航行器稳定性问题中的三个核心关键词。",
        aliases=["扰流姿态控制"],
        tags=["水下机器人", "姿态控制"],
    )

    result = ask_wiki(
        vault,
        question="我想研究水下航行器在强扰流下的姿态控制问题，第一步如何开始？",
        limit=5,
    )

    pages = {page["path"]: page for page in result["pages"]}
    assert "concepts/strong-disturbance-attitude-control.md" in pages
    assert "direct" in pages["concepts/strong-disturbance-attitude-control.md"]["reasons"]


def test_query_wiki_filters_promoted_papers_by_consensus_role_and_warning(tmp_path):
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        [
            _paper(
                "strong-paper",
                consensus="approve-for-staging",
                role_verdicts={
                    "nature-sci-editor": "pass",
                    "peer-reviewer": "pass",
                    "senior-domain-researcher": "pass",
                },
                warnings=["paper-quality-critic"],
            ),
            _paper(
                "risky-paper",
                consensus="revise-before-staging",
                role_verdicts={
                    "nature-sci-editor": "pass",
                    "peer-reviewer": "fail",
                    "senior-domain-researcher": "pass",
                },
                blocking=["peer-reviewer"],
            ),
            {
                "slug": "draft-paper",
                "title": "Draft Paper",
                "promotion_status": "staged",
            },
        ],
    )

    result = query_wiki(
        vault,
        consensus="approve-for-staging",
        role="peer-reviewer",
        verdict="pass",
        warning_reviewer="paper-quality-critic",
    )

    assert result["summary"] == {"matched_count": 1, "total_promoted_count": 2}
    assert [paper["slug"] for paper in result["papers"]] == ["strong-paper"]
    assert result["papers"][0]["decision"]["panel_consensus"] == "approve-for-staging"
    assert result["papers"][0]["role_verdicts"]["peer-reviewer"] == "pass"


def test_render_wiki_query_shows_operational_research_queue_fields(tmp_path):
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        [
            _paper(
                "risky-paper",
                consensus="revise-before-staging",
                role_verdicts={
                    "nature-sci-editor": "pass",
                    "peer-reviewer": "fail",
                    "senior-domain-researcher": "pass",
                },
                blocking=["peer-reviewer"],
            )
        ],
    )

    output = render_wiki_query(
        query_wiki(
            vault,
            consensus="revise-before-staging",
            blocking_lens="peer-reviewer",
        )
    )

    assert "EPI Wiki Query" in output
    assert "risky-paper" in output
    assert "decision: revise-before-staging" in output
    assert "roles: editor=pass, reviewer=fail, domain=pass" in output
    assert "blocking: peer-reviewer" in output


def test_wiki_query_cli_filters_manifest_by_peer_reviewer_failure(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        [
            _paper(
                "accepted-paper",
                consensus="approve-for-staging",
                role_verdicts={
                    "nature-sci-editor": "pass",
                    "peer-reviewer": "pass",
                    "senior-domain-researcher": "pass",
                },
            ),
            _paper(
                "reviewer-risk",
                consensus="revise-before-staging",
                role_verdicts={
                    "nature-sci-editor": "pass",
                    "peer-reviewer": "fail",
                    "senior-domain-researcher": "pass",
                },
                blocking=["peer-reviewer"],
            ),
        ],
    )

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "wiki-query",
        "--vault",
        str(vault),
        "--role",
        "peer-reviewer",
        "--verdict",
        "fail",
    )

    assert exit_code == 0
    assert "reviewer-risk" in output
    assert "accepted-paper" not in output
    assert "roles: editor=pass, reviewer=fail, domain=pass" in output
