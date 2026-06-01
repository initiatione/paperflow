from __future__ import annotations

import json
import uuid
from pathlib import Path

from epi.artifacts import runs_root, utc_now, write_json_atomic


def record_feedback(
    vault_path: Path,
    *,
    feedback_type: str,
    target: str,
    message: str,
    source: str,
    run_id: str | None = None,
) -> dict:
    feedback = {
        "id": uuid.uuid4().hex,
        "recorded_at": utc_now(),
        "type": feedback_type,
        "target": target,
        "message": message,
        "source": source,
    }
    if run_id is not None:
        feedback["run_id"] = run_id
    log_path = runs_root(vault_path) / "feedback.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(feedback, ensure_ascii=False) + "\n")
    if run_id is not None:
        summary_path = log_path.parent / run_id / "feedback-summary.json"
        if summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            summary = {
                "run_id": run_id,
                "feedback_count": 0,
                "feedback_ids": [],
                "feedback_types": [],
                "last_feedback_id": None,
                "created_at": feedback["recorded_at"],
            }
        summary["feedback_count"] += 1
        summary["feedback_ids"].append(feedback["id"])
        summary["feedback_types"].append(feedback_type)
        summary["last_feedback_id"] = feedback["id"]
        summary["updated_at"] = feedback["recorded_at"]
        write_json_atomic(summary_path, summary)
    return feedback
