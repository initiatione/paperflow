# EPI/PRW Brief-Canonical Boundary Design

- Date: 2026-06-07
- Status: Design ready for user review
- Scope: EPI/PRW boundary contract, canonical handoff artifact, and legacy deposition-task migration
- Decision: use scheme 3, one-step boundary convergence

## Purpose

This design optimizes the EPI and PRW workflow by making the handoff boundary explicit and machine-verifiable. The current system already says PRW is the canonical paper wiki writing layer, but EPI still emits and tests a broader required wiki stack and still treats `wiki_deposition_task.json` as a normal required handoff artifact. That keeps old and new models alive at the same time.

The new model is brief-first:

- EPI owns paper discovery, ranking, PDF acquisition, MinerU parsing, source staging, human approval, trigger artifacts, gate checks, and `record-wiki-ingest` record writes.
- PRW `$paper-research-wiki` owns formal paper wiki page writing and maintenance.
- `_epi/staging/papers/<slug>/wiki-ingest-brief.json` is the canonical EPI-to-PRW handoff artifact.
- `_epi/staging/papers/<slug>/wiki_deposition_task.json` becomes a legacy compatibility artifact, not a new-flow required artifact.
- `epi-paper-deposition` becomes a thin compatibility alias for legacy task names and historical `epi-wiki-deposition` mentions.

## Goals

1. Make `wiki-ingest-brief.json` the only required new-flow handoff artifact for PRW formal wiki deposition.
2. Stop requiring `wiki_deposition_task.json` in new EPI gate, handoff, trigger, and PRW preflight paths.
3. Preserve compatibility with existing `wiki_deposition_task.json` files and historical records.
4. Collapse EPI's required wiki skill stack to the actual boundary: `paper-research-wiki` plus `epi-paper-deposition`.
5. Reclassify external wiki skills and upstream repositories as optional helpers, quality enhancers, or design references.
6. Keep PRW's current formal-page writing standard unchanged.
7. Update tests and docs so the machine contract, skill docs, workflow docs, and plugin manifests agree.

## Non-Goals

- Do not rewrite existing formal pages in `D:\paper-research-wiki`.
- Do not weaken PRW page families, frontmatter, clickable PDF source links, provenance, language gate, graph-aware rewrite, or post-task check requirements.
- Do not refactor large Python modules such as `orchestrator.py`, `stage_wiki.py`, or `wiki_ingest_record.py` beyond scoped contract changes.
- Do not implement critic redo loops, `redo-until-pass`, or broader automation features in this phase.
- Do not change paper acquisition, PDF identity checks, MinerU parsing, source bundle audit, or manual-download behavior.
- Do not remove legacy artifact reading. Historical staging folders and records must remain interpretable.

## Locked Decisions

| Topic | Decision |
| --- | --- |
| Canonical write layer | PRW `$paper-research-wiki` is the single user-facing formal paper wiki writing and maintenance layer. |
| Canonical handoff | `wiki-ingest-brief.json` is the required EPI-to-PRW handoff for new flows. |
| Legacy handoff | `wiki_deposition_task.json` is legacy-compatible, optional, and no longer required for new ready checks. |
| Legacy generation | EPI defaults to not writing new `wiki_deposition_task.json`; an explicit legacy option may emit it for compatibility tests or migrations. |
| Required skills | `REQUIRED_WIKI_SKILLS = ("paper-research-wiki", "epi-paper-deposition")`. |
| External wiki skills | `llm-wiki`, `wiki-ingest`, `wiki-context-pack`, `wiki-lint`, `wiki-stage-commit`, `wiki-status`, `wiki-query`, `wiki-provenance`, `tag-taxonomy`, `wiki-synthesize`, `wiki-dedup`, and `cross-linker` are optional helpers, policy references, or quality enhancers. Their policies may remain required by PRW standards, but invoking those skills is not a runtime prerequisite. |
| PRW writing standard | Keep current PRW formal-page logic and quality gates. This phase changes task intake and boundary contract, not page-writing semantics. |

## Target Data Flow

1. EPI runs `dry-run`, `prepare-ranked`, `advance-*`, `ingest-one`, or related ingest commands.
2. EPI creates source artifacts under `_epi/raw/<slug>/`: `paper.pdf`, `metadata.json`, MinerU Markdown, TeX, images, manifest, parse records, and optional evidence indexes.
3. EPI creates source-staging artifacts under `_epi/staging/papers/<slug>/`: Chinese approval report, `promotion-plan.json`, and canonical `wiki-ingest-brief.json`.
4. New EPI flows do not write `wiki_deposition_task.json` by default.
5. `paper-gate` treats a complete brief plus complete source bundle as the machine handoff prerequisite. Missing `wiki_deposition_task.json` is not a failure.
6. After human approval, `wiki-ingest-trigger` writes a resume artifact that explicitly routes the current slug or brief to PRW `$paper-research-wiki`.
7. PRW reads `wiki-ingest-brief.json` first, checks source bundle and target vault contract, then writes or stages formal pages under the existing PRW writing rules.
8. PRW writes `final-source-review.json` and, for ask-mode automation, `prw-record-request.json`.
9. EPI `record-wiki-ingest` consumes direct page arguments or `--from-prw-request`, validates live pages and source-review closure, and writes EPI record sidecars.
10. If an old `wiki_deposition_task.json` exists, EPI may record its path and hash as a legacy sidecar, but it is not used to prove new-flow readiness.

## Artifact Contract

### `wiki-ingest-brief.json`

The brief is the canonical handoff. It must contain enough information for PRW or another wiki-capable agent to write final pages without reading a second task file:

- `schema_version: epi-wiki-ingest-brief-v1`
- `handoff_type: agent-mediated-wiki-ingest`
- source bundle paths and hashes where available
- target vault path and vault-contract pointers
- suggested page routes as non-authoritative hints
- `ingest_policy.required_wiki_skills` with only PRW and EPI compatibility adapter
- optional helper/reference skill lists
- `wiki_rule_source_model` with PRW as canonical execution layer
- `execution_agent_policy` allowing Claude, Codex, or another wiki-capable agent under the same vault contract
- formal page families and frontmatter schema for EPI validation
- source-first review requirements
- `final_source_review_contract`
- QMD boundary policy
- human approval and `record-wiki-ingest` next-step expectations

If the brief is missing, PRW must not treat a new EPI deposition task as ready. The correct response is to route back to EPI to regenerate or repair the brief.

### `wiki_deposition_task.json`

The task file is legacy-compatible only:

- Existing files remain readable.
- EPI may emit it only through an explicit legacy option or dedicated compatibility test path.
- PRW can use it to recover context when a historical handoff lacks a brief, but it must mark the path as legacy and avoid treating it as canonical readiness evidence.
- `record-wiki-ingest` may record its path and hash if present.
- Missing task files must not block `paper-gate`, `wiki-ingest-handoff`, `wiki-ingest-trigger`, PRW preflight, or `record-wiki-ingest` when the brief and source review are complete.

## Skill Stack Model

EPI's machine contract becomes small and stable:

```python
REQUIRED_WIKI_SKILLS = (
    "paper-research-wiki",
    "epi-paper-deposition",
)
```

External skills are not required runtime dependencies. They can be grouped as:

- Optional execution helpers: `llm-wiki`, `wiki-ingest`, `wiki-context-pack`, `wiki-status`, `wiki-query`.
- Optional verification helpers: `wiki-lint`, `wiki-stage-commit`, `wiki-provenance`, `tag-taxonomy`.
- Optional graph-quality enhancers: `wiki-synthesize`, `wiki-dedup`, `cross-linker`.
- Upstream design references: `Ar9av/obsidian-wiki`, `kepano/obsidian-skills`, and `initiatione/obsidian-wiki-dev` wiki-skills.

Important distinction: some policies are still mandatory even when a standalone skill is optional. For example, source provenance, PDF-only `sources`, tag discipline, and lint-like checks remain mandatory because PRW has internalized those policies in `rules/wiki-writing-standard.md` and related workflows.

## PRW Scope

PRW changes in this phase are task-intake and boundary changes only.

PRW will update:

- `paper-research-wiki/references/epi-artifact-contract.md` to say brief is canonical and task is legacy.
- `extract-papers.md`, `check-wiki.md`, and `epi-integration.md` to use brief-first ready checks.
- `paper-research-wiki/SKILL.md` boundary wording so users do not choose internal skills.
- PRW tests that assert EPI handoff semantics.

PRW will not update:

- Seven page families.
- Required formal frontmatter fields.
- Clickable original-paper PDF source-link contract.
- Provenance extracted/inferred/ambiguous model.
- Chinese formal page language gate.
- Graph-aware rewrite obligations.
- Post-task check requirements.
- Existing formal pages in the vault.

## EPI Component Changes

### `wiki_contracts.py`

- Shrink `REQUIRED_WIKI_SKILLS` to PRW plus EPI compatibility adapter.
- Move external skills into optional/helper/enhancement lists.
- Keep formal page family and frontmatter constants for EPI execution validation.
- Add a short code comment that PRW writing-standard docs are the human-readable canonical source and EPI constants are validation mirrors.

### `stage_wiki.py`

- Keep building complete `wiki-ingest-brief.json`.
- Stop writing `wiki_deposition_task.json` by default.
- Add an explicit legacy-generation option if current CLI/test seams require one.
- Ensure generated promotion plans, source-review contracts, brief paths, and reports identify the brief as canonical.
- Update `wiki_rule_source_model` so PRW appears before external references and external skills are optional/reference, not required execution layers.

### `paper_gate.py`

- Remove missing `wiki_deposition_task.json` as a failure condition for agent-mediated wiki ingest.
- Keep failure when `wiki-ingest-brief.json`, source bundle, `wiki_rule_source_model`, execution agent policy, human approval, or source-review contract is missing or incomplete.
- Keep formal page validation strict after PRW writes pages.

### `wiki_ingest_handoff.py` and `wiki_ingest_trigger.py`

- Render PRW as the next action: invoke `$paper-research-wiki` with the slug/brief.
- Include brief path prominently.
- Mention legacy task only if present.
- Do not instruct users to load the external wiki stack as required.

### `wiki_ingest_record.py`

- Accept final reviews whose `wiki_skill_used` satisfies the new required stack.
- Preserve optional recording of external helpers when present.
- Record existing legacy task sidecar path/hash if present.
- Continue validating final pages, `final-source-review.json`, approval identity, source bundle hashes, frontmatter, provenance, page-family gates, forbidden roots, and formula-block rules.

### EPI Skill Docs

- `paper-ingest`, `wiki-provenance`, `wiki-setup`, and `epi-paper-deposition` docs must align with the brief-first boundary.
- `epi-paper-deposition` should become a short compatibility adapter. It routes legacy task files and legacy `epi-wiki-deposition` mentions to PRW, and does not duplicate PRW writing rules.

## Error Handling And Migration

| State | Behavior |
| --- | --- |
| New staging has brief and no task | Normal. Gate can pass if all other checks pass. |
| New staging lacks brief | Failure. Route back to EPI to regenerate/repair brief. |
| Old staging has task and brief | Use brief as canonical. Record task as legacy sidecar if relevant. |
| Old staging has task but no brief | Compatibility path only. Report legacy limitation and route to EPI repair/regeneration before formal writes. |
| Brief lists old broad required stack | Treat as old contract. Gate or repair tooling should normalize to new required stack before ready. |
| PRW receives user request with only old `epi-wiki-deposition` wording | Route through `epi-paper-deposition` compatibility alias, then to PRW after brief is available. |

## Documentation Plan

Detailed docs are allowed, but they must not recreate multiple competing contracts.

- EPI `epi-linkage.md`: authoritative end-to-end behavior and boundary model.
- EPI `workflow.md`: operational short entry that points to the authoritative model and names brief-first handoff.
- EPI `structure.md`: module/artifact map, not a second full pipeline spec.
- EPI `progress.md`: current status only, not a long append-only changelog.
- PRW `epi-integration.md`: PRW-facing EPI boundary and record contract.
- PRW `epi-artifact-contract.md`: brief canonical, task legacy.
- PRW `wiki-writing-standard.md`: formal page writing standard remains canonical for page quality.

The implementation plan should avoid broad prose rewrites unless needed to make these boundaries true.

## Test Matrix

### EPI Tests

- `tests/epi/test_wiki_deposition_task.py`
  - New default staging does not require `wiki_deposition_task.json`.
  - Legacy generation option still produces a valid task if retained.
  - Existing compatibility aliases remain recognized.

- `tests/epi/test_wiki_ingest_handoff.py`
  - Required skills equal `paper-research-wiki`, `epi-paper-deposition`.
  - Handoff output points to `wiki-ingest-brief.json` and PRW.
  - External skills appear only as optional/reference if present.

- `tests/epi/test_wiki_ingest_record.py`
  - Final review passes with new required stack.
  - Existing task sidecar is optional.
  - PRW request flow remains record-only.

- `tests/epi/test_paper_gate.py`
  - Missing brief fails.
  - Complete brief without task can pass.
  - Missing execution agent policy, source bundle, or approval still fails.

- `tests/epi/test_one_paper_ingest.py` and batch/router tests
  - Ingest creates canonical brief.
  - Default ingest no longer depends on `wiki_deposition_task.json`.

### PRW Tests

- `tests/paper_research_wiki/test_plugin_contract.py`
  - PRW docs say brief is canonical and task is legacy.
  - PRW preflight uses brief-first readiness.
  - Formal page quality assertions remain unchanged.
  - PRW still does not write EPI human approval or `wiki-ingest-record.json`.

### Docs And Plugin Tests

- EPI docs tests should expect the new required-vs-optional model.
- PRW docs tests should keep upstream repositories as internalized design references, not runtime fetches.
- EPI and PRW plugin validators should pass.
- Marketplace manifests should reflect any version bumps.

## Verification Commands

After implementation, run:

```powershell
python -m pytest tests/epi tests/paper_research_wiki plugins/epi/tests -q
python C:\Users\liuchf\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py D:\paper-search\plugins\epi
python C:\Users\liuchf\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py D:\paper-search\plugins\PRW
```

If the default Python cannot import validator dependencies on this machine, use `D:\MiniConda\python.exe` for validator runs.

## Acceptance Criteria

- A newly staged EPI paper has `wiki-ingest-brief.json` as the canonical handoff.
- New default staging does not require or emit `wiki_deposition_task.json`.
- `paper-gate` can report ready for PRW when brief/source/approval checks pass and task is absent.
- `wiki-ingest-trigger` clearly routes to PRW `$paper-research-wiki`.
- PRW docs and tests recognize brief-first readiness.
- Legacy `wiki_deposition_task.json` remains readable and recordable when present.
- External wiki skills are not required runtime dependencies in generated JSON, gate checks, or final-review pass conditions.
- PRW formal-page quality gates remain as strict as before.
- Full EPI/PRW tests and plugin validation pass.

## Risks

- Existing tests may encode old broad required-skill expectations. Mitigation: update tests first to express the new boundary, then update implementation.
- Some generated reports may still mention `wiki_deposition_task.json` as normal. Mitigation: search all docs, generated strings, and tests for the old artifact wording.
- Old staging folders may be mistaken for new failures. Mitigation: branch behavior by brief presence and task-only legacy state.
- Moving `wiki-provenance` from required skill to optional helper could be misread as weakening provenance. Mitigation: docs and tests must say provenance policy is mandatory through PRW writing standards even when standalone skill invocation is optional.

## Handoff To Implementation Planning

The next step is a dedicated implementation plan. It should sequence work as:

1. Update tests to express brief-first canonical behavior.
2. Update EPI contract constants and generated artifacts.
3. Update gate, handoff, trigger, and record logic.
4. Update PRW intake docs and compatibility wording.
5. Update EPI/PRW documentation and versions.
6. Run focused tests after each cluster, then full verification.

