---
name: run-lifecycle
description: "Use when EPI _runs, dashboards, research-queue, run logs, or transition-state artifacts accumulate too much, or when the user asks to clean, prune, archive, deduplicate, or lifecycle-manage EPI workflow artifacts."
---

# EPI Run Lifecycle

管理 EPI 工作流的临时产物（`_runs`、dashboards、research-queue、run logs、transition-state），不触碰已下载论文和最终 wiki 内容。

## 默认 dry-run 优先

清理是有破坏性的，所以默认先 dry-run 看清单，确认后再 `--apply`。

工作流在 `_runs` 超过 15 个单次运行目录时会自动触发清理。手动清理仍默认 dry-run：

```powershell
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --json
```

用户同意后才加 `--apply`：

```powershell
python scripts\orchestrator.py run-lifecycle --vault <vault> --keep-latest 15 --keep-per-workflow 2 --apply --json
```

## 委派给子 agent（如可用）

有 subagent 时，把生命周期维护委派给一个小/低成本 worker，让主 agent 继续面向用户的工作流。worker 应：先跑 dry-run，报告候选清单和 manifest 路径，等待用户明确批准后才用 `--apply`。

## 清理边界

**只清理** `_runs` 下的单次运行目录。

**绝不删除**：

- `_runs/index.json`、dashboards、research queue、feedback logs
- `_raw`、`_staging`、最终 wiki 页面、Zotero 记录、config history
- active runs、human-gate-pending runs、非终态 failures（默认受保护）

命令会在 `_meta\run-lifecycle\` 下写一份清理 manifest，便于回溯。

## 与 Discovery 的去重协同

Discovery 阶段必须同时和 `_raw\papers` 去重：已下载的论文应以 `already_in_library:<slug>` 拒绝，而不是再次推荐。这样生命周期清理和去重不会互相打架。
