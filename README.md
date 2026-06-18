# PaperFlow

中文 README 是默认入口；英文版见 [README.en.md](README.en.md)。

PaperFlow 是一个 Codex 插件市场 bundle，用于 evidence-first 的学术论文工作流。它帮助 agent 从论文发现进入 source bundle、人工确认的 handoff artifact，再进入正式 Obsidian/LLM wiki 页面，同时保持“来源准备”和“正式写入”的职责边界清晰。

当前 bundle 包含两个协作插件：

| 插件 | Machine name | 当前源码版本 | 职责 |
| --- | --- | ---: | --- |
| Paper Source | `paper-source` | `2.8.1` | 发现、排序、获取、解析、审计、staging、approval、vault 图谱可见性初始化和 record 论文证据。 |
| Paper Wiki | `paper-wiki` | `1.0.5` | 面向正式论文 wiki 的问答、沉淀、检测、关系图谱可见性修复、更新、重 link、重做和维护。 |

`paperflow` 是 marketplace bundle 名。`paper-search` 只保留为仓库/历史名称，以及外部 `paper-search-mcp` 或 `paper-search` CLI 集成名。`PS` 和 `PW` 只是自然语言短称，不是独立插件或 skill 名称。

## 为什么是 PaperFlow？

PaperFlow 面向“找到论文还不够”的研究流程。它保留 source evidence，让 query、ranking、quality gate 和 handoff 决策可审计；它要求 human approval 显式存在；它也避免让论文检索、PDF 解析、正式 wiki 写页和 record 混在一个不可追踪的脚本里。

推荐主链路：

```text
Paper Source discovery
  -> source bundle and reader/critic evidence
  -> source-staging and human approval
  -> wiki-ingest-brief.json
  -> Paper Wiki formal pages and post-task checks
  -> Paper Source record-wiki-ingest
```

## 能力概览

Paper Source 负责 source/evidence 层：

- 通过 `discover-papers` 处理 profile-driven 和自然语言论文发现。
- 生成透明 query plan、hard/soft constraints、source coverage report、DOI-required chat recommendations 和跨学科 quality gates。
- 使用 Paper Wiki `_meta/reference-index.json` 做已沉淀/已收集论文去重。
- 支持 PDF 获取、manual-download card、MinerU 解析、asset normalization、evidence index、reader output、critic checks 和 source bundle audit。
- 对主推荐论文做安全 auto-staging，默认停在 source-staging，不自动写 approval 或正式 wiki 页面。
- 生成 `paper-gate`、`record-human-approval`、`wiki-ingest-trigger` 和 `record-wiki-ingest` 相关 artifact，用于可审计 handoff 和完成记录。
- 通过 `wiki-setup` 初始化或修复目标 vault contract。
- 可选接入 Grok supplemental discovery、安装可见的 `grok-search-rs` MCP 入口、EasyScholar 指标、Zotero sidecar 和各类 paper-search provider credentials。

MinerU 解析是 Paper Source 的内部辅助能力，不是独立 marketplace 插件。

Paper Wiki 负责 formal wiki 层：

- 公开 conversational assistant 是 `paper-research-wiki`，用于问论文 wiki、沉淀 Paper Source handoff、检测库状态、更新页面、重 link、redo/deep extraction 和图/公式证据维护。
- `paper-wiki-language` 是正式页语言质量 gate，是支持能力，不是另一个公开主助手。
- 按 source map 写入和维护正式页面族：`references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/` 和 `opportunities/`。
- 完成后检查 provenance、语言、links、tags、aliases、`_meta/reference-index.json`、配置了 QMD 时的 freshness，以及 Paper Source record readiness。

Paper Source 的 `wiki-ask` 和 `wiki-query` 是程序化 fallback 或 diagnostics 入口。普通对话式论文 wiki 问答优先走 Paper Wiki `paper-research-wiki`。

## 职责边界

这些边界属于项目 contract：

- Paper Source 不写正式 wiki 页面。
- Paper Wiki 不负责论文 discovery、PDF acquisition、MinerU parsing、Paper Source approval record 或替换 `wiki-ingest-record.json`。
- `wiki-ingest-brief.json` 是当前 Paper Source -> Paper Wiki 的 canonical handoff。历史 `wiki_deposition_task.json` 只用于 cleanup，不是新的用户路径。
- `paper-wiki-language` 是 supporting language gate，不是和 `paper-research-wiki` 竞争的公开助手。
- 外部 wiki helper skills 是 optional helpers / policy references，不是 runtime-required dependencies。
- 源码 checkout 验证不等于 installed runtime 验证。Marketplace refresh、reinstall 和 installed-cache verification 必须分开报告。

## 安装

在 Codex Desktop 中把本仓库添加为 plugin marketplace source：

1. 打开 Plugin Marketplaces。
2. 添加 marketplace source：

   ```text
   https://github.com/initiatione/paperflow
   ```

3. Git ref 使用 `main`，Sparse path 留空。
4. 从 PaperFlow marketplace 安装 `Paper Source` 和 `Paper Wiki`。

安装后新开 Codex thread，提及 Paper Source、PS 或 `@paper-source` 进入论文发现/source-preparation；提及 Paper Wiki、PW、`@paper-wiki` 或 Paper Research Wiki 进入正式论文 wiki 写入和维护。

开发时如果把源码 checkout 当作本地 marketplace，根目录 `marketplace.json` 指向：

```text
./plugins/paper-source
./plugins/paper-wiki
```

## 首次运行

完整流程需要先配置 Paper Source runtime：

- 目标 Obsidian/LLM wiki vault。
- `paper-search-mcp` 或兼容的 paper-search CLI。
- 可选 `grok-search-rs` MCP command/env file；插件安装后提供 MCP 入口，但 endpoint、key、model 仍由用户级 runtime 配置。
- 构建 source bundle 时所需的 MinerU 凭据。
- 可选 provider credentials：Unpaywall、Semantic Scholar、CORE、DOAJ、Zenodo、EasyScholar、Grok-compatible search 和 Zotero。

从这里开始：

```powershell
python plugins\paper-source\scripts\orchestrator.py doctor --json
python plugins\paper-source\scripts\orchestrator.py init-config --vault <vault>
```

源码 checkout 中常用命令：

```powershell
python plugins\paper-source\scripts\orchestrator.py discover-papers --query "<topic>" --max-results 20 --vault <vault> --json
python plugins\paper-source\scripts\orchestrator.py report --run-id <run-id> --vault <vault>
python plugins\paper-source\scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
python plugins\paper-source\scripts\orchestrator.py record-human-approval --slug <paper-slug> --approved-by <name> --scope run-wiki-ingest-agent --vault <vault>
python plugins\paper-source\scripts\orchestrator.py record-wiki-ingest --from-paper-wiki-request <request.json> --vault <vault>
```

Paper Wiki 主要是 Codex skill surface，不是 orchestrator-style CLI。它仍包含少量 narrow helper wrapper，用于 reference index refresh、figure/formula support 等维护任务。

## 仓库结构

```text
.
|-- marketplace.json
|-- docs/
|   `-- plugin-development.md
|-- plugins/
|   |-- paper-source/
|   |   |-- .codex-plugin/plugin.json
|   |   |-- docs/
|   |   |-- scripts/
|   |   `-- skills/
|   `-- paper-wiki/
|       |-- .codex-plugin/plugin.json
|       |-- docs/
|       |-- scripts/
|       |-- rules/
|       `-- skills/
|-- scripts/
|   |-- paperflow_audit.py
|   |-- release_check_paper_source.ps1
|   `-- release_check_paper_wiki.ps1
`-- tests/
```

重要 source of truth：

- `plugins/<plugin>/.codex-plugin/plugin.json` 是 plugin manifest。
- `plugins/<plugin>/skills/routing.yaml` 是 route manifest。
- `plugins/<plugin>/skills/*/SKILL.md` 是 thin skill entrypoint。
- `plugins/<plugin>/skills/*/agents/openai.yaml` 是 skill UI metadata。
- `docs/plugin-development.md` 是修改 plugin、skill、workflow、test、manifest、marketplace 和 contract 前必须读取的开发门禁。

## 开发

安装测试依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

在修改插件代码、skills、workflows、docs、tests、generated contracts、release scripts 或 marketplace-visible behavior 前，先读：

- `docs/plugin-development.md`
- `plugins/paper-source/AGENTS.md`
- `plugins/paper-source/skills/routing.yaml`
- `plugins/paper-wiki/AGENTS.md`
- `plugins/paper-wiki/skills/routing.yaml`

开发改动只写 `plugins/...`，不要把 installed Codex cache 当作开发源。若改动影响 plugin-visible behavior 或 metadata，需要按 `docs/plugin-development.md` bump 对应插件版本并同步 marketplace mirrors。

## 验证

基础源码 checkout 验证：

```powershell
python -m pytest tests\paper_research_wiki\test_plugin_contract.py tests\paper_source\test_skill_bundle_contract.py tests\test_marketplace_manifest.py -q
python -m json.tool plugins\paper-source\.codex-plugin\plugin.json > $null
python -m json.tool plugins\paper-wiki\.codex-plugin\plugin.json > $null
git diff --check
```

路由和包卫生检查：

```powershell
python scripts\paperflow_audit.py route-health plugins\paper-source --json
python scripts\paperflow_audit.py route-health plugins\paper-wiki --json
python scripts\paperflow_audit.py package-hygiene plugins\paper-source --json
python scripts\paperflow_audit.py package-hygiene plugins\paper-wiki --json
```

发布前检查：

```powershell
scripts\release_check_paper_source.ps1
scripts\release_check_paper_wiki.ps1
```

这些命令只证明源码 checkout 通过。要声称用户运行态已更新，还需要 refresh/reinstall marketplace plugin，并在新的 Codex session 中验证 installed cache。

## 安全与隐私

不要提交 runtime secrets、provider tokens、vault-private papers、installed cache 内容或用户 vault 生成物。Runtime credentials 应来自用户环境变量或获准的本地 env files。插件日志和报告可以说明 secret 是否已配置，但不能打印 secret value。

## License

两个插件 manifest 当前声明项目 license 为 MIT。
