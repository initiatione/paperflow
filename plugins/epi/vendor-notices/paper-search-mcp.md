# paper-search-mcp Notice

Upstream project: `openags/paper-search-mcp`.

EPI uses this as an external discovery dependency and does not vendor upstream source.

Verified on 2026-05-27: PyPI `paper-search-mcp==0.1.3` exposes the MCP server through `python -m paper_search_mcp.server` but no console scripts. Live EPI discovery expects a `paper-search` CLI from upstream `main` or an `EPI_PAPER_SEARCH_COMMAND` wrapper.

Policy: probe before discovery, fail closed when unavailable, preserve raw response provenance, and keep adaptation in `scripts/build/epi/paper_search_adapter.py`.
