# EPI Reader Evidence Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade EPI reader outputs and critic checks so important paper claims are evidence-addressable and critic-verifiable instead of relying on the placeholder `Evidence:` marker.

**Architecture:** Keep the change narrowly scoped to the Phase 2 read/critic contract. `generate_reader.py` will emit a minimal structured evidence-address format for `reader.md`, `figures.md`, and `reproducibility.md`; `run_critic.py` will parse and validate those addresses against raw artifacts and select `pass` or `revise-reader` accordingly. `implementation-ideas.md` remains the home for transfer ideas and inference-heavy content.

**Tech Stack:** Python 3.13 standard library, existing EPI scripts, pytest.

---

## Scope

Included:

- Structured evidence lines in reader outputs.
- Critic-side parsing and validation for evidence addresses.
- Tests for valid evidence, broken evidence, and non-promotable critic outcomes.

Excluded:

- LLM-generated summarization.
- PDF page-number extraction.
- `human-review`, `quarantine`, or `redo-parse` routing expansion.
- `concepts/` and `synthesis/` staging.

## Files

- Modify `D:\paper-search\plugins\epi\scripts\epi\generate_reader.py`
- Modify `D:\paper-search\plugins\epi\scripts\epi\run_critic.py`
- Test `D:\paper-search\tests\epi\test_reader_evidence_traceability.py`
- Test `D:\paper-search\tests\epi\test_critic_evidence_traceability.py`

## Contract

Evidence lines use this exact flat format:

```text
Evidence: source=mineru/paper.md; heading=Abstract
Evidence: source=metadata.json; field=venue
Evidence: source=mineru/images; image=figure-1.png
Evidence: source=inference; basis=implementation-ideas
```

For this batch, `run_critic.py` must treat these forms as valid:

- `source=mineru/paper.md; heading=<heading text>`
- `source=metadata.json; field=<field name>`
- `source=mineru/images; image=<file name>`
- `source=inference; basis=<label>`

Reader-phase policy for this batch:

- `reader.md` claims should cite `mineru/paper.md` headings or `metadata.json` fields.
- `figures.md` should cite `mineru/images` when images exist, or clearly say no figures were detected without inventing figure claims.
- `reproducibility.md` should cite `metadata.json` fields.
- `implementation-ideas.md` keeps inference-oriented content and does not need to be promotable fact output.

## Tasks

### Task 1: Reader Red Tests

- [ ] Add `tests\epi\test_reader_evidence_traceability.py`.
- [ ] Write a failing test that seeds `metadata.json`, `mineru/paper.md`, and an image, then asserts generated reader files contain structured evidence lines.
- [ ] Verify `reader.md` includes a claim backed by `source=mineru/paper.md; heading=...`.
- [ ] Verify `figures.md` includes `source=mineru/images; image=...` when an image exists.
- [ ] Verify `reproducibility.md` includes `source=metadata.json; field=sources`.
- [ ] Run the targeted test and watch it fail for the expected reason.

### Task 2: Reader Implementation

- [ ] Add minimal MinerU heading parsing in `generate_reader.py`.
- [ ] Emit structured evidence lines in the exact contract format.
- [ ] Preserve current audit metadata fields in the returned `reader_record`.
- [ ] Re-run the reader traceability test to green.

### Task 3: Critic Red Tests

- [ ] Add `tests\epi\test_critic_evidence_traceability.py`.
- [ ] Write one passing fixture test with valid structured evidence.
- [ ] Write one failing fixture test where a reader claim cites a missing heading or field and must result in `revise-reader`.
- [ ] Write one focused test showing non-pass critic output cannot be staged.
- [ ] Run the targeted critic tests and confirm the expected red failures.

### Task 4: Critic Implementation

- [ ] Add evidence-line parsing in `run_critic.py`.
- [ ] Validate reader claims against existing raw artifacts using the agreed evidence formats.
- [ ] Keep the hard rule and current pass/revise-reader routing stable.
- [ ] Re-run critic tests and the existing one-paper ingest tests to green.

### Task 5: Verification

- [ ] Run `python -m pytest tests\epi\test_reader_evidence_traceability.py tests\epi\test_critic_evidence_traceability.py -v`.
- [ ] Run `python -m pytest tests\epi\test_one_paper_ingest.py tests\epi\test_promote_to_wiki.py -v`.
- [ ] Run `python -m pytest tests\epi -q --basetemp .pytest_tmp_reader_evidence`.
