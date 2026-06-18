# Paper Wiki Health

Use this reference when the user says Paper Wiki cannot deposit, ask, check, update, relink, or consume Paper Source handoffs.

## Boundary

Paper Source owns vault bootstrap, `_paper_source/` evidence, source-staging, approval, trigger, and record metadata. Paper Wiki owns formal page writing, formal page repair, wiki ask, paper extraction/deposition, update, relink, and language/figure evidence repair.

Do not make Health Doctor write formal pages. Route formal page work to Paper Wiki `$paper-research-wiki` after Paper Source health and target vault contracts are clear.

## Vault Prerequisites

A PaperFlow-compatible paper wiki vault should have:

- `_paper_source/` with raw/staging/meta/policies roots;
- `_meta/` contract files such as schema, taxonomy, and directory structure;
- `AGENTS.md`;
- `.obsidian/` and `.git`;
- formal page roots: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.

If these roots are missing, use Paper Source `wiki-setup` for initialization or repair. Paper Wiki should report missing structure rather than silently bootstrap the vault.

## Handoff Health

For a paper-level handoff, inspect:

- `_paper_source/raw/<slug>/paper.pdf`
- `_paper_source/raw/<slug>/metadata.json`
- `_paper_source/raw/<slug>/mineru/`
- `_paper_source/raw/<slug>/evidence-index.json`
- `_paper_source/staging/papers/<slug>/wiki-ingest-brief.json`
- `_paper_source/staging/papers/<slug>/human-approval.json`
- `_paper_source/staging/papers/<slug>/wiki-agent-trigger.json`
- `_paper_source/staging/papers/<slug>/final-source-review.json`

`wiki-ingest-brief.json` is the current Paper Source-to-Paper Wiki handoff. `wiki_deposition_task.json` is historical cleanup only.

## Formal Page Health

Formal pages must stay outside `_paper_source/`, `.obsidian/`, `.claude/`, legacy `_epi/`, and snapshot trees. Frontmatter `sources` should use title-display Markdown links to canonical source PDFs under `_paper_source/raw/<slug>/paper.pdf`; body `## 原文与证据入口` should repeat the same source entry.

New or repaired formal pages should use `lifecycle: draft`; old `review-needed` is migration debt. Do not introduce `review_status`.

## QMD And Graph Boundary

Markdown formal pages are the source of truth. QMD indexing and graph views are accelerators or visibility layers. `_paper_source/**`, raw MinerU Markdown, staging handoffs, snapshots, `.obsidian/**`, and tool histories must stay out of the formal graph.

