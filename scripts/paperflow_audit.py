from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required for PaperFlow audit checks") from exc


LATIN_STOP = {"the", "this", "that", "for", "and", "you", "with", "new", "fix", "add", "use", "run"}
CJK_STOP = {"这个", "一个", "帮我", "一下", "我的", "怎么", "什么", "这里", "这次", "这条"}
GENERATED_DIR_NAMES = {"__pycache__", ".plugin-eval", "coverage"}
GENERATED_FILE_SUFFIXES = {".pyc", ".pyo", ".pyd"}


@dataclass(frozen=True)
class FileStats:
    lines: int
    chars: int


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def display(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root()).as_posix()
    except ValueError:
        return resolved.as_posix()


def load_routing(plugin_root: Path) -> tuple[Path, dict]:
    routing_path = plugin_root.resolve() / "skills" / "routing.yaml"
    if not routing_path.is_file():
        raise SystemExit(f"missing routing manifest: {routing_path}")
    return routing_path, yaml.safe_load(routing_path.read_text(encoding="utf-8")) or {}


def trigger_tokens(triggers: list[str]) -> set[str]:
    tokens: set[str] = set()
    for trigger in triggers:
        for word in re.findall(r"[a-z0-9]{3,}", trigger.lower()):
            if word not in LATIN_STOP:
                tokens.add(word)
        for run in re.findall(r"[\u4e00-\u9fff]{2,}", trigger):
            if run not in CJK_STOP:
                tokens.add(run)
    return tokens


@lru_cache(maxsize=None)
def resolve_manifest_item(plugin_root: Path, item: str) -> list[Path]:
    raw = item.strip()
    if not raw:
        return []

    roots = [plugin_root / "skills", plugin_root]
    matches: list[Path] = []
    for root in roots:
        for candidate in root.glob(raw):
            if candidate.is_file():
                matches.append(candidate.resolve())

    if not matches:
        normalized = raw[3:] if raw.startswith("../") else raw
        candidate = plugin_root / normalized
        if candidate.is_file():
            matches.append(candidate.resolve())

    return sorted(set(matches))


@lru_cache(maxsize=None)
def read_file_stats(path: Path) -> FileStats:
    if not path.is_file():
        return FileStats(lines=0, chars=0)
    text = path.read_text(encoding="utf-8")
    return FileStats(lines=len(text.splitlines()), chars=len(text))


def route_health(plugin_root: Path) -> dict:
    plugin_root = plugin_root.resolve()
    routing_path, manifest = load_routing(plugin_root)
    routes = manifest.get("routes") or {}
    warnings: list[dict] = []
    acknowledged_overlaps: list[dict] = []
    token_by_route: dict[str, set[str]] = {}
    allowed_overlaps = allowed_route_overlaps(manifest)

    for allowed in allowed_overlaps:
        missing_routes = [route for route in allowed["routes"] if route not in routes]
        if missing_routes:
            warnings.append(
                {
                    "kind": "stale-allowed-overlap",
                    "routes": allowed["routes"],
                    "missing_routes": missing_routes,
                }
            )
        if not allowed["reason"]:
            warnings.append({"kind": "allowed-overlap-without-reason", "routes": allowed["routes"]})

    for route_id, route in routes.items():
        triggers = [str(item) for item in route.get("triggers") or [] if str(item).strip()]
        if not triggers:
            warnings.append({"kind": "no-triggers", "route": route_id})
        elif len(triggers) == 1:
            warnings.append({"kind": "weak-triggers", "route": route_id})

        skill = route.get("skill")
        if skill and not (plugin_root / "skills" / str(skill)).is_file():
            warnings.append({"kind": "missing-skill", "route": route_id, "path": str(skill)})

        for collection_name in ("workflows", "references", "docs"):
            for relative in route.get(collection_name) or []:
                if not resolve_manifest_item(plugin_root, str(relative)):
                    warnings.append(
                        {
                            "kind": f"missing-{collection_name[:-1]}",
                            "route": route_id,
                            "path": str(relative),
                        }
                    )

        token_by_route[route_id] = trigger_tokens(triggers)

    route_ids = list(token_by_route)
    document_frequency: dict[str, int] = {}
    for tokens in token_by_route.values():
        for token in tokens:
            document_frequency[token] = document_frequency.get(token, 0) + 1

    for left_index, left in enumerate(route_ids):
        for right in route_ids[left_index + 1 :]:
            shared = sorted(
                token
                for token in token_by_route[left] & token_by_route[right]
                if document_frequency.get(token) == 2
            )
            if len(shared) >= 2:
                allowed = matching_allowed_overlap(allowed_overlaps, left, right, set(shared))
                if allowed:
                    acknowledged_overlaps.append(
                        {
                            "kind": "overlap",
                            "routes": [left, right],
                            "tokens": shared,
                            "reason": allowed["reason"],
                        }
                    )
                else:
                    warnings.append({"kind": "overlap", "routes": [left, right], "tokens": shared})

    return {
        "plugin": plugin_root.name,
        "routing_path": display(routing_path),
        "route_count": len(routes),
        "warnings": warnings,
        "acknowledged_overlaps": acknowledged_overlaps,
    }


def allowed_route_overlaps(manifest: dict) -> list[dict]:
    raw_entries = (manifest.get("route_health") or {}).get("allowed_overlaps") or []
    allowed: list[dict] = []
    for entry in raw_entries:
        routes = sorted(str(route) for route in entry.get("routes") or [])
        tokens = {str(token).lower() for token in entry.get("tokens") or []}
        allowed.append(
            {
                "routes": routes,
                "tokens": tokens,
                "reason": str(entry.get("reason") or "").strip(),
            }
        )
    return allowed


def matching_allowed_overlap(
    allowed_overlaps: list[dict],
    left: str,
    right: str,
    shared_tokens: set[str],
) -> dict | None:
    route_pair = sorted([left, right])
    for allowed in allowed_overlaps:
        if allowed["routes"] == route_pair and shared_tokens.issubset(allowed["tokens"]):
            return allowed
    return None


def footprint(plugin_root: Path) -> dict:
    plugin_root = plugin_root.resolve()
    _routing_path, manifest = load_routing(plugin_root)
    always_files: set[Path] = set()
    for item in manifest.get("always_read") or []:
        always_files.update(resolve_manifest_item(plugin_root, str(item)))

    route_files: dict[str, set[Path]] = {}
    all_files: set[Path] = set(always_files)
    for route_id, route in (manifest.get("routes") or {}).items():
        files = set(always_files)
        if route.get("skill"):
            files.update(resolve_manifest_item(plugin_root, str(route["skill"])))
        for key in ("workflows", "references", "docs"):
            for item in route.get(key) or []:
                files.update(resolve_manifest_item(plugin_root, str(item)))
        all_files.update(files)
        route_files[route_id] = files

    stats = {path: read_file_stats(path) for path in all_files}
    route_reports: dict[str, dict] = {}
    for route_id, files in route_files.items():
        route_reports[route_id] = {
            "files": len(files),
            "lines": sum(stats[path].lines for path in files),
            "chars": sum(stats[path].chars for path in files),
            "top_files": top_files(files, stats, limit=5),
        }

    return {
        "plugin": plugin_root.name,
        "always_read_files": len(always_files),
        "always_read_lines": sum(stats[path].lines for path in always_files),
        "always_read_chars": sum(stats[path].chars for path in always_files),
        "top_files": top_files(all_files, stats, limit=10),
        "routes": route_reports,
    }


def top_files(paths: set[Path], stats: dict[Path, FileStats], limit: int) -> list[dict]:
    ranked = sorted(paths, key=lambda path: (stats[path].lines, stats[path].chars, display(path)), reverse=True)
    return [
        {
            "path": display(path),
            "lines": stats[path].lines,
            "chars": stats[path].chars,
        }
        for path in ranked[:limit]
    ]


def is_generated_path(path: Path) -> bool:
    if any(part in GENERATED_DIR_NAMES for part in path.parts):
        return True
    if any(part.startswith(".pytest_tmp") for part in path.parts):
        return True
    return path.suffix in GENERATED_FILE_SUFFIXES


def generated_artifacts(plugin_root: Path) -> list[Path]:
    if not plugin_root.exists():
        raise SystemExit(f"missing plugin root: {plugin_root}")
    return sorted(path for path in plugin_root.rglob("*") if is_generated_path(path))


def remove_artifacts(plugin_root: Path, artifacts: list[Path]) -> None:
    root = plugin_root.resolve()
    for artifact in artifacts:
        resolved = artifact.resolve()
        if resolved != root and root not in resolved.parents:
            raise SystemExit(f"refusing to remove outside plugin root: {resolved}")
        if not resolved.exists():
            continue
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()


def package_hygiene(plugin_roots: list[Path], clean: bool = False) -> dict:
    reports = []
    bad: list[Path] = []
    for plugin_root in plugin_roots:
        plugin_root = plugin_root.resolve()
        artifacts = generated_artifacts(plugin_root)
        if clean and artifacts:
            remove_artifacts(plugin_root, artifacts)
            artifacts = generated_artifacts(plugin_root)
        bad.extend(artifacts)
        reports.append(
            {
                "plugin": plugin_root.name,
                "artifact_count": len(artifacts),
                "artifacts": [display(path) for path in artifacts],
            }
        )

    return {
        "ok": not bad,
        "plugins": reports,
        "artifact_count": len(bad),
    }


def print_report(report: dict, json_output: bool) -> None:
    if json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if "routes" in report:
        print(f"Footprint: {report['plugin']}")
        print(f"Always read: {report['always_read_lines']} lines")
        for route, data in report["routes"].items():
            print(f"- {route}: {data['lines']} lines across {data['files']} files")
    elif "route_count" in report:
        print(f"Route health: {report['plugin']} ({report['route_count']} routes)")
        for warning in report["warnings"]:
            print(f"- {warning}")
    else:
        print(f"Package hygiene: {'PASS' if report['ok'] else 'FAIL'}")
        for plugin in report["plugins"]:
            print(f"- {plugin['plugin']}: {plugin['artifact_count']} generated artifacts")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    route_parser = subparsers.add_parser("route-health")
    route_parser.add_argument("plugin_root")
    route_parser.add_argument("--json", action="store_true")

    footprint_parser = subparsers.add_parser("footprint")
    footprint_parser.add_argument("plugin_root")
    footprint_parser.add_argument("--json", action="store_true")

    hygiene_parser = subparsers.add_parser("package-hygiene")
    hygiene_parser.add_argument("plugin_roots", nargs="+")
    hygiene_parser.add_argument("--clean", action="store_true")
    hygiene_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "route-health":
        report = route_health(Path(args.plugin_root))
        print_report(report, args.json)
        return 0
    if args.command == "footprint":
        report = footprint(Path(args.plugin_root))
        print_report(report, args.json)
        return 0
    if args.command == "package-hygiene":
        report = package_hygiene([Path(root) for root in args.plugin_roots], clean=args.clean)
        print_report(report, args.json)
        return 0 if report["ok"] else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
