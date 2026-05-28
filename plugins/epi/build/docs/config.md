# Configuration

Publishable examples live under `templates/`.

Private secrets live outside committed files:

- `MINERU_TOKEN` environment variable, or
- `D:\paper-search\.env\mineru.env`
- optional paper-search upstream variables such as `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`, `PAPER_SEARCH_MCP_CORE_API_KEY`, and `PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY`
- optional `EPI_MINERU_COMMAND` when the bundled MinerU precise batch script is not the desired parser command

The committed `.env_example` file is a template only. It must not contain real API tokens.

Default paper wiki:

`D:\paper-research-wiki`

Phase 1 dry-run writes only `_runs/<run-id>/` artifacts. It does not write compiled pages under `references`, `concepts`, or `synthesis`.

Live discovery command:

- Default CLI command: `paper-search`
- Override: `EPI_PAPER_SEARCH_COMMAND`
- CLI override flag: `--paper-search-command`
- Source override flag: `--sources arxiv,semantic,openalex`
- Expected CLI shape: `paper-search search "<query>" -n <max-results> -s arxiv,semantic,openalex,crossref,dblp`

Current upstream packaging boundary:

- PyPI `paper-search-mcp==0.1.3` can be installed for `python -m paper_search_mcp.server`.
- PyPI `paper-search-mcp==0.1.3` does not expose `paper-search` console scripts.
- Upstream GitHub `main` exposes the `paper-search` CLI. On Windows, prefer a local wrapper script in `D:\paper-search\.env\` and point `EPI_PAPER_SEARCH_COMMAND` at it.

MinerU parse command:

- Default command: bundled `skills\mineru-paper-parser\scripts\mineru_batch_to_md.py` through the current Python interpreter.
- Override: `EPI_MINERU_COMMAND`
- CLI override flag: `--mineru-command`
- EPI passes `--project-root`, `--input-dir`, `--output-dir`, and `--layout document-dir` to the command.
- The command should write Markdown under the configured output directory. If it writes a `mineru_batch_<batch_id>.json` manifest, EPI imports it as `_raw\papers\<paper-slug>\mineru\mineru-manifest.json`.
- Parse stdout/stderr logs stay under `_raw\papers\<paper-slug>\mineru-command\`.
