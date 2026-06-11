# References Page Anatomy

This is the binding contract for writing a `references/` page — the single-paper evidence node of
the paper research wiki. `wiki-writing-standard.md` defines the cross-family rules; this file is the
references-specific deep contract. Read it before drafting, rewriting, or materially repairing any
reference page. It was distilled from the vault's reviewed exemplar pages (ALMPC, MPQ-DPG,
RLBMPA-COI, IPF) and validated against held-out papers.

## Document-type gate

This file is the **single-method (primary) paper** contract. If the source paper is a **survey or
review**, this spine misfires — a survey has no single mechanism and runs no experiment of its own, so
forcing `核心机制` / `实验设置与证据边界` turns borrowed illustrative formulas into fake contributions
and produces a `derivations/`/`experiments/` page for a paper that derived and ran nothing. Stop and
follow `survey-page-anatomy.md` instead (the survey map/hub spine, the detection signals, and the
survey frontmatter incl. `evidence/literature-review`). Use the method spine below for primary papers,
including a paper that *proposes a method and also surveys the field*.

## What a reference page is for

A reference page is **not** a paper abstract and **not** a translation. It is a *reusable evidence
node* in a knowledge graph. Three properties make it reusable, and every rule below serves one of
them:

1. **Every durable claim carries its source and its evidence boundary.** A future reader (human or
   agent) must be able to tell what the paper *proved*, under what conditions, and what it only
   *claimed* or left as future work — without reopening the PDF.
2. **The page positions itself against its neighbors.** A node that says "X is good" is weak; a node
   that says "unlike sibling Y which optimizes reward, X writes stability into a hard constraint" is
   reusable. Distillation without integration is failure — this is the core rule of the whole wiki.
3. **The mechanism is explained, not just named.** "Uses SAC" is a label. "Writes the current-induced
   value-estimation bias into the Q-target, which a plain SAC baseline cannot do" is knowledge.

If a sentence advances none of these three, cut it or move it to `## 局限与未覆盖问题` /
`## Provenance`. Length is not the goal: **richness means evidence density, not word count.** Prefer
a precise table, a defined formula, and one sharp contrast over three paragraphs of restatement.

## Frontmatter contract

```yaml
---
title: <full paper title, not abbreviated>
category: references
page_family: references
tags: ["domain/<d>", "method/<m>", "task/<t>", "topic/<topic>", "evidence/<tier>"]
aliases: ["<ACRONYM>", "<full method name>", "<descriptive name>"]
relationships:
  - target: "[[concepts/<page>]]"
    type: uses
  - target: "[[synthesis/<page>]]"
    type: related_to
sources: ["<short source label>"]
source_id: "<slug>"
source_pdf: "obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf"
summary: "<year> <venue> <type>，提出 <ACRONYM>：<one-line mechanism>。"
provenance:
  extracted:
    - "<what was taken directly from the source bundle: metadata, MinerU Markdown, figures/tables>"
  inferred:
    - "<cross-page or reuse inference this page makes>"
  ambiguous:
    - "<OCR noise, author future-work, data/code availability, anything uncertain>"
base_confidence: 0.8x
lifecycle: draft
lifecycle_changed: <YYYY-MM-DD>
tier: core | supporting
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---
```

Field rules and *why*:

- **`aliases`** — give three handles: the acronym (`ALMPC`), the spelled-out method
  (`Adaptive Lyapunov-constrained MPC`), and a descriptive name (`Fault-tolerant AUV tracking MPC`).
  Future pages refer to the paper by different names; all three must resolve here.
- **`tags`** — exactly the five facets below, in order. Facets let the graph be sliced by domain,
  method, task, topic, and *evidence strength* — the last one is what stops a simulation paper from
  being cited as field-proven.
- **`sources`** — frontmatter `sources:` must stay scan-friendly: use exactly one short source
  label for a `references/` page, normally the paper slug, DOI slug, or canonical title label.
  Do not expose long `obsidian://` URIs in the properties pane. Do not use Markdown links,
  `[[...]]` wikilinks, `_paper_source/`, legacy `_epi/`, PDF paths, DOI/arXiv URLs, metadata,
  MinerU, manifest, or figure paths in frontmatter `sources`.
  Put the full clickable PDF URI in `## 原文与证据入口` as a Markdown link displayed as `原论文 PDF`,
  pointing at `obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf`.
  The path is `_paper_source/raw/<slug>/paper.pdf` — **no `papers/` segment**.
- **`summary`** — fixed shape: `年份 + 出处 + 类型，提出 缩写：一句机制`. A summary that does not
  name the venue/year and the one-line mechanism is incomplete. Keep under ~120 Chinese characters.
- **`provenance`** — three *qualitative bullet lists* (not numeric ratios). `extracted` = what the
  bundle directly supports; `inferred` = what this page concludes by reasoning across pages;
  `ambiguous` = OCR noise, future-work, availability caveats. This is the page's honesty ledger.
- **`base_confidence`** — set from the rubric at the end of this file, not by feel. Calibrated AUV
  simulation papers land ~0.80–0.86; never 1.0.
- **`lifecycle`** — new agent-written pages start `draft`. Do not add `review_status`. Old
  `lifecycle: review-needed` pages are legacy repair inputs and should be migrated to `draft`
  during property repair, not accepted as a steady-state status. Only a human review pass or a
  target vault contract with explicit authority can move a page beyond draft. Never auto-promote.
- **`tier`** — `core` if the page owns a method/result the graph leans on; `supporting` if it is a
  baseline or peripheral comparison.

### Tag facet vocabulary

Use these five facets. Reuse an existing value before coining a new one; if you coin one, keep it
lowercase-kebab and parallel to the examples.

- `domain/` — research domain. e.g. `domain/auv`.
- `method/` — the method(s) the paper contributes or centers on; multiple allowed. e.g.
  `method/mpc`, `method/lyapunov-control`, `method/economic-mpc`, `method/rl`, `method/sac`,
  `method/ddpg`, `method/dqn`, `method/actor-critic`, `method/potential-field`,
  `method/sliding-mode`, `method/adrc`, `method/fuzzy`.
- `task/` — the control/planning task. e.g. `task/trajectory-tracking`, `task/path-planning`,
  `task/motion-planning`, `task/docking`, `task/target-hunting`, `task/heading-control`,
  `task/attitude-control`, `task/multi-agent-cooperation`, `task/energy-management`.
- `topic/` — a cross-cutting concern, optional but encouraged. e.g. `topic/fault-tolerant-control`,
  `topic/ocean-current`, `topic/input-saturation`, `topic/energy-aware-control`,
  `topic/sample-efficiency`.
- `evidence/` — evidence strength, **required**, exactly one primary tier:
  `evidence/simulation`, `evidence/hardware-in-the-loop`, `evidence/pool-trial`,
  `evidence/sea-trial`. Add `evidence/real-data-driven-simulation` when real-world data builds a
  sim environment but the loop is still simulated.

## Body skeleton

Use this default section spine. It is a spine, not a cage: keep every role, but **add
paper-specific sub-headings** under 核心机制 and 实验 where the paper's real structure demands it
(e.g. `### 三类协作 degree`, `### 对 SAC target function 的改动`, `### two-stage energy-to-go`). A
page that is all generic headings and no paper-specific ones is too shallow.

```
# <ACRONYM>：<one-sentence thesis that adds an angle beyond the title>

<opening paragraph: the problem the paper sets, and its core design idea, in curator voice>

## 证据钩子
## 原文与证据入口
## 问题设定
## 核心机制
## 实验设置与证据边界
## 局限与未覆盖问题
## Provenance
```

Accepted aliases (accepted aliases from current approved pages) may remain during repairs when the section role is
clear: `Evidence Hooks` for `证据钩子`, `原论文 PDF`, `原论文与证据`, or `原论文与证据入口`
for `原文与证据入口`, `实验设置和证据边界` for `实验设置与证据边界`,
`局限和未覆盖问题` for `局限与未覆盖问题`, and `与现有图谱的关系` for graph
integration prose. For new writes, prefer the canonical spine above and keep graph integration in
natural body links and comparison prose, not a mandatory heading.

Section-by-section:

- **H1** — never repeat the title verbatim. State the thesis: method + what it does differently.
  Example: `# ALMPC：推进器故障下的 Bayesian-Lyapunov MPC 跟踪控制`.
- **Opening paragraph** — frame the problem the paper attacks and its central design choice. Curator
  voice, not "本文提出". Name the real contribution in one or two sentences.
- **`## 证据钩子`** — a 4-bullet scannable fingerprint. Always these four labels:
  - `模型/方法：` the platform/model and the named method components.
  - `公式/算法：` the distinguishing equations/algorithms (named, not derived here).
  - `实验/指标：` the test scenarios, baselines, and metrics.
  - `边界：` evidence tier and the author-declared future work / unproven scope.
- **`## 原文与证据入口`** — clickable PDF URI, DOI or arXiv id, MinerU Markdown path, image
  directory, manifest path, and figure/formula indexes. This is the audit trail. If non-empty native
  `mineru/paper.tex` exists, mention it only as an optional cross-check, not a required source.
- **`## 问题设定`** — what is specifically hard, and the gap the paper targets. State the *baseline
  failure mode* here or in 核心机制 — the page must make clear what was wrong before.
- **`## 核心机制`** — the actual method. Requirements that make it deep, not descriptive:
  - Render the **distinguishing formula(s)** in `$$...$$`, and define the variables inline.
  - State explicitly **what this mechanism does that the obvious baseline cannot** (contrast, not
    description). Pattern: baseline failure mode → the mechanism → the consequence. Example:
    "AMPC 先更新模型再算控制，ALMPC 同时维护候选模式、posterior 和共同收缩约束，从而减少模式切换时的
    控制跳变".
  - Split into `###` sub-sections when the method has distinct parts.
- **`## 实验设置与证据边界`** — make the evidence concrete and reproducible:
  - Name the **platform/testbed** (REMUS, Saab Seaeye Falcon, DROP-Sphere, South China Sea data…).
  - Name the **baselines compared** and reproduce the **real metric table** with numbers (RMSE,
    success rate, reward, steps, energy, CPU time) — never "performs better" without the table.
  - Capture **reproducibility knobs**: training budget, network sizes, learning rates, replay
    buffer, episode counts, reward weights, horizons, detection thresholds. These make the page
    reusable for re-implementation.
  - Embed **evidence figures** as Evidence figure cards with placement, source, caption, and
    reading note.
  - Attribute every number (see Quantified-claim rule).
- **`## 局限与未覆盖问题`** — separate *proven* from *not proven*. Cover all four boundary types
  below. Be blunt: "这是作者仿真结果，不是实艇容错能力证明".
- **Graph integration** — not a mandatory heading. Use natural body links and page-specific
  comparison prose to contrast this paper against named sibling pages on a *specific axis*
  (objective optimized, evidence tier, assumptions, how the objective is expressed). Optionally add
  a `可复用的设计` note where it reads naturally: what a future method/page can borrow.
- **`## Provenance`** — the claim ledger (schema below).
- **`## Related`** — the page-end outgoing-link audit list. It may repeat links already used
  naturally in the body, but every entry must target a formal page family only.

## Depth & precision rules

These separate a strong page from a competent summary — they are what "分析深入且精确" means here.

### Source-map-first writing
Write from the source bundle, not from reader or critic summaries. MinerU Markdown is the primary formula and notation source: use `mineru/paper.md` or `mineru/<slug>.md` first for formulas,
symbols, method context, and prose. Only fall back to the PDF, formula-index.json, figure-index.json, or image evidence when MinerU Markdown is missing, wrong, ambiguous, or insufficient. If non-empty native `mineru/paper.tex` exists, use it only as an optional cross-check,
not as a required or equal-primary source. Reader/critic artifacts are secondary aids for source-map checks; reader/critic artifacts are secondary aids for
orientation, critique, or quality checks; they cannot replace a direct pass over the MinerU source
artifacts for load-bearing claims.

Use source-map depth as the page's depth control:
- For every core mechanism claim, find the source section/block, formula, table, figure, or caption
  before writing the distilled prose.
- Prefer stable addresses such as `MinerU Markdown 第 III 节`, `Formula index Eq. (7)`,
  `Fig. 2 caption`, or `Table I row <metric>`. If optional native TeX is used as a cross-check,
  label it explicitly as such. If a local source map provides block IDs such as `S012`, `C003`,
  `F002`, or `T001`, preserve them in the body or Provenance.
- Do not expose the full source map in the reference page. Surface only the anchors needed to audit
  the page's durable claims; the full source map remains in `_paper_source/raw/<slug>/mineru/*`.
- If the source bundle does not support a step, say `原文未明确说明` instead of filling the gap from
  general field knowledge.

### Mechanism contrast
In 核心机制, every core mechanism is paired with the baseline it improves on and *why*. State the
baseline's failure mode → the mechanism → the consequence. A mechanism described in isolation is a
description; described against its baseline it is knowledge.

### Formula reasoning chain
Do not paste a load-bearing equation as an isolated decoration. For each distinguishing formula,
write the chain in this order: premise -> equation -> variable definitions -> guarantee -> next step -> baseline contrast.
This makes the derivation inspectable without turning the page into a full proof.

Use stance labels while writing the chain:
- `source-grounded` when the paper states the equation, definition, setup, or proof step.
- `author-method-description` when explaining the authors' intended mechanism.
- `inferred` when the page connects two paper facts or contrasts a sibling page; mark with
  `^[inferred]`.
- `ambiguous` when OCR, notation, or a skipped proof step makes the interpretation uncertain; mark
  with `^[ambiguous]`.

If a reasoning step is standard but not explicit in the paper, write it as an inference and keep the
boundary visible: `原文未明确说明该中间步；这里按 Lyapunov/MPC 常规读法解释为 ...` Do not upgrade
that inference into an author claim.

### Quantified-claim attribution
Every quantitative claim carries three things: the **number**, the **source artifact** (table/
figure/section), and a **stance**. Use the curator verbs the source warrants: `作者报告`,
`Table I 报告`, `实验显示`, `作者据此称`. Never launder an author's simulation claim into a flat
fact. Reproduce the key table verbatim rather than paraphrasing it lossily.

### Stance vocabulary
Tag the epistemic status of each load-bearing claim (inline via verb choice, and explicitly in the
Provenance block):
- `author-method-description` — the authors describe their own design.
- `author-claim-from-simulation` — a result the authors obtained in simulation.
- `author-claim-from-experiment` — a result from hardware / pool / sea trial.
- `source-grounded` — a fact directly in the bundle (definition, equation, setup).
- `inferred` — this page's cross-page reasoning. Mark prose with `^[inferred]`.
- `ambiguous` — uncertain due to OCR, contradiction, or missing detail. Mark with `^[ambiguous]`.

### Evidence-boundary taxonomy
`## 局限与未覆盖问题` addresses all four, when applicable:
1. **Evidence tier** — simulation vs HIL vs pool vs sea trial. State it plainly.
2. **Scope / assumptions** — 2D vs 3D, horizontal-plane simplification, ideal communication, known
   dynamics, omitted disturbance models.
3. **Proven vs author future-work** — quote what the authors explicitly defer (continuous fault
   manifolds, robustness margins, 6-DOF experiments, sea trials, 3D extension).
4. **Reproducibility gaps** — code not provided, data available-on-request, hyperparameters or
   approximations that dominate results.

### Reviewer-style boundary check
Use a lightweight reviewer-style pass to calibrate `## 局限与未覆盖问题`, `base_confidence`, and
`tier`; do not turn the reference page into a reviewer report. Check the paper against:
`originality`, `scientific importance`, `interdisciplinary readership`, `technical soundness`, and
`readability for nonspecialists`. Then translate only the relevant findings into the page's normal
boundary language: what is supported, what is weak, and what is not assessable from the source bundle.
Do not invent missing experiments, controls, citations, line numbers, or prior-work distinctions.

### Graph contrast must be differential
Graph integration is not a "Related" link dump and not a mandatory heading. Use natural body links
and comparison prose to say *how this page differs from* named sibling pages on a concrete axis. If
you cannot name the axis of difference, you have not yet understood how the paper fits the graph.

## Formula & figure rendering

- Math uses Obsidian delimiters: inline `$u_t$`, block `$$ ... $$`. **Never** fenced ` ```math `,
  ` ```tex `, or ` ```latex ` blocks — Obsidian renders those as code, not math.
- Define variables right after the equation that introduces them.
- Embed evidence figures as an Evidence figure card near the first substantive use, not as a
  gallery at the end. Put architecture/mechanism figures in `## 核心机制`; put result curves/tables
  in `## 实验设置与证据边界`. Later mentions should link back to the first card instead of duplicating
  the image.
- Each Evidence figure card needs the original figure name, placement anchor, MinerU figure/caption
  source, image path, Chinese caption, and a reading note:

```markdown
<a id="F002"></a>
**原文 Fig. 2：Bayesian multi-model LMPC 架构**

**Placed near:** 核心机制（第 III 节首次实质引用）
**Source:** MinerU Fig. 2 / Fig. 2 caption C003

![Fig. 2](file:///D:/paper-research-wiki/_paper_source/raw/<slug>/mineru/images/<hash>.jpg)

**中文图注:** <原图注的保守译文>

**Reading note:** 看 controller bank、posterior、共享 Lyapunov 约束之间的连接；这张图支撑机制结构，
不是实验结果。
```

  Pick figures that carry mechanism or evidence, not decorative ones. If MinerU has OCR noise in a
  formula or caption, normalize against MinerU Markdown, the PDF/index fallback, and optional native
  TeX when present; say so honestly rather than copying garbled symbols. A result figure must cite
  its caption and the relevant table/metric when the claim depends on both.

## Provenance block schema

End the page with `## Provenance`. One entry per load-bearing claim, formula, and result. Two forms:

```markdown
## Provenance

- Claim: <the statement being supported>
  Support: source-grounded; stance=author-claim-from-simulation
  Evidence: MinerU Markdown 第 V 节; formula-index.json/Table I; 原论文 PDF (source: [<title>](obsidian://...paper.pdf)).
- Inference: <a cross-page conclusion this page draws>
  Support: inferred
  Basis: <the reasoning / which pages it rests on>
```

Support labels: `source-grounded`, `metadata-only`, `inferred`, `unsupported`. Unsupported claims
stay out of factual prose — if they must be preserved, put them under 局限与未覆盖问题 as open
questions. Formula and figure claims need a formula/figure evidence address.

## Language

Write as a Chinese research-wiki curator, not a translator (full rules in `paper-wiki-language`).

- Lead with the durable idea. No "本文提出", no translated-abstract framing.
- Keep technical terms in English where the field writes them that way: RL, SAC, PPO, DDPG, MPC,
  EMPC, LMPC, posterior, RMSE, replay buffer, baseline, ablation. Do not translate a term just to
  make a sentence look fully Chinese, and do not coin a new Chinese alias that splits an existing
  wiki identity.
- Use plain verbs: 区分, 约束, 复用, 重分配, 退化, 依赖, 比较, 暴露, 限制, 指向.
- Use consistent full-width Chinese punctuation in prose (，。：；）, not mixed half-width commas.
- Avoid AI-prose tells: 值得注意的是 / 不难发现 / 综上所述 / 为后续研究奠定基础 / 从 X 到 Y (when
  X,Y are not a real scale) / literal-category headings like 方法家族 / 未来展望.

## base_confidence rubric

Start at 0.70 and adjust:
- Evidence tier: sea-trial `+0.10`, pool/HIL `+0.06`, real-data-driven simulation `+0.04`,
  pure simulation `+0.00`.
- Parse quality: clean MinerU Markdown with fallback/index agreement `+0.06`; noticeable OCR noise on key formulas `-0.04`.
- Reproducibility: full hyperparameters + platform named `+0.04`; code/data unavailable `-0.02`.
- Internal consistency: results, figures, and tables agree `+0.04`; contradictions `-0.06`.

Clamp to [0.50, 0.90] for agent-written pages. A page that cannot exceed ~0.80 is fine — that is an
honest simulation-tier node.

## Self-check before declaring the page done

- Five tag facets present, `evidence/` tier set, and tier matches the prose boundary.
- `summary` follows `年份+出处+类型，提出 缩写：机制`.
- `sources` uses scan-friendly short source labels only; the body `## 原文与证据入口` has the full
  clickable PDF URI, path `_paper_source/raw/<slug>/paper.pdf` (no `papers/`).
- Frontmatter `provenance` has all three lists; body has a `## Provenance` block with stance labels.
- Source-map-first writing used MinerU Markdown as the primary formula and notation source, with
  PDF/index/image fallback only for Markdown gaps, errors, or ambiguity, not only reader/critic
  summaries.
- 核心机制 renders the distinguishing formula as a Formula reasoning chain and contrasts a baseline's
  failure mode.
- 实验 names the platform, reproduces the metric table, and lists reproducibility knobs.
- At least one mechanism/evidence figure embedded as an Evidence figure card with `Placed near:`,
  `Source:`, `中文图注:`, and `Reading note:`.
- 局限 covers the four boundary types plus reviewer-style unsupported/not-assessable items; no
  author simulation claim is laundered into a flat fact.
- Graph integration uses natural body links to contrast named sibling pages on a concrete axis.
- No `本文提出`, no machine-translation headings, no fenced math blocks; richness is evidence
  density, not word count.
