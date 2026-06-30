# 自动化与自愈增强 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加自动化钩子（自动上下文加载、定时 lint）+ 升级 lint 为自愈模式（自动修复孤立页面、断裂链接、矛盾裁决）

**Architecture:** 通过 settings.json hook 实现自动加载，CronCreate 实现定时 lint，扩展 lint skill 加入自愈步骤

**Tech Stack:** Markdown, YAML, Claude Code settings.json, Claude Code cron

## Global Constraints

- `10-原始资料/` 下文件永不修改
- 所有知识库文件在 `20-知识库/XX-分类/` 下
- settings.json 修改只做最小必要变更
- 自愈操作必须可追踪（在 log 中记录自动修复）

---

### Task 1: 创建 settings.json hook — 自动上下文加载

**Files:**
- Create or Modify: `.claude/settings.json`

- [ ] **Step 1: 检查是否有现有 settings.json**

```bash
cat .claude/settings.json 2>/dev/null || echo "文件不存在"
```

- [ ] **Step 2: 写入 settings.json 配置**

```json
{
  "onSessionStart": [
    {
      "prompt": "我是 nongbaoyun 知识库的自动启动检查。请用中文做三件事：（1）读取 20-知识库/00-索引/log.md 的最后 5 条记录，了解最近动态；（2）检查 00-收件箱/ 中是否有待处理的文件；（3）读取 20-知识库/00-索引/stats.md 的一行摘要。完成后用一两句话告诉我当前 vault 状态即可，不要展开。如果收件箱有文件，问我要不要处理。"
    }
  ]
}
```

---

### Task 2: 设置定时 lint

**Files:**
- No file changes — uses CronCreate

- [ ] **Step 1: 创建每周 lint 定时任务**

使用 CronCreate 设置每周自动 lint：
- 时间：每周一上午 9:03（避开整点）
- Prompt：执行 llm-wiki-lint 对知识库进行健康检查，如果发现问题摘要报告，无问题静默完成
- 注意：设定 recurring: true, durable: true（跨会话持久）

---

### Task 3: 更新 CLAUDE.md — 新增自动化章节 + Lint 升级

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 读取当前 CLAUDE.md**

Read `CLAUDE.md` 全文。

- [ ] **Step 2: 在三大核心工作流之后、文件操作守则之前，插入自动化章节**

插入以下内容：

```
## 自动化

### 自动上下文加载

每次 Claude Code 在 vault 中启动时，自动执行：
- 读取最近 5 条操作日志
- 检查 `00-收件箱/` 中是否有待处理文件
- 读取 `stats.md` 摘要

### 定时 lint 检查

- 频率：每周自动执行一次 lint 检查
- 结果：有问题则主动报告，无问题则静默更新

### 主动提醒

- 收件箱中有新文件时主动询问是否处理
- 检测到 `fading` 页面时提醒是否更新
```

- [ ] **Step 3: 升级 Lint 工作流标题和描述**

将 Lint 工作流的描述从"检查"升级为"检查与自愈"：

```
### 3️⃣ 检查与自愈 (Lint + Self-heal)

当用户要求对知识库进行健康检查、审计或维护 review 时（如"检查"、"lint"、"审计"、"健康检查"、"整理知识库"），自动调用 `llm-wiki-lint` skill 执行检查与自愈。

检查结果以报告形式输出，包含自动修复的内容和仍需人工处理的问题。
```

---

### Task 4: 改造 lint skill — 增加自愈步骤

**Files:**
- Modify: `.claude/skills/llm-wiki-lint/SKILL.md`

- [ ] **Step 1: 读取当前 lint skill**

Read `.claude/skills/llm-wiki-lint/SKILL.md` 全文。

- [ ] **Step 2: 在孤立页面检测后增加自动修复步骤**

找到 `### 5. Check for Orphan Pages` 部分，在现有脚本之后追加自动修复逻辑：

```
#### 5a. 孤立页面自动修复

对上一节发现的孤立页面，执行自动修复：

1. 对每个孤立页面，读取其标题和正文前 200 字，确定主题
2. 在全 vault 中搜索包含相同关键词的页面
3. 在匹配页面中找到最合适的位置，添加 `[[孤立页面名]]` 链接
4. 如果找不到合适的匹配页面，在孤立页面末尾添加 `## 待链接` 区段
5. 在报告中记录：已修复 N 个、无法修复 M 个及其原因
```

- [ ] **Step 3: 在断裂链接检查后增加自动修复步骤**

找到 `### 6. Check for Missing Concept Pages` 部分，在现有脚本之后追加：

```
#### 6b. 断裂链接自动修复

对上一节发现的断裂链接（指向不存在页面的 `[[链接]]`）：

1. **别名匹配**：检查链接文本是否与某个已有页面的 title 或 alias 匹配
   - 如果匹配 → 自动修正链接路径为标准格式
2. **频繁引用自动创建**：同一断裂链接被引用 ≥3 次
   - 自动创建目标页面，补充基本 frontmatter 和结构
   - 在页面中添加"自动创建"标记和引用来源
3. **低频断裂记录**：引用 1-2 次的断裂链接
   - 记录到 lint 报告，标注"低优先级"
```

- [ ] **Step 4: 在矛盾检测后增加裁决步骤**

找到 `### 3. Check for Contradictions` 部分，在现有脚本之后追加：

```
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
```

---

### Task 5: 验证完整性

**Files:**
- Read: 所有修改的文件

- [ ] **Step 1: 验证 settings.json**

确认 `onSessionStart` hook 配置正确、JSON 格式有效。

- [ ] **Step 2: 验证 CLAUDE.md**

确认自动化章节存在、Lint 工作流标题已升级。

- [ ] **Step 3: 验证 lint skill**

确认自愈步骤 3a、5a、6b 存在且内容完整。

- [ ] **Step 4: 更新 log**

追加操作日志条目。
