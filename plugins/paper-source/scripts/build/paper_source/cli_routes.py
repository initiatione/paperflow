from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Callable


Handler = Callable[[argparse.Namespace], int]

HANDLER_NAMES: dict[str, str] = {
    "doctor": "_handle_doctor",
    "config-status": "_handle_config_status",
    "init-config": "_handle_init_config",
    "propose-config-update": "_handle_propose_config_update",
    "apply-config-update": "_handle_apply_config_update",
    "config-recover": "_handle_config_recover",
    "config-restore": "_handle_config_restore",
    "research-brief": "_handle_research_brief",
    "wiki-reset": "_handle_wiki_reset",
    "wiki-repair": "_handle_wiki_repair",
    "paper-source-repository-migrate": "_handle_paper_source_repository_migrate",
    "paper-source-repository-cleanup": "_handle_paper_source_repository_cleanup",
    "dry-run": "_handle_dry_run",
    "discover-to-handoff": "_handle_discover_to_handoff",
    "ingest-one": "_handle_ingest_one",
    "acquire-paper": "_handle_acquire_paper",
    "advance-paper": "_handle_advance_paper",
    "advance-batch": "_handle_advance_batch",
    "advance-ranked": "_handle_advance_ranked",
    "prepare-ranked": "_handle_prepare_ranked",
    "parse-paper": "_handle_parse_paper",
    "normalize-mineru-assets": "_handle_normalize_mineru_assets",
    "promote-to-wiki": "_handle_promote_to_wiki",
    "rollback-promotion": "_handle_rollback_promotion",
    "redo-acquire": "_handle_redo_acquire",
    "redo-parse": "_handle_redo_parse",
    "redo-read": "_handle_redo_read",
    "recritic": "_handle_recritic",
    "zotero-sync": "_handle_zotero_sync",
    "record-feedback": "_handle_record_feedback",
    "evaluation-brief": "_handle_evaluation_brief",
    "propose-evolution": "_handle_propose_evolution",
    "activate-evolution": "_handle_activate_evolution",
    "evolution-query": "_handle_evolution_query",
    "runs-query": "_handle_runs_query",
    "report": "_handle_report",
    "run-lifecycle": "_handle_run_lifecycle",
    "research-queue": "_handle_research_queue",
    "wiki-query": "_handle_wiki_query",
    "wiki-ask": "_handle_wiki_ask",
    "wiki-ingest-handoff": "_handle_wiki_ingest_handoff",
    "wiki-ingest-trigger": "_handle_wiki_ingest_trigger",
    "record-human-approval": "_handle_record_human_approval",
    "record-wiki-ingest": "_handle_record_wiki_ingest",
    "paper-gate": "_handle_paper_gate",
}

COMMAND_ROUTES: tuple[str, ...] = tuple(HANDLER_NAMES)


def bind_handlers(namespace: Mapping[str, object]) -> dict[str, Handler]:
    handlers: dict[str, Handler] = {}
    for command, handler_name in HANDLER_NAMES.items():
        handler = namespace[handler_name]
        if not callable(handler):
            raise TypeError(f"{handler_name} must be callable")
        handlers[command] = handler
    return handlers


def dispatch(args: argparse.Namespace, handlers: Mapping[str, Handler]) -> int:
    return handlers[args.command](args)
