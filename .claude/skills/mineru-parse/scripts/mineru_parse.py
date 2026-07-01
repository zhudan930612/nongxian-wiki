#!/usr/bin/env python3
"""
mineru_parse.py

Call the MinerU cloud precise parsing API to convert documents to Markdown.
Supports single local files, local directory batches, and single remote URLs.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import secrets
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

BASE_URL = "https://mineru.net/api/v4"
SUPPORTED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp",
    ".html", ".htm",
}
MAX_BATCH_SIZE = 50


class MinerUError(Exception):
    """Base exception for MinerU API errors."""

    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.exit_code = exit_code
        self.message = message


class ExtractionError(MinerUError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=4)


class OutputError(MinerUError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=5)


def log(message: str, verbose: bool = True) -> None:
    """Log human-readable messages to stderr."""
    if verbose:
        print(message, file=sys.stderr)


def get_api_token(args: argparse.Namespace) -> str:
    """Resolve API token: --token > MINERU_API_TOKEN env > error."""
    token = args.token or os.environ.get("MINERU_API_TOKEN")
    if not token:
        raise MinerUError(
            "Missing MinerU API token. Set MINERU_API_TOKEN environment variable or pass --token.",
            exit_code=1,
        )
    return token


def is_url(path: str) -> bool:
    """Check if input is a remote URL."""
    parsed = urlparse(path)
    return parsed.scheme in ("http", "https")


def collect_local_files(input_path: str) -> list[str]:
    """Expand directory to list of supported files."""
    path = Path(input_path)
    if not path.exists():
        raise MinerUError(f"Input path does not exist: {input_path}", exit_code=1)

    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise MinerUError(
                f"Unsupported file type: {path.suffix}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                exit_code=1,
            )
        return [str(path.resolve())]

    if path.is_dir():
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(path.rglob(f"*{ext}"))
            files.extend(path.rglob(f"*{ext.upper()}"))
        # De-duplicate and sort
        files = sorted(set(str(p.resolve()) for p in files))
        if not files:
            raise MinerUError(f"No supported files found in directory: {input_path}", exit_code=1)
        return files

    raise MinerUError(f"Input path is neither a file nor a directory: {input_path}", exit_code=1)


def build_common_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build the common extraction parameters payload."""
    payload: dict[str, Any] = {
        "model_version": args.model_version,
        "enable_formula": args.enable_formula,
        "enable_table": args.enable_table,
        "language": args.language,
    }
    if args.extra_formats:
        payload["extra_formats"] = args.extra_formats
    if args.callback:
        payload["callback"] = args.callback
    if args.seed is not None:
        payload["seed"] = args.seed
    if args.no_cache:
        payload["no_cache"] = True
    if args.cache_tolerance is not None:
        payload["cache_tolerance"] = args.cache_tolerance
    return payload


def resolve_output_dir(input_path: str, override: str | None = None) -> Path:
    """Resolve the parent output directory."""
    if override:
        return Path(override)
    return Path("00-收件箱/PDF解析")


def build_file_entry(local_path: str, args: argparse.Namespace, index: int) -> dict[str, Any]:
    """Build a single file entry for batch upload API."""
    path = Path(local_path)
    data_id = args.data_id or f"{path.stem}_{index}"
    entry: dict[str, Any] = {
        "name": path.name,
        "data_id": data_id,
        "is_ocr": args.is_ocr,
    }
    if args.page_ranges:
        entry["page_ranges"] = args.page_ranges
    return entry


def headers(token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def request_upload_urls(file_paths: list[str], token: str, args: argparse.Namespace) -> tuple[str, dict[str, tuple[str, str]]]:
    """
    Request temporary upload URLs for local files.
    Returns (batch_id, {local_path: (file_id_or_name, upload_url)}).
    """
    payload = build_common_payload(args)
    payload["files"] = [
        build_file_entry(p, args, i) for i, p in enumerate(file_paths)
    ]

    log(f"Applying for {len(file_paths)} upload URL(s)...", args.verbose)
    resp = requests.post(
        f"{BASE_URL}/file-urls/batch",
        headers=headers(token),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise MinerUError(
            f"Failed to request upload URLs: {data.get('msg', 'unknown error')} (code={data.get('code')})",
            exit_code=2,
        )

    batch_id = data["data"]["batch_id"]
    upload_urls = data["data"]["file_urls"]

    if len(upload_urls) != len(file_paths):
        raise MinerUError(
            f"Upload URL count mismatch: got {len(upload_urls)}, expected {len(file_paths)}",
            exit_code=2,
        )

    mapping: dict[str, tuple[str, str]] = {}
    for local_path, upload_url in zip(file_paths, upload_urls):
        file_name = Path(local_path).name
        mapping[local_path] = (file_name, upload_url)

    log(f"batch_id: {batch_id}", args.verbose)
    return batch_id, mapping


def upload_file(local_path: str, upload_url: str, verbose: bool) -> None:
    """Upload a single file to the temporary URL via PUT."""
    log(f"Uploading {Path(local_path).name}...", verbose)
    with open(local_path, "rb") as f:
        resp = requests.put(upload_url, data=f, timeout=300)
    resp.raise_for_status()
    log(f"Uploaded {Path(local_path).name}", verbose)


def poll_batch_result(batch_id: str, file_paths: list[str], token: str, args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    """
    Poll batch extraction result until all files are done or failed.
    Returns {local_path: result_dict}.
    """
    file_names = {str(Path(p).name): p for p in file_paths}
    url = f"{BASE_URL}/extract-results/batch/{batch_id}"
    headers_ = {"Authorization": f"Bearer {token}"}
    start = time.time()

    log("Waiting for extraction to complete...", args.verbose)
    while time.time() - start < args.timeout:
        resp = requests.get(url, headers=headers_, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise MinerUError(
                f"Failed to query batch result: {data.get('msg', 'unknown error')} (code={data.get('code')})",
                exit_code=2,
            )

        results = data["data"].get("extract_result", [])
        # Map by file_name
        mapped: dict[str, dict[str, Any]] = {}
        for r in results:
            file_name = r.get("file_name")
            if file_name in file_names:
                mapped[file_names[file_name]] = r

        # Check if all are terminal
        all_done = True
        for local_path in file_paths:
            r = mapped.get(local_path, {})
            state = r.get("state", "")
            if state in ("done", "failed"):
                continue
            all_done = False
            progress = r.get("extract_progress", {})
            log(
                f"[{state}] {Path(local_path).name}: "
                f"{progress.get('extracted_pages', 0)}/{progress.get('total_pages', '?')} pages",
                args.verbose,
            )

        if all_done:
            log("Extraction complete.", args.verbose)
            return mapped

        time.sleep(args.poll_interval)

    raise MinerUError(
        f"Polling timed out after {args.timeout}s for batch {batch_id}",
        exit_code=3,
    )


def submit_url_task(file_url: str, token: str, args: argparse.Namespace) -> str:
    """Submit a single remote URL extraction task. Returns task_id."""
    payload = build_common_payload(args)
    payload["url"] = file_url
    if args.data_id:
        payload["data_id"] = args.data_id
    if args.page_ranges:
        payload["page_ranges"] = args.page_ranges

    log(f"Submitting URL task: {file_url}", args.verbose)
    resp = requests.post(
        f"{BASE_URL}/extract/task",
        headers=headers(token),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise MinerUError(
            f"Failed to submit URL task: {data.get('msg', 'unknown error')} (code={data.get('code')})",
            exit_code=2,
        )

    task_id = data["data"]["task_id"]
    log(f"task_id: {task_id}", args.verbose)
    return task_id


def poll_url_task(task_id: str, token: str, args: argparse.Namespace) -> dict[str, Any]:
    """Poll single URL extraction result until done or failed."""
    url = f"{BASE_URL}/extract/task/{task_id}"
    headers_ = {"Authorization": f"Bearer {token}"}
    start = time.time()

    log("Waiting for extraction to complete...", args.verbose)
    while time.time() - start < args.timeout:
        resp = requests.get(url, headers=headers_, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise MinerUError(
                f"Failed to query task result: {data.get('msg', 'unknown error')} (code={data.get('code')})",
                exit_code=2,
            )

        result = data["data"]
        state = result.get("state", "")
        if state == "done":
            log("Extraction complete.", args.verbose)
            return result
        elif state == "failed":
            raise ExtractionError(f"Task {task_id} failed: {result.get('err_msg', 'unknown')}")

        progress = result.get("extract_progress", {})
        log(
            f"[{state}] {progress.get('extracted_pages', 0)}/{progress.get('total_pages', '?')} pages",
            args.verbose,
        )
        time.sleep(args.poll_interval)

    raise MinerUError(
        f"Polling timed out after {args.timeout}s for task {task_id}",
        exit_code=3,
    )


def to_relative_path(path: str) -> str:
    """Convert an absolute path under the vault root to a relative POSIX path."""
    try:
        p = Path(path).resolve()
        cwd = Path.cwd().resolve()
        rel = p.relative_to(cwd)
        return rel.as_posix()
    except (ValueError, OSError):
        return path


def make_base_name(input_path: str) -> str:
    """Derive a safe base name from input file path or URL."""
    if is_url(input_path):
        parsed = urlparse(input_path)
        path = parsed.path
        name = Path(path).stem if path and Path(path).name else parsed.netloc.replace(".", "_")
    else:
        name = Path(input_path).stem
    # Strip common suffixes MinerU might add
    name = name.strip()
    return name


def build_frontmatter(base_name: str, source_path: str) -> str:
    """Build YAML frontmatter for the extracted markdown."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return f"""---
title: 全文·{base_name}
source_pdf: {source_path}
type: fulltext
extracted_by: mineru
extracted_date: {today}
extraction_quality: good
---

"""


def normalize_images_and_markdown(output_dir: Path, base_name: str, source_path: str, verbose: bool) -> None:
    """Rename images dir/images and update markdown references."""
    old_md = output_dir / "full.md"
    old_images_dir = output_dir / "images"

    if not old_md.exists():
        raise OutputError(f"full.md not found in extracted output: {output_dir}")
    if not old_images_dir.exists():
        raise OutputError(f"images/ not found in extracted output: {output_dir}")

    # Generate a globally unique token for image assets
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    token = f"{timestamp}_{rand}"

    new_md = output_dir / f"{base_name}.md"
    new_images_dir = output_dir / f"{token}.images"

    # Rename images directory
    old_images_dir.rename(new_images_dir)

    # Rename image files to {token}_{seq}.{ext}
    image_files = sorted(new_images_dir.iterdir(), key=lambda p: p.stat().st_mtime)
    rename_map: dict[str, str] = {}
    for idx, img_path in enumerate(image_files, start=1):
        if not img_path.is_file():
            continue
        new_name = f"{token}_{idx:03d}{img_path.suffix.lower()}"
        new_path = new_images_dir / new_name
        img_path.rename(new_path)
        rename_map[img_path.name] = new_name

    # Read markdown and replace image references
    md_content = old_md.read_text(encoding="utf-8")

    for old_name, new_name in rename_map.items():
        old_ref_md = f"images/{old_name}"
        new_ref_md = f"{token}.images/{new_name}"
        md_content = md_content.replace(old_ref_md, new_ref_md)

        old_ref_md_alt = f"images/{old_name.replace(' ', '%20')}"
        md_content = md_content.replace(old_ref_md_alt, new_ref_md)

    # Add figure captions to bare image references
    lines = md_content.splitlines()
    new_lines = []
    fig_no = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("!") and f"{token}.images/" in stripped:
            fig_no += 1
            line = line.replace("![](", f"![图 {fig_no}](", 1)
            line = line.replace("![image](", f"![图 {fig_no}](", 1)
        new_lines.append(line)
    md_content = "\n".join(new_lines)

    # Write frontmatter + content to new markdown file
    if is_url(source_path):
        rel_source = source_path
    else:
        rel_source = to_relative_path(source_path)
    frontmatter = build_frontmatter(base_name, rel_source)
    new_md.write_text(frontmatter + md_content, encoding="utf-8")

    # Remove old full.md
    old_md.unlink()

    log(f"Saved {new_md.name} and {new_images_dir.name}/", verbose)
    return token


def download_and_extract(zip_url: str, output_dir: Path, base_name: str, source_path: str, verbose: bool) -> str:
    """Download the result zip and normalize output naming. Returns image token."""
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "mineru_result.zip"

    log(f"Downloading result to {output_dir}...", verbose)
    resp = requests.get(zip_url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    log("Extracting result...", verbose)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(output_dir)

    zip_path.unlink(missing_ok=True)

    # Keep only full.md and images/; remove everything else from the zip
    for item in output_dir.iterdir():
        if item.name in ("full.md", "images"):
            continue
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

    return normalize_images_and_markdown(output_dir, base_name, source_path, verbose)


def process_local_files(file_paths: list[str], output_dir: Path, token: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Process a list of local files in batches of up to 50."""
    results: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    chunks = [file_paths[i : i + MAX_BATCH_SIZE] for i in range(0, len(file_paths), MAX_BATCH_SIZE)]

    for chunk in chunks:
        try:
            batch_id, upload_map = request_upload_urls(chunk, token, args)
            for local_path in chunk:
                _, upload_url = upload_map[local_path]
                upload_file(local_path, upload_url, args.verbose)

            batch_results = poll_batch_result(batch_id, chunk, token, args)

            for local_path in chunk:
                result = batch_results.get(local_path, {})
                state = result.get("state", "")
                base_name = make_base_name(local_path)
                file_output_dir = output_dir / base_name
                file_output_dir.mkdir(parents=True, exist_ok=True)

                if state != "done":
                    err = result.get("err_msg") or f"state={state}"
                    failed.append({
                        "input": local_path,
                        "error": err,
                    })
                    log(f"FAILED {Path(local_path).name}: {err}", args.verbose)
                    continue

                zip_url = result.get("full_zip_url")
                if not zip_url:
                    failed.append({
                        "input": local_path,
                        "error": "No full_zip_url in result",
                    })
                    continue

                token = download_and_extract(zip_url, file_output_dir, base_name, local_path, args.verbose)
                results.append({
                    "input": local_path,
                    "output_dir": str(file_output_dir),
                    "markdown_file": str(file_output_dir / f"{base_name}.md"),
                    "images_dir": str(file_output_dir / f"{token}.images"),
                    "state": "done",
                    "error": None,
                })
        except MinerUError as e:
            # Whole chunk failed
            for local_path in chunk:
                failed.append({
                    "input": local_path,
                    "error": str(e),
                })
        except requests.RequestException as e:
            for local_path in chunk:
                failed.append({
                    "input": local_path,
                    "error": f"Network error: {e}",
                })

    return results, failed


def process_url(file_url: str, output_dir: Path, token: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Process a single remote URL."""
    results: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    try:
        task_id = submit_url_task(file_url, token, args)
        result = poll_url_task(task_id, token, args)
        zip_url = result.get("full_zip_url")
        if not zip_url:
            raise OutputError("No full_zip_url in task result")

        base_name = make_base_name(file_url)
        file_output_dir = output_dir / base_name
        file_output_dir.mkdir(parents=True, exist_ok=True)

        token = download_and_extract(zip_url, file_output_dir, base_name, file_url, args.verbose)
        results.append({
            "input": file_url,
            "output_dir": str(file_output_dir),
            "markdown_file": str(file_output_dir / f"{base_name}.md"),
            "images_dir": str(file_output_dir / f"{token}.images"),
            "state": "done",
            "error": None,
        })
    except MinerUError as e:
        failed.append({
            "input": file_url,
            "error": str(e),
        })
    except requests.RequestException as e:
        failed.append({
            "input": file_url,
            "error": f"Network error: {e}",
        })

    return results, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert documents to Markdown using MinerU cloud API.",
    )
    parser.add_argument("input", help="Input file, directory, or URL")
    parser.add_argument("--output-dir", "-o", default=None, help="Output directory (default: 00-收件箱/PDF解析/<file_stem>)")
    parser.add_argument("--token", default=None, help="MinerU API token (overrides env var)")
    parser.add_argument(
        "--model-version",
        default="vlm",
        choices=["pipeline", "vlm", "MinerU-HTML"],
        help="Extraction model version (default: vlm)",
    )
    parser.add_argument("--is-ocr", action="store_true", help="Enable OCR mode")
    parser.add_argument(
        "--enable-formula",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable formula recognition (default: on)",
    )
    parser.add_argument(
        "--enable-table",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable table recognition (default: on)",
    )
    parser.add_argument("--language", default="ch", help="Document language (default: ch)")
    parser.add_argument(
        "--extra-formats",
        nargs="+",
        choices=["docx", "html", "latex"],
        help="Extra export formats besides markdown/json",
    )
    parser.add_argument("--page-ranges", help="Page ranges to process, e.g. '1-5,7,10-12'")
    parser.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds (default: 5)")
    parser.add_argument("--timeout", type=int, default=600, help="Max polling timeout in seconds (default: 600)")
    parser.add_argument("--no-cache", action="store_true", help="Bypass MinerU server-side cache")
    parser.add_argument("--cache-tolerance", type=int, default=None, help="Cache tolerance in seconds")
    parser.add_argument("--data-id", help="Custom business data ID")
    parser.add_argument("--callback", help="Callback URL for push notifications")
    parser.add_argument("--seed", help="Random seed string for callback signature")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output to stderr")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        token = get_api_token(args)
        parent_output_dir = resolve_output_dir(args.input, args.output_dir).resolve()
        parent_output_dir.mkdir(parents=True, exist_ok=True)
        log(f"Using parent output directory: {parent_output_dir}", args.verbose)

        if is_url(args.input):
            results, failed = process_url(args.input, parent_output_dir, token, args)
        else:
            file_paths = collect_local_files(args.input)
            log(f"Found {len(file_paths)} file(s) to process", args.verbose)
            results, failed = process_local_files(file_paths, parent_output_dir, token, args)

        result_json = {
            "success": len(failed) == 0,
            "results": results,
            "failed": failed,
        }
        print(json.dumps(result_json, ensure_ascii=False, indent=2))

        if failed:
            return 4 if all("failed" in f.get("error", "").lower() for f in failed) else 2
        return 0

    except MinerUError as e:
        log(f"ERROR: {e.message}", verbose=True)
        result_json = {
            "success": False,
            "results": [],
            "failed": [{"input": args.input, "error": e.message}],
        }
        print(json.dumps(result_json, ensure_ascii=False, indent=2))
        return e.exit_code
    except requests.RequestException as e:
        log(f"ERROR: Network error: {e}", verbose=True)
        result_json = {
            "success": False,
            "results": [],
            "failed": [{"input": args.input, "error": f"Network error: {e}"}],
        }
        print(json.dumps(result_json, ensure_ascii=False, indent=2))
        return 3
    except Exception as e:
        log(f"ERROR: Unexpected error: {e}", verbose=True)
        result_json = {
            "success": False,
            "results": [],
            "failed": [{"input": args.input, "error": f"Unexpected error: {e}"}],
        }
        print(json.dumps(result_json, ensure_ascii=False, indent=2))
        return 5


if __name__ == "__main__":
    sys.exit(main())
