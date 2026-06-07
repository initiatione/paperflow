# EPI Concepts And Synthesis Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend EPI staging and promotion so a passed paper stages and promotes not only a reference page but also minimal `concepts/` and `synthesis/` compiled pages with rollback coverage.

**Architecture:** Keep the change narrowly scoped to the current single-paper pipeline. `stage_wiki.py` will derive one staged concept draft and one staged synthesis draft from the paper slug, metadata, and reader outputs, then record all staged drafts in `promotion-plan.json`. `promote_to_wiki.py` will treat the reference, concept, and synthesis pages as one transactional page-set for promotion and rollback.

**Tech Stack:** Python 3.13 standard library, existing EPI staging/promotion modules, pytest.

---

## Scope

Included:

- Stage `references/`, `concepts/`, and `synthesis/` drafts under `_staging/papers/<slug>/`.
- Record all staged draft paths and compiled targets in `promotion-plan.json`.
- Promote and roll back all compiled page targets transactionally.
- Keep manifest/log/index/hot refresh behavior intact for references.

Excluded:

- Multi-paper synthesis merging.
- Semantic topic clustering.
- Cross-paper concept deduplication.
- Rich concept extraction from methods sections.

## Assumptions

- This batch uses stable single-paper placeholder slugs for compiled concept/synthesis pages:
  - `concepts/<paper-slug>-concept.md`
  - `synthesis/<paper-slug>-synthesis.md`
- These slugs are intentionally conservative; later work can replace them with shared topic slugs without breaking the artifact contract.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\stage_wiki.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\promote_to_wiki.py`
- Test `D:\paper-search\tests\epi\test_one_paper_ingest.py`
- Test `D:\paper-search\tests\epi\test_promote_to_wiki.py`

## Tasks

### Task 1: Stage Multi-Target Red Tests

- [ ] Extend `tests\epi\test_one_paper_ingest.py`.
- [ ] Add assertions that `_staging/papers/<slug>/concepts/` contains one concept draft.
- [ ] Add assertions that `_staging/papers/<slug>/synthesis/` contains one synthesis draft.
- [ ] Add assertions that `promotion-plan.json` records `staged_concepts`, `staged_synthesis`, and all compiled targets.
- [ ] Run `python -m pytest tests\epi\test_one_paper_ingest.py -v`.
- [ ] Expected red failure: missing staged concept/synthesis artifacts or missing plan fields.

### Task 2: Stage Multi-Target Implementation

- [ ] Update `stage_paper()` to derive conservative concept/synthesis slugs from the paper slug.
- [ ] Write minimal staged concept and synthesis drafts with provenance/frontmatter plus links back to the reference page.
- [ ] Record staged draft paths and compiled targets for all page types in `promotion-plan.json`.
- [ ] Re-run `tests\epi\test_one_paper_ingest.py -v` to green.

### Task 3: Promotion Page-Set Red Tests

- [ ] Extend `tests\epi\test_promote_to_wiki.py`.
- [ ] Add assertions that promotion writes compiled concept and synthesis pages alongside the reference page.
- [ ] Add assertions that `promotion-record.json` includes all promoted page paths and any overwritten snapshots for each page type.
- [ ] Add assertions that rollback restores or removes compiled concept/synthesis pages together with the reference page.
- [ ] Run `python -m pytest tests\epi\test_promote_to_wiki.py -v`.
- [ ] Expected red failure: missing compiled concept/synthesis outputs or incomplete rollback state.

### Task 4: Promotion Page-Set Implementation

- [ ] Update `promote_paper()` to load all staged drafts from `promotion-plan.json`.
- [ ] Snapshot existing compiled pages for each target before writing.
- [ ] Promote reference, concept, and synthesis pages as one transaction record.
- [ ] Update rollback to restore/remove all compiled targets from `promotion-record.json`.
- [ ] Re-run `tests\epi\test_promote_to_wiki.py -v` to green.

### Task 5: Verification

- [ ] Run `python -m pytest tests\epi\test_one_paper_ingest.py tests\epi\test_promote_to_wiki.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_concepts_synthesis`.
