from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HELPER_ENV = "PAPERFLOW_ZOTERO_HELPER"
ROOTS_ENV = "PAPERFLOW_ZOTERO_PLUGIN_ROOTS"
HELPER_RELATIVE_PATH = Path("skills") / "zotero" / "scripts" / "zotero.py"
DEFAULT_TIMEOUT_SECONDS = 10
REQUIRED_COMMANDS = (
    "status",
    "inventory",
    "search",
    "export-bibtex",
    "import-bibtex",
    "import-ris",
    "selected-target",
)
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|proxy)(=|:)[^\s\"']+"
)
PRIVATE_ENDPOINT_PATTERN = re.compile(r"https?://[^\s\"']*(?:token|key|secret|proxy)[^\s\"']*", re.I)


@dataclass(frozen=True)
class HelperCandidate:
    path: Path
    source: str
    reason: str


@dataclass(frozen=True)
class HelperResolution:
    helper: dict[str, Any] | None
    candidates: list[dict[str, Any]]
    gate: str | None = None
    message: str | None = None


def redact_text(value: str) -> str:
    text = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", value)
    return PRIVATE_ENDPOINT_PATTERN.sub("<redacted-url>", text)


def sanitize_diagnostics(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [sanitize_diagnostics(item) for item in value]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if re.search(r"(?i)(token|secret|password|api[_-]?key|authorization)", str(key)):
                sanitized[key] = "<redacted>"
            else:
                sanitized[key] = sanitize_diagnostics(item)
        return sanitized
    return value


def _candidate_from_root(root: Path, source: str, reason: str) -> HelperCandidate:
    path = root if root.name == "zotero.py" else root / HELPER_RELATIVE_PATH
    return HelperCandidate(path=path.expanduser(), source=source, reason=reason)


def _path_list(raw: str | None) -> list[Path]:
    if not raw:
        return []
    return [Path(part).expanduser() for part in raw.split(os.pathsep) if part.strip()]


def collect_helper_candidates(
    *,
    helper_path: Path | str | None = None,
    extra_roots: list[Path | str] | None = None,
    include_defaults: bool = True,
) -> list[HelperCandidate]:
    candidates: list[HelperCandidate] = []
    if helper_path is not None:
        candidates.append(
            HelperCandidate(Path(helper_path).expanduser(), "explicit_override", "argument")
        )
    env_helper = os.environ.get(HELPER_ENV)
    if env_helper:
        candidates.append(HelperCandidate(Path(env_helper).expanduser(), "explicit_override", HELPER_ENV))
    for root in _path_list(os.environ.get(ROOTS_ENV)):
        candidates.append(_candidate_from_root(root, "configured_root", ROOTS_ENV))
    for root in extra_roots or []:
        candidates.append(_candidate_from_root(Path(root), "configured_root", "extra_roots"))

    if include_defaults:
        home = Path.home()
        cache = home / ".codex" / "plugins" / "cache"
        for base in [
            cache / "openai-curated-remote" / "zotero",
            cache / "openai-bundled" / "zotero",
        ]:
            for version_root in sorted(base.glob("*")) if base.exists() else []:
                candidates.append(_candidate_from_root(version_root, "codex_plugin_cache", str(base)))
        curated = cache / "openai-curated"
        for plugin_root in sorted(curated.glob("*/*/zotero")) if curated.exists() else []:
            candidates.append(_candidate_from_root(plugin_root, "codex_plugin_cache", str(curated)))
        marketplace_plugins = home / ".codex" / ".tmp" / "marketplaces"
        pattern = "*" + os.sep + "plugins" + os.sep + "zotero"
        for plugin_root in sorted(marketplace_plugins.glob(pattern)) if marketplace_plugins.exists() else []:
            candidates.append(
                _candidate_from_root(plugin_root, "paperflow_marketplace_cache", str(marketplace_plugins))
            )
        adjacent = Path.cwd().parent / "zotero"
        if adjacent.exists():
            candidates.append(_candidate_from_root(adjacent, "adjacent_development_checkout", str(adjacent)))

    seen: set[str] = set()
    unique: list[HelperCandidate] = []
    for candidate in candidates:
        key = str(candidate.path)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _skill_dir_for_helper(path: Path) -> Path | None:
    parts = path.parts
    expected = HELPER_RELATIVE_PATH.parts
    if len(parts) < len(expected) or tuple(parts[-len(expected) :]) != expected:
        return None
    return path.parents[1]


def _plugin_root_for_helper(path: Path) -> Path:
    return path.parents[3]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _validate_layout(path: Path) -> tuple[bool, str | None, dict[str, Any]]:
    if not path.is_file():
        return False, "helper_file_missing", {}
    skill_dir = _skill_dir_for_helper(path)
    if skill_dir is None:
        return False, "unexpected_helper_layout", {}
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return False, "skill_metadata_missing", {"skill_md": str(skill_md)}
    skill_text = _read_text(skill_md)
    if "name: Zotero" not in skill_text and "# Zotero" not in skill_text:
        return False, "skill_identity_mismatch", {"skill_md": str(skill_md)}
    manifest_path = _plugin_root_for_helper(path) / ".codex-plugin" / "plugin.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(_read_text(manifest_path))
        except json.JSONDecodeError as exc:
            return False, "plugin_manifest_invalid", {"manifest": str(manifest_path), "error": str(exc)}
        display = ((manifest.get("interface") or {}).get("displayName") or "").lower()
        if str(manifest.get("name") or "").lower() != "zotero" and display != "zotero":
            return False, "plugin_identity_mismatch", {"manifest": str(manifest_path)}
    return True, None, {"skill_md": str(skill_md), "plugin_root": str(_plugin_root_for_helper(path))}


def _run_helper_command(path: Path, args: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), *args],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _validate_command_surface(path: Path, timeout_seconds: int) -> tuple[bool, str | None, dict[str, Any]]:
    try:
        completed = _run_helper_command(path, ["--help"], timeout_seconds)
    except subprocess.TimeoutExpired:
        return False, "command_surface_timeout", {"timeout_seconds": timeout_seconds}
    if completed.returncode != 0:
        return False, "command_surface_help_failed", {
            "returncode": completed.returncode,
            "stderr": redact_text(completed.stderr or ""),
        }
    help_text = f"{completed.stdout}\n{completed.stderr}"
    missing = [command for command in REQUIRED_COMMANDS if command not in help_text]
    if missing:
        return False, "required_commands_missing", {"missing_commands": missing}
    return True, None, {"required_commands": list(REQUIRED_COMMANDS)}


def validate_helper_candidate(candidate: HelperCandidate, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    path = candidate.path.resolve()
    ok, reason, details = _validate_layout(path)
    if ok:
        ok, reason, command_details = _validate_command_surface(path, timeout_seconds)
        details.update(command_details)
    return {
        "path": str(path),
        "source": candidate.source,
        "reason": candidate.reason,
        "validated": ok,
        "rejection_reason": None if ok else reason,
        "details": sanitize_diagnostics(details),
    }


def discover_zotero_helper(
    *,
    helper_path: Path | str | None = None,
    extra_roots: list[Path | str] | None = None,
    include_defaults: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> HelperResolution:
    records: list[dict[str, Any]] = []
    incompatible_seen = False
    for candidate in collect_helper_candidates(
        helper_path=helper_path, extra_roots=extra_roots, include_defaults=include_defaults
    ):
        record = validate_helper_candidate(candidate, timeout_seconds=timeout_seconds)
        records.append(record)
        if record["validated"]:
            return HelperResolution(
                helper={
                    "path": record["path"],
                    "source": record["source"],
                    "validated": True,
                },
                candidates=records,
            )
        if record.get("rejection_reason") != "helper_file_missing":
            incompatible_seen = True
    gate = "zotero_helper_incompatible" if incompatible_seen else "zotero_plugin_missing"
    message = "No compatible official Zotero helper was found."
    return HelperResolution(helper=None, candidates=records, gate=gate, message=message)


def _result(
    *,
    ok: bool,
    gate: str | None,
    message: str | None,
    helper: dict[str, Any] | None,
    command: list[str] | None = None,
    data: Any = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "gate": gate,
        "message": message,
        "command": command,
        "helper": helper,
        "data": data,
        "diagnostics": sanitize_diagnostics(diagnostics or {}),
    }


def _map_failure_gate(text: str) -> str:
    lowered = text.lower()
    if "without --yes" in lowered or "refusing to write" in lowered:
        return "write_not_authorized"
    if "connector" in lowered:
        return "connector_unavailable"
    if "local api" in lowered and ("disabled" in lowered or "pref" in lowered):
        return "local_api_disabled"
    if "timed out" in lowered or "timeout" in lowered:
        return "zotero_timeout"
    if "no response" in lowered or "connection" in lowered or "port" in lowered:
        return "zotero_desktop_unavailable"
    return "zotero_helper_failed"


def _status_gate(data: dict[str, Any]) -> str | None:
    if data.get("local_api_enabled_pref") is False:
        return "local_api_disabled"
    if data.get("api_running") is False:
        return "zotero_desktop_unavailable"
    if data.get("connector_running") is False:
        return "connector_unavailable"
    return None


def _selected_target_name(data: Any) -> str | None:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("name", "collection", "collectionName", "selectedCollection"):
            value = data.get(key)
            if isinstance(value, str):
                return value
            nested = _selected_target_name(value)
            if nested:
                return nested
        for value in data.values():
            nested = _selected_target_name(value)
            if nested:
                return nested
    return None


class ZoteroHelperAdapter:
    def __init__(
        self,
        *,
        helper_path: Path | str | None = None,
        extra_roots: list[Path | str] | None = None,
        include_defaults: bool = True,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.helper_path = helper_path
        self.extra_roots = extra_roots or []
        self.include_defaults = include_defaults
        self.timeout_seconds = timeout_seconds
        self._resolution: HelperResolution | None = None

    def resolve(self) -> HelperResolution:
        if self._resolution is None:
            self._resolution = discover_zotero_helper(
                helper_path=self.helper_path,
                extra_roots=self.extra_roots,
                include_defaults=self.include_defaults,
                timeout_seconds=self.timeout_seconds,
            )
        return self._resolution

    def _execute(
        self,
        args: list[str],
        *,
        expect_json: bool = False,
        write: bool = False,
        approved: bool = False,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        if write and not approved:
            return _result(
                ok=False,
                gate="write_not_authorized",
                message="Zotero write operation requires explicit approval.",
                helper=None,
            )
        resolution = self.resolve()
        if not resolution.helper:
            return _result(
                ok=False,
                gate=resolution.gate,
                message=resolution.message,
                helper=None,
                diagnostics={"candidates": resolution.candidates},
            )
        helper_path = Path(resolution.helper["path"])
        command = [sys.executable, str(helper_path), *args]
        try:
            completed = _run_helper_command(
                helper_path, args, timeout_seconds or self.timeout_seconds
            )
        except subprocess.TimeoutExpired:
            return _result(
                ok=False,
                gate="zotero_timeout",
                message="Zotero helper command timed out.",
                helper=resolution.helper,
                command=command,
                diagnostics={"timeout_seconds": timeout_seconds or self.timeout_seconds},
            )
        diagnostics = {
            "returncode": completed.returncode,
            "stderr": completed.stderr,
            "stdout": completed.stdout if not expect_json else "",
        }
        if completed.returncode != 0:
            detail = completed.stderr or completed.stdout
            return _result(
                ok=False,
                gate=_map_failure_gate(detail),
                message=redact_text(detail.strip() or "Zotero helper command failed."),
                helper=resolution.helper,
                command=command,
                diagnostics=diagnostics,
            )
        data: Any = completed.stdout
        if expect_json:
            try:
                data = json.loads(completed.stdout or "null")
            except json.JSONDecodeError as exc:
                return _result(
                    ok=False,
                    gate="zotero_invalid_json",
                    message=f"Zotero helper returned invalid JSON: {exc}",
                    helper=resolution.helper,
                    command=command,
                    diagnostics=diagnostics,
                )
        return _result(
            ok=True,
            gate=None,
            message=None,
            helper=resolution.helper,
            command=command,
            data=data,
            diagnostics=diagnostics,
        )

    def status(self) -> dict[str, Any]:
        result = self._execute(["status", "--json"], expect_json=True)
        if result["ok"] and isinstance(result["data"], dict):
            gate = _status_gate(result["data"])
            if gate:
                result["ok"] = False
                result["gate"] = gate
                result["message"] = f"Zotero status gate: {gate}"
        return result

    def inventory(self) -> dict[str, Any]:
        return self._execute(["inventory", "--json"], expect_json=True)

    def search(self, query: str, *, with_bibtex_keys: bool = False) -> dict[str, Any]:
        args = ["search", query, "--json"]
        if with_bibtex_keys:
            args.append("--with-bibtex-keys")
        return self._execute(args, expect_json=True)

    def export_bibtex(self, *, out: Path | str | None = None) -> dict[str, Any]:
        args = ["export-bibtex"]
        if out is not None:
            args.extend(["--out", str(out)])
            return self._execute(args, expect_json=True)
        return self._execute(args)

    def export_item_bibtex(self, item_key: str, *, out: Path | str | None = None) -> dict[str, Any]:
        args = ["export-bibtex", "--item-key", item_key]
        if out is not None:
            args.extend(["--out", str(out)])
            return self._execute(args, expect_json=True)
        return self._execute(args)

    def selected_target(self, *, required_name: str | None = None) -> dict[str, Any]:
        result = self._execute(["selected-target", "--json"], expect_json=True)
        if result["ok"] and required_name is not None:
            actual = _selected_target_name(result["data"])
            if actual != required_name:
                result["ok"] = False
                result["gate"] = "selected_target_mismatch"
                result["message"] = f"Selected Zotero target is {actual!r}, expected {required_name!r}."
        return result

    def import_bibtex(
        self,
        *,
        file: Path | str | None = None,
        text: str | None = None,
        session: str | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        return self._import_records("import-bibtex", file=file, text=text, session=session, approved=approved)

    def import_ris(
        self,
        *,
        file: Path | str | None = None,
        text: str | None = None,
        session: str | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        return self._import_records("import-ris", file=file, text=text, session=session, approved=approved)

    def _import_records(
        self,
        command_name: str,
        *,
        file: Path | str | None,
        text: str | None,
        session: str | None,
        approved: bool,
    ) -> dict[str, Any]:
        if (file is None) == (text is None):
            return _result(
                ok=False,
                gate="zotero_helper_failed",
                message="Provide exactly one of file or text for Zotero import.",
                helper=None,
            )
        args = [command_name, "--yes"]
        if file is not None:
            args.extend(["--file", str(file)])
        else:
            args.extend(["--text", text or ""])
        if session:
            args.extend(["--session", session])
        return self._execute(args, expect_json=True, write=True, approved=approved)

