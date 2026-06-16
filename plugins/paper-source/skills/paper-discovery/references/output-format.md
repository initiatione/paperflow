# Output Format

When the user asks to "find papers", "找最新/高质量论文", "不要综述", or similar, do not stop at the raw dry-run report. Run the Paper Source discovery evidence first, then curate the chat answer for reading decisions from `report.json.session_recommendations`.

In the chat, present the curated result in a scan-friendly format before technical logs. The section title can be `推荐优先看`. Use `session_recommendations.primary_recommendations` as the primary list: it is capped at 10 papers by default and includes only non-`review-candidate` Tier A/B or `advance-candidate` papers. Do not mix Tier C or `review-candidate` papers into the primary list. Use `session_recommendations.review_appendix` for a compact lower-priority appendix, and mention `session_recommendations.overflow.hidden_count` when more primary candidates exist in the artifact. Do not output an unsorted title-only list.

For each primary item, report:

- a numbered title line in reading-priority order
- venue/year
- paper type and classification confidence
- quality tier and the strongest `quality_reason` / `quality_gate` evidence
- DOI, using `未核实` or `缺失` from the contract when unavailable
- citation count or `未核实`
- impact factor/quartile, CiteScore, or `未核实`
- EasyScholar metrics from `verified_metrics.easyscholar` when present; otherwise `未核实`
- venue prior, if it affected ordering
- PDF/manual-download status and auto-staging status
- a short Chinese abstract / summary, 2-3 compact sentences explaining method, task, evidence, and caveat

Paper Source scripts do not generate semantic Chinese summaries. The calling agent writes the Chinese summary from `original_abstract` / `chinese_summary.source_text` and keeps the original provider abstract in artifacts for audit.

Then add `Paper Source 实测证据` with:

- run path
- `source_mode`
- whether the answer came from a fresh Paper Source run, a resumed review session, or an existing run artifact; if live web search was used, label it as targeted verification and name the candidate identity it verified
- query strategy: `query_plan_multi_query`, `single_query`, or fixture mode
- query plan summary: domain, concept blocks, query variants
- candidate pool size before/after dedup/filter when available
- ranking evidence: `paper_type`, `quality_tier`, `quality_gate`, `ranking_confidence`, and key rubric dimensions
- EasyScholar evidence: `easyscholar-record.json`, `easyscholar_score`, and matched/no-match/missing-key counts when checked
- accepted/rejected counts
- `session_recommendations.rejected_summary` count/reason summary
- review exclusion evidence, wiki backlog exclusions such as `already_in_wiki:<page>`, and raw-library exclusions such as `already_in_library:<slug>`
- query variants and whether a sharper rerun was needed
- venue prior sources used, especially configured field venues or curated field lists; weak community hints must be labeled as unverified context
- citation graph expansion evidence when used
- recall gaps if any
- `MINERU_TOKEN` set/missing only if setup was checked

Quality metrics must be current evidence, not memory or guesses. Verify citation counts, impact factor/quartile, CiteScore, publisher/venue metadata, EasyScholar venue metrics, or code availability when available; otherwise write `未核实` for that field.

For each recommendation, avoid raw JSON and long abstracts. Use links when verified. If the full kept list is long, do not list every kept paper in `推荐优先看`; use the capped primary list, appendix, and overflow count. Rejected review/survey papers should not appear in `推荐优先看` when the user asked to exclude them.

Do not present a Firecrawl/web-only result set as a Paper Source recommendation. If no Paper Source run/candidate artifact exists yet, say that discovery has not been run and run or request a Paper Source dry-run before making a reading recommendation.
