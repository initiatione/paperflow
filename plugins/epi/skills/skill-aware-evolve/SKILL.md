---
name: skill-aware-evolve
description: "Use when EPI evidence suggests controlled profile, filter, ranking, template, or routing changes."
---

# Skill-Aware Evolve

Use run evidence, feedback, Plugin Eval, or benchmark reports to propose controlled changes. Follow `docs\epi-linkage.md`: classify evidence as `skill_change`, `execution_lapse`, or `configuration_change`. Execution lapses and configuration changes are record-only and must not mutate valid guidance or templates.

If config is missing, record the issue and use `config-setup`. See `docs\config.md`.

## Acceptance Gates

Human approval is required before activation. Accepted chain changes must update `docs\epi-linkage.md`.

Acceptance gates with `metric`, `operator`, and `value` are real non-regression gates. For example, `plugin_eval_score >= 91` must be present in `--validation-result-json`; `passed: true` alone is not enough if the metric regresses, is missing, or cannot be compared.

## Commands

```powershell
python scripts\orchestrator.py propose-evolution --reflection-type OPTIMIZATION --evidence-type plugin_eval_warning --target-asset templates\ranking.example.yaml --rationale <text> --proposed-change-json <json> --before-metrics-json <json> --acceptance-gates-json <json> --evidence <artifact>
python scripts\orchestrator.py evolution-query --status pending_validation --json
python scripts\orchestrator.py activate-evolution --proposal-id <proposal-id> --approved --validation-result-json <json>
```

Config changes use the separate proposal/apply flow in `docs\config.md`; `evolution-query` should point them to `propose-config-update`.
