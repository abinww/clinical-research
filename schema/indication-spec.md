# 适应症页格式规范 (2.0)

本文件定义 `{research_dir}/indication/{indication_id}.md`。`research_dir` 本身是 Obsidian vault 根目录；适应症页跨公司、跨药品比较已审核的临床数据，所有药品和来源链接均使用完整 vault 路径 wikilink。

## 建档范围

只为明确、可比较的具体适应症建页；治疗线不同通常视为不同适应症。以下探索性泛瘤种不建立适应症页：

- 实体瘤
- 多瘤种
- 泛瘤种
- 晚期实体瘤
- 晚期恶性肿瘤

泛瘤种仍可出现在 summary 的 `indications` 中，但不得自动生成索引页。无法确定治疗线时 `line: null`，不得猜测为 `1L`；是否建页取决于该适应症是否足够明确和可比较。

## 文件命名

- 路径固定为 `{research_dir}/indication/{indication_id}.md`。
- 示例：`NSCLC_1L.md`、`胃癌一线.md`、`HER2阳性乳腺癌.md`。
- 空格和斜杠替换为 `_`，括号移除。
- 推荐线数后缀：一线 `_1L`、二线 `_2L`、三线及以后 `_3L+`、无法细分的后线 `_Later`。
- `indication_id` 必须在全 vault 唯一，并与文件名一致。

## Frontmatter

```yaml
---
indication_id: NSCLC_1L
indication: 非小细胞肺癌一线
category: NSCLC
line: 1L
aliases: [非小细胞肺癌一线, NSCLC一线]
biomarker: null
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

必需字段为 `indication_id`、`indication`、`created`、`updated`。`line` 无法确认时为 `null`。`aliases` 仅维护适应症别名，不维护公司或药品别名。

## 数据来源边界

- 数据对比表、安全性对比和时间线只可来自 summary 的 `indications` 中包含本页 `indication_id`、且一致性审核通过的部分。
- 摘要必须满足 `verification: passed`、`verification_fail_count: 0`、`verification_coverage: complete`、审核章节存在且无 `FAIL`。
- 一个摘要包含多个适应症时，只提取与本页 `indication_id` 对应的正文分组，不得引用其他组的数据。
- 下游匹配假定 summary 的每个 `indications` 对象具有稳定且唯一的 section identity：以该对象的 `indication_id` 作为 `section_id`，并一一对应正文中同序的一个 `## {适应症}` 分组。`section_id` 重复、对象与分组数量/顺序不一致或无法唯一对应时阻断该 summary，不得仅按显示标题模糊匹配。
- 不得直接从 raw、外部网页、注册库、模型记忆或药品页反向补全临床数值。
- 公司展示名和别名从根 `index.md` 解析；不建立 `company.md` 或适应症页局部公司映射。

## 链接规则

适应症页的内部链接必须使用完整 vault 路径 wikilink，避免标准 Markdown 链接被错误地相对于 `indication/` 解析：

```markdown
[[第一三共/DS-8201.md|DS-8201]]
[[第一三共/summary/DS-8201@ASCO2026.md|DS-8201@ASCO2026]]
```

不得使用 `../` 相对路径，不得添加 `research/` 或 `company/` 前缀，也不得省略 `company_id` 或药品页文件名。

wikilink 位于 Markdown 表格单元格时，alias 分隔符 `|` 前必须加反斜杠；位于表格外的来源引用、列表或正文时使用普通 `|`，如上例，不加反斜杠。

## 正文结构

```markdown
# {适应症名称}

## 概述

## 数据对比表

### Phase III

### Phase II

## 安全性对比

## 数据时间线
```

`数据对比表` 只设 Phase III 和 Phase II 两张子表；不设 Phase I 表（人数太少、疗效说服力不足，且多为剂量爬坡）。安全性数据独立成 `安全性对比` 表。所有章节均应保留。

## 概述

```markdown
## 概述

{适应症名称}的治疗现状：

- **标准治疗**：{当前标准治疗方案}
- **未满足需求**：{主要挑战}
- **热门靶点**：{正在研发的靶点}
```

概述中的事实应有明确来源；不得用临床摘要无法支持的模型记忆补全。

## 数据对比表

数据对比表按临床阶段分成 `Phase III` 和 `Phase II` 两张子表，不设 Phase I 表。来源明确为 Phase I 的疗效数据不进对比表，仅进入 `数据时间线`；Phase I/II 合并试验（如剂量递增+扩展）且人数足够视为 Phase II 的，按 Phase II 进入 `Phase II` 子表。

每个由 indexer 写入或更新的来源在本页恰好出现一次 `source_identity` 标记，集中置于 `## 数据对比表` 标题之后的表格之前：

```markdown
<!-- source_identity: {company_id}/summary/{drug_id}@{source_label}.md -->
```

```markdown
## 数据对比表

<!-- source_identity: 第一三共/summary/DS-8201@ASCO2026.md -->
<!-- source_identity: Pfizer/summary/PF-0001@ESMO2025.md -->

### Phase III

| 药品 | 公司 | 用药方案 | 对照 | 分析人群 | 数据截止 | ORR | mPFS (mo) | mOS (mo) | 来源 |
|------|------|----------|------|----------|----------|-----|-----------|----------|------|
| [[第一三共/DS-8201.md\|DS-8201]] | 第一三共 | DS-8201 5.4 mg/kg | 多西他赛 | ITT | 2026-05 | 41.4% vs 25.3% | 11.3 vs 6.8 | 22.1 vs 14.2 | [[第一三共/summary/DS-8201@ASCO2026.md\|ASCO2026]] |

### Phase II

| 药品 | 公司 | 用药方案 | 对照 | 分析人群 | 数据截止 | ORR | mPFS (mo) | mOS (mo) | 来源 |
|------|------|----------|------|----------|----------|-----|-----------|----------|------|
| [[Pfizer/PF-0001.md\|PF-0001]] | Pfizer | PF-0001 单药 | 单臂 | 可评估 N=82 | 2025-09 | 35.2% | 8.5 | — | [[Pfizer/summary/PF-0001@ESMO2025.md\|ESMO2025]] |
```

### 核心指标模板

- 疗效列按疾病大类选用模板展开，单位统一写在表头（如 `mPFS (mo)`）。
- 实体瘤（NSCLC、胃癌、乳腺癌等）：`ORR | mPFS | mOS`
- 血液肿瘤（淋巴瘤、多发性骨髓瘤、白血病等）：`ORR | CR | DoR`
- 其他或无法判断：通用兜底 `ORR | mPFS | mOS`
- 来源未披露的终点写 `—`。

### 每药每阶段选优规则

- 每张子表内，同一药品只保留一条最优记录：同一阶段多来源按 详细/最终分析 > 预披露/期中，再按数据截止日最新，唯一选一条。
- 该行全部数值取自选定的这一个来源；来源未披露的终点写 `—`，不得用其他来源补充（避免混不同截止或人群）。
- 跨阶段不互斥：某药品同时有 Phase III 和 Phase II 数据时，两张子表各占一行；药品从 Phase II 更新到 Phase III 后，Phase II 行仍保留，不被淘汰。

### 单元格与对比规则

- `药品` 的显示文本为 `drug_id`，链接同一单元格内的药品页，不另加链接列。
- `公司` 使用根 `index.md` 中的规范公司名，不显示局部别名。
- `用药方案` 写明剂量、频次和联合方案；`对照` 写该试验自己的对照臂名称，单臂试验写"单臂"。
- 疗效格采用 `试验组 vs 对照` 格式，且 `vs` 前后必须是同一终点、同一单位、同一分析人群；单臂试验或对照未披露该终点时只写试验组值。
- PFS、OS、DOR 等时间值只写数字，单位统一写在表头；百分比保留一位小数；无数据写 `—`。
- 禁止跨试验横向比较对照组数值；禁止为了横向比较而重算、转置或混合不同分析人群的数据。
- 同阶段被选优规则淘汰的来源进入 `数据时间线`，不占表内额外行。
- 子表内按 药品 稳定顺序排列；同一药品在同一阶段只占一行。

## 安全性对比

安全性独立成表，每药只保留一行、取该药最新阶段的来源（样本量最大、最具代表性）。

```markdown
## 安全性对比

| 药品 | 阶段 | >=3 级 TRAE | 描述 | 来源 |
|------|------|-------------|------|------|
| [[第一三共/DS-8201.md\|DS-8201]] | Phase III | 25.0% | 最常见：恶心、疲乏；ILD 1 例 | [[第一三共/summary/DS-8201@ASCO2026.md\|ASCO2026]] |
| [[Pfizer/PF-0001.md\|PF-0001]] | Phase II | 18.0% | 最常见：贫血、血小板减少 | [[Pfizer/summary/PF-0001@ESMO2025.md\|ESMO2025]] |
```

- 只比较 `>=3 级 TRAE`；`描述` 列写最常见事件、停药或特殊信号等描述性信息。
- 每药一行，取该药最新阶段的来源；`阶段` 列注明 TRAE 数据来自哪一期。
- 必须严格区分 AE、TEAE、TRAE 和 SAE，单元格注明口径；来源未提供相同口径时，不得将不同术语放入同一列直接比较。
- 来源逐行 wikilink。
- 数据对比表中未占行的 Phase I 纯安全性药品，可在此表出现并注明阶段。

## 数据时间线

按时间倒序记录本适应症的研发进展，只使用审核通过的 summary 信息，并保留来源链接。对比表未采用的来源也要进入时间线：同阶段被选优规则淘汰的旧/预披露来源、Phase I 事件、跨阶段演进（如 Phase II → Phase III）均在此保留。

```markdown
## 数据时间线

- 2026-05: [[第一三共/DS-8201.md|DS-8201]] EXAMPLE-301 Phase III PFS 阳性 ([[第一三共/summary/DS-8201@ASCO2026.md|ASCO2026]])
- 2025-09: [[Pfizer/PF-0001.md|PF-0001]] Phase II 数据更新 ([[Pfizer/summary/PF-0001@ESMO2025.md|ESMO2025]])
- 2025-03: [[Pfizer/PF-0001.md|PF-0001]] Phase II 期中 ORR 预披露 ([[Pfizer/summary/PF-0001@ESMO2025_Interim.md|ESMO2025_Interim]])
```

## 治疗线数

| 线数 | 缩写 | 文件名示例 | 适用场景 |
|------|------|------------|----------|
| 一线 | 1L | `NSCLC_1L.md` | 初治患者 |
| 二线 | 2L | `NSCLC_2L.md` | 一线治疗后进展 |
| 三线及以后 | 3L+ | `NSCLC_3L+.md` | 多线治疗失败 |
| 后线 | Later | `NSCLC_Later.md` | 二线及以后但无法进一步细分 |

线数必须由来源明确支持，例如 first-line、1L、一线、初治或既往未接受治疗等表述。来源不足时保持 `null`，不得推断。

## 验证清单

- [ ] 文件路径为 `{research_dir}/indication/{indication_id}.md`，文件名与 frontmatter 一致。
- [ ] 不为泛瘤种或探索性笼统适应症建页。
- [ ] 所有临床数据均来自包含本 `indication_id` 且审核通过的 summary 正文分组。
- [ ] 多适应症摘要的数据未串入本页。
- [ ] `数据对比表` 只含 Phase III 和 Phase II 两张子表，不设 Phase I 表；Phase I/II 合并且人数足够者按 Phase II 入 `Phase II` 子表。
- [ ] 每张子表内同一药品只有一条最优记录（详细/最终 > 预披露/期中，再按数据截止最新），行内数值全部取自该来源。
- [ ] 跨阶段不互斥：同一药品在 Phase III 和 Phase II 各占一行；Phase II 行在更新到 Phase III 后仍保留。
- [ ] 疗效格 `vs` 前后为同一终点、单位、人群；单臂或对照未披露时只写试验组值；未横比对照、未重算或混人群。
- [ ] 核心指标列按疾病大类模板展开，未披露终点写 `—`。
- [ ] 药品链接的显示文本为 `drug_id`，链接位于同一 `药品` 单元格。
- [ ] 所有跨目录内部链接均为完整 vault 路径 wikilink，且不含 `research/` 或 `company/` 前缀。
- [ ] 表格内 wikilink alias 使用 `\|`，表格外 wikilink alias 使用普通 `|`。
- [ ] 公司名来自根 `index.md`，未建立公司页或局部别名映射。
- [ ] `安全性对比` 每药一行取最新阶段，只比较 `>=3 级 TRAE` 并含描述列；AE/TEAE/TRAE/SAE 口径未混用。
- [ ] 每个来源 `source_identity` 在本页恰好一次；对比表行和时间线事件均有来源链接。
- [ ] 被选优淘汰的来源进入 `数据时间线`；缺失值用 `—`，线数不明确时没有猜测。
