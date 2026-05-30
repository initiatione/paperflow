# Workflow: Multi-Source Engineering Paper Discovery

Use this workflow when the user asks for high-quality papers, latest papers, non-review papers, or a specific robotics/control/AI topic.

## Procedure

1. Analyze topic into concept blocks:
   - platform or domain object, such as AUV, humanoid, manipulator, mobile robot
   - method family, such as RL, MPC, adaptive control, diffusion policy, world model
   - task, such as tracking, stabilization, path following, manipulation, navigation
   - environment or disturbance, such as ocean current, turbulence, contact, sim-to-real
   - validation mode, such as field trial, real robot, simulator, benchmark, proof
   - exclusions, especially review/survey when requested
2. Build 3-5 query variants. Include exact phrases and acronym expansions.
3. Route sources by `source-tiers.md`.
4. Search T1 sources first through `paper_search_mcp` or configured source adapters.
5. Deduplicate by `dedup-engine.md`.
6. Apply venue prior using `venue-prior.md`, then verify venue/citation/DOI/PDF/code and record unverified metrics explicitly.
7. Apply `quality-gate.md` to label Tier A/B/C/Reject.
8. If venue priors indicate missing obvious venues or papers, run a sharper rerun and record the recall gap.
9. Present all kept papers using `output-format.md`.

## Venue Prior Step

For robotics/control topics, classify venue before final ranking:

- Use curated robotics lists such as RoboWiki as a community prior.
- Use community discussions such as Zhihu only as weak recall hints or subjective context.
- Verify official venue, publisher page, DOI, citation count, and impact metrics separately.
- For AUV/control topics, include marine engineering and ocean robotics venues in the recall check, not only general robotics/AI venues.

Do not promote a paper only because a venue is highly ranked. A strong venue with weak topic fit still needs review; a lower-tier venue with real field validation may be valuable for engineering reading.

## Output Evidence

The final answer should distinguish:

- `venue_prior`: community or curated venue tier, if used.
- `verified_metrics`: DOI, citation count, IF/JCR/CiteScore, official venue page, PDF/code.
- `verification_warnings`: fields that are plausible but not confirmed.
- `recall_gap`: important papers or venues discovered outside the first EPI result set.
