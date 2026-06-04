---
name: paper-ingest
description: >
  Use when the user asks to advance selected EPI papers, such as "推进论文",
  "生成阅读报告", "准备 wiki handoff", "沉淀前准备", source artifacts,
  optional readers/critics, source-staging reports, approval, or wiki-ingest handoff.
---

# Paper Ingest

Use after dry-run ranking selects papers. Chain goal in `docs\epi-linkage.md`: high-quality collection, LLM Wiki deposition, low-burden reading report.

If config is missing, stop and use `config-setup`. See `docs\config.md`.

For formal wiki deposition from an EPI source bundle or `wiki_deposition_task.json`, switch to `epi-paper-deposition`. Use `wiki-provenance` inside that layer for final wiki-page provenance, support labels, and claim-to-evidence round-trips.

## Reference Routing

Load `references/source-first-reading.md` when generating or checking reader outputs, critic inputs, staging bundles, or wiki-ingest handoffs. Keep reader summaries compact, but preserve source paper claims, formulas, figures, tables, image interpretations, caveats, and evidence pointers.

Treat parse quality as a source bundle check: Markdown alone is not enough when `parse-record.json` says parse succeeded; inspect TeX, images, and the MinerU manifest too.

## Workflow Routing

| Intent | Load |
| --- | --- |
| Download selected ranked papers, run MinerU, write source artifacts, and prepare source-staging | `workflows/prepare-ranked.md` |
| Add reader or critic outputs for important, complex, contradictory, reproducibility, review, or project-decision papers | `workflows/prepare-ranked.md` |
| Show approval report, record human approval, create wiki-agent trigger, or record final wiki ingest | `workflows/approval-and-trigger.md` |
| Formal page writing after `wiki_deposition_task.json` exists | `epi-paper-deposition/workflows/formal-wiki-write.md` |
| Final claim labels, provenance blocks, and evidence-address preservation | `wiki-provenance/SKILL.md` |

## Ingest Modes

- `fast-ingest` is the default. EPI acquires the paper, runs MinerU, saves source artifacts, writes `_epi/staging/papers/<slug>/wiki-ingest-brief.json`, and produces a short Chinese reading/approval report. It does not run reader or critic.
- `reviewed-ingest` adds reader outputs when parse quality is poor, formulas/figures are complex, or the user asks for a detailed reading report.
- `audited-ingest` adds critic outputs when the paper is critical for reproduction, a literature review, a project decision, or resolving contradictions.

Reader and critic reduce reading cost; they are navigation and audit aids, not the authority for final wiki prose. The final wiki agent must ingest from source artifacts.

Reader and critic sidecars are not source authority.

## Human Approval Boundary

Before final/staged vault writes, the user must see a single concise Chinese-first approval report with Chinese-English terminology and one recommendation: `建议沉淀`, `谨慎沉淀`, or `暂不沉淀`. EPI must record pre-write approval with `record-human-approval --scope run-wiki-ingest-agent`. Approval must not be requested from raw JSON, gate dumps, path lists, or critic sidecars.

When the user later calls `@EPI` to continue, use `research-queue --bucket ready_to_promote --actions --json` or the known slug's `wiki-ingest-trigger --slug <slug> --json`. The trigger writes a resume artifact for the current wiki-capable agent; it does not spawn a hidden background agent and does not write final pages.

## Wiki Boundary

Final Obsidian/LLM Wiki pages are agent-mediated under the target vault contract. EPI prepares source bundles, approval, trigger, record artifacts, and `wiki_deposition_task.json`; it does not directly write final pages in `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, or `opportunities/`.

After the wiki ingest agent writes or stages final Markdown pages, create `final-source-review.json`, then record completion with `record-wiki-ingest`. This command is record-only and must not rewrite final pages or replace the target vault's ingest agent.
