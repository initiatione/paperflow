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
Get-ChildItem C:\Users\liuchf\.codex\plugins\cache\paper-search\epi
```

Run the read-only doctor command from the installed plugin directory:

```powershell
cd C:\Users\liuchf\.codex\plugins\cache\paper-search\epi\<version>
python scripts\orchestrator.py doctor
python scripts\orchestrator.py doctor --json
```

`doctor` returns non-zero only when the plugin structure itself is broken. Missing live dependencies such as `paper-search`, `MINERU_TOKEN`, a MinerU command, or an uninitialized EPI vault config are reported as warnings so offline checks remain usable.

When `paper-search` or `MINERU_TOKEN` is missing, `doctor` prints first-use setup links and PowerShell examples. It does not open a browser unless you explicitly ask it to:

```powershell
python scripts\orchestrator.py doctor --open-setup
```

Use `--open-setup` when you want EPI to open the paper-search and MinerU setup pages for the currently missing items.

If `doctor` reports `epi_config: warning`, run `config-status` and complete the chat-style initialization in `plugins\epi\docs\config.md` before starting paper discovery.

## Plugins

- `epi`: Engineering Paper Intelligence. Searches, ranks, preserves, parses, reviews, and promotes engineering papers into a dedicated paper research wiki.
- `mineru-paper-parser`: Local MinerU precise-batch paper parser used as a lower-level parsing capability.

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
