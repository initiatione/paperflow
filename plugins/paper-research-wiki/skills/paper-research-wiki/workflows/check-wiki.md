# Check Wiki

Use this when the user asks to detect or inspect the paper wiki library. Also run it as the preflight for vague EPI deposition requests.

Check:

- target vault contract files
- pending EPI handoffs
- staged pages
- missing `final-source-review.json`
- lint failures
- duplicate concept candidates
- provenance gaps
- stale tags or aliases
- relink and cross-link opportunities

Return a concise status grouped by ready, blocked, warning, and next action. Do not output raw JSON unless the user asks.
