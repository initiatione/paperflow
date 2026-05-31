# Paper Search Codex Plugins

This repository publishes a Codex plugin marketplace for paper-search workflows.

## Add The Marketplace In Codex

In Codex, open **Plugin Marketplaces** and choose **Add marketplace**.

Use these values:

- Source: `https://github.com/initiatione/paper-search`
- Git ref: `main`
- Sparse path: leave empty

After the marketplace is added, select **Paper Search** from the marketplace dropdown and install `EPI`.

## Verify An Installed EPI Plugin

After installing from the Codex UI, start a new thread and mention `@epi`. If the CLI marketplace list has not caught up with the UI, check the local cache path instead:

```powershell
$cacheRoot = Join-Path $env:USERPROFILE ".codex\plugins\cache\paper-search\epi"
Get-ChildItem $cacheRoot
```

Run the read-only doctor command from the installed plugin directory:

```powershell
cd "$env:USERPROFILE\.codex\plugins\cache\paper-search\epi\<version>"
python scripts\orchestrator.py doctor
python scripts\orchestrator.py doctor --json
```

`doctor` returns non-zero only when the plugin structure itself is broken. Missing live dependencies such as `paper-search`, `MINERU_TOKEN`, a MinerU command, or an uninitialized EPI vault config are reported as warnings so offline checks remain usable.

When `paper-search` or `MINERU_TOKEN` is missing, `doctor` prints first-use setup links and PowerShell examples. It does not open a browser unless you explicitly ask it to:

```powershell
python scripts\orchestrator.py doctor --open-setup
```

Use `--open-setup` when you want EPI to open the paper-search and MinerU setup pages for the currently missing items.

If `doctor` reports `epi_config: warning`, run `config-status` and complete the chat-style initialization described in `plugins\epi\docs\config.md` before starting paper discovery. EPI is profile-driven: research profile, domains, positive/negative keywords, venue prior, and the current request decide query planning, source routing, ranking, and later wiki/reader emphasis.

## Plugins

- `epi`: A general academic paper intelligence workflow. It searches, ranks, preserves, parses, reviews, and stages papers for agent-mediated Obsidian/LLM Wiki ingest.

MinerU parsing is an internal EPI helper capability, not a separate marketplace plugin.

## Local Development

The canonical marketplace manifest for Codex is:

```text
.agents/plugins/marketplace.json
```

The root `marketplace.json` mirrors the same entries for local inspection and compatibility with older local workflows.

Development checks:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests\epi -q
python -m coverage run -m pytest tests\epi
python -m coverage xml -o plugins\epi\coverage\coverage.xml
```

EPI's source-of-truth chain document is `plugins\epi\docs\epi-linkage.md`. Every plugin change or optimization must check and update that document so the implementation stays aligned with the intended chain: profile-driven high-quality paper collection -> Obsidian/LLM Wiki knowledge deposition -> low-burden reading report.

MinerU parsing is part of the EPI pipeline, but the marketplace now exposes it only through the EPI plugin path rather than as a separate installable plugin.

For an installed or source checkout, the current handoff flow is:

```powershell
python plugins\epi\scripts\orchestrator.py paper-gate --slug <paper-slug> --vault <vault>
python plugins\epi\scripts\orchestrator.py wiki-ingest-handoff --slug <paper-slug> --vault <vault>
```

`wiki-ingest-handoff` is read-only. It renders the paper gate, target-vault contract files, wiki rule source priority, suggested routes, and agent checklist before the final Obsidian/LLM Wiki ingest.

EPI critic development treats `paper-quality-critic` as an academic paper reliability gate, not a file-existence check. It verifies stable paper identity, reader claim support, benchmark context for outperform/SOTA claims, and scope overclaim risk while preserving reproducibility gaps and MinerU parse limitations as warnings. Reader development also emits `reader/evidence-map.json` so editor, reviewer, and senior-researcher claims can be checked as structured evidence before promotion. The critic quorum includes role reviewers for editorial significance, peer-review methods, and fit to the user's configured research profile. Every reviewer now writes a machine-readable `review_protocol` with its lens, consumed artifacts, hard-fail checks, warning checks, and decision boundary so reader and critic responsibilities stay explicit in the run artifact. Critic runs also write `critic/reader-revision-plan.json` and `.md`, translating blocking failures and warnings into role-specific reader repair worklists for the Nature/Sci editor, peer reviewer, and senior domain researcher.
