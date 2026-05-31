# EPI 论文发现子 Skill 说明

这个子 skill 负责 EPI 的论文发现、质量优先排序，以及“1-3 快路”：搜索 -> 选择高价值论文 -> 下载 PDF -> MinerU 解析后停在 raw artifact。

它借鉴 `nature-academic-search` 的 bundle 思路：`SKILL.md` 只做入口，真正的检索策略拆到 `references/`。这样后续优化 source routing、去重、质量门和输出格式时，不需要把所有规则塞进一个大文件。

## 当前结构

```text
paper-discovery/
  SKILL.md
  README.md
  scripts/
    query-planner.py
  references/
    query-planner.md
    domain-ontology.md
    search-protocol.md
    source-tiers.md
    dedup-engine.md
    venue-prior.md
    two-stage-retrieval.md
    citation-graph.md
    evaluation-set.md
    quality-gate.md
    output-format.md
    workflows/
      multi-source-discovery.md
```

## 什么时候用

- 用户要求找某个方向的高质量论文。
- 用户要求最新论文、非综述论文，或任何由用户画像/config 定义的具体主题论文。
- 用户要求 EPI 的 1-3 步，只下载和 MinerU 解析，不进入 reader/critic/staging。

## 执行原则

- 不把 `paper_search_mcp` 返回结果本身当成质量定义。
- 先用用户画像/config + Query Planner 做概念块拆分，再构造 5-8 个 query variants。
- 从 config 的 domains、positive_keywords、negative_keywords、venue_prior 和当前请求衍生匹配词、同义词、验证证据和排除项；不要把某个学科写成全局默认。
- Query plan 的扩展词用于召回和 gap checks；ranking 的画像匹配词只用用户 config 和当前请求核心词，避免宽召回词稀释窄主题相关性。
- 两阶段检索：先做高召回 candidate pool，再去重、核验、精排。
- 按 source tier 路由：结构化学术源优先，网页/出版社页面用于核验和补召回。
- 用期刊/会议分层做 `venue_prior`，但不把主观榜单当成最终质量判断。
- 对高质量 seed paper 使用 citation graph 查 related、references、cited-by 和 journal/conference version。
- 跨 query/source 去重，再和 `_raw/papers` 已下载文献去重。
- 输出给用户时列出本轮保留的全部候选，按阅读优先级排序。
- 影响因子、分区、引用数等质量指标必须有来源或标注未核实。

## 常用命令

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<exact narrow topic>" --no-query-plan --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault <vault>
```

`query-planner.py` 不访问网络，只把用户画像/config 和用户主题转换成可审计的检索计划。默认 `dry-run` 会生成 `_runs/<run-id>/query-plan.json`，并按 query variants 多次搜索形成 candidate pool；默认排除 review/survey/meta 类综述候选，用户明确找综述时才放开。如果 profile-derived 计划偏离用户当前主题，改用 `--no-query-plan` 的精确短语查询或先更新 config。`dry-run` 只写 `_runs`。`prepare-ranked` 只写 `_raw/papers/<slug>`，完成 PDF 下载和 MinerU 解析后停止；实测批量用 `--max-papers 10 --skip-existing`，`--max-papers 1` 只用于 smoke test。

## 参考来源

本子 skill 蒸馏的是 `nature-academic-search` 的结构化检索思想，不迁移它的医学/PubMed 默认语境。迁移点包括 query planning、source tiers、multi-source workflow、dedup engine、venue prior、citation graph、evaluation set 和 citation/venue verification 思路。
