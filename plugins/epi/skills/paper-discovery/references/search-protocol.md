# Search Protocol

Treat `paper_search_mcp` as a search transport, not as the definition of quality. The user usually wants papers that are worth reading, not just papers that one source happened to return. Borrow the discipline of multi-source academic search: explicit query construction, source routing, deduplication, citation/venue verification, and a visible evidence trail.

Before running the first query:

1. Split the topic into concept blocks: domain object, method family, control task, environment/disturbance, validation mode, and exclusions.
2. Build 3-5 query variants instead of one vague query. Include exact phrases, synonyms, acronym expansions, and task-specific terms.
3. For non-review requests, every query variant should carry `-review -survey` and the filter stage should still enforce the exclusion.
4. Route sources by intent: use `paper_search_mcp` first with `arxiv,semantic,openalex` for robotics/AI/control; use live academic/web search to verify recent journal papers, DOI pages, citation counts, JCR/CiteScore-style metrics, code/PDF availability, and gaps that MCP missed.
5. Apply `venue-prior.md` as a recall/ranking prior. For robotics/control, check whether flagship robotics, robot learning, AI/ML, and domain venues are missing. For AUV work, include marine engineering/ocean robotics venues.
6. Deduplicate across variants by DOI first, then normalized title.
7. Deduplicate against the downloaded wiki library under `_raw\papers`. A paper already present in `_raw\papers\<slug>\metadata.json` must be rejected with `already_in_library:<slug>` and should not be recommended again unless the user explicitly asks to repair or reprocess that existing paper.

If the first result set is generic, stale, or too review-heavy, run a sharper rerun rather than stopping early.
