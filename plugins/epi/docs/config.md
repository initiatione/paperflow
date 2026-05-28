# EPI 配置

安装后如果不确定环境状态，可以先运行只读检查：

```powershell
python scripts\orchestrator.py doctor --json
```

配置缺失时，EPI 必须先完成纯对话初始化。不要直接运行论文流程，不要启动 `dry-run`、`ingest`、MinerU 或 Zotero。初始化只负责把用户确认过的设置写入所选 paper wiki 的 `_meta\epi-config.yaml`，历史备份写入 `_meta\config-history`。更新配置时也必须保留 `_raw`、`_runs`、`_staging`、`references` 和 Zotero 记录。

## 聊天式初始化脚本

这是 EPI 初始化的唯一话术来源。对话要像有人带用户一步步配置，不要自由发挥成技术字段问卷，不要用字段名当问题标题。每一步先说明“这一步决定什么”，再给推荐值，并告诉用户：不懂可以直接回复：默认。

### 开场

我先帮你把 EPI 的基础设置配好。这里只决定论文库放哪里、主要看什么方向、搜索和解析先怎么接；不会开始搜索论文，也不会写入正式 wiki。你不确定的地方都可以直接回复“默认”，后面也能重新配置。

### 8 步逐步确认

1. 第一步，先定论文库放哪里。我建议用 `D:\paper-research-wiki`，以后搜索记录、论文原文、解析结果和配置都会放在这里。直接用这个可以回复：默认。
2. 第二步，我需要知道你主要看哪类论文。建议先用“机器人控制”，它会偏机器人、具身智能和控制方向。以后如果研究重点变了，可以重新配置。
3. 第三步，告诉我哪些词算有用，哪些词要避开。建议先用默认关键词：偏 robot learning、humanoid、model predictive control，避开纯综述和无关生物医学试验。直接用默认即可。
4. 第四步，先定搜索从哪里来。我建议先记录 `paper-search`，来源用 arxiv、semantic、openalex；如果本机命令还没装好，EPI 只保存配置，不会硬跑搜索。
5. 第五步，定每次先看多少篇。我建议先从 20 篇开始；想轻一点可以用 10，想覆盖更广再调高。
6. 第六步，MinerU 先怎么接。建议先写成使用环境变量 `MINERU_TOKEN` 和插件默认解析命令；初始化阶段不会调用 MinerU。
7. 第七步，Zotero 要不要先连。我建议先不启用，只把 collection 记为 `EPI`；等你确定要同步时再打开。
8. 最后一步，什么时候需要你确认？我建议在写入正式 wiki 前问你一次，这样不会自动把未确认的论文写进去。

### 确认摘要

问完后先展示用户版摘要，不要一上来贴大段 YAML：

```text
你刚刚选了什么：
- 论文库位置：D:\paper-research-wiki
- 研究方向：机器人控制，覆盖 robotics / embodied intelligence / control
- 搜索范围：paper-search + arxiv / semantic / openalex
- 每次最多结果数：20
- MinerU：先记录 MINERU_TOKEN 环境变量和默认命令，初始化不调用
- Zotero：暂不启用，collection 记为 EPI
- 人工确认点：写入正式 wiki 前确认

将写入：
- D:\paper-research-wiki\_meta\epi-config.yaml
- D:\paper-research-wiki\_meta\epi-config-state.json
- D:\paper-research-wiki\_meta\config-history\*.yaml
```

然后再给技术预览。YAML 只作为技术预览，不要把它当成主要说明。等用户明确确认后，才把结构化 answers 写成 JSON 并运行：

```powershell
python scripts\orchestrator.py init-config --vault D:\paper-research-wiki --answers-json <answers.json>
```

如果用户说 `reset`、`重新配置`、`修改 EPI 配置`，或用自然语言要求修改配置，先按同样口吻说明当前值、目标值和影响，再运行 `propose-config-update` 生成预览；等用户明确确认后，才运行 `apply-config-update`。
