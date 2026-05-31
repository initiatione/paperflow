# Search Protocol

Treat `paper_search_mcp` as a search transport, not as the definition of quality. The user usually wants papers that are worth reading, not just papers that one source happened to return. Borrow the discipline of multi-source academic search: explicit query construction, source routing, deduplication, citation/venue verification, and a visible evidence trail.

Before running the first query:

1. Build a query plan using `query-planner.md` and the optional `scripts/query-planner.py` helper.
2. Split the request using the user's config/profile: discipline/domain, method or topic terms, problem/task, context, quality evidence, venue prior, and exclusions.
3. Build 5-8 query variants instead of one vague query. Include exact phrases, synonyms, acronym expansions, and task-specific terms derived from config first; load `domain-ontology.md` only as optional examples.
4. Default discovery is non-review: every query variant should carry `-review -survey` and the filter stage should still enforce the exclusion. Skip this only when the user explicitly asks for review or survey papers.
5. Route sources by intent: use `paper_search_mcp` first with configured sources such as `arxiv,semantic,openalex,crossref`; use live academic/web search to verify recent journal papers, DOI pages, citation counts, JCR/CiteScore-style metrics, code/PDF availability, and gaps that MCP missed.
6. Apply `two-stage-retrieval.md`: first form a high-recall candidate pool, then deduplicate, verify, and precision-rank.
7. Apply `venue-prior.md` as a recall/ranking prior from user config. Check whether the user's configured flagship venues, journals, conferences, or field databases are missing before accepting the result set.
8. Deduplicate across variants by DOI first, then normalized title.
9. Deduplicate against the downloaded wiki library under `_raw\papers`. A paper already present in `_raw\papers\<slug>\metadata.json` must be rejected with `already_in_library:<slug>` and should not be recommended again unless the user explicitly asks to repair or reprocess that existing paper.
10. For strong seed papers, use `citation-graph.md` to check journal versions, related papers, references, and recent cited-by papers.

For any narrow field, do not let the query planner blur the target into generic AI/science terms. If the first planned run broadens away from the user's configured profile or current request, rerun with `--no-query-plan` and exact phrases from the user's wording, or update config before rerunning.

Treat publisher PDF blocks as acquisition evidence, not as the end of discovery. HTTP 403/502 from IEEE, Wiley, or publisher PDFs should be reported as publisher PDF blocks; then try open sources, arXiv versions, DOI landing pages, Semantic Scholar/OpenAlex metadata, or a sharper arXiv-first query before concluding that the paper cannot be processed.

If the first result set is generic, stale, too review-heavy, or full of blocked PDFs, run a sharper rerun rather than stopping early.
