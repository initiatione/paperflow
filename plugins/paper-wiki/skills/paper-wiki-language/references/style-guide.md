# Paper Wiki Language Style Guide

Use after `paper-wiki-language/SKILL.md` when drafting, rewriting, reviewing, or polishing formal Paper Wiki/Paper Source paper wiki pages.

## Voice Target

Write as a Chinese academic knowledge curator, not as a translator. Lead with the durable idea, keep paragraphs short, use compact bullets only for list-shaped content, and name the page's graph role. Prefer plain verbs such as "区分", "约束", "复用", "依赖", "比较", "暴露", "限制", "指向". Preserve uncertainty with "作者报告", "实验显示", "该设置下", "目前证据支持", and "仍未覆盖"; avoid promotional language, inflated significance, and empty bridge sentences.

## Chinese Style Rules

Translate the argument, not English clause order.

- Prefer "这篇论文把问题设定为..." over "本文提出了一个...".
- Use "这个页面记录..." only for the wiki page itself.
- Prefer "该方法依赖..." / "实验只覆盖..." / "结果说明..." over vague significance claims.
- Use "相关方法脉络", "技术谱系", or "可复用设计" over stiff labels such as "方法家族".
- Rewrite machine-translation patterns: "值得注意的是", "不难发现", "综上所述", "基于以上分析", outline-only "首先/其次/最后", unsupported "为后续研究奠定基础", fake-scale "从 X 到 Y", repeated "提出了一种...", and category-label headings such as "实验结果分析" or "未来展望".

## Terminology

Before writing, build a small term ledger from the paper, vault, and existing pages.

- Keep common abbreviations in English: RL, SAC, PPO, DQN, MDP, LLM, RAG, trajectory tracking, reward, value network, policy, baseline, ablation.
- Keep the paper's original named method, dataset, benchmark, metric, or algorithm.
- Reuse the vault's existing Chinese rendering when present.
- Do not translate terms merely to make a sentence fully Chinese or create aliases that split wiki identity.

## Heading Rules

Headings should help graph navigation, not mirror paper sections. Good headings name a role: `## 这篇论文解决什么问题`, `## 方法放在什么技术线上`, `## 关键机制`, `## 实验设置和证据边界`, `## 可复用的设计`, `## 局限和未覆盖问题`.

For `references/` pages, use `../../paper-research-wiki/references/references-page-anatomy.md`: `证据钩子 / 原文与证据入口 / 问题设定 / 核心机制 / 实验设置与证据边界 / 局限与未覆盖问题 / Provenance`. This spine is preferred for new writes; accepted aliases remain acceptable during repairs when the role is clear. If the source is a survey/review, switch to `../../paper-research-wiki/references/survey-page-anatomy.md` instead of forcing the method-paper spine.

For other families, make headings page-specific: concept = distinction preserved; derivation = formula, assumption, or proof step; experiment = setup, metric, or comparison; synthesis = cross-paper tension or convergence; opportunity = actionable research gap. Avoid H1/H2 duplication.

## Page-Family Voice

- `references/`: explain paper identity, contribution, setup, evidence, and limits without turning the page into an abstract.
- `concepts/`: define the reusable concept and why it matters across papers.
- `derivations/`: reconstruct assumptions, variables, equations, and logical steps.
- `experiments/`: state what was tested, against what, under which metric, and what the evidence does not cover.
- `synthesis/`: compare papers directly; name agreements, contradictions, and missing evidence.
- `reports/`: summarize a bounded review or batch finding with source-grounded claims.
- `opportunities/`: write actionable research questions, not generic future work.

## Claim-Preserving Rewrite Pattern

For each paragraph preserve this order: claim/distinction -> supporting artifact or evidence address -> evidence boundary -> graph connection. If a sentence cannot map to those four points, rewrite it as an open question or remove it from factual prose.

## Density Gate

- Mechanism over label: explain what a method fixes and the consequence, not just "uses SAC".
- Differential graph-contrast: use natural body links and page-specific comparisons; a Related link dump is not graph integration.
- Attribute every number to table/figure/source and use stance verbs such as 作者报告.
- Richness is evidence density, not word count; prefer one precise formula/table/contrast over restatement.
- Use consistent full-width Chinese punctuation in prose.
