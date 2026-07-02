---
name: mineru-parse
description: Call the MinerU cloud precise parsing API to convert local documents or remote URLs into Markdown and image directories. Use this skill when the user says "mineru parse", "mineru 解析", "MinerU 转换", "parse PDF with MinerU", "mineru-parse", or when high-quality OCR/layout/formula/table extraction is needed for scanned or complex documents.
source: internal
---

# MinerU Parse

Convert documents (PDF, images, Office files, HTML) into clean Markdown and an `images/` directory using the [MinerU](https://mineru.net) cloud precise parsing API.

## When to Use This Skill

**MinerU 是本 vault 的唯一 PDF 抽取路径**——无论 ingest 流程还是独立调用，任何 PDF/文档转 Markdown 一律用本技能，不再使用 `pdf-to-markdown`。

**USE THIS** when:

- Any PDF/document needs to be converted to Markdown (ingest workflow or standalone)
- The document is scanned, has complex tables, formulas, or multi-column layouts
- User explicitly mentions MinerU, e.g.:
  - "用 MinerU 解析这个 PDF"
  - "mineru 解析"
  - "mineru-parse"
  - "MinerU 转换"
  - "parse PDF with MinerU"

> `MINERU_API_TOKEN` 缺失或网络不可用时，**停止并报告用户**，不静默回退到本地抽取。

## Prerequisites

1. A MinerU API token from [https://mineru.net/apiManage](https://mineru.net/apiManage).
2. Set the token as an environment variable:
   ```powershell
   $env:MINERU_API_TOKEN = "your_token_here"
   ```
   Or on Git Bash / WSL:
   ```bash
   export MINERU_API_TOKEN="your_token_here"
   ```

## Installation

This skill uses a dedicated virtual environment at `.claude/skills/mineru-parse/.venv/`.

### First-Time Setup

```bash
cd "E:/wiki/nongbaoyun/.claude/skills/mineru-parse" && uv venv .venv && uv pip install --python .venv/Scripts/python -r requirements.txt
```

### Verify Installation

```bash
.claude/skills/mineru-parse/.venv/Scripts/python.exe -c "import requests; print('OK')"
```

## Quick Start

```bash
# Single local file (default output: 00-收件箱/PDF解析/document/)
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "00-收件箱/document.pdf"

# Local directory (batch)
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "00-收件箱/batch/"

# Remote URL
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "https://example.com/report.pdf"

# Custom output directory
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "00-收件箱/document.pdf" --output-dir "20-知识库/04-来源/20260701-document"
```

## Usage

```text
mineru_parse.py <input> [--output-dir <dir>] [options]
```

### Positional Argument

| Argument | Description |
|---|---|
| `input` | Local file path, local directory, or a single remote URL (`http://` / `https://`). |

### Output Directory

- If `--output-dir` is provided, it is used as the **parent directory**. Each document gets a sub-directory named after its stem.
- If omitted, the parent directory is `00-收件箱/PDF解析/`.

Final output layout:

| Input | Final directory | Markdown file | Images directory |
|---|---|---|---|
| Single file `document.pdf` | `00-收件箱/PDF解析/document/` | `document.md` | `document.images/` |
| URL `https://example.com/file.pdf` | `00-收件箱/PDF解析/file/` | `file.md` | `file.images/` |
| Directory `batch/` | `00-收件箱/PDF解析/<stem1>/`, `00-收件箱/PDF解析/<stem2>/`, ... | `<stem>.md` | `<stem>.images/` |

### Options

| Option | Default | Description |
|---|---|---|
| `--output-dir`, `-o` | `00-收件箱/PDF解析/` | Parent output directory. Each document gets a sub-directory named after its stem. |
| `--token` | env var | MinerU API token. Overrides `MINERU_API_TOKEN`. |
| `--model-version` | `vlm` | `pipeline` / `vlm` / `MinerU-HTML`. Use `vlm` for best accuracy. Use `MinerU-HTML` only for HTML input. |
| `--is-ocr` | disabled | Enable OCR. **Strongly recommended for scanned documents.** |
| `--enable-formula` | enabled | Enable formula recognition. Use `--no-enable-formula` to disable. |
| `--enable-table` | enabled | Enable table recognition. Use `--no-enable-table` to disable. |
| `--language` | `ch` | Document language. See MinerU docs for supported values. |
| `--extra-formats` | none | Extra export formats: `docx`, `html`, `latex`. Can specify multiple. |
| `--page-ranges` | none | Page ranges, e.g. `"1-5,7,10-12"`. |
| `--poll-interval` | `5` | Seconds between status polls. |
| `--timeout` | `600` | Maximum seconds to wait for extraction. |
| `--no-cache` | disabled | Bypass MinerU server-side cache. |
| `--cache-tolerance` | server default | Cache tolerance in seconds. |
| `--data-id` | none | Custom business ID for tracking. |
| `--callback` / `--seed` | none | Callback URL and signature seed for push notifications. |
| `-v`, `--verbose` | disabled | Print detailed progress to stderr. |

### Examples

```bash
# Scanned PDF with OCR
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "00-收件箱/scan.pdf" --output-dir "20-知识库/04-来源/scan" --is-ocr --model-version vlm

# Office document with extra docx export
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "00-收件箱/report.docx" --output-dir "20-知识库/04-来源/report" --extra-formats docx

# Single URL
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "https://example.com/file.pdf" --output-dir "20-知识库/04-来源/url-file" --model-version vlm
```

## Output Format

For a single file or URL:

```text
<output-parent>/
└── <document_stem>/
    ├── <document_stem>.md
    └── images/                     # plain relative images directory
        ├── page_001.png
        ├── figure_002.png
        └── ...
```

For a directory batch:

```text
<output-parent>/
├── document1/
│   ├── document1.md
│   └── images/
└── document2/
    ├── document2.md
    └── images/
```

The markdown file uses **relative** image references (e.g. `![图 1](images/figure_002.png)`), so the whole directory can be moved as a unit without rewriting links.

The markdown file includes YAML frontmatter:

```yaml
---
title: 全文·<document_stem>
source_pdf: <input_path_or_url>
type: fulltext
extracted_by: mineru
extracted_date: 2026-07-01
extraction_quality: unverified
---
```

Images are referenced with relative paths and numbered captions:

```markdown
![图 1](20260701_143052_a1b2.images/20260701_143052_a1b2_001.png)
```

The image directory token (`YYYYMMDD_HHMMSS_xxxx`) is globally unique so that image folders can later be moved to a centralized archive location without name collisions.

```json
{
  "success": true,
  "results": [
    {
      "input": "00-收件箱/document.pdf",
      "output_dir": "00-收件箱/PDF解析/document",
      "markdown_file": "00-收件箱/PDF解析/document/document.md",
      "images_dir": "00-收件箱/PDF解析/document/document.images",
      "state": "done",
      "error": null
    }
  ],
  "failed": []
}
```

Human-readable logs go to **stderr**.

## Integration with llm-wiki-ingest

`llm-wiki-ingest` uses this skill as **the primary (and only) PDF extraction path** — every PDF dropped into `00-收件箱/` is parsed via MinerU (no local `pdf-to-markdown` fallback):

```bash
.claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "<pdf-path>" --is-ocr --enable-formula --enable-table --model-version vlm
```

Then parse the stdout JSON, read `results[].markdown_file` / `results[].images_dir`, and migrate them into the vault archive (see `llm-wiki-ingest` steps 3–4b). If the exit code is non-zero, ingest stops and reports to the user rather than silently degrading.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All inputs processed successfully |
| 1 | CLI argument error or missing token |
| 2 | MinerU API returned 4xx/5xx |
| 3 | Network timeout or connection failure |
| 4 | MinerU reported extraction failure |
| 5 | Output processing error (zip corrupt, missing `full.md`, etc.) |

## Troubleshooting

### "Missing MINERU_API_TOKEN"

Set the environment variable before running:

```powershell
$env:MINERU_API_TOKEN = "your_token"
```

### "No module named requests"

Recreate the virtual environment:

```bash
cd "E:/wiki/nongbaoyun/.claude/skills/mineru-parse" && rm -rf .venv && uv venv .venv && uv pip install --python .venv/Scripts/python -r requirements.txt
```

### "任务失败" / `state: failed`

Check `err_msg` in the JSON output. Common causes:

- Unsupported file format
- File exceeds 200 MB or 200 pages
- Foreign URL (GitHub/AWS) times out
- Invalid token

### 输出为空或图片丢失

Ensure `--output-dir` is writable and has enough disk space. The script keeps MinerU's original `images/` structure; if images are missing, check `full.md` for broken relative references.
