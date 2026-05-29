# paper-search-mcp Notice

Upstream project: `openags/paper-search-mcp`.

EPI uses this as an external discovery dependency and does not vendor upstream source.

Verified on 2026-05-30: EPI prefers the upstream stdio MCP server through `python -m paper_search_mcp.server` or `EPI_PAPER_SEARCH_MCP_COMMAND`. If the MCP server is unavailable, times out, returns an error, or returns no discoverable papers, EPI falls back to the `paper-search` CLI from upstream `main` or an `EPI_PAPER_SEARCH_COMMAND` wrapper.

Policy: try MCP first for discovery/acquisition, use CLI fallback when MCP cannot produce usable artifacts, record MCP probe and fallback evidence, preserve raw response provenance, and keep adaptation in `scripts/build/epi/paper_search_adapter.py`.
