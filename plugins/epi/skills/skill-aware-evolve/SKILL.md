---
name: skill-aware-evolve
description: "Use when EPI evidence suggests controlled changes to profiles, filters, ranking, templates, or routing."
---

# Skill-Aware Evolve

Evolution is staged and reversible. It must not directly edit plugin code. Check config first:

```powershell
python scripts\orchestrator.py config-status --vault D:\paper-research-wiki --json
```

If config is missing, stop before proposing or activating evolution and follow `docs\config.md` 的 `## 聊天式初始化脚本`. 不要自由发挥成技术字段问卷. User config changes must use the config proposal/apply flow in that doc, separate from plugin evolution.

Create proposals from run evidence, feedback, Plugin Eval output, or benchmark reports:

```powershell
python scripts\orchestrator.py propose-evolution --reflection-type OPTIMIZATION --target-asset templates\ranking.example.yaml --rationale "Boost reproducibility after user feedback" --proposed-change-json "{\"weights\":{\"reproducibility_signal\":0.12}}" --evidence "_runs\feedback.jsonl#1"
```

Activate only after human approval:

```powershell
python scripts\orchestrator.py activate-evolution --proposal-id <proposal-id> --approved
```

Config changes use the separate proposal/apply flow in `docs\config.md`.
