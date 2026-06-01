---
name: paper-ingest
description: "Use when ingesting selected EPI papers into raw artifacts, readers, critics, staging drafts, or handoff."
---

# Paper Ingest

Use after dry-run ranking selects papers. Chain goal in `docs\epi-linkage.md`: high-quality collection, LLM Wiki deposition, low-burden reading report.

If config is missing, stop and use `config-setup`. See `docs\config.md`.

## Reference Routing

Load `references/source-first-reading.md` when generating or checking reader outputs, critic inputs, staging bundles, or wiki-ingest handoffs. Keep reader summaries compact, but preserve source paper claims, formulas, figures, tables, image interpretations, caveats, and evidence pointers. Treat parse quality as a source bundle check: Markdown alone is not enough when `parse-record.json` says parse succeeded; inspect TeX, images, and the MinerU manifest too.

For final wiki-page provenance, support labels, and claim-to-evidence round-trips, use `wiki-provenance` as the final deposition layer. This skill stays focused on raw -> reader -> critic -> staging -> handoff.

## Choose Path

| Intent | Command path |
| --- | --- |
| Steps 1-3 only: download + MinerU parse, stop at raw artifacts | `prepare-ranked` |
| Continue into reader, critic, staging, approval, and handoff | `advance-*`, `paper-gate`, `wiki-ingest-handoff`, `record-human-approval` |
| Resume final wiki writing after approval or a later `@EPI` turn | `research-queue --bucket ready_to_promote --actions`, then `wiki-ingest-trigger` |
| Final wiki provenance and claim labels | `wiki-provenance` |

## Path A: Raw Artifacts Only

Stops after `mineru\paper.md`, `mineru\paper.tex`, `mineru\images`, and `mineru\mineru-manifest.json`.

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 1 --vault <vault>
```

Use `--max-papers 10 --skip-existing` for real testing; `--max-papers 1` is a smoke test. Use `--json` for run id, counts, stop point, and report paths. Inspect per-paper failures: `acquire_failed`, `parse_failed`, `prepare_failed`.

Failed `acquire-record.json` includes `failure_class`, `retryable`, and `recovery_hint`; use them to decide whether to retry, switch source, or skip. For slow MinerU jobs, pass `--mineru-timeout <seconds>` or set `EPI_MINERU_TIMEOUT`; complete parse reuse requires `parse-record.json status=success`, not just a Markdown file.

Do not use `advance-paper`, `advance-ranked`, or `advance-batch` when the user only asked for 1-3.

## Path B: Reader, Critic, Staging

```powershell
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --vault <vault>
python scripts\orchestrator.py advance-batch --candidates <candidate-json> --max-papers 3 --vault <vault>
python scripts\orchestrator.py paper-gate --slug <slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <slug> --vault <vault>
python scripts\orchestrator.py record-human-approval --slug <slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
python scripts\orchestrator.py wiki-ingest-trigger --slug <slug> --vault <vault>
python scripts\orchestrator.py record-wiki-ingest --slug <slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault <vault>
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault <vault>
```

After critic pass, staging prepares evidence drafts, `wiki-ingest-brief.json`, and `reports/<slug>-reading-report.md`. The report should emphasize theory insight, experiment design, Reading Trust Status, evidence strength, suggested wiki routes, and reproducibility caveats.

The workflow image's Report step is read-only: use `report --run-id` to display an existing `_runs/<run-id>/report.md` or `report.json`. The internal module is `report_run.py`; do not invent a `run-report` command.

## Source-First Wiki Handoff

`reader/` and critic outputs reduce reading cost; they are not the source of truth for final wiki writing. Before final wiki ingest, load `references/source-first-reading.md`, run `wiki-ingest-handoff`, and verify the handoff requires:

- source artifacts: `paper.pdf`, `metadata.json`, `mineru/paper.md`, `mineru/paper.tex`, `mineru/images/*`, `mineru/mineru-manifest.json`
- evidence aids: `reader/evidence-map.json`, `reader/claim-support.json`, `reader/figures.md`, `critic/*.json`
- formula/figure review: preserve central formulas, notation, derivation cues, figures, tables, image interpretations, parse uncertainty, and source provenance
- final source review: require `final-source-review.json` with source artifact hashes, formula review, figure/image review, PDF fallback decision, and final page provenance

If the handoff lacks these fields, repair staging or rerun the relevant EPI step before final wiki writing.

## Wiki Boundary

Final Obsidian/LLM Wiki pages are agent-mediated under the target vault contract. The final wiki executor may be Claude, Codex, or another wiki-capable agent. Before final writing, run `wiki-ingest-handoff`, resolve `AGENTS.md` and `_meta/*`, use the framework references named in `docs\epi-linkage.md`, keep local wiki skills as adapters, and require `wiki_rule_source_model`. Then record pre-write approval with `record-human-approval --scope run-wiki-ingest-agent`; do not let the wiki ingest agent write final or staged vault pages until the handoff reports `ready_for_agent=true`.

When the user has read the lightweight report and calls `@EPI` again to continue wiki writing, run `research-queue --bucket ready_to_promote --actions --json` or the known slug's `wiki-ingest-trigger --slug <slug> --json`. The trigger writes `_staging/papers/<slug>/wiki-agent-trigger.json` only after approval and gives the current Claude, Codex, or other wiki-capable agent the source-first instruction bundle. It does not spawn a hidden background agent and does not write final pages by itself.

If the user asks for claim labels, provenance blocks, evidence-address preservation, or later round-trip retrieval from final pages, switch to `wiki-provenance` instead of expanding this skill.

After the wiki ingest agent has written or staged the final Markdown pages, create `final-source-review.json`, then run `record-wiki-ingest --page ... --approved-by ... --source-review ...`. This command is record-only: it rechecks `paper-gate`, requires matching pre-write `human-approval.json`, validates final source review, verifies each final page is inside the vault and outside EPI internal folders, records sha256 hashes in raw/staging, and marks the paper `wiki_ingest_recorded`. It must not rewrite final pages or replace the target vault's ingest agent.

Safety: raw/staging writes are allowed. Compiled wiki writes require critic pass, handoff, pre-write human approval, and final source review.
