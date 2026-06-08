# Survey / Review Page Anatomy

This is the binding contract for writing a `references/` page **when the source paper is a survey /
review**, not a single-method paper. `wiki-writing-standard.md` defines the cross-family rules;
`references-page-anatomy.md` is the method-paper deep contract; this file is the survey-specific deep
contract that the document-type gate at the top of `references-page-anatomy.md` routes review/survey
papers to. Read it before drafting, rewriting, or repairing any review/survey reference page.

It was distilled and validated against the reviewed exemplar
`references/trajectory-tracking-control-auv-review-classical-to-ai.md` (Eissa et al. 2026, a PRISMA
systematic review). Treat that page as the worked example for every rule below.

## Why a survey needs its own contract

A survey's contribution is **not** a new mechanism plus its own experiment, so the method-paper spine
(`核心机制` with a distinguishing formula, `实验设置与证据边界` with a platform and a metric table)
misfires on it. Forcing that spine produces the failure modes this contract exists to prevent:
treating a *borrowed* illustrative formula as the survey's mechanism, reconstructing it as a
`derivations/` page, and presenting a cross-literature summary table as if it were a single benchmark.
The review-methodology literature names this directly: requesting the wrong document's rigor "leads to
structural inconsistencies." The distillation schema must match the document type.

A survey's reusable value is a **map**:

1. **A taxonomy** — the classification that organizes the field (the survey's primary contribution).
2. **A landscape** — what methods exist, their representative studies, reported results, and trade-offs.
3. **A gap map** — the open problems, stated as durable, actionable items.
4. **A reading map** — pointers to the primary sources the survey organizes (it is a hub node).
5. **Coverage metadata** — review type, search, inclusion criteria, how many screened vs included.

The reference page is the **hub** that carries this map. But **a hub is not thin**: its depth is the
per-taxonomy-branch landscape (representative methods + reported numbers + trade-offs). Route to owner
pages only for *reusable cross-paper* definitions — never as an excuse to drop the survey's substance.

## When to use this contract (survey detection)

Use the survey spine when any of these hold:

- the `method/review` tag is present, or the title/venue says *review*, *survey*, *a survey of*,
  *state of the art*, *systematic review*, *meta-analysis*, *scoping review*;
- the body has a PRISMA flow, explicit inclusion/exclusion criteria, or a taxonomy/classification
  figure that organizes many *cited* works;
- the paper's quantitative results are **aggregated from cited studies**, and it declares something
  like "no datasets were generated or analysed".

Counter-rule (do **not** misroute): a paper that contributes **one new method plus its own
experiments** is a primary paper — use `references-page-anatomy.md` even if its title contains
"review". A paper that *both* proposes a method *and* surveys the field is a primary paper; its survey
content may feed `concepts/`/`synthesis/`, but the reference page follows the method spine.

Record the **review type** (narrative / systematic-PRISMA / scoping / meta-analysis) explicitly — it
drives `base_confidence` (systematic > narrative) and the honesty of the coverage section.

## Frontmatter contract

Same required fields as every formal page (see `wiki-writing-standard.md`), with these survey deltas:

- **`tags`** — keep the five facets. `method/review` is required; also tag the method families the
  survey taxonomizes (e.g. `method/rl`, `method/sliding-mode-control`, `method/pinn`). The `evidence/`
  tier is **`evidence/literature-review`** — a survey runs no loop of its own; it aggregates. Never
  label a survey `evidence/simulation` (that misrepresents secondary evidence as primary).
- **`summary`** — survey shape: `<年份> <出处> <综述类型>，覆盖 <范围/篇数>，给出 taxonomy/对照/gap：
  <一句定位>。` (No 缩写/机制 slot — a survey has no single method.)
- **`base_confidence`** — use the survey sub-rubric below, not the method-paper one (sea-trial tiers
  are meaningless for a survey).
- **`provenance.ambiguous`** — MUST carry the heterogeneity caveat: the aggregated numbers come from
  different studies/models/tasks/protocols and cannot be read as a unified benchmark. If the survey's
  own table disagrees with its prose (it happens), record that here too.
- **`relationships`** — `related_to` the taxonomy `concepts/` owner and the cross-paper `synthesis/`
  page. Link the primaries it covers inline in 阅读地图 (there is no "covers" relationship type).

### base_confidence rubric (survey)

Start at 0.70 and adjust:

- Review rigor: systematic/PRISMA `+0.06`; scoping `+0.03`; narrative `+0.00`.
- Coverage: broad and traceable (named databases, search string, # screened→included) `+0.04`.
- Taxonomy quality: clean, reused by a downstream `concepts/` owner `+0.04`.
- Internal consistency: table-vs-prose or figure-vs-text numeric contradictions `-0.06`.
- Reading map: links resolve to real primary nodes `+0.02`.

Clamp to **[0.50, 0.85]** — a survey is secondary evidence; cap below a primary sea-trial paper. An
honest systematic review with one internal inconsistency lands ~0.80.

## Body skeleton

```
# <thesis: what field this maps, on what organizing principle — not the title verbatim>

<opening paragraph: the field the survey maps, its organizing principle, and the honest boundary, in curator voice>

## 证据钩子
## 原文与证据入口
## 代表公式边界
## 综述定位与覆盖
## 分类体系与逐支方法景观
## 验证层级分布
## 方法景观对照
## 趋势与争议
## 空白与研究机会
## 阅读地图
## 局限与未覆盖问题
## Provenance
```

Mandatory: 证据钩子, 原文与证据入口, 综述定位与覆盖, 分类体系与逐支方法景观, 空白与研究机会,
阅读地图, 局限与未覆盖问题, Provenance. Strongly-encouraged when the survey supports them: 验证层级分布,
方法景观对照, 趋势与争议. Optional: 代表公式边界 (only when the survey quotes a load-bearing baseline
formula worth scoping — see the Borrowed-formula rule). A short note at the top of the page declaring "页型说明：综述，按 survey 蒸馏法
写成 map/hub" helps future editors not re-impose the method spine.

Section-by-section:

- **H1** — state the map, not the title. Example: `# AUV 控制综述：PRISMA 谱系图 + 逐支机制/证据景观
  + “指标是趋势不是 benchmark”的边界`.
- **`## 证据钩子`** — survey-flavored 4 bullets: `综述类型/覆盖`, `分类骨架`, `景观/对照`, `边界`.
- **`## 原文与证据入口`** — same audit trail as any reference page (clickable PDF, DOI, OA/license,
  bundle paths, key anchors incl. the reference-list count).
- **`## 代表公式边界`** (optional) — only when the survey quotes a load-bearing baseline formula (a
  textbook PID law, a Bellman target). Show it once, attribute it to its source, define the variables,
  and scope it: state which branch it defines and which of the survey's claims it does **not** support.
  Frame as baseline-failure-mode → formula → limited-adaptation, never as the survey's own derivation.
  Link the cross-paper formula-role distinction to its owner page rather than re-deriving it here.
- **`## 综述定位与覆盖`** — replaces 问题设定/实验. The review's *own* method is its experiment: review
  type, databases, search string, inclusion/exclusion criteria, the PRISMA funnel (`N screened → N
  included`), time window, and any bibliometrics (counts by year/venue/country). Embed the PRISMA
  figure here. Note sampling bias when the bibliometrics show concentration (one country/venue).
- **`## 分类体系与逐支方法景观`** — replaces 核心机制. This is the heart and must be **deep**:
  - A compact taxonomy table (the organizing dimension / 能力来源 per branch) + the taxonomy figure;
    route the reusable definition to the `concepts/` owner (do not duplicate it in full).
  - One `###` sub-section per branch, each with a **per-study landscape table** reproducing the
    survey's per-method tables (e.g. its Tables 1–4) as rows of
    `方法 (ref) | 机制要点 | 报告效果（基线/条件） | 平台 / 验证层级`.
  - A short curator analysis per branch (what is solid vs vs-weak-baseline; where evidence is thin).
- **`## 验证层级分布`** — the cross-cut the survey usually does not tabulate: bucket the representative
  studies by validation tier (real-robot/pool/tank/field vs real-data-driven sim vs pure simulation),
  and state where real-world validation concentrates. This is high-value curator analysis (`^[inferred]`).
- **`## 方法景观对照`** — the survey's cross-method comparison (e.g. its Table 5 / a radar). Reproduce
  the table with second-hand stance, and **flag internal inconsistencies** (table vs prose) as the
  proof that these are trends, not a benchmark.
- **`## 趋势与争议`** — direction of travel, the (almost always present) "no universal winner" thesis,
  contradictions, and the baseline-selection trap.
- **`## 空白与研究机会`** — actionable gaps; route the durable version to the `opportunities/` owner.
  Embed the challenges figure here. Pull the future-directions list verbatim-in-spirit.
- **`## 阅读地图`** — the hub. Link `concepts/`/`synthesis/`/`opportunities/` owners, link the primary
  papers it covers that already have vault nodes (hub→primary), and list prioritized ingest candidates
  (prefer those with real-world validation).
- **`## 局限与未覆盖问题`** — evidence boundary: review-level ≠ benchmark/deployment; heterogeneity;
  internal inconsistency; "proven vs future-work"; reproducibility (must return to primaries).
- **`## Provenance`** — the claim ledger (schema in `references-page-anatomy.md`), with second-hand
  stance on aggregated numbers.

## Depth & precision rules (survey-specific)

### Per-study evidence card
For each representative study in the landscape tables, capture three fields a future reader needs to
judge it without reopening the survey: the **mechanism** (what it actually changes), the **reported
effect with its baseline and conditions** (e.g. "−73.6% vs RBF-PID-SMC, Gazebo"), and the **platform /
evidence tier**. The third is what stops a simulation result from reading as a deployed one.

### Evidence-tier cross-cut
Aggregate the per-study tiers into 验证层级分布. A survey's "best metrics" are usually simulation; the
real-robot/pool/field evidence clusters in a few sub-areas. Surfacing this is the single most useful
thing the page adds beyond the survey, and it operationalizes the survey's own "few field trials" caveat.

### Second-hand-number rule
A survey's numbers are reported from cited studies. Never assemble them into a single benchmark or
ranking. Every number carries (number, *which cited study*, `作者综述汇总` stance). If the survey's own
table and prose give different ranges, record the contradiction — it is positive evidence that the
numbers are cross-literature trends.

### Borrowed-formula rule
Formulas a survey quotes from cited works (a textbook PID law, a Bellman target) are **not** the
survey's contribution, and the failure mode to prevent is presenting them as if they were — a faked
`核心机制`, or a new `derivations/` page that reconstructs them as the survey's own result. The
discipline is *scoping*, not deletion:

- It is fine — often useful — to show the single load-bearing baseline formula in an optional
  `代表公式边界` section, **if** it is attributed to its source, its variables are defined, and it is
  explicitly scoped: which branch it defines (e.g. PID/traditional) and which of the survey's
  intelligent/hybrid claims it does **not** support. Keep the chain short and boundary-focused
  (baseline-failure-mode → formula → limited-adaptation).
- Do **not** create a new `derivations/` page solely to hold borrowed formulas as if the survey
  derived them. If a cross-paper *formula-role* page already exists (one that frames each quoted
  formula by its evidence role — error feedback vs value target vs trajectory discretization vs neural
  mapping), the hub links to it as the owner instead of re-deriving the distinction inline.
- Never upgrade a borrowed formula into a stability/performance guarantee for methods the survey
  merely cites.

### Baseline-selection-trap check
Large reported "% improvements" are often against weak baselines (PID, plain NN, an older variant).
Against strong baselines (NMPC, GP-MPC) the margin usually collapses. Note this in 趋势与争议 so a
reader does not over-read a headline number.

### Taxonomy-axis rule
Every taxonomy branch states its *organizing dimension* (capability source, evidence type) and
contrasts its siblings on that axis. A branch listed without its axis is a label, not knowledge.

### Coverage-as-method
The survey's literature search **is** its experiment. Put it in 综述定位与覆盖, never an
`experiments/` page. Missing search detail (no databases, no criteria) is a coverage limitation worth
recording.

### Ownership / no-duplication
The hub summarizes and points out; the owners hold the depth: taxonomy definition → `concepts/`,
cross-method synthesis → `synthesis/`, actionable gaps → `opportunities/`. Keep the reference page's
own per-branch landscape (that is the survey's substance), but do not re-derive the reusable concept
definitions that belong to an owner page.

## Figure rendering

Use the Evidence figure card format from `references-page-anatomy.md` (anchor, `Placed near:`,
`Source:`, image, `中文图注:`, `Reading note:`). For surveys the figures that earn a card are the
**taxonomy tree**, the **PRISMA flow**, the **comparison/radar/landscape** figure, and the
**challenge** figure — not architecture or result-curve figures (a survey has none of its own). Place
the taxonomy figure in 分类体系, PRISMA in 综述定位与覆盖, the comparison in 方法景观对照, challenges in
空白与研究机会.

## Routing (what a survey spawns, and what it must not)

A survey's durable knowledge routes to the **existing** families — it does not need a new one:

- taxonomy → `concepts/` (the classification owner);
- cross-method landscape / contradictions → `synthesis/`;
- actionable gaps → `opportunities/`;
- high-value covered primaries → their own `references/` (ingest candidates) or at least the reading map.

A survey must **not** spawn a **new** `derivations/` page that reconstructs borrowed formulas as if
the survey derived them, and must **not** spawn an `experiments/` page (it ran no experiments). A
cross-paper *formula-role* page (framing each quoted formula by its evidence role) is acceptable when
it already exists or is genuinely reusable across papers — the hub links to it as the owner. Other
evidence-boundary content lives in the reference page's `代表公式边界`/`局限` sections or a `synthesis/`
boundary note. Keep existing such pages additively: reframe them honestly rather than forcing a survey
through them, and never delete an existing page just to fit the spine.

## Self-check before declaring the page done

- Document-type gate applied: this is genuinely a survey (detection signals), not a primary paper.
- Five tag facets present; `method/review` set; `evidence/literature-review` set (not `simulation`).
- `summary` follows the survey shape; `base_confidence` from the survey rubric; `provenance.ambiguous`
  carries the heterogeneity caveat.
- 综述定位与覆盖 states review type + search + inclusion + funnel; PRISMA figure embedded.
- 分类体系与逐支方法景观 is **deep**: taxonomy table + figure + one per-branch landscape table with
  per-study `机制 / 报告效果(基线,条件) / 平台·验证层级` rows; not a thin 3-row summary.
- 验证层级分布 buckets studies by tier and says where real validation concentrates (when supported).
- 方法景观对照 reproduces the comparison table with second-hand stance and flags any internal
  inconsistency; no aggregated number is laundered into a benchmark.
- Any borrowed formula appears only in a scoped `代表公式边界` section (attributed, branch-scoped, not
  a guarantee); no **new** `experiments/`/`derivations/` page reconstructs the survey's borrowed
  formulas as its own result.
- 阅读地图 links the taxonomy/synthesis/opportunities owners and the covered primaries that have vault
  nodes; ingest candidates prioritized by validation tier.
- 局限 separates review-level evidence from deployment; states the heterogeneity and inconsistency.
- Language follows `paper-wiki-language`; richness is evidence density, not word count.
