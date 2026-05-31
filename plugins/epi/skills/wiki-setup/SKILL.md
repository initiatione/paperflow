---
name: wiki-setup
description: "Use when the user wants to initialize, create, inspect, repair, or reset the EPI paper research wiki vault structure. Reset is destructive, preserves EPI config by default, and must require a second explicit confirmation before any deletion or move."
---

# EPI Wiki Setup

只负责目标论文研究 wiki 的 vault 结构：初始化、查看、修复、重置。不负责 paper search、paper ingest、MinerU、Zotero 或最终 wiki 写入。

## 配置边界

wiki structure reset and EPI config reset are separate operations. **wiki 结构重置**和 **EPI config 重置**是两个独立操作，需要各自独立的确认。这是这个 skill 最核心的安全原则——清理 wiki 内容时绝不能顺手删掉用户的配置。

默认重置**保留 EPI 配置**，即使用户说"不需要备份"。以下 vault-local 路径在重置时必须保留：

- `_meta\epi-config.yaml`
- `_meta\epi-config-state.json`
- `_meta\epi-config-history\`
- `_meta\config-history\`

user-level runtime 配置在 vault 之外，这个 skill **永不删除**它：

- `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`

任何重置前后都跑 config status，只报告非 secret 状态（`_meta\epi-config.yaml` 是否存在、是否需要 onboarding、`MINERU_TOKEN` 是否设置）：

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

## 初始化

Initialization is idempotent. 幂等操作：只创建缺失的目录和种子文件，不删除已有内容：

```powershell
python scripts\init_paper_wiki.py --vault <vault>
```

预期结构包含：`_raw\papers`、`_staging\papers`、`_quarantine\papers`、`_runs`、`_evolution`、`_meta`、`references`、`concepts`、`synthesis`、`entities`、`skills`、`projects`、`journal`、`.obsidian`、`index.md`、`log.md`、`hot.md`、`.manifest.json`。

完成后总结创建的路径，并告诉用户已有文件被保留。

## 重置（破坏性）

Reset is destructive. 重置不可从单句话直接执行。优先用 CLI reset executor——它默认保留配置并写 reset manifest：

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --preview --json
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --json
```

### 重置前流程

1. 只读 inventory：vault 根目录和重要 EPI 目录。
2. 跑 `config-status`，记录重置前配置是否存在。
3. 明确说明将移动、删除、保留什么。显式列出**配置边界**中的保留行为。
4. 在 active vault 之外提议备份（backup outside the active vault），例如 `<vault-parent>\paper-research-wiki-reset-backups\<timestamp>`。
5. 要求第二次明确确认，使用精确短语：`确认重置 EPI wiki`。
6. 用户说`不需要备份`时，解读为"不备份 wiki 内容" / "do not back up wiki content"，**不授权删除 EPI config**。
7. 确认后才移动/删除重置目标，同时保留配置路径，然后跑初始化。

用户明确拒绝内容备份时用 `--no-backup`，仍保留配置（除非另有 config 重置确认）：

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --no-backup --json
```

### 同时重置配置（需第二道独立确认）

要连同 EPI config 一起重置，必须在同一次对话里提供另一个精确短语：

```text
确认同时重置 EPI config
```

**不要**从"reset wiki"、"clean everything"、"no backup"、"重新初始化"推断出 config 重置。没有这个额外短语，就保护 config 文件和 runtime.json。

只有两个确认都齐全时，才通过 config 重置门：

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --reset-config-confirmed-by "确认同时重置 EPI config" --json
```

### 重置后流程

1. 跑初始化。
2. 再跑一次 `config-status`。
3. 报告配置是被保留还是现在需要 onboarding。
4. 如果配置意外丢失，**停下来**询问是恢复还是重新初始化；不要继续进入 paper discovery、ingest、MinerU 或 wiki-writing。

## Misdelete Recovery / 误删恢复

检测到意外删除、错误重置、保留式重置后配置却丢失，或用户报告"误删""误操作""配置没了""为什么要重新初始化 config"时：

1. **停止当前工作流**，在 paper search / ingest / MinerU / staging / wiki 写入之前停下。
2. 用通俗语言解释可能的边界错误：wiki 内容清理可能误删了 vault-local 配置，而 user-level runtime.json 可能还在。
3. Actively ask whether the user wants help restoring important settings from backups or history. 主动询问是否需要从备份或历史恢复重要设置。
4. 在让用户重新输入前，先搜索安全恢复源：
   - 提议过的 reset 备份根目录，如 `<vault-parent>\paper-research-wiki-reset-backups\`
   - `_meta\epi-config-history\` 或 `_meta\config-history\`（若保留）
   - `<plugin-repo>` 近期 git 历史中的 skill/template 默认值
   - Codex 日志（仅非 secret 配置状态，绝不打印 secret）
   - `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`（runtime 命令路径和 env-file 位置）
5. 找到可信备份时，展示其路径、时间戳和非 secret 摘要，确认后再恢复。
6. 无备份时，用 `config-setup` 协助重新初始化，并明确说明哪些设置无法恢复。

恢复命令：

```powershell
python scripts\orchestrator.py wiki-repair --vault <vault> --json
python scripts\orchestrator.py config-recover --vault <vault> --json
python scripts\orchestrator.py config-restore --vault <vault> --from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
python scripts\orchestrator.py wiki-repair --vault <vault> --restore-from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
```

## 绝不执行的操作

- without the exact second confirmation：没有精确的第二道确认，不重置、不删除。
- 不保留 EPI 配置就重置（除非也提供了`确认同时重置 EPI config`）。
- 解析出的目标路径不是预期 vault 时，不动手。
- 不触碰无关仓库或父目录。
- 在 paper ingest、MinerU parse、promotion 或 wiki ingest 运行期间，不重置。

不确定时，在 inventory 和备份提议之后停下来。
