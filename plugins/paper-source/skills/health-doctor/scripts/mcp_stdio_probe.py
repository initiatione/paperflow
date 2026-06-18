#!/usr/bin/env python3
"""Probe a line-delimited stdio MCP server and list tools."""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List


SECRET_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASS|AUTH|COOKIE|BEARER)", re.I)


def redact_arg(value: str) -> str:
    if SECRET_RE.search(value):
        return "<redacted>"
    if len(value) > 160:
        return f"{value[:80]}...<truncated>"
    return value


def redact_command(command: List[str]) -> List[str]:
    redacted: List[str] = []
    previous_was_secret_flag = False
    for part in command:
        if previous_was_secret_flag:
            redacted.append("<redacted>")
            previous_was_secret_flag = False
            continue
        redacted.append(redact_arg(part))
        previous_was_secret_flag = bool(SECRET_RE.search(part)) or part.lower() in {
            "--api-key",
            "--token",
            "--secret",
            "--password",
            "--auth",
        }
    return redacted


def parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.lower().startswith("export "):
            stripped = stripped[7:].strip()
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def reader_thread(stream: Any, out: "queue.Queue[str | None]") -> None:
    try:
        for line in stream:
            out.put(line)
    finally:
        out.put(None)


def stderr_thread(stream: Any, lines: List[str], limit: int = 40) -> None:
    for line in stream:
        lines.append(line.rstrip("\n"))
        if len(lines) > limit:
            del lines[: len(lines) - limit]


def send_message(proc: subprocess.Popen[str], message: Dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def wait_for_id(
    out: "queue.Queue[str | None]",
    wanted_id: int,
    timeout: float,
    notifications: List[Dict[str, Any]],
) -> Dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            line = out.get(timeout=remaining)
        except queue.Empty:
            return None
        if line is None:
            return None
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            notifications.append({"non_json_stdout": line[:300]})
            continue
        if message.get("id") == wanted_id:
            return message
        notifications.append(message)
    return None


def terminate(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True, help="Executable to launch")
    parser.add_argument("--arg", action="append", default=[], help="Argument; repeat for multiple args")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--env-file", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    command = [args.command, *args.arg]
    env = os.environ.copy()
    env_file_errors: Dict[str, str] = {}
    for raw_path in args.env_file:
        path = Path(raw_path).expanduser()
        try:
            env.update(parse_env_file(path))
        except OSError as exc:
            env_file_errors[str(path)] = f"{type(exc).__name__}: {exc}"

    redacted_command = redact_command(command)
    stderr_lines: List[str] = []
    notifications: List[Dict[str, Any]] = []
    result: Dict[str, Any] = {
        "schema": "paperflow-mcp-stdio-probe-v1",
        "framing": "line-delimited-json",
        "command": redacted_command,
        "cwd": args.cwd,
        "env_files": args.env_file,
        "env_file_errors": env_file_errors,
    }

    try:
        proc = subprocess.Popen(
            command,
            cwd=args.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        result.update({"status": "launch_failed", "error": f"{type(exc).__name__}: {exc}"})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    assert proc.stdout is not None
    assert proc.stderr is not None
    out: "queue.Queue[str | None]" = queue.Queue()
    threading.Thread(target=reader_thread, args=(proc.stdout, out), daemon=True).start()
    threading.Thread(target=stderr_thread, args=(proc.stderr, stderr_lines), daemon=True).start()

    try:
        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "paperflow-health-doctor", "version": "1.0.0"},
                },
            },
        )
        initialized = wait_for_id(out, 1, args.timeout, notifications)
        if not initialized:
            result.update({"status": "initialize_timeout_or_no_response"})
            return_code = proc.poll()
            if return_code is not None:
                result["process_return_code"] = return_code
            return 0
        if initialized.get("error"):
            result.update({"status": "initialize_error", "initialize": initialized})
            return 0

        send_message(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        send_message(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_response = wait_for_id(out, 2, args.timeout, notifications)
        if not tools_response:
            result.update({"status": "tools_list_timeout_or_no_response", "initialize": initialized})
            return 0
        if tools_response.get("error"):
            result.update(
                {"status": "tools_list_error", "initialize": initialized, "tools_list": tools_response}
            )
            return 0

        tools = tools_response.get("result", {}).get("tools", [])
        tool_names = [tool.get("name") for tool in tools if isinstance(tool, dict) and tool.get("name")]
        result.update(
            {
                "status": "ok",
                "server_info": initialized.get("result", {}).get("serverInfo"),
                "tool_count": len(tool_names),
                "tools": tool_names,
            }
        )
        return 0
    except BrokenPipeError:
        result.update({"status": "broken_pipe"})
        return 0
    finally:
        result["notifications"] = notifications[:20]
        result["stderr_tail"] = stderr_lines[-20:]
        terminate(proc)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
