#!/usr/bin/env python3
"""
finalize_ingest.py

将 mineru-parse 抽取产物整理到 vault 归档位：
- 全文 md 落到 10-原始资料/{分类}/YYYYMMDD-原标题.md
- 原始 PDF 和 图片目录 落到 10-原始资料/99-PDF原件/{分类}/YYYYMMDD-原标题/ 下（按篇隔离）
- md 内图片相对引用 images/x.jpg 改写为指向 99-PDF原件 的 Obsidian wikilink

用法：
  python finalize_ingest.py --stem <PDF文件名去扩展名> \
      --category <7类之一> --name <YYYYMMDD-原标题> --title <原标题> \
      [--quality good|partial] [--images auto|keep|drop] [--vault-root <path>]
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


def fail(msg: str, code: int = 1):
    print(json.dumps({"success": False, "error": msg}, ensure_ascii=False, indent=2))
    sys.exit(code)


def main() -> int:
    ap = argparse.ArgumentParser(description="Finalize mineru ingest into vault archive.")
    ap.add_argument("--stem", required=True, help="PDF 文件名去扩展名（= 解析子目录名 / 原 PDF 名）")
    ap.add_argument("--category", required=True, help="7 类之一，如 03-行业报告")
    ap.add_argument("--name", required=True, help="归档基名 YYYYMMDD-原标题")
    ap.add_argument("--title", required=True, help="原标题（用于 frontmatter title 全文·原标题）")
    ap.add_argument("--quality", default="good", choices=["good", "partial"],
                    help="LLM 校验后的抽取质量（默认 good）")
    ap.add_argument("--images", default="auto", choices=["auto", "keep", "drop"],
                    help="图片处理：auto=md有引用则保留并改写/无引用则删；keep=保留并改写；drop=删除")
    ap.add_argument("--vault-root", default=".", help="vault 根目录（默认当前目录）")
    args = ap.parse_args()

    if args.category not in CATEGORIES:
        fail(f"未知分类 {args.category!r}，应为 7 类之一：{sorted(CATEGORIES)}")

    root = Path(args.vault_root).resolve()
    stem, cat, name, title = args.stem, args.category, args.name, args.title

    parsed_dir = root / "00-收件箱" / "PDF解析" / stem
    src_md = parsed_dir / f"{stem}.md"
    src_pdf = root / "00-收件箱" / f"{stem}.pdf"
    src_images = parsed_dir / "images"

    md_dst_dir = root / "10-原始资料" / cat
    archive_dir = root / "10-原始资料" / "99-PDF原件" / cat / name
    archive_pdf = archive_dir / f"{name}.pdf"
    archive_images = archive_dir / "images"
    md_dst = md_dst_dir / f"{name}.md"

    # --- 前置校验 ---
    if not src_md.exists():
        fail(f"未找到全文 md：{src_md}")
    if not src_pdf.exists():
        fail(f"未找到原始 PDF：{src_pdf}")
    for p in (md_dst, archive_dir):
        if p.exists():
            fail(f"目标已存在，拒绝覆盖：{p.relative_to(root)}（请先清理或换 name）")

    text = src_md.read_text(encoding="utf-8")

    # --- 图片处理 ---
    image_files = [f for f in src_images.iterdir() if f.is_file()] if src_images.exists() else []
    ref_count = len(re.findall(r'!\[[^\]]*\]\(images/[^)]+\)', text))
    orphan_dropped = 0
    keep_images = False

    if args.images == "keep":
        keep_images = bool(image_files)
    elif args.images == "drop":
        keep_images = False
    else:  # auto
        keep_images = ref_count > 0 and bool(image_files)

    if keep_images:
        md_dst_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_images.mkdir(parents=True, exist_ok=True)
        for f in image_files:
            shutil.copy2(f, archive_images / f.name)
        # 改写 md 内图片引用：![..](images/x) -> ![[10-原始资料/99-PDF原件/{cat}/{name}/images/x]]
        # wikilink 不需要 alt 文本，直接指向图片路径
        text = re.sub(
            r'!\[[^\]]*\]\(images/([^)]+)\)',
            lambda m: f'![[10-原始资料/99-PDF原件/{cat}/{name}/images/{m.group(1)}]]',
            text
        )
    else:
        if src_images.exists():
            orphan_dropped = len(image_files)
            shutil.rmtree(src_images)

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
    fm = set_field(fm, "source_pdf", f"10-原始资料/99-PDF原件/{cat}/{name}/{name}.pdf")
    fm = set_field(fm, "extraction_quality", args.quality)
    fm = set_field(fm, "extracted_by", "mineru")

    # --- 原始资料索引 ---
    index_line = f"\n> 📎 **原始资料**：[[10-原始资料/99-PDF原件/{cat}/{name}/{name}.pdf]]\n"
    body = parts[2]
    text = "---\n" + fm + "---\n" + index_line + body

    # --- 落盘 ---
    md_dst_dir.mkdir(parents=True, exist_ok=True)
    md_dst.write_text(text, encoding="utf-8")

    archive_dir.mkdir(parents=True, exist_ok=True)
    src_pdf.rename(archive_pdf)

    # 清理解析目录
    leftover = [p.name for p in parsed_dir.iterdir()] if parsed_dir.exists() else []
    if parsed_dir.exists():
        shutil.rmtree(parsed_dir)

    images_result = f"10-原始资料/99-PDF原件/{cat}/{name}/images" if keep_images and archive_images.exists() else None

    result = {
        "success": True,
        "pdf": f"10-原始资料/99-PDF原件/{cat}/{name}/{name}.pdf",
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
