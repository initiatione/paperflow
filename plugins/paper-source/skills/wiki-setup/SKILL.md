---
name: wiki-setup
description: >
  Use when initializing, inspecting, repairing, or resetting a Paper Source / EPI paper wiki vault,
  including "初始化 vault", "修复 vault", "重置 vault", graph visibility,
  destructive reset safety, or misdelete recovery.
---

# EPI Wiki Setup

Use only for the target paper research wiki vault structure: initialize, inspect, repair, reset. Do not use for paper search, ingest, MinerU, Zotero, or final wiki writing.

Load `references/reset-recovery.md` and `workflows/reset-repair.md` before reset, `--no-backup`, config reset, or misdelete recovery.

## Config Boundary

wiki structure reset and EPI config reset are separate operations. Default reset preserves config, even if the user says 不需要备份.

Preserve:

- `_epi\meta\epi-config.yaml`
- `_epi\meta\epi-config-state.json`
- `_epi\meta\epi-config-history\`
- `_epi\meta\config-history\`
- `%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`

Before and after destructive actions, report non-secret config state only with `config-status --vault <vault> --json --include-values --include-runtime`.

## Workflow Routing

| Intent | Load |
| --- | --- |
| Initialize or inspect a vault structure | This `SKILL.md` |
| Preview reset, execute reset, decline backup, reset config, repair, restore, or recover from misdelete | `workflows/reset-repair.md` |
| Understand reset safeguards and recovery sources | `references/reset-recovery.md` |
| Search, ingest, parse, Zotero sync, or formal wiki writing | Switch to the matching EPI skill |

## Initialize

Initialization is idempotent:

```powershell
python scripts\init_paper_wiki.py --vault <vault>
```

Initialization must ensure the vault is a git repository. `init_paper_wiki.py` runs `git init` when `<vault>\.git` is missing, records `.git` in the created path list, and does not create a first commit. If `.git` already exists, preserve the existing repository.

Expected structure includes one EPI internal repository root `_epi`, wiki contract root `_meta`, wiki roots, `.obsidian`, `.git`, `index.md`, `log.md`, `hot.md`, and `.manifest.json`. New initialization must not create top-level `_raw`, `_staging`, `_runs`, `_quarantine`, or `_evolution`.

The core `_epi` bootstrap must include `_epi\README.md`, `_epi\manifest.json`, `_epi\policies\retention.json`, and raw/staging/meta/policies roots. `runs`, `cache`, `tmp`, `tmp-manual-pdfs`, and quarantine/evolution roots are on-demand workflow directories, not empty bootstrap shells. Obsidian graph views should ignore `_epi`; `_epi/raw/<slug>/mineru/<slug>.md` remains source material, not a formal wiki page. The default retention policy must cap lifecycle artifacts even when the repository is under total file/byte budget: transient run dirs, `_epi\meta\run-lifecycle`, `_epi\meta\raw-cleanup`, `_epi\meta\repository-maintenance`, `_epi\meta\migrations`, `_epi\meta\wiki-reset`, `_epi\meta\formal-page-snapshots`, and `_epi\tmp-manual-pdfs` are not allowed to grow forever once those on-demand paths exist.

Initialization also seeds the vault contract files used by final wiki-ingest agents: `AGENTS.md`, `_meta\agent-operating-contract.md`, `_meta\schema.md`, `_meta\taxonomy.md`, and `_meta\directory-structure.md`.

These defaults are source-first for paper research: final wiki pages must read `mineru\<slug>.md`, `mineru\paper.tex`, `mineru\images\*`, and `mineru\mineru-manifest.json`, then use reader/critic outputs as evidence aids.

For existing vaults with old top-level operational roots, migrate before or after initialization:

```powershell
python scripts\orchestrator.py epi-repository-migrate --vault <vault> --preview --json
python scripts\orchestrator.py epi-repository-migrate --vault <vault> --json
python scripts\orchestrator.py epi-repository-cleanup --vault <vault> --preview --json
```

`epi-repository-cleanup --preview --json` is a no-write inspection path. It must not refresh `_epi\manifest.json`, create missing directories, or seed policy files. The non-preview cleanup may delete only lifecycle-bounded, reproducible maintenance artifacts; it must preserve `_epi\\raw`, config files/history, final wiki pages, Zotero records, and source-first paper bundles.

## Literature Wiki Contract

Initialization seeds formal wiki page families for paper research: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. EPI itself still writes only `_epi/`; final pages are written by PRW `$paper-research-wiki` after handoff and approval. `wiki-ingest-brief.json` is the canonical EPI-to-PRW handoff. `wiki_deposition_task.json is legacy` compatibility only, and `epi-paper-deposition` is only the compatibility adapter for existing EPI handoff artifacts or legacy records.

The vault contract should expect `wiki-ingest-brief.json` plus source bundle artifacts, human approval, `final-source-review.json`, and `record-wiki-ingest` closure. Required EPI/PRW skills are `$paper-research-wiki` and `epi-paper-deposition`; external wiki skills are optional helpers / policy references, including `llm-wiki`, `wiki-ingest`, `wiki-context-pack`, `wiki-lint`, `wiki-stage-commit`, `wiki-status`, `wiki-query`, `wiki-provenance`, and `tag-taxonomy`. `epi-wiki-deposition` is a legacy compatibility alias, not the primary adapter name.

PRW assumes this bootstrap exists. If PRW detects missing `_epi/`, `_meta/`, `.obsidian`, `.git`, or formal page roots, it should report the missing vault structure and send the user back to EPI `wiki-setup`; PRW should not initialize or reset the vault itself.

Formal page frontmatter requires `title`, `category`, `page_family`, `tags`, `aliases`, `sources`, `summary`, `provenance`, `base_confidence`, `lifecycle`, `lifecycle_changed`, `tier`, `created`, and `updated`; initial lifecycle is `draft` or `review-needed`, not automatic `source-reviewed` or `verified`. Frontmatter `sources` must contain only Obsidian source PDF links to `_epi/raw/<slug>/paper.pdf`; prefer paper-title `obsidian://open?...paper.pdf` links so `_epi` does not enter the formal graph, while legacy slug wikilinks are accepted for compatibility.
