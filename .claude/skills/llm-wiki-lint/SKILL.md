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

#### 3a. 矛盾自动裁决

对上一节发现的矛盾，执行自动裁决：

1. **评估依据**（按优先级）：
   - 来源权威性：政策文件 > 学术论文 > 行业报告 > 媒体报道 > 会议沟通
   - 来源时效性：更新日期越近越可信
   - 页面置信度：confidence 越高越可信
   - 支持来源数：支持某一方的来源数量更多

2. **裁决输出格式**：
   ```
   矛盾：[页面A] 说"X"，[页面B] 说"Y"
   裁决：采用[页面B]的说法
   理由：[页面B]引用2025年新政（权威性：政策文件），[页面A]仅引用2022年旧版
   操作：已将[页面A]设为 superseded，添加 superseded_by 指向[页面B]
   ```

3. **执行修复**：
   - 将被裁决为劣势的页面设为 `status: superseded`
   - 添加 `superseded_by` 指向优势页面
   - 在优势页面中添加 `supersedes` 指向劣势页面

### 4. Check for Outdated Claims

Identify content that may no longer be accurate:

- Old policy references that have been superseded
- Outdated statistics
- Deprecated terminology
- Source pages with old dates that may need re-evaluation

### 4b. 批量置信度评分

对 01-实体/、02-概念/、03-主题/、05-问答/ 下的页面进行置信度评分：

1. **读取页面 frontmatter**：获取 `confidence_factors` 中存储的原始数据
2. **时效性计算**：`days_since_confirmed = today - last_confirmed`，`timeliness = max(0, 1 - days_since_confirmed / 180)`
3. **完成度检查**：页面是否有正文内容（h1 后至少一段文字）、是否有 Wiki 链接、是否有完整 frontmatter
4. **加权求和**：
   ```
   confidence = source_score × 0.30 + timeliness × 0.25 + contradiction_score × 0.20 + reference_score × 0.15 + completeness × 0.10
   ```
5. **状态自动流转**：
   - `days_since_confirmed > 180` → `status: fading`（之前是 active）
   - `days_since_confirmed > 365` → `status: archived`（之前是 fading）
   - 被 `superseded_by` 引用的 → `status: superseded`
6. **写入更新**：将新的 `confidence` 和 `status` 写回页面 frontmatter

### 5. Check for Orphan Pages

Find pages with no inbound wiki links:

- Read each page's content
- Search the vault for `[[page-name]]` references
- If a page is never linked, flag it as orphan
- Suggest where it should be linked from, or whether it should be removed

#### 5a. 孤立页面自动修复

对上一节发现的孤立页面，执行自动修复：

1. 对每个孤立页面，读取其标题和正文前 200 字，确定主题
2. 在全 vault 中搜索包含相同关键词的页面
3. 在匹配页面中找到最合适的位置，添加 `[[孤立页面名]]` 链接
4. 如果找不到合适的匹配页面，在孤立页面末尾添加 `## 待链接` 区段
5. 在报告中记录：已修复 N 个、无法修复 M 个及其原因

### 6. Check for Missing Concept Pages

Scan pages for wiki links that point to non-existent pages:

- Extract all `[[...]]` links
- Check if the target file exists
- If a concept is referenced frequently but has no page, suggest creating it in `02-概念/`

### 6a. 取代检测

扫描所有页面的 `supersedes` 和 `superseded_by` 字段：

1. **正向验证**：对每页的 `superseded_by` 列表，检查目标页面是否存在
   - 若存在且 `status: active`，当前页设 `status: superseded`
   - 若不存在，记录到 lint 报告（断链警告）
2. **反向验证**：对每页的 `supersedes` 列表，类似处理
3. **循环检测**：检查是否存在 A→B→C→A 的取代循环
4. **活跃引用检测**：检查 `status: superseded` 的页面是否还被其他活跃页面引用
   - 若有，在 lint 报告中列出过时引用，建议修复
5. **更新取代日志**：将新发现的取代关系追加到 supersession-log.md

#### 6b. 断裂链接自动修复

对步骤 6 中发现的断裂链接（指向不存在页面的 `[[链接]]`）：

1. **别名匹配**：检查链接文本是否与某个已有页面的 title 或 alias 匹配
   - 如果匹配 → 自动修正链接路径为标准格式
2. **频繁引用自动创建**：同一断裂链接被引用 ≥3 次
   - 自动创建目标页面，补充基本 frontmatter 和结构
   - 在页面中添加"自动创建"标记和引用来源
3. **低频断裂记录**：引用 1-2 次的断裂链接
   - 记录到 lint 报告，标注"低优先级"

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
- **文件名日期检查**：文件名中的 `YYYYMMDD` 优先级为：文档有自身固有日期则使用该日期，无固有日期才用 `created` 日期。
  - 检查步骤：先看文档是否有 `published`、发文日、会议日期等固有日期 → 文件名应匹配该日期
  - 无固有日期 → 文件名应匹配 `created` 日期
  - 不一致则标记为违规，注明期望日期

### 8a. Check Root-Level Files

Scan the vault root for `.md` files that should not be there:

- ✅ Allowed at root: `CLAUDE.md`, `README.md`, `.gitignore`, `.obsidian/`
- ❌ Anything else (e.g., `01-华宇科技.md`, `概念名.md`) → flag as **misplaced**

For each misplaced file:
1. Report the filename and its size
2. Suggest the correct target directory based on the naming prefix:
   - `01-` prefix → `20-知识库/01-实体/`
   - `02-` prefix → `20-知识库/02-概念/`
   - `03-` prefix → `20-知识库/03-主题/`
   - `04-` prefix → `20-知识库/04-来源/`
   - No prefix → examine content to determine type
3. If the file is empty (0 bytes), flag for **deletion or content completion**
4. In the lint report, list all misplaced files as a separate section

> **Prevention note**: Root-level files are typically created when the ingest workflow writes a file without the full `20-知识库/XX-分类/` prefix. The ingest skill's step 6a (Path Verification) should prevent this, but this lint check catches any that slip through.

### 8b. 结晶后处理

遍历 `20-知识库/05-问答/` 下所有 `status: active` 且含 `## 待确认事实` 区块的页面：

1. **解析事实原子**：读取 `## 待确认事实` 下的每个列表项
   ```
   - **事实**：描述
     - 类型：组织事实/统计数据/观点/定义
     - 来源：[[页面链接]]
     - 目标页面：[[目标页面]]
     - 置信度影响：+0.05
   ```
2. **合并到目标页面**：
   - 读取目标页面内容
   - 在适当位置添加事实引用（或更新已有内容）
   - 增量更新目标页面的 `confidence_factors.source_count`
   - 增量更新目标页面的 `confidence_factors.last_confirmed`
3. **标记已处理**：
   - 将 `## 待确认事实` 改为 `## 已吸收事实`
   - 若全部事实已吸收，将结晶页 `status` 设为 `absorbed`
4. **报告**：列出本次吸收了哪些事实、更新了哪些目标页面

### 8c. 知识图谱验证

遍历 `20-知识库/00-索引/knowledge-graph.md` 中所有关系记录，执行以下检查：

1. **孤立实体检测**：
   - 获取所有实体和概念页面的列表（01-实体/、02-概念/）
   - 检查每个实体是否出现在至少一条关系中
   - 列出孤立实体（没有任何关系的页面）
   - 基于页面内容推断可能的关系类型和目标

2. **残缺关系检测**：
   - 检查每条关系是否有 source、type、target、sources 四个字段
   - 检查 source 和 target 是否指向存在的页面
   - 报告缺少必要字段或指向不存在页面的关系

3. **单向关系合理性检查**：
   - 对 bidirectional: false 的关系，根据 type 判断是否需要双向
   - 规则：合作、竞争应双向；研究、监管一般单向
   - 报告不合理的单向设置

4. **置信度衰减**：
   - 读取每条关系的来源页的 last_confirmed
   - 如果超过 180 天，confidence 自动乘以 0.8
   - 更新知识图谱中的 confidence 值

5. **更新图谱统计**：
   - 在报告中增加图谱统计：关系总数、孤立实体数、待修复数

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

> 当前状态参考（`04-来源/`），数字为快照，执行前应由 LLM 重新统计：
> - `01-政策法规/` — 5 ✅
> - `02-学术论文/` — 19 ✅
> - `03-行业报告/` — 5 ✅
> - `04-技术规范/` — 11 ✅
> - `05-产品与公司/` — 5 ✅
> - **`06-媒体报道/` — 85 🔶**
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

### 6. 置信度概览

| 分类 | 页面数 | 平均置信度 | 最低 | 最高 |
|------|--------|-----------|------|------|
| 实体 | N | 0.XX | 0.XX | 0.XX |
| 概念 | N | 0.XX | 0.XX | 0.XX |
| 主题 | N | 0.XX | 0.XX | 0.XX |
| 问答 | N | 0.XX | 0.XX | 0.XX |

### 7. 状态分布

| 状态 | 计数 |
|------|------|
| active | N |
| fading | N |
| superseded | N |
| archived | N |

### 8. 结晶吸收

- 本次吸收事实数：N
- 已标记 absorbed：N
- 仍在待确认：N
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
