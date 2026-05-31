---
name: paper-discovery
description: "Use when running EPI paper search/ranking dry-runs, finding high-quality papers for a topic, excluding reviews/surveys on request, or starting the precise EPI steps 1-3 path: search, ranked selection, download, and MinerU parse without reader/critic/staging."
---

# Academic Paper Discovery

EPI 检索链路的入口：把用户画像变成可审计的检索计划，召回高质量论文，排序后停在 raw artifact（steps 1-3）。不进入 reader/critic/staging。

主文件只做导航和命令分组；真正的检索策略在 `references/` 里，按需加载，避免一次性塞满 context。

## 核心理念

这个 skill 的灵魂是**用户画像驱动检索**，而不是"把搜索源返回的结果当成质量定义"。流程永远是：

1. 从 `_meta\epi-config.yaml` 的 profile / domains / positive_keywords / negative_keywords / venue_prior 出发；
2. 用 Query Planner 拆成概念块，构造 5-8 个 query variants（宽查询保召回，窄查询保精度）；
3. 两阶段检索：先高召回 candidate pool，再去重、核验、精排。

EPI 是**领域无关**的通用论文插件。不要默认 robotics / AUV / AI / medicine 或任何单一学科词表——所有侧重点必须从用户 config 和当前请求衍生。

## 何时加载哪个 reference

不要一次性读完所有 reference。按当前任务取用：

| 任务 | 读这个 |
| --- | --- |
| 把模糊主题变成检索计划 | `references/query-planner.md` |
| 构造查询、路由源、跑首轮检索 | `references/search-protocol.md` |
| 判断该用哪些源、各源贡献什么 | `references/source-tiers.md` |
| 去重（跨 query + 跨已下载库） | `references/dedup-engine.md` |
| 用期刊/会议分层做排序 prior | `references/venue-prior.md` |
| 高召回池 → 精排的两阶段细节 | `references/two-stage-retrieval.md` |
| 对 seed paper 查 related/cited-by | `references/citation-graph.md` |
| 领域词表示例（仅作可选示例） | `references/domain-ontology.md` |
| 质量门槛与放行标准 | `references/quality-gate.md` |
| 给用户的输出格式 | `references/output-format.md` |
| 多源发现的完整 workflow | `references/workflows/multi-source-discovery.md` |
| 评测集 / 回归检查 | `references/evaluation-set.md` |

The full EPI chain stays documented in `docs\epi-linkage.md`. 整条 EPI 链路文档在 `docs\epi-linkage.md`。`README.md` 是这个子 skill 的中文总览。

## 前置检查

- 配置缺失时**停止检索**，转用 `config-setup`。配置 onboarding 在 `docs\config.md` 的 `## 聊天式初始化脚本`——按脚本走，不要自由发挥成技术字段问卷，也不要一次性输出完整默认配置。
- 安装/依赖不清时跑 `doctor` 或 `config-status`：

```powershell
python scripts\orchestrator.py doctor --plugin-root <plugin-root> --vault <vault> --json
```

## 命令分组

### 1. 生成检索计划（不联网）

`query-planner.py` 只把用户画像 + 主题转成可审计的检索计划，不访问网络：

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
```

### 2. 检索 + 排序（dry-run，只写 _runs）

默认 `dry-run` 会生成 `query-plan.json`，按 query variants 多次检索形成 candidate pool，并在去重/过滤/排序前**排除 review/survey/meta** 类候选：

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
```

仅当 profile-derived 计划明显偏离用户的窄主题、或调试时，才用 `--no-query-plan` 走精确短语查询：

```powershell
python scripts\orchestrator.py dry-run --query "<exact narrow topic>" --no-query-plan --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
```

用户**明确要找综述**时，保留该意图，不要强制排除 review。

### 3. 取数 + 解析（prepare-ranked，只写 _raw\papers）

下载选中的排序论文并用 MinerU 解析，停在 `_raw\papers\<slug>\mineru\...`；prepare-ranked stops after parse / raw artifact：

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault <vault>
```

- 实测批量用 `--max-papers 10 --skip-existing`，避免已解析论文重复消耗配额。
- `--max-papers 1` **只是 smoke test**，不要用于正式跑。
- 串联工具时加 `--json`，读取 prepared run id、processed/skipped counts、stop point 和报告路径。
- `review-candidate` 指"排序置信度较低"，**不一定是综述**。用户要求处理全部论文、或窄领域保守标注时纳入它。
- `prepare-ranked` 记录每篇论文的 `acquire_failed`、`parse_failed` 或 `prepare_failed` 并继续处理后续论文——检查报告而非假设非零退出码意味着全部失败。

## 证据核验

跑完后用这些产物确认结果真实：

- `search-record.json` — 检索记录
- `acquire-record.json` — 下载记录
- `parse-record.json` — 解析记录
- `paper.pdf` — 原始 PDF
- `mineru\paper.md` — Markdown 全文
- `mineru\paper.tex` — LaTeX（含公式）
- `mineru\images` — 图片资产
- `mineru\mineru-manifest.json` — 解析清单

## 安全边界

- `dry-run` 只写 `_runs/<run-id>/`。
- `prepare-ranked` 只写 raw paper artifact，解析后即停。
- 不触碰 reader / critic / staging / wiki。
