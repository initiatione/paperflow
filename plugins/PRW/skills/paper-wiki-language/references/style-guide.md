# Paper Wiki Language Style Guide

Use this reference after `paper-wiki-language/SKILL.md` when drafting, rewriting, reviewing, or polishing formal PRW/EPI paper wiki pages.

## Voice Target

Write as a Chinese academic knowledge curator, not as a translator.

- Lead with the durable idea, not with "本文" or a translated abstract frame.
- Prefer short paragraphs with one claim or distinction per paragraph.
- Use compact bullets only when the content is genuinely list-shaped.
- Make page titles and headings specific to the page's role in the graph.
- Use plain verbs: "区分", "约束", "复用", "依赖", "比较", "暴露", "限制", "指向".
- Preserve uncertainty with precise language: "作者报告", "实验显示", "该设置下", "目前证据支持", "仍未覆盖".
- Avoid promotional language, inflated significance, and empty bridge sentences.

## Chinese Style Rules

Avoid literal English-to-Chinese order. Translate the argument, not the clause structure.

Prefer:

- "这篇论文把问题设定为..." instead of "本文提出了一个..."
- "这个页面记录..." only when describing the wiki page itself, not the source paper.
- "该方法依赖..." / "实验只覆盖..." / "结果说明..." instead of vague "具有重要意义".
- "相关方法脉络" / "技术谱系" / "可复用设计" instead of stiff labels such as "方法家族".

Avoid or rewrite these machine-translation and AI-prose patterns:

- "值得注意的是", "不难发现", "综上所述", "基于以上分析"
- "首先/其次/最后" when it only mirrors an outline
- "本文将..." in formal wiki pages
- "为后续研究奠定基础" unless the paper explicitly supports that claim
- "从 X 到 Y" when X and Y are not a real scale
- repeated "提出了一种..." paragraphs with no graph-level distinction
- headings that are literal category labels: "方法家族", "实验结果分析", "未来展望"

## Terminology

Before writing, build a small term ledger from the paper, target vault, and existing pages.

- Keep common technical abbreviations in English: RL, SAC, PPO, DQN, MDP, LLM, RAG, trajectory tracking, reward, value network, policy, baseline, ablation.
- Use the paper's original term when it is a named method, dataset, benchmark, metric, or algorithm.
- Use one Chinese rendering consistently when the vault already has one.
- Do not translate a term just to make a sentence look fully Chinese.
- Do not create a new Chinese alias if it would split existing wiki identity.

## Heading Rules

Headings should help graph navigation. They are not translated section titles from the paper.

Good headings name the durable role:

- `## 这篇论文解决什么问题`
- `## 方法放在什么技术线上`
- `## 关键机制`
- `## 实验设置和证据边界`
- `## 可复用的设计`
- `## 局限和未覆盖问题`

For `references/` pages, use the canonical section spine in `../../paper-research-wiki/references/references-page-anatomy.md`: `证据钩子 / 原文与证据入口 / 问题设定 / 核心机制 / 实验设置与证据边界 / 局限与未覆盖问题 / Provenance`. This spine is preferred for new writes; current approved heading aliases remain acceptable during repairs when the section role is clear.

For concept, derivation, experiment, synthesis, and opportunity pages, make headings page-specific:

- concept: name the distinction the concept preserves
- derivation: name the formula, assumption, or proof step
- experiment: name the tested setup, metric, or comparison
- synthesis: name the cross-paper tension or convergence
- opportunity: name the actionable research gap

Avoid H1/H2 duplication. If the page title already says the method name, the first H2 should add a new angle.

## Page-Family Voice

- `references/`: explain paper identity, contribution, setup, evidence, and limits without turning the page into an abstract.
- `concepts/`: define the reusable concept and why it matters across papers.
- `derivations/`: reconstruct assumptions, variables, equations, and logical steps.
- `experiments/`: state what was tested, against what, under which metric, and what the evidence does not cover.
- `synthesis/`: compare papers directly; name agreements, contradictions, and missing evidence.
- `reports/`: summarize a bounded review or batch finding with source-grounded claims.
- `opportunities/`: write actionable research questions, not generic "future work".

## Claim-Preserving Rewrite Pattern

For each paragraph, preserve this order:

1. What claim or distinction is being made.
2. Which source artifact supports it: paper section, formula, figure, table, experiment, or source-review evidence address.
3. What the evidence boundary is: scope, assumptions, dataset, simulation setting, missing ablation, or unsupported leap.
4. Which graph page it should connect to.

If a sentence cannot be mapped to those four points, either rewrite it as an open question or remove it from factual prose.

## Depth, Density, and Punctuation

These apply to every reference page and are part of the write gate, not cosmetic polish.

- **Mechanism over label.** "Uses SAC" is a label; "writes the current-induced value-estimation bias into the Q-target, which a plain SAC baseline cannot do" is knowledge. In 核心机制, pair each mechanism with the baseline failure mode it fixes and the resulting consequence.
- **Differential graph-contrast.** Use natural body links and page-specific comparison prose to contrast the paper against named sibling pages on concrete axes (objective optimized, evidence tier, assumptions, how the objective is expressed). A "Related" link dump is not graph integration.
- **Attribute every number.** Each metric carries its value, its source table/figure, and a stance verb (作者报告 / Table I 报告 / 作者据此称). Never launder an author's simulation claim into a flat fact; reproduce the key table verbatim rather than paraphrasing it lossily.
- **Richness is evidence density, not word count.** Prefer a precise table, a defined formula, and one sharp contrast over three paragraphs of restatement. If a paragraph adds no claim, number, or distinction, cut it.
- **Consistent full-width Chinese punctuation** (，。：；）in prose; do not mix half-width commas into Chinese sentences.
