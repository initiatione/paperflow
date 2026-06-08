from __future__ import annotations


def agent_context_policy() -> dict[str, object]:
    return {
        "delegation_model": "clean-worker-final-artifacts",
        "subagent_policy": (
            "Independent wiki-deposition subtasks should run in fresh-context workers. "
            "Workers return bounded final artifacts and verification summaries, then exit."
        ),
        "main_agent_reads": [
            "final worker output",
            "changed file list",
            "verification result",
        ],
        "main_agent_avoids": [
            "large intermediate transcripts",
            "unbounded worker scratchpads",
            "duplicated source-paper summaries",
        ],
        "codex_permission_note": (
            "Codex may use subagents only when the user explicitly authorizes delegation "
            "or parallel agent work for the task or session."
        ),
    }
