import argparse
import json
import os
import re
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

import requests


API_ROOT = "https://mineru.net/api/v4"


def default_project_root() -> Path:
    return Path.cwd()


def resolve_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def relative_text(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return os.path.relpath(path.resolve(), project_root.resolve())


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def data_id_for(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._-")
    return (stem or "document")[:100]


def require_ok_json(response: requests.Response, action: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        text = response.text[:500]
        raise RuntimeError(f"{action} returned non-json HTTP {response.status_code}: {text}") from exc
    if response.status_code != 200:
        raise RuntimeError(f"{action} returned HTTP {response.status_code}: {payload}")
    if payload.get("code") != 0:
        raise RuntimeError(f"{action} failed: {payload}")
    return payload


def apply_upload_urls(token: str, files: list[Path], model_version: str, language: str) -> tuple[str, list[str]]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    body = {
        "files": [{"name": file.name, "data_id": data_id_for(file)} for file in files],
        "model_version": model_version,
        "language": language,
        "enable_formula": True,
        "enable_table": True,
        "is_ocr": False,
    }
    response = requests.post(f"{API_ROOT}/file-urls/batch", headers=headers, json=body, timeout=60)
    payload = require_ok_json(response, "apply upload urls")
    data = payload["data"]
    return data["batch_id"], data["file_urls"]


def upload_files(files: list[Path], urls: list[str]) -> None:
    if len(files) != len(urls):
        raise RuntimeError(f"upload url count mismatch: {len(files)} files, {len(urls)} urls")
    for file, url in zip(files, urls):
        print(f"uploading {file.name} ({file.stat().st_size / 1024 / 1024:.1f} MB)")
        with file.open("rb") as handle:
            response = requests.put(url, data=handle, timeout=600)
        if response.status_code not in {200, 201, 204}:
            text = response.text[:500]
            raise RuntimeError(f"upload failed for {file.name}: HTTP {response.status_code}, {text}")


def normalize_results(data: dict) -> list[dict]:
    results = data.get("extract_result", [])
    if isinstance(results, dict):
        return [results]
    return results


def poll_batch(token: str, batch_id: str, timeout: int, interval: int) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    deadline = time.time() + timeout
    last_summary = None
    while time.time() < deadline:
        response = requests.get(f"{API_ROOT}/extract-results/batch/{batch_id}", headers=headers, timeout=60)
        payload = require_ok_json(response, "poll batch")
        results = normalize_results(payload["data"])
        summary = ", ".join(
            f"{item.get('file_name', item.get('data_id', 'unknown'))}:{item.get('state', 'unknown')}"
            for item in results
        )
        if summary != last_summary:
            print(f"batch {batch_id}: {summary}")
            last_summary = summary

        states = {item.get("state") for item in results}
        if results and states <= {"done", "failed"}:
            return results
        time.sleep(interval)
    raise TimeoutError(f"timed out waiting for batch {batch_id}")


def download_markdown_and_assets(zip_url: str, asset_root: Path, extract_images: bool) -> tuple[bytes, int]:
    response = requests.get(zip_url, timeout=600)
    if response.status_code != 200:
        text = response.text[:500]
        raise RuntimeError(f"download zip failed: HTTP {response.status_code}, {text}")
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        candidates = [name for name in archive.namelist() if name.replace("\\", "/").endswith("full.md")]
        if not candidates:
            raise RuntimeError(f"full.md not found in zip. members: {archive.namelist()[:20]}")
        image_count = 0
        if extract_images:
            for member in archive.namelist():
                normalized = member.replace("\\", "/")
                if not normalized.startswith("images/") or normalized.endswith("/"):
                    continue
                target = (asset_root / normalized).resolve()
                if not str(target).startswith(str(asset_root.resolve())):
                    raise RuntimeError(f"unsafe zip member path: {member}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
                image_count += 1
        return archive.read(candidates[0]), image_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse local PDFs with MinerU precise batch API into per-paper Markdown and image folders."
    )
    parser.add_argument("--project-root", default=str(default_project_root()))
    parser.add_argument("--env-file", default=".env/mineru.env")
    parser.add_argument("--input-dir", default="paper")
    parser.add_argument("--output-dir", default="parsed")
    parser.add_argument("--model-version", default="vlm", choices=["pipeline", "vlm"])
    parser.add_argument("--language", default="en")
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--layout", default="document-dir", choices=["document-dir", "flat"])
    parser.add_argument(
        "--batch-id",
        help="Reuse an existing MinerU batch id and download its outputs without re-uploading files.",
    )
    parser.add_argument(
        "--no-extract-images",
        action="store_true",
        help="Save Markdown only. By default, images/ assets are extracted too.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    env_file = resolve_path(project_root, args.env_file)
    load_env_file(env_file)

    token = os.environ.get("MINERU_TOKEN")
    if not token:
        raise RuntimeError(
            f"MINERU_TOKEN is required. Set it in the environment or {relative_text(project_root, env_file)}"
        )

    input_dir = resolve_path(project_root, args.input_dir)
    output_dir = resolve_path(project_root, args.output_dir)
    files = sorted(input_dir.glob("*.pdf")) if input_dir.exists() else []
    if not args.batch_id:
        if not files:
            raise RuntimeError(f"no PDFs found under {relative_text(project_root, input_dir)}")
        if len(files) > 50:
            raise RuntimeError("MinerU batch upload supports at most 50 files per request")

    output_dir.mkdir(parents=True, exist_ok=True)

    if args.batch_id:
        batch_id = args.batch_id
        print(f"batch_id: {batch_id} (reuse)")
    else:
        batch_id, urls = apply_upload_urls(token, files, args.model_version, args.language)
        print(f"batch_id: {batch_id}")
        upload_files(files, urls)
    results = poll_batch(token, batch_id, args.timeout, args.interval)

    manifest = {
        "batch_id": batch_id,
        "model_version": args.model_version,
        "language": args.language,
        "input_dir": relative_text(project_root, input_dir),
        "output_dir": relative_text(project_root, output_dir),
        "layout": args.layout,
        "outputs": [],
    }
    failures = []
    by_name = {file.name: file for file in files}
    for item in results:
        file_name = item.get("file_name") or item.get("data_id") or "unknown.pdf"
        state = item.get("state")
        entry = {
            "file_name": file_name,
            "state": state,
            "data_id": item.get("data_id"),
            "err_msg": item.get("err_msg", ""),
        }
        if state == "done":
            source = by_name.get(file_name)
            stem = source.stem if source else Path(file_name).stem
            if args.layout == "document-dir":
                document_dir = output_dir / stem
                md_dir = document_dir
                asset_root = document_dir
            else:
                document_dir = output_dir
                md_dir = output_dir
                asset_root = output_dir
            md_dir.mkdir(parents=True, exist_ok=True)

            md_bytes, image_count = download_markdown_and_assets(
                item["full_zip_url"],
                asset_root,
                extract_images=not args.no_extract_images,
            )
            out_path = md_dir / f"{stem}.md"
            out_path.write_bytes(md_bytes)
            entry["document_dir"] = relative_text(project_root, document_dir)
            entry["markdown_path"] = relative_text(project_root, out_path)
            entry["image_count"] = image_count
            entry["image_dir"] = relative_text(project_root, asset_root / "images") if image_count else ""
            image_note = f" and {image_count} images" if image_count else ""
            print(f"saved {relative_text(project_root, out_path)}{image_note}")
        else:
            failures.append(entry)
            print(f"failed {file_name}: {item.get('err_msg', '')}")
        manifest["outputs"].append(entry)

    manifest_path = output_dir / f"mineru_batch_{batch_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest: {relative_text(project_root, manifest_path)}")

    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
