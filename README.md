# PaperFlow

本仓库是 PaperFlow 的 Codex 插件市场源。PaperFlow 是一个捆绑发布的论文知识流产品，当前包含两个可协作、也可单独安装的插件：Paper Source 和 Paper Wiki。

Stage 2 命名说明：bundle marketplace 机器名已切为 `paperflow`，两个插件机器名已切为 `paper-source` / `paper-wiki`。`paper-search` 只保留为仓库 URL、外部 `paper-search-mcp` / `paper-search` CLI 名称和 pre-Stage-2 安装缓存线索；`epi` / `prw` 只作为 pre-Stage-2 legacy alias、内部 artifact/skill 历史词和兼容语义出现。

## Paper Source 是什么

Paper Source (formerly EPI) 是通用论文智能工作流插件，不默认绑定某个学科方向。它围绕用户画像、当前研究问题、领域关键词、排除词、venue prior 和质量门控来运行，目标是把高质量论文从检索候选推进到可沉淀的证据包。

用户口语别名：PS。PS 只是自然语言别名，不是 `$PS` 入口，也不是独立插件名。Paper Source 当前 machine-facing name 是 `paper-source`；`epi` 是 pre-Stage-2 legacy alias。

A general academic paper intelligence workflow: it searches, ranks, preserves, parses, reads, critic-checks, stages, reports, and hands papers to an agent-mediated Obsidian/LLM Wiki ingest flow.

MinerU parsing is an internal Paper Source/EPI helper capability, not as a separate marketplace plugin; in other words, it is not a separate marketplace plugin.

## Paper Wiki 是什么

Paper Wiki (formerly PRW) 不是论文检索器，而是 Paper Source 之后的正式论文 wiki 写入、问答和维护层：读取 Paper Source source bundle、handoff、source review 和正式 wiki 图谱，按目标 vault contract 回答研究问题、写入或修复正式页面，并处理检测、更新、重做、重link、语言 gate、tracking 文件和 QMD 兼容检查。

用户口语别名：PW。PW 只是自然语言别名，不是 `$PW` 入口，也不是独立插件名。Paper Wiki 当前 machine-facing name 是 `paper-wiki`；`prw` 是 pre-Stage-2 legacy alias。

Paper Wiki exposes one user-facing paper wiki assistant for read-only wiki Q&A, source-map-grounded deposition, wiki checks, updates, relinking, and redo/deep extraction. Paper Source/EPI remains responsible for discovery, acquisition, MinerU parsing, paper gate, human approval, and record-only completion.

## 工作链路

Paper Source 的核心链路是 profile-driven high-quality paper collection -> source-first paper bundle -> reader/critic review -> staging -> human approval -> wiki handoff -> provenance record。
Paper Wiki 的核心链路是 Paper Source handoff -> wiki state check 或 read-only wiki ask -> formal page write/update/redo/relink -> provenance/language/QMD check -> Paper Source/EPI record readiness report。

链路含义如下：

- 画像驱动检索：根据研究画像、当前问题和领域配置生成检索意图，避免把插件固定成单一学科工具。
- 论文候选排序：按主题相关性、来源质量、论文类型、指标证据和可复现性线索筛选候选。
- source-first 保存：优先保留 PDF、metadata、MinerU Markdown、TeX、图片和 manifest，缺关键来源时不进入正式 wiki。
- 解析与阅读：用 MinerU 解析论文，再生成结构化阅读、证据地址和 claim-support 信息。
- critic 复核：对论文身份、方法证据、公式/图表支撑、实验指标、SOTA/性能声明和局限性进行可靠性检查。
- staging 与人工确认：先进入 Paper Source/EPI staging 和 gate 记录，由人工确认是否继续沉淀。
- wiki handoff：把通过 gate 的论文交给 Paper Wiki / Obsidian / LLM Wiki 写作链路，正式正文默认中文，英文仅保留题名、术语、缩写、证据字段和路径。
- provenance record：记录 final-source-review、页面 hash、artifact hash、source bundle 状态和写入生命周期，确保后续可审计。

## 功能范围

- 学术论文发现、候选排序和研究队列维护。
- PDF 获取、metadata 固化、MinerU 解析和 source bundle 完整性审计。
- reader 输出、claim-support、evidence map 和 critic quorum。
- paper gate、human approval、wiki-ingest handoff、wiki-ingest trigger 和最终 record。
- Obsidian/LLM Wiki 目录初始化、graph 可见性修复、formal 页面语言策略和 provenance 约束。
- run lifecycle、dashboard、研究队列、Zotero 同步和质量演化建议。
- Paper Source/EPI `wiki-ask` 只读查询：从正式论文 wiki graph 检索，标记 wiki 证据、综合判断、推断、不确定性和纠错候选。
- 基于 skill-based architecture 的轻量路由：插件根入口保持 thin shell，具体任务交给 skill 与模块化脚本，独立子任务可在用户授权后交由 Codex subagents 完成。
- Paper Wiki/PRW 正式 wiki 侧闭环：根据 wiki 提问、提取 Paper Source/EPI 论文、检测 wiki 库、更新正式页、重做/更详细提取、重link、修复 tracking/QMD surface，并把剩余 Paper Source/EPI `record-wiki-ingest` 动作报告清楚。

## 依赖

Paper Source 依赖以下能力，但安装插件本身不要求一次性全部配置完成：

- Codex 插件市场：用于发现、安装和更新 Paper Source。
- paper-search：用于学术论文搜索、候选返回和可选下载能力。
- MinerU：用于 PDF 到 Markdown、TeX、图片和 manifest 的解析。
- EPI vault config：保存研究画像、领域、正负关键词、venue prior、预算和人工确认策略。
- Obsidian 或 LLM Wiki vault：承载 source-first deposition、Paper Wiki/PRW formal wiki 页面和 provenance record。
- Zotero：可选，用于文献库同步和后续引用管理。

外部依赖缺失时，Paper Source/EPI 应以 warning 方式提示可补配置项；插件结构损坏才属于安装级错误。

## 结构

仓库根目录承担插件市场源和发布说明职责。Paper Source 插件主体位于 `plugins/paper-source/`，Paper Wiki 插件主体位于 `plugins/paper-wiki/`。

- `plugins/paper-source/.codex-plugin/plugin.json`：Paper Source marketplace 元数据、版本号、展示文案和 skill 声明。Paper Source 机器名是 `paper-source`。
- `plugins/paper-wiki/.codex-plugin/plugin.json`：Paper Wiki marketplace 元数据、版本号、展示文案和 skill 声明。Paper Wiki 机器名是 `paper-wiki`。
- `AGENTS.md`：插件级 thin shell 路由入口，说明如何按任务类型匹配 skill。
- `plugins/paper-source/skills/`：用户可触发的 Paper Source/EPI skills，包括配置、发现、ingest、MinerU 解析、wiki setup、provenance、run lifecycle、topic tracking 和 Zotero。
- `plugins/paper-wiki/skills/`：Paper Wiki/PRW 的 `paper-research-wiki` 用户入口和 `paper-wiki-language` 支持 gate。
- `skills/routing.yaml`：任务路由、闭环检查和本地约束。
- `scripts/build/epi/`：插件内部 Python 模块，承载 CLI 路由、source bundle audit、paper gate、wiki handoff、record workflow、graph visibility 和 language gate。
- `docs/epi-linkage.md`：EPI 总链路契约。
- `docs/structure.md`：模块、skill、artifact 和边界说明。
- `docs/workflow.md`：运行闭环、handoff 和 skill-based routing 约定。
- `docs/progress.md`：当前版本状态、验证结果、风险和下一步。

## 安装方式

在 Codex 的 Plugin Marketplaces 页面添加本仓库作为 marketplace source。Source 使用 `https://github.com/initiatione/paper-search`，Git ref 使用 `main`，Sparse path 留空。

添加 marketplace 后，在插件列表中选择 PaperFlow，再安装 `Paper Source` 和 `Paper Wiki`。当前机器名是 `paper-source` / `paper-wiki`；旧安装缓存或历史记录里可能仍显示 pre-Stage-2 `paper-search` / `epi` / `prw`。安装后在新线程中提及 Paper Source、PS 或 `@paper-source` 可进入论文发现/采集/解析链路；提及 Paper Wiki、PW、`@paper-wiki` 或 Paper Research Wiki 可进入正式论文 wiki 写入和维护链路。

首次使用 Paper Source 时按 config-setup 的中文引导补齐研究画像、vault、paper-search、MinerU 和可选 Zotero 配置。

插件更新以 marketplace 版本为准。源码仓库中的修改需要发布到 marketplace 后，安装缓存中的 Paper Source/Paper Wiki 才会更新；`codex plugin list`、安装缓存目录和当前会话已加载技能是三个不同信号，检查运行态时必须分开报告。

## 开发规范

插件开发必须遵守 [Plugin Development Rules](docs/plugin-development.md)。每次改动插件源码、skill、workflow、生成物 contract 或 marketplace 可见行为时，都要同步插件版本信息和相关文档；源码验证通过不等于安装缓存已经更新。

## 使用原则

- 不把不完整 raw bundle 写入正式 wiki。
- 不绕过 human approval 和 provenance record。
- 不把 MinerU 当作独立 marketplace 插件发布。
- 不把安装缓存当作开发源。
- 不把 formal wiki 正文默认写成英文。
- 不用 generic summary 替代 source-first、claim-support 和 evidence-addressed deposition。
- 不让 Paper Wiki/PRW 接管 Paper Source/EPI 的 discovery、MinerU、human approval 或 `record-wiki-ingest`；Paper Wiki 只负责正式页面写入、维护、检查和 record readiness 报告。
