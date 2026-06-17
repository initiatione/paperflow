# Output Format

When the user asks to "find papers", "找最新/高质量论文", "不要综述", or similar, use `discover-papers` as the natural-language Paper Source default. Do not stop at a raw dry-run report. Run the Paper Source discovery evidence first, then curate the chat answer for reading decisions from `report.json.session_recommendations`.

In the chat, present the curated result in a scan-friendly format before technical logs. The section title can be `推荐优先看` only when `session_recommendations.primary_recommendations` is non-empty. Use `session_recommendations.primary_recommendations` as the primary list: it is capped at 10 papers by default and includes only new papers that were not rejected by `already_in_wiki:*` or `already_in_library:*`, only non-`review-candidate` Tier A/B or `advance-candidate` papers, and only DOI-present papers. Do not mix Tier C, `review-candidate`, already-in-wiki, already-in-library, or DOI-missing papers into the primary list. Use `session_recommendations.review_appendix` for a compact lower-priority section titled `新增待复核候选`; if primary recommendations are empty but review appendix is non-empty, do not call the review appendix `推荐优先看`. Mention `session_recommendations.overflow.hidden_count` when more primary candidates exist in the artifact. Use `session_recommendations.existing_library_appendix` only for a separate `库中已有，可回看` reminder section; never call those items recommendations and never include them in auto-staging. Do not output an unsorted title-only list.

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
- PDF/manual-download status and auto-staging status
- a short Chinese abstract / summary, 2-3 compact sentences explaining method, task, evidence, and caveat

Paper Source scripts do not generate semantic Chinese summaries. The calling agent writes the Chinese summary from `original_abstract` / `chinese_summary.source_text` and keeps the original provider abstract in artifacts for audit.

Then add `Paper Source 实测证据` with:

- run path
- `discover-papers` run path plus linked discovery / auto-staging run ids when available
- `source_mode`
- whether the answer came from a fresh Paper Source run, a resumed review session, or an existing run artifact; if live web search was used, label it as targeted verification and name the candidate identity it verified
- query strategy: `query_plan_multi_query`, `single_query`, or fixture mode
- query plan summary: domain, concept blocks, query variants
- candidate pool size before/after dedup/filter when available
- ranking evidence: `paper_type`, `quality_tier`, `quality_gate`, `ranking_confidence`, and key rubric dimensions
- EasyScholar evidence: `easyscholar-record.json`, `easyscholar_score`, and matched/no-match/missing-key counts when checked
- accepted/rejected counts
- `session_recommendations.rejected_summary` count/reason summary
- `session_recommendations.existing_library_appendix` as a separate already-in-library/wiki reminder, not a recommendation list
- `session_recommendations.verification_summary`; when it reports unverified citation counts or venue metrics, say which recommendations still need targeted verification instead of silently filling numbers
- `session_recommendations.doi_filtered_summary`; when total is non-zero, say DOI-missing candidates were filtered as `missing_required_doi`
- `session_recommendations.doi_recovery_summary` and `session_recommendations.doi_resolution_summary`; show DOI recovery success/failure counts before explaining any filtered candidates
- Grok supplemental status from `provider_records.grok_search`: call Grok valid evidence only when `status=ok`, `record_count>0`, and there is no provider/source fallback warning; if `source_fallback`, `fallback_used`, `grok_provider_error`, `timeout_after_paper_search`, `not_configured`, or warnings appear, say Grok was attempted/configured but not valid recommendation evidence
- `auto_staging_plan` summary when automatic source-staging ran: selected count, skipped reasons, and `auto_staging_status` values
- review exclusion evidence, wiki backlog exclusions such as `already_in_wiki:<page>`, and raw-library exclusions such as `already_in_library:<slug>`
- query variants and whether a sharper rerun was needed
- venue prior sources used, especially configured field venues or curated field lists; weak community hints must be labeled as unverified context
- citation graph expansion evidence when used
- recall gaps if any
- `MINERU_TOKEN` set/missing only if setup was checked

Quality metrics must be current evidence, not memory or guesses. Verify citation counts, impact factor/quartile, CiteScore, publisher/venue metadata, EasyScholar venue metrics, or code availability when available; otherwise write `未核实` for that field. A numeric citation value is verified only when `citation_count_status=verified` and `citation_count_source` is present; a missing provider citation field is not the same as a verified `0`.

For each recommendation, avoid raw JSON and long abstracts. Use links when verified. If the full kept list is long, do not list every kept paper in `推荐优先看`; use the capped primary list, appendix, and overflow count. Rejected review/survey papers should not appear in `推荐优先看` when the user asked to exclude them.

Do not present a Firecrawl/web-only result set as a Paper Source recommendation. If no Paper Source run/candidate artifact exists yet, say that discovery has not been run and run or request a Paper Source dry-run before making a reading recommendation.
