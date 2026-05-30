---
name: paper-discovery
description: "Use when running EPI paper search/ranking dry-runs, finding high-quality papers for a topic, excluding reviews/surveys on request, or starting the precise EPI steps 1-3 path: search, ranked selection, download, and MinerU parse without reader/critic/staging."
---

# Engineering Paper Discovery

Use this skill for search/rank dry-runs and the narrow steps 1-3 path. Keep the main file thin and load the references below for the actual policy:

- `references/search-protocol.md`
- `references/quality-gate.md`
- `references/output-format.md`

The full EPI chain stays documented in `docs\epi-linkage.md`. If setup is unclear, run `doctor` or `config-status`. If config is missing, stop discovery and use `config-setup`; config onboarding lives in `docs\config.md` 的 `## 聊天式初始化脚本`，不要自由发挥成技术字段问卷，不要一次性输出完整默认配置.

```powershell
python scripts\orchestrator.py doctor --plugin-root <plugin-root> --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault <vault>
```

`prepare-ranked` downloads selected ranked papers and parses them with MinerU, then stops after `_raw\papers\<slug>\mineru\...`. It must not generate reader, critic, staging, Zotero, or final wiki outputs. Verify evidence with `search-record.json`, `acquire-record.json`, `parse-record.json`, `paper.pdf`, `mineru\paper.md`, `mineru\paper.tex`, `mineru\images`, and `mineru\mineru-manifest.json`.

Safety: `dry-run` writes only `_runs/<run-id>/`. `prepare-ranked` writes raw paper artifacts only and stops after parse.
