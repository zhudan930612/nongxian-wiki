#!/usr/bin/env python3
"""
recompute_stats.py

从 vault 文件系统真实计数，重算并原地更新 20-知识库/00-索引/stats.md 表格，
纠正手工增减导致的漂移。仅用标准库。

用法：
  python recompute_stats.py [--ingest-date YYYY-MM-DD] [--vault-root <path>] [--dry-run]

计数口径（在此明确，避免歧义）：
- 实体数   20-知识库/01-实体/**/01-*.md
- 概念数   20-知识库/02-概念/**/02-*.md
- 主题数   20-知识库/03-主题/**/03-*.md
- 来源数   20-知识库/04-来源/**/*.md
- 问答数   20-知识库/05-问答/**/*.md
- 总页面数 20-知识库/**/*.md（含 00-索引/06-元 等所有 md）
- 原始资料数 = 10-原始资料/**/*.pdf 数 + 10-原始资料/{7类}/**/*.md 中 type!=fulltext 的数
- 知识图谱关系数 = knowledge-graph.md 中 "- source:" 行数
- 待创建实体/概念（灰色链接）= 全库 [[01-实体/01-X]] / [[02-概念/02-X]] 去重后目标 md 不存在的数量
- 平均置信度 = 所有含 confidence 字段页面的均值（2 位小数）
- 取代事件数 = superseded_by 非空的页面数
保留不动：最后检查（lint 维护）、孤立实体数。最后摄取仅在 --ingest-date 传入时更新。
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

CATEGORIES = [
    "01-政策法规", "02-学术论文", "03-行业报告", "04-技术规范",
    "05-产品与公司", "06-媒体报道", "07-会议沟通",
]

LINK_RE = re.compile(r'\[\[(01-实体/01-[^\]|#]+|02-概念/02-[^\]|#]+)(?:[|#][^\]]*)?\]\]')
CONF_RE = re.compile(r'^confidence:\s*([0-9]*\.?[0-9]+)\s*$', re.MULTILINE)


def frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---\n", 2)
    return parts[1] if len(parts) == 3 else ""


def has_fulltext_type(text: str) -> bool:
    fm = frontmatter(text)
    return bool(re.search(r'^type:\s*fulltext\s*$', fm, re.MULTILINE))


def has_superseded(text: str) -> bool:
    fm = frontmatter(text)
    m = re.search(r'^superseded_by:\s*(.*)$', fm, re.MULTILINE)
    if not m:
        return False
    v = m.group(1).strip()
    return v not in ("", "[]", "[ ]")


def compute(root: Path) -> dict:
    kb = root / "20-知识库"
    raw = root / "10-原始资料"

    def count(glob_root: Path, pattern: str) -> int:
        return sum(1 for _ in glob_root.glob(pattern)) if glob_root.exists() else 0

    stats = {}
    stats["实体数"] = count(kb / "01-实体", "**/01-*.md")
    stats["概念数"] = count(kb / "02-概念", "**/02-*.md")
    stats["主题数"] = count(kb / "03-主题", "**/03-*.md")
    stats["来源数"] = count(kb / "04-来源", "**/*.md")
    stats["问答数"] = count(kb / "05-问答", "**/*.md")
    stats["总页面数"] = count(kb, "**/*.md")

    # 原始资料数
    pdfs = count(raw, "**/*.pdf")
    text_md = 0
    for c in CATEGORIES:
        d = raw / c
        if not d.exists():
            continue
        for f in d.glob("**/*.md"):
            try:
                if not has_fulltext_type(f.read_text(encoding="utf-8", errors="ignore")):
                    text_md += 1
            except OSError:
                pass
    stats["原始资料数"] = pdfs + text_md

    # 知识图谱关系数
    kg = kb / "00-索引" / "knowledge-graph.md"
    if kg.exists():
        stats["知识图谱关系数"] = len(re.findall(r'^\s*- source:', kg.read_text(encoding="utf-8"), re.MULTILINE))
    else:
        stats["知识图谱关系数"] = 0

    # 灰色链接 + 平均置信度 + 取代事件
    ent_targets, con_targets = set(), set()
    conf_vals = []
    superseded = 0
    for f in kb.glob("**/*.md"):
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for tgt in LINK_RE.findall(t):
            (ent_targets if tgt.startswith("01-实体/") else con_targets).add(tgt)
        m = CONF_RE.search(frontmatter(t))
        if m:
            conf_vals.append(float(m.group(1)))
        if has_superseded(t):
            superseded += 1

    def missing(targets: set) -> int:
        return sum(1 for tgt in targets if not (kb / f"{tgt}.md").exists())

    stats["待创建实体（灰色链接）"] = missing(ent_targets)
    stats["待创建概念（灰色链接）"] = missing(con_targets)
    stats["平均置信度"] = round(sum(conf_vals) / len(conf_vals), 2) if conf_vals else 0.0
    stats["取代事件数"] = superseded
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Recompute vault stats from filesystem.")
    ap.add_argument("--ingest-date", default=None, help="若传入则更新『最后摄取』与 frontmatter updated")
    ap.add_argument("--vault-root", default=".")
    ap.add_argument("--dry-run", action="store_true", help="只打印对比，不写回")
    args = ap.parse_args()

    root = Path(args.vault_root).resolve()
    stats_path = root / "20-知识库" / "00-索引" / "stats.md"
    if not stats_path.exists():
        print(f"ERROR: 未找到 {stats_path}", file=sys.stderr)
        return 1

    new = compute(root)
    lines = stats_path.read_text(encoding="utf-8").splitlines(keepends=True)

    row_re = re.compile(r'^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$')
    changes = []
    for i, line in enumerate(lines):
        m = row_re.match(line)
        if not m:
            continue
        key = m.group(1).strip()
        old = m.group(2).strip()
        if key in new:
            newv = str(new[key])
            if old != newv:
                changes.append((key, old, newv))
            lines[i] = f"| {key} | {newv} |\n"
        elif key == "最后摄取" and args.ingest_date:
            if old != args.ingest_date:
                changes.append((key, old, args.ingest_date))
            lines[i] = f"| {key} | {args.ingest_date} |\n"

    # frontmatter updated
    upd = args.ingest_date or datetime.date.today().isoformat()
    for i, line in enumerate(lines[:10]):
        if line.startswith("updated:"):
            lines[i] = f"updated: {upd}\n"
            break

    # 输出对比
    print("=== stats 重算 before → after ===")
    if changes:
        for k, o, n in changes:
            print(f"  {k}: {o} → {n}")
    else:
        print("  （无变化，统计已是最新）")

    if args.dry_run:
        print("[dry-run] 未写回")
    else:
        stats_path.write_text("".join(lines), encoding="utf-8")
        print(f"已更新 {stats_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
