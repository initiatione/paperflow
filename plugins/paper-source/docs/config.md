# Paper Source 配置

只读检查和配置页：

```powershell
python scripts\orchestrator.py doctor --json
python scripts\orchestrator.py doctor --open-setup
```

缺 `paper-search-mcp`、CLI fallback、`MINERU_TOKEN`、`EASYSCHOLAR_SECRET_KEY` 或 `_paper_source\meta\paper-source-config.yaml` 只报 warning。`doctor --json` 同时报告 `mcp_outer_launcher` 和 `codex_mcp_registration`：前者检查插件 `.mcp.json` 外层 bootstrap command、`cwd: "."`、`cmd /c .\scripts\paper_search_mcp_launcher.cmd` 相对启动器，以及是否残留 Codex 不会展开的 `${CLAUDE_PLUGIN_ROOT}` / `${PLUGIN_ROOT}` 占位符；残留时报告 `unresolved_plugin_root_placeholder`。后者检查用户级 `config.toml` 是否残留会遮蔽插件自注册的 `[mcp_servers.paper-search-mcp]`。配置链接：`paper-search-mcp` -> `https://github.com/openags/paper-search-mcp`；`MINERU_TOKEN` -> `https://mineru.net/apiManage/docs?openApplyModal=true`；`EasyScholar` -> `https://www.easyscholar.cc`。不保存、不打印 token 或 secret。

Paper Source 有两层配置，边界不要混：一层是研究偏好，一层是本机工具 runtime。插件配置不能只理解成用户研究喜好；paper-search、Grok、MinerU、EasyScholar、provider key env file 和 CLI/MCP 命令同样属于插件运行配置，必须可诊断、可迁移、可在没有开发源码 checkout 的机器上工作。

- 研究画像、领域、关键词、venue prior、预算、Zotero 和人工确认门写入目标论文库的 Paper Source 内部仓库：`<vault>\_paper_source\meta\paper-source-config.yaml`。
- 本机 runtime 依赖写入 Codex 用户级插件区：`%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json`。这里记录 `paper-search` MCP server 命令、CLI fallback、可选 `grok-search-rs MCP` 命令、MinerU 命令和 env file 路径，例如 `mineru.env`；也可以用 `paper_search_mcp.env_file` 指向只包含 `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL` / `UNPAYWALL_EMAIL`、`PAPER_SEARCH_MCP_CORE_API_KEY`、`PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY`、`PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL`、`PAPER_SEARCH_MCP_DOAJ_API_KEY` 或 `PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN` 的独立 env file，用 `grok_search_mcp.env_file` / `grok_search_mcp.env_files` 指向只包含 Grok/search provider key 的独立 env file，用 `easyscholar.env_file` 或 `easyscholar.env_files` 指向只包含 `EASYSCHOLAR_SECRET_KEY` 的独立 env file。默认和推荐做法是把这些 env file 放在同一个用户级插件 runtime 目录下，例如 `%USERPROFILE%\.codex\plugins\paperflow\paper-source\paper-search-providers.env`、`grok-search.env`、`mineru.env`、`easyscholar.env`；`runtime.json` 只引用这些用户级 runtime 文件，不能依赖开发源码 checkout、项目 `.env` 目录、vault 内部 `_paper_source`、临时目录或版本化 plugin cache。命令字段应是 PATH 上的安装命令、全局工具路径、解释器路径或用户级 runtime wrapper；不能指向开发目录中的辅助脚本，例如 `<dev-checkout>\.env\paper-search-live.ps1`。MinerU env file 可额外放 `PAPER_SOURCE_MINERU_CDN_RESOLVE=cdn-mineru.openxlab.org.cn=<ip>`，用于 fake-IP/TLS EOF 环境下恢复 `full_zip_url` 下载；这不是 token，仍应避免把临时 CDN IP 当成永久配置。runtime.json 不保存 token 明文，也不保存 secret 明文。插件的 source `.mcp.json` 负责自注册 `paper-search-mcp`，使用 `cwd: "."` 和 `cmd /c .\scripts\paper_search_mcp_launcher.cmd` 从安装插件根启动通用 launcher；不要求用户在 `config.toml` 写 `[mcp_servers.paper-search-mcp]`，也不写死机器解释器；本机解释器路径只放在 runtime.json 的 `paper_search_mcp.command`，或由 launcher 的 adaptive Python detection 自动选择真正能 `import paper_search_mcp` 的 Python。若找不到可用解释器，launcher 会直接输出包含 runtime.json 和 `PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND` 的诊断信息后退出，避免 Codex 只显示不透明的 handshake failure。`doctor --json` 会报告 `mcp_outer_launcher`、`codex_mcp_registration`、`runtime_path_policy`、`paper_search_provider_readiness` 和可选 `grok_search_mcp`，把插件外层启动器、用户级静态覆盖、runtime 路径越界、Unpaywall email、CORE key、Semantic Scholar key、Google Scholar proxy、DOAJ key、Zenodo token、Grok runtime command 的缺口显示成安装期状态，而不是隐藏成搜索/下载随机失败。`MINERU_TOKEN`、`EASYSCHOLAR_SECRET_KEY`、paper-search provider key 和 Grok provider key 只从进程环境或 runtime env file 载入，报告时只能说 key 是否已加载，不得打印值。
- 目标 vault 的 `_paper_source\meta\paper-source-config.yaml` 可配置 `grok_search.mode`、`targeted_query_budget`、`parallel_query_budget`、`grok_only_recommendation_cap` 和 `academic_domains`。默认 `mode: targeted`；未配置 runtime command 时实际 discovery 自动 resolves to `off`。`academic_domains.mode: append` 会在内置 IEEE/ACM/ScienceDirect/Springer/JSTOR/Web of Science/Scopus/ResearchGate 等 gap domains 后追加自定义域；`override` 只使用自定义域。
- 采集阶段优先调用 paper-search MCP `download_with_fallback`，默认开放访问链为 `source-native -> OpenAIRE -> CORE -> Europe PMC -> PMC -> Unpaywall`；若候选没有 direct PDF URL 且 OA fallback 无 PDF，会写 `failure_class=manual-download-required`、`manual_download.candidate_manual_urls` 和 organization/institution 手动下载提示，不继续弱 fallback。只有 direct PDF URL 存在时才继续回退 source-native MCP、CLI 或 direct URL。Sci-Hub 默认关闭；只有用户显式设置 `PAPER_SOURCE_PAPER_SEARCH_MCP_USE_SCIHUB=1` 时才会把 `scihub` 加入 fallback chain，可用 `PAPER_SOURCE_PAPER_SEARCH_MCP_SCIHUB_BASE_URL` 覆盖 base URL。采集成功后可调用 MCP `read_<source>_paper` 或 CLI read 写 `paper-search-read-preview.txt`，并把 `retrieval_preview` 记录进 `acquire-record.json`；这是 non-authoritative sidecar，not replacing MinerU。不要把 provider key、token 或 secret 明文写入运行报告。
- EasyScholar 质量增强是 default-on：`dry-run` 默认在 filter 后、rank 前查询期刊/会议质量指标，写入 `_paper_source\runs\<run-id>\easyscholar-record.json`、候选 `verified_metrics.easyscholar` 和 `easyscholar_score`。缺 key、无匹配、超时或 API 错误都软失败，不阻断 discovery；输出中相关指标写 `未核实`。单次运行可用 `--no-easyscholar` 禁用。
- 显式进程环境变量优先，runtime.json 只补缺失项；插件升级 cache 时不会覆盖用户级 runtime.json。

配置缺失时，不要直接运行论文流程、`dry-run`、MinerU 或 Zotero。初始化只写确认过的 `_paper_source\meta\paper-source-config.yaml`；更新配置不得改动 `_paper_source\raw`、`_paper_source\runs`、`_paper_source\staging`、正式 wiki 页或 Zotero 记录。根 `_meta\` 只保留 wiki skill 的正式 contract 文件，例如 schema、taxonomy 和 directory structure。旧命名配置文件不再作为运行时兼容读取来源；需要历史迁移时先运行显式迁移/恢复流程生成当前命名配置。

误删或 reset 后配置缺失时，先恢复再继续论文流程。使用只读恢复扫描列出候选配置，不打印 token 或 secret：

```powershell
python scripts\orchestrator.py wiki-repair --vault <vault> --json
python scripts\orchestrator.py config-recover --vault <vault> --json
```

找到候选后，必须经用户确认再恢复：

```powershell
python scripts\orchestrator.py config-restore --vault <vault> --from <backup-config-yaml> --confirmed-by "确认恢复 Paper Source config" --json
python scripts\orchestrator.py wiki-repair --vault <vault> --restore-from <backup-config-yaml> --confirmed-by "确认恢复 Paper Source config" --json
```

## 聊天式初始化脚本

唯一话术来源。不要自由发挥成技术字段问卷，不要用字段名当问题标题。一次只问一个问题。每步说明影响和推荐值，给出 2-3 个参考方向，并告诉用户：不懂可以直接回复：默认。不要一次性输出完整默认配置。

开场：我先帮你把 Paper Source 的基础设置配好。这里只决定论文库、方向、搜索和解析；不会搜索论文，也不会写正式 wiki。不确定就回复“默认”。

八步确认：

1. 第一步，先定论文库放哪里。推荐一个专用的本地论文库目录，例如 `<vault>`。
2. 第二步，我需要知道你的研究画像：学科/应用对象/方法族/常看任务分别是什么。Paper Source 是通用插件，不默认任何学科；后续匹配词、同义词、venue prior、搜索 query 和阅读/wiki 侧重点都从这个画像和 config 衍生。
3. 第三步，告诉我哪些词算有用，哪些词要避开，以及你所在领域的高质量期刊/会议/数据库线索。默认把 review / survey / systematic review / literature review / meta-analysis 作为避开词；只有用户明确要求综述时才加入综述偏好。
4. 第四步，先定搜索从哪里来。推荐 `paper-search` + arxiv / semantic / openalex / crossref / unpaywall；Unpaywall 需要 provider email 才能稳定补充开放 PDF 链接。
5. 第五步，定每次先看多少篇。推荐 20。
6. 第六步，MinerU 先怎么接。推荐 `MINERU_TOKEN` + 默认命令；初始化不调用 MinerU。
7. 第七步，Zotero 要不要先连。推荐暂不启用，只记 collection=`Paper Source`。
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
