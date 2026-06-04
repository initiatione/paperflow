# Formal Wiki Write

Use this workflow when `wiki_deposition_task.json` is ready and the task is to stage or write formal Obsidian/LLM Wiki pages.

## Load Inputs

Read the required EPI source bundle and target vault contract before writing:

- `_epi/staging/papers/<slug>/wiki_deposition_task.json`
- `_epi/staging/papers/<slug>/wiki-ingest-brief.json`
- `_epi/staging/papers/<slug>/briefs/reading-report.md`
- `_epi/raw/papers/<slug>/metadata.json`
- `_epi/raw/papers/<slug>/paper.pdf`
- `_epi/raw/papers/<slug>/mineru/<slug>.md`
- `_epi/raw/papers/<slug>/mineru/paper.tex`
- `_epi/raw/papers/<slug>/mineru/images/*`
- `_epi/raw/papers/<slug>/mineru/mineru-manifest.json`
- target vault `AGENTS.md` and `_meta/*` contract files

Reader and critic files reduce reading cost when present. They are evidence aids, not source authority.

## Use Wiki Skill Stack

Use the obsidian-wiki layer explicitly:

- `llm-wiki` for source-first knowledge compilation.
- `wiki-context-pack` before writing, so related pages are read first.
- `wiki-ingest` for staged page creation and merge decisions.
- `wiki-lint` before record or stage commit.
- `wiki-stage-commit` for human-reviewed promotion.
- `wiki-status` and `wiki-query` for existing knowledge and staged pages.
- `wiki-provenance` for support labels, evidence addresses, and final-source-review closure.
- `tag-taxonomy` for tags and aliases.

After first staged pages exist, `wiki-synthesize`, `wiki-dedup`, and `cross-linker` may improve graph quality.

## Page Families

Choose final page families under the target vault contract:

- `references/`: single-paper evidence pages.
- `concepts/`: reusable concepts, variables, assumptions, method variants, and conditions of use.
- `derivations/`: equations, variable definitions, derivation chain, assumptions, and cross-paper differences.
- `experiments/`: platforms, settings, baselines, metrics, environments, and reproducibility risks.
- `synthesis/`: cross-paper matrices, complementarity, contradictions, and evidence strength.
- `reports/`: low-burden Chinese reading entrypoints.
- `opportunities/`: research gaps linked to paper limitations and verifiable experiments.

Do not create generic `entities/`, `skills/`, `journal/`, or `projects/` pages for formal EPI deposition unless the target vault contract explicitly routes a secondary copy there.

## Frontmatter

Every formal page must include:

```yaml
---
title:
category:
page_family:
tags:
aliases:
sources:
summary:
provenance:
  extracted:
  inferred:
  ambiguous:
base_confidence:
lifecycle:
lifecycle_changed:
tier:
created:
updated:
---
```

Initial `lifecycle` is `draft` or `review-needed`; do not mark pages `source-reviewed` or `verified` until source reread, formula/figure review, `wiki-lint`, and human stage review have passed.

## Quality Gates

Before `record-wiki-ingest` or `wiki-stage-commit`, check:

- Required frontmatter fields are present and non-empty where applicable.
- Formal pages use Obsidian wikilinks for internal knowledge.
- `_epi/` and other internal roots must not enter the formal graph as pages.
- Do not use fenced formula blocks such as ` ```math`, ` ```tex`, or ` ```latex`; use `$...$` or `$$...$$`.
- `derivations/` pages include variable definitions and a derivation chain.
- `references/` pages include model or method, formulas, experiments, metrics, and limitations.
- `synthesis/` pages include a cross-paper comparison matrix.
- `concepts/` pages are reusable concept pages, not one paper retitled as a concept.

If lint fails, repair staged pages before recording ingest completion.
