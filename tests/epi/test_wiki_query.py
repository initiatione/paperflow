import json
import sys

from epi.orchestrator import main
from epi.wiki_query import query_wiki, render_wiki_query


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
