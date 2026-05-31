---
name: config-setup
description: "Use when EPI config is missing or the user wants to view, initialize, or change profile, keywords, budget, MinerU, Zotero, runtime dependencies, or approval gates."
---

# EPI Config Setup

EPI 配置的唯一交互入口：查看、初始化、修改 profile、keywords、budget、MinerU、Zotero、runtime 依赖和审批门。任何论文工作流开始前若配置缺失，先用这个 skill。

## 快速查看（只读优先）

用户要求"输出当前配置 / 展示配置 / 现在配置是什么"时，直接走只读路径，总结 `_meta\epi-config.yaml` 和 user-level runtime 状态即可——不探测 MCP、不下载论文、不调用 MinerU：

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Only run `doctor` when the user asks for dependency health, plugin diagnosis, MCP/CLI/MinerU availability, or a setup failure. 只有当用户要求依赖健康检查、插件诊断、MCP/CLI/MinerU 可用性，或排查 setup 失败时，才跑 `doctor`。不要为了展示当前配置而跑 `doctor`。

## 安全边界

这些是硬约束，保护用户配置和凭证不被误改、误泄露：

- **最终确认前不得运行 `init-config`**、**最终确认前不得运行 `apply-config-update`**、`dry-run`、MinerU、Zotero、promotion 或 wiki 写入。
- **不打印 token 或 secret**；只报告 token is set / missing。
- 本机依赖配置写入 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`：paper-search MCP command/args、CLI fallback、MinerU command、`mineru.env` 路径。不保存 token 明文；`MINERU_TOKEN` 只能来自进程环境或 `mineru.env`。
- 显式进程环境变量优先；`runtime.json` 只补缺失项，并在插件缓存升级后保留。

## 对话方式

配置 onboarding 是聊天式的，不是技术字段问卷。让用户轻松回答，而不是被一堆 YAML 字段淹没：

- **一次只问一个问题。**
- 每个问题必须说明影响、给推荐值、提供 2-3 个参考方向，并告诉用户可以回复"默认"或用自然语言。
- 不要一次性输出完整默认配置，不要用 YAML 或字段名当问题标题。

## 领域中立

EPI 是通用论文插件，不绑定任何单一学科。不要默认机器人、AUV、AI、医学或任何特定词表——后续 search / ranking / reader / wiki 的侧重点必须从用户画像、domains、positive_keywords、negative_keywords 和 venue_prior 衍生。

## 初始化流程

逐步收集答案，每步只问一个：

1. **论文库位置** — 推荐一个专用本地论文库目录，例如 `<vault>`。
2. **主要研究画像** — 学科 / 应用对象 / 方法族 / 常看任务，外加使用目的（前沿跟踪、项目实现、方法论文、系统论文、长期 wiki 沉淀）。
3. **论文偏好** — method、system、dataset、benchmark、real experiment、field validation、reproducible code。默认不是综述论文；只有用户明确要求时才加入 survey/review 偏好。
4. **Positive/negative keywords 和 venue prior** — 哪些词算匹配、哪些要避开、哪些期刊/会议/数据库/领域榜单只作召回和排序 prior。
5. **检索源和单次 budget。**
6. **MinerU 连接** — 推荐 `MINERU_TOKEN` + default command；setup 期间不调用 MinerU。
7. **Zotero 策略** — 推荐先 disabled，collection 用 `EPI`。
8. **人工审批门** — 推荐放在最终 wiki 写入前。

收集完毕后，先用通俗中文在"你刚刚选了什么"下总结，再展示紧凑的技术预览。**只有在用户明确确认后**，写入 answers JSON 并运行：

```powershell
python scripts\orchestrator.py init-config --vault <vault> --answers-json <answers.json>
```

## 更新流程

配置已存在时，先解释当前值、目标值和影响。逐个问要改哪个区域。最终确认后用 `propose-config-update`，**只有用户明确批准提案后**才运行 `apply-config-update`：

```powershell
python scripts\orchestrator.py propose-config-update --vault <vault> --answers-json <answers.json>
python scripts\orchestrator.py apply-config-update --vault <vault> --proposal <proposal.json>
```
