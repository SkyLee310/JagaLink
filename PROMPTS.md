# PROMPTS.md — Coding Agent 通用 Prompt 模板

**现有文件：** `docs/PROBLEM_STATEMENT.md`、`docs/PRD.md`、`docs/TECH_SPEC.md`

把 `【】` 里的内容换成你的项目实际内容。

---

## 0. 生成 AGENTS.md（第一步）

```
读 docs/PROBLEM_STATEMENT.md、docs/PRD.md、docs/TECH_SPEC.md。

根据这些文档，在 repo root 生成一份 AGENTS.md，包含：
- 项目一句话简介
- Tech stack（从 TECH_SPEC 提取）
- 常用命令（dev / build / test / lint）
- Coding conventions
- 一条规则：开始任何功能前先读 docs/ 底下所有文件
- Don't 清单：不要擅自新增 dependency、不要动范围外的文件、
  不要改 docs/ 里已定的产品行为

写完先给我看，我确认后才存档。
```

> 注意：如果 repo 里同时有 CLAUDE.md 和 AGENTS.md，Claude Code 默认只读 CLAUDE.md。
> 要么只留 AGENTS.md，要么在 CLAUDE.md 第一行写 `@AGENTS.md`。

---

## 1. 补齐缺失的文档（DECISIONS + TASKS）

```
读 docs/ 底下全部文件。

现在帮我生成两份文件：

A) docs/DECISIONS.md — 已拍板、agent 不可擅改的规则
   - 从 PRD 和 TECH_SPEC 里提取所有已经定下的产品行为和技术选择
   - 每条给编号（D-01, D-02...）、决策内容、原因、状态（✅ 已定 / ⏳ 待定）
   - 按类别分组
   - 文档里没明确写、但实作时一定要定的事项，标 ⏳ 列出来

B) docs/TASKS.md — milestone 拆解
   - 每个 milestone 必须是能跑起来的纵向切片，不是「先写完所有后端」
   - 每个任务给编号和完成标准
   - 预留 owner 栏位

先给我看，不要直接写文件。
```

---

## 2. 验证文档有被读到

```
读 AGENTS.md 和 docs/ 底下所有文件，用你自己的话回答：

1. 这个项目是做什么的？目标用户是谁？
2. DECISIONS.md 里哪几条是你绝对不能改的？
3. 下一个该做的任务是什么？
4. 文档里有哪些地方不清楚、互相矛盾，或缺了你实作时会需要的信息？

先不要写代码。
```

> 答错或说找不到文件，先解决加载问题。Claude Code 里用 `/memory` 确认文件在列表中。

---

## 3. Milestone — Plan 阶段

```
读 AGENTS.md 和 docs/ 全部文件。

我们现在做 【M1 — 任务名称】。

先给我实施计划，不要写代码：
1. 要新增/修改哪些文件（列出路径）
2. 数据层需要什么变更（schema / migration / 类型定义）
3. 这个 milestone 碰到 DECISIONS.md 哪几条，你打算怎么遵守
4. 有哪些边界情况和风险
5. 建议拆成几个 commit

计划我确认后才动手。
```

---

## 4. Milestone — 执行

```
计划确认，开始实作 【M1】。

要求：
- 严格按刚才的计划，范围外的文件不要动
- 不要新增 AGENTS.md 没列的 dependency
- 数据库变更写成 migration 文件
- 做完跑 lint 和 build 确认没报错

完成后告诉我要怎么手动验收。
```

---

## 5. 验收 / Gap Check

```
对照 docs/PRD.md 里 【M1】 的 acceptance criteria，逐条检查目前实作：

| Criteria | 状态 | 证据（文件 / 函数） |

未满足的列清单并说明原因。先不要修。
```

---

## 6. 收尾（更新文档）

```
【M1】 验收通过，做收尾：

1. 更新 docs/TASKS.md：完成的标 ✅ 加日期
2. 在 docs/PROGRESS.md 追加记录（没有这个文件就建）：
   - 完成了什么
   - 做了哪些实作层面的决定（命名、数据格式、工具函数）
   - ⚠️ 下一个 agent 或下一个 session 需要知道的坑
3. 有新产品决策就提议加进 DECISIONS.md，先给我看再写
4. 建议的 commit message
```

---

## 7. Multi-agent — 分派

**给 Agent A：**
```
读 AGENTS.md 和 docs/。你这轮负责 TASKS.md 里标 @agent-a 的任务。

规则：
- 只做分派给你的任务，标其他 owner 的不要碰
- 开始前把你要改的文件加进 TASKS.md 的 "Files currently being edited"
- 【migration / schema】只由 @agent-a 负责，其他人的需求写进 TASKS.md
- 在 branch 【feat/m1-a】 上工作，不要 merge 别人的分支
- 做完更新 TASKS.md + PROGRESS.md，移除你的 file lock
```

**给 Agent B：** 同上，把 owner、branch 换掉，并加一句：
```
- 不要碰 【migration / schema】，需要变更就写进 TASKS.md 由我转交
```

---

## 8. Multi-agent — 接手别人的工作

```
读 docs/PROGRESS.md 最近的记录，特别注意 ⚠️ 标记。
再读 docs/TASKS.md 确认现状。

告诉我：
1. 另一个 agent 建立了哪些约定，我要沿用什么
2. 有没有未完成或被 block 的东西
3. 我这轮该做什么

等我确认再开始。
```

---

## 9. 需求变更

```
产品决策变了：【新的决策内容】

按顺序做：
1. 先更新 docs/DECISIONS.md（改状态、写明做法和原因、Changelog 加一行）
2. 检查 PRD 和 TECH_SPEC 有没有要同步改的地方
3. 列出受影响的既有代码
4. 文档改完给我看，确认后才改代码
```

---

## 10. Debug（卡住时）

```
问题：【具体症状，包含预期行为和实际行为】

按这个顺序处理，不要先猜：
1. 复述你理解的问题
2. 列出 3 个最可能的原因，各自说怎么验证
3. 从最可能的开始逐一验证，把结果告诉我
4. 找到根因才提修复方案

不要一次改多个地方。
```

---

## 11. 定期健检（每 2–3 个 milestone）

```
做一次项目健检，只报告不要修：

1. 对照 DECISIONS.md，有没有规则在代码里被违反
2. 有没有 secret / API key 泄漏到 client side
3. 权限和数据访问控制有没有遗漏
4. TASKS.md 状态和实际代码是否一致
5. 有没有 dead code 或已废弃的文件
6. 文档和实作有没有脱节
```

---

## 常用小 prompt

| 用途 | Prompt |
|---|---|
| 确认文档载入 | `你现在的 project instructions 来自哪些文件？` |
| 防范围蔓延 | `只改我指定的文件，其他一律不要动。` |
| 要它先问 | `动手前有任何不确定先问我，不要自己假设。` |
| 清 context | `/clear` 后重新贴 Plan prompt |
| 存教训 | `把这次的教训加进 docs/PROGRESS.md 的 ⚠️ 区块` |
| 换模型前交接 | `总结目前进度和未完成事项，写成一段可以直接贴给另一个 session 的交接说明` |
