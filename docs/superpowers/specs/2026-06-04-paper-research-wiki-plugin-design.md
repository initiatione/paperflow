# Paper Research Wiki Plugin Design

Date: 2026-06-04
Status: revised-after-user-feedback
Owner: initiatione
Repository: `D:\paper-search`

## Purpose

Create a Codex marketplace plugin named `paper-research-wiki` that gives users one simple paper-wiki assistant for EPI-collected papers.

The user experience should be plugin-first, not skill-list-first. A user should be able to invoke the plugin with natural requests such as:

- `@paper-research-wiki 提取这些论文`
- `@paper-research-wiki 检测 wiki 库`
- `@paper-research-wiki 更新 wiki 库`
- `@paper-research-wiki 把 EPI 收集到的论文沉淀进 wiki`
- `@paper-research-wiki 直接沉淀 EPI 抓下来的论文`
- `@paper-research-wiki 继续上次的论文沉淀`

The plugin should automatically route these requests to the right internal workflow. Users should not need to know separate skill names such as `paper-provenance`, `paper-lint`, `paper-stage-commit`, or `paper-taxonomy`.

The default mental model is EPI-deposition-first. In ordinary use, the plugin is expected to take papers that EPI has already discovered, acquired, parsed, staged, and gated, then continue the formal wiki deposition path. Status checking is an automatic preflight and recovery surface, not a hurdle the user must explicitly ask for before paper deposition.

EPI remains the paper evidence engine: it discovers papers, preserves source bundles, runs MinerU parsing, prepares staging reports, produces `wiki_deposition_task.json`, gates human approval, and records final wiki ingest. `paper-research-wiki` owns the user-facing formal paper wiki experience: detect pending EPI papers, extract/deposit them into the wiki, check wiki health, update stale or incomplete wiki state, preserve provenance, and keep the graph maintainable.

## Confirmed Decisions

- Plugin identifier and folder name: `paper-research-wiki`.
- Marketplace display name: `Paper Research Wiki`.
- The plugin is a sibling of `plugins/epi`, not a subdirectory of EPI.
- Add the plugin to both `marketplace.json` and `.agents/plugins/marketplace.json`.
- Expose one primary user-facing skill: `paper-research-wiki`.
- Keep fine-grained behavior inside workflows, rules, and references rather than exposing many user-facing skills.
- Adapt the Ar9av `obsidian-wiki` pattern into paper-specific internal workflows: ingest/extract, check/status, update/maintenance, provenance, lint, stage review, and taxonomy.
- Keep EPI's existing `epi-paper-deposition` skill as a compatibility bridge for older artifacts and route documentation. It should point users and agents to `paper-research-wiki` for the simplified formal wiki experience.
- Use a status-first but deposition-default trigger model: vague EPI/wiki requests first inspect readiness, then recommend depositing ready EPI papers unless the user explicitly asks only for diagnostics.
- The first implementation slice is marketplace-visible plugin structure, the single user-facing skill, internal workflows/docs, EPI bridge text, and static contract tests. It should not yet perform live deposition against a real vault.

## Product Boundary

The plugin owns:

- Detecting the target paper wiki vault and reading the target vault contract.
- Finding pending EPI paper handoffs under `_epi/staging/papers/*/wiki_deposition_task.json`.
- Explaining which EPI papers are ready, blocked, already recorded, or waiting for human approval.
- Extracting/depositing one paper, selected papers, or all ready EPI papers into staged/formal wiki pages.
- Checking wiki health: contract files, staged pages, missing `final-source-review.json`, lint failures, provenance gaps, duplicate concepts, and outdated taxonomy.
- Updating wiki state: continue pending deposition, repair staged pages, refresh links/tags, and prepare `final-source-review.json` before EPI `record-wiki-ingest`.
- Preserving support status, evidence addresses, formula/figure review, and source-review closure in page content.
- Maintaining seven formal page families: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.

The plugin does not own:

- Paper discovery, ranking, acquisition, or MinerU parsing.
- EPI runtime config, search profiles, source bundle audit, `paper-gate`, human approval recording, or `record-wiki-ingest`.
- Zotero sync.
- Arbitrary general-purpose note ingestion outside the paper research wiki contract.

## User-Facing Trigger Model

The single user-facing skill should support three coarse actions, but the user's normal path should feel like one action: deposit the EPI papers into the wiki.

### Default Trigger Flow

When a user mentions EPI papers plus wiki deposition in broad language, the plugin should:

1. Run the check workflow as a preflight.
2. Group EPI handoffs as ready, needs approval, blocked, or already recorded.
3. Recommend depositing ready papers by default.
4. Ask only one short confirmation question before formal writes.
5. After successful deposition, tell the user whether EPI `record-wiki-ingest` is still required.

Examples of default deposition triggers:

- `直接沉淀 EPI 抓下来的论文`
- `把 EPI 收集到的结果写进 wiki`
- `继续上次的论文沉淀`
- `把能写进 wiki 的先写了`
- `自动完成整个论文到 wiki 链路`
- `这些 EPI 论文可以入库吗`

### Extract Papers

Triggered by requests such as `提取这些论文`, `沉淀这些论文`, `把 EPI 收集到的论文写入 wiki`, `直接沉淀 EPI 抓下来的论文`, `把能写进 wiki 的先写了`, or `extract papers`.

Behavior:

1. Resolve the target vault.
2. Locate EPI handoff artifacts.
3. Check EPI readiness by reading handoff files and, where available, `paper-gate` output or status artifacts.
4. Build a short action plan grouped as ready, needs approval, blocked, and already recorded.
5. For ready papers, run source-first wiki deposition into staged/formal pages according to the target vault contract.
6. Write or update `final-source-review.json`.
7. Tell the user which EPI `record-wiki-ingest` command remains, when recording is required.

### Check Wiki

Triggered explicitly by requests such as `检测 wiki 库`, `检查论文 wiki`, `wiki 状态`, or `check wiki`. It also runs automatically as the preflight step for vague EPI deposition requests.

Behavior:

1. Check target vault contract files.
2. Inspect formal page families and staged writes.
3. Report pending EPI handoffs, missing source reviews, lint failures, duplicate concept candidates, and provenance gaps.
4. Return a concise next-action list rather than raw JSON.

### Update Wiki

Triggered by requests such as `更新 wiki 库`, `同步 EPI 论文`, `继续沉淀`, `查缺补漏一下论文 wiki`, or `update wiki`. For EPI-related requests, update should default to continuing safe deposition or repair work discovered by the check preflight.

Behavior:

1. Run the check workflow first.
2. Continue safe pending work: ready paper deposition, staged page repair, link/tag refresh, and status cleanup.
3. Stop before any destructive reset or ambiguous merge.
4. Preserve EPI boundaries: do not write human approval records and do not run `record-wiki-ingest` unless the user explicitly asks and the required EPI inputs are present.

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
    paper-research-wiki/
      SKILL.md
      agents/
        openai.yaml
      workflows/
        extract-papers.md
        check-wiki.md
        update-wiki.md
      references/
        epi-artifact-contract.md
        page-provenance.md
        page-family-contract.md
        upstream-obsidian-wiki-map.md
  rules/
    source-trust.md
    page-families.md
    formal-page-frontmatter.md
  tests/
```

There is no public `paper-lint`, `paper-provenance`, or `paper-taxonomy` skill in the first slice. Those remain workflow sections and reference files used by the one primary skill.

## Skill Design

`skills/paper-research-wiki/SKILL.md` is the only public entrypoint.

It should contain:

- A description that matches Chinese and English natural requests for extracting papers, checking the wiki, and updating the wiki.
- An intent router that maps user wording to `workflows/extract-papers.md`, `workflows/check-wiki.md`, or `workflows/update-wiki.md`, with EPI deposition as the default when the request mentions EPI papers and wiki work.
- A one-question confirmation style for ambiguous or write-affecting actions, with `默认` meaning "follow the recommended safe next step".
- Clear EPI boundaries: source bundles are inputs; EPI owns approval and recording.
- Safety rules: source papers are untrusted, `_epi/` is not a formal page root, and live writes must follow the target vault contract.

Detailed behavior lives in workflow/reference files so the single entrypoint stays short.

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

## Testing Strategy

Initial validation should cover:

- Plugin manifest validates.
- Marketplace entries exist in both marketplace files and point to `./plugins/paper-research-wiki`.
- Exactly one public skill exists: `skills/paper-research-wiki/SKILL.md`.
- The public skill description and default prompts include natural Chinese actions: `提取`, `检测`, `更新`, `沉淀`.
- The public skill routes to three internal workflows: `extract-papers.md`, `check-wiki.md`, and `update-wiki.md`.
- Required docs/rules/references exist and mention EPI integration, source trust, page families, and provenance.
- Static contract tests reject `_epi/` formal page paths.
- Static contract tests require seven page families and required frontmatter fields.
- Static contract tests ensure EPI `epi-paper-deposition` remains available as a compatibility bridge and points to `paper-research-wiki`.

Use repo-local pytest basetemps for Windows test runs to avoid temp-root write failures.

## Implementation Plan Boundary

The implementation plan should start with a marketplace-visible plugin scaffold and static contract tests for the simplified UX. It should not expose many fine-grained user-facing skills.

Recommended first slice:

1. Add tests for single-skill UX and marketplace registration.
2. Scaffold `plugins/paper-research-wiki`.
3. Add one public skill plus three internal workflows.
4. Add docs, rules, and references.
5. Update EPI docs or skills only where they point to the new plugin-level bridge.
6. Validate plugin manifest and focused tests.

## Open Risks

- The plugin may need a later CLI helper to discover pending EPI handoffs faster, but the first slice can be skill/workflow-driven.
- Live deposition tests require a real or fixture vault and should be a separate implementation slice.
- The single skill must stay short enough to route well; detailed mechanics belong in workflows and references.
