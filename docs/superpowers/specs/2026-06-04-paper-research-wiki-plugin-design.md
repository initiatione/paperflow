# Paper Research Wiki Plugin Design

Date: 2026-06-04
Status: approved-for-planning
Owner: initiatione
Repository: `D:\paper-search`

## Purpose

Create a Codex marketplace plugin named `paper-research-wiki` for formal academic paper knowledge deposition and maintenance. The plugin adapts the Ar9av `obsidian-wiki` skill pattern into a paper-specific, EPI-compatible wiki layer.

EPI remains the paper evidence engine: it discovers papers, preserves source bundles, runs MinerU parsing, prepares staging reports, produces `wiki_deposition_task.json`, gates human approval, and records final wiki ingest. `paper-research-wiki` owns the formal wiki writing and maintenance layer: source-first page creation, existing-page merge decisions, provenance-preserving claim writing, lint, staged review, taxonomy, cross-linking, status, and long-term graph maintenance.

## Confirmed Decisions

- Plugin identifier and folder name: `paper-research-wiki`.
- Marketplace display name: `Paper Research Wiki`.
- The plugin is a sibling of `plugins/epi`, not a subdirectory of EPI.
- Add the plugin to both `marketplace.json` and `.agents/plugins/marketplace.json`.
- Use the `skill-based-architecture` layout style: short router, explicit `routing.yaml`, split rules, workflows, and references.
- Do not copy all upstream `obsidian-wiki` skills. Transplant the pattern and the relevant wiki operations into a lean paper-specific skill set.
- Keep EPI's existing `epi-paper-deposition` skill as a compatibility bridge for older artifacts and route documentation. Formal deposition behavior should move into `paper-research-wiki`.
- The first implementation slice is source/plugin structure, marketplace registration, skill routing, docs, and static contract tests. It should not yet perform live paper deposition.

## Source Patterns

The design draws from three source layers:

- Ar9av `obsidian-wiki`: agent-mediated LLM Wiki pattern, manifest/index/log style, ingest/query/lint/status/stage workflows, and staged writes.
- `skill-based-architecture`: compact `SKILL.md`, route source of truth in `routing.yaml`, and progressive disclosure through `rules/`, `workflows/`, and `references/`.
- Current EPI plugin contract: EPI writes `_epi/raw` and `_epi/staging` evidence artifacts and delegates final pages to a wiki-capable layer.

The new plugin should preserve these boundaries instead of turning EPI into a general wiki engine or vendoring the full upstream wiki framework.

## Product Boundary

The plugin owns:

- Reading `wiki_deposition_task.json` and related EPI handoff artifacts.
- Resolving the target vault contract from `AGENTS.md` and `_meta/*`.
- Building context packs from existing formal pages before writing.
- Creating or updating formal paper wiki pages.
- Preserving support status, evidence addresses, and source-review closure in page content.
- Maintaining seven formal page families: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
- Linting staged/formal pages before EPI `record-wiki-ingest`.
- Maintaining paper wiki status, taxonomy, tags, aliases, deduplication, and cross-links.

The plugin does not own:

- Paper discovery, ranking, acquisition, or MinerU parsing.
- EPI runtime config, search profiles, or source bundle audit.
- Human approval recording.
- EPI `record-wiki-ingest`.
- Zotero sync.
- Arbitrary general-purpose note ingestion outside the paper research wiki contract.

## Plugin Layout

Target layout:

```text
plugins/paper-research-wiki/
  .codex-plugin/
    plugin.json
  AGENTS.md
  docs/
    workflow.md
    structure.md
    epi-integration.md
    provenance.md
    privacy.md
    terms.md
  skills/
    routing.yaml
    paper-wiki-setup/
      SKILL.md
    paper-deposition/
      SKILL.md
      workflows/
        formal-paper-write.md
    paper-provenance/
      SKILL.md
      references/
        page-provenance.md
    paper-context-pack/
      SKILL.md
    paper-lint/
      SKILL.md
    paper-stage-commit/
      SKILL.md
    paper-status/
      SKILL.md
    paper-taxonomy/
      SKILL.md
  rules/
    source-trust.md
    page-families.md
    formal-page-frontmatter.md
  workflows/
    epi-deposition.md
    staged-review.md
    maintenance-cycle.md
  references/
    upstream-obsidian-wiki-map.md
    epi-artifact-contract.md
    skill-routing.md
  tests/
```

`skills/routing.yaml` is the source of truth for skill routing. `AGENTS.md` is a thin shell pointing agents to the plugin skill router and the target vault contract resolution order.

## Skill Set

`paper-deposition` is the primary EPI handoff skill. It loads `wiki_deposition_task.json`, `wiki-ingest-brief.json`, the reading report, metadata, PDF, MinerU Markdown, TeX, images, and manifest. It then resolves the target vault contract and writes staged or formal pages according to the paper wiki rules.

`paper-provenance` preserves claim support labels and evidence routes. It distinguishes `source-grounded`, `metadata-only`, `inferred`, and `unsupported` claims, and requires source-review closure before final lifecycle promotion.

`paper-context-pack` searches existing formal pages before writing. It prevents duplicate pages and gives `paper-deposition` a compact view of related concepts, prior synthesis pages, and possible contradictions.

`paper-lint` statically checks frontmatter, allowed page families, provenance blocks, wikilinks, forbidden internal roots, formula formatting, and family-specific requirements.

`paper-stage-commit` promotes staged writes after human review when the target vault uses staged writes.

`paper-status` summarizes pending staged pages, recently deposited papers, lint failures, missing source reviews, and unresolved provenance gaps.

`paper-taxonomy` maintains tags, aliases, page-family vocabulary, cross-links, and deduplication decisions.

`paper-wiki-setup` initializes or repairs the formal paper wiki contract files without touching EPI runtime config.

## EPI Artifact Contract

The plugin consumes these EPI artifacts:

```text
<vault>/_epi/staging/papers/<slug>/wiki_deposition_task.json
<vault>/_epi/staging/papers/<slug>/wiki-ingest-brief.json
<vault>/_epi/staging/papers/<slug>/briefs/reading-report.md
<vault>/_epi/raw/papers/<slug>/metadata.json
<vault>/_epi/raw/papers/<slug>/paper.pdf
<vault>/_epi/raw/papers/<slug>/mineru/<slug>.md
<vault>/_epi/raw/papers/<slug>/mineru/paper.tex
<vault>/_epi/raw/papers/<slug>/mineru/images/*
<vault>/_epi/raw/papers/<slug>/mineru/mineru-manifest.json
```

Optional aids include reader evidence maps, claim support JSON, critic reports, and `wiki-agent-trigger.json`. They lower reading cost but do not replace the source paper bundle.

The plugin writes or prepares formal wiki pages and `final-source-review.json`. EPI remains responsible for `record-wiki-ingest`, which records final page paths, hashes, approval metadata, and source review results.

## Data Flow

```text
EPI discovery and preparation
  -> _epi/raw source bundle
  -> _epi/staging/wiki_deposition_task.json
  -> paper-research-wiki paper-deposition
  -> source-first staged/formal pages
  -> paper-lint and paper-provenance checks
  -> final-source-review.json
  -> EPI record-wiki-ingest
```

This keeps the final write path agent-mediated and target-vault-aware. Suggested routes from EPI are hints; the target vault contract decides final paths, tags, merge policy, and staged writes.

## Formal Page Contract

Every formal page must include frontmatter fields:

```yaml
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
```

Initial lifecycle is `draft` or `review-needed`. Pages cannot be marked `source-reviewed` or `verified` until source reread, formula and figure/table review, lint, and human review have passed.

Formal pages must not be created inside `_epi/`, legacy `_raw/`, legacy `_staging/`, `_runs/`, `_quarantine/`, `.obsidian/`, or other operational roots.

## Error Handling

- Missing required EPI source artifacts stop formal deposition and point the user back to EPI `paper-gate`.
- Missing target vault contract stops writing but may allow a setup/repair recommendation.
- Existing-page ambiguity produces staged patches or review-needed pages instead of overwriting live pages.
- Unsupported or inference-only claims cannot enter main factual prose.
- Lint failures block `record-wiki-ingest` readiness.
- The plugin does not delete raw source bundles or final pages during first-version workflows.

## Testing Strategy

Initial validation should cover:

- Plugin manifest validates.
- Marketplace entries exist in both marketplace files and point to `./plugins/paper-research-wiki`.
- Skill bundle contains all routed skills.
- `skills/routing.yaml` references existing skill files and workflows.
- Required docs exist and mention EPI integration, source trust, page families, and provenance.
- Static contract tests reject `_epi/` formal page paths.
- Static contract tests require seven page families and required frontmatter fields.
- Static contract tests ensure `paper-deposition` consumes `wiki_deposition_task.json` and `wiki-ingest-brief.json`.
- Static contract tests ensure EPI `epi-paper-deposition` remains available as a compatibility bridge after any later EPI edits.

Use repo-local pytest basetemps for Windows test runs to avoid temp-root write failures.

## Implementation Plan Boundary

The implementation plan should start with a marketplace-visible plugin scaffold and static contract tests. It should not attempt live deposition until the plugin structure, docs, route contracts, and EPI compatibility bridge are in place.

Recommended first slice:

1. Scaffold `plugins/paper-research-wiki`.
2. Add marketplace entries.
3. Add skill router and first-pass skills/docs.
4. Add contract tests.
5. Validate plugin manifest and focused tests.
6. Update EPI docs or skills only where they point to the new bridge boundary.

## Open Risks

- Upstream `obsidian-wiki` can change quickly. This plugin should document what was adapted instead of trying to mirror every upstream skill.
- The plugin may overlap with globally installed wiki skills. The first implementation should use paper-specific skill names to avoid accidental routing collisions.
- If EPI artifacts change schema, the new plugin needs a compatibility layer rather than direct ad hoc reads.
- Live deposition tests require a real or fixture vault and should be a later implementation slice.
