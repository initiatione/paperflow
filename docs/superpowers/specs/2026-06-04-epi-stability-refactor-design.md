# EPI Stability Refactor Design

## Goal

Make the EPI plugin produce stable source-first wiki handoffs after real vault use exposed raw bundle completeness, final-page language, graph visibility, final-source-review, run index fragility, and oversized workflow scripts.

## Architecture

Split stability and workflow responsibilities out of the long orchestration files:

- `source_bundle_audit.py` owns raw paper source bundle completeness checks.
- `wiki_language.py` owns formal wiki language policy checks.
- `graph_visibility.py` owns Obsidian graph search filter construction and repair.
- `wiki_handoff_contracts.py` owns wiki handoff policy, final-source-review contracts, deposition task payloads, and brief construction currently embedded in `stage_wiki.py`.
- `cli_routes.py` owns argparse command registration and dispatch wiring currently embedded in `cli.py`.
- `wiki_record_workflows.py` owns human approval and wiki-ingest record orchestration currently embedded in `orchestrator.py`.
- `run_index.py` keeps the run dashboard but uses the shared atomic JSON writer.

Existing workflow files should call these focused modules instead of accumulating more inline checks. `stage_wiki.py`, `cli.py`, and `orchestrator.py` become thin routers or compatibility facades for their large subdomains. `paper_gate.py` blocks wiki handoff when the raw source bundle on disk is incomplete. `wiki_ingest_record.py` blocks English-only formal pages and requires a final-source-review language-policy record. `wiki_init.py` delegates graph filter generation and repair to `graph_visibility.py`.

## Requirements

- Raw source bundle audit must classify complete and incomplete `_epi/raw/papers/<slug>` directories with exact missing artifacts.
- Agent-mediated wiki handoff must fail before final deposition if source files are missing on disk, not only when the brief omits artifact labels.
- Formal wiki pages default to Chinese body prose; English remains allowed for paper titles, terms, abbreviations, evidence fields, paths, code, and math.
- `final-source-review.json` must record language-policy review alongside formal content quality.
- Obsidian graph filter must keep only `index.md` plus the seven formal page families and repair over-escaped legacy filters.
- Run index machine JSON must be written through the repo atomic writer.
- `orchestrator.py`, `stage_wiki.py`, and `cli.py` must stop being the only home for large route/workflow logic; new workflow code belongs in focused modules with narrow ownership.
- EPI skills must state the rule that future features should add focused workflow modules rather than growing these router files.
- EPI handoff artifacts must carry a clean-worker delegation policy: independent subtasks should go to fresh-context workers, workers should exit after writing bounded outputs, and the main agent should review final artifacts instead of importing long intermediate context.
- EPI plugin version must be bumped after implementation and docs/skills must describe the new workflow contract.

## Validation

Focused tests first:

- `tests/epi/test_source_bundle_audit.py`
- `tests/epi/test_paper_gate.py`
- `tests/epi/test_wiki_ingest_record.py`
- `tests/epi/test_wiki_init.py`
- `tests/epi/test_run_index_dashboard.py`
- `tests/epi/test_current_docs.py`

After focused tests pass, run broader EPI pytest with repo-local `--basetemp`, validate the plugin manifest, then test the installed or source plugin against `D:\paper-research-wiki` with approval because that vault is outside this workspace sandbox.
