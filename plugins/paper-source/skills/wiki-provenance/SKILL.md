---
name: wiki-provenance
description: >
  Use when checking Paper Source wiki provenance: "claim 能否回溯", "证据地址", support status, final-source-review.
---

# Wiki Provenance

Use at the final knowledge deposition boundary. Reader/critic artifacts reduce reading cost, but final wiki claims must trace back to source paper evidence.

## Core Rule

No durable wiki claim without support status and evidence route. Preserve the difference between source-grounded findings, author claims, metadata facts, agent inferences, and unsupported hypotheses.

## Read Before Writing

Load the handoff/trigger (`wiki-ingest-handoff`, `wiki-agent-trigger.json`, `wiki-ingest-brief.json`), source bundle (`paper.pdf`, `metadata.json`, MinerU Markdown/images/manifest, optional non-empty native TeX), evidence aids (`evidence-index.json`, reader maps, critic reports), reading report, and target vault `AGENTS.md` / `_meta/*`.

## Claim Statuses

Use Paper Source status when present: `source-grounded`, `metadata-only`, `inferred`, `unsupported`. If a source-grounded claim is only the author's assertion, keep the status and add `stance=author-claim`.

## Workflow

1. Run `wiki-ingest-handoff --slug <slug>` and stop if not ready; after approval, `wiki-ingest-trigger --slug <slug>` may provide the resume package.
2. Read the source bundle before final prose. Reader summaries are navigation aids, not source authority.
3. Use `evidence-index.json` only to locate evidence; verify important claims against MinerU Markdown, TeX, images, manifest, and `paper.pdf`.
4. For each durable claim, choose support status and cite the evidence address from source artifacts or evidence sidecars.
5. Embed evidence addresses in the page or page-local provenance block; do not leave them only in sidecar JSON.
6. Label agent inferences and add retrieval hooks: method, task, benchmark, metric, dataset, limitation, conflict candidate, related slugs.
8. After final page writing, create `final-source-review.json`, then run `record-wiki-ingest` with the same approved identity used for pre-write human approval.

## Page Pattern

Keep the target vault contract authoritative. When it allows inline provenance, prefer compact claim lines like:

```markdown
- Claim: <paper-backed statement>
  Support: source-grounded; stance=author-claim
  Evidence: reader/claim-support.json#claim-014; mineru/<slug>.md#experiments; Table 2
```

For inferred synthesis:

```markdown
- Inference: <agent interpretation>
  Support: inferred
  Basis: claim-014 + claim-021; compare with [[related-paper]]
```

Load `references/page-provenance.md` for the full page and final-source-review checklist.

## Hard Stops

- Do not flatten `inferred` or `metadata-only` statements into source-grounded claims.
- Do not let unsupported claims enter main factual sections.
- Do not omit evidence addresses from final pages just because `record-wiki-ingest` stores hashes.
- Do not treat `evidence-index.json` chunks as sufficient verification; use them to locate evidence, then reread source artifacts before marking claims source-grounded or pages verified.
- Do not write final pages from Paper Source suggested routes directly; the target vault contract decides paths, links, tags, merge policy, and staged writes.

## Literature Wiki Contract

Apply provenance across `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. `wiki-ingest-brief.json` is the canonical Paper Source-to-Paper Wiki handoff; `wiki_deposition_task.json is legacy` compatibility only. Paper Wiki `$paper-research-wiki` owns final writing; `paper-source-paper-deposition` is the compatibility adapter. external wiki skills are optional helpers / policy references.

`final-source-review.json` preserves `theory_reconstruction`, `formula_derivation`, `figure_table_evidence`, `novelty_type`, `implementability`, `reproducibility_risk`, `research_gap`, and `cost_level`. Only mark pages `verified` after source reread, formula/figure review, and complete evidence paths.
