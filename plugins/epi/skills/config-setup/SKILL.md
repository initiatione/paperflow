---
name: config-setup
description: "Use when EPI config is missing or the user wants to view, initialize, or change profile, keywords, budget, MinerU, Zotero, runtime dependencies, or approval gates."
---

# EPI Config Setup

Use this skill before any EPI paper workflow when config is missing, or when the user asks to view or change EPI settings. 这是 EPI 配置查看、初始化和修改的唯一交互入口. Prefer the fast read-only path for display tasks:

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Only run `doctor` when the user asks for dependency health, plugin diagnosis, MCP/CLI/MinerU availability, or a setup failure. Do not run `doctor` just to output current configuration.

## Conversation Rules

- 一次只问一个问题.
- 每个问题必须说明影响, 给出推荐值, 提供 2-3 个参考方向, 并说明用户可以回复“默认”或自然语言.
- 不要一次性输出完整默认配置, 不要用 YAML 或字段名当问题标题.
- 最终确认前不得运行 `init-config`.
- 最终确认前不得运行 `apply-config-update`.
- 不运行 `dry-run`, MinerU, Zotero, promotion, 或 wiki 写入.
- 不打印 token 或 secret; 只报告 token is set/missing.
- 用户要求“输出当前配置/展示配置/现在配置是什么”时，直接用 fast read-only path，总结 `_meta\epi-config.yaml` 和 user-level runtime status；不要探测 MCP，不要下载论文，不要调用 MinerU.
- 本机依赖配置写入 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`: paper-search MCP command/args, CLI fallback, MinerU command, and `mineru.env` path. 不保存 token 明文; `MINERU_TOKEN` 只能来自进程环境或 `mineru.env`.
- 显式进程环境变量优先; runtime.json 只补缺失项, and it survives plugin cache upgrades.
- EPI 是通用论文插件。不要默认使用机器人、AUV、AI、医学或任何单一学科词表；后续 search/ranking/reader/wiki 侧重点必须从用户画像、domains、positive_keywords、negative_keywords 和 venue_prior 衍生.

## Initialization Flow

Collect answers step by step:

1. 论文库位置. 推荐一个专用本地论文库目录，例如 `<vault>`.
2. 主要研究画像: 学科/应用对象/方法族/常看任务, plus 使用目的 such as 前沿跟踪, 项目实现, 方法论文, 系统论文, or 长期 wiki 沉淀.
3. 用户画像 and paper preference: method, system, dataset, benchmark, real experiment, field validation, reproducible code. 默认不是综述论文; 只有用户明确要求综述时才加入 survey/review 偏好.
4. Positive/negative keywords and venue prior: 哪些词算匹配, 哪些词要避开, 哪些期刊/会议/数据库/领域榜单只作为召回和排序 prior.
5. Search source and per-run budget.
6. MinerU connection. 推荐 `MINERU_TOKEN` + default command; do not call MinerU during setup.
7. Zotero policy. 推荐 disabled first, collection `EPI`.
8. Human approval gate. 推荐 before final wiki write.

After all answers are collected, summarize in plain Chinese under “你刚刚选了什么”, then show a compact technical preview. Only after explicit user confirmation, write an answers JSON and run:

```powershell
python scripts\orchestrator.py init-config --vault <vault> --answers-json <answers.json>
```

## Update Flow

If config already exists, first explain current value, target value, and impact. Ask which area to change, one question at a time. After final confirmation, use `propose-config-update`; run `apply-config-update` only after the user explicitly approves the proposal.
