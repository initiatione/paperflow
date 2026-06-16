# Approval And Trigger

Use after source-staging exists and the next step is human approval, wiki-agent dispatch, or final ingest recording.

## Approval

Before `record-human-approval`, present exactly one concise human-readable approval report. Use staged `briefs/reading-report.md` when complete; otherwise repair staging first. Do not ask from raw JSON, gate output, path lists, or critic sidecars.

The report is Chinese-first, dense, and short. For a batch, use one compact card per paper covering identity, method/theory idea, validation setup, evidence strength, caveats, wiki deposition value, and one recommendation: `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`.

```powershell
python scripts\orchestrator.py record-human-approval --slug <slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
```

Writes `_paper_source/staging/papers/<slug>/human-approval.json` and changes the handoff to `ready_for_agent=true`.

Codex automation is explicit opt-in. Do not infer it from ordinary `discover-papers`, auto-staging, or a general "find papers" request. Only use it when the user has explicitly authorized the current Codex/Trellis task to continue through Paper Wiki deposition:

```powershell
python scripts\orchestrator.py record-human-approval --slug <slug> --approved-by codex-automation:<task-id> --scope run-wiki-ingest-agent --automation-mode codex-task --automation-task-id <task-id> --automation-task-source <task-path-or-session> --automation-authorization "<explicit user authorization>" --vault <vault> --json
```

This still writes the existing `paper-source-human-approval-v1` approval artifact. Automation approval requires `approved_by=codex-automation:<task-id>`, records `approval_actor_type=codex-automation` plus an `automation` object, and remains a pre-write approval for the current/wiki-capable agent. Paper Source does not write formal Paper Wiki pages.

## Queue And Trigger

```powershell
python scripts\orchestrator.py research-queue --bucket ready_to_promote --actions --json --vault <vault>
python scripts\orchestrator.py wiki-ingest-trigger --slug <slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-trigger --slug <slug> --vault <vault> --json
```

`wiki-ingest-trigger` writes `_paper_source/staging/papers/<slug>/wiki-agent-trigger.json`, a resume package for Paper Wiki `$paper-research-wiki` or another wiki-capable agent following the Paper Wiki/vault contract. It does not spawn a hidden LLM process or write final pages. The trigger points at `wiki-ingest-brief.json`, the canonical Paper Source-to-Paper Wiki handoff.

When the approval record contains automation metadata, the trigger includes `approved_by`, `approval_actor_type`, `automation_mode`, and `automation_handoff` so the running Codex task can audit why it may continue. Human approval triggers omit `automation_handoff`.

## Record Final Wiki Ingest

After Paper Wiki writes or stages final Markdown pages and `final-source-review.json` exists:

```powershell
python scripts\orchestrator.py record-wiki-ingest --slug <slug> --page <final-page.md> --approved-by <name> --source-review <final-source-review.json> --vault <vault>
python scripts\orchestrator.py record-wiki-ingest --from-paper-wiki-request _paper_source/staging/papers/<slug>/paper-wiki-record-request.json --vault <vault> --json
```

Paper Wiki writes the request artifact; Paper Source consumes it. The request uses schema `paper-wiki-record-request-v1` and `automation_mode=ask`. Paper Source validates live page hashes, `final-source-review.json`, matching human approval, `paper-gate`, and formal-page rules before writing `wiki-ingest-record.json`.

`record-wiki-ingest` is record-only: it rechecks `paper-gate`, requires matching pre-write `human-approval.json` / `approved-by`, validates final pages stay inside the vault and outside Paper Source internal folders, records sha256 hashes in raw/staging, marks `wiki_ingest_recorded`, and writes `zotero-record.json` when Zotero is enabled.

## Corrections And Buckets

If `_paper_source/meta/record-corrections/` marks `correction_type=premature-wiki-ingest-record`, send the paper to Paper Wiki while status is `pending-paper-wiki-review`. After Paper Wiki repairs pages and `final-source-review.json`, Paper Source writes or replaces `wiki-ingest-record.json` when status is `paper-wiki-reviewed-ready-for-paper-source-record` and `paper-gate` returns `ready_for_wiki_ingest_agent`; rerun `record-wiki-ingest` to replace the premature record. Paper Wiki reports readiness but must not write the Paper Source replacement record.

```powershell
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault <vault>
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault <vault>
```

Common buckets: `ready_to_promote`, `needs_reader_repair`, `warning_only`, and `reproducibility_caveats`.
