---
name: paper-discovery
description: "Use when running EPI paper search/ranking dry-runs, or when starting the precise EPI steps 1-3 path: search, ranked selection, download, and MinerU parse without reader/critic/staging."
---

# Engineering Paper Discovery

Use for search/rank dry-runs and the narrow steps 1-3 path. The full EPI chain is documented in `docs\epi-linkage.md` and stays focused on high-quality paper collection, LLM Wiki deposition, and low-burden reading reports. If setup is unclear, run `doctor` or `config-status`. If config is missing, stop discovery and use `config-setup`; config onboarding lives in `docs\config.md` 的 `## 聊天式初始化脚本`，不要自由发挥成技术字段问卷，不要一次性输出完整默认配置.

```powershell
python scripts\orchestrator.py init-config --vault D:\paper-research-wiki --answers-json <answers.json>
python scripts\orchestrator.py dry-run --query "robotics embodied intelligence control" --max-results 20 --vault D:\paper-research-wiki
```

For "重新走 1-3", "下载论文并 MinerU 解析", or similar requests, avoid hand-writing candidate JSON. Run:

```powershell
python scripts\orchestrator.py doctor --plugin-root D:\paper-search\plugins\epi --vault D:\paper-research-wiki --json
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex --plugin-root D:\paper-search\plugins\epi --vault D:\paper-research-wiki
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault D:\paper-research-wiki
```

`prepare-ranked` downloads selected ranked papers and parses them with MinerU, then stops after `_raw\papers\<slug>\mineru\...`. It must not generate reader, critic, staging, Zotero, or final wiki outputs. Verify evidence with `search-record.json`, `acquire-record.json`, `parse-record.json`, `paper.pdf`, `mineru\paper.md`, `mineru\paper.tex`, `mineru\images`, and `mineru\mineru-manifest.json`.

Safety: `dry-run` writes only `_runs/<run-id>/`. `prepare-ranked` writes raw paper artifacts only and stops after parse.
