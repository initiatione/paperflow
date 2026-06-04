---
name: epi-paper-deposition
description: >
  Use when turning EPI source bundles or wiki_deposition_task.json files into
  formal Obsidian/LLM Wiki staging pages, including "沉淀进 wiki",
  "写正式论文 wiki 页面", EPI handoff, wiki ingest trigger, final paper deposition,
  formula derivation page, synthesis page, or seven-family EPI paper wiki writing.
---

# EPI Paper Deposition

Use this skill at the boundary where EPI stops being a paper evidence engine and the wiki layer starts writing formal knowledge. EPI Core prepares source bundles and audit artifacts under `_epi/`; those internal audit artifacts must not enter the formal graph. This adapter reads `wiki_deposition_task.json` and coordinates the formal wiki skills.

Compatibility note: older EPI artifacts may say `epi-wiki-deposition`. Treat that as an alias for this skill.

Preferred user experience: when the `prw` plugin package (`plugins/PRW`) is installed, route formal paper wiki work through `$paper-research-wiki`. Users should be able to ask it to `提取` EPI papers, `检测` the wiki library, `更新` the wiki library, or `重link` paper knowledge without choosing internal workflow names. This EPI skill remains a compatibility bridge for existing `wiki_deposition_task.json` artifacts.

## Workflow Routing

| Intent | Load |
| --- | --- |
| Stage or write formal wiki pages from `wiki_deposition_task.json` | `workflows/formal-wiki-write.md` |
| Preserve final claim support labels, evidence addresses, and source-review closure | `wiki-provenance/SKILL.md` |
| Check existing related pages before writing | `wiki-context-pack`, then `wiki-query` or `wiki-status` |
| Lint, stage-commit, or human-review final pages | `wiki-lint` and `wiki-stage-commit` |

## Required Inputs

Before writing, the formal workflow must load `wiki_deposition_task.json`, `wiki-ingest-brief.json`, the staged reading report, raw metadata/PDF, MinerU Markdown/TeX/images/manifest, and the target vault `AGENTS.md` plus `_meta/*` contract files.

Reader and critic files reduce reading cost when present. They are not source authority.

## Skill Stack

Use the obsidian-wiki layer explicitly: `llm-wiki`, `wiki-context-pack`, `wiki-ingest`, `wiki-lint`, `wiki-stage-commit`, `wiki-status`, `wiki-query`, `wiki-provenance`, and `tag-taxonomy`.

Quality enhancement skills such as `wiki-synthesize`, `wiki-dedup`, and `cross-linker` are useful after the first staged pages exist.

## Page Family Boundary

Formal deposition may land in `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`, chosen by the target vault contract and the wiki agent.

Do not create generic `entities/`, `skills/`, `journal/`, or `projects/` pages for formal EPI deposition unless the target vault contract explicitly routes a secondary copy there.

## Frontmatter And Quality Gates

Every formal page must include frontmatter fields `title`, `category`, `page_family`, `tags`, `aliases`, `sources`, `summary`, `provenance`, `base_confidence`, `lifecycle`, `lifecycle_changed`, `tier`, `created`, and `updated`. Initial lifecycle is `draft` or `review-needed`; do not mark pages `source-reviewed` or `verified` until source review and lint gates pass.

Before `record-wiki-ingest` or `wiki-stage-commit`, verify provenance, Obsidian wikilinks, source bundle paths, page-family/category alignment, no `_epi/` formal pages, no forbidden formula blocks, derivation variable definitions and derivation chain, reference model/formula/experiment/limit coverage, and synthesis cross-paper comparison matrix. Internal `_epi/` pages must not enter the formal graph. If lint fails, repair staged pages before recording ingest completion.
