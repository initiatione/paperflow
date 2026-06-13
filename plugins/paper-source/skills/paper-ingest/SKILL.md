---
name: paper-ingest
description: >
  Use when advancing selected Paper Source papers: "推进论文", prepare-ranked, source-staging, approval, wiki handoff.
---

# Paper Ingest

Use after dry-run ranking selects papers. Paper Source / PS chain goal in `docs\paper-source-linkage.md`: high-quality collection, LLM Wiki deposition, low-burden reading report. If config is missing, stop and use `config-setup`; see `docs\config.md`.

## Workflow Routing

- Source-first handoff checks: load `references/source-first-reading.md`; reader/critic outputs are navigation aids, not source authority.
- Prepare PDFs, MinerU artifacts, source-staging, and `wiki-ingest-brief.json`: load `workflows/prepare-ranked.md`.
- Human approval, `wiki-ingest-trigger`, `record-human-approval`, Paper Wiki record request, or `record-wiki-ingest`: load `workflows/approval-and-trigger.md`.
- Formal page writing after `wiki-ingest-brief.json`: switch to Paper Wiki `$paper-research-wiki`; use `paper-source-paper-deposition/workflows/formal-wiki-write.md` only for legacy `wiki_deposition_task.json is legacy` / `epi-wiki-deposition` compatibility.
- Claim labels, provenance blocks, and evidence-address preservation: use `wiki-provenance/SKILL.md`.

## Modes

- `fast-ingest`: source acquisition, MinerU parse, short Chinese reading/approval report, and `_paper_source/staging/papers/<slug>/wiki-ingest-brief.json`.
- `reviewed-ingest`: add reader outputs for weak parse quality, complex formulas/figures, or requested detailed reading.
- `audited-ingest`: add critic outputs for reproduction, literature review, project decisions, or contradictions.

## Boundaries

Before final/staged vault writes, show one single concise Chinese-first approval report with Chinese-English terminology and one recommendation: `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`. Never ask from raw JSON, gate dumps, path lists, or critic sidecars.

Paper Source prepares source bundles, approval, trigger, record artifacts, and the canonical Paper Source-to-Paper Wiki handoff `wiki-ingest-brief.json`; it does not write final pages in `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, or `opportunities/`. external wiki skills are optional helpers / policy references.

After Paper Wiki completes formal pages, consume `_paper_source/staging/papers/<slug>/paper-wiki-record-request.json` with `record-wiki-ingest --from-paper-wiki-request <request>`. Schema: `paper-wiki-record-request-v1`, `automation_mode=ask`. Paper Wiki writes the request artifact; Paper Source consumes it, validates live page hashes, `final-source-review.json`, human approval, `paper-gate`, and formal-page rules, then writes `wiki-ingest-record.json`. Legacy `prw-record-request.json` remains accepted only for existing artifacts.

If `_paper_source/meta/record-corrections/` marks `correction_type=premature-wiki-ingest-record`, route to Paper Wiki while status is `pending-paper-wiki-review`. After Paper Wiki repairs pages and `final-source-review.json`, Paper Source writes or replaces `wiki-ingest-record.json` when status is `paper-wiki-reviewed-ready-for-paper-source-record` and `paper-gate` returns `ready_for_wiki_ingest_agent`.

Paper Source owns vault bootstrap through `wiki-setup`; Paper Wiki should report missing vault structure back here instead of creating or resetting the vault.
