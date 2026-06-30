---
name: llm-wiki-ingest
description: Use this skill when the user drops new materials into the 00-收件箱/ folder of an LLM Wiki vault and says "处理", "读取", "分析", "提炼", "整理", "总结", "ingest", or similar. It performs the full ingest workflow for an LLM Wiki vault structured with 10-原始资料/, 20-知识库/, and CLAUDE.md.
---

# LLM Wiki Ingest Skill

## When to Use

Use this skill when the user has placed new files in `00-收件箱/` and wants the LLM to process, classify, summarize, and integrate them into the knowledge base.

Common trigger phrases:
- "处理"
- "处理收件箱"
- "读取并整理这个文件"
- "分析这篇文章"
- "提炼核心观点"
- "总结并归档"
- "ingest"

Always read `CLAUDE.md` first if it exists, as it may override this skill. See `CLAUDE.md` for schema, naming, path rules, and file operation conventions.

## Ingest Workflow

Execute the following steps in order. If any step fails or requires a user decision, pause and ask the user before proceeding.

### 1. Read Inbox Files

- List all files in `00-收件箱/`
- Ignore `README.md` and other system files
- Read each incoming material completely
- For PDFs, extract text using `pypdf`, `pdfplumber`, or OCR (`easyocr`) if needed

### 2. Deduplication Check

Before processing each file, verify it is not already in the vault:

- Check `10-原始资料/` for files with the same or very similar name
- Check `20-知识库/04-来源/` for pages with highly similar content (title, abstract, key paragraphs)
- Check the incoming file's frontmatter `source` URL if present
- If duplicate, notify the user and skip ingestion

### 3. Content Availability Check

Confirm the material has usable body content:

- For PDFs: try text extraction / OCR. If the file has very few pages, only web frame/cover/preview pages, or no substantive text, notify the user and suggest removal. Do not create placeholder source pages.
- For web clippings: verify actual body content was captured. Reject pages that contain only navigation, ads, or loading placeholders.
- If unusable, do not migrate to `10-原始资料/`; advise deletion or replacement with a complete version.

### 4. Classify and Migrate

Classify each usable file and move it to the appropriate raw-material folder with the naming convention `YYYYMMDD-原标题.扩展名`:

- Web articles / blogs → `10-原始资料/01-文章/`
- Academic papers → `10-原始资料/02-论文/`
- Reports / policies / data / images → `10-原始资料/03-资源/`
- User notes / ideas → create or update pages directly in `20-知识库/`

**日期规则（优先级）**：
1. 文档有自身固有日期（`published` 字段、发文日、会议日期、微信公众号发表日期等）→ 文件名前缀使用该日期
2. 文档无固有日期 → 文件名前缀使用 frontmatter 中的 `created` 日期
3. 重命名前，检查目标日期+标题是否与已有文件冲突；如有冲突，在标题后添加区分标识（如序号）

**Classification boundary rule**: If a file clearly does not fit the existing three categories (e.g., audio, video, special-format datasets, interview transcripts), pause and ask the user whether to add a new category. Do not create new folders like `04-XX/` without user confirmation, and do not temporarily misfile materials.

### 5. Discuss Key Points with User

Briefly summarize the material's core claims, methods, and conclusions, and confirm the user's focus areas before creating pages.

### 6. Create Source Summary Page

Create a Markdown summary page in `20-知识库/04-来源/` with the same base name as the raw material (including the `YYYYMMDD-` prefix).

**来源页日期规则**：来源页是衍生作品无固有日期，文件名中的 `YYYYMMDD` 使用 frontmatter 中的 `created` 日期。

Page structure:

```markdown
---
title: 资料标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [source, tag1, tag2]
source: 10-原始资料/XX-分类/YYYYMMDD-原标题.扩展名
author: 作者名
---

# 资料标题

> 一句话摘要

## 核心观点

1. ...
2. ...

## 关键内容

...

## 相关实体

- [[01-实体名]]

## 相关概念

- [[02-概念名]]

## 相关主题

- [[03-主题名]]

## 来源

- 原始资料：`10-原始资料/XX-分类/YYYYMMDD-原标题.扩展名`
- 原文链接：...
- 原载：...
```

### 6a. Path Verification (Prevent Root-Level Files)

Before creating ANY new file, verify it is NOT placed in the vault root:

- ✅ Valid: `20-知识库/04-来源/01-政策法规/20260630-xxx.md`
- ❌ Invalid: `01-华宇科技.md` (at root — misplaced)
- ❌ Invalid: `任何.md` (at root — misplaced)

**规则**：知识库文件必须放在 `20-知识库/XX-分类/` 下，禁止在根目录创建 `.md` 文件。

If a file path resolves to the root level, correct it to the proper subdirectory before writing.

### 7. Reference Entity Pages (Forward References)

In the source summary page, add wiki links to relevant entities (people, organizations, locations):

- Use `[[01-实体/01-实体名]]` format (with prefix, without `20-知识库/` prefix)
- **Default**: Do NOT create the entity page during ingest — leave it as a gray link (forward reference)
- **Exception**: Only create the entity page if it is the **core topic** of this ingest AND you have sufficient information to write a meaningful page
- If creating: MUST use `20-知识库/01-实体/01-实体名.md` full path, NEVER at root

### 8. Reference Concept Pages (Forward References)

In the source summary page, add wiki links to relevant concepts (definitions, methods, theories):

- Use `[[02-概念/02-概念名]]` format
- **Default**: Do NOT create the concept page during ingest — leave it as a gray link
- **Exception**: Only create if the concept is the **core topic** of this ingest AND you have sufficient information
- If creating: MUST use `20-知识库/02-概念/02-概念名.md` full path, NEVER at root

### 9. Reference Theme Pages (Forward References)

In the source summary page, add wiki links to relevant themes (cross-cutting synthesis topics):

- Use `[[03-主题/03-主题名]]` format
- **Default**: Do NOT create the theme page during ingest — leave it as a gray link
- **Exception**: Only create if the theme is the core contribution of this ingest
- If creating: MUST use `20-知识库/03-主题/03-主题名.md` full path, NEVER at root

### 10. Update Index

Add the new source to the appropriate section of `20-知识库/00-索引/index.md`.

### 11. Append Log

Add a new entry to `20-知识库/00-索引/log.md` describing the ingest operation.

### 12. Update Statistics

Update counts in `20-知识库/00-索引/stats.md`.

### 13. Clean Up Inbox

Remove processed files from `00-收件箱/`. Keep `README.md` and any files the user explicitly wants to retain.

### 14. Update Todos

Check `20-知识库/06-元/06-todo.md` and clear or update relevant items.

## Example

User: "处理收件箱"

LLM:
1. Read all files in `00-收件箱/`
2. Check for duplicates in `10-原始资料/` and `20-知识库/04-来源/`
3. Verify each PDF has extractable text
4. Move PDFs to `10-原始资料/01-文章/`, `02-论文/`, or `03-资源/`
5. Create source summary pages in `20-知识库/04-来源/` with wiki links (forward references)
6. Update `index.md`, `log.md`, `stats.md`
7. Remove processed files from `00-收件箱/`
8. Report summary to user
