---
title: 知识图谱关系类型
created: 2026-06-30
updated: 2026-07-02
tags: [system, convention, knowledge-graph]
aliases: [关系类型, 图谱关系, relationship types]
---

# 知识图谱关系类型

> 知识图谱使用以下类型化关系连接实体和概念页面，统一存储在 `20-知识库/00-索引/knowledge-graph.md` 中。

## 关系类型表

| 关系 | 反向关系 | 说明 |
|------|---------|------|
| 研究 | 被研究 | 学者/机构研究某概念或主题 |
| 任职于 | 有成员 | 人物属于某组织 |
| 合作 | 合作 | 组织间/人物间合作（双向） |
| 监管 | 被监管 | 监管机构管辖被监管方 |
| 竞争 | 竞争 | 公司间竞争关系（双向） |
| 提供产品 | 使用产品 | 公司提供某产品/平台 |
| 制定政策 | 受政策影响 | 政府制定影响某领域/产品的政策 |
| 隶属 | 有下属 | 组织层级关系 |
| 案例/试点 | 试点参与 | 组织在某地实施试点项目 |
| 关注/痛点 | 是痛点 | 组织面临某问题/风险 |

## 使用说明

- 每条关系记录应包含 `source`、`type`、`target`、`sources` 四个字段
- `source` 和 `target` 使用相对路径格式的页面标识，如 `01-实体/01-易福金`、`02-概念/02-农业保险`，**不带 `[[ ]]` Wiki 链接语法**（知识图谱 YAML 为纯数据）
- 合作和竞争关系应设为 `bidirectional: true`
- 研究、监管等关系一般设为 `bidirectional: false`（单向）
- 关系的 `confidence` 取自来源页置信度的 80%

## 编辑规范

- 新关系追加到 `knowledge-graph.md` 的 `relationships` 列表末尾
- 追加前检查去重（相同的 source + type + target）
- 更新关系时同步更新 `knowledge-graph.md` 中的统计信息

## 相关页面

- [[naming-convention|命名约定]]
- [[forward-reference-convention|前向引用约定]]
