# LLM Wiki v2 增强 — 阶段 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 LLM Wiki vault 基础上，落地置信度评分、取代机制、结晶机制三个核心增强

**Architecture:** 所有改动在 Obsidian Markdown + Claude Code skill 框架内完成，不引入外部依赖。通过扩展 YAML frontmatter、改造 Ingest/Query/Lint 三个工作流来实现

**Tech Stack:** Markdown, YAML frontmatter, Claude Code skills

## Global Constraints

- `10-原始资料/` 下文件永不修改（只读）
- 所有知识库文件必须放在 `20-知识库/XX-分类/` 下，禁止根目录创建 `.md`
- 内部链接使用 `[[XX-分类/XX-名称]]` 格式（无 `20-知识库/` 前缀）
- 新增字段为 optional，向后兼容
- 置信度评分采用 0.0-1.0 浮点数，lint 批量重算

---

### Task 1: 更新 CLAUDE.md — YAML frontmatter 规范扩展

**Files:**
- Modify: `CLAUDE.md`（页面规范章节 + 三大工作流章节）

**Interfaces:**
- Consumes: 无
- Produces: 新增 frontmatter 字段定义、Query 结晶流程、Lint 扩展步骤

- [ ] **Step 1: 读取当前 CLAUDE.md**

Read `CLAUDE.md` 全文以确认当前内容。

- [ ] **Step 2: 更新"页面规范"章节** — 扩展 YAML frontmatter 定义

在"可选字段"段落后，插入以下内容：

```markdown
### 新增元数据字段（v2 增强）

所有知识库页面可选择性地包含以下扩展字段：

```yaml
confidence: 0.85                        # 总体置信度 [0.0, 1.0]
confidence_factors:                      # 评分明细
  source_count: 8                        # 支持页面的来源数
  last_confirmed: 2026-06-30             # 最近确认日期
  contradiction_count: 0                 # 矛盾数
  cross_references: 5                    # 引用数
supersedes: []                           # 取代的旧页面列表
superseded_by: []                        # 被哪些新页面取代
status: active                           # active / fading / superseded / archived / draft
crystallized_from: query                 # 结晶来源（问答页专有）
session_summary: true                    # 是否完整会话摘要（问答页专有）
```

**字段说明：**

| 字段 | 适用页面 | 说明 |
|------|---------|------|
| `confidence` | 实体/概念/主题/问答 | 0.0-1.0，lint 时批量计算 |
| `confidence_factors` | 同 confidence | 提供评分透明度，lint 时更新 |
| `supersedes` | 所有 | 被当前页面取代的旧页面路径 |
| `superseded_by` | 所有 | 取代当前页面的新页面路径 |
| `status` | 所有 | 扩展可选值：fading(180天未确认)、superseded(被取代) |
| `crystallized_from` | 问答页 | 结晶来源：query / session / ingest-auto |
| `session_summary` | 问答页 | 是否为完整会话摘要 |

**状态流转：**

```
active ──(180天未确认)──→ fading ──(365天未确认)──→ archived
active ──(被新页面取代)────→ superseded
```

`fading/superseded/archived` 页面默认不参与查询排序，仅在回溯时可见。
```

- [ ] **Step 3: 更新 Query 工作流** — 嵌入结晶步骤

修改"查询 (Query)"章节，将原有步骤 4 替换为：

```markdown
### 2️⃣ 查询 (Query)

当用户向知识库提问时：

1. 先读取 `index.md` 了解知识库全貌
2. 根据问题搜索相关页面并阅读
3. 综合回答，附上引用（Wiki 链接形式）
4. **结晶检查**：回答完成后自动评估是否值得归档
   - **触发条件**（满足任一即可）：
     - 回答涉及 3+ 个不同来源的交叉分析
     - 回答包含知识库现有页面未覆盖的结论
     - 回答涉及当前项目关键决策
     - 同一类型问题被多次询问（自动判断频率）
   - **触发时**：按结晶流程（见下文）创建归档
5. **结晶流程**（仅在触发时执行）：
   a. 创建 Q&A 归档页：`20-知识库/05-问答/YYYYMMDD-标题.md`
      - 写入 frontmatter：包含 `crystallized_from`、`confidence` 等字段
      - 正文记录问题和综合回答
   b. 抽取事实原子：放入结晶页的 `## 待确认事实` 区块
   c. 增量更新相关页面的 `source_count`、`cross_references`、`last_confirmed`
   d. 更新索引和日志
```

- [ ] **Step 4: 更新 Lint 工作流** — 增加置信度评分、取代检测、结晶后处理

在"检查 (Lint)"章节末尾增加：

```markdown
#### Lint 扩展步骤（v2 增强）

##### 4a. 置信度批量评分

对实体、概念、主题、问答页面批量计算置信度：

| 维度 | 计算方式 | 权重 |
|------|---------|------|
| 来源数 | `min(source_count / 5, 1.0)` | 30% |
| 时效性 | `max(0, 1 - days_since_last_confirmed / 180)` | 25% |
| 矛盾数 | `max(0, 1 - contradiction_count × 0.2)` | 20% |
| 引用数 | `min(cross_references / 3, 1.0)` | 15% |
| 完成度 | 内容结构完整度（正文+链接+frontmatter） | 10% |

更新状态流转：`last_confirmed > 180天 → fading`，`> 365天 → archived`。

##### 4b. 取代检测

1. 遍历所有页面，检查 `superseded_by` 字段
2. 若目标页面存在且 `status: active`，将当前页面设为 `status: superseded`
3. 检查 `superseded` 页面是否还被活跃页引用 → 报告
4. 检查取代链是否形成循环 → 报告异常

##### 4c. 结晶后处理

1. 遍历 `05-问答/` 中 `status: active` 且含 `## 待确认事实` 的页面
2. 将事实原子批量合并到对应的实体/概念/主题页
3. 合并成功后，将 `## 待确认事实` 改为 `## 已吸收事实`
4. 设定结晶页 `status: absorbed`（表示事实已完全吸收）
```

- [ ] **Step 5: 确认并写入修改**

使用 Edit 工具对 CLAUDE.md 进行精确替换，逐步写入上述三处修改。

---

### Task 2: 改造 ingest skill — 支持新 frontmatter 字段

**Files:**
- Modify: `.claude/skills/llm-wiki-ingest/SKILL.md`

**Interfaces:**
- Consumes: Task 1 定义的 frontmatter 规范
- Produces: 创建页面时带有 `confidence`、`confidence_factors` 等字段；来源引用时增量更新目标页面字段

- [ ] **Step 1: 读取当前 ingest skill**

Read `.claude/skills/llm-wiki-ingest/SKILL.md` 全文。

- [ ] **Step 2: 更新来源页模板** — 增加 frontmatter 字段

在"6. Create Source Summary Page"的模板中，将 frontmatter 示例替换为：

```markdown
---
title: 资料标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [source, tag1, tag2]
source: 10-原始资料/XX-分类/YYYYMMDD-原标题.扩展名
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

并在模板说明中增加一行：
> 来源页初次创建时，`source_count: 1`（自身作为第一个来源），`last_confirmed` 设为创建日期。`cross_references` 初始为 0，后续其他页面链接时增量更新。

- [ ] **Step 3: 更新实体/概念/主题创建规则** — 增加字段

在"7. Reference Entity Pages"、"8. Reference Concept Pages"、"9. Reference Theme Pages"中，当**创建**新页面时（例外情况），frontmatter 包含：

```yaml
---
title: 实体名称
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [entity]
confidence: 0.70
confidence_factors:
  source_count: 1
  last_confirmed: YYYY-MM-DD
  contradiction_count: 0
  cross_references: 1
status: active
---
```

- [ ] **Step 4: 新增"增量字段更新"步骤**

在"9. Reference Theme Pages"之后、"10. Update Index"之前，插入新步骤：

```
### 9a. 增量更新引用目标页面的统计字段

当来源页引用已有实体/概念/主题页面时：
1. 读取目标页面的 frontmatter
2. 对 `confidence_factors.source_count` +1
3. 对 `confidence_factors.cross_references` +1
4. 更新 `confidence_factors.last_confirmed` 为当前日期
5. 写回目标页面
```

---

### Task 3: 改造 lint skill — 置信度 + 取代 + 结晶后处理

**Files:**
- Modify: `.claude/skills/llm-wiki-lint/SKILL.md`

**Interfaces:**
- Consumes: Task 1 定义的 lint 扩展步骤
- Produces: lint 时执行置信度评分、取代检测、结晶后处理

- [ ] **Step 1: 读取当前 lint skill**

Read `.claude/skills/llm-wiki-lint/SKILL.md` 全文。

- [ ] **Step 2: 插入"置信度批量评分"步骤**

在"5. Check for Orphan Pages"之前，插入新步骤：

```
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
```

- [ ] **Step 3: 插入"取代检测"步骤**

在"6. Check for Missing Concept Pages"之后，插入：

```
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
```

- [ ] **Step 4: 插入"结晶后处理"步骤**

在"8. Check File Naming and Frontmatter"之后，插入：

```
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
```

- [ ] **Step 5: 更新报告模板**

在"10. Generate Lint Report"的模板中增加以下章节：

```markdown
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

- [ ] **Step 6: 确认并写入修改**

逐步使用 Edit 工具更新 lint skill。

---

### Task 4: 创建取代日志文件

**Files:**
- Create: `20-知识库/00-索引/supersession-log.md`

- [ ] **Step 1: 创建取代日志文件**

创建 `20-知识库/00-索引/supersession-log.md`：

```markdown
---
title: 取代日志
created: 2026-06-30
updated: 2026-06-30
tags: [system, log, supersession]
---

# 取代日志

> 此文件为追加式日志，记录所有知识取代事件。每行格式为 `## [YYYY-MM-DD] 取代类型 | 标题`。

## 说明

**取代机制**跟踪知识库中信息被新信息替代的过程。当新页面明确取代旧页面时：

1. 旧页面的 `superseded_by` 指向新页面
2. 新页面的 `supersedes` 指向旧页面
3. lint 时旧页面自动设 `status: superseded`

初始状态：无取代事件。
```

- [ ] **Step 2: 验证文件路径正确**

确认文件位于 `20-知识库/00-索引/` 下，非根目录。

---

### Task 5: 批量更新现有知识库页面 — 补充新增字段

**Files:**
- Modify: 所有 `20-知识库/01-实体/`、`02-概念/`、`03-主题/`、`05-问答/` 下的页面（约 57 个）
- Note: `04-来源/` 和 `06-元/` 暂不处理（来源页为衍生品，元页为系统文件）

**Interfaces:**
- Produces: 所有实体/概念/主题/问答页面包含初始化的 `confidence`、`confidence_factors`、`status` 字段

- [ ] **Step 1: 扫描所有需更新页面**

使用 Glob 获取所有需要更新的页面列表：
- `20-知识库/01-实体/**/*.md`
- `20-知识库/02-概念/*.md`
- `20-知识库/03-主题/*.md`
- `20-知识库/05-问答/*.md`

- [ ] **Step 2: 计算每页的初始字段值**

对每个页面：
1. 读取 frontmatter 中的 `created`、`updated`、`source` 字段
2. 计算 ~~`days_since_created`（当前日期 2026-06-30 - created）~~
3. 计算 ~~`timeliness = max(0, 1 - days_since_created / 180)`~~
4. 设置初始值：
   ```yaml
   confidence: 0.75
   confidence_factors:
     source_count: 1
     last_confirmed: <created 日期>
     contradiction_count: 0
     cross_references: <从 index.md 统计引用次数>
   status: active
   ```
   其中用 `cross_references` 从 index.md 初步统计引用次数，而非创建日期。

- [ ] **Step 3: 批量写入（每次 Edit 一个页面）**

使用 Edit 工具逐个页面插入新增字段。

具体操作：在每个页面的 frontmatter 末尾（`tags:` 之后，`---` 之前）插入：

```yaml
confidence: 0.75
confidence_factors:
  source_count: 1
  last_confirmed: <页面自身的 created 日期>
  contradiction_count: 0
  cross_references: <从 index.md 统计值>
status: active
```

- [ ] **Step 4: 更新 stats.md**

在 `stats.md` 中新增两行：

```
| 平均置信度 | -（待 lint 后首次评分） |
| 取代事件数 | 0 |
```

- [ ] **Step 5: 更新 log.md**

追加操作日志：

```
## [2026-06-30] enhance | 阶段 1 元数据增强 - 批量初始化

- 更新 CLAUDE.md：YAML frontmatter 扩展、Query 结晶流程、Lint 扩展
- 更新 ingest skill：支持新 frontmatter 字段、增量更新
- 更新 lint skill：置信度评分、取代检测、结晶后处理
- 创建取代日志：`supersession-log.md`
- 批量初始化 N 个页面：补充 confidence / confidence_factors / status 字段
```

---

### Task 6: 验证完整性

**Files:**
- Read: `CLAUDE.md`, `.claude/skills/llm-wiki-ingest/SKILL.md`, `.claude/skills/llm-wiki-lint/SKILL.md`, 更新的页面样本

- [ ] **Step 1: 验证 CLAUDE.md**

确认三处修改正确：
- YAML frontmatter 扩展定义完整
- Query 工作流包含结晶检查步骤
- Lint 工作流包含置信度评分、取代检测、结晶后处理

- [ ] **Step 2: 验证 ingest skill**

确认两处修改正确：
- 来源页模板包含新 frontmatter 字段
- 新增"增量字段更新"步骤

- [ ] **Step 3: 验证 lint skill**

确认三处修改正确：
- 置信度批量评分步骤完整
- 取代检测步骤完整
- 结晶后处理步骤完整

- [ ] **Step 4: 验证 supersession-log.md**

确认文件存在、格式正确、frontmatter 完整。

- [ ] **Step 5: 抽样检查页面更新**

随机读取 3-5 个更新后的页面，确认新字段存在且格式正确。
