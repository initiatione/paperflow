# EPI Workflow

Phase 1 supports dry-run discovery:

`configure -> discover -> normalize -> filter -> rank -> report`

Dry-run mode writes run artifacts under the configured paper wiki `_runs/<run-id>/` directory. It does not download PDFs, call MinerU, write compiled wiki pages, or write Zotero.

The routing state source is `run-state.json`. Later phases must preserve the hard gate: No critic pass, no compiled wiki write. The critic gate must pass before promote-to-wiki can write compiled pages.

Raw paper retention is explicit in later acquisition phases: every acquired paper keeps `paper.pdf` and `metadata.json` under the raw artifact layout before parsing, reading, critic, or promotion steps run.

Default paper wiki path:

`D:\paper-research-wiki`

Default interest profile:

robotics, AI, embodied intelligence, and control.

Run from the plugin directory:

```powershell
python scripts\init_paper_wiki.py --vault D:\paper-research-wiki
python scripts\orchestrator.py dry-run --query "robotics embodied intelligence control" --max-results 20 --vault D:\paper-research-wiki
```

Phase 1 fixture runs remain fully offline. Live discovery invokes the upstream `paper-search` CLI when it is available, records the command/probe/query/source provenance in `search-record.json`, preserves the raw JSON response at `_runs/<run-id>/paper-search-raw.json`, and then normalizes paper records for the rest of EPI.

The adapter intentionally calls the CLI, not the stdio MCP server. The verified PyPI package `paper-search-mcp==0.1.3` can run the MCP server with `python -m paper_search_mcp.server`, but it does not publish `paper-search` or `paper-search-mcp` console-script executables. The CLI contract is currently from upstream GitHub `main`.

For live CLI discovery, put a `paper-search` command on PATH or point `EPI_PAPER_SEARCH_COMMAND` at a local wrapper script. A Windows wrapper can look like:

```powershell
# D:\paper-search\.env\paper-search-live.ps1
uvx --from git+https://github.com/openags/paper-search-mcp.git paper-search @args
```

Then run:

```powershell
$env:EPI_PAPER_SEARCH_COMMAND='D:\paper-search\.env\paper-search-live.ps1'
python scripts\orchestrator.py dry-run --query "robotics embodied intelligence control" --max-results 20 --sources arxiv,semantic,openalex --vault D:\paper-research-wiki
```

If the command is unavailable, EPI fails closed with an empty `records` array and an explicit dependency error. It must not fabricate search results.

The dry-run report is written to:

`D:\paper-research-wiki\_runs\<run-id>\report.md`

Live dry-run source JSON is written to:

`D:\paper-research-wiki\_runs\<run-id>\paper-search-raw.json`

Phase 2 supports one-paper ingest from local or fixture inputs:

`acquire -> parse-fixture -> read -> critic -> staging`

```powershell
python scripts\orchestrator.py ingest-one --candidate D:\codex-tmp\candidate.json --pdf D:\codex-tmp\paper.pdf --mineru-md D:\codex-tmp\paper.md --mineru-tex D:\codex-tmp\paper.tex --vault D:\paper-research-wiki
```

To acquire a selected candidate from its `pdf_url` before parsing:

```powershell
python scripts\orchestrator.py acquire-paper --candidate D:\codex-tmp\candidate.json --vault D:\paper-research-wiki
```

`acquire-paper` downloads the URL into `_raw\papers\<paper-slug>\paper.pdf`, writes `metadata.json`, and writes `acquire-record.json`. If the URL is missing, returns HTTP error, cannot be reached, or produces an empty response, EPI writes a failed `acquire-record.json` and does not fabricate `paper.pdf`.

For a paper that already has `_raw\papers\<paper-slug>\paper.pdf`, EPI can invoke the configured MinerU command boundary:

```powershell
python scripts\orchestrator.py parse-paper --slug <paper-slug> --vault D:\paper-research-wiki
python scripts\orchestrator.py parse-paper --slug <paper-slug> --mineru-command "python D:\paper-search\plugins\epi\skills\mineru-paper-parser\scripts\mineru_batch_to_md.py" --vault D:\paper-research-wiki
```

`parse-paper` writes command logs under `_raw\papers\<paper-slug>\mineru-command\` and imports successful outputs into `_raw\papers\<paper-slug>\mineru\paper.md`, `paper.tex`, `images\`, and `mineru-manifest.json`. If the command fails or produces no Markdown, EPI writes a failed `parse-record.json` and does not fabricate `mineru\paper.md`.

The resumable router advances a paper by one safe stage per invocation, based on missing artifacts:

```powershell
python scripts\orchestrator.py advance-paper --candidate D:\codex-tmp\candidate.json --vault D:\paper-research-wiki
python scripts\orchestrator.py advance-paper --candidate D:\codex-tmp\candidate.json --mineru-command "python D:\paper-search\plugins\epi\skills\mineru-paper-parser\scripts\mineru_batch_to_md.py" --vault D:\paper-research-wiki
```

`advance-paper` writes `_raw\papers\<paper-slug>\run-state.json` after every invocation. It can route through acquire, parse, read, critic, staging, and awaiting promotion. It never writes compiled pages under `references`, `concepts`, or `synthesis`; once staging exists it reports `next_action=promote-to-wiki` and keeps `human_gate_required=true`.

For ranked candidate lists, the batch router advances each selected paper by one stage and records a run-level state:

```powershell
python scripts\orchestrator.py advance-batch --candidates D:\codex-tmp\ranked-candidates.json --max-papers 3 --vault D:\paper-research-wiki
```

`advance-batch` writes `_runs\<run-id>\run-state.json` and `_runs\<run-id>\batch-advance-record.json`. `max_papers` is a hard per-call budget: skipped candidates are counted as `skipped_count`, and unprocessed candidates are not acquired or parsed. The batch command also stops before compiled wiki promotion; use `promote-to-wiki --approved-by <name>` for the explicit human gate.

To continue directly from a dry-run discovery without copying candidate JSON by hand, point the router at the dry-run `run_id`:

```powershell
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --vault D:\paper-research-wiki
```

`advance-ranked` reads `_runs\<dry-run-id>\rank.json`, preserves `source_run_id` and `candidate_source` in the new batch record, and fails closed if ranked candidates are missing.

Phase 2 writes raw paper artifacts under `_raw/papers/<paper-slug>/` and draft pages under `_staging/papers/<paper-slug>/`. It does not write compiled pages under `references`, `concepts`, or `synthesis`; Phase 3 owns transactional promotion.

The critic stage writes both legacy critic files and the Phase 5 reviewer-quorum artifact:

- `_raw\papers\<paper-slug>\critic\paper-quality-critic.md`
- `_raw\papers\<paper-slug>\critic\parse-quality-critic.md`
- `_raw\papers\<paper-slug>\critic\reader-quality-critic.md`
- `_raw\papers\<paper-slug>\critic\critic-report.json`
- `_raw\papers\<paper-slug>\critic\critic-quorum.json`

`critic-quorum.json` currently records three local reviewers in `mode: local`: `paper-quality-critic`, `parse-quality-critic`, and `reader-quality-critic`. This is the additive Phase 5 contract for later subagent or LLM reviewer integration. Promotion and staging still use the compatible hard gate in `critic-report.json`: `outcome` must be `pass`, and the hard rule remains `No critic pass, no compiled wiki write.`

Phase 3 promotes staged references after critic approval and an explicit human gate approval:

```powershell
python scripts\orchestrator.py promote-to-wiki --slug <paper-slug> --approved-by <name> --vault D:\paper-research-wiki
```

If `--approved-by` is omitted, promotion fails before any compiled page is written. The approval decision is recorded in `promotion-record.json`.

Rollback uses the paper's `promotion-record.json`:

```powershell
python scripts\orchestrator.py rollback-promotion --slug <paper-slug> --vault D:\paper-research-wiki
```

Promotion snapshots the previous compiled page, `.manifest.json`, `index.md`, `hot.md`, and `log.md` before writing. It refreshes managed promoted-paper sections in `index.md` and `hot.md` while preserving surrounding text. Rollback restores the compiled page and state snapshots, then appends a rollback entry to `log.md` so the recovery remains auditable.

Redo and recritic commands operate only on `_raw/papers/<paper-slug>/` artifacts and append an audit event to `redo-records.jsonl`:

```powershell
python scripts\orchestrator.py redo-acquire --slug <paper-slug> --pdf D:\codex-tmp\replacement.pdf --reason "better source" --vault D:\paper-research-wiki
python scripts\orchestrator.py redo-parse --slug <paper-slug> --mineru-md D:\codex-tmp\paper.md --mineru-tex D:\codex-tmp\paper.tex --reason "parse critic requested redo" --vault D:\paper-research-wiki
python scripts\orchestrator.py redo-read --slug <paper-slug> --reason "reader stale after parse redo" --vault D:\paper-research-wiki
python scripts\orchestrator.py recritic --slug <paper-slug> --reason "reader revised" --vault D:\paper-research-wiki
```

Promotion validates both gates before writing compiled pages: critic must pass, and human approval must be present. The hard rule remains: No critic pass, no compiled wiki write.

Phase 4 optional integrations are explicit and auditable:

```powershell
python scripts\orchestrator.py zotero-sync --paper-root D:\paper-research-wiki\_raw\papers\<paper-slug> --collection EPI
python scripts\orchestrator.py record-feedback --type reader-correction --target <paper-slug>/reader.md --message "Needs stronger evidence" --source human
python scripts\orchestrator.py propose-evolution --reflection-type OPTIMIZATION --target-asset templates\ranking.example.yaml --rationale "Boost reproducibility after feedback" --proposed-change-json "{\"weights\":{\"reproducibility_signal\":0.12}}" --evidence "_runs\feedback.jsonl#1"
python scripts\orchestrator.py activate-evolution --proposal-id <proposal-id> --approved
```

Zotero writes and evolution activation are manual-gated by default. Skill-aware evolution records proposals and activation metadata; it does not directly edit plugin code.
