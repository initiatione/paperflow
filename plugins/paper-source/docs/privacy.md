# Privacy

EPI is a local Codex plugin for profile-driven academic paper discovery and workflow preparation.

Phase 1 reads local templates, the target vault EPI config, and optional fixture files. It calls the configured external paper-search MCP server first, falls back to the paper-search CLI when MCP is unavailable or returns no usable papers, and writes run artifacts under the configured paper research wiki. It records source coverage and raw-response provenance, but it does not upload PDFs, call MinerU, write Zotero, or write compiled wiki pages.

Later phases may call configured external services such as paper-search MCP, MinerU, or Zotero only when the corresponding stage is enabled by the user. PDF acquisition may pass DOI, title, source id, and output path to paper-search MCP `download_with_fallback`; Sci-Hub remains disabled by default and is called only when the user explicitly opts in with `EPI_PAPER_SEARCH_MCP_USE_SCIHUB=1` or equivalent runtime env.

After successful acquisition, EPI may call upstream paper-search-mcp `read_<source>_paper` or CLI read with the source id, paper id, and a local save path to create the non-authoritative preview sidecar `paper-search-read-preview.txt`. The result is recorded as `retrieval_preview` and may depend on upstream paper indexes or provider terms. It stores no token/secret value, does not upload local MinerU outputs, and is not replacing MinerU as the source-first parse path.
