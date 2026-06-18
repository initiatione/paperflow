from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from paper_source.artifacts import utc_now, write_json_atomic, write_text_atomic


PROGRESS_EVENTS_SCHEMA_VERSION = "paper-source-progress-events-v1"
DEFAULT_HEARTBEAT_SECONDS = 30.0


def _heartbeat_interval_from_env() -> float:
    raw = os.environ.get("PAPER_SOURCE_PROGRESS_HEARTBEAT_SECONDS")
    if raw is None or not str(raw).strip():
        return DEFAULT_HEARTBEAT_SECONDS
    try:
        value = float(str(raw).strip())
    except ValueError:
        return DEFAULT_HEARTBEAT_SECONDS
    return max(0.01, value)


def _rounded_seconds(value: float) -> float:
    return round(max(0.0, value), 3)


class ProgressReporter:
    def __init__(
        self,
        run_dir: Path,
        *,
        run_id: str,
        workflow_type: str,
        heartbeat_interval_seconds: float | None = None,
        emit_to_stderr: bool = True,
    ) -> None:
        self.run_dir = run_dir
        self.run_id = run_id
        self.workflow_type = workflow_type
        self.heartbeat_interval_seconds = (
            _heartbeat_interval_from_env() if heartbeat_interval_seconds is None else max(0.01, heartbeat_interval_seconds)
        )
        self.emit_to_stderr = emit_to_stderr
        self.events_path = run_dir / "progress-events.jsonl"
        self.summary_path = run_dir / "progress-summary.json"
        self._started_monotonic = time.monotonic()
        self._events: list[dict[str, Any]] = []
        self._phases: dict[str, dict[str, Any]] = {}
        self._current_phase: str | None = None
        self._lock = RLock()

    def artifacts(self) -> dict[str, str]:
        return {
            "progress_events": str(self.events_path),
            "progress_summary": str(self.summary_path),
            "run_dir": str(self.run_dir),
        }

    def start_phase(
        self,
        phase: str,
        message: str,
        *,
        counts: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.event(
            phase,
            "start",
            message,
            counts=counts,
            artifacts=artifacts,
            details=details,
        )

    def end_phase(
        self,
        phase: str,
        message: str,
        *,
        counts: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.event(
            phase,
            "end",
            message,
            counts=counts,
            artifacts=artifacts,
            details=details,
        )

    def heartbeat(
        self,
        phase: str,
        message: str,
        *,
        counts: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.event(
            phase,
            "heartbeat",
            message,
            counts=counts,
            artifacts=artifacts,
            details=details,
        )

    def fail_phase(
        self,
        phase: str,
        message: str,
        *,
        error: object | None = None,
        artifacts: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_details = dict(details or {})
        if error is not None:
            payload_details["error"] = str(error)
            payload_details["error_type"] = type(error).__name__
        return self.event(
            phase,
            "error",
            message,
            artifacts=artifacts,
            details=payload_details,
        )

    def event(
        self,
        phase: str,
        event: str,
        message: str,
        *,
        counts: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now_monotonic = time.monotonic()
        timestamp = utc_now()
        with self._lock:
            phase_info = self._phases.setdefault(
                phase,
                {
                    "phase": phase,
                    "started_at": None,
                    "finished_at": None,
                    "duration_seconds": None,
                    "status": "pending",
                    "event_count": 0,
                    "heartbeat_count": 0,
                    "_started_monotonic": None,
                },
            )
            if event == "start":
                phase_info["started_at"] = timestamp
                phase_info["_started_monotonic"] = now_monotonic
                phase_info["status"] = "running"
                self._current_phase = phase
            elif event == "heartbeat":
                phase_info["heartbeat_count"] = int(phase_info.get("heartbeat_count") or 0) + 1
                phase_info["status"] = "running"
                self._current_phase = phase
            elif event in {"end", "error", "timeout", "cancelled"}:
                phase_info["finished_at"] = timestamp
                phase_info["status"] = "success" if event == "end" else event
                started_monotonic = phase_info.get("_started_monotonic")
                if isinstance(started_monotonic, (int, float)):
                    phase_info["duration_seconds"] = _rounded_seconds(now_monotonic - float(started_monotonic))
                if self._current_phase == phase:
                    self._current_phase = None
            phase_info["event_count"] = int(phase_info.get("event_count") or 0) + 1
            phase_elapsed = None
            started_monotonic = phase_info.get("_started_monotonic")
            if isinstance(started_monotonic, (int, float)):
                phase_elapsed = _rounded_seconds(now_monotonic - float(started_monotonic))
            payload: dict[str, Any] = {
                "schema_version": PROGRESS_EVENTS_SCHEMA_VERSION,
                "timestamp": timestamp,
                "run_id": self.run_id,
                "workflow_type": self.workflow_type,
                "phase": phase,
                "event": event,
                "elapsed_seconds": _rounded_seconds(now_monotonic - self._started_monotonic),
                "message": message,
            }
            if phase_elapsed is not None:
                payload["phase_elapsed_seconds"] = phase_elapsed
            if counts:
                payload["counts"] = counts
            if artifacts:
                payload["artifacts"] = artifacts
            if details:
                payload["details"] = details
            self._events.append(payload)
            self._persist_locked()
        self._emit(payload)
        return payload

    def run_with_heartbeat(
        self,
        phase: str,
        message: str,
        func: Callable[..., Any],
        *args: Any,
        heartbeat_message: str | None = None,
        details: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        result_counts: Callable[[Any], dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        self.start_phase(phase, message, artifacts=artifacts, details=details)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            while True:
                try:
                    result = future.result(timeout=self.heartbeat_interval_seconds)
                    break
                except FutureTimeout:
                    self.heartbeat(
                        phase,
                        heartbeat_message or f"{message} still running",
                        artifacts=artifacts,
                        details=details,
                    )
                except BaseException as exc:
                    self.fail_phase(phase, f"{message} failed", error=exc, artifacts=artifacts, details=details)
                    raise
        counts = result_counts(result) if result_counts is not None else None
        self.end_phase(phase, f"{message} completed", counts=counts, artifacts=artifacts, details=details)
        return result

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return self._summary_locked()

    def _summary_locked(self) -> dict[str, Any]:
        phases: list[dict[str, Any]] = []
        for phase in self._phases.values():
            public_phase = {key: value for key, value in phase.items() if not key.startswith("_")}
            phases.append(public_phase)
        last_event = self._events[-1] if self._events else None
        return {
            "schema_version": PROGRESS_EVENTS_SCHEMA_VERSION,
            "run_id": self.run_id,
            "workflow_type": self.workflow_type,
            "event_count": len(self._events),
            "current_phase": self._current_phase,
            "last_event": last_event,
            "phases": phases,
            "artifacts": self.artifacts(),
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
        }

    def _persist_locked(self) -> None:
        jsonl = "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in self._events)
        write_text_atomic(self.events_path, jsonl)
        write_json_atomic(self.summary_path, self._summary_locked())

    def _emit(self, payload: dict[str, Any]) -> None:
        if not self.emit_to_stderr:
            return
        counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
        count_text = " ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        line = (
            f"[paper-source] phase={payload['phase']} event={payload['event']} "
            f"elapsed={payload['elapsed_seconds']}s {payload['message']}"
        )
        if count_text:
            line = f"{line} {count_text}"
        sys.stderr.write(line.rstrip() + "\n")
        sys.stderr.flush()
