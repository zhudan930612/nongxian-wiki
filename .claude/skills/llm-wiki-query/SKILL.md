---
name: llm-wiki-query
description: Use this skill when the user asks questions about the knowledge base and wants the LLM to search, synthesize, and answer with citations from the LLM Wiki vault. Trigger phrases include "查询", "查找", "搜索", "告诉我关于", or similar.
---

# LLM Wiki Query Skill

## When to Use

Use this skill when the user asks a question about the knowledge base content and expects a comprehensive, cited answer.

Common trigger phrases:
- "查询..."
- "查找关于..."
- "搜索..."
- "告诉我关于..."
- "有什么关于..."
- "整理一下关于..."
- "分析..."
- "解释..."

Always read `CLAUDE.md` first if it exists, as it may override this skill. See `CLAUDE.md` for the page schema, naming conventions, and metadata fields.

## Query Workflow

Execute the following steps in order.

### 1. Read the Knowledge Base Overview

Read `20-知识库/00-索引/index.md` to understand the full scope and structure of the vault.

### 2. Search and Gather Relevant Pages

a. **Full-text search + index.md lookup** to find directly relevant pages
b. **Knowledge graph assisted search**: Identify entities in the question → look up `20-知识库/00-索引/knowledge-graph.md` for connections → traverse relationship types → discover indirectly related pages

### 3. Synthesize Answer with Citations

Provide a comprehensive answer using Wiki links as citations:
- Use `[[20-知识库/02-概念/llm-wiki|display text]]` format
- Reference raw materials by YYYY-MM-DD date where relevant
- Cite specific page titles and sections

### 4. Crystallization Check

After answering, automatically evaluate whether the response deserves archival in `20-知识库/05-问答/`.

**Trigger conditions** (any one suffices):
- Answer involves cross-referencing **3+** different sources
- Answer contains conclusions **not covered** by existing pages
- Answer relates to a **key project decision**
- Same type of question asked **multiple times** (auto-detect frequency)

### 5. Crystallization Flow (Only When Triggered)

a. **Create Q&A archive page**: `20-知识库/05-问答/YYYYMMDD-标题.md`
   - Frontmatter includes `crystallized_from`, `confidence`, `status` and other metadata fields
   - Body records the question and comprehensive answer
b. **Extract atomic facts** into a `## 待确认事实` section
c. Incrementally update `source_count`, `cross_references`, `last_confirmed` on affected pages
d. Update `20-知识库/00-索引/index.md` and `20-知识库/00-索引/log.md`

## Example

User: "查询农险遥感相关政策"

LLM:
1. Read `index.md` for vault overview
2. Search for "农险", "遥感", "政策" across pages
3. Look up entities in `knowledge-graph.md` to find related organizations and policies
4. Synthesize answer with Wiki link citations
5. Evaluate crystallization: if answer covers 3+ policies with cross-analysis, archive as Q&A
6. Report summary with source links
