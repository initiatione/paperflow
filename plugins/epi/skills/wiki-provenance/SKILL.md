---
name: wiki-provenance
description: >
  Use when final EPI paper knowledge is written to an Obsidian or LLM wiki and
  claims must preserve provenance, including "claim 能否回溯", "证据地址",
  support status, evidence-map addresses, final-source-review links, or retrieval hooks.
---

# Wiki Provenance

Use this for the final knowledge deposition boundary. EPI reader and critic artifacts reduce reading cost, but final wiki claims must remain traceable back to source paper evidence, whether the final writer is Claude, Codex, or another wiki-capable agent.

## Core Rule

No durable wiki claim without a support status and an evidence route. The page must preserve the difference between source-grounded findings, author claims, metadata facts, agent inferences, and unsupported hypotheses.

## Inputs

Before writing or reviewing final pages, load:

- `wiki-ingest-handoff` output.
- `wiki-agent-trigger.json` when the handoff has already been approved and EPI has generated the resume package.
- `wiki-ingest-brief.json`.
- `paper.pdf`, `metadata.json`, `mineru/<slug>.md`, `mineru/paper.tex`, `mineru/images/*`, `mineru/mineru-manifest.json`.
- `reader/evidence-map.json` and `reader/claim-support.json`.
- `critic/*.json` and `briefs/reading-report.md`.
- Target vault `AGENTS.md` and `_meta/*` contract files.

## Claim Statuses

Use the EPI support status when present:

- `source-grounded`: supported by parsed paper text, TeX, figure/table/image, or PDF review.
- `metadata-only`: supported by title, DOI, venue, year, authors, source metadata, or abstract-only fields.
- `inferred`: agent synthesis or interpretation; keep it useful, but label it.
- `unsupported`: do not put in main factual prose; move to open questions or hypotheses.

If a source-grounded claim is only the paper author's assertion, keep the support status and add an explicit stance such as `author-claim`.

## Workflow

1. Run `wiki-ingest-handoff --slug <slug>` and stop if the handoff is not ready; after human approval, `wiki-ingest-trigger --slug <slug>` may provide the current agent's resume package.
2. Read the source bundle before final prose. Reader summaries are navigation aids, not source authority.
3. For each durable claim, choose a support status and cite the evidence address from `evidence-map.json`, `claim-support.json`, source artifacts, or PDF fallback review.
4. Embed evidence addresses in the page or in a page-local provenance block; do not leave them only in EPI sidecar JSON.
5. Put agent inferences in a clearly labeled section such as `Inferences`, `Hypotheses`, or `Open Questions`.
6. Add synthesis hooks for later retrieval: method family, task, benchmark, metric, dataset, limitation, conflict candidate, and related paper slugs.
7. After final page writing, create `final-source-review.json`, then run `record-wiki-ingest` with the same approved identity used for pre-write human approval.

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

Load `references/page-provenance.md` for a fuller page and final-source-review checklist.

## Hard Stops

- Do not flatten `inferred` or `metadata-only` statements into source-grounded claims.
- Do not let unsupported claims enter main factual sections.
- Do not omit evidence addresses from final pages just because `record-wiki-ingest` stores hashes.
- Do not write final pages from EPI suggested routes directly; the target vault contract decides paths, links, tags, merge policy, and staged writes.

## Literature Wiki Contract

Apply provenance across the seven EPI paper wiki families: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. Use `wiki-provenance` with `tag-taxonomy` so evidence status and tags do not drift between single-paper pages, derivation pages, experiment pages, synthesis pages, and opportunity pages.

`final-source-review.json` must preserve `theory_reconstruction`, `formula_derivation`, `figure_table_evidence`, `novelty_type`, `implementability`, `reproducibility_risk`, `research_gap`, and `cost_level`. Keep author-claimed novelty separate from EPI-confirmed novelty, and only mark pages `verified` after source reread, formula/figure review, and complete evidence paths.
