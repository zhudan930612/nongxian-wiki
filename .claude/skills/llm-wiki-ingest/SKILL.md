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
  5. **通过** → 进入步骤 4；全文 md 的 `extracted_by` 固定为 `mineru`。mineru 初始 frontmatter 中 `extraction_quality` 为 `unverified`，LLM 校验后通过 `finalize_ingest.py` 的 `--quality` 参数定稿为 `good` / `partial`。
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

### 4b. 搬迁：按篇隔离的归档目录 (仅 PDF)

不再手工搬迁，而是调用确定性脚本 `finalize_ingest.py` 一次完成：把 mineru 解析目录 `00-收件箱/PDF解析/<stem>/` 整体搬到 `10-原始资料/99-PDF原件/{分类}/YYYYMMDD-原标题/`，并将原始 PDF 也放入该目录，形成"每篇一个独立目录"的整洁布局。`<stem>` 为原 PDF 文件名去扩展名。

```bash
.claude/skills/mineru-parse/.venv/Scripts/python.exe \
  .claude/skills/llm-wiki-ingest/scripts/finalize_ingest.py \
  --stem "<原PDF名去扩展名>" \
  --category "<7类之一>" \
  --name "YYYYMMDD-原标题" \
  --title "原标题" \
  --quality good            # 步骤 3 校验结果：good / partial
  # [--images auto|keep|drop] 默认 auto
```

mineru 现在直接输出与归档一致的目录结构：

```text
00-收件箱/PDF解析/<stem>/
├── <stem>.md          # 图片引用为相对路径 images/x.jpg
└── images/            # 图片目录（不再使用全局唯一 token）
```

脚本行为（全部相对 vault 根）：
0. 解析目录 `00-收件箱/PDF解析/<stem>/` 包含：`<stem>.md`（图片引用为相对 `images/x.jpg`）和 `images/`
1. **全文 md** 改写后落到 `10-原始资料/{分类}/YYYYMMDD-原标题.md`（供 Grep 检索）
2. **原始 PDF + 图片目录** 整体搬到 `10-原始资料/99-PDF原件/{分类}/YYYYMMDD-原标题/`，形成按篇隔离的目录：
   ```text
   10-原始资料/99-PDF原件/{分类}/YYYYMMDD-原标题/
   ├── YYYYMMMDD-原标题.pdf
   └── images/
   ```
3. **改写图片引用**：把 md 内相对引用 `![图 N](images/x.jpg)` 改写为指向归档图片的 Obsidian wikilink：
   ```markdown
   ![[99-PDF原件/{分类}/YYYYMMDD-原标题/images/x.jpg]]
   ```
4. frontmatter：`title: 全文·原标题`、`source_pdf` 指向归档 PDF、`extraction_quality` 定为 `--quality` 值、保留 `extracted_by: mineru`
5. 正文开头插入 `> 📎 **原始资料**：[[99-PDF原件/{分类}/YYYYMMDD-原标题/YYYYMMDD-原标题.pdf]]`
6. 删除 `00-收件箱/PDF解析/<stem>/` 空壳
7. stdout 打印 JSON（归档路径、图片引用数、孤立图片删除数、quality），据此核对

**孤立图片规则**（脚本 `--images` 参数）：
- `auto`（默认）：md 图片引用数 > 0 → 保留 `images/`；引用数 = 0 且图片目录非空（多为公式/表格的冗余渲染）→ **删除 `images/` 目录**，JSON 报告 `orphan_dropped`（PDF 原件已保全部内容，可兜底）
- `keep`：疑似含真实图表却未被引用时，强制保留 `images/`，人工补引用
- `drop`：强制删除 `images/`

**防覆盖**：目标归档目录已存在时脚本报错退出，不覆盖；需先清理或更换 `--name`。

归档后布局：

```text
10-原始资料/
├── {分类}/
│   └── YYYYMMMDD-原标题.md                # 全文转录，可被 Grep 检索
└── 99-PDF原件/{分类}/
    └── YYYYMMMDD-原标题/                  # 每篇一个目录，不混放
        ├── YYYYMMMDD-原标题.pdf
        └── images/                        # 仅当 md 有图片引用时存在
```

Frontmatter + 正文开头最终形态：

```yaml
---
title: 全文·原标题
source_pdf: 10-原始资料/99-PDF原件/{分类}/YYYYMMDD-原标题/YYYYMMDD-原标题.pdf
type: fulltext
extracted_by: mineru
extracted_date: YYYY-MM-DD
extraction_quality: good             # 由 --quality 定稿：good / partial
---

> 📎 **原始资料**：[[99-PDF原件/{分类}/YYYYMMDD-原标题/YYYYMMDD-原标题.pdf]]

<mineru 抽取的完整正文（图片引用已改写为指向 99-PDF原件 的 Obsidian 嵌入）>
```

> 全文 md 为 PDF 的机器转录，**只读、可从 `99-PDF原件/` 下的 PDF 用 mineru-parse 重新生成**（重生后再跑 finalize）。表格/公式在纯文本转录中可能错位，涉及精确排版以 PDF 原件为准。

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

来源页应作为**产品需求分析与产品规划的入口**，从原文中提取对后续分析最关键的信息。来源页**不是全文复制**，但要比简单摘要更结构化：重点保留现状、问题、数据、做法、技术相关内容，便于快速定位可用信息。

# 资料标题

> 一句话摘要

> 📎 **原始资料**：[[99-PDF原件/XX-分类/YYYYMMDD-原标题/YYYYMMDD-原标题.pdf]] · [[10-原始资料/XX-分类/YYYYMMDD-原标题.md|全文转录]]

## 核心观点

1. ...
2. ...

## 背景与现状

- 政策/市场/业务现状
- 行业所处阶段
- 主要参与方及其角色

## 关键数据与指标

- 规模、增速、覆盖率
- 投入、成本、效率指标
- 其他可量化的关键数字

## 关键问题与痛点

- 当前面临的主要约束
- 效率瓶颈或风险点
- 不同参与方的痛点差异

## 做法与机制

- 制度设计、流程机制
- 组织分工与协作方式
- 成功实践或典型案例

## 技术应用与工具

- 使用的技术手段（遥感、GIS、大数据、AI、平台系统等）
- 技术解决的具体问题
- 技术落地的前提条件或限制

## 建议/启示/可落地方向

- 政策/行业/企业层面的建议
- 对产品需求或产品规划的启发
- 可进一步调研或验证的方向

## 相关实体

- [[01-实体名]]

## 相关概念

- [[02-概念名]]

## 相关主题

- [[03-主题名]]

## 来源

- PDF 原件：[[99-PDF原件/XX-分类/YYYYMMDD-原标题/YYYYMMDD-原标题.pdf]]
- 全文转录：[[10-原始资料/XX-分类/YYYYMMDD-原标题.md]]（PDF 类才有）
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

运行 `recompute_stats.py` 从文件系统真实计数并更新 `20-知识库/00-索引/stats.md`，取代手工增减（避免漂移）：

```bash
.claude/skills/mineru-parse/.venv/Scripts/python.exe \
  .claude/skills/llm-wiki-ingest/scripts/recompute_stats.py --ingest-date <today>
```

脚本重算实体/概念/主题/来源/问答/总页面/原始资料/知识图谱关系/灰色链接/平均置信度/取代事件数，并打印 before→after 对比。`最后检查` 保持不动（lint 维护）。

### 12. Clean Up Inbox

Remove processed files from `00-收件箱/`. Keep `README.md` and any files the user explicitly wants to retain.

### 13. Update Action Items

If the ingest surfaced follow-up tasks or open questions, capture them in `20-知识库/00-索引/log.md` or crystallize into `05-问答/` pages. There is no standalone `06-todo.md`; todos are handled via logs and Q&A crystallization.

## Example

User: "处理收件箱"

LLM:
1. Read all files in `00-收件箱/`
2. Check for duplicates in `10-原始资料/`（含 `99-PDF原件/`）and `20-知识库/04-来源/`
3. 用 `mineru-parse` 抽取每个 PDF 全文（`--is-ocr --enable-formula --enable-table --model-version vlm`）；缺 token / 网络错 / API 错 / 质量不过则**停止并报告**，不归档、不建来源页（唯一路径，无兜底）
4. 定好分类/命名/标题后，运行 `finalize_ingest.py`：全文 md → `10-原始资料/{分类}/`；PDF 原件 + 图片目录 → `99-PDF原件/{分类}/YYYYMMDD-原标题/`（按篇隔离，孤立图片默认删除）；md 内图片引用改写为 `![[99-PDF原件/.../images/x.jpg]]`；frontmatter 定稿；md 开头插入原始资料索引（分类取自 7 类：政策法规/学术论文/行业报告/技术规范/产品与公司/媒体报道/会议沟通）
5. Create source summary pages in `20-知识库/04-来源/` based on 全文 md, with wiki links (forward references); `source:` 指向 `99-PDF原件/` 下的 PDF
6. Update `index.md`、`log.md`，并运行 `recompute_stats.py --ingest-date <today>` 重算 `stats.md`
7. Remove processed files from `00-收件箱/`（finalize 已清 `PDF解析/<stem>/` 空壳）
8. Report summary to user
