# Paper Source Research Brief Intake Design

- Date: 2026-06-09
- Status: Approved in conversation for design capture
- Scope: Paper Source research-intake skill, Research Brief artifacts, and discovery integration
- Decision: use scheme 2, `research-grill-me` skill plus `research-brief` CLI plus `dry-run --from-brief`

## Purpose

Paper Source currently has a long-term Research Profile in `_paper_source/meta/paper-source-config.yaml` and a deterministic query planner for `dry-run --query`, but it does not have a first-class way to turn a user's fuzzy research intent into a reusable, inspectable task artifact before search.

This design adds a Research Grill entrypoint that challenges and clarifies a user's research intent into a persisted Research Brief. A Research Brief is task-scoped: it overrides the default Research Profile for the current research task, while the profile fills only missing background preferences.

## Glossary Decisions

These terms are also recorded in `CONTEXT.md`.

| Term | Meaning |
| --- | --- |
| Research Brief | A clarified, task-scoped research intent that Paper Source can use before discovery or tracking. |
| Research Profile | The long-term default research interests, domains, keywords, exclusions, and venue preferences in Paper Source config. |
| Research Grill | The Paper Source conversation entrypoint that challenges and clarifies research intent before a Research Brief is confirmed. |

Avoid calling the artifact `question-refiner output`, `query brief`, `research profile`, or `wiki-ingest brief`. The external `question-refiner` pattern may inspire the questioning workflow, but Paper Source's domain artifact is Research Brief.

## Goals

1. Add a Paper Source primary skill named `research-grill-me`.
2. Persist confirmed research intent as managed Research Brief artifacts.
3. Make Research Briefs override Research Profile values for current-task intent.
4. Keep Research Profile as the default long-term background and soft preference source.
5. Add CLI support to create, validate, and list Research Briefs.
6. Add `dry-run --from-brief` as the formal discovery path.
7. Keep `dry-run --query` as a quick path for one-off search.
8. Record Research Brief path, status, revision, and hash in runs that consume a brief.
9. Prevent Research Briefs from bypassing source-staging or Paper Wiki handoff gates.

## Non-Goals

- Do not make Research Briefs part of the Paper Wiki formal graph.
- Do not let Paper Wiki write formal pages directly from a Research Brief.
- Do not replace Paper Source config or the Research Profile with task briefs.
- Do not build an interactive CLI questionnaire in the first version.
- Do not add delete/archive semantics for confirmed briefs in the first version.
- Do not create a long-term tracking ledger inside Research Briefs.
- Do not add a complex provider-weight DSL for source selection.
- Do not use `academic_search` naming for source scope; Paper Source uses `paper-search-mcp`.

## User Experience

Paper Source routing should separate quick search from formal intake.

Use `research-grill-me` when the user asks to clarify a research direction, plan a research topic, build a literature-review seed, prepare a serious discovery run, initialize topic tracking, or says they are unsure how to search.

Use `paper-discovery` quick path when the user explicitly asks for a quick search, `dry-run`, or a temporary one-off paper list.

If the request is fuzzy but looks like a serious research task, Paper Source should recommend `research-grill-me` and explain that the user can skip it and search directly. If the user insists on direct search, run the quick path and warn that no Research Brief was generated.

`research-grill-me` questioning style:

- Ask one decision point per turn.
- Give a recommended answer each time.
- Explain why the decision affects Paper Source.
- Read config or repository state instead of asking when the answer is discoverable.
- Stop once the minimum complete brief can be produced.
- Do not follow a fixed number of rounds.
- Before creating a confirmed brief, present a Chinese confirmation summary and wait for explicit user confirmation.

## Artifact Layout

Research Briefs are centrally managed under:

```text
_paper_source/research-briefs/YYYYMMDD-<short-topic-slug>/
```

Each brief directory contains:

```text
research-brief.json
research-brief.md
agent-brief.md
revisions/
```

File roles:

- `research-brief.json` is the canonical machine artifact.
- `research-brief.md` is the Chinese user-facing brief. It may keep necessary English terms, venue names, datasets, and search keywords.
- `agent-brief.md` is fully English and is written for later agent handoff.
- `revisions/` stores historical snapshots when a confirmed brief is revised.

Directory slug rules:

- Default slug format is `YYYYMMDD-<short-topic-slug>`.
- Users may override the slug.
- Slugs must be lowercase ASCII kebab-case.
- Chinese titles live in `title`, not in the directory name.
- Slug conflicts fail by default; the command must not overwrite an existing brief directory.

## State Model

Research Brief status values:

- `draft`: still being clarified; can be overwritten.
- `confirmed`: explicitly confirmed by the user and valid for formal `--from-brief` runs.
- `superseded`: replaced by a revision or fork and not recommended for new runs.

Default `dry-run --from-brief` accepts only `confirmed` briefs. Draft briefs require an explicit override such as `--allow-draft-brief`; draft use must be marked in run state and command output.

Confirmed briefs must not be silently modified in place. A small revision creates a snapshot under `revisions/`, updates the main JSON, increments `revision_number`, and records `supersedes_hash`. A substantial topic change creates a new brief directory.

## Schema Shape

The first version of `research-brief.json` should include:

```json
{
  "schema_version": "paper-source-research-brief-v1",
  "status": "confirmed",
  "slug": "20260609-auv-current-disturbance-control",
  "title": "AUV strong-current disturbance control",
  "task": "...",
  "domain_scope": "...",
  "specific_questions": [],
  "keywords": [],
  "exclusions": [],
  "review_policy": {
    "type": "exclude"
  },
  "source_scope": {
    "type": "paper_search_mcp_default",
    "notes": ""
  },
  "output_goal": {
    "type": "reading_priority_list",
    "notes": ""
  },
  "unknowns": [],
  "field_sources": {},
  "created_at": "...",
  "updated_at": "...",
  "revision_number": 1
}
```

Minimum completeness:

- `task` must be explicit.
- `domain_scope` must be explicit and contain at least one searchable anchor.
- `output_goal.type` must be explicit.
- `review_policy.type` must be explicit, even when the value comes from Paper Source defaults.

Fields may be `unknown` if explicitly recorded:

- `timeframe`
- `source_scope`
- `venue_prior`
- `specific_questions`
- `quality_signals`
- `exclusions`

`field_sources` records provenance for important fields:

- `user_confirmed`: user explicitly confirmed this value.
- `brief_default`: Research Grill applied a Paper Source default.
- `profile_fill`: Research Profile filled a missing value.
- `unknown`: not yet determined.

Do not inflate the brief with a full config snapshot. Keep provenance compact.

## Review Policy

Use a three-state review policy:

- `exclude`: exclude review, survey, systematic review, literature review, and meta-analysis candidates unless exact lookup or user intent overrides it.
- `include`: user explicitly asks for reviews/surveys/systematic reviews.
- `mixed`: user wants both method papers and review/survey papers.

The source of this value matters. A default exclusion inherited from Paper Source policy must not be presented as user-confirmed.

## Output Goal

Use an enum plus freeform notes:

- `reading_priority_list`: produce an ordered reading list.
- `source_staging_candidates`: find papers intended for later PDF/MinerU/source-staging.
- `literature_review_seed`: seed a literature review or direction map.
- `topic_tracking_seed`: initialize topic tracking with this brief as an input anchor.
- `fact_check_sources`: verify a claim or existing hypothesis with paper evidence.

## Source Scope

Use a light source-scope enum, not a provider DSL:

- `paper_search_mcp_default`: Paper Source default multi-source discovery through `paper-search-mcp`.
- `paper_search_mcp_oa_priority`: use `paper-search-mcp` while emphasizing open-access and downloadable PDF availability.
- `known_paper_lookup`: DOI, arXiv ID, or exact title lookup.
- `venue_or_publisher_targeted`: user provided target venue, journal, publisher, or proceedings.
- `manual_sources_provided`: user will provide local PDFs, URLs, or source files.

Known single-paper lookup does not force Research Grill. If the user wants to find or advance a known paper, use existing exact lookup or ingest paths. Use Research Brief only when a known paper becomes an anchor for a broader research direction.

## Profile And Brief Precedence

For current-task behavior:

1. Research Brief values are hard constraints and current intent.
2. Research Profile fills missing background preferences.
3. Profile-derived preferences can affect ranking only when they do not violate the brief.

Examples:

- If the brief asks for aircraft control reviews, an AUV-heavy Research Profile must not pull the search back to AUV.
- If the brief has no venue prior, the Research Profile may provide venue priors.
- If two candidates equally satisfy the brief, profile fit may break ties.

## CLI Surface

Add a `research-brief` command group with four first-version operations:

```powershell
python scripts\orchestrator.py research-brief create --answers-json <file> --vault <vault>
python scripts\orchestrator.py research-brief validate --brief <research-brief.json> --json
python scripts\orchestrator.py research-brief list --vault <vault> --json
python scripts\orchestrator.py dry-run --from-brief <research-brief.json>
```

The first version does not include interactive CLI questioning or delete/archive operations.

`research-brief create` reads structured JSON generated by `research-grill-me`; it does not infer a brief from Markdown.

`research-brief list` should show:

- `brief_slug`
- `status`
- title or short task
- `created_at`
- `updated_at`
- `revision_number`
- `last_used_at` when derivable from run history
- path

Do not show full constraints, keywords, or provenance in the default list view.

## Dry-Run Integration

`dry-run --query` remains supported as a quick path.

`dry-run --from-brief` becomes the formal brief-first path.

`--query` and `--from-brief` must be mutually exclusive. Do not silently merge them.

When a brief is used, the run state and report should record:

- `research_brief.path`
- `research_brief.slug`
- `research_brief.hash`
- `research_brief.status`
- `research_brief.revision_number`

The brief content hash must participate in dry-run resume and dedup signatures. A revised brief should not silently resume an old review session created from different intent.

The run must not mutate the Research Brief merely because it used it. `last_used_at` should be derived from run records or run index, not by rewriting the brief file.

## Query Planner Integration

Do not render a Research Brief into one string and call that the query.

`Research Brief + Research Profile -> Query Plan`

Mapping:

- `task` and `domain_scope` form hard search anchors.
- `keywords` and `specific_questions` generate query variants.
- `exclusions` and `review_policy` drive query suffixes and filtering.
- `quality_signals` influence ranking priority.
- `source_scope` influences source routing and follow-up verification.
- `output_goal` influences research mode.

Keep this mapping deterministic and testable. LLMs may help the user produce a brief in the skill layer, but CLI and query planner logic should not use an LLM to reinterpret a confirmed brief.

## Skill Structure

Follow existing Paper Source plugin structure and skill-creator guidance.

Add:

```text
plugins/paper-source/skills/research-grill-me/
  SKILL.md
  agents/openai.yaml
  references/research-brief-contract.md
```

Keep `SKILL.md` concise. It should own the conversation flow and point to the reference contract for schema and artifact rules. The detailed schema belongs in `references/research-brief-contract.md` and code tests, not duplicated across multiple docs.

Add `research_grill_me` to `plugins/paper-source/skills/routing.yaml` as a primary route. Triggers should include Chinese and English phrases for clarifying a research direction, grilling a research idea, building a Research Brief, planning a literature search, and preparing a serious Paper Source discovery run.

The skill should not instruct agents to write final Paper Wiki pages or bypass `wiki-ingest-brief.json`.

## Paper Wiki Boundary

Research Briefs are not Paper Wiki handoff artifacts.

Valid chain:

```text
research-grill-me
-> Research Brief
-> paper-discovery or topic-tracking
-> prepare-ranked / source-staging
-> wiki-ingest-brief
-> Paper Wiki
```

Paper Wiki may see a Research Brief only as background context after Paper Source has produced a source-staging handoff. Formal pages still require source evidence, approval, and `wiki-ingest-brief.json`.

## Topic Tracking Boundary

Topic tracking may reference a Research Brief as an input anchor or initialization source.

Topic tracking must not write its long-term ledger, delta history, backlog, or coverage-gap state into the Research Brief. If the research direction changes materially, create a new brief or a revised brief rather than turning the brief into a tracking database.

## Context Reminders

Do not generate verbose config snapshots in every artifact.

Use a light model:

- JSON keeps compact field provenance.
- Chinese `research-brief.md` includes a short context section of at most a few lines.
- `agent-brief.md` stays focused on the English task and references the JSON contract implicitly.
- `dry-run --from-brief` prints a short reminder: which brief is used, which major fields override profile, and whether critical prerequisites are missing.

Blocking conditions:

- missing Paper Source vault
- missing Paper Source Research Profile/config
- Research Brief lacks required fields
- trying to use a draft brief without explicit override

Warnings:

- missing Unpaywall email or provider keys
- missing EasyScholar key
- missing MinerU setup when the output goal implies source-staging
- missing Paper Wiki capability when the user expects formal deposition later

## Test Plan

Add focused tests before implementation.

### New tests

- `tests/paper_source/test_research_brief.py`
  - create writes JSON, Chinese Markdown, English agent brief
  - slug validation rejects unsafe names
  - validate enforces required fields
  - confirmed brief revision preserves historical snapshot
  - draft brief validation distinguishes formal-use eligibility

- `tests/paper_source/test_research_brief_cli.py`
  - parser accepts `research-brief create/validate/list`
  - parser rejects invalid command shapes
  - create/list JSON output follows the contract

- `tests/paper_source/test_dry_run_from_brief.py`
  - `--query` and `--from-brief` are mutually exclusive
  - confirmed brief can drive dry-run
  - draft brief requires explicit override
  - run state records brief path/hash/status/revision
  - brief hash participates in resume signature

- `tests/paper_source/test_research_grill_skill_contract.py`
  - routing.yaml includes primary `research_grill_me`
  - `research-grill-me/SKILL.md` uses one-question-at-a-time contract
  - skill docs name `research-brief` as CLI artifact manager
  - skill docs forbid direct Paper Wiki formal writing from a Research Brief

### Existing tests to update

- `tests/paper_source/test_cli_parser.py`
- `tests/paper_source/test_paper_discovery_query_planner.py`
- `tests/paper_source/test_config_onboarding_docs.py`
- `tests/paper_source/test_orchestrator_dry_run.py`
- `plugins/paper-source/tests/test_skill_bundle_contract.py`

## Verification Commands

Focused verification:

```powershell
python -m pytest tests\paper_source\test_research_brief.py tests\paper_source\test_research_brief_cli.py tests\paper_source\test_dry_run_from_brief.py tests\paper_source\test_research_grill_skill_contract.py -q
```

Existing adjacent coverage:

```powershell
python -m pytest tests\paper_source\test_cli_parser.py tests\paper_source\test_paper_discovery_query_planner.py tests\paper_source\test_orchestrator_dry_run.py tests\paper_source\test_config_onboarding_docs.py plugins\paper-source\tests\test_skill_bundle_contract.py -q
```

Final source verification:

```powershell
python -m pytest tests\paper_source plugins\paper-source\tests -q
git diff --check
```

If skill metadata changes, run plugin validation against `plugins/paper-source`.

## Acceptance Criteria

- `CONTEXT.md` defines Research Brief, Research Profile, and Research Grill.
- Paper Source has a primary `research-grill-me` route and skill folder.
- `research-grill-me` follows one-question-at-a-time strong questioning with recommended answers.
- A confirmed Research Brief is persisted under `_paper_source/research-briefs/YYYYMMDD-<slug>/`.
- Each brief directory has `research-brief.json`, Chinese `research-brief.md`, English `agent-brief.md`, and revision support.
- Research Brief schema records field provenance and required fields.
- `research-brief create/validate/list` are available through the orchestrator.
- `dry-run --from-brief` is available and mutually exclusive with `--query`.
- `dry-run --from-brief` records brief path/hash/status/revision in run artifacts.
- Brief hash affects dry-run resume/dedup behavior.
- Research Brief overrides Research Profile for task intent while the profile fills gaps.
- `topic-tracking` may reference a Research Brief but does not store tracking state in it.
- Paper Wiki formal writes remain gated by source-staging and `wiki-ingest-brief.json`.
- Focused and adjacent tests pass.

## Implementation Planning Notes

Implementation should follow the existing Paper Source pattern: small focused modules with thin CLI and orchestrator routers.

Likely new module:

```text
plugins/paper-source/scripts/build/paper_source/research_brief.py
```

Likely modified modules:

```text
plugins/paper-source/scripts/build/paper_source/cli_parser.py
plugins/paper-source/scripts/build/paper_source/cli_routes.py
plugins/paper-source/scripts/build/paper_source/cli.py
plugins/paper-source/scripts/build/paper_source/orchestrator.py
plugins/paper-source/scripts/build/paper_source/query_planner.py
plugins/paper-source/scripts/build/paper_source/review_sessions.py
plugins/paper-source/scripts/build/paper_source/report_run.py
plugins/paper-source/skills/routing.yaml
```

Do not grow `orchestrator.py` with large research-brief logic. It should call focused helpers in `research_brief.py`.
