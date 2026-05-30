# EPI 论文发现子 Skill 说明

这个子 skill 负责 EPI 的论文发现、质量优先排序，以及“1-3 快路”：搜索 -> 选择高价值论文 -> 下载 PDF -> MinerU 解析后停在 raw artifact。

它借鉴 `nature-academic-search` 的 bundle 思路：`SKILL.md` 只做入口，真正的检索策略拆到 `references/`。这样后续优化 source routing、去重、质量门和输出格式时，不需要把所有规则塞进一个大文件。

## 当前结构

```text
paper-discovery/
  SKILL.md
  README.md
  references/
    search-protocol.md
    source-tiers.md
    dedup-engine.md
    venue-prior.md
    quality-gate.md
    output-format.md
    workflows/
      multi-source-discovery.md
```

## 什么时候用

- 用户要求找某个方向的高质量论文。
- 用户要求最新论文、非综述论文、AUV/RL/AI/control 等具体主题论文。
- 用户要求 EPI 的 1-3 步，只下载和 MinerU 解析，不进入 reader/critic/staging。

## 执行原则

- 不把 `paper_search_mcp` 返回结果本身当成质量定义。
- 先做概念块拆分，再构造 3-5 个 query variants。
- 按 source tier 路由：结构化学术源优先，网页/出版社页面用于核验和补召回。
- 用期刊/会议分层做 `venue_prior`，但不把主观榜单当成最终质量判断。
- 跨 query/source 去重，再和 `_raw/papers` 已下载文献去重。
- 输出给用户时列出本轮保留的全部候选，按阅读优先级排序。
- 影响因子、分区、引用数等质量指标必须有来源或标注未核实。

## 常用命令

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault <vault>
```

`dry-run` 只写 `_runs`。`prepare-ranked` 只写 `_raw/papers/<slug>`，完成 PDF 下载和 MinerU 解析后停止。

## 参考来源

本子 skill 蒸馏的是 `nature-academic-search` 的结构化检索思想，不迁移它的医学/PubMed 默认语境。迁移点包括 source tiers、multi-source workflow、dedup engine、venue prior 和 citation/venue verification 思路。
