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

- ✅ 按固定顺序编排各子 skill：身份锚定 → 管线 → plan 表 → 检查进度 → 批量提取（含验证与索引）→ 复查完成情况
- ❌ 不重复实现各子 skill 的内部逻辑，只读取并执行对应 SKILL.md 的 workflow
- ❌ 跳过任意步骤（除非用户明确要求）
- ✅ 静默执行：除非遇到问题（身份无法确认、plan 表为空等），不向用户展示中间结果或要求确认

## 固化规则

1. **多链接处理全部委托 clinical-extractor**：待处理 URL 一次性传入 extractor，由其内部完成并行提取、data-verify 验证、indexer 归档。
2. **完成判断以脚本为准**：`check_plan_progress.py` 按"plan 表 URL → raw source 匹配 → summary 引用 → verification"三级判断每个 URL 状态，不猜文件名。
3. **静默执行**：重复来源由 extractor 静默跳过（不询问）；"已提取未生成summary" / "未审核"行不重跑，记入失败项报告人工处理；仅在身份无法确认、plan 表为空时停下询问。
4. **搜不到药物身份就停**：沿用 data-search Step 1 规则，不猜测。

## Step 1: 药物身份锚定

读取 `../drug-identity/SKILL.md`，按其中 workflow 执行，获取该药品的标准身份对象（drug_id、drug_aliases、target、companies、molecule_type；drug 展示名从 drug_aliases 选取）。

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

## Step 5: 检查 plan 表进度并批量提取

### 5.1 运行进度检查脚本

```bash
python3 {skill_dir}/scripts/check_plan_progress.py --config ../config.yaml --plan drug/temp/search_plan_{drug_id}_{date}.md
```

脚本输出每个 URL 的状态：

```text
plan 表进度：
- {url}: 已完成 / 未提取 / 已提取未生成summary / 未审核

待处理 URL（传给 clinical-extractor）：
- {未提取 的 URL 列表}

失败项（报告人工处理）：
- {已提取未生成summary / 未审核 的 URL 列表}
```

### 5.2 调用 clinical-extractor 提取待处理 URL

读取 `../clinical-extractor/SKILL.md`，把脚本输出的**待处理 URL**（未提取）作为多链接输入一次性传入，按其中 workflow 完整执行：

- 多链接的并行提取、data-verify 验证、indexer 归档都由 clinical-extractor 内部处理，本 skill 不重复实现
- clinical-extractor 完成：每个 URL 的 raw/ + summary/，全部 summary 经 data-verify 验证（含 FAIL 回修），并调用 clinical-indexer 归档
- 收集 clinical-extractor 的返回结果（提取数、验证汇总、归档结果、失败项）

## Step 6: 复查完成情况

再次运行 Step 5.1 的进度检查脚本，确认 plan 表剩余行状态：

```text
- "未提取" → 重新传给 clinical-extractor 再次提取
- "已提取未生成summary" / "未审核" → 不重跑，记入最终报告的失败项，留待用户人工处理
- "已完成" → 该行完成
```

- 全部行"已完成"：删除 plan 表文件（`drug/temp/search_plan_{drug_id}_{date}.md`），进入 Step 7 输出报告。
- 仍有"未提取"行：重复执行 Step 5.2 提取，再复查。
- 存在"已提取未生成summary" / "未审核"行：不重跑（extractor 静默模式对重复来源一律跳过），记入失败项，进入 Step 7。

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

clinical-extractor 内部处理：修正 2 次仍 FAIL 后，报告该行失败并留给用户人工处理，继续处理其他行；drug-build 的 Step 6 复查脚本会把"已提取未生成summary" / "未审核"行记入失败项，不重跑（extractor 静默模式对重复来源一律跳过），最终报告列出。

### Q: 重复来源在静默模式下如何处理？

extractor 多来源静默模式下，重复来源一律跳过，不询问、不重新提取。drug-build 的重跑只覆盖"未提取"行；需要修复已提取但未审核的 summary 时，由用户人工处理。
