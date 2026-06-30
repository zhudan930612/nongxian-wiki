---
name: llm-wiki-lint
description: Use this skill when the user asks for a knowledge base health check, audit, or maintenance review in an LLM Wiki vault. Trigger phrases include "检查", "lint", "审计", "健康检查", "整理知识库", "清理知识库", "检查孤立页面", "检查矛盾", or similar.
---

# LLM Wiki Lint Skill

## When to Use

Use this skill when the user wants to perform a periodic health check on an LLM Wiki vault. This includes checking for contradictions, outdated claims, orphan pages, missing concepts, broken links, and suggesting improvements.

Common trigger phrases:
- "检查"
- "lint"
- "审计知识库"
- "健康检查"
- "整理知识库"
- "清理知识库"
- "检查孤立页面"
- "检查矛盾"
- "检查过时内容"

Always read `CLAUDE.md` first if it exists, as it may override this skill. See `CLAUDE.md` for schema, naming, path rules, and file operation conventions.

## Lint Workflow

### 1. Read the Knowledge Base Overview

Start by reading `20-知识库/00-索引/index.md` and `20-知识库/00-索引/stats.md` to understand the current scope and structure.

### 2. Scan Pages

List all pages in `20-知识库/` (excluding `00-索引/` system files):

- `01-实体/`
- `02-概念/`
- `03-主题/`
- `04-来源/`
- `05-问答/`
- `06-元/`

Use Glob to discover files efficiently.

### 3. Check for Contradictions

Read concept and theme pages and compare them with recent source pages.

Look for:
- Claims in one page that contradict claims in another
- New evidence from source pages that overturns older conclusions
- Inconsistent definitions of the same concept

Report specific contradictions with page paths and suggested resolutions.

### 4. Check for Outdated Claims

Identify content that may no longer be accurate:

- Old policy references that have been superseded
- Outdated statistics
- Deprecated terminology
- Source pages with old dates that may need re-evaluation

### 5. Check for Orphan Pages

Find pages with no inbound wiki links:

- Read each page's content
- Search the vault for `[[page-name]]` references
- If a page is never linked, flag it as orphan
- Suggest where it should be linked from, or whether it should be removed

### 6. Check for Missing Concept Pages

Scan pages for wiki links that point to non-existent pages:

- Extract all `[[...]]` links
- Check if the target file exists
- If a concept is referenced frequently but has no page, suggest creating it in `02-概念/`

### 7. Check Cross-Reference Completeness

Verify that related pages reference each other appropriately:

- Source pages should link to relevant entities, concepts, and themes
- Concept pages should link to related concepts and sources
- Theme pages should link to relevant concepts and sources

### 8. Check File Naming and Frontmatter

Verify consistency:

- All pages have required YAML frontmatter (`title`, `created`, `updated`, `tags`)
- File names follow the vault's naming convention
- Page titles (h1) are in Chinese where required
- **文件名日期检查**：文件名中的 `YYYYMMDD` 前缀应与 frontmatter 中的 `created` 日期一致，而非文档自带的 `published` 或其他日期。若不一致则标记为违规。

### 9. Check Raw Materials Integrity

Verify that every source page in `20-知识库/04-来源/` has a corresponding raw material in `10-原始资料/` and that the `source` path in frontmatter is correct.

Also check that no raw materials exist without corresponding source pages (unless intentionally excluded).

### 9a. Check Source Page Classification Integrity

#### 9a-1. Verify Classification Consistency

Verify that every source page in `20-知识库/04-来源/` is placed in the correct subdirectory, matching its `10-原始资料/` category:

1. Traverse `20-知识库/04-来源/` subdirectories
2. For each `.md` file, read the `source:` field from YAML frontmatter
3. Extract the raw-material category from the path (e.g., `10-原始资料/06-媒体报道/xxx.pdf` → `06-媒体报道`)
4. Compare with the actual subdirectory name in `04-来源/` (e.g., `04-来源/06-媒体报道/xxx.md`)
5. Flag any mismatch:
   - `source:` points to `10-原始资料/06-媒体报道/` but file is in `04-来源/04-技术规范/` → **miscategorized**, suggest moving to correct subdir
   - `source:` is missing or doesn't contain a valid category → **uncategorizable**, flag for manual review

Also check for files in `04-来源/` root (not in any subdirectory) and flag them as **uncategorized**.

#### 9a-2. Suggest Subdirectory Splits for Overgrown Folders

For each subdirectory in `20-知识库/04-来源/`, count the number of `.md` files. Apply these thresholds:

| Count | Status | Action |
|-------|--------|--------|
| ≤ 30 | ✅ 健康 | 无需操作 |
| 31–50 | ⚠️ 偏大 | 建议关注，考虑是否需要拆分 |
| 51–100 | 🔶 过大 | 建议规划拆分方案 |
| > 100 | 🔴 拥挤 | 必须拆分 |

When a folder exceeds a threshold, analyze the contents to propose a natural split:

1. **Scan existing implicit categories** — Read the files' topics, sources, and tags to identify natural groupings (e.g., `06-媒体报道/` could split into `实务经验/`, `政策解读/`, `技术方案/`, `学术观点/`).
2. **Check against `10-原始资料/` structure** — See if the raw materials already imply a finer classification that the source pages don't reflect.
3. **Propose the split** — Suggest specific subdirectory names, file counts per new subdir, and the migration steps (move files + update index links).
4. **Honor user decision** — Present the proposal clearly and let the user approve before executing.

> 当前状态参考（`04-来源/`）：
> - `01-政策法规/` — 2 ✅
> - `02-学术论文/` — 17 ✅
> - `03-行业报告/` — 5 ✅
> - `04-技术规范/` — 11 ✅
> - `05-产品与公司/` — 4 ✅
> - **`06-媒体报道/` — 83 🔶**
> - `07-会议沟通/` — 32 ⚠️

After confirming corrections, rebuild the `04-来源/` index in `index.md` to ensure all wiki links include the subdirectory prefix.

### 10. Generate Lint Report

Create or update a report page, typically in `20-知识库/06-元/` or append to `20-知识库/00-索引/log.md`.

Report structure:

```markdown
# 知识库健康检查报告

检查时间：YYYY-MM-DD

## 摘要

- 检查页面总数：N
- 发现问题数：N
- 高风险问题：N
- 建议操作：N

## 详细发现

### 1. 矛盾

- [[page-a]] 与 [[page-b]] 在 XXX 上存在矛盾
  - 建议：...

### 2. 过时主张

- [[page-c]] 中引用的 YYY 政策已更新
  - 建议：...

### 3. 孤立页面

- [[page-d]] 无入站链接
  - 建议：...

### 4. 缺失概念

- [[02-缺失概念]] 被多次引用但页面不存在
  - 建议：...

### 5. 引用不完整

- [[page-e]] 应链接到 [[page-f]]
  - 建议：...

## 后续建议

1. ...
2. ...
```

### 11. Update Stats (Optional)

If `20-知识库/00-索引/stats.md` has a "最后检查" field, update it to the current date.

### 12. Log the Operation

Append a summary entry to `20-知识库/00-索引/log.md`.

## Lint Frequency

Recommend running this check:
- After every 5–10 ingests
- Before major reviews or exports
- When the user explicitly requests it

## Example

User: "检查知识库"

LLM:
1. Read `index.md` and `stats.md`
2. Glob all knowledge-base pages
3. Check for contradictions between recent sources and older concept pages
4. Identify orphan pages
5. Find missing concept pages from frequent wiki links
6. Generate a lint report
7. Update "最后检查" date in stats
8. Append operation to log
9. Present findings to user with prioritized action items
