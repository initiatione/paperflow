# Discovery Anti-Patterns

Use this checklist when dry-run results look plausible but the recommendation quality is weak.

| Anti-pattern | Symptom | Correct action |
| --- | --- | --- |
| Search order treated as quality | First MCP/CLI results are reported without reranking | Run two-stage retrieval and inspect `rank.json`. |
| Method-only leakage | Generic RL/GNN/AI papers pass a narrow domain query | Enforce `domain_focus_terms` and reject `outside_domain`. |
| Review leakage | Surveys appear in non-review recommendations | Confirm query variants contain review exclusions and filter reasons include review/survey/meta. |
| Venue prior as fact | A venue name becomes proof of quality | Label venue prior separately; verify metrics or write `unverified`. |
| Duplicate library hits | Already downloaded papers are recommended again | Check `_epi/raw/*/metadata.json` and use `already_in_library:<slug>`. |
| Classification overreach | A weak title/abstract signal is treated as final paper type | Treat `paper_classification` as a routing hint until source reading. |
| Summary replaces source | Reader/report is used as if it were the paper | Move to source-first ingest and read `mineru/<slug>.md`, TeX, images, and manifest. |
| Figure/formula blindness | Important diagrams or equations never enter notes | Require source-first figure/formula review during ingest. |
| Silent recall gap | Expected venue family or seed paper family is absent | Run citation-graph expansion or sharper query variants and record the gap. |
