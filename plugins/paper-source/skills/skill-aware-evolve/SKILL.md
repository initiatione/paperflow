---
name: skill-aware-evolve
description: >
  Use when optimizing Paper Source safely: "优化 Paper Source 插件", Plugin Eval, quality gates, propose-evolution.
---

# Skill-Aware Evolve

Use run evidence, feedback, Plugin Eval, or benchmark reports to propose controlled Paper Source changes. Follow `docs\paper-source-linkage.md`: classify evidence as `skill_change`, `execution_lapse`, or `configuration_change`. Execution/configuration lapses are record-only and must not mutate valid guidance or templates. If config is missing, record it and use `config-setup`; see `docs\config.md`.

For run evidence, use the public Report surface:

```powershell
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
```

This reads `_paper_source/runs/<run-id>/report.json` and `report.md`; it does not rerun workflows or apply changes. The internal module is `report_run.py`, not a separate `run-report` command.

## Gates

Human approval is required before activation. Accepted chain changes must update `docs\paper-source-linkage.md`.

Acceptance gates with `metric`, `operator`, and `value` are real non-regression gates. Example: `plugin_eval_score >= 91` must be present in `--validation-result-json`; `passed: true` alone is not enough if the metric regresses, is missing, or cannot be compared.

`quality_loop_sources_complete` is also a real activation gate. If an `evaluation-brief` forwards missing/invalid Plugin Eval, `paper-source-quality-gates`, or benchmark sources into `propose-evolution`, `activate-evolution` must reject it even when `--validation-result-json` says `{"passed": true}`.

## Commands

```powershell
python scripts\orchestrator.py propose-evolution --reflection-type OPTIMIZATION --evidence-type plugin_eval_warning --target-asset templates\ranking.example.yaml --rationale <text> --proposed-change-json <json> --before-metrics-json <json> --acceptance-gates-json <json> --evidence <artifact>
python scripts\orchestrator.py evolution-query --status pending_validation --json
python scripts\orchestrator.py activate-evolution --proposal-id <proposal-id> --approved --validation-result-json <json>
```

Config changes use the separate proposal/apply flow in `docs\config.md`; `evolution-query` should point them to `propose-config-update`.
