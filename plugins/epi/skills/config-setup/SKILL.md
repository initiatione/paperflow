---
name: config-setup
description: "Use when EPI config is missing or the user wants to initialize/change profile, keywords, budget, MinerU, Zotero, or approval gates."
---

# EPI Config Setup

Use this skill before any EPI paper workflow when config is missing, or when the user asks to change EPI settings. 这是 EPI 配置初始化和配置修改的唯一交互入口. Run only read-only checks first:

```powershell
python scripts\orchestrator.py doctor --json
python scripts\orchestrator.py config-status --json
```

## Conversation Rules

- 一次只问一个问题.
- 每个问题必须说明影响, 给出推荐值, 提供 2-3 个参考方向, 并说明用户可以回复“默认”或自然语言.
- 不要一次性输出完整默认配置, 不要用 YAML 或字段名当问题标题.
- 最终确认前不得运行 `init-config`.
- 最终确认前不得运行 `apply-config-update`.
- 不运行 `dry-run`, MinerU, Zotero, promotion, 或 wiki 写入.
- 不打印 token 或 secret; 只报告 token is set/missing.
- 本机依赖配置写入 `C:\Users\liuchf\.codex\plugins\paper-search\epi\runtime.json`: paper-search MCP command/args, CLI fallback, MinerU command, and `mineru.env` path. 不保存 token 明文; `MINERU_TOKEN` 只能来自进程环境或 `mineru.env`.
- 显式进程环境变量优先; runtime.json 只补缺失项, and it survives plugin cache upgrades.

## Initialization Flow

Collect answers step by step:

1. 论文库位置. 推荐 `D:\paper-research-wiki`.
2. 主要研究方向和使用目的, such as 前沿跟踪, 项目实现, 论文综述, or 长期 wiki 沉淀.
3. 用户画像 and paper preference: benchmark, survey, method, system, dataset, reproducible code.
4. Positive and negative keywords.
5. Search source and per-run budget.
6. MinerU connection. 推荐 `MINERU_TOKEN` + default command; do not call MinerU during setup.
7. Zotero policy. 推荐 disabled first, collection `EPI`.
8. Human approval gate. 推荐 before final wiki write.

After all answers are collected, summarize in plain Chinese under “你刚刚选了什么”, then show a compact technical preview. Only after explicit user confirmation, write an answers JSON and run:

```powershell
python scripts\orchestrator.py init-config --vault D:\paper-research-wiki --answers-json <answers.json>
```

## Update Flow

If config already exists, first explain current value, target value, and impact. Ask which area to change, one question at a time. After final confirmation, use `propose-config-update`; run `apply-config-update` only after the user explicitly approves the proposal.
