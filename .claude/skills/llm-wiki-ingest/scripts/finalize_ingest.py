#!/usr/bin/env python3
"""
finalize_ingest.py

将 mineru-parse 抽取产物（00-收件箱/PDF解析/<stem>/）连同原始 PDF 搬迁到 vault 归档位，
并完成图片目录重命名、图片引用改写、frontmatter 定稿、原始资料索引插入、空壳清理。

对应 llm-wiki-ingest SKILL 步骤 4b 的确定性实现。仅用标准库。

用法：
  python finalize_ingest.py --stem <PDF文件名去扩展名> \
      --category <7类之一> --name <YYYYMMDD-原标题> --title <原标题> \
      [--quality good|partial] [--images auto|keep|drop] [--vault-root <path>]

约定路径（均相对 vault 根）：
  解析产物   00-收件箱/PDF解析/<stem>/<stem>.md  +  <token>.images/
  原始 PDF   00-收件箱/<stem>.pdf
  归档 PDF   10-原始资料/99-PDF原件/<category>/<name>.pdf
  全文 md    10-原始资料/<category>/<name>.md
  归档图片   10-原始资料/99-PDF原件/<category>/<name>.images/
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

CATEGORIES = {
    "01-政策法规", "02-学术论文", "03-行业报告", "04-技术规范",
    "05-产品与公司", "06-媒体报道", "07-会议沟通",
}

# 匹配 mineru 产出的图片引用：![任意alt](<token>.images/<file>)
IMG_REF_RE = re.compile(r'!\[[^\]]*\]\(([0-9A-Za-z_]+\.images)/([^)]+)\)')


def fail(msg: str, code: int = 1):
    print(json.dumps({"success": False, "error": msg}, ensure_ascii=False, indent=2))
    sys.exit(code)


def find_token_images_dir(parsed_dir: Path) -> Path | None:
    """在解析目录下找形如 <token>.images 的图片目录。"""
    candidates = [d for d in parsed_dir.iterdir() if d.is_dir() and d.name.endswith(".images")]
    if not candidates:
        return None
    if len(candidates) > 1:
        fail(f"解析目录下存在多个 .images 目录，无法确定：{[c.name for c in candidates]}")
    return candidates[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Finalize mineru ingest into vault archive.")
    ap.add_argument("--stem", required=True, help="PDF 文件名去扩展名（= 解析子目录名 / 原 PDF 名）")
    ap.add_argument("--category", required=True, help="7 类之一，如 03-行业报告")
    ap.add_argument("--name", required=True, help="归档基名 YYYYMMDD-原标题")
    ap.add_argument("--title", required=True, help="原标题（用于 frontmatter title 全文·原标题）")
    ap.add_argument("--quality", default="good", choices=["good", "partial"],
                    help="LLM 校验后的抽取质量（默认 good）")
    ap.add_argument("--images", default="auto", choices=["auto", "keep", "drop"],
                    help="图片处理：auto=有引用则搬迁改写/无引用则删；keep=一律搬迁保留；drop=一律删")
    ap.add_argument("--vault-root", default=".", help="vault 根目录（默认当前目录）")
    args = ap.parse_args()

    if args.category not in CATEGORIES:
        fail(f"未知分类 {args.category!r}，应为 7 类之一：{sorted(CATEGORIES)}")

    root = Path(args.vault_root).resolve()
    stem, cat, name, title = args.stem, args.category, args.name, args.title

    parsed_dir = root / "00-收件箱" / "PDF解析" / stem
    src_md = parsed_dir / f"{stem}.md"
    src_pdf = root / "00-收件箱" / f"{stem}.pdf"

    pdf_dst_dir = root / "10-原始资料" / "99-PDF原件" / cat
    md_dst_dir = root / "10-原始资料" / cat
    pdf_dst = pdf_dst_dir / f"{name}.pdf"
    md_dst = md_dst_dir / f"{name}.md"
    images_dst = pdf_dst_dir / f"{name}.images"

    # --- 前置校验 ---
    if not src_md.exists():
        fail(f"未找到全文 md：{src_md}")
    if not src_pdf.exists():
        fail(f"未找到原始 PDF：{src_pdf}")
    # 防覆盖
    for p in (pdf_dst, md_dst, images_dst):
        if p.exists():
            fail(f"目标已存在，拒绝覆盖：{p.relative_to(root)}（请先清理或换 name）")

    pdf_dst_dir.mkdir(parents=True, exist_ok=True)
    md_dst_dir.mkdir(parents=True, exist_ok=True)

    text = src_md.read_text(encoding="utf-8")

    # --- 图片处理 ---
    token_dir = find_token_images_dir(parsed_dir)
    ref_matches = IMG_REF_RE.findall(text)          # [(dir, file), ...]
    ref_count = len(ref_matches)
    images_dir_files = (
        [f for f in token_dir.iterdir() if f.is_file()] if token_dir and token_dir.exists() else []
    )

    images_result = None       # 归档后的相对路径
    orphan_dropped = 0

    move_images = False
    if args.images == "keep":
        move_images = bool(images_dir_files)
    elif args.images == "drop":
        move_images = False
    else:  # auto
        move_images = ref_count > 0 and bool(images_dir_files)

    if move_images:
        token_dir.rename(images_dst)
        # 改写引用：![..](<token>.images/x) -> ![[99-PDF原件/{cat}/{name}.images/x]]
        def _sub(m):
            return f"![[99-PDF原件/{cat}/{name}.images/{m.group(2)}]]"
        text = IMG_REF_RE.sub(_sub, text)
        images_result = f"10-原始资料/99-PDF原件/{cat}/{name}.images"
    else:
        # 不搬迁：删除孤立/空目录
        if token_dir and token_dir.exists():
            orphan_dropped = len(images_dir_files)
            shutil.rmtree(token_dir)

    # --- frontmatter 改写 ---
    if not text.startswith("---"):
        fail("全文 md 缺少 frontmatter")
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        fail("frontmatter 解析失败（分隔符不足）")
    fm = parts[1]

    def set_field(fm_text: str, key: str, value: str) -> str:
        pat = re.compile(rf'^({key}:).*$', re.MULTILINE)
        if pat.search(fm_text):
            return pat.sub(rf'\1 {value}', fm_text, count=1)
        return fm_text + f"{key}: {value}\n"

    fm = set_field(fm, "title", f"全文·{title}")
    fm = set_field(fm, "source_pdf", f"10-原始资料/99-PDF原件/{cat}/{name}.pdf")
    fm = set_field(fm, "extraction_quality", args.quality)
    fm = set_field(fm, "extracted_by", "mineru")

    # --- 原始资料索引 ---
    index_line = f"\n> 📎 **原始资料**：[[99-PDF原件/{cat}/{name}.pdf]]\n"
    body = parts[2]
    text = "---\n" + fm + "---\n" + index_line + body

    # --- 落盘：先写 md，再移 PDF，最后清壳 ---
    md_dst.write_text(text, encoding="utf-8")
    src_md.unlink()
    src_pdf.rename(pdf_dst)

    # 清理空壳解析目录（此时应已无 md / 图片目录）
    leftover = [p.name for p in parsed_dir.iterdir()] if parsed_dir.exists() else []
    if parsed_dir.exists():
        shutil.rmtree(parsed_dir)

    result = {
        "success": True,
        "pdf": f"10-原始资料/99-PDF原件/{cat}/{name}.pdf",
        "fulltext_md": f"10-原始资料/{cat}/{name}.md",
        "images_dir": images_result,
        "image_refs": ref_count,
        "orphan_dropped": orphan_dropped,
        "quality": args.quality,
        "parsed_dir_leftover_before_cleanup": leftover,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
