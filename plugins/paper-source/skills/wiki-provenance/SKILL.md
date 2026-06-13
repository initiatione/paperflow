---
name: wiki-provenance
description: >
  Use when checking Paper Source wiki provenance: "claim 能否回溯", "证据地址", support status, final-source-review.
---

# Wiki Provenance

Use at the final knowledge deposition boundary. Reader/critic artifacts reduce reading cost, but final wiki claims must trace back to source paper evidence.

## Core Rule

No durable wiki claim without support status and evidence route. Preserve the difference between `source-grounded`, `metadata-only`, `inferred`, `unsupported`, author claims, metadata facts, agent inferences, and hypotheses.

## Read Before Writing

Load `wiki-ingest-handoff`, `wiki-agent-trigger.json`, `wiki-ingest-brief.json`, evidence aids, reading report, target vault `AGENTS.md` / `_meta/*`, `references/page-provenance.md`, and `../paper-ingest/references/source-first-reading.md` when reader outputs, claim support, final source review, or formal page writes are involved. If a source-grounded claim is only the author's assertion, keep the status and add `stance=author-claim`.

## Workflow

1. Run `wiki-ingest-handoff --slug <slug>` and stop if not ready; after approval, `wiki-ingest-trigger --slug <slug>` may provide the resume package.
2. Read the source bundle before final prose. Reader summaries and `evidence-index.json` locate evidence; they are not source authority.
3. For each durable claim, choose support status and cite source artifact or sidecar evidence addresses in the page or page-local provenance block.
4. Label agent inferences and add retrieval hooks: method, task, benchmark, metric, dataset, limitation, conflict candidate, related slugs.
5. After final page writing, create `final-source-review.json`, then run `record-wiki-ingest` with the same approved identity used for pre-write human approval.

Load `references/page-provenance.md` for the full page and final-source-review checklist.

## Hard Stops

- Do not flatten `inferred` or `metadata-only` into source-grounded claims.
- Do not let unsupported claims enter main factual sections.
- Do not omit evidence addresses from final pages just because `record-wiki-ingest` stores hashes.
- Do not treat `evidence-index.json` chunks as sufficient verification; reread source artifacts before marking claims source-grounded or final-source-review checks complete.
- Do not convert this provenance check into a formal page `lifecycle: verified` state.
- Do not write final pages from Paper Source suggested routes directly; the target vault contract decides paths, links, tags, merge policy, and staged writes.

## Literature Wiki Contract

Apply provenance across `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. `wiki-ingest-brief.json` is the canonical Paper Source-to-Paper Wiki handoff; `wiki_deposition_task.json is legacy` compatibility only. Paper Wiki `$paper-research-wiki` owns final writing; `paper-source-paper-deposition` is the compatibility adapter. external wiki skills are optional helpers / policy references.

`final-source-review.json` preserves `theory_reconstruction`, `formula_derivation`, `figure_table_evidence`, `novelty_type`, `implementability`, `reproducibility_risk`, `research_gap`, and `cost_level`. Mark checks complete only after source reread, formula/figure review, and complete evidence paths; formal page lifecycle remains governed by the target vault.
