# EPI Plugin Agent Entry

This is a thin shell for agents working inside the EPI plugin package. It does not duplicate the skill bodies or long-lived workflow rules.

<!-- ROUTING_BOOTSTRAP_START -->
<always-applicable>
- Read `skills/routing.yaml` before changing code, docs, or skill behavior.
- Match the current task route, then read only the routed skill/docs needed for that route.
- re-match the route on every new user task; re-read routed files when the route changes, context was compacted, or you are unsure.
- Keep durable rules in skill docs or `docs/`, not in this shell.
</always-applicable>

<task-routing>
- Prefer focused workflow modules over growing `cli.py`, `orchestrator.py`, or `stage_wiki.py`.
- For code or docs changes, close the task with original constraints, verification evidence, and a 30-second AAR.
- Codex may use subagents only when the user explicitly authorizes delegation or parallel agent work for the task or session.
- When that permission exists, delegate independent EPI workflow subtasks to fresh-context workers and review only final artifacts, changed files, and verification results.
</task-routing>
<!-- ROUTING_BOOTSTRAP_END -->
