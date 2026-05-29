---
name: paper-ingest
description: "Use when ingesting selected papers into EPI raw artifacts, or continuing beyond MinerU parse into readers, critics, and staging drafts."
---

# Paper Ingest

Use after dry-run ranking selects candidate papers. Keep the chain aligned with `docs\epi-linkage.md`: high-quality paper collection -> LLM Wiki deposition -> low-burden reading report. If config is missing, stop ingest and use `config-setup`; config onboarding lives in `docs\config.md` 的 `## 聊天式初始化脚本`，不要自由发挥成技术字段问卷，不要一次性输出完整默认配置.

For steps 1-3 only, prefer the precise raw-prep command:

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 1 --vault D:\paper-research-wiki
```

This path performs acquire + MinerU parse and stops after `mineru\paper.md`, `mineru\paper.tex`, `mineru\images`, and `mineru\mineru-manifest.json`. Do not use `advance-paper`, `advance-ranked`, or `advance-batch` when the user only asked for 1-3, because those commands continue into reader/critic/staging on later invocations.

```powershell
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --vault D:\paper-research-wiki
python scripts\orchestrator.py advance-batch --candidates D:\codex-tmp\ranked-candidates.json --max-papers 3 --vault D:\paper-research-wiki
python scripts\orchestrator.py paper-gate --slug <slug> --vault D:\paper-research-wiki
python scripts\orchestrator.py wiki-ingest-handoff --slug <slug> --vault D:\paper-research-wiki
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault D:\paper-research-wiki
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault D:\paper-research-wiki
```

After critic pass, staging prepares evidence drafts, `wiki-ingest-brief.json`, and `reports/<slug>-reading-report.md` for low-burden reading. Final Obsidian/LLM Wiki pages are created by an agent according to the target vault contract, not fixed by EPI staging or by only the local `llm-wiki` / `wiki-ingest` skills. Resolve the vault `AGENTS.md` and `_meta/*`, and use Ar9av/obsidian-wiki, kepano/obsidian-skills, and initiatione/obsidian-wiki-dev `liuchf/wiki-skills` as framework references. Treat local `llm-wiki`, `wiki-ingest`, and `obsidian-markdown` as execution adapters; `wiki-ingest-brief.json` must carry `wiki_rule_source_model` so the receiving agent sees the rule priority before writing. Use `wiki-ingest-handoff` to render the read-only agent checklist and target-vault contract status before any final wiki ingest. The report should emphasize theory insight, experiment design, Reading Trust Status, evidence strength, suggested wiki routes, and compact reproducibility caveats. Safety: raw/staging writes are allowed; compiled wiki writes are not. No critic pass, no wiki ingest handoff.
