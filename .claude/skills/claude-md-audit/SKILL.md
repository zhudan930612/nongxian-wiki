---
name: claude-md-audit
description: 扫描 CLAUDE.md 内容，按 Skills/Hooks/Settings/Agents/Commands/Conventions 六个维度分类，建议哪些内容应提取到外部文件，以精简 CLAUDE.md 核心配置。
---

# CLAUDE.md 审查技能

## When to Use

当用户要求对 `CLAUDE.md` 进行结构审计、审查配置、或精简 `CLAUDE.md` 时使用。此技能**仅生成建议报告，不执行任何修改**。

Common trigger phrases:
- "审查配置"
- "审查 claude.md"
- "审查"
- "claude.md 审查"
- "精简 claude.md"
- "检查 claude.md"
- "claude.md 审计"

Always read `CLAUDE.md` first if it exists, as it may override this skill.

## Audit Workflow

Execute the following steps in order. This skill is **read-only** — it never modifies any file.

### 1. Read CLAUDE.md

- Read the full `CLAUDE.md` file
- If `CLAUDE.md` does not exist or is empty → report "无内容可审查" and exit
- Count total lines as baseline

### 2. Parse Sections by Heading

Split the content by `##` headings. For each section:

- Record heading name, line range, and content length
- Identify sub-headings (`###`) within each section
- Note any inline code blocks, lists, or tables

### 3. Classify Each Section Against 6 Dimensions

For each section, determine which dimension(s) it belongs to, or mark as "core retain":

| 维度 | 检测标志 | 建议去向 |
|------|---------|---------|
| **📦 Skills** | 详细工作流步骤、执行规范（如"步骤1-3"）、操作指令、触发条件 | `.claude/skills/<name>/SKILL.md` |
| **⚡ Hooks** | SessionStart/SessionStop 自动行为、启动检查、定时提醒 | `.claude/hooks/` + `settings.json` |
| **🔧 Settings** | 权限规则、环境变量、行为开关、路径白名单 | `.claude/settings.json` |
| **🤖 Agents** | Agent 角色定义、专用指令集、分工描述 | `.claude/agents/<name>.md` |
| **📎 Commands** | Slash 命令、快捷操作、宏定义 | `.claude/commands/` |
| **📄 Conventions** | 约定规范、操作守则、命名规则、最佳实践 | `20-知识库/06-元/06-约定/` |
| **💎 Core** | 仓库架构定义、不可变 schema、核心配置 | 保留在 CLAUDE.md |

Classification rules:
- A section can match **one or more** dimensions (e.g., a workflow description can be both Skills and Conventions)
- Sections with code blocks, numbered lists of steps, or trigger phrases are likely **Skills**
- Sections describing automatic behavior at startup/stop are likely **Hooks**
- Sections enumerating "do" and "don't" rules are likely **Conventions**
- Sections defining directory structure, YAML schema, immutable rules → **Core**

### 4. Cross-Reference External Files

For sections classified as Skills/Hooks/Settings/Agents/Commands:

- Check if the corresponding external file already exists
- If it exists, read the external file and compare:
  - **Consistency**: Is the content aligned between CLAUDE.md and the external file?
  - **Redundancy**: Is there significant duplication? Estimate overlap percentage
  - **Outdatedness**: Does one version have content the other lacks?
- If it doesn't exist, note "外部文件尚未创建"

For sections classified as Conventions:

- Check if a corresponding wiki page exists in `20-知识库/06-元/06-约定/`
- Same consistency/redundancy/outdatedness check as above

For sections classified as Core:

- Verify that the content is truly unique to CLAUDE.md and not duplicated elsewhere

### 5. Check Cross-Section Dependencies

Identify if any section references definitions from another section:
- Example: "Ingest 阶段详见 [[forward-reference-convention]]" → the reference target may also be extractable
- If two sections have a dependency, note "建议一起提取"

### 6. Generate Audit Report

Output the report directly in the conversation. Use the following format:

```
┌─ CLAUDE.md 审查报告 ─────────────────────────┐
│                                                │
│  📊 总览                                       │
│     总行数: XXX 行                              │
│     核心保留: XX 行 (XX%)                      │
│     建议提取: XX 行 (XX%)                      │
│                                                │
│  📦 Skills 可提取 (XX行)                       │
│    ├ "章节标题" → 建议去向                      │
│    │   理由 / 与外部文件对比结果                 │
│    └ "章节标题" → 建议去向                      │
│                                                │
│  📄 Conventions 可迁移 (XX行)                  │
│    ├ "章节标题" → 20-知识库约定页面              │
│    └ "章节标题" → 20-知识库约定页面              │
│                                                │
│  ⚡ Hooks 可注册 (XX行)                        │
│                                                │
│  🔧 Settings 可配置 (XX行)                     │
│                                                │
│  🤖 Agents 可定义 (XX行)                       │
│                                                │
│  📎 Commands 可注册 (XX行)                     │
│                                                │
│  ⚠️ 注意事项                                    │
│    ├ 内容重复 / 不一致 / 过时提醒                │
│    ├ 跨段落依赖提醒                              │
│    └ 其他异常                                   │
│                                                │
│  💡 建议保留的核心内容                          │
│    ├ 保留项清单                                 │
│    └ 精简后的 CLAUDE.md 预估行数                │
│                                                │
└────────────────────────────────────────────────┘
```

### 7. Summarize Recommendations

After the report, provide a brief natural language summary:

- What's the biggest win? (e.g., "移除三大工作流后可精简 40% 内容")
- What to do first? (prioritized extraction order)
- Any risks or notes (e.g., "需要同步更新 skills 文件中的引用")

## Boundary Conditions

- **CLAUDE.md 不存在或为空** → 报告无内容可审查，退出
- **无对应外部文件** → 仅标注分类建议，跳过交叉检查
- **跨段落依赖** → 标注"建议一起提取"
- **内容已存在于外部文件但 CLAUDE.md 未删除** → 标注为"重复"并给出清理建议
- **外部文件内容比 CLAUDE.md 更完整** → 标注为"CLAUDE.md 版本过时"
- **CLAUDE.md 和外部文件内容冲突** → 标注为"矛盾"并说明差异

## Output Convention

- 报告输出在对话中（不写入文件）
- 使用 Markdown 格式，便于阅读
- 所有路径引用使用 Wiki 链接格式
- 报告末尾提供清晰的优先级建议
