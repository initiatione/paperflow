# Venue Prior For Robotics Paper Quality

Use venue prior to improve ranking and recall for robotics, control, embodied AI, and AUV topics. A venue prior is only an input signal. It is not a final quality label and must not replace DOI, official metadata, citation counts, impact metrics, PDF/code availability, or actual validation evidence.

## Source Classes

| Source class | Examples | How to use |
| --- | --- | --- |
| Curated robotics venue lists | RoboWiki-style conference and journal pages | Community prior for domain fit, venue family, h-index-like indicators, and missing venue recall |
| Community discussions | Zhihu/forum/blog rankings | Weak recall hint and subjective context only |
| Official/publisher metadata | venue site, publisher page, DOI, CrossRef, OpenAlex, Semantic Scholar | Verification source for venue identity, year, DOI, citation count, PDF, code, and metrics |

## Practical Robotics Prior

For system-level robotics/control work, prefer the following venue families when other signals are comparable:

- Highest robotics signal: Science Robotics, TRO, IJRR, RSS, ICRA.
- Strong robotics/control signal: RA-L, IROS, CoRL, JFR, RAS, Autonomous Robots, T-Mech, TCST, T-ASE, CASE, HRI, Humanoids.
- Strong AI/ML signal when the paper is genuinely robot/control-facing: NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, AAAI, IJCAI.
- Strong AUV/marine engineering signal: Ocean Engineering, IEEE Journal of Oceanic Engineering, Applied Ocean Research, Control Engineering Practice, ISA Transactions, OCEANS.
- Interdisciplinary high-impact signal: Nature Machine Intelligence, Nature Communications, Science Robotics, NPJ Robotics.

These groups should boost ranking only when the paper also fits the user's topic and has credible evidence. A lower-prior venue with real AUV trials, field deployment, sim-to-real validation, safety guarantees, or strong benchmark evidence can outrank a top venue paper with weak relevance.

## Dynamic Decay

Recent high-quality venues are stronger signals for fast-moving areas such as embodied AI, VLA, diffusion policy, robot foundation models, and RL control. Older top-venue papers remain important as background, but do not automatically outrank newer papers with stronger current evidence and better topic fit.

Apply this decay gently:

- Newer than 3 years: keep venue prior at full strength.
- 3-7 years old: require stronger citation, benchmark, or deployment evidence.
- Older than 7 years: treat as foundational/background unless it is still heavily cited or directly necessary.

## Required Output Separation

When venue prior affects ordering, expose it separately:

- `venue_prior`: curated/community prior used, such as `RoboWiki: robotics flagship` or `Zhihu: subjective Tier 1 hint`.
- `verified_metrics`: citation count, DOI, IF/JCR/CiteScore, official venue page, PDF/code.
- `verification_warnings`: anything not confirmed, such as `impact factor 未核实`.

Never invent impact factors, rankings, acceptance rates, or citation counts. If a metric was not verified in the current run, write `未核实`.

## Recall Use

If the first EPI/MCP result set misses obvious venue families for the topic, run a sharper query. Examples:

- AUV RL/control should include marine/control venues such as Ocean Engineering, IEEE Journal of Oceanic Engineering, Applied Ocean Research, Control Engineering Practice, and OCEANS.
- Embodied AI/robot learning should include CoRL, RSS, ICRA/IROS, RA-L, and AI/ML venues only when robotics-facing.
- Field robotics should include JFR, ICRA/IROS, Field Robotics, and relevant domain journals.

Record missed venue families as `recall_gap` under `EPI 实测证据`.
