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

`wiki-ingest-trigger` writes `_epi/staging/papers/<slug>/wiki-agent-trigger.json`, a machine-readable resume package for PRW `$paper-research-wiki` or another wiki-capable agent following the PRW/vault contract. It does not spawn a hidden background LLM process and does not write final pages. The trigger points at `wiki-ingest-brief.json`, the canonical EPI-to-PRW handoff; `wiki_deposition_task.json is legacy` compatibility only.

## Record Final Wiki Ingest

After PRW `$paper-research-wiki` or another wiki-capable agent following the PRW/vault contract writes or stages final Markdown pages, create `final-source-review.json`, then record completion:

```powershell
python scripts\orchestrator.py record-wiki-ingest --slug <slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault>
```

For PRW ask-mode automation, PRW writes the request artifact; EPI consumes it:

```powershell
python scripts\orchestrator.py record-wiki-ingest --from-prw-request _epi/staging/papers/<slug>/prw-record-request.json --vault <vault> --json
```

The request uses schema `prw-record-request-v1` and `automation_mode=ask`. EPI validates live page hashes, `final-source-review.json`, matching human approval, `paper-gate`, and formal-page rules before writing `wiki-ingest-record.json`.

`record-wiki-ingest` is record-only. It rechecks `paper-gate`, requires matching pre-write `human-approval.json` and `approved-by`, validates `final-source-review.json`, verifies final pages are inside the vault and outside EPI internal folders, records sha256 hashes in raw/staging, and marks the paper `wiki_ingest_recorded`.

When Zotero is enabled in vault config, the completion step also writes a local `zotero-record.json` sidecar and surfaces it in the routed report.

## Corrected Premature Records

If a prior `wiki-ingest-record.json` was corrected as `premature-wiki-ingest-record`, the correction entry is under `_epi/meta/record-corrections/`. While its wiki status is `pending-prw-review`, send the paper to PRW for formal page and `final-source-review.json` repair. After PRW repairs pages and `final-source-review.json`; EPI writes or replaces `wiki-ingest-record.json`: when the correction status is `prw-reviewed-ready-for-epi-record`, `paper-gate` returns `ready_for_wiki_ingest_agent`; rerun `record-wiki-ingest` to replace the premature record. PRW reports readiness but must not write the EPI replacement record.

## Queue Buckets

```powershell
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault <vault>
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault <vault>
```

Common buckets are `ready_to_promote`, `needs_reader_repair`, `warning_only`, and `reproducibility_caveats`.
