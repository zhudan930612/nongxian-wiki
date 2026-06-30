---
title: LLM Wiki v2 增强设计
created: 2026-06-30
updated: 2026-06-30
tags: [system, design, convention]
---

# LLM Wiki v2 增强设计

> 基于 [LLM Wiki v2](https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2) 的理念，对当前知识库进行系统性增强。本文档为阶段 1 的详细设计。

## 背景

当前 vault 已实现 Karpathy 原始 LLM Wiki 三层架构的最小可行版本（三层架构 + Ingest/Query/Lint 三大工作流）。LLM Wiki v2 提出了多项增强方向，本设计从中选取第一阶段需要落地的三个核心能力：

1. **置信度评分** — 让知识有"保鲜期"，量化可信度
2. **取代机制** — 新旧信息变更时有迹可循
3. **结晶机制** — 自动沉淀每次有价值的讨论

---

## 一、YAML 元数据扩展

### 新增字段

所有知识库页面（实体、概念、主题、问答）新增以下 frontmatter 字段：

```yaml
---
title: 页面标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [tag1, tag2]
source: 10-原始资料/.../xxx.pdf       # 来源页专有
confidence: 0.85                        # 总体置信度 [0.0, 1.0]
confidence_factors:                      # 评分明细
  source_count: 8                        # 支持此页面的来源数
  last_confirmed: 2026-06-30             # 最近一次确认日期
  contradiction_count: 0                 # 矛盾数
  cross_references: 5                    # 引用数
supersedes: []                           # 取代的旧页面
superseded_by: []                        # 被哪些新页面取代
status: active                           # active / fading / superseded / archived
crystallized_from: query                 # 结晶来源（结晶页专有）
session_summary: true                    # 是否来自完整会话（结晶页专有）
---
```

### 字段说明

| 字段 | 适用页面 | 必填 | 说明 |
|------|---------|------|------|
| `confidence` | 实体/概念/主题/问答 | optional | 0.0-1.0 浮点数，lint 时计算 |
| `confidence_factors` | 同上 | optional | 评分明细，含 source_count/last_confirmed/contradiction_count/cross_references |
| `supersedes` | 所有 | optional | 被此页面取代的页面路径列表 |
| `superseded_by` | 所有 | optional | 取代此页面的页面路径列表 |
| `crystallized_from` | 问答页 | optional | 结晶来源：query/session/ingest-auto |
| `session_summary` | 问答页 | optional | 是否为完整会话摘要 |

### status 字段扩展

原有 `status` 字段可选值从 `draft/active/archived` 扩展为：

```
active     → 活跃，正常参与查询
fading     → 超过 180 天未确认，可被引用但优先级低
superseded → 已被新页面取代，仅查询历史时展示
archived   → 归档，基本不参与查询
draft      → 草稿，未完成
```

---

## 二、置信度评分机制

### 评分模型

| 维度 | 计算方式 | 权重 | 更新时机 |
|------|---------|------|---------|
| **来源数** | `min(source_count / 5, 1.0)` — 5 来源满分 | 30% | 实时增量 |
| **时效性** | `max(0, 1 - days_since_last_confirmed / 180)` — 180 天衰减至 0 | 25% | lint 批量 |
| **矛盾数** | `max(0, 1 - contradiction_count × 0.2)` — 每个 -0.2 | 20% | lint 批量 |
| **引用数** | `min(cross_references / 3, 1.0)` — 3 引用满分 | 15% | 实时增量 |
| **完成度** | 页面内容结构完整度（有正文 + 有链接 + 有 frontmatter） | 10% | lint 批量 |

**实时更新规则**（ingest/结晶时触发）：

- `source_count++`：新来源引用此页面时
- `cross_references++`：新页面链接到此页面时
- `last_confirmed`：设为当前日期

**批量更新规则**（lint 时触发）：

- 时效性：全量重算所有页面
- 矛盾数：跨页面扫描后更新
- 完成度：检查内容完整性
- 最终置信度：按各维度加权求和

### 状态自动流转

```
active ──(last_confirmed > 180 天)──→ fading ──(last_confirmed > 365 天)──→ archived
active ──(被 superseded_by 引用)──────→ superseded
```

---

## 三、取代机制

### 取代操作记录

新增 `20-知识库/00-索引/supersession-log.md`，格式：

```markdown
## [YYYY-MM-DD] 取代类型
- `旧页面路径` → `新页面路径`
  - 原因：...
  - 置信度变化：X → Y
```

### Lint 中的取代检测

执行 lint 时：

1. 遍历所有页面，检查 `superseded_by` 字段
2. 如果 `superseded_by` 指向的页面存在且 `status: active`，将当前页面设为 `status: superseded`
3. 检查 `status: superseded` 的页面是否还被其他活跃页面引用 → 报告过时引用
4. 检查取代链是否形成循环 → 报告异常

### 查询时的处理

- 默认查询：仅返回 `status: active` 的页面
- 明确搜索历史时：可包含 `superseded` 和 `fading` 页面
- 结果排序：置信度降序

---

## 四、结晶机制

### 流程

在 Query 工作流中嵌入结晶步骤：

```
当前流程：
  用户提问 → 搜索知识库 → 综合回答 → [结束]

改造后流程：
  用户提问 → 搜索知识库 → 综合回答
    → 评估回答质量（触发条件自动判断）
    → 如果触发：创建结晶记录
      → 抽取事实原子（写入结晶页的 ## 待确认事实 区块）
      → 更新相关页面的置信度（增量实时更新）
    → 如果不触发：正常结束
```

### 触发条件（满足任一即可）

| 条件 | 判定方式 |
|------|---------|
| **综合性** | 回答涉及 3 个以上不同来源 |
| **新颖性** | 回答中包含知识库现有页面未覆盖的结论 |
| **时效性** | 回答涉及当前项目关键决策或方向 |
| **频率** | 同一类型问题被多次询问 |

### 结晶产物

**1. Q&A 归档页**（`20-知识库/05-问答/YYYYMMDD-标题.md`）：

```yaml
---
title: 保险公司核心痛点
created: 2026-06-30
updated: 2026-06-30
tags: [qa, insight]
confidence: 0.75
confidence_factors:
  source_count: 3
  last_confirmed: 2026-06-30
  contradiction_count: 0
  cross_references: 0
crystallized_from: query
---
```

**2. 事实原子**（放在结晶页的单独区块）：

```markdown
## 待确认事实

> 以下事实来自本此结晶，尚未写入实体/概念页面，lint 时确认吸收。

- **事实**：浙江太保连续八年亏损
  - 类型：组织事实
  - 来源：[[07-会议沟通/20260508-农险&浙江太保沟通]]
  - 目标页面：[[01-实体/客户现状/浙江太保]]
  - 置信度影响：+0.05
```

### Lint 中的后处理

1. 遍历 `05-问答/` 中 `status: active` 且含 `## 待确认事实` 的页面
2. 将事实原子合并到对应的实体/概念/主题页
3. 合并成功后，将结晶页的 `## 待确认事实` 改为 `## 已吸收事实`
4. 如果事实已被完全吸收，结晶页可设 `status: absorbed`
5. 统计吸收率：已吸收 / 总结晶，监控知识库健康状况

---

## 五、CLAUDE.md 修改要点

### 需修改的部分

1. **YAML frontmatter 规范** — 更新页面规范章节，加入新字段定义
2. **Query 工作流** — 嵌入结晶检查步骤
3. **Lint 工作流** — 增加置信度评分、取代检测、结晶后处理子步骤
4. **迭代原则** — 可补充一行说明置信度的意义

### 不需修改的部分

- 目录结构不变
- 命名约定不变
- 文件操作守则不变
- Ingest 主流程不变（仅增加 frontmatter 字段写入）

---

## 六、实施范围总结

| 模块 | 涉及文件 | 改动量 |
|------|---------|--------|
| YAML 扩展 | CLAUDE.md | 小（增加字段定义） |
| 置信度评分 | CLAUDE.md + ingest skill + lint skill | 中（评分逻辑 + lint 新增步骤） |
| 取代机制 | CLAUDE.md + supersession-log.md（新建）+ lint skill | 中（取代检测 + 日志） |
| 结晶机制 | CLAUDE.md + ingest skill | 中（Query 流程改造 + 结晶产出） |
| Lint 后处理 | lint skill | 小（新增结晶吸收步骤） |

所有改动均在现有文件架构内，不引入外部依赖。
