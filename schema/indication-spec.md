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

- 在研药品、疗效、安全性和时间线只可来自 summary 的 `indications` 中包含本页 `indication_id`、且一致性审核通过的部分。
- 摘要必须满足 `verification: passed`、`verification_fail_count: 0`、`verification_coverage: complete`、审核章节存在且无 `FAIL`。
- 一个摘要包含多个适应症时，只提取与本页 `indication_id` 对应的正文分组，不得引用其他组的数据。
- 下游匹配假定 summary 的每个 `indications` 对象具有稳定且唯一的 section identity：以该对象的 `indication_id` 作为 `section_id`，并一一对应正文中同序的一个 `## {适应症}` 分组。`section_id` 重复、对象与分组数量/顺序不一致或无法唯一对应时阻断该 summary，不得仅按显示标题模糊匹配。
- 不得直接从 raw、外部网页、注册库、模型记忆或药品页反向补全临床数值。
- 公司展示名和别名从根 `index.md` 解析；不建立 `company.md` 或适应症页局部公司映射。

## 链接规则

适应症页的内部链接必须使用完整 vault 路径 wikilink，避免标准 Markdown 链接被错误地相对于 `indication/` 解析：

```markdown
[[第一三共/DS-8201/DS-8201.md|DS-8201]]
[[第一三共/DS-8201/summary/DS-8201@ASCO2026.md|DS-8201@ASCO2026]]
```

不得使用 `../` 相对路径，不得添加 `research/` 或 `company/` 前缀，也不得省略 `company_id` 或药品目录。

wikilink 位于 Markdown 表格单元格时，alias 分隔符 `|` 前必须加反斜杠；位于表格外的来源引用、列表或正文时使用普通 `|`，如上例，不加反斜杠。

## 正文结构

```markdown
# {适应症名称}

## 概述

## 在研药品

## 疗效数据详表

## 安全性对比

## 数据时间线
```

`疗效数据详表` 和 `安全性对比` 可按数据量省略；其他章节应保留。

## 概述

```markdown
## 概述

{适应症名称}的治疗现状：

- **标准治疗**：{当前标准治疗方案}
- **未满足需求**：{主要挑战}
- **热门靶点**：{正在研发的靶点}
```

概述中的事实应有明确来源；不得用临床摘要无法支持的模型记忆补全。

## 在研药品

每个由 indexer 写入或更新的药品/来源数据块必须在块起始处包含：

```markdown
<!-- source_identity: {company_id}/{drug_id}/summary/{drug_id}@{source_label}.md -->
```

同一来源 identity 在本页恰好出现一次，去重和更新以该标记为准。

```markdown
## 在研药品

| 药品 | 公司 | 阶段 | ORR | mPFS | mOS | 安全性要点 | 最新进展 |
|------|------|------|-----|------|-----|------------|----------|
| [[第一三共/DS-8201/DS-8201.md\|DS-8201]] | 第一三共 | Phase III | 41.4% | 11.3 | 22.1 | >=3 级 TRAE 25.0% | ASCO 2026 |
| [[Pfizer/PF-0001/PF-0001.md\|PF-0001]] | Pfizer | Phase II | 35.2% | 8.5 | — | >=3 级 TRAE 18.0% | ESMO 2025 |

> 来源: [[第一三共/DS-8201/summary/DS-8201@ASCO2026.md|DS-8201@ASCO2026]] | [[Pfizer/PF-0001/summary/PF-0001@ESMO2025.md|PF-0001@ESMO2025]]
```

### 列和排序规则

- `药品` 的显示文本为 `drug_id`，链接同一单元格内的药品页，不另加链接列。
- `公司` 使用根 `index.md` 中的规范公司名，不显示局部别名。
- `阶段` 使用该适应症对应的临床阶段，不使用药品在其他适应症的最高阶段。
- ORR、mPFS、mOS、安全性和最新进展只提取本适应症正文组的数据。
- PFS、OS、DOR 等时间值只写数字，并在表头或表格说明中统一注明单位；无数据写 `—`。
- 来源不放 frontmatter 或表格列中，在表格下方以 `> 来源:` 汇总；多个来源以 ` | ` 分隔。
- 按 Phase III、II、I 排序；同阶段优先按证据成熟度和发布日期排序。只有分析人群、方案和时间点可比时，才按 mPFS 或 ORR 数值排序。

## 疗效数据详表

需要展示更多终点时，可按终点分表。每张表都必须保留完整根路径来源。

```markdown
## 疗效数据详表

### ORR 对比

| 药品 | ORR | cORR | DCR | 分析人群 |
|------|-----|------|-----|----------|
| [[第一三共/DS-8201/DS-8201.md\|DS-8201]] | 41.4% | 34.5% | 87.9% | 可评估人群 N=82 |

> 来源: [[第一三共/DS-8201/summary/DS-8201@ASCO2026.md|DS-8201@ASCO2026]]

### PFS 对比

| 药品 | mPFS (mo) | HR | p-value | 分析人群 |
|------|-----------|----|---------|----------|
| [[第一三共/DS-8201/DS-8201.md\|DS-8201]] | 11.3 | 0.62 | <0.0001 | ITT |

> 来源: [[第一三共/DS-8201/summary/DS-8201@ASCO2026.md|DS-8201@ASCO2026]]
```

- 不得为了横向比较而重算、转置或混合不同分析人群的数据。
- 同名终点单位不同、定义不同或时间点不同，应分表或增加明确说明。
- 百分比保留一位小数；不使用空白单元格。

## 安全性对比

```markdown
## 安全性对比

| 药品 | >=3 级 AE | 常见 AE | 因 AE 停药率 | 安全性人群 |
|------|-----------|---------|-------------|------------|
| [[第一三共/DS-8201/DS-8201.md\|DS-8201]] | 25.3% | 恶心、疲乏 | 5.2% | N=100 |

> 来源: [[第一三共/DS-8201/summary/DS-8201@ASCO2026.md|DS-8201@ASCO2026]]
```

必须严格区分 AE、TEAE、TRAE 和 SAE。来源未提供相同口径时，不得将不同术语放入同一列直接比较。

## 数据时间线

按时间倒序记录本适应症的研发进展，只使用审核通过的 summary 信息，并保留来源链接。

```markdown
## 数据时间线

- 2026-05: [[第一三共/DS-8201/DS-8201.md|DS-8201]] EXAMPLE-301 Phase III PFS 阳性 ([[第一三共/DS-8201/summary/DS-8201@ASCO2026.md|ASCO2026]])
- 2025-09: [[Pfizer/PF-0001/PF-0001.md|PF-0001]] Phase II 数据更新 ([[Pfizer/PF-0001/summary/PF-0001@ESMO2025.md|ESMO2025]])
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
- [ ] 药品链接的显示文本为 `drug_id`，链接位于同一 `药品` 单元格。
- [ ] 所有跨目录内部链接均为完整 vault 路径 wikilink，且不含 `research/` 或 `company/` 前缀。
- [ ] 表格内 wikilink alias 使用 `\|`，表格外 wikilink alias 使用普通 `|`。
- [ ] 公司名来自根 `index.md`，未建立公司页或局部别名映射。
- [ ] 不同分析人群、时间点、单位和安全性术语未被错误合并。
- [ ] 每张临床表有来源行，时间线事件有对应来源链接。
- [ ] 缺失值用 `—`，线数不明确时没有猜测。
