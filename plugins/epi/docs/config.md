# EPI 配置

只读检查和配置页：

```powershell
python scripts\orchestrator.py doctor --json
python scripts\orchestrator.py doctor --open-setup
```

缺 `paper-search-mcp`、CLI fallback、`MINERU_TOKEN` 或 `_meta\epi-config.yaml` 只报 warning。配置链接：`paper-search-mcp` -> `https://github.com/openags/paper-search-mcp`；`MINERU_TOKEN` -> `https://mineru.net/apiManage/docs?openApplyModal=true`。不保存、不打印 token。

EPI 有两层配置，边界不要混：

- 研究画像、关键词、预算、Zotero 和人工确认门写入目标论文库：`D:\paper-research-wiki\_meta\epi-config.yaml`。
- 本机 runtime 依赖写入 Codex 用户级插件区：`C:\Users\liuchf\.codex\plugins\paper-search\epi\runtime.json`。这里记录 `paper-search` MCP server 命令、CLI fallback、MinerU 命令和 `mineru.env` 路径；runtime.json 不保存 token 明文。`MINERU_TOKEN` 只从进程环境或 `mineru.env` 载入，报告时只能说 set/missing。
- 显式进程环境变量优先，runtime.json 只补缺失项；插件升级 cache 时不会覆盖用户级 runtime.json。

配置缺失时，不要直接运行论文流程、`dry-run`、MinerU 或 Zotero。初始化只写确认过的 `_meta\epi-config.yaml`；更新配置不得改动 `_raw`、`_runs`、`_staging`、`references` 或 Zotero 记录。

## 聊天式初始化脚本

唯一话术来源。不要自由发挥成技术字段问卷，不要用字段名当问题标题。一次只问一个问题。每步说明影响和推荐值，给出 2-3 个参考方向，并告诉用户：不懂可以直接回复：默认。不要一次性输出完整默认配置。

开场：我先帮你把 EPI 的基础设置配好。这里只决定论文库、方向、搜索和解析；不会搜索论文，也不会写正式 wiki。不确定就回复“默认”。

八步确认：

1. 第一步，先定论文库放哪里。推荐 `D:\paper-research-wiki`。
2. 第二步，我需要知道你主要看哪类论文。推荐“机器人控制”。
3. 第三步，告诉我哪些词算有用，哪些词要避开。
4. 第四步，先定搜索从哪里来。推荐 `paper-search` + arxiv / semantic / openalex。
5. 第五步，定每次先看多少篇。推荐 20。
6. 第六步，MinerU 先怎么接。推荐 `MINERU_TOKEN` + 默认命令；初始化不调用 MinerU。
7. 第七步，Zotero 要不要先连。推荐暂不启用，只记 collection=`EPI`。
8. 最后一步，什么时候需要你确认？推荐写入正式 wiki 前确认。

确认时先给用户版摘要，必须包含“你刚刚选了什么”；再给技术预览。YAML 只作为技术预览。等用户明确确认后，把 answers 写成 JSON 并运行。最终确认前不得运行 `init-config`：

```powershell
python scripts\orchestrator.py init-config --vault D:\paper-research-wiki --answers-json <answers.json>
```

用户要求重新配置时，先说明当前值、目标值和影响；一次只问一个修改目标；确认后才运行 `apply-config-update`。最终确认前不得运行 `apply-config-update`。
