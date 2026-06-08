# Domain Ontology

Use this lightweight ontology as examples for synonym and evidence-term expansion. It is not a fixed taxonomy and must not override `_meta\epi-config.yaml`; load a section only when the user's profile or current request matches it. For other disciplines, derive equivalent blocks from the user's config, field vocabulary, and venue prior.

## AUV / Marine Control

| Block | Terms |
| --- | --- |
| Platform | AUV, autonomous underwater vehicle, unmanned underwater vehicle, underwater robot, marine robot |
| Methods | reinforcement learning, deep reinforcement learning, offline reinforcement learning, model-based reinforcement learning, adaptive control, MPC, robust control, safety-critical control |
| Tasks | trajectory tracking, path following, tracking control, stabilization, station keeping, manoeuvring, navigation |
| Environment | ocean current, current disturbance, underwater disturbance, turbulence, wave disturbance, uncertain hydrodynamics |
| Evidence | sea trial, field trial, real AUV, hardware experiment, simulation-to-real, sim-to-real, digital twin, benchmark, code |
| Exclusions | review, survey, literature review, systematic review, acoustic communication, underwater sensor network, routing protocol |

## Embodied AI / Robot Learning

| Block | Terms |
| --- | --- |
| Platform | embodied agent, mobile robot, manipulator, humanoid, quadruped, robot system |
| Methods | foundation model, VLA, world model, diffusion policy, imitation learning, reinforcement learning, offline RL, policy learning |
| Tasks | manipulation, locomotion, navigation, planning, whole-body control, dexterous control |
| Evidence | real robot, sim-to-real, benchmark, open-source code, dataset, ablation, long-horizon task |
| Exclusions | review, survey, position paper, pure LLM benchmark, game-only environment |

## General Robotics / Control

| Block | Terms |
| --- | --- |
| Platform | robot, robotic system, autonomous system, field robot |
| Methods | model predictive control, optimal control, adaptive control, robust control, learning-based control, control barrier function |
| Tasks | trajectory tracking, path planning, motion planning, manipulation, navigation, stabilization |
| Evidence | real-world experiment, hardware experiment, field test, benchmark, safety guarantee, reproducibility |
| Exclusions | review, survey, tutorial, editorial |

## Expansion Rules

1. Expand one concept block at a time; do not combine every synonym into one giant query.
2. Keep exact phrases for platform and task terms.
3. Pair broad method terms with narrow platform/task terms.
4. For engineering quality, add one evidence term to at least half of the query variants.
5. Keep exclusions explicit when the user asks for non-review papers.
