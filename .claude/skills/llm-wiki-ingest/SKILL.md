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

## Vault Structure Assumptions

This skill assumes the vault follows the LLM Wiki pattern:

```
vault-root/
├── CLAUDE.md              # Schema and workflow definition
├── 00-收件箱/              # Inbox: only entry point for new materials
├── 10-原始资料/            # Raw materials (read-only after ingest)
│   ├── 01-文章/            # Web articles / blog posts
│   ├── 02-论文/            # Academic papers
│   └── 03-资源/            # Reports / policies / data / images
└── 20-知识库/              # LLM-maintained knowledge base
    ├── 00-索引/
    │   ├── index.md
    │   ├── log.md
    │   └── stats.md
    ├── 01-实体/            # People / organizations
    ├── 02-概念/            # Concepts / definitions
    ├── 03-主题/            # Themes / synthesis
    ├── 04-来源/            # Source summaries
    ├── 05-问答/            # Archived Q&A
    └── 06-元/              # Meta: todos, templates
```

Always read `CLAUDE.md` first if it exists, as it may override this skill.

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

**Classification boundary rule**: If a file clearly does not fit the existing three categories (e.g., audio, video, special-format datasets, interview transcripts), pause and ask the user whether to add a new category. Do not create new folders like `04-XX/` without user confirmation, and do not temporarily misfile materials.

### 5. Discuss Key Points with User

Briefly summarize the material's core claims, methods, and conclusions, and confirm the user's focus areas before creating pages.

### 6. Create Source Summary Page

Create a Markdown summary page in `20-知识库/04-来源/` with the same base name as the raw material.

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

### 7. Update Entity Pages

Create or update pages in `20-知识库/01-实体/` for relevant people, organizations, or locations.

### 8. Update Concept Pages

Create or update pages in `20-知识库/02-概念/` for key concepts, definitions, or methodologies.

### 9. Update Theme Pages (if needed)

Create or update pages in `20-知识库/03-主题/` for cross-cutting synthesis.

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

## Naming Conventions

- Directory names at levels 1–2 use Chinese with `XX-` sorting prefix
- Raw material files: `YYYYMMDD-原标题.扩展名`
- Knowledge-base source pages: same base name as raw material, `.md`
- Entity / concept / theme pages: use the existing vault naming style
- Page titles (h1): Chinese

## Link Style

- Internal links: `[[页面名]]` or `[[路径/页面]]`
- Source pages in index: `[[04-来源/YYYY-MM-DD-标题]]`
- External links: `[text](url)`

## Path Rules

- Use relative paths from the vault root
- Do not use absolute paths or leading slashes for vault operations
- `10-原始资料/` is read-only after ingest
- `20-知识库/` is maintained by the LLM

## Iteration Principle

First-pass pages do not need to be exhaustive. Create concise summaries and refine them as the knowledge base grows.

## Example

User: "处理收件箱"

LLM:
1. Read all files in `00-收件箱/`
2. Check for duplicates in `10-原始资料/` and `20-知识库/04-来源/`
3. Verify each PDF has extractable text
4. Move PDFs to `10-原始资料/01-文章/`, `02-论文/`, or `03-资源/`
5. Create source summary pages in `20-知识库/04-来源/`
6. Update entity/concept/theme pages as needed
7. Update `index.md`, `log.md`, `stats.md`
8. Remove processed files from `00-收件箱/`
9. Report summary to user
