---
name: wiki-setup
description: >
  Use when setting up or repairing a Paper Source vault: "初始化 vault", "修复 vault", reset, graph visibility.
---

# Paper Source Wiki Setup

Use only for the target paper research wiki vault structure: initialize, inspect, repair, reset. Do not use for paper search, ingest, MinerU, Zotero, or final wiki writing.

Load `references/reset-recovery.md` and `workflows/reset-repair.md` before reset, `--no-backup`, config reset, or misdelete recovery.

## Config Boundary

wiki structure reset and Paper Source config reset are separate operations. Default reset preserves config, even when the user says 不需要备份.

Preserve:

- `_paper_source\meta\paper-source-config.yaml`
- `_paper_source\meta\paper-source-config-state.json`
- `_paper_source\meta\config-history\`
- legacy `_epi\meta\paper-source-config.yaml`
- legacy `_epi\meta\epi-config-state.json`
- legacy `_epi\meta\epi-config-history\`
- `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`

Before and after destructive actions, report non-secret config state only with `config-status --vault <vault> --json --include-values --include-runtime`.

## Workflow Routing

| Intent | Load |
| --- | --- |
| Initialize or inspect a vault structure | This `SKILL.md` |
| Preview reset, execute reset, decline backup, reset config, repair, restore, or recover from misdelete | `workflows/reset-repair.md` |
| Understand reset safeguards and recovery sources | `references/reset-recovery.md` |
| Search, ingest, parse, Zotero sync, or formal wiki writing | Switch to the matching Paper Source skill |

## Initialize

Initialization is idempotent:

```powershell
python scripts\init_paper_wiki.py --vault <vault>
```

Initialization must ensure the vault is a git repository. `init_paper_wiki.py` runs `git init` when `<vault>\.git` is missing, records `.git` in the created path list, and does not create a first commit. If `.git` already exists, preserve the existing repository.

Expected structure: `_paper_source`, `_meta`, formal wiki roots, `.obsidian`, `.git`, `index.md`, `log.md`, `hot.md`, `.manifest.json`. Do not create top-level `_raw`, `_staging`, `_runs`, `_quarantine`, or `_evolution`.

The core `_paper_source` bootstrap must include `_paper_source\README.md`, `_paper_source\manifest.json`, `_paper_source\policies\retention.json`, and raw/staging/meta/policies roots. `runs`, `cache`, `tmp`, `tmp-manual-pdfs`, and quarantine/evolution roots are on-demand workflow directories. Existing `_epi` roots remain legacy-readable. Obsidian graph views should ignore `_paper_source`; `_paper_source/raw/<slug>/mineru/<slug>.md` is source material, not a formal page. The default retention policy must cap lifecycle artifacts, including run dirs, `_paper_source\meta\run-lifecycle`, `_paper_source\meta\raw-cleanup`, `_paper_source\meta\repository-maintenance`, `_paper_source\meta\migrations`, `_paper_source\meta\wiki-reset`, `_paper_source\meta\formal-page-snapshots`, and `_paper_source\tmp-manual-pdfs`.

Seed vault contract files for wiki-ingest agents: `AGENTS.md`, `_meta\agent-operating-contract.md`, `_meta\schema.md`, `_meta\taxonomy.md`, and `_meta\directory-structure.md`.

Defaults are source-first for paper research: final pages use `mineru\<slug>.md` as the primary source for formulas, notation, method context, and prose. Use `paper.pdf`, `mineru\images\*`, `mineru\mineru-manifest.json`, `figure-index.json`, and `formula-index.json` as fallback or visual-evidence checks only when MinerU Markdown is missing, wrong, ambiguous, or insufficient. Use `mineru\paper.tex` only when it exists as non-empty native TeX and only as an optional cross-check; reader/critic outputs are aids.

For existing vaults with old top-level operational roots, migrate before or after initialization:

```powershell
python scripts\orchestrator.py paper-source-repository-migrate --vault <vault> --preview --json
python scripts\orchestrator.py paper-source-repository-migrate --vault <vault> --json
python scripts\orchestrator.py paper-source-repository-cleanup --vault <vault> --preview --json
```

`paper-source-repository-cleanup --preview --json` is the no-write inspection path. Preview must not refresh `_paper_source\manifest.json`, create missing directories, or seed policy files. Non-preview cleanup may delete only lifecycle-bounded, reproducible maintenance artifacts; preserve `_paper_source\\raw`, config history, final pages, Zotero records, and source bundles.

## Literature Wiki Contract

Formal page families: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. Paper Source writes only `_paper_source/`; Paper Wiki `$paper-research-wiki` writes final pages after handoff and approval. `wiki-ingest-brief.json` is the canonical Paper Source-to-Paper Wiki handoff. `wiki_deposition_task.json is legacy` compatibility only; `paper-source-paper-deposition` is the compatibility adapter. external wiki skills are optional helpers / policy references.

The vault contract expects source bundle artifacts, human approval, `final-source-review.json`, and `record-wiki-ingest` closure.

Paper Wiki assumes this bootstrap exists. If Paper Wiki detects missing `_paper_source/`, `_meta/`, `.obsidian`, `.git`, or formal page roots, it should report the missing vault structure and send the user back to Paper Source `wiki-setup`; Paper Wiki should not initialize or reset the vault itself.

Formal page frontmatter requires `title`, `category`, `page_family`, `tags`, `aliases`, `sources`, `summary`, `provenance`, `base_confidence`, `lifecycle`, `lifecycle_changed`, `tier`, `created`, and `updated`; initial lifecycle is `draft`, and `draft` is the only steady-state lifecycle value Paper Source/Paper Wiki should emit. Do not add `review_status`. Do not use `source-reviewed`, `verified`, or legacy `review-needed` as formal page lifecycle states. Old `lifecycle: review-needed` pages are migration/repair inputs and should be converted to `draft` during property repair. Frontmatter `sources` must contain title-display Markdown links to canonical source PDFs, such as `[<paper title>](obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf)`. Do not put internal wikilinks, legacy `_epi` links, plain/relative PDF paths, DOI/arXiv URLs, GitHub URLs, metadata paths, MinerU paths, or figure paths in frontmatter `sources`.
