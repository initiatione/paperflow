# Paper Research Wiki Governance Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `D:\paper-search` and `D:\paper-research-wiki` to the current Paper Wiki governance contract so new writes are `_paper_source`-first, `lifecycle: draft` only, `sources:` uses title-display canonical PDF Markdown links, and legacy `_epi` survives only as a repair input until it can be removed.

**Architecture:** Treat the governance problem as three layers that must agree: vault-local contract files in `D:\paper-research-wiki`, plugin source contracts in `plugins/paper-wiki` and `plugins/paper-source`, and the live formal pages that still carry legacy `_epi` / `review-needed` state. Tighten source-level validators first so new drift stops, then migrate the vault with snapshots and targeted rewrites.

**Tech Stack:** Markdown contract docs, Python validators, existing Paper Source / Paper Wiki scripts, pytest contract tests, Obsidian vault metadata.

**Execution Status (2026-06-12):** Implemented. Source contracts and validators now emit `_paper_source`-first, `lifecycle: draft` only, title-display canonical PDF Markdown links in `sources:` and body PDF entries, canonical `paper-wiki-record-request.json`, and MinerU-Markdown-first formula evidence. Current vault formal pages have been migrated and audited: 56 formal pages, 0 contract issues, `_epi/` absent from the live formal graph, active artifact migration dry-run `action_count: 0`, formal-page migration dry-run `pages_changed: 0`, QMD refreshed and verified to exclude `_paper_source/**`, `_paper_source/meta/formal-page-snapshots/**`, and `_epi/**`.

---

### Task 1: Freeze The Canonical Contract In Source Docs

**Files:**
- Modify: `plugins/paper-wiki/rules/wiki-writing-standard.md`
- Modify: `plugins/paper-wiki/rules/formal-page-frontmatter.md`
- Modify: `plugins/paper-source/skills/wiki-provenance/references/page-provenance.md`
- Modify: `plugins/paper-wiki/skills/paper-research-wiki/workflows/maintain-figures.md`

- [x] **Step 1: Make the canonical root explicit in every active write contract**

Add or tighten wording so every active write path says:

```md
Use `_paper_source/raw/<slug>/paper.pdf` as the canonical body PDF target.
Legacy `_epi` paths are repair inputs only; do not emit them in new formal pages.
```

- [x] **Step 2: Keep legacy compatibility wording read-only**

Use wording shaped like:

```md
Legacy `_epi` artifacts may be read to repair existing pages, but recorded formal pages
must be rewritten to the current `_paper_source` contract before `record-wiki-ingest`.
```

- [x] **Step 3: Make the lifecycle contract unambiguous**

Keep this exact rule in the human-readable contract:

```md
Initial lifecycle is `draft`.
Do not add `review_status`.
Old `lifecycle: review-needed` pages are legacy repair inputs and must be migrated to `draft`.
```

- [x] **Step 4: Verify the docs still agree**

Run: `python -m pytest tests/paper_research_wiki/test_plugin_contract.py -q`

Expected: contract phrases stay synchronized across `rules/`, `workflows/`, and provenance references.

### Task 2: Tighten Record-Time Validation So New Pages Cannot Re-Legitimize `_epi`

**Files:**
- Modify: `plugins/paper-source/scripts/build/paper_source/wiki_ingest_record.py`
- Test: `tests/paper_source/test_wiki_ingest_record.py`

- [x] **Step 1: Split canonical and compatibility PDF-link matching**

Refactor the validator so:

```python
_CANONICAL_BODY_SOURCE_PDF_PATTERN = re.compile(
    rf"\[[^\]]+\]\(obsidian://open\?[^)]*file={re.escape(PAPER_SOURCE_ROOT_NAME)}%2Fraw%2F(?P<slug>[^%/)]+)%2Fpaper\.pdf(?:[&#][^)]*)?\)",
    re.IGNORECASE,
)
_LEGACY_BODY_SOURCE_PDF_PATTERN = re.compile(
    rf"\[[^\]]+\]\(obsidian://open\?[^)]*file={re.escape(LEGACY_EPI_ROOT_NAME)}%2Fraw%2F(?P<slug>[^%/)]+)%2Fpaper\.pdf(?:[&#][^)]*)?\)",
    re.IGNORECASE,
)
```

- [x] **Step 2: Reject legacy `_epi` body PDF links at record time**

Use logic shaped like:

```python
def _body_source_pdf_link_issues(body: str) -> list[str]:
    if "## 原文与证据入口" not in body:
        return ["formal page body must include ## 原文与证据入口"]
    if _CANONICAL_BODY_SOURCE_PDF_PATTERN.search(body):
        return []
    if _LEGACY_BODY_SOURCE_PDF_PATTERN.search(body):
        return [
            "formal page body 原文与证据入口 must use canonical _paper_source/raw/<slug>/paper.pdf, not legacy _epi/raw/<slug>/paper.pdf"
        ]
    return [
        "formal page body 原文与证据入口 must include a clickable obsidian:// source PDF link"
    ]
```

- [x] **Step 3: Add a regression test for legacy body-link rejection**

Add a focused test shaped like:

```python
def test_create_wiki_ingest_record_rejects_legacy_epi_body_pdf_link(tmp_path):
    ...
    page = _write_final_page(
        vault,
        "references/legacy-epi-body-link.md",
        _formal_page_content("references", "Legacy EPI Body Link").replace(
            _obsidian_uri_pdf_url(),
            "obsidian://open?vault=paper-research-wiki&file=_epi%2Fraw%2Ffixture-paper%2Fpaper.pdf",
        ),
    )
    ...
    with pytest.raises(ValueError, match="canonical _paper_source/raw/<slug>/paper.pdf|legacy _epi/raw"):
        create_wiki_ingest_record(...)
```

- [x] **Step 4: Run the focused record tests**

Run: `python -m pytest tests/paper_source/test_wiki_ingest_record.py -q`

Expected: existing compatibility reads still work where intended, but final-page recording rejects legacy `_epi` body PDF links.

### Task 3: Canonicalize Figure-Maintenance Record Requests

**Files:**
- Modify: `plugins/paper-wiki/scripts/maintain_figures.py`
- Modify: `plugins/paper-wiki/skills/paper-research-wiki/workflows/maintain-figures.md`
- Test: `tests/paper_research_wiki/test_maintain_figures.py`
- Test: `tests/paper_research_wiki/test_plugin_contract.py`

- [x] **Step 1: Make figure maintenance refresh the canonical request artifact**

Change the script from:

```python
request_path = staging / "prw-record-request.json"
```

to:

```python
request_path = staging / "paper-wiki-record-request.json"
legacy_request_path = staging / "prw-record-request.json"
```

Refresh the canonical request when present, and touch the legacy one only if it already exists and the vault is still being repaired.

- [x] **Step 2: Keep the metadata vocabulary canonical**

Update the refresh payload so new request metadata reads like:

```python
task["route"] = "maintain_figures"
task["summary"] = (
    "Paper Wiki refreshed normalized raw figure evidence links; "
    "Paper Source can consume this request with record-wiki-ingest if recording is desired."
)
```

- [x] **Step 3: Update the workflow docs to match**

Replace active output references like:

```md
- `prw-record-request.json`
```

with:

```md
- `paper-wiki-record-request.json`
- legacy `prw-record-request.json` only when repairing an existing old staging bundle
```

- [x] **Step 4: Add tests for canonical request refresh**

Add a focused test shaped like:

```python
def test_refresh_sidecars_updates_canonical_paper_wiki_record_request(tmp_path):
    ...
    request_path = staging / "paper-wiki-record-request.json"
    ...
    result = module.refresh_sidecars(...)
    assert result["paper_wiki_record_request_changed"] is True
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    assert payload["final_source_review"]["sha256"]
```

Also extend the contract test so `maintain-figures.md` must mention `paper-wiki-record-request.json`.

- [x] **Step 5: Run the Paper Wiki tests**

Run: `python -m pytest tests/paper_research_wiki/test_maintain_figures.py tests/paper_research_wiki/test_plugin_contract.py -q`

Expected: figure maintenance now emits the canonical request artifact and docs reflect the same behavior.

### Task 4: Prepare The Vault-Local Migration Pass

**Files:**
- Modify later in vault: `D:\paper-research-wiki\AGENTS.md`
- Modify later in vault: `D:\paper-research-wiki\_meta\agent-operating-contract.md`
- Modify later in vault: `D:\paper-research-wiki\_meta\schema.md`
- Modify later in vault: `D:\paper-research-wiki\_meta\directory-structure.md`
- Modify later in vault: formal pages under `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, `opportunities/`

- [x] **Step 1: Rewrite the vault-local contract to `_paper_source`-first**

Use contract wording shaped like:

```md
`_paper_source/` is the canonical internal evidence repository.
Legacy `_epi/` is readable only for migration, repair, and snapshot recovery.
New formal pages and refreshed formal pages must not emit `_epi` body PDF links.
```

- [x] **Step 2: Snapshot before formal migration**

Run a snapshot step before touching live formal pages:

```text
_paper_source/meta/formal-page-snapshots/<yyyyMMdd-HHmmss>-pre-governance-migration/
```

If the live vault still only has `_epi/meta/formal-page-snapshots/`, record that as temporary technical debt and create the next snapshot under `_paper_source/meta/`.

- [x] **Step 3: Run the mechanical formal-page migration**

For each live formal page:

```text
lifecycle: review-needed -> lifecycle: draft
remove review_status if present
frontmatter sources -> short labels only
body 原文与证据入口 -> canonical _paper_source/raw/<slug>/paper.pdf
leave body evidence addresses readable, but do not create formal graph links into internal roots
```

- [x] **Step 4: Refresh tracking and re-audit**

After the vault migration:

```text
refresh .manifest.json, index.md, log.md, hot.md, final-source-review.json hashes, and QMD if in scope
re-run a whole-vault grep for review-needed, review_status, and body _epi PDF URIs
```

### Task 5: Final Verification And Retirement Gate

**Files:**
- Modify if needed: `plugins/paper-source/docs/structure.md`
- Modify if needed: `plugins/paper-wiki/docs/structure.md`
- Verify: `tests/paper_source/test_wiki_ingest_record.py`
- Verify: `tests/paper_research_wiki/test_plugin_contract.py`
- Verify later in vault: `D:\paper-research-wiki`

- [x] **Step 1: Run the focused governance suite**

Run:

```powershell
python -m pytest tests/paper_research_wiki/test_plugin_contract.py tests/paper_research_wiki/test_maintain_figures.py tests/paper_source/test_wiki_ingest_record.py -q
```

Expected: all governance, record-time, and figure-maintenance contracts pass together.

- [x] **Step 2: Run the hygiene check**

Run:

```powershell
git diff --check
```

Expected: no whitespace or patch-format issues.

- [x] **Step 3: Declare `_epi` retirement criteria explicitly**

Do not delete `_epi` until all of the following are true:

```text
no live formal page uses lifecycle: review-needed
no live formal page uses review_status
no live formal page body uses _epi/raw/<slug>/paper.pdf as the canonical source link
new record-wiki-ingest runs pass with _paper_source-only body PDF links
all remaining _epi content is either snapshot history or legacy repair data already duplicated under _paper_source
```

- [x] **Step 4: Execute retirement in a separate change**

Only after the criteria above pass:

```text
migrate or archive remaining _epi snapshots and staging artifacts
switch any remaining local docs from "_epi main root" to "legacy-only"
remove `_epi` from the live vault in one explicit, reviewable maintenance run
```
