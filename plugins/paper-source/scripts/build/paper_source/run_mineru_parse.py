from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from paper_source.artifacts import PAPER_SOURCE_ROOT_NAME, file_sha256, read_json, utc_now, write_json_atomic, write_text_atomic
from paper_source.asset_normalization import count_preserved_images, normalize_mineru_assets
from paper_source.evidence_index import build_paper_evidence_index
from paper_source.runtime_config import apply_runtime_config
from paper_source.source_artifacts import canonical_mineru_markdown_path, is_nonempty_file


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _command_tokens(command: str | Sequence[str] | None, plugin_root: Path) -> list[str]:
    if command is None:
        command = os.environ.get("PAPER_SOURCE_MINERU_COMMAND")
    if command is None:
        bundled = plugin_root / "skills" / "mineru-paper-parser" / "scripts" / "mineru_batch_to_md.py"
        return [sys.executable, str(bundled)] if bundled.exists() else ["mineru_batch_to_md.py"]
    if isinstance(command, str):
        if command.lower().endswith(".ps1"):
            return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", command]
        tokens = shlex.split(command, posix=os.name != "nt")
        if os.name == "nt":
            tokens = [token.strip("\"'") for token in tokens]
        return tokens
    return [str(part) for part in command]


def _write_failure_record(
    paper_root: Path,
    *,
    command: list[str],
    exit_code: int | None,
    stdout_path: Path,
    stderr_path: Path,
    error: str,
    started_at: str,
    batch_id: str | None = None,
) -> dict:
    record = {
        "stage": "parse",
        "mode": "mineru-command",
        "status": "failed",
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 1,
        "command": command,
        "exit_code": exit_code,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "error": error,
        "input_artifact_hashes": {
            "paper.pdf": file_sha256(paper_root / "paper.pdf"),
        },
        "output_artifact_hashes": {
            "stdout.txt": file_sha256(stdout_path),
            "stderr.txt": file_sha256(stderr_path),
        },
    }
    if batch_id:
        record["batch_id"] = batch_id
    write_json_atomic(paper_root / "parse-record.json", record)
    return record


def _read_manifest(output_dir: Path) -> tuple[dict | None, Path | None]:
    manifests = sorted(output_dir.glob("mineru_batch_*.json"))
    if not manifests:
        return None, None
    manifest_path = manifests[0]
    return read_json(manifest_path), manifest_path


def _resolve_manifest_path(work_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else work_dir / path


def _find_markdown(work_dir: Path, output_dir: Path, manifest: dict | None) -> Path | None:
    if manifest:
        for output in manifest.get("outputs", []):
            if output.get("state") == "done":
                markdown = _resolve_manifest_path(work_dir, output.get("markdown_path"))
                if markdown and markdown.exists():
                    return markdown
    candidates = sorted(output_dir.rglob("*.md"))
    return candidates[0] if candidates else None


def _batch_id_from(stdout: str, manifest: dict | None) -> str | None:
    if manifest and manifest.get("batch_id"):
        return str(manifest["batch_id"])
    match = re.search(r"batch_id:\s*([^\s()]+)", stdout)
    return match.group(1) if match else None


def _manifest_failure_summary(manifest: dict | None) -> str | None:
    if not manifest:
        return None
    failures: list[str] = []
    for output in manifest.get("outputs", []):
        if not isinstance(output, dict):
            continue
        state = str(output.get("state") or "").strip()
        if state in {"done", ""}:
            continue
        file_name = output.get("file_name") or output.get("data_id") or "unknown"
        message = str(output.get("err_msg") or "").strip()
        if message:
            failures.append(f"{file_name}:{state}: {message}")
        else:
            failures.append(f"{file_name}:{state}")
    if not failures:
        return None
    return "; ".join(failures[:3])


def _copy_tree_contents(source_dir: Path, target_dir: Path) -> int:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    if not source_dir.exists():
        return count
    for source in source_dir.rglob("*"):
        if not source.is_file():
            continue
        target = target_dir / source.relative_to(source_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        count += 1
    return count


def _escape_latex_text(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _markdown_image_to_latex(line: str) -> str | None:
    match = re.match(r"!\[[^\]]*\]\(([^)]+)\)", line.strip())
    if not match:
        return None
    image_path = match.group(1).strip()
    return "\n".join(
        [
            r"\begin{figure}[htbp]",
            r"\centering",
            rf"\includegraphics[width=\linewidth]{{{_escape_latex_text(image_path)}}}",
            r"\end{figure}",
        ]
    )


def _markdown_to_latex(markdown: str) -> str:
    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{graphicx}",
        r"\usepackage{hyperref}",
        r"\usepackage{amsmath}",
        r"\begin{document}",
        "",
    ]
    in_itemize = False
    heading_commands = {
        1: "section",
        2: "subsection",
        3: "subsubsection",
    }
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append("")
            continue

        image_latex = _markdown_image_to_latex(line)
        if image_latex:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(image_latex)
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            level = len(heading.group(1))
            title = _escape_latex_text(heading.group(2).strip())
            command = heading_commands.get(level)
            if command:
                lines.append(rf"\{command}{{{title}}}")
            else:
                lines.append(rf"\paragraph{{{title}}}")
            continue

        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if bullet:
            if not in_itemize:
                lines.append(r"\begin{itemize}")
                in_itemize = True
            lines.append(rf"\item {_escape_latex_text(bullet.group(1).strip())}")
            continue

        if in_itemize:
            lines.append(r"\end{itemize}")
            in_itemize = False
        lines.append(_escape_latex_text(line))

    if in_itemize:
        lines.append(r"\end{itemize}")
    lines.extend(["", r"\end{document}", ""])
    return "\n".join(lines)


def _existing_tex_path(mineru_dir: Path) -> Path | None:
    tex_path = mineru_dir / "paper.tex"
    return tex_path if is_nonempty_file(tex_path) else None


def _record_tex_artifact(record: dict, output_hashes: dict[str, str], mineru_dir: Path, tex_source: str) -> None:
    tex_path = _existing_tex_path(mineru_dir)
    record["tex_path"] = str(tex_path) if tex_path else None
    record["tex_source"] = tex_source
    if tex_path:
        output_hashes["paper.tex"] = file_sha256(tex_path)


_DEFAULT_MINERU_TIMEOUT_SECONDS = 7200


def _resolve_mineru_timeout(timeout_seconds: int | None) -> int:
    """Resolve the MinerU subprocess timeout.

    Precedence: explicit positive ``timeout_seconds`` -> ``PAPER_SOURCE_MINERU_TIMEOUT``
    environment variable (positive int) -> default 7200 seconds. Invalid or
    non-positive values are ignored rather than raising.
    """

    if isinstance(timeout_seconds, int) and not isinstance(timeout_seconds, bool) and timeout_seconds > 0:
        return timeout_seconds
    raw = os.environ.get("PAPER_SOURCE_MINERU_TIMEOUT")
    if raw is not None:
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return _DEFAULT_MINERU_TIMEOUT_SECONDS


def _vault_path_from_paper_root(paper_root: Path) -> Path | None:
    parts = paper_root.resolve().parts
    if len(parts) >= 3 and parts[-3] == PAPER_SOURCE_ROOT_NAME and parts[-2] == "raw":
        return Path(*parts[:-3])
    return None


def _attach_evidence_index(record: dict, paper_root: Path) -> dict:
    vault_path = _vault_path_from_paper_root(paper_root)
    try:
        evidence_index = build_paper_evidence_index(paper_root, vault_path=vault_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        record["evidence_index"] = {"status": "failed", "error": str(exc)}
        return record

    evidence_path = paper_root / "evidence-index.json"
    record["evidence_index"] = {
        "status": "success",
        "path": str(evidence_path),
        "chunk_count": len(evidence_index.get("chunks") or []),
        "warnings": evidence_index.get("warnings") or [],
    }
    record.setdefault("output_artifact_hashes", {})
    record["output_artifact_hashes"]["evidence-index.json"] = file_sha256(evidence_path)
    return record


def run_mineru_command(
    paper_root: Path,
    *,
    command: str | Sequence[str] | None = None,
    plugin_root: Path | None = None,
    timeout_seconds: int | None = None,
) -> dict:
    apply_runtime_config()
    timeout_seconds = _resolve_mineru_timeout(timeout_seconds)
    paper_root = paper_root.resolve()
    source_pdf = paper_root / "paper.pdf"
    if not source_pdf.exists():
        raise FileNotFoundError(f"missing acquired PDF: {source_pdf}")

    plugin_root = (plugin_root or _plugin_root()).resolve()
    command_tokens = _command_tokens(command, plugin_root)
    work_dir = paper_root / "mineru-command"
    input_dir = work_dir / "paper"
    output_dir = work_dir / "parsed"
    stdout_path = work_dir / "stdout.txt"
    stderr_path = work_dir / "stderr.txt"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_pdf, input_dir / "paper.pdf")

    started_at = utc_now()
    args = command_tokens + [
        "--project-root",
        str(work_dir),
        "--input-dir",
        "paper",
        "--output-dir",
        "parsed",
        "--layout",
        "document-dir",
    ]
    try:
        completed = subprocess.run(
            args,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        write_text_atomic(stdout_path, "")
        write_text_atomic(stderr_path, str(exc))
        return _write_failure_record(
            paper_root,
            command=args,
            exit_code=None,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            error=f"MinerU command unavailable: {command_tokens[0]}",
            started_at=started_at,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")
        write_text_atomic(stdout_path, stdout)
        write_text_atomic(stderr_path, stderr)
        return _write_failure_record(
            paper_root,
            command=args,
            exit_code=None,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            error=f"MinerU command timed out after {timeout_seconds} seconds",
            started_at=started_at,
        )

    write_text_atomic(stdout_path, completed.stdout)
    write_text_atomic(stderr_path, completed.stderr)
    if completed.returncode != 0:
        manifest, _ = _read_manifest(output_dir)
        markdown_path = _find_markdown(work_dir, output_dir, manifest)
        batch_id = _batch_id_from(completed.stdout, manifest)
        error = f"MinerU command failed with exit code {completed.returncode}"
        manifest_failure = _manifest_failure_summary(manifest)
        if manifest_failure and not markdown_path:
            error = f"MinerU output download failed: {manifest_failure}"
        elif batch_id and not markdown_path and re.search(rf"batch\s+{re.escape(batch_id)}:.*:done", completed.stdout):
            error = "MinerU reported done but produced no Markdown output"
        return _write_failure_record(
            paper_root,
            command=args,
            exit_code=completed.returncode,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            error=error,
            started_at=started_at,
            batch_id=batch_id,
        )

    manifest, manifest_path = _read_manifest(output_dir)
    markdown_path = _find_markdown(work_dir, output_dir, manifest)
    if not markdown_path:
        batch_id = _batch_id_from(completed.stdout, manifest)
        return _write_failure_record(
            paper_root,
            command=args,
            exit_code=completed.returncode,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            error="MinerU command produced no Markdown output",
            started_at=started_at,
            batch_id=batch_id,
        )

    mineru_dir = paper_root / "mineru"
    mineru_dir.mkdir(parents=True, exist_ok=True)
    mineru_markdown_path = canonical_mineru_markdown_path(paper_root)
    legacy_markdown_path = mineru_dir / "paper.md"
    if legacy_markdown_path.exists() or legacy_markdown_path.is_symlink():
        legacy_markdown_path.unlink()
    shutil.copyfile(markdown_path, mineru_markdown_path)
    tex_candidates = sorted(path for path in markdown_path.parent.glob("*.tex") if path.stat().st_size > 0)
    if tex_candidates:
        shutil.copyfile(tex_candidates[0], mineru_dir / "paper.tex")
        tex_source = "mineru-native"
    else:
        stale_tex = mineru_dir / "paper.tex"
        if stale_tex.exists() or stale_tex.is_symlink():
            stale_tex.unlink()
        tex_source = "paused-no-native-tex"
    image_dir = markdown_path.parent / "images"
    image_count = _copy_tree_contents(image_dir, mineru_dir / "images")
    if manifest_path:
        shutil.copyfile(manifest_path, mineru_dir / "mineru-manifest.json")
    asset_record = normalize_mineru_assets(paper_root, execute=True)
    image_count = count_preserved_images(paper_root)
    if input_dir.exists():
        shutil.rmtree(input_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    record = {
        "stage": "parse",
        "mode": "mineru-command",
        "status": "success",
        "started_at": started_at,
        "finished_at": utc_now(),
        "exit_status": 0,
        "command": args,
        "exit_code": completed.returncode,
        "batch_id": _batch_id_from(completed.stdout, manifest),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "markdown_path": str(mineru_markdown_path),
        "manifest_path": str(mineru_dir / "mineru-manifest.json") if manifest_path else None,
        "image_count": image_count,
        "asset_normalization": {
            "status": "success",
            "path": str(paper_root / "asset-normalization-record.json"),
            "renamed_count": len(asset_record.get("rename_plan") or []),
            "dropped_formula_image_count": len(asset_record.get("dropped_formula_images") or []),
            "needs_review_count": len(asset_record.get("needs_review") or []),
            "warnings": asset_record.get("warnings") or [],
        },
        "work_dir_retention": "logs-only",
    }
    record["input_artifact_hashes"] = {
        "paper.pdf": file_sha256(source_pdf),
    }
    output_hashes = {
        f"{paper_root.name}.md": file_sha256(mineru_markdown_path),
        "stdout.txt": file_sha256(stdout_path),
        "stderr.txt": file_sha256(stderr_path),
    }
    _record_tex_artifact(record, output_hashes, mineru_dir, tex_source)
    if manifest_path:
        output_hashes["mineru-manifest.json"] = file_sha256(mineru_dir / "mineru-manifest.json")
    for artifact_name in ["figure-index.json", "formula-index.json", "asset-normalization-record.json"]:
        artifact_path = paper_root / artifact_name
        if artifact_path.exists():
            output_hashes[artifact_name] = file_sha256(artifact_path)
    record["output_artifact_hashes"] = output_hashes
    record = _attach_evidence_index(record, paper_root)
    write_json_atomic(paper_root / "parse-record.json", record)
    return record


def materialize_mineru_fixture(
    paper_root: Path,
    markdown_path: Path,
    tex_path: Path | None = None,
    images_dir: Path | None = None,
) -> dict:
    started_at = utc_now()
    mineru_dir = paper_root / "mineru"
    mineru_dir.mkdir(parents=True, exist_ok=True)
    mineru_markdown_path = canonical_mineru_markdown_path(paper_root)
    legacy_markdown_path = mineru_dir / "paper.md"
    if legacy_markdown_path.exists() or legacy_markdown_path.is_symlink():
        legacy_markdown_path.unlink()
    shutil.copyfile(markdown_path, mineru_markdown_path)
    if tex_path and is_nonempty_file(tex_path):
        shutil.copyfile(tex_path, mineru_dir / "paper.tex")
        tex_source = "fixture-native"
    else:
        stale_tex = mineru_dir / "paper.tex"
        if stale_tex.exists() or stale_tex.is_symlink():
            stale_tex.unlink()
        tex_source = "paused-no-native-tex"
    (mineru_dir / "images").mkdir(exist_ok=True)
    image_count = 0
    if images_dir and images_dir.exists():
        for image_path in images_dir.iterdir():
            if image_path.is_file():
                shutil.copyfile(image_path, mineru_dir / "images" / image_path.name)
                image_count += 1
    asset_record = normalize_mineru_assets(paper_root, execute=True)
    image_count = count_preserved_images(paper_root)
    manifest_path = mineru_dir / "mineru-manifest.json"
    write_json_atomic(
        manifest_path,
        {
            "batch_id": "fixture",
            "outputs": [
                {
                    "file_name": "paper.pdf",
                    "state": "done",
                    "markdown_path": f"{paper_root.name}.md",
                    "tex_path": "paper.tex" if tex_source == "fixture-native" else None,
                    "image_count": image_count,
                }
            ],
        },
    )
    parse_record = {
        "stage": "parse",
        "mode": "fixture",
        "status": "success",
        "started_at": started_at,
        "finished_at": utc_now(),
        "parsed_at": utc_now(),
        "exit_status": 0,
        "markdown_path": str(mineru_markdown_path),
        "manifest_path": str(manifest_path),
        "image_count": image_count,
        "asset_normalization": {
            "status": "success",
            "path": str(paper_root / "asset-normalization-record.json"),
            "renamed_count": len(asset_record.get("rename_plan") or []),
            "dropped_formula_image_count": len(asset_record.get("dropped_formula_images") or []),
            "needs_review_count": len(asset_record.get("needs_review") or []),
            "warnings": asset_record.get("warnings") or [],
        },
    }
    input_hashes = {
        "fixture_markdown": file_sha256(markdown_path),
    }
    if tex_path and is_nonempty_file(tex_path):
        input_hashes["fixture_tex"] = file_sha256(tex_path)
    parse_record["input_artifact_hashes"] = input_hashes
    output_artifact_hashes = {
        f"{paper_root.name}.md": file_sha256(mineru_markdown_path),
        "mineru-manifest.json": file_sha256(manifest_path),
        "figure-index.json": file_sha256(paper_root / "figure-index.json"),
        "formula-index.json": file_sha256(paper_root / "formula-index.json"),
        "asset-normalization-record.json": file_sha256(paper_root / "asset-normalization-record.json"),
    }
    _record_tex_artifact(parse_record, output_artifact_hashes, mineru_dir, tex_source)
    parse_record["output_artifact_hashes"] = output_artifact_hashes
    parse_record = _attach_evidence_index(parse_record, paper_root)
    write_json_atomic(paper_root / "parse-record.json", parse_record)
    return parse_record
