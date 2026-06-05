# Search Protocol

Treat `paper_search_mcp` as a search transport, not as the definition of quality. The user usually wants papers that are worth reading, not just papers that one source happened to return. Borrow the discipline of multi-source academic search: explicit query construction, source routing, deduplication, citation/venue verification, and a visible evidence trail.

Before running the first query:

1. Build a query plan using `query-planner.md` and the optional `scripts/query-planner.py` helper.
2. Split the request using the user's config/profile: discipline/domain, method or topic terms, problem/task, context, quality evidence, venue prior, and exclusions.
3. Build 5-8 query variants instead of one vague query. Include exact phrases, synonyms, acronym expansions, and task-specific terms derived from config first; load `domain-ontology.md` only as optional examples.
4. Default discovery is non-review: every query variant should carry `-review -survey` and the filter stage should still enforce the exclusion. Skip this only when the user explicitly asks for review or survey papers.
5. Route sources by intent: use `paper_search_mcp` first with configured sources such as `arxiv,semantic,openalex,crossref,unpaywall`; use live academic/web search to verify recent journal papers, DOI pages, citation counts, JCR/CiteScore-style metrics, code/PDF availability, and gaps that MCP missed.
6. Apply `two-stage-retrieval.md`: first form a high-recall candidate pool, then deduplicate, verify, and precision-rank.
7. Apply the `domain_focus_terms` hard anchor gate before ranking when the query plan provides it. A paper that only matches a broad method term, such as reinforcement learning, graph neural network, or deep learning, but not the requested object/task/domain anchor should be rejected as `outside_domain`.
8. Apply `venue-prior.md` as a recall/ranking prior from user config. Check whether the user's configured flagship venues, journals, conferences, or field databases are missing before accepting the result set.
9. Deduplicate across variants by DOI first, then normalized title.
10. Deduplicate against the downloaded wiki library under `_epi\\raw`. A paper already present in `_epi\\raw\\<slug>\metadata.json` must be rejected with `already_in_library:<slug>` and should not be recommended again unless the user explicitly asks to repair or reprocess that existing paper.
11. For strong seed papers, use `citation-graph.md` to check journal versions, related papers, references, and recent cited-by papers.

After each dry-run, inspect `report.json.discovery_context.source_coverage` or the `Source Coverage` section in `report.md`. Treat `sources_used`, `source_results`, `errors`, `raw_total`, `deduped_total`, `query_count`, `capabilities`, and `provider_readiness` as recall evidence: a zero-count or errored configured source is a concrete gap to rerun or explain, an unsupported download/read capability is a source boundary, and a missing provider env is a recall/fallback risk rather than cosmetic telemetry. Use `doctor --json` to inspect `paper_search_provider_readiness` before blaming ranking when OA fallback is weak.

For any narrow field, do not let the query planner blur the target into generic AI/science terms. If the first planned run broadens away from the user's configured profile or current request, rerun with `--no-query-plan` and exact phrases from the user's wording, or update config before rerunning.

If the current request activates a domain hint pack, keep the hard anchor gate on that pack's strong synonyms and the user's configured domain terms. Long-query n-grams that describe only a broad task or object class are recall aids, not sufficient evidence for domain fit.

Treat publisher PDF blocks as acquisition evidence, not as the end of discovery. HTTP 403/502 from IEEE, Wiley, or publisher PDFs should be reported as publisher PDF blocks; then try open sources, Unpaywall, arXiv versions, DOI landing pages, Semantic Scholar/OpenAlex metadata, or a sharper arXiv-first query before concluding that the paper cannot be processed.

During acquisition, EPI should pass stable DOI/title/source identity to paper-search MCP `download_with_fallback` first. The default fallback chain is source-native, OpenAIRE, CORE, Europe PMC, PMC, and Unpaywall; Sci-Hub is disabled unless the user explicitly opts in. If MCP fallback fails, EPI may still try source-native MCP, CLI, and direct URL recovery. A DOI or publisher landing page is not a PDF. If a landing page exposes `citation_pdf_url` or an obvious publisher PDF link, EPI can follow it once. When merged candidates provide multiple `pdf_urls`, acquisition should try each candidate URL in order and record `candidate_pdf_urls` plus `acquire_attempts`; only after those fallbacks fail should `acquire-record.json` report `failure_class=not-pdf` or a publisher/network block and ask for a direct PDF/open-access source rather than sending HTML to MinerU.

If the first result set is generic, stale, too review-heavy, or full of blocked PDFs, run a sharper rerun rather than stopping early.
