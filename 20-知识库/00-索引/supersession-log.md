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
