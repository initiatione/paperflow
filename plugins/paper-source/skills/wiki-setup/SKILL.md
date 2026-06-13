---
name: wiki-setup
description: >
  Use when setting up or repairing a Paper Source vault: "初始化 vault", "修复 vault", reset, graph visibility.
---

# Paper Source Wiki Setup

Use only for target paper research wiki vault initialization, inspection, repair, reset, and graph visibility; not for paper search, ingest, MinerU, Zotero, or final wiki writing.

Load `workflows/reset-repair.md` and `references/reset-recovery.md` before reset, `--no-backup`, config reset, restore, or misdelete recovery.

## Workflow Routing

Initialize or inspect here; load `workflows/reset-repair.md` for destructive reset, repair, restore, or misdelete recovery.

## Reset Boundary

wiki structure reset and Paper Source config reset are separate operations. Default reset preserves config even when the user says 不需要备份. Preserve `_paper_source\meta\paper-source-config.yaml`, `_paper_source\meta\paper-source-config-state.json`, `_paper_source\meta\config-history\`, legacy `_epi\meta\paper-source-config.yaml`, legacy `_epi\meta\epi-config-state.json`, legacy `_epi\meta\epi-config-history\`, and `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`. Before/after destructive actions, report non-secret state with `config-status --vault <vault> --json --include-values --include-runtime`.

## Initialize

Initialization is idempotent:

```powershell
python scripts\init_paper_wiki.py --vault <vault>
```

`init_paper_wiki.py` runs `git init` when `<vault>\.git` is missing, records `.git`, and does not create a first commit.

Expected roots: `_paper_source`, `_meta`, formal wiki roots, `.obsidian`, `.git`, `index.md`, `log.md`, `hot.md`, `.manifest.json`; do not create top-level `_raw`, `_staging`, `_runs`, `_quarantine`, or `_evolution`.

core `_paper_source` bootstrap: `_paper_source\README.md`, `_paper_source\manifest.json`, `_paper_source\policies\retention.json`, raw/staging/meta/policies roots, and on-demand `runs`, `cache`, `tmp`, `tmp-manual-pdfs`, quarantine/evolution. Existing `_epi` roots remain legacy-readable. `_paper_source/raw/<slug>/mineru/<slug>.md` is source material, not a formal page.

The retention policy must cap lifecycle artifacts: run dirs, `_paper_source\meta\run-lifecycle`, `_paper_source\meta\raw-cleanup`, `_paper_source\meta\repository-maintenance`, `_paper_source\meta\migrations`, `_paper_source\meta\wiki-reset`, `_paper_source\meta\formal-page-snapshots`, and `_paper_source\tmp-manual-pdfs`.

Seed `AGENTS.md`, `_meta\agent-operating-contract.md`, `_meta\schema.md`, `_meta\taxonomy.md`, and `_meta\directory-structure.md`.

Defaults remain source-first for paper research. Load `../paper-ingest/references/source-first-reading.md` for reader outputs, claim support, final source review, or formal page writes; it covers `mineru\<slug>.md`, `mineru\images\*`, and fallback evidence.

Old-root maintenance commands:

```powershell
python scripts\orchestrator.py paper-source-repository-migrate --vault <vault> --preview --json
python scripts\orchestrator.py paper-source-repository-migrate --vault <vault> --json
python scripts\orchestrator.py paper-source-repository-cleanup --vault <vault> --preview --json
```

`paper-source-repository-cleanup --preview --json` is the no-write inspection path; it must not refresh `_paper_source\manifest.json`, create directories, or seed policy files. Non-preview cleanup may delete only lifecycle-bounded reproducible maintenance artifacts; preserve `_paper_source\\raw`, config history, final pages, Zotero records, and source bundles.

## Literature Wiki Contract

Formal page families are `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. Paper Source writes only `_paper_source/`; Paper Wiki `$paper-research-wiki` writes final pages after handoff and approval. `wiki-ingest-brief.json` is the canonical Paper Source-to-Paper Wiki handoff. `wiki_deposition_task.json is legacy` compatibility only; `paper-source-paper-deposition` is the compatibility adapter. external wiki skills are optional helpers / policy references.

Paper Wiki assumes this bootstrap exists. If `_paper_source/`, `_meta/`, `.obsidian`, `.git`, or formal roots are missing, it reports missing vault structure and sends the user back to Paper Source `wiki-setup`; Paper Wiki does not initialize or reset the vault.

Formal page frontmatter requires `title`, `category`, `page_family`, `tags`, `aliases`, `sources`, `summary`, `provenance`, `base_confidence`, `lifecycle`, `lifecycle_changed`, `tier`, `created`, and `updated`. Initial lifecycle is `draft`; old `review-needed` pages are legacy repair inputs. Do not add `review_status`; do not use `source-reviewed` or `verified` lifecycle states.

Frontmatter `sources` use title-display Markdown links to canonical source PDFs with source paper title as link text. URI example: `obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf`. Do not put internal wikilinks, legacy `_epi` links, plain/relative PDF paths, DOI/arXiv URLs, GitHub URLs, metadata paths, MinerU paths, or figure paths in frontmatter `sources`.
