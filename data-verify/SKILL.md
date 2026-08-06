---
name: data-verify
description: |
  数据一致性审核工具。当用户提到以下关键词时触发：
  - "验证这个summary"
  - "审核summary"
  - "检查summary数据"
  也可由 clinical-extractor / drug-build 编排调用。
---

# 数据一致性审核

> 本文件由 clinical-research/SKILL.md 路由后读取执行，或由 clinical-extractor / drug-build 编排调用。
> 职责：验证 summary 文件中的临床数据是否全部来源于对应 raw 文件，并把审核结果写入 summary 文件末尾。
> 本 skill 只修改 summary 的审核章节和 verification 字段，不碰正文，不联网，不评价临床价值。

## 执行约束

- ✅ 输入：一个 summary 文件 + 其对应的 raw 文件
- ✅ 支持批量派发：由一个 verifier 子 agent 负责多个 summary 时，对每个 summary **独立执行**全部步骤（定位文件 → 逐项核对 → 写入审核结果）
- ✅ 从 summary 的 `> 来源原文: [[raw/{文件}.md]]` 定位 raw 文件
- ✅ 按 `schema/summary-spec.md` 的"数据一致性审核"规则逐项核对
- ✅ 只修改 summary 末尾的 `## 数据一致性审核` 章节和 YAML 的 `verification` / `verification_fail_count` 字段（需要该 summary 文件的写权限）
- ❌ 不修改 summary 正文（核心数据、图片、试验设计、专家点评等章节）
- ❌ 不联网
- ❌ 不补充新数据
- ❌ 不评价临床价值
- ❌ 不基于常识、外部知识或推测判定为通过

## Step 1: 定位文件

从用户输入或调用方获得 summary 文件路径。

读取 summary 文件，从正文中提取：

```text
> 来源原文: [[raw/{raw文件名}.md]]
```

得到对应的 raw 文件路径。如果 summary 中没有来源原文行，停止并报告无法定位 raw 文件。

## Step 2: 读取审核规范

读取 `../schema/summary-spec.md`，按其中"数据一致性审核"章节的规则执行。

审核字段包括但不限于：

- 样本量：`N`、`n`
- 疗效：`ORR`、`cORR`、`DCR`、`CR`、`PR`、`SD`、`mPFS`、`rPFS`、`mOS`、`mDoR`、`DoR`
- 统计量：`HR`、`p-value`、`CI`
- 安全性：`AE`、`TEAE`、`TRAE`、`SAE`、`≥3级AE/TEAE/TRAE`、减量、停药、死亡
- 试验信息：phase、trial name、cohort、剂量、治疗组、对照组、适应症、治疗线数、会议/发布日期

## Step 3: 逐项核对

对 summary 中的每一项临床数据和试验事实，在 raw 文件中查找依据：

状态定义：

- `PASS`: `raw/` 中能找到直接证据或明确等价表达，且组别、剂量、单位、时间点一致
- `WARN`: `raw/` 中有近似依据，但组别、单位、时间点、术语或上下文需要人工确认
- `FAIL`: `raw/` 中找不到依据，或发现组别/剂量/单位/时间点对应错误

注意：

- `summary` 中的每一个临床数值都必须有对应审核行
- `summary` 中每一个临床数值、试验事实和关键分组信息都必须能追溯到 `> 来源原文:` 行指向的 raw 文件
- cohort、剂量、治疗组、对照组不能串列
- `TEAE`、`TRAE`、`AE`、`SAE` 不得混用；如原文术语不同，标记 `WARN` 或 `FAIL`
- 时间单位不得擅自转换；如原文为 weeks，summary 写成 months，标记 `FAIL`
- 原文没有的数据不得写成确定数据

## Step 4: 写入审核结果

只做以下两处修改，其余内容一律不动：

1. 在 summary 文件**末尾**写入（或覆盖）`## 数据一致性审核` 章节：

```markdown
## 数据一致性审核

| 数据项 | summary中的值 | raw证据 | 状态 | 问题 |
|------|-------------|---------|------|------|
| ORR | 42.3% | "...ORR was 42.3%..." | PASS | - |
| mPFS | 11.3 | 未找到 | FAIL | raw中未出现该数值 |
| G≥3 TRAE | 25.0% | "...grade 3 or higher TEAEs..." | WARN | raw为TEAE，summary写TRAE |
```

2. 更新 YAML frontmatter 中的审核字段：

- 全部 `PASS`（无 `FAIL`，`WARN` 允许存在）且审核覆盖完整：

```yaml
verification: passed
verification_fail_count: 0
```

- 存在 `FAIL`：

```yaml
verification: failed
verification_fail_count: {FAIL数量}
```

- 存在 `WARN` 但无 `FAIL`：`verification` 仍为 `passed`，但必须在 summary 审核章节的问题列中保留 WARN 项，供调用方/用户人工复核。

## Step 5: 返回状态

审核结果已写入 summary 文件，不需要向用户输出审核报告。返回时只给一行状态：

```text
data-verify: {summary文件名} verification: {passed/failed}（PASS x / WARN y / FAIL z）
```

调用方通过 summary YAML 的 `verification` / `verification_fail_count` 字段读取结果，判断是否需要修正后重新验证。

## 常见问题

### Q: summary 中找不到 `> 来源原文:` 行？

停止并报告无法定位 raw 文件，不进行审核。

### Q: 发现 FAIL 怎么处理？

把 `verification: failed` 和 FAIL 数量写入 YAML。由调用方（extractor 或 drug-build）负责修正 summary 正文后重新调用本 skill 审核。

### Q: 可以修改 summary 正文里的数据吗？

不可以。本 skill 只写审核章节和 verification 字段；数据修正由调用方完成。
