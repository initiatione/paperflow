# Paper Source Evaluation

This doc is the public contract for the plugin development quality loop.

## Runtime Checks

These checks cover the runtime chain only. They validate the live workflow commands and the artifacts they emit, not the offline development quality loop below.

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 20 --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py paper-gate --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py record-human-approval --slug <paper-slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
python scripts\orchestrator.py wiki-ingest-trigger --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py record-wiki-ingest --slug <paper-slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault>
python scripts\orchestrator.py zotero-sync --paper-root <vault>\_paper_source\\raw\\<paper-slug> --collection Paper Source --enabled
```

Runtime artifacts stay under the single `_paper_source` internal repository and the optional Zotero sidecar. The main artifacts are `_paper_source/runs/<run-id>/search-record.json`, `rank.json`, `report.md`, `report.json`, and `run-state.json`, plus paper-scoped `parse-record.json`, `critic-report.json`, `_paper_source/staging/papers/<slug>/human-approval.json`, `_paper_source/staging/papers/<slug>/wiki-agent-trigger.json`, `wiki-ingest-record.json`, and `zotero-record.json` files.

`report --run-id` reads existing `_paper_source/runs/<run-id>/report.md`, `report.json`, and `run-state.json`; it does not rerun discovery, ingest, MinerU, staging, or wiki writes.

## Development Quality Loop

This loop is separate from the runtime chain above.

Plugin Eval -> paper-source-quality-gates -> benchmark -> compare before/after -> improvement brief -> skill-aware-evolve proposal.

1. Run Plugin Eval.
2. Run `paper-source-quality-gates`.
3. Capture a benchmark or comparison payload.
4. Compare before/after metrics.
5. Write an improvement brief.
6. Turn the brief into a skill-aware-evolve proposal.

During development, run Plugin Eval through `$env:PLUGIN_EVAL_SCRIPT` instead of committing a machine-local cache path. Preserve the Paper Source metric pack in release checks:

```powershell
node $env:PLUGIN_EVAL_SCRIPT analyze plugins\paper-source --metric-pack plugins\paper-source\metric-packs\paper-source-quality-gates\manifest.json --format markdown
```

`scripts\release_check_paper_source.ps1` generates a transient `plugins\paper-source\.plugin-eval\coverage.xml` before Plugin Eval when `$env:PLUGIN_EVAL_SCRIPT` is set, then removes `.plugin-eval` through package hygiene after the evaluator finishes. Do not commit that coverage file.

Use the local `evaluation-brief` command to generate the brief:

```powershell
python scripts\orchestrator.py evaluation-brief --target-asset templates\ranking.example.yaml --rationale "<text>" --proposed-change-json "<json>" --before-metrics-json "<json>" --after-metrics-json "<json>" --plugin-eval-json <path> --metric-pack-json <path> --benchmark-json <path> --out-dir .plugin-eval\improvement-briefs
```

The command writes both JSON and Markdown under `.plugin-eval\improvement-briefs\`. Those outputs are local development artifacts and stay out of commits. A complete dev-loop brief must provide all three evidence sources: Plugin Eval JSON, `paper-source-quality-gates` metric-pack JSON, and a benchmark/comparison JSON. If any source is missing, the brief records `source_completeness.complete=false`, adds the required `quality_loop_sources_complete` gate, and sets `next_action=collect-missing-quality-evidence` instead of treating the brief as ready for a skill-aware-evolve proposal. `activate-evolution` enforces that gate at activation time: non-empty `missing_sources` or `invalid_sources` rejects the proposal even when `validation_result.passed=true`.

The benchmark payload should use a stable schema, currently `paper-source-benchmark-v1`, so a loose JSON blob does not masquerade as a comparable benchmark. Invalid or incomplete benchmark sources remain evidence gaps, not valid promotion signals.

Paper Source repository-level contract tests live under `tests\paper_source\`, not inside the plugin package, so development tests do not inflate plugin static cost. Current Windows Plugin Eval builds absolute paths with backslashes, while its Python test-file heuristic matches only `/tests/` or `/test_*.py`, so `py-tests-missing` can appear even when the repo-level Paper Source suite passes. Treat that warning as an evaluator path-normalization and packaging-boundary limitation unless Plugin Eval starts reporting `py_test_file_count > 0`.

`deferred_cost_tokens-budget-high` is expected while `docs\paper-source-linkage.md` remains inside the plugin package as the required Chinese chain contract. Do not remove that document only to raise the static score. Valid budget cleanup is limited to deleting generated/redundant package files, trimming duplicated prose, and keeping `docs\workflow.md`, `docs\evaluation.md`, and `docs\config.md` as compact entrypoints.

Keep `.plugin-eval`, `.pytest_tmp*`, `.coverage`, and generated coverage artifacts out of commits. Release coverage XML is evaluator input, not package content.
