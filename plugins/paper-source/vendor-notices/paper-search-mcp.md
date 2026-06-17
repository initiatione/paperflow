# paper-search-mcp Notice

Upstream project: `openags/paper-search-mcp`.

Paper Source uses this as an external discovery dependency and does not vendor upstream source.

Verified on 2026-06-17: Paper Source prefers the upstream stdio MCP server through `python -m paper_search_mcp.server` or `PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND`. Discovery calls MCP `search_papers`, preserves `sources_used`, `source_results`, `errors`, source counts, and total counts in Paper Source run reports, and falls back to the `paper-search` CLI from upstream `main` or a `PAPER_SOURCE_PAPER_SEARCH_COMMAND` wrapper if MCP is unavailable, times out, returns an error, or returns no discoverable papers.

Capability boundary: upstream `openags/paper-search-mcp` is broad retrieval and metadata infrastructure. Its `search_papers` implementation runs selected sources concurrently, normalizes output, deduplicates by DOI/title/authors/source id, and reports source-level counts and errors. It does not provide Paper Source's semantic reranking, cross-discipline quality gate, DOI-required recommendation policy, or chat-facing `session_recommendations`. Some upstream sources are inherently unstable or scoped, including Google Scholar bot detection, Semantic Scholar rate limits, CORE/BASE/SSRN/provider gaps, and Unpaywall DOI-lookup-only behavior. Treat those as recall/source-coverage diagnostics; do not treat upstream ordering or source availability as final paper quality.

Acquisition policy: try MCP `download_with_fallback` first with Sci-Hub disabled by default, then source-native MCP `download_<source>`, then CLI/direct URL fallback when MCP cannot produce usable artifacts. Paper Source records MCP probe, fallback chain, `use_scihub`, upstream tool evidence, and raw response provenance, and keeps adaptation in `scripts/build/paper_source/paper_search_adapter.py`.

Retrieval preview policy: after a successful acquisition, Paper Source may call MCP `read_<source>_paper` or CLI read to create `paper-search-read-preview.txt` and record `retrieval_preview`. This is a non-authoritative retrieval preview for upstream extraction visibility; MinerU remains canonical parse/source artifact path, and the preview is not replacing MinerU or final source-first wiki review.
