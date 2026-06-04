# Approval And Trigger

Use this workflow after source-staging exists and the next step is human approval, wiki-agent dispatch, or final ingest recording.

## Approval Report

Before `record-human-approval`, present exactly one concise human-readable approval report to the user. Use the staged `briefs/reading-report.md` when complete enough; otherwise repair staging first.

Do not ask the user to approve from raw JSON, gate output, path lists, or critic sidecars.

The report must be Chinese-first and dense but short. For a batch, use one compact card per paper. Each card covers identity metadata, theory or method idea, experiment or validation setup, evidence strength, main caveats, wiki deposition value, and one recommendation: `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`.

## Record Human Approval

```powershell
python scripts\orchestrator.py record-human-approval --slug <slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
```

This writes `_epi/staging/papers/<slug>/human-approval.json` and changes the handoff to `ready_for_agent=true`.

## Queue And Trigger

When the user resumes after reading the report, inspect the queue or known slug:

```powershell
python scripts\orchestrator.py research-queue --bucket ready_to_promote --actions --json --vault <vault>
python scripts\orchestrator.py wiki-ingest-trigger --slug <slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-trigger --slug <slug> --vault <vault> --json
```

`wiki-ingest-trigger` writes `_epi/staging/papers/<slug>/wiki-agent-trigger.json`, a machine-readable resume package for the current Claude, Codex, or other wiki-capable agent. It does not spawn a hidden background LLM process and does not write final pages.

## Record Final Wiki Ingest

After the external wiki-ingest agent writes or stages final Markdown pages under the target vault contract, create `final-source-review.json`, then record completion:

```powershell
python scripts\orchestrator.py record-wiki-ingest --slug <slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault>
```

`record-wiki-ingest` is record-only. It rechecks `paper-gate`, requires matching pre-write `human-approval.json` and `approved-by`, validates `final-source-review.json`, verifies final pages are inside the vault and outside EPI internal folders, records sha256 hashes in raw/staging, and marks the paper `wiki_ingest_recorded`.

When Zotero is enabled in vault config, the completion step also writes a local `zotero-record.json` sidecar and surfaces it in the routed report.

## Queue Buckets

```powershell
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault <vault>
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault <vault>
```

Common buckets are `ready_to_promote`, `needs_reader_repair`, `warning_only`, and `reproducibility_caveats`.
