# PaperFlow Agent Instructions

This is the repo-level thin shell for agents working in `D:\paper-search`.

Before changing any plugin code, skill, workflow, docs, tests, manifest, generated contract, release script, or marketplace-visible behavior, read `docs/plugin-development.md` and follow it.

For Paper Source work, also read `plugins/paper-source/AGENTS.md` and `plugins/paper-source/skills/routing.yaml`.

For Paper Wiki work, also read `plugins/paper-wiki/AGENTS.md` and `plugins/paper-wiki/skills/routing.yaml`.

Local contracts and tests override external references. External projects are references only unless `docs/plugin-development.md` says otherwise.

PS/PW are allowed natural-language aliases and trigger phrases. Historical legacy names are not user entrypoints, route triggers, or new artifact contracts.

Do not treat source checkout validation as installed runtime validation. Report whether marketplace refresh, reinstall, or installed-cache verification is still needed.

<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->
