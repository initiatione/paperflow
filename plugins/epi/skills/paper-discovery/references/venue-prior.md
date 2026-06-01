# Venue Prior For Profile-Driven Paper Quality

Use venue prior to improve ranking and recall for whatever field the user's EPI config describes. A venue prior is only an input signal. It is not a final quality label and must not replace DOI, official metadata, citation counts, impact metrics, PDF/code availability, or actual validation evidence.

## Source Classes

| Source class | Examples | How to use |
| --- | --- | --- |
| Curated field venue lists | Society pages, field databases, conference/journal indexes, curated community pages | Community prior for domain fit, venue family, h-index-like indicators, and missing venue recall |
| Community discussions | forum/blog/community rankings | Weak recall hint and subjective context only |
| Official/publisher metadata | venue site, publisher page, DOI, CrossRef, OpenAlex, Semantic Scholar | Verification source for venue identity, year, DOI, citation count, PDF, code, and metrics |

## Practical Prior From Config

Start with `venue_prior` in `_epi\meta\epi-config.yaml`. The user can list journals, conferences, publishers, societies, field databases, or curated pages that matter in their discipline. If `venue_prior` is empty, use only generic metadata verification until the user config is improved.

Domain examples, not defaults:

- Robotics/control profiles may list Science Robotics, TRO, IJRR, RSS, ICRA, RA-L, IROS, CoRL, JFR, T-Mech, TCST, T-ASE, OCEANS, or related venues.
- Biomedical profiles may list PubMed-indexed journals, MICCAI, Nature Biomedical Engineering, Lancet-family journals, IEEE TMI, or domain registries.
- Materials/chemistry profiles may list Nature Materials, Advanced Materials, JACS, ACS Nano, NeurIPS/ICLR only when the configured topic is computational.
- Social science or humanities profiles may list field societies, SSRN/arXiv only when appropriate, publisher databases, and domain-specific proceedings.

These groups should boost ranking only when the paper also fits the user's topic and has credible evidence. A lower-prior venue with stronger validation, data, field evidence, or relevance can outrank a top venue paper with weak profile fit.

## Dynamic Decay

Recent high-quality venues are stronger signals for fast-moving areas defined by the user's profile. Older top-venue papers remain important as background, but do not automatically outrank newer papers with stronger current evidence and better topic fit.

Apply this decay gently:

- Newer than 3 years: keep venue prior at full strength.
- 3-7 years old: require stronger citation, benchmark, or deployment evidence.
- Older than 7 years: treat as foundational/background unless it is still heavily cited or directly necessary.

## Required Output Separation

When venue prior affects ordering, expose it separately:

- `venue_prior`: configured or curated prior used, such as `config: <venue>` or `field index: <source>`.
- `verified_metrics`: citation count, DOI, IF/JCR/CiteScore, official venue page, PDF/code.
- `verification_warnings`: anything not confirmed, such as `impact factor 未核实`.

Never invent impact factors, rankings, acceptance rates, or citation counts. If a metric was not verified in the current run, write `未核实`.

## Recall Use

If the first EPI/MCP result set misses obvious venue families from the user's config, run a sharper query, update `venue_prior`, or use field-specific official sources for recall.

Record missed venue families as `recall_gap` under `EPI 实测证据`.
