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
    "config-recover": "_handle_table_driven",
    "config-restore": "_handle_table_driven",
    "research-brief": "_handle_research_brief",
    "wiki-reset": "_handle_table_driven",
    "wiki-repair": "_handle_wiki_repair",
    "paper-source-repository-migrate": "_handle_table_driven",
    "paper-source-repository-cleanup": "_handle_table_driven",
    "dry-run": "_handle_dry_run",
    "discover-papers": "_handle_discover_papers",
    "discover-to-handoff": "_handle_discover_to_handoff",
    "ingest-one": "_handle_table_driven",
    "acquire-paper": "_handle_table_driven",
    "advance-paper": "_handle_table_driven",
    "advance-batch": "_handle_table_driven",
    "advance-ranked": "_handle_table_driven",
    "prepare-ranked": "_handle_prepare_ranked",
    "parse-paper": "_handle_table_driven",
    "normalize-mineru-assets": "_handle_normalize_mineru_assets",
    "redo-acquire": "_handle_redo_acquire",
    "redo-parse": "_handle_redo_parse",
    "redo-read": "_handle_redo_read",
    "recritic": "_handle_recritic",
    "zotero-sync": "_handle_table_driven",
    "record-feedback": "_handle_table_driven",
    "evaluation-brief": "_handle_evaluation_brief",
    "discovery-benchmark": "_handle_discovery_benchmark",
    "propose-evolution": "_handle_table_driven",
    "activate-evolution": "_handle_table_driven",
    "evolution-query": "_handle_table_driven",
    "runs-query": "_handle_table_driven",
    "report": "_handle_table_driven",
    "run-lifecycle": "_handle_table_driven",
    "research-queue": "_handle_table_driven",
    "wiki-query": "_handle_table_driven",
    "wiki-ask": "_handle_table_driven",
    "wiki-ingest-handoff": "_handle_table_driven",
    "wiki-ingest-trigger": "_handle_table_driven",
    "record-human-approval": "_handle_table_driven",
    "record-wiki-ingest": "_handle_table_driven",
    "paper-gate": "_handle_table_driven",
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
