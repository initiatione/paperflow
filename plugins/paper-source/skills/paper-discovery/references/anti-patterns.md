# Discovery Anti-Patterns

Use this checklist when dry-run results look plausible but the recommendation quality is weak.

| Anti-pattern | Symptom | Correct action |
| --- | --- | --- |
| Search order treated as quality | First MCP/CLI results are reported without reranking | Run two-stage retrieval and inspect `rank.json`. |
| Method-only leakage | Generic RL/GNN/AI papers pass a narrow domain query | Use explicit `hard_domain_anchors` when the user/config/Research Brief confirms them; otherwise keep inferred terms soft and surface the risk in diagnostics. |
| Review leakage | Surveys appear in non-review recommendations | Confirm query variants contain review exclusions and filter reasons include review/survey/meta. |
| Venue prior as fact | A venue name becomes proof of quality | Label venue prior separately; verify metrics or write `unverified`. |
| Duplicate library hits | Already deposited or downloaded papers are recommended again | Check `_meta/reference-index.json` first (`already_in_wiki:<page>`), then `_paper_source/raw/*/metadata.json` (`already_in_library:<slug>`). |
| Classification overreach | A weak title/abstract signal is treated as final paper type | Treat `paper_classification` as a routing hint until source reading. |
| Summary replaces source | Reader/report is used as if it were the paper | Move to source-first ingest and read `mineru/<slug>.md`, TeX, images, and manifest. |
| Figure/formula blindness | Important diagrams or equations never enter notes | Require source-first figure/formula review during ingest. |
| Silent recall gap | Expected venue family or seed paper family is absent | Run citation-graph expansion or sharper query variants and record the gap. |
| Web-first discovery | Firecrawl, generic web search, publisher search, or GitHub search is used before a Paper Source candidate/run artifact exists | Run or resume Paper Source `dry-run` / `paper_search_mcp.search_papers` first; use web search only for targeted DOI/arXiv/venue/code verification after candidates exist. |
| Repeat provider loop | The same topic is searched again even though a matching review session or recent `search-record.json` exists | Resume the review session, inspect existing artifacts, or use `report --run-id`; use `--refresh` only for explicit freshness or a documented recall gap. |
| Repository as paper identity | A GitHub repository is treated as proof that the corresponding paper should be recommended | First anchor the paper through DOI/arXiv/title and Paper Source metadata, then verify repository alignment as reproducibility evidence. |
