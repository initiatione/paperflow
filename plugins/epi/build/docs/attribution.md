# Attribution

This plugin wraps and learns from mature research tooling while keeping runtime contracts explicit.

## openags/paper-search-mcp

The discovery layer wraps `openags/paper-search-mcp` as an external dependency. The plugin adapter records the upstream command, version or availability probe result, source names, query, source counts, upstream errors, and raw response path for every live discovery run.

Phase 1 uses the upstream `paper-search search` CLI contract for live search and keeps the stdio MCP server as a separately documented MCP integration. The verified PyPI package `paper-search-mcp==0.1.3` does not provide console scripts; live CLI use currently requires a PATH `paper-search` command from upstream GitHub `main` or an `EPI_PAPER_SEARCH_COMMAND` wrapper.

## MinerU

The PDF parsing stage reuses the existing local MinerU precise batch workflow from `plugins/mineru-paper-parser`. Tokens are read from `MINERU_TOKEN` or `.env/mineru.env` and must not be committed.

## Ar9av LLM Wiki Pattern

The dedicated paper wiki follows the raw source -> compiled wiki -> schema pattern. Raw paper assets remain under `_raw`, while compiled pages live under `references`, `concepts`, and `synthesis`.

## Nature-style Reader Inspiration

Future reader stages can borrow figure-aware and source-grounded reading patterns from Nature-style paper-reader workflows, adapted for engineering papers rather than manuscript submission.
