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

from epi.artifacts import file_sha256, utc_now, write_json_atomic, write_text_atomic
from epi.runtime_config import apply_runtime_config


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _command_tokens(command: str | Sequence[str] | None, plugin_root: Path) -> list[str]:
    if command is None:
        command = os.environ.get("EPI_MINERU_COMMAND")
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
    return json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path


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


def run_mineru_command(
    paper_root: Path,
    *,
    command: str | Sequence[str] | None = None,
    plugin_root: Path | None = None,
    timeout_seconds: int = 7200,
) -> dict:
    apply_runtime_config()
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
        if batch_id and not markdown_path and re.search(rf"batch\s+{re.escape(batch_id)}:.*:done", completed.stdout):
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
    shutil.copyfile(markdown_path, mineru_dir / "paper.md")
    tex_candidates = sorted(path for path in markdown_path.parent.glob("*.tex") if path.stat().st_size > 0)
    if tex_candidates:
        shutil.copyfile(tex_candidates[0], mineru_dir / "paper.tex")
        tex_source = "mineru-native"
    else:
        tex_source = "markdown-fallback"
        write_text_atomic(
            mineru_dir / "paper.tex",
            _markdown_to_latex((mineru_dir / "paper.md").read_text(encoding="utf-8")),
        )
    image_dir = markdown_path.parent / "images"
    image_count = _copy_tree_contents(image_dir, mineru_dir / "images")
    if manifest_path:
        shutil.copyfile(manifest_path, mineru_dir / "mineru-manifest.json")
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
        "markdown_path": str(mineru_dir / "paper.md"),
        "tex_path": str(mineru_dir / "paper.tex"),
        "tex_source": tex_source,
        "manifest_path": str(mineru_dir / "mineru-manifest.json") if manifest_path else None,
        "image_count": image_count,
        "work_dir_retention": "logs-only",
    }
    record["input_artifact_hashes"] = {
        "paper.pdf": file_sha256(source_pdf),
    }
    output_hashes = {
        "paper.md": file_sha256(mineru_dir / "paper.md"),
        "paper.tex": file_sha256(mineru_dir / "paper.tex"),
        "stdout.txt": file_sha256(stdout_path),
        "stderr.txt": file_sha256(stderr_path),
    }
    if manifest_path:
        output_hashes["mineru-manifest.json"] = file_sha256(mineru_dir / "mineru-manifest.json")
    record["output_artifact_hashes"] = output_hashes
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
    shutil.copyfile(markdown_path, mineru_dir / "paper.md")
    if tex_path:
        shutil.copyfile(tex_path, mineru_dir / "paper.tex")
        tex_source = "fixture-native"
    else:
        tex_source = "markdown-fallback"
        write_text_atomic(
            mineru_dir / "paper.tex",
            _markdown_to_latex((mineru_dir / "paper.md").read_text(encoding="utf-8")),
        )
    (mineru_dir / "images").mkdir(exist_ok=True)
    image_count = 0
    if images_dir and images_dir.exists():
        for image_path in images_dir.iterdir():
            if image_path.is_file():
                shutil.copyfile(image_path, mineru_dir / "images" / image_path.name)
                image_count += 1
    manifest_path = mineru_dir / "mineru-manifest.json"
    write_json_atomic(
        manifest_path,
        {
            "batch_id": "fixture",
            "outputs": [
                {
                    "file_name": "paper.pdf",
                    "state": "done",
                    "markdown_path": "paper.md",
                    "tex_path": "paper.tex",
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
        "markdown_path": str(mineru_dir / "paper.md"),
        "tex_path": str(mineru_dir / "paper.tex"),
        "manifest_path": str(manifest_path),
        "tex_source": tex_source,
        "image_count": image_count,
    }
    input_hashes = {
        "fixture_markdown": file_sha256(markdown_path),
    }
    if tex_path:
        input_hashes["fixture_tex"] = file_sha256(tex_path)
    parse_record["input_artifact_hashes"] = input_hashes
    parse_record["output_artifact_hashes"] = {
        "paper.md": file_sha256(mineru_dir / "paper.md"),
        "paper.tex": file_sha256(mineru_dir / "paper.tex"),
        "mineru-manifest.json": file_sha256(manifest_path),
    }
    write_json_atomic(paper_root / "parse-record.json", parse_record)
    return parse_record
