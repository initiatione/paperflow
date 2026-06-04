# Output Format

When the user asks to "find papers", "找最新/高质量论文", "不要综述", or similar, do not stop at the raw dry-run report. Run the EPI discovery evidence first, then curate the chat answer for reading decisions.

In the chat, present the curated result in a scan-friendly format before technical logs. The section title can be `推荐优先看`, but the section must include every paper found and kept for this run, sorted by reading priority, not only the top few. Do not output an unsorted title-only list.

Each item should have:

- a numbered title line in reading-priority order
- venue/year
- paper type and classification confidence
- quality tier and the strongest `quality_gate` evidence
- DOI
- citation count or `未核实`
- impact factor/quartile, CiteScore, or `未核实`
- EasyScholar metrics from `verified_metrics.easyscholar` when present; otherwise `未核实`
- venue prior, if it affected ordering
- PDF/code availability
- a short Chinese abstract, 2-3 compact sentences explaining method, task, evidence, and caveat

Then add `EPI 实测证据` with:

- run path
- `source_mode`
- query strategy: `query_plan_multi_query`, `single_query`, or fixture mode
- query plan summary: domain, concept blocks, query variants
- candidate pool size before/after dedup/filter when available
- ranking evidence: `paper_type`, `quality_tier`, `quality_gate`, `ranking_confidence`, and key rubric dimensions
- EasyScholar evidence: `easyscholar-record.json`, `easyscholar_score`, and matched/no-match/missing-key counts when checked
- accepted/rejected counts
- review exclusion evidence and already-downloaded exclusions such as `already_in_library:<slug>`
- query variants and whether a sharper rerun was needed
- venue prior sources used, especially configured field venues or curated field lists; weak community hints must be labeled as unverified context
- citation graph expansion evidence when used
- recall gaps if any
- `MINERU_TOKEN` set/missing only if setup was checked

Quality metrics must be current evidence, not memory or guesses. Verify citation counts, impact factor/quartile, CiteScore, publisher/venue metadata, EasyScholar venue metrics, or code availability when available; otherwise write `未核实` for that field.

For each recommendation, avoid raw JSON and long abstracts. Use links when verified. If the kept list is long, still list all kept papers; use shorter notes for lower-priority items rather than omitting them. Rejected review/survey papers should not appear in `推荐优先看` when the user asked to exclude them.
