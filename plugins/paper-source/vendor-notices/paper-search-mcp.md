# paper-search-mcp Notice

Upstream project: `openags/paper-search-mcp`.

EPI uses this as an external discovery dependency and does not vendor upstream source.

Verified on 2026-06-05: EPI prefers the upstream stdio MCP server through `python -m paper_search_mcp.server` or `EPI_PAPER_SEARCH_MCP_COMMAND`. Discovery calls MCP `search_papers`, preserves `sources_used`, `source_results`, `errors`, and total counts in EPI run reports, and falls back to the `paper-search` CLI from upstream `main` or an `EPI_PAPER_SEARCH_COMMAND` wrapper if MCP is unavailable, times out, returns an error, or returns no discoverable papers.

Acquisition policy: try MCP `download_with_fallback` first with Sci-Hub disabled by default, then source-native MCP `download_<source>`, then CLI/direct URL fallback when MCP cannot produce usable artifacts. EPI records MCP probe, fallback chain, `use_scihub`, upstream tool evidence, and raw response provenance, and keeps adaptation in `scripts/build/epi/paper_search_adapter.py`.

Retrieval preview policy: after a successful acquisition, EPI may call MCP `read_<source>_paper` or CLI read to create `paper-search-read-preview.txt` and record `retrieval_preview`. This is a non-authoritative retrieval preview for upstream extraction visibility; MinerU remains canonical parse/source artifact path, and the preview is not replacing MinerU or final source-first wiki review.
