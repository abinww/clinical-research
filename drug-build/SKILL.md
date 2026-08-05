---
name: drug-build
description: |
  创新药数据库建库编排。当用户提到以下关键词时触发：
  - "对{药品}建库"
  - "建库"
  本 skill 编排 drug-trials-search、data-search、clinical-extractor 完成完整建库。多链接的提取、验证与索引归档由 clinical-extractor 内部处理。
---

# 创新药建库编排

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 职责：为指定创新药建立完整的临床数据库条目，包括管线表、已公布临床数据摘要、验证和索引归档。

## 执行约束

- ✅ 按固定顺序编排各子 skill：身份锚定 → 管线 → plan 表 → 批量提取（含验证与索引）→ 检查完成情况
- ❌ 不重复实现各子 skill 的内部逻辑，只读取并执行对应 SKILL.md 的 workflow
- ❌ 跳过任意步骤（除非用户明确要求）
- ✅ 静默执行：除非遇到问题（身份无法确认、plan 表为空等），不向用户展示中间结果或要求确认

## 固化规则

1. **多链接处理全部委托 clinical-extractor**：待处理 URL 一次性传入 extractor，由其内部完成并行提取、data-verify 验证、indexer 归档。
2. **完成情况检查**：Step 6 在 extractor 执行后检查 plan 表每行是否已生成并验证通过的 summary，未完成行重新传给 extractor，全部完成后删除 plan 表。
3. **静默执行**：Step 4 保存 plan 表后直接继续，不要求用户确认；仅在有问题时停下询问。
4. **搜不到药物身份就停**：沿用 data-search Step 1 规则，不猜测。

## Step 1: 药物身份锚定

读取 `../data-search/SKILL.md`，按其中 Step 1 执行：

- 搜索 `{代号} + 公司名`、`{代号} + clinical trial`
- 收集别名全集（研发代号、合作方代号、通用名、商品名）
- 确定 `drug_id`、target、公司、分子类型

如果无法确认药物身份，停下返回用户确认，不进入后续步骤。

## Step 2: 临床试验注册查询

读取 `../drug-trials-search/SKILL.md`，按其中 workflow 执行：

- 查询该药品在 ClinicalTrials.gov 的全部试验
- 写入 `drug/{drug_id}.md` 的 `## 当前临床管线` 章节（新建或更新）

## Step 3: 搜索已公布临床数据

读取 `../data-search/SKILL.md`，按其中 workflow 执行：

- 分层搜索（注册库、公司渠道、学术会议、期刊、媒体线索）
- 内容判断与去重，输出 plan 表

## Step 4: 保存 plan 表

将 plan 表保存到 `drug/temp/search_plan_{drug_id}_{date}.md`。

静默执行，不向用户展示 plan 表，除非有问题才停下询问（如 plan 表为空、身份无法确认）。保存后直接进入 Step 5。

## Step 5: 调用 clinical-extractor 批量提取

读取 `../clinical-extractor/SKILL.md`，把 plan 表中的全部 URL 作为多链接输入一次性传入，按其中 workflow 完整执行：

- 多链接的并行提取、data-verify 验证、indexer 归档都由 clinical-extractor 内部处理，本 skill 不重复实现
- clinical-extractor 完成：每个 URL 的 raw/ + summary/，全部 summary 经 data-verify 验证（含 FAIL 回修），并调用 clinical-indexer 归档
- 收集 clinical-extractor 的返回结果（提取数、验证汇总、归档结果、失败项）

## Step 6: 检查完成情况

对 plan 表每一行，检查对应的 summary 是否已生成且验证通过：

```text
- 每行的 summary 路径为 summary/{drug_id}/{drug_id}@{indication_id}@{source_label}.md
- 若该 summary 已存在且 verification: passed → 该行已完成
- 若该 summary 不存在或未验证通过 → 该行未完成
```

处理结果：

- **存在未完成行**：把未完成行的 URL 重新传给 clinical-extractor（按 Step 5 重复执行），完成后再次检查；仍未完成的记入最终报告的失败项。
- **全部行已完成**：删除 plan 表文件（`drug/temp/search_plan_{drug_id}_{date}.md`），进入 Step 7 输出报告。

## Step 7: 输出报告

```text
drug-build 完成：
- 药品: {drug_id} ({drug})
- 别名全集: {列表}
- 管线表: drug/{drug_id}.md（CTG 试验 N 个）
- plan 表: drug/temp/search_plan_{drug_id}_{date}.md（M 行）
- 提取: 成功 X 个 / 失败 Y 个 / 跳过 Z 个
- 验证: PASS/WARN/FAIL 汇总
- 索引: drug/ 与 indication/ 归档结果
- 人工复核项: （WARN 列表；如有）
- 失败项: （列表及原因；如有）
```

## 常见问题

### Q: 为什么不需要在 drug-build 里管理多链接并发？

多链接的提取与验证并发全部在 `clinical-extractor` 内部处理（每轮 ≤5 个并发子 agent，OpenClaw 默认 `maxChildrenPerAgent=5`）。drug-build 只负责把 plan 表全部 URL 传入，保持编排职责单一。

### Q: 提取阶段未验证的 summary 已写入 summary/？

`clinical-indexer` 只接受 `verification: passed` 的 summary，未验证文件会被跳过，无副作用。验证完成后即满足归档条件。

### Q: 某行反复 FAIL 怎么办？

clinical-extractor 内部处理：修正 2 次仍 FAIL 后，报告该行失败并留给用户人工处理，继续处理其他行；drug-build 的 Step 6 会把该行记入失败项，最终报告列出。
