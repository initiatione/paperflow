# Output Format

When the user asks to "find papers", "找最新/高质量论文", "不要综述", or similar, use `discover-papers` as the natural-language Paper Source default. Do not stop at a raw dry-run report. Run the Paper Source discovery evidence first, then curate the chat answer for reading decisions from `report.json.session_recommendations`.

## Required Chat Response Shape

Final chat responses for discovery runs must carry the chat-visible decision sections explicitly. Do not rely on the user opening `report.md` to recover omitted sections. Use this order:

1. Run status and artifact path.
2. Primary/new recommendations, or an explicit `主推荐：无`.
3. If primary is empty, the reason summary, `dominant_blocking_reason`, counts, `top_blocked_candidates`, and next action from `session_recommendations.no_primary_recommendations_summary`.
4. `新增待复核候选` when `session_recommendations.review_appendix` is non-empty; otherwise state it is empty when that matters to explain the outcome.
5. `库中已有，可回看` from `session_recommendations.existing_library_appendix` as a separate Markdown table when present.
6. Provider/runtime caveats and `Paper Source 实测证据`, including Grok contribution only when artifacts show usable evidence.

In the chat, present the curated result in a scan-friendly format before technical logs. The section title can be `推荐优先看` only when `session_recommendations.primary_recommendations` is non-empty. Use `session_recommendations.primary_recommendations` as the primary list: it is capped at 10 papers by default and includes only new papers that were not rejected by `already_in_wiki:*` or `already_in_library:*`, only non-`review-candidate` Tier A/B or `advance-candidate` papers, and only DOI-present papers. Do not mix Tier C, `review-candidate`, already-in-wiki, already-in-library, or DOI-missing papers into the primary list. Use `session_recommendations.review_appendix` for a compact lower-priority section titled `新增待复核候选`; this appendix is also DOI-present and non-Reject only. Do not manually add `quality_tier=Reject` / `quality_gate.tier=Reject` papers to the appendix; summarize them from `session_recommendations.quality_reject_debug` as diagnostics when useful. If primary recommendations are empty but review appendix is non-empty, do not call the review appendix `推荐优先看`; explicitly say this is `review_appendix_available_not_primary` when `no_primary_recommendations_summary.secondary_candidate_status` says so. Mention `session_recommendations.overflow.hidden_count` when more primary candidates exist in the artifact. Use `session_recommendations.existing_library_appendix` only for a separate `库中已有，可回看` reminder section; never call those items recommendations and never include them in auto-staging. Do not output an unsorted title-only list.

Render primary recommendations as a numbered list, not as a dense table. Each item must use this chat shape:

```markdown
1. Paper title
   Journal or conference, year; DOI: [10.xxxx/example](https://doi.org/10.xxxx/example); OpenAlex citations: 55.
   summary：说明这篇论文用了什么方法，解决什么问题，效果、验证或证据如何。
```

The `summary：` line is required for each primary item. It should be derived from `original_abstract`, `chinese_summary.source_text`, provider metadata, and verified report fields. Explain the method/system, target problem/task, and reported effect/result/validation evidence when available. If the available abstract does not clearly state the effect or validation result, say that the effect is not clear from the current abstract instead of inventing one. Keep detailed quality-gate, DOI recovery, Grok, and artifact diagnostics in the evidence sections unless they are necessary to explain a specific item.

Format `库中已有，可回看` as a short explanatory sentence plus a Markdown table, not as a one-line semicolon-separated list. Recommended table columns are `论文`, `年份`, `状态`, and `入口`; add `DOI` when present. Use `状态` values such as `已在 wiki` for `already_in_wiki:*` / `existing_source_type=wiki_reference_index` and `已在 raw library` for `already_in_library:*` / `existing_source_type=raw_library`. Start the section with wording like `这些论文已在当前 wiki/raw library 中命中，未重复放入新推荐：`. Keep this section after `新增待复核候选` and before technical evidence, unless there are no existing-library hits.

DOI is required for `session_recommendations.primary_recommendations` and `session_recommendations.review_appendix`. Paper Source may use targeted DOI recovery through configured Grok/web search for DOI-missing candidates before filtering. In the chat, report `session_recommendations.doi_recovery_summary`, `session_recommendations.doi_resolution_summary`, and `session_recommendations.doi_filtered_summary`: say how many DOI lookups succeeded, how many failed, and list DOI-filtered candidates briefly so promising papers are not silently lost. Do not manually re-add DOI-missing or DOI-unverified papers to the recommendation list; present them as DOI待补 / `missing_required_doi` candidates.

For each primary item, report:

- a numbered title line in reading-priority order
- venue/year
- paper type and classification confidence
- quality tier and the strongest `quality_reason` / `quality_gate` evidence
- DOI plus `doi_url`; these should be present for every primary/review item
- primary link from `primary_url` when present
- citation count plus `citation_count_source` and `citation_count_status`; show `未核实` only when status/source are absent
- impact factor/quartile, CiteScore, or `未核实`
- EasyScholar metrics from `verified_metrics.easyscholar` when present; otherwise `未核实`
- venue prior, if it affected ordering
- quality risk status from `quality_risk`: show verified/suspected/unverified and list cautions; missing provider risk data is `unverified`, not safe
- PDF/manual-download status and auto-staging status
- a short Chinese abstract / summary, 2-3 compact sentences explaining method, task, evidence, and caveat

Paper Source scripts do not generate semantic Chinese summaries. The calling agent writes the Chinese `summary：` line from `original_abstract` / `chinese_summary.source_text` and keeps the original provider abstract in artifacts for audit.

Then add `Paper Source 实测证据` with:

- run path
- `discover-papers` run path plus linked discovery / auto-staging run ids when available
- `source_mode`
- whether the answer came from a fresh Paper Source run, a resumed review session, or an existing run artifact; if live web search was used, label it as targeted verification and name the candidate identity it verified
- query strategy: `query_plan_multi_query`, `single_query`, or fixture mode
- query plan summary: domain, concept blocks, query variants
- candidate pool size before/after dedup/filter when available
- ranking evidence: `paper_type`, `quality_tier`, `quality_gate`, `ranking_confidence`, and key rubric dimensions
- quality gate dimensions: summarize `quality_gate.dimensions.identity`, `relevance`, `inspectability`, `validation`, `source_confidence`, `reproducibility`, `request_risk`, and `quality_risk` when they explain why a paper was kept, held for review, or rejected
- `recall-gap-record.json`: recovered official versions, related papers, cited-by papers, or references plus filter summary when provider metadata supplied them
- `quality-risk-record.json`: verified/suspected/unverified risk counts and any verified severe risk evidence
- EasyScholar evidence: `easyscholar-record.json`, `easyscholar_score`, and matched/no-match/missing-key counts when checked
- accepted/rejected counts
- `session_recommendations.rejected_summary` count/reason summary
- `session_recommendations.existing_library_appendix` as a separate already-in-library/wiki reminder, not a recommendation list
- `session_recommendations.verification_summary`; when it reports unverified citation counts, venue metrics, or quality-risk data, say which recommendations still need targeted verification instead of silently filling numbers
- `session_recommendations.doi_filtered_summary`; when total is non-zero, say DOI-missing candidates were filtered as `missing_required_doi`
- `session_recommendations.doi_recovery_summary` and `session_recommendations.doi_resolution_summary`; show DOI recovery success/failure counts before explaining any filtered candidates
- `session_recommendations.no_primary_recommendations_summary` when primary recommendations are empty; explain whether DOI policy, quality gates, existing-library saturation, or recall/search gaps caused the empty primary list
- `session_recommendations.no_primary_recommendations_summary.dominant_blocking_reason`, `.counts`, `.secondary_candidate_status`, and `.top_blocked_candidates` when primary recommendations are empty; top blocked candidates are diagnostics only and must not be renamed as recommendations
- `session_recommendations.quality_reject_debug` when quality-gate Reject candidates matter for debugging; report counts and representative blocking reasons, not as recommendations
- Grok supplemental status from `provider_records.grok_search`: call Grok valid evidence only when `status=ok`, `record_count>0`, and there is no provider/source fallback warning; if `source_fallback`, `fallback_used`, `grok_provider_error`, `timeout_after_paper_search`, `not_configured`, or warnings appear, say Grok was attempted/configured but not valid recommendation evidence
- `auto_staging_plan` summary when automatic source-staging ran: selected count, skipped reasons, and `auto_staging_status` values
- review exclusion evidence, wiki backlog exclusions such as `already_in_wiki:<page>`, and raw-library exclusions such as `already_in_library:<slug>`
- query variants and whether a sharper rerun was needed
- venue prior sources used, especially configured field venues or curated field lists; weak community hints must be labeled as unverified context
- citation graph expansion evidence when used
- recall gaps if any
- `MINERU_TOKEN` set/missing only if setup was checked

Quality metrics must be current evidence, not memory or guesses. Verify citation counts, impact factor/quartile, CiteScore, publisher/venue metadata, EasyScholar venue metrics, or code availability when available; otherwise write `未核实` for that field. A numeric citation value is verified only when `citation_count_status=verified` and `citation_count_source` is present; a missing provider citation field is not the same as a verified `0`.

For each recommendation, avoid raw JSON and long abstracts. Use links when verified. If the full kept list is long, do not list every kept paper in `推荐优先看`; use the capped primary list, appendix, and overflow count. Rejected review/survey papers and quality-tier Reject papers should not appear in `推荐优先看` or `新增待复核候选`.

Do not present a Firecrawl/web-only result set as a Paper Source recommendation. If no Paper Source run/candidate artifact exists yet, say that discovery has not been run and run or request a Paper Source dry-run before making a reading recommendation.
