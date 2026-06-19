# PaperFlow

Chinese is the default project README. This is the English version of
[README.md](README.md).

PaperFlow is a Codex plugin marketplace bundle for evidence-first academic
paper workflows. It helps agents move from paper discovery to source bundles,
human-reviewed handoff artifacts, and formal Obsidian/LLM wiki pages without
mixing those responsibilities into one opaque script.

The bundle currently ships two cooperating plugins:

| Plugin | Machine name | Current source version | Role |
| --- | --- | ---: | --- |
| Paper Source | `paper-source` | `2.9.0` | Discover, rank, acquire, parse, audit, stage, approve, initialize vault graph visibility, expose a Zotero helper adapter, run discovery-time Zotero dedupe, and record paper evidence. |
| Paper Wiki | `paper-wiki` | `1.3.0` | Ask, deposit, check, repair graph visibility, update, relink, redo, expose a Zotero helper adapter, provide Zotero data-contract foundations, run read-only Zotero status/dry-run previews, apply approved Zotero sync plans, and maintain formal paper wiki knowledge. |

`paperflow` is the marketplace bundle name. `paper-search` is retained only as
the repository/history name and for external `paper-search-mcp` or
`paper-search` CLI integrations. `PS` and `PW` are conversational aliases, not
separate plugin or skill names.

## Why PaperFlow?

PaperFlow is built for research workflows where "found a paper" is not enough.
It preserves source evidence, makes query and ranking decisions auditable, keeps
human approval explicit, and separates source preparation from formal wiki
writing.

The intended path is:

```text
Paper Source discovery
  -> source bundle and reader/critic evidence
  -> source-staging and human approval
  -> wiki-ingest-brief.json
  -> Paper Wiki formal pages and post-task checks
  -> Paper Source record-wiki-ingest
```

## Capabilities

Paper Source provides the source/evidence layer:

- Profile-driven and natural-language paper discovery through `discover-papers`.
- Transparent query plans, hard and soft constraints, source coverage reports,
  DOI-required chat recommendations, and cross-discipline quality gates.
- Deduplication against Paper Wiki `_meta/reference-index.json`.
- PDF acquisition, manual-download cards, MinerU parsing, asset normalization,
  evidence indexes, reader output, critic checks, and source bundle audits.
- Automatic source-staging for selected primary recommendations, with default
  limits that stop before approval or formal wiki writing.
- `paper-gate`, `record-human-approval`, `wiki-ingest-trigger`, and
  `record-wiki-ingest` artifacts for auditable handoff and completion.
- Vault bootstrap and repair through `wiki-setup`.
- Optional integrations for Grok supplemental discovery, a plugin-installed
  `grok-search-rs` MCP entry, EasyScholar metrics, Zotero sidecars, and
  provider-specific paper-search credentials.

MinerU parsing is an internal Paper Source helper capability, not as a separate marketplace plugin.

Paper Wiki provides the formal wiki layer:

- One public conversational assistant, `paper-research-wiki`, for asking the
  wiki, depositing Paper Source handoffs, checking the library, updating pages,
  relinking knowledge, redo/deep extraction, and figure/formula maintenance.
- A supporting `paper-wiki-language` gate for formal page prose quality.
- Source-map-grounded page writes across the formal wiki families:
  `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`,
  `reports/`, and `opportunities/`.
- Post-task checks for provenance, language, links, tags, aliases,
  `_meta/reference-index.json`, QMD freshness when configured, and Paper Source
  record readiness.

Paper Source `wiki-ask` and `wiki-query` are programmatic fallback or diagnostic
surfaces. The normal conversational wiki path is Paper Wiki
`paper-research-wiki`.

## Boundaries

These boundaries are part of the project contract:

- Paper Source does not write final formal wiki pages.
- Paper Wiki does not discover papers, acquire PDFs, parse with MinerU, write
  Paper Source approval records, or replace `wiki-ingest-record.json`.
- `wiki-ingest-brief.json` is the canonical new Paper Source to Paper Wiki
  handoff. Historical `wiki_deposition_task.json` artifacts are cleanup inputs,
  not the current user path.
- `paper-wiki-language` is a supporting language gate, not a competing public
  assistant.
- External wiki helper skills are optional helpers or policy references, not
  runtime-required dependencies.
- Source checkout validation is not installed runtime validation. Marketplace
  refresh, reinstall, and installed-cache verification are separate steps.

## Installation

Install through Codex Desktop as a plugin marketplace source:

1. Open Plugin Marketplaces.
2. Add this repository as a marketplace source:

   ```text
   https://github.com/initiatione/paperflow
   ```

3. Use Git ref `main` and leave sparse path empty.
4. Install `Paper Source` and `Paper Wiki` from the PaperFlow marketplace.

After installation, start a new Codex thread and mention Paper Source, PS, or
`@paper-source` for discovery/source-preparation work. Mention Paper Wiki, PW,
`@paper-wiki`, or Paper Research Wiki for formal wiki work.

For a source checkout used as a local marketplace during development,
`marketplace.json` points to:

```text
./plugins/paper-source
./plugins/paper-wiki
```

## First Run

Paper Source needs local runtime configuration before the full workflow can run:

- A target Obsidian/LLM wiki vault.
- `paper-search-mcp` or compatible paper-search CLI access.
- Optional `grok-search-rs` MCP command/env file; the plugin installs the MCP
  entry, while endpoint, key, and model stay in user-level runtime config.
- MinerU credentials for PDF-to-Markdown parsing when source bundles are built.
- Optional provider credentials for Unpaywall, Semantic Scholar, CORE, DOAJ,
  Zenodo, EasyScholar, Grok-compatible search, and Zotero.

Start with:

```powershell
python plugins\paper-source\scripts\orchestrator.py doctor --json
python plugins\paper-source\scripts\orchestrator.py init-config --vault <vault>
```

Common development-checkout commands:

```powershell
python plugins\paper-source\scripts\orchestrator.py discover-papers --query "<topic>" --max-results 20 --vault <vault> --json
python plugins\paper-source\scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python plugins\paper-source\scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
python plugins\paper-source\scripts\orchestrator.py record-human-approval --slug <paper-slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
python plugins\paper-source\scripts\orchestrator.py record-wiki-ingest --from-paper-wiki-request <request.json> --vault <vault>
```

Paper Wiki is primarily a Codex skill surface, not an orchestrator-style CLI.
It does ship narrow helper wrappers for maintenance tasks such as reference
index refresh and figure/formula support.

## Repository Layout

```text
.
|-- marketplace.json
|-- docs/
|   `-- plugin-development.md
|-- plugins/
|   |-- paper-source/
|   |   |-- .codex-plugin/plugin.json
|   |   |-- docs/
|   |   |-- scripts/
|   |   `-- skills/
|   `-- paper-wiki/
|       |-- .codex-plugin/plugin.json
|       |-- docs/
|       |-- scripts/
|       |-- rules/
|       `-- skills/
|-- scripts/
|   |-- paperflow_audit.py
|   |-- release_check_paper_source.ps1
|   `-- release_check_paper_wiki.ps1
`-- tests/
```

Important sources of truth:

- `plugins/<plugin>/.codex-plugin/plugin.json` is the plugin manifest.
- `plugins/<plugin>/skills/routing.yaml` is the route manifest.
- `plugins/<plugin>/skills/*/SKILL.md` is the thin skill entrypoint.
- `plugins/<plugin>/skills/*/agents/openai.yaml` is the skill UI metadata.
- `docs/plugin-development.md` is the required development gate for plugin,
  skill, workflow, test, manifest, marketplace, and contract changes.

## Development

Install the test dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Before changing plugin code, skills, workflows, docs, tests, generated
contracts, release scripts, or marketplace-visible behavior, read:

- `docs/plugin-development.md`
- `plugins/paper-source/AGENTS.md`
- `plugins/paper-source/skills/routing.yaml`
- `plugins/paper-wiki/AGENTS.md`
- `plugins/paper-wiki/skills/routing.yaml`

Keep plugin edits in `plugins/...`, not in the installed Codex cache. If a
change modifies plugin-visible behavior or metadata, bump the affected plugin
version and update marketplace mirrors according to
`docs/plugin-development.md`.

## Validation

Baseline source-checkout checks:

```powershell
python -m pytest tests\paper_research_wiki\test_plugin_contract.py tests\paper_source\test_skill_bundle_contract.py tests\test_marketplace_manifest.py -q
python -m json.tool plugins\paper-source\.codex-plugin\plugin.json > $null
python -m json.tool plugins\paper-wiki\.codex-plugin\plugin.json > $null
git diff --check
```

Route and package hygiene checks:

```powershell
python scripts\paperflow_audit.py route-health plugins\paper-source --json
python scripts\paperflow_audit.py route-health plugins\paper-wiki --json
python scripts\paperflow_audit.py package-hygiene plugins\paper-source --json
python scripts\paperflow_audit.py package-hygiene plugins\paper-wiki --json
```

Release-oriented checks:

```powershell
scripts\release_check_paper_source.ps1
scripts\release_check_paper_wiki.ps1
```

These commands validate the source checkout. To claim a user runtime is updated,
also refresh/reinstall the marketplace plugin and verify the installed cache in
a new Codex session.

## Security And Privacy

Do not commit runtime secrets, provider tokens, vault-private papers, installed
cache contents, or generated user vault artifacts. Runtime credentials should
come from the user's environment or approved local env files. Plugin logs and
reports must describe whether a secret is configured without printing the
secret value.

## License

Both plugin manifests declare the project license as MIT.
