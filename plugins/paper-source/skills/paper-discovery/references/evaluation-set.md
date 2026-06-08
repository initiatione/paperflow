# Evaluation Set For Discovery Quality

Use this file to keep EPI paper discovery honest as the skill evolves. The point is not to create a large benchmark immediately; it is to keep small, repeatable prompts with expected behavior.

## Metrics

| Metric | Meaning |
| --- | --- |
| `recall_at_20` | Did the run find known important papers or venue families in the top 20 kept/near-kept candidates? |
| `precision_at_10` | Are the first 10 recommendations actually on topic and non-review when requested? |
| `review_leakage` | Count of review/survey papers that survived when the user excluded them |
| `duplicate_rate` | DOI/title/library duplicates divided by raw candidates |
| `verified_metric_coverage` | Share of kept papers with verified DOI, venue/year, PDF, and citation or metric status |
| `recall_gap_count` | Important papers or venue families found only after live verification or citation expansion |

## Seed Prompts

| ID | Prompt | Expected behavior |
| --- | --- | --- |
| `auv-rl-control-non-review` | Find latest high-quality AUV reinforcement learning control papers, not reviews | Expand AUV/UUV synonyms, exclude reviews, include marine/control venues, prefer real AUV/field/sim-to-real/safety evidence |
| `embodied-ai-world-models` | Find high-quality embodied intelligence world model robot learning papers | Include robot learning and AI/ML venues, reject pure LLM/game-only papers |
| `humanoid-rl-whole-body-control` | Find humanoid whole-body control papers using RL | Include Humanoids/ICRA/IROS/RSS/CoRL, prefer real robot and sim-to-real |
| `robot-foundation-model-manipulation` | Find robot foundation model manipulation papers with real robot evidence | Include VLA/foundation model terms, prefer real manipulation benchmarks and code/data |
| `marine-path-following-current` | Find marine robot path following papers under ocean currents | Include AUV/marine robot synonyms, current disturbance, tracking/path-following, marine engineering venues |

## Regression Rule

When a future change claims to improve precision, run at least one seed prompt manually or with a fixture and record:

- query plan
- raw candidate count
- deduped candidate count
- accepted/rejected count
- top kept papers
- review leakage
- recall gaps

Do not accept a skill change that only makes the prose sound better while reducing recall or allowing review leakage.
