from __future__ import annotations

import argparse
import os
from pathlib import Path

from paper_source.cli_routes import COMMAND_ROUTES
from paper_source.rank_papers import SELECTION_POLICIES
from paper_source.run_index import RESEARCH_QUEUE_BUCKETS
from paper_source.stage_wiki import FAST_INGEST_MODE, INGEST_MODES


def _default_plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_vault() -> Path:
    configured = os.environ.get("PAPER_SOURCE_VAULT")
    if configured:
        return Path(configured)
    return Path.cwd() / "paper-research-wiki"


def _add_common_vault(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vault", type=Path, default=_default_vault())


def _add_ingest_mode(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=sorted(INGEST_MODES), default=FAST_INGEST_MODE)


def _add_selection_policy(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--selection-policy",
        choices=sorted(SELECTION_POLICIES),
        default="balanced_high_quality",
        help="Ranked-candidate selection policy; default keeps high-quality review candidates visible.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paper Source orchestrator.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--plugin-root", type=Path, default=_default_plugin_root())
    doctor.add_argument("--vault", type=Path, default=_default_vault())
    doctor.add_argument("--paper-search-command", default=None)
    doctor.add_argument("--mineru-command", default=None)
    doctor.add_argument("--open-setup", action="store_true")
    doctor.add_argument("--json", action="store_true")

    config_status = subparsers.add_parser("config-status")
    _add_common_vault(config_status)
    config_status.add_argument("--json", action="store_true")
    config_status.add_argument("--include-values", action="store_true")
    config_status.add_argument("--include-runtime", action="store_true")

    init_config = subparsers.add_parser("init-config")
    _add_common_vault(init_config)
    init_config.add_argument("--answers-json", type=Path, required=True)

    propose_config = subparsers.add_parser("propose-config-update")
    _add_common_vault(propose_config)
    propose_config.add_argument("--proposal-json", type=Path, required=True)
    propose_config.add_argument("--json", action="store_true")

    apply_config = subparsers.add_parser("apply-config-update")
    _add_common_vault(apply_config)
    apply_config.add_argument("--proposal-json", type=Path, required=True)
    apply_config.add_argument("--confirmed-by", required=True)

    config_recover = subparsers.add_parser("config-recover")
    _add_common_vault(config_recover)
    config_recover.add_argument("--backup-root", type=Path, default=None)
    config_recover.add_argument("--json", action="store_true")

    config_restore = subparsers.add_parser("config-restore")
    _add_common_vault(config_restore)
    config_restore.add_argument("--from", dest="source_path", type=Path, required=True)
    config_restore.add_argument("--confirmed-by", required=True)
    config_restore.add_argument("--json", action="store_true")

    research_brief = subparsers.add_parser("research-brief")
    research_brief_subparsers = research_brief.add_subparsers(dest="research_brief_action", required=True)

    research_brief_create = research_brief_subparsers.add_parser("create")
    research_brief_create.add_argument("--answers-json", type=Path, required=True)
    _add_common_vault(research_brief_create)
    research_brief_create.add_argument("--json", action="store_true")

    research_brief_validate = research_brief_subparsers.add_parser("validate")
    research_brief_validate.add_argument("--brief", type=Path, required=True)
    research_brief_validate.add_argument("--json", action="store_true")

    research_brief_list = research_brief_subparsers.add_parser("list")
    _add_common_vault(research_brief_list)
    research_brief_list.add_argument("--json", action="store_true")

    wiki_reset = subparsers.add_parser("wiki-reset")
    _add_common_vault(wiki_reset)
    wiki_reset.add_argument("--confirmed-by", default=None)
    wiki_reset.add_argument("--reset-config-confirmed-by", default=None)
    wiki_reset.add_argument("--backup-root", type=Path, default=None)
    wiki_reset.add_argument("--no-backup", action="store_true")
    wiki_reset.add_argument("--preview", action="store_true")
    wiki_reset.add_argument("--json", action="store_true")

    wiki_repair = subparsers.add_parser("wiki-repair")
    _add_common_vault(wiki_repair)
    wiki_repair.add_argument("--backup-root", type=Path, default=None)
    wiki_repair.add_argument("--restore-from", type=Path, default=None)
    wiki_repair.add_argument("--confirmed-by", default=None)
    wiki_repair.add_argument("--json", action="store_true")

    paper_source_migrate = subparsers.add_parser("paper-source-repository-migrate")
    _add_common_vault(paper_source_migrate)
    paper_source_migrate.add_argument("--preview", action="store_true")
    paper_source_migrate.add_argument("--json", action="store_true")

    paper_source_cleanup = subparsers.add_parser("paper-source-repository-cleanup")
    _add_common_vault(paper_source_cleanup)
    paper_source_cleanup.add_argument("--preview", action="store_true")
    paper_source_cleanup.add_argument("--json", action="store_true")

    dry_run = subparsers.add_parser("dry-run")
    dry_run_query_input = dry_run.add_mutually_exclusive_group(required=True)
    dry_run_query_input.add_argument("--query", default=None)
    dry_run_query_input.add_argument("--from-brief", type=Path, default=None)
    dry_run.add_argument("--allow-draft-brief", action="store_true")
    dry_run.add_argument("--max-results", type=int, default=None)
    _add_common_vault(dry_run)
    dry_run.add_argument("--plugin-root", type=Path, default=_default_plugin_root())
    dry_run.add_argument("--fixture", type=Path, default=None)
    dry_run.add_argument("--paper-search-command", default=None)
    dry_run.add_argument("--sources", default=None, help="Comma-separated paper-search sources for live discovery.")
    dry_run.add_argument("--no-query-plan", action="store_true")
    dry_run.add_argument(
        "--agent-query-plan-json",
        type=Path,
        default=None,
        help="Agent-compiled structured query plan JSON; scripts validate, record, and execute fields.",
    )
    dry_run.add_argument(
        "--query-variant",
        action="append",
        default=None,
        help="Agent-compiled academic search query. Repeat to run an explicit multi-query plan.",
    )
    dry_run.add_argument(
        "--domain-focus-term",
        action="append",
        default=None,
        help="Agent-compiled hard domain anchor for filtering. Repeat for synonyms/acronyms.",
    )
    dry_run.add_argument("--year-min", type=int, default=None, help="Reject candidates older than this year.")
    dry_run.add_argument(
        "--code-policy",
        choices=["ignore", "prefer", "require"],
        default=None,
        help="Request-level public-code policy: prefer ranks code higher; require rejects missing code_url.",
    )
    dry_run.add_argument(
        "--query-plan-domain",
        default="auto",
        choices=["auto", "profile"],
    )
    dry_run.add_argument("--query-plan-max-queries", type=int, default=6)
    _add_selection_policy(dry_run)
    dry_run.add_argument("--no-easyscholar", action="store_true")
    dry_run_resume_group = dry_run.add_mutually_exclusive_group()
    dry_run_resume_group.add_argument("--refresh", action="store_true")
    dry_run_resume_group.add_argument("--no-resume", action="store_true")
    dry_run.add_argument("--json", action="store_true")

    discover_papers = subparsers.add_parser("discover-papers")
    discover_papers_query_input = discover_papers.add_mutually_exclusive_group(required=True)
    discover_papers_query_input.add_argument("--query", default=None)
    discover_papers_query_input.add_argument("--from-brief", type=Path, default=None)
    discover_papers.add_argument("--allow-draft-brief", action="store_true")
    discover_papers.add_argument("--max-results", type=int, default=None)
    _add_common_vault(discover_papers)
    discover_papers.add_argument("--plugin-root", type=Path, default=_default_plugin_root())
    discover_papers.add_argument("--fixture", type=Path, default=None)
    discover_papers.add_argument("--paper-search-command", default=None)
    discover_papers.add_argument("--sources", default=None, help="Comma-separated paper-search sources for live discovery.")
    discover_papers.add_argument("--no-query-plan", action="store_true")
    discover_papers.add_argument("--agent-query-plan-json", type=Path, default=None)
    discover_papers.add_argument("--query-variant", action="append", default=None)
    discover_papers.add_argument("--domain-focus-term", action="append", default=None)
    discover_papers.add_argument("--year-min", type=int, default=None)
    discover_papers.add_argument("--code-policy", choices=["ignore", "prefer", "require"], default=None)
    discover_papers.add_argument("--query-plan-domain", default="auto", choices=["auto", "profile"])
    discover_papers.add_argument("--query-plan-max-queries", type=int, default=6)
    _add_selection_policy(discover_papers)
    discover_papers.add_argument("--no-easyscholar", action="store_true")
    discover_papers.add_argument("--refresh", action="store_true")
    discover_papers.add_argument("--max-auto-stage", type=int, default=3)
    discover_papers.add_argument("--review-survey-requested", action="store_true")
    discover_papers.add_argument("--no-auto-stage", dest="auto_stage", action="store_false", default=True)
    discover_papers.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    discover_papers.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    discover_papers.add_argument("--mineru-command", default=None)
    discover_papers.add_argument("--mineru-timeout", type=int, default=None)
    _add_ingest_mode(discover_papers)
    discover_papers.add_argument("--json", action="store_true")

    discover_to_handoff = subparsers.add_parser("discover-to-handoff")
    discover_query_input = discover_to_handoff.add_mutually_exclusive_group(required=True)
    discover_query_input.add_argument("--query", default=None)
    discover_query_input.add_argument("--from-brief", type=Path, default=None)
    discover_to_handoff.add_argument("--allow-draft-brief", action="store_true")
    discover_to_handoff.add_argument("--max-results", type=int, default=None)
    discover_to_handoff.add_argument("--max-papers", type=int, default=10)
    _add_common_vault(discover_to_handoff)
    discover_to_handoff.add_argument("--plugin-root", type=Path, default=_default_plugin_root())
    discover_to_handoff.add_argument("--fixture", type=Path, default=None)
    discover_to_handoff.add_argument("--paper-search-command", default=None)
    discover_to_handoff.add_argument("--sources", default=None, help="Comma-separated paper-search sources for live discovery.")
    discover_to_handoff.add_argument("--no-query-plan", action="store_true")
    discover_to_handoff.add_argument("--agent-query-plan-json", type=Path, default=None)
    discover_to_handoff.add_argument("--query-variant", action="append", default=None)
    discover_to_handoff.add_argument("--domain-focus-term", action="append", default=None)
    discover_to_handoff.add_argument("--year-min", type=int, default=None)
    discover_to_handoff.add_argument("--code-policy", choices=["ignore", "prefer", "require"], default=None)
    discover_to_handoff.add_argument("--query-plan-domain", default="auto", choices=["auto", "profile"])
    discover_to_handoff.add_argument("--query-plan-max-queries", type=int, default=6)
    _add_selection_policy(discover_to_handoff)
    discover_to_handoff.add_argument("--no-easyscholar", action="store_true")
    discover_to_handoff.add_argument("--refresh", action="store_true")
    discover_to_handoff.add_argument("--include-review-candidates", action="store_true")
    discover_to_handoff.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    discover_to_handoff.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    discover_to_handoff.add_argument("--mineru-command", default=None)
    discover_to_handoff.add_argument("--mineru-timeout", type=int, default=None)
    _add_ingest_mode(discover_to_handoff)
    discover_to_handoff.add_argument("--json", action="store_true")

    ingest_one = subparsers.add_parser("ingest-one")
    ingest_one.add_argument("--candidate", type=Path, required=True)
    ingest_one.add_argument("--pdf", type=Path, required=True)
    ingest_one.add_argument("--mineru-md", type=Path, required=True)
    ingest_one.add_argument("--mineru-tex", type=Path, default=None)
    ingest_one.add_argument("--mineru-images", type=Path, default=None)
    _add_common_vault(ingest_one)
    _add_ingest_mode(ingest_one)

    acquire = subparsers.add_parser("acquire-paper")
    acquire.add_argument("--candidate", type=Path, required=True)
    _add_common_vault(acquire)

    advance = subparsers.add_parser("advance-paper")
    advance.add_argument("--candidate", type=Path, required=True)
    _add_common_vault(advance)
    advance.add_argument("--mineru-command", default=None)
    advance.add_argument("--mineru-timeout", type=int, default=None)
    _add_ingest_mode(advance)

    advance_batch = subparsers.add_parser("advance-batch")
    advance_batch.add_argument("--candidates", type=Path, required=True)
    _add_common_vault(advance_batch)
    advance_batch.add_argument("--max-papers", type=int, default=None)
    advance_batch.add_argument("--mineru-command", default=None)
    advance_batch.add_argument("--mineru-timeout", type=int, default=None)
    _add_selection_policy(advance_batch)
    _add_ingest_mode(advance_batch)

    advance_ranked = subparsers.add_parser("advance-ranked")
    advance_ranked.add_argument("--run-id", required=True)
    _add_common_vault(advance_ranked)
    advance_ranked.add_argument("--max-papers", type=int, default=None)
    advance_ranked.add_argument("--mineru-command", default=None)
    advance_ranked.add_argument("--mineru-timeout", type=int, default=None)
    advance_ranked.add_argument("--include-review-candidates", action="store_true")
    _add_selection_policy(advance_ranked)
    _add_ingest_mode(advance_ranked)

    prepare_ranked = subparsers.add_parser("prepare-ranked")
    prepare_ranked.add_argument("--run-id", required=True)
    _add_common_vault(prepare_ranked)
    prepare_ranked.add_argument("--max-papers", type=int, default=1)
    prepare_ranked.add_argument("--mineru-command", default=None)
    prepare_ranked.add_argument("--mineru-timeout", type=int, default=None)
    prepare_ranked.add_argument("--include-review-candidates", action="store_true")
    prepare_ranked.add_argument("--skip-existing", action="store_true")
    _add_selection_policy(prepare_ranked)
    _add_ingest_mode(prepare_ranked)
    prepare_ranked.add_argument("--json", action="store_true")

    parse_paper = subparsers.add_parser("parse-paper")
    _add_common_vault(parse_paper)
    parse_paper.add_argument("--slug", required=True)
    parse_paper.add_argument("--mineru-command", default=None)
    parse_paper.add_argument("--mineru-timeout", type=int, default=None)

    normalize_assets = subparsers.add_parser("normalize-mineru-assets")
    _add_common_vault(normalize_assets)
    normalize_assets.add_argument("--slug", required=True)
    normalize_assets.add_argument("--execute", action="store_true")
    normalize_assets.add_argument("--json", action="store_true")

    redo_acquire = subparsers.add_parser("redo-acquire")
    _add_common_vault(redo_acquire)
    redo_acquire.add_argument("--slug", required=True)
    redo_acquire.add_argument("--pdf", type=Path, required=True)
    redo_acquire.add_argument("--reason", default="")

    redo_parse = subparsers.add_parser("redo-parse")
    _add_common_vault(redo_parse)
    redo_parse.add_argument("--slug", required=True)
    redo_parse.add_argument("--mineru-md", type=Path, required=True)
    redo_parse.add_argument("--mineru-tex", type=Path, default=None)
    redo_parse.add_argument("--mineru-images", type=Path, default=None)
    redo_parse.add_argument("--reason", default="")

    redo_read = subparsers.add_parser("redo-read")
    _add_common_vault(redo_read)
    redo_read.add_argument("--slug", required=True)
    redo_read.add_argument("--reason", default="")
    redo_read.add_argument("--from-revision-plan", action="store_true")
    redo_read.add_argument("--recritic", action="store_true")

    recritic = subparsers.add_parser("recritic")
    _add_common_vault(recritic)
    recritic.add_argument("--slug", required=True)
    recritic.add_argument("--reason", default="")

    zotero = subparsers.add_parser("zotero-sync")
    zotero.add_argument("--paper-root", type=Path, required=True)
    zotero.add_argument("--collection", default="Paper Source")
    zotero.add_argument("--enabled", action="store_true")
    zotero.add_argument("--item-key", default=None)

    feedback = subparsers.add_parser("record-feedback")
    _add_common_vault(feedback)
    feedback.add_argument("--type", required=True)
    feedback.add_argument("--target", required=True)
    feedback.add_argument("--message", required=True)
    feedback.add_argument("--source", default="human")

    evaluation_brief = subparsers.add_parser("evaluation-brief")
    evaluation_brief.add_argument("--target-asset", required=True)
    evaluation_brief.add_argument("--rationale", required=True)
    evaluation_brief.add_argument("--proposed-change-json", required=True)
    evaluation_brief.add_argument("--before-metrics-json", default=None)
    evaluation_brief.add_argument("--after-metrics-json", default=None)
    evaluation_brief.add_argument("--plugin-eval-json", type=Path, default=None)
    evaluation_brief.add_argument("--metric-pack-json", type=Path, default=None)
    evaluation_brief.add_argument("--benchmark-json", type=Path, default=None)
    evaluation_brief.add_argument("--evidence", action="append", default=[])
    evaluation_brief.add_argument("--reflection-type", default="OPTIMIZATION")
    evaluation_brief.add_argument("--evidence-type", default="plugin_eval_warning")
    evaluation_brief.add_argument("--brief-id", default=None)
    evaluation_brief.add_argument("--out-dir", type=Path, default=Path(".plugin-eval") / "improvement-briefs")
    evaluation_brief.add_argument("--json", action="store_true")

    propose = subparsers.add_parser("propose-evolution")
    _add_common_vault(propose)
    propose.add_argument("--reflection-type", required=True)
    propose.add_argument("--target-asset", required=True)
    propose.add_argument("--rationale", required=True)
    propose.add_argument("--proposed-change-json", required=True)
    propose.add_argument("--evidence", action="append", default=[])
    propose.add_argument("--evidence-type", default=None)
    propose.add_argument("--before-metrics-json", default=None)
    propose.add_argument("--acceptance-gates-json", default=None)
    propose.add_argument("--risk-level", default=None)

    activate = subparsers.add_parser("activate-evolution")
    _add_common_vault(activate)
    activate.add_argument("--proposal-id", required=True)
    activate.add_argument("--approved", action="store_true")
    activate.add_argument("--validation-result-json", default=None)

    evolution_query = subparsers.add_parser("evolution-query")
    _add_common_vault(evolution_query)
    evolution_query.add_argument("--status", default=None)
    evolution_query.add_argument("--limit", type=int, default=20)
    evolution_query.add_argument("--json", action="store_true")

    runs_query = subparsers.add_parser("runs-query")
    _add_common_vault(runs_query)
    runs_query_group = runs_query.add_mutually_exclusive_group()
    runs_query_group.add_argument("--failed", action="store_true")
    runs_query_group.add_argument("--human-gate", action="store_true")
    runs_query_group.add_argument("--latest-success")
    runs_query.add_argument("--workflow", default=None)
    runs_query.add_argument("--limit", type=int, default=10)
    runs_query.add_argument("--json", action="store_true")

    report = subparsers.add_parser("report")
    _add_common_vault(report)
    report.add_argument("--run-id", required=True)
    report.add_argument("--json", action="store_true")

    run_lifecycle = subparsers.add_parser("run-lifecycle")
    _add_common_vault(run_lifecycle)
    run_lifecycle.add_argument("--keep-latest", type=int, default=15)
    run_lifecycle.add_argument("--keep-per-workflow", type=int, default=2)
    run_lifecycle.add_argument("--max-age-days", type=int, default=None)
    run_lifecycle.add_argument("--apply", action="store_true")
    run_lifecycle.add_argument("--json", action="store_true")

    research_queue = subparsers.add_parser("research-queue")
    _add_common_vault(research_queue)
    research_queue.add_argument("--bucket", choices=RESEARCH_QUEUE_BUCKETS, default=None)
    research_queue.add_argument("--limit", type=int, default=10)
    research_queue.add_argument("--actions", action="store_true")
    research_queue.add_argument("--json", action="store_true")

    wiki_query = subparsers.add_parser("wiki-query")
    _add_common_vault(wiki_query)
    wiki_query.add_argument("--consensus", default=None)
    wiki_query.add_argument("--role", default=None)
    wiki_query.add_argument("--verdict", default=None)
    wiki_query.add_argument("--warning-reviewer", default=None)
    wiki_query.add_argument("--blocking-lens", default=None)
    wiki_query.add_argument("--limit", type=int, default=20)
    wiki_query.add_argument("--json", action="store_true")

    wiki_ask = subparsers.add_parser("wiki-ask")
    _add_common_vault(wiki_ask)
    wiki_ask.add_argument("--question", required=True)
    wiki_ask.add_argument("--limit", type=int, default=8)
    wiki_ask.add_argument("--max-hops", type=int, default=1)
    wiki_ask.add_argument("--json", action="store_true")

    wiki_ingest_handoff = subparsers.add_parser("wiki-ingest-handoff")
    _add_common_vault(wiki_ingest_handoff)
    wiki_ingest_handoff.add_argument("--slug", required=True)
    wiki_ingest_handoff.add_argument("--json", action="store_true")

    wiki_ingest_trigger = subparsers.add_parser("wiki-ingest-trigger")
    _add_common_vault(wiki_ingest_trigger)
    wiki_ingest_trigger.add_argument("--slug", required=True)
    wiki_ingest_trigger.add_argument("--json", action="store_true")

    record_human_approval = subparsers.add_parser("record-human-approval")
    _add_common_vault(record_human_approval)
    record_human_approval.add_argument("--slug", required=True)
    record_human_approval.add_argument("--approved-by", required=True)
    record_human_approval.add_argument("--scope", required=True)
    record_human_approval.add_argument("--notes", default=None)
    record_human_approval.add_argument("--automation-mode", default=None)
    record_human_approval.add_argument("--automation-task-id", default=None)
    record_human_approval.add_argument("--automation-task-source", default=None)
    record_human_approval.add_argument("--automation-authorization", default=None)
    record_human_approval.add_argument("--json", action="store_true")

    record_wiki_ingest = subparsers.add_parser("record-wiki-ingest")
    _add_common_vault(record_wiki_ingest)
    record_wiki_ingest.add_argument("--slug", default=None)
    record_wiki_ingest.add_argument("--page", action="append", default=None)
    record_wiki_ingest.add_argument("--approved-by", default=None)
    record_wiki_ingest.add_argument("--notes", default=None)
    record_wiki_ingest.add_argument("--source-review", default=None)
    record_wiki_ingest.add_argument("--from-paper-wiki-request", dest="from_paper_wiki_request", type=Path, default=None)
    record_wiki_ingest.add_argument("--json", action="store_true")

    paper_gate = subparsers.add_parser("paper-gate")
    _add_common_vault(paper_gate)
    paper_gate.add_argument("--slug", required=True)
    paper_gate.add_argument("--json", action="store_true")

    parser_commands = set(subparsers.choices)
    missing_routes = parser_commands - set(COMMAND_ROUTES)
    extra_routes = set(COMMAND_ROUTES) - parser_commands
    if missing_routes or extra_routes:
        raise RuntimeError(
            "Paper Source CLI parser/routes drift: "
            f"missing_routes={sorted(missing_routes)} extra_routes={sorted(extra_routes)}"
        )
    return parser
