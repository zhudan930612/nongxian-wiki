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
- 识别所有 `.pdf` 文件，收集为 PDF 列表交步骤 3；PDF 的正文抽取统一在步骤 3 用 `mineru-parse` 处理（云端高精度 OCR/表格/公式），此处不重复抽取

### 2. Deduplication Check

Before processing each file, verify it is not already in the vault:

- Check `10-原始资料/` (including `10-原始资料/99-PDF原件/`) for files with the same or very similar name
- Check `20-知识库/04-来源/` for pages with highly similar content (title, abstract, key paragraphs)
- Check the incoming file's frontmatter `source` URL if present
- If duplicate, notify the user and skip ingestion

### 3. Content Availability Check (抽取即检查)

Confirm the material has usable body content:

- **For PDFs（mineru 云端抽取 + 质量校验）**：用 `mineru-parse` 技能抽取全文，产出供步骤 4b 使用。**mineru 为 PDF 唯一抽取路径，不再使用 pdf-to-markdown。**
  1. **调用 mineru**：对每个 PDF 运行（默认输出到 `00-收件箱/PDF解析/<stem>/`）：
     ```bash
     .claude/skills/mineru-parse/.venv/Scripts/python.exe .claude/skills/mineru-parse/scripts/mineru_parse.py "00-收件箱/<原PDF名>.pdf" --is-ocr --enable-formula --enable-table --model-version vlm -v
     ```
  2. **解析结果**：读脚本 stdout 的 JSON，取 `results[].markdown_file` 与 `results[].images_dir`
  3. **失败即停止（无兜底）**：退出码非 0 时按退出码报告并**停止该 PDF 的处理**，不建全文 md、不建来源页，交用户决定：
     - `1` = 缺 `MINERU_API_TOKEN` 或参数错 ｜ `2` = MinerU API 4xx/5xx ｜ `3` = 网络超时 ｜ `4` = MinerU 抽取失败 ｜ `5` = 输出处理错误
  4. **质量校验**：读产出 md，检查是否存在——内容为空、大段乱码、正文明显缺失、表格错位串行、仅封面/目录/预览页、编码异常等。不通过 → **停止并报告**具体问题，交用户决定（换更完整版本、手工修正、或接受局部），**不归档、不建来源页**
  5. **通过** → 进入步骤 4；全文 md 的 `extracted_by` 固定为 `mineru`，并据抽取效果如实标注 `extraction_quality`（good / partial）
- For web clippings: verify actual body content was captured. Reject pages that contain only navigation, ads, or loading placeholders.
- If unusable, do not migrate to `10-原始资料/`; advise deletion or replacement with a complete version.

### 4. Classify and Migrate (按类型分流)

Classify each usable file. 文件名统一用 `YYYYMMDD-原标题.扩展名`。归档路径按资料类型分流：

**分类体系（7 类，与 CLAUDE.md 一致）**：
`01-政策法规` / `02-学术论文` / `03-行业报告` / `04-技术规范` / `05-产品与公司` / `06-媒体报道` / `07-会议沟通`

**按类型处理**：

- **PDF 类**：
  1. 确定分类与 `YYYYMMDD-原标题` 命名
  2. 触发下方 **步骤 4b**，统一搬迁三件套（原始 PDF、全文 md、图片目录）到归档位并改写引用
- **文本类**（网页剪藏、会议原文、笔记等 `.md`）：原样落 `10-原始资料/{分类}/YYYYMMDD-原标题.md`，无需抽取
- **User notes / ideas**：create or update pages directly in `20-知识库/`

**日期规则（优先级）**：
1. 文档有自身固有日期（`published` 字段、发文日、会议日期、微信公众号发表日期等）→ 文件名前缀使用该日期
2. 文档无固有日期 → 文件名前缀使用 frontmatter 中的 `created` 日期
3. 重命名前，检查目标日期+标题是否与已有文件冲突；如有冲突，在标题后添加区分标识（如序号）

**Classification boundary rule**: If a file clearly does not fit the existing seven categories (e.g., audio, video, special-format datasets), pause and ask the user whether to add a new category. Do not create new top-level folders without user confirmation, and do not temporarily misfile materials.

### 4b. 搬迁三件套：原件 + 全文 md + 图片 (仅 PDF)

不再本地抽取，而是把**原始 PDF** 与步骤 3 mineru 生成的产物（`00-收件箱/PDF解析/<stem>/`）统一搬到归档位。`<stem>` 为原 PDF 文件名去扩展名，`<token>` 为 mineru 生成的图片目录 token（形如 `20260701_143052_a1b2`）。

0. **原始 PDF 搬迁**：`00-收件箱/<原PDF名>.pdf` → 移动到 `10-原始资料/99-PDF原件/{分类}/YYYYMMDD-原标题.pdf`（二进制原件，只读，最终 ground truth）
1. **全文 md 搬迁**：`00-收件箱/PDF解析/<stem>/<stem>.md` → 移动到 `10-原始资料/{分类}/YYYYMMDD-原标题.md`（与 PDF 同名、同分类，落在分类目录而非 99-PDF原件），使 PDF 内容可被 `Grep` 检索
2. **图片目录搬迁 + 重命名**：`00-收件箱/PDF解析/<stem>/<token>.images/` → 重命名为 `YYYYMMDD-原标题.images/` → 移动到 `10-原始资料/99-PDF原件/{分类}/`（按篇隔离，避免不同 PDF 图片撞名）
3. **改写图片引用**：把全文 md 内全部 mineru 相对引用 `![图 N](<token>.images/<file>)` 改写为指向归档位置的 Obsidian 嵌入，保证从 md 可直接点开查看：
   ```markdown
   ![[99-PDF原件/{分类}/YYYYMMDD-原标题.images/<file>]]
   ```
   （即：把 markdown 语法换成 Obsidian 嵌入，并把目录名 `<token>` 换成 `YYYYMMDD-原标题`。图片存在 99-PDF原件、md 链接到 99-PDF原件——两者分离但连通；正文原有图注文字照常保留，可被检索。）
4. **改写 frontmatter**：`source_pdf` 指向归档 PDF；`title` 规整为 `全文·原标题`；保留 `extracted_by: mineru`
5. **正文开头插入原始资料**：在 frontmatter 之后、正文第一个标题之前，插入指向归档 PDF 的 Obsidian 链接，便于从全文 md 一键打开原件：
   ```markdown
   > 📎 **原始资料**：[[99-PDF原件/{分类}/YYYYMMDD-原标题.pdf]]
   ```
6. **清理**：删除 `00-收件箱/PDF解析/<stem>/` 空壳目录

Frontmatter + 正文开头固定格式：

```yaml
---
title: 全文·原标题
source_pdf: 10-原始资料/99-PDF原件/{分类}/YYYYMMDD-原标题.pdf
type: fulltext
extracted_by: mineru                 # PDF 唯一抽取路径固定为 mineru
extracted_date: YYYY-MM-DD
extraction_quality: good             # good / partial（表格错位或局部缺失时如实标注）
---

> 📎 **原始资料**：[[99-PDF原件/{分类}/YYYYMMDD-原标题.pdf]]

<mineru 抽取的完整正文（图片引用已改写为指向 99-PDF原件 的 Obsidian 嵌入）>
```

> 全文 md 为 PDF 的机器转录，**只读、可从 `99-PDF原件/` 下的 PDF 用 mineru-parse 重新生成**（重生时图片一并重新抽取、重命名、归档）。表格/公式在纯文本转录中可能错位，涉及精确排版以 PDF 原件为准。

### 5. Create Source Summary Page

Create a Markdown summary page in `20-知识库/04-来源/` with the same base name as the raw material (including the `YYYYMMDD-` prefix).

**PDF 资料**：摘要**基于步骤 4b 搬迁到位的 mineru 全文 md** 提炼（不再直接读 PDF），确保摘要建立在完整上下文之上。

**来源页日期规则**：来源页是衍生作品无固有日期，文件名中的 `YYYYMMDD` 使用 frontmatter 中的 `created` 日期。

Page structure:

```markdown
---
title: 资料标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [source, tag1, tag2]
source: 10-原始资料/99-PDF原件/XX-分类/YYYYMMDD-原标题.pdf   # PDF 类指向 99-PDF原件；文本类指向 10-原始资料/XX-分类/…md
author: 作者名
confidence: 0.80
confidence_factors:
  source_count: 1
  last_confirmed: YYYY-MM-DD
  contradiction_count: 0
  cross_references: 0
status: active
---
```

> 来源页初次创建时，`source_count: 1`（自身作为第一个来源），`last_confirmed` 设为创建日期。`cross_references` 初始为 0，后续其他页面链接时增量更新。

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

- PDF 原件：`10-原始资料/99-PDF原件/XX-分类/YYYYMMDD-原标题.pdf`
- 全文转录：`10-原始资料/XX-分类/YYYYMMDD-原标题.md`（PDF 类才有）
- 原文链接：...
- 原载：...
```

### 5a. Path Verification (Prevent Root-Level Files)

Before creating ANY new file, verify it is NOT placed in the vault root:

- ✅ Valid: `20-知识库/04-来源/01-政策法规/20260630-xxx.md`
- ❌ Invalid: `01-华宇科技.md` (at root — misplaced)
- ❌ Invalid: `任何.md` (at root — misplaced)

**规则**：知识库文件必须放在 `20-知识库/XX-分类/` 下，禁止在根目录创建 `.md` 文件。

If a file path resolves to the root level, correct it to the proper subdirectory before writing.

### 6. Reference Entity Pages (Forward References)

In the source summary page, add wiki links to relevant entities (people, organizations, locations):

- Use `[[01-实体/01-实体名]]` format (with prefix, without `20-知识库/` prefix)
- **Default**: Do NOT create the entity page during ingest — leave it as a gray link (forward reference)
- **Exception**: Only create the entity page if it is the **core topic** of this ingest AND you have sufficient information to write a meaningful page
- If creating: MUST use `20-知识库/01-实体/01-实体名.md` full path, NEVER at root
- If creating: frontmatter 需包含 v2 增强字段（见下方统一规则）

### 7. Reference Concept Pages (Forward References)

In the source summary page, add wiki links to relevant concepts (definitions, methods, theories):

- Use `[[02-概念/02-概念名]]` format
- **Default**: Do NOT create the concept page during ingest — leave it as a gray link
- **Exception**: Only create if the concept is the **core topic** of this ingest AND you have sufficient information
- If creating: MUST use `20-知识库/02-概念/02-概念名.md` full path, NEVER at root
- If creating: frontmatter 需包含 v2 增强字段（见下方统一规则）

### 8. Reference Theme Pages (Forward References)

In the source summary page, add wiki links to relevant themes (cross-cutting synthesis topics):

- Use `[[03-主题/03-主题名]]` format
- **Default**: Do NOT create the theme page during ingest — leave it as a gray link
- **Exception**: Only create if the theme is the core contribution of this ingest
- If creating: MUST use `20-知识库/03-主题/03-主题名.md` full path, NEVER at root
- If creating: frontmatter 需包含 v2 增强字段（见下方统一规则）

#### 创建新实体/概念/主题页时的 frontmatter 统一规则

当例外情况触发创建新页面时，frontmatter 应包括：

```yaml
---
title: 页面名称
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [entity/concept/theme]
confidence: 0.70
confidence_factors:
  source_count: 1
  last_confirmed: YYYY-MM-DD
  contradiction_count: 0
  cross_references: 1
status: active
---
```

### 8a. 增量更新引用目标页面的统计字段

当来源页引用已有实体/概念/主题页面时（即链接指向已存在的页面）：
1. 读取目标页面的 frontmatter
2. 对 `confidence_factors.source_count` +1
3. 对 `confidence_factors.cross_references` +1
4. 更新 `confidence_factors.last_confirmed` 为当前日期
5. 写回目标页面

### 8b. 知识图谱关系抽取

创建来源摘要页时，扫描正文中的实体关系模式，自动生成关系条目：

1. **识别关系动词**：在正文中搜索以下模式：
   - "[实体A]研究[概念B]" → type: 研究
   - "[实体A]任职于[实体B]" → type: 任职于
   - "[实体A]与[实体B]合作" → type: 合作
   - "[实体A]监管[实体B]" → type: 监管 / 制定政策
   - "[实体A]是[实体B]的下属/子公司" → type: 隶属
2. **去重**：检查 `20-知识库/00-索引/knowledge-graph.md` 中是否已有相同的关系记录（相同的 source + type + target）
3. **追加**：将新关系追加到 knowledge-graph.md 的 relationships 列表末尾
4. **置信度继承**：新关系的 confidence 取来源页 confidence 值的 80%

### 9. Update Index

Add the new source to the appropriate section of `20-知识库/00-索引/index.md`.

### 10. Append Log

Add a new entry to `20-知识库/00-索引/log.md` describing the ingest operation.

### 11. Update Statistics

Update counts in `20-知识库/00-索引/stats.md`.

### 12. Clean Up Inbox

Remove processed files from `00-收件箱/`. Keep `README.md` and any files the user explicitly wants to retain.

### 13. Update Todos

Check `20-知识库/06-元/06-todo.md` and clear or update relevant items.

## Example

User: "处理收件箱"

LLM:
1. Read all files in `00-收件箱/`
2. Check for duplicates in `10-原始资料/`（含 `99-PDF原件/`）and `20-知识库/04-来源/`
3. 用 `mineru-parse` 抽取每个 PDF 全文（`--is-ocr --enable-formula --enable-table --model-version vlm`）；缺 token / 网络错 / API 错 / 质量不过则**停止并报告**，不归档、不建来源页（唯一路径，无兜底）
4. 搬迁三件套：原始 PDF → `10-原始资料/99-PDF原件/{分类}/`；全文 md → `10-原始资料/{分类}/`（供 Grep 检索，开头插入 `[[99-PDF原件/...pdf]]` 原始资料）；图片目录重命名为 `YYYYMMDD-原标题.images/` → `99-PDF原件/{分类}/`，并把 md 内图片引用改写为 `![[99-PDF原件/...]]`（分类取自 7 类：政策法规/学术论文/行业报告/技术规范/产品与公司/媒体报道/会议沟通）
5. Create source summary pages in `20-知识库/04-来源/` based on 全文 md, with wiki links (forward references); `source:` 指向 `99-PDF原件/` 下的 PDF
6. Update `index.md`, `log.md`, `stats.md`
7. Remove processed files from `00-收件箱/`（含 `PDF解析/<stem>/` 空壳）
8. Report summary to user
