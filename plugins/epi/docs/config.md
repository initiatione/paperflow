# EPI 配置

只读检查和配置页：

```powershell
python scripts\orchestrator.py doctor --json
python scripts\orchestrator.py doctor --open-setup
```

缺 `paper-search-mcp`、CLI fallback、`MINERU_TOKEN`、`EASYSCHOLAR_SECRET_KEY` 或 `_epi\meta\epi-config.yaml` 只报 warning。配置链接：`paper-search-mcp` -> `https://github.com/openags/paper-search-mcp`；`MINERU_TOKEN` -> `https://mineru.net/apiManage/docs?openApplyModal=true`；`EasyScholar` -> `https://www.easyscholar.cc`。不保存、不打印 token 或 secret。

EPI 有两层配置，边界不要混：

- 研究画像、领域、关键词、venue prior、预算、Zotero 和人工确认门写入目标论文库的 EPI 内部仓库：`<vault>\_epi\meta\epi-config.yaml`。
- 本机 runtime 依赖写入 Codex 用户级插件区：`%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`。这里记录 `paper-search` MCP server 命令、CLI fallback、MinerU 命令和 env file 路径，例如 `mineru.env`；也可以用 `easyscholar.env_file` 或 `easyscholar.env_files` 指向只包含 `EASYSCHOLAR_SECRET_KEY` 的独立 env file。runtime.json 不保存 token 明文，也不保存 secret 明文。`MINERU_TOKEN` 和 `EASYSCHOLAR_SECRET_KEY` 只从进程环境或 runtime env file 载入，报告时只能说 `MINERU_TOKEN=set` / `MINERU_TOKEN=missing` 和 `EASYSCHOLAR_SECRET_KEY=set` / `EASYSCHOLAR_SECRET_KEY=missing`。
- EasyScholar 质量增强是 default-on：`dry-run` 默认在 filter 后、rank 前查询期刊/会议质量指标，写入 `_epi\runs\<run-id>\easyscholar-record.json`、候选 `verified_metrics.easyscholar` 和 `easyscholar_score`。缺 key、无匹配、超时或 API 错误都软失败，不阻断 discovery；输出中相关指标写 `未核实`。单次运行可用 `--no-easyscholar` 禁用。
- 显式进程环境变量优先，runtime.json 只补缺失项；插件升级 cache 时不会覆盖用户级 runtime.json。

配置缺失时，不要直接运行论文流程、`dry-run`、MinerU 或 Zotero。初始化只写确认过的 `_epi\meta\epi-config.yaml`；更新配置不得改动 `_epi\raw`、`_epi\runs`、`_epi\staging`、正式 wiki 页或 Zotero 记录。根 `_meta\` 只保留 wiki skill 的正式 contract 文件，例如 schema、taxonomy 和 directory structure。

误删或 reset 后配置缺失时，先恢复再继续论文流程。使用只读恢复扫描列出候选配置，不打印 token 或 secret：

```powershell
python scripts\orchestrator.py wiki-repair --vault <vault> --json
python scripts\orchestrator.py config-recover --vault <vault> --json
```

找到候选后，必须经用户确认再恢复：

```powershell
python scripts\orchestrator.py config-restore --vault <vault> --from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
python scripts\orchestrator.py wiki-repair --vault <vault> --restore-from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
```

## 聊天式初始化脚本

唯一话术来源。不要自由发挥成技术字段问卷，不要用字段名当问题标题。一次只问一个问题。每步说明影响和推荐值，给出 2-3 个参考方向，并告诉用户：不懂可以直接回复：默认。不要一次性输出完整默认配置。

开场：我先帮你把 EPI 的基础设置配好。这里只决定论文库、方向、搜索和解析；不会搜索论文，也不会写正式 wiki。不确定就回复“默认”。

八步确认：

1. 第一步，先定论文库放哪里。推荐一个专用的本地论文库目录，例如 `<vault>`。
2. 第二步，我需要知道你的研究画像：学科/应用对象/方法族/常看任务分别是什么。EPI 是通用插件，不默认任何学科；后续匹配词、同义词、venue prior、搜索 query 和阅读/wiki 侧重点都从这个画像和 config 衍生。
3. 第三步，告诉我哪些词算有用，哪些词要避开，以及你所在领域的高质量期刊/会议/数据库线索。默认把 review / survey / systematic review / literature review / meta-analysis 作为避开词；只有用户明确要求综述时才加入综述偏好。
4. 第四步，先定搜索从哪里来。推荐 `paper-search` + arxiv / semantic / openalex。
5. 第五步，定每次先看多少篇。推荐 20。
6. 第六步，MinerU 先怎么接。推荐 `MINERU_TOKEN` + 默认命令；初始化不调用 MinerU。
7. 第七步，Zotero 要不要先连。推荐暂不启用，只记 collection=`EPI`。
8. 最后一步，什么时候需要你确认？推荐写入正式 wiki 前确认。

确认时先给用户版摘要，必须包含“你刚刚选了什么”；再给技术预览。YAML 只作为技术预览。等用户明确确认后，把 answers 写成 JSON 并运行。最终确认前不得运行 `init-config`：

```powershell
python scripts\orchestrator.py init-config --vault <vault> --answers-json <answers.json>
```

用户要求输出当前配置时，走快路径，不跑 `doctor`：

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

用户要求重新配置时，先说明当前值、目标值和影响；一次只问一个修改目标；确认后才运行 `apply-config-update`。最终确认前不得运行 `apply-config-update`。
