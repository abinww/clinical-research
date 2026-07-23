# 临床摘要格式规范 (summary-spec.md)

# 临床摘要格式规范

本文件定义从临床试验文稿提取核心数据并生成规范摘要的格式要求。

## 格式规范概述

本规范用于从学术会议文稿、上市公司公告、新闻稿等提取核心临床数据，生成规范化的 markdown 格式摘要文档。

## 使用方式

当执行摘要生成步骤时，读取本文件作为格式参考，然后按规范生成摘要。

---

# 摘要生成详细步骤

## Overview

本文档目的是，从各种描述临床数据的文稿，包括学术会议文稿、上市公司公告、新闻稿等，提取核心临床数据并生成规范化的markdown格式的临床数据摘要文档。

## Configuration

**命名格式**: `summary/` 目录按药品分子目录组织，每个药品一个子目录 `summary/{drug_id}/`，每个来源快照必须命名为 `{drug_id}@{indication_id}@{source_label}.md`。同一来源重新提取时复用同一 `source_label`，不同来源或同标签冲突时生成新的快照。

`summary/` 文件名不得使用网页标题、raw 文件名或任意摘要标题。网页/PDF 标题只用于 `raw/` 文件命名。

**药品身份优先级规则**（用于确定 `drug_id`）：
按以下优先级选择药品身份，优先使用简洁、易读的标识：
1. 开发代码（如 ABC123, ABC456, ABC789, ABC101）
2. 短名称/缩写（如 exa-mab）
3. 中文通用名（如 示例单抗, 示例ADC）
4. 英文通用名（尽量避免，如 Examplemab）

示例：
- ✅ 优先: `ABC123@Example_Cancer@ASCO2026.md` 或 `exa-mab@Example_Cancer@ASCO2026.md`
- ✅ 可接受: `示例单抗@Example_Cancer@company_release_2025.md`
- ❌ 避免: `Examplemab@Example_Cancer@source.md`

`source_label` 是短的、人工可读的来源标签，默认使用来源简称和年份，例如 `ASCO2026`、`ESMO2026`、`NEJM2026` 或 `CompanyRelease2025`。同一 drug/indication 下同标签确有多个不同来源时，追加最短区分后缀，例如 `ASCO2026_2` 或 `ASCO2026_FinalAnalysis`。不强制把摘要编号、试验代码或完整标题放入文件名。

**文件名清理规则**:
- 替换空格为下划线
- 移除特殊字符

**常见终点缩写列表** - 以下缩写在表格中无需写中文全称：
- ORR (客观缓解率)
- cORR (确认缓解率)
- DCR (疾病控制率)
- mPFS/rPFS (中位无进展生存期)
- mOS (中位总生存期)
- mDOR (中位缓解持续时间)
- PSA50/PSA90 (PSA缓解率)
- CR (完全缓解)
- PR (部分缓解)
- SD (疾病稳定)
- PD (疾病进展)
- AE (不良事件)

⚠️ 如需修改配置，请直接编辑本配置区域
⚠️ 注意：不在列表中的终点数据应写中文全称以清晰说明
⚠️ 注意：本技能会尝试自动提取网页图片，但对于受限平台（微信公众号等）需要手动截图


## Workflow

### Step 1: Read the content

仔细阅读需要提取的文档，确定该文档是在描述药品的临床数据；

如果文档有链接的图片，那么启用默认的多模态大模型，对图片内容进行阅读，判断该图片是否与临床数据相关；不相关的图片可以直接忽略；相关的图片，如果该图片是较为重要的临床数据表格或图片，那么保留图片链接，准备在后续步骤生成的文档里插入图片链接；

### Step 2: Extract Key Information

最终生成的摘要文档，应该包含以下部分：

1. **YAML**，基础信息；
2. **有效性和安全性数据**，以表格形式展示，最为重要的部分，务必不能出错；
3. **临床数据图片**，“Step 1”里面，判断重要的图片，可以将链接插入这里；
4. **试验设计**，以表格形式展示，如果有基线人群数据，也可以放在这一部分；
5. **专家点评**，仅供参考，从药学/医学专家角度分析该临床数据的意义；
6. **数据一致性审核**，放在文档末尾，用于记录 summary 数据与 raw 原文的逐项核对结果；

#### YAML
分析文档，并提取如下内容。如果无法获取，那么就留空:

| 字段 | 类型 | 说明 |
|------|------|------|
| drug_id | 字符串 | 开发代码或规范短名（必填；用于 summary 目录、文件名和 drug 索引归档） |
| drug | 字符串 | 药品通用名（必填；用于展示） |
| drug_aliases | 数组 | 别名、商品名 |
| indication_id | 字符串 | 规范适应症ID（必填；用于 indication 索引文件名） |
| indication | 字符串 | 适应症（必填） |
| source_label | 字符串 | 来源快照短标签（必填；用于 summary 文件名，同一来源重提取时保持不变） |
| source_type | 字符串 | 来源类型，仅允许 `journal`、`conference`、`company_release`、`regulatory`、`other` |
| published_date | 日期或 null | 来源明确发布日期、会议日期或期刊在线发表日期；无法确认时为 `null`，不得使用提取日期代替 |
| combination_regimen | 字符串 | 标准化联合用药方案；单药也必须明确写入 |
| clinical_match_key | 字符串 | `drug_id|combination_regimen|indication_id|phase`，用于 drug 临床记录合并 |
| companies | 数组 | 研发公司列表 |
| phase | 字符串 | Phase I/II/III（必填） |
| trial_name | 字符串 | 试验名称 |
| conference | 字符串 | 学术会议或发布场合 |
| created | 日期 | summary 生成日期 |
| verification | 字符串 | 必填；仅允许 `passed`，表示独立 data verifier 已完成且 FAIL=0 |
| verification_fail_count | 整数 | 必填；必须为 `0` |
#### 有效性和安全性数据
For effectiveness and safety data, present findings in **markdown table format**:

```markdown
## 药品有效性和安全性

| 指标 | ABC001 | 对照组 | HR | p-value |
|------|----------------|--------|------|------|
| N | 100 | 50 | - | - |
| ORR | 41.4% | 25.3% | - | <0.0001 |
| cORR | 34.5% | - | - | <0.0001 |
| DCR | 87.9% | - | - | <0.0001 |
| mPFS | 11.3 | 6.8 |  0.62  | <0.0001 |
| mOS | 22.1 | 14.2 |  0.73  | <0.0001 |
| 最常见AE | 恶心、血液事件（1-2级） | - | - | - |
```

**多剂量组示例**：
```markdown
| 指标 |  AAB001 2mg | AAB001 4mg | AAB001 6mg |  Placebo |
|------|----------|--------------|--------------|--------------|
| N | 50 | 50 | 50 | 50 |
| OS | 12.1 | 14.2 | 17.3 | 0.2 |
| OS p-value | <0.0001 | <0.0001 | <0.0001 | - |
| PFS | 12.1 | 14.2 | 17.3 | 0.2 |
| PFS p-value | <0.0001 | <0.0001 | <0.0001 | - |
```

**表格格式规范**：
- 表格内容第一行必须列出各组入组人数，指标列写"N"
- **关键原则**：确保同一列的数据与该列标题对应的cohort一致
- **重要规则**：必须明确标注cohort的具体信息（如剂量组、治疗方案等），避免使用"最大剂量组"、"高剂量组"等笼统表述
  - ❌ 错误：`AAB001 (最大效果)` 或 `高剂量组`
  - ✅ 正确：`AAB001 6mg` 或 `对照组`
- 不同终点可能基于不同分析人群（如总人群 vs 可评估人群），需分别分列
- 缺乏的数据统一标注为 `—`，不要将不同人群的数据混用
- 合并主要终点、次要终点、安全性到一个表格
- 列名：`["指标", "实验组1", "实验组2", ...]` 或 `["指标", "实验组", "对照组"]`（如有对照）
- 常见终点使用英文缩写（见 **Configuration** 中的"常见终点缩写列表"）
- 不常见的终点写中文全称
- 不要写95% CI置信区间
- 时间指标（PFS/OS/DOR等）只写数字，不写单位（如 `11.3` 而非 `11.3个月`）
- 百分比保留一位小数（如 `41.4%`）
- 数值不存在的用 `—` 表示；明确“未成熟/未评估”时可使用 `NE`，并在备注中说明原因
- 可在数值后用括号标注实际样本量（如 `11.3 (N=82)`）

#### 数据一致性审核

本章节用于记录 data verifier subagent 对 summary 摘要与 raw 原文的核对结果，必须放在整个 summary 文件末尾。

只检查临床数据和试验事实是否能在 `raw/` 中找到依据，不评价临床价值，不补充新数据。

审核字段包括但不限于：
- 样本量：`N`、`n`
- 疗效：`ORR`、`cORR`、`DCR`、`CR`、`PR`、`SD`、`mPFS`、`rPFS`、`mOS`、`mDoR`、`DoR`
- 统计量：`HR`、`p-value`、`CI`
- 安全性：`AE`、`TEAE`、`TRAE`、`SAE`、`≥3级AE/TEAE/TRAE`、减量、停药、死亡
- 试验信息：phase、trial name、cohort、剂量、治疗组、对照组、适应症、治疗线数、会议/发布日期

状态定义：
- `PASS`: `raw/` 中能找到直接证据或明确等价表达，且组别、剂量、单位、时间点一致
- `WARN`: `raw/` 中有近似依据，但组别、单位、时间点、术语或上下文需要人工确认
- `FAIL`: `raw/` 中找不到依据，或发现组别/剂量/单位/时间点对应错误

审核章节格式：

```markdown
## 数据一致性审核

| 数据项 | summary中的值 | raw证据 | 状态 | 问题 |
|------|-------------|---------|------|------|
| ORR | 42.3% | "...ORR was 42.3%..." | PASS | - |
| mPFS | 11.3 | 未找到 | FAIL | raw中未出现该数值 |
| G≥3 TRAE | 25.0% | "...grade 3 or higher TEAEs..." | WARN | raw为TEAE，summary写TRAE |
```

注意：
- `summary` 中的每一个临床数值都必须有对应审核行
- `summary` 中每一个临床数值、试验事实和关键分组信息都必须能追溯到 `> 来源原文:` 行指向的 raw 文件
- cohort、剂量、治疗组、对照组不能串列
- `TEAE`、`TRAE`、`AE`、`SAE` 不得混用；如原文术语不同，标记 `WARN` 或 `FAIL`
- 时间单位不得擅自转换；如原文为 weeks，summary 写成 months，标记 `FAIL`
- 原文没有的数据不得写成确定数据
- 只有 `verification: passed`、`verification_fail_count: 0` 且审核章节存在的 summary，才允许作为 drug/ 或 indication/ 索引的数据来源

### Step 3: File Content Structure

The generated markdown file should follow this template:

```markdown
---
drug_id: {开发代码或规范短名}
drug: {药品通用名}
drug_aliases: [{别名1, 别名2}]
indication_id: {规范适应症ID}
indication: {适应症}
source_label: {ASCO2026}
source_type: {journal|conference|company_release}
published_date: {YYYY-MM-DD 或 null}
combination_regimen: {标准化联合用药方案}
clinical_match_key: "{drug_id}|{combination_regimen}|{indication_id}|{phase}"
companies: [{公司列表}]
phase: {Phase}
trial_name: {试验名称}
conference: {学术会议}
created: {YYYY-MM-DD}
verification: passed
verification_fail_count: 0
---

# {drug_id}@{indication_id}@{source_label}

> 来源原文: [[raw/{原始文件名.md}]]

## 核心数据

| 指标 | 实验组 | 对照组 | HR | p-value |
|------|--------|--------|-----|---------|
{提取的表格数据}


## 临床数据图片（如果没有图片，或者无法获取图片，则省略）
{重要图片链接}

## 试验设计

| 设计要素 | 内容 |
|----------|------|
| 研究类型 | {从内容提取} |
| 入组人数 | {从内容提取} |
| 用药方案 | {从内容提取} |

## 专家点评
（仅供参考）

从药学/医学专家角度分析该临床数据的意义：

- **疗效评价**：[分析主要终点结果是否达到临床意义，对比同类药物]
- **安全性考量**：[分析安全性概况，关注关键AE]
- **研究设计评价**：[研究设计是否合理、样本量是否充足、对照组选择等]
- **临床前景**：[基于当前数据评估药物商业化潜力及后续研究方向]
- **注意事项**：[数据的局限性、需要进一步验证的点等]

## 数据一致性审核

| 数据项 | summary中的值 | raw证据 | 状态 | 问题 |
|------|-------------|---------|------|------|
| {数据项} | {summary中的值} | {raw原文证据或未找到} | {PASS/WARN/FAIL} | {问题说明} |

```



## 边缘情况处理

### 字段缺失

如果无法提取某个字段：
- drug/indication/phase: 标记为 "待补充"，提示用户
- 其他字段: 留空字符串或空数组

### 多个药品或适应症

如果内容涉及多个药品或适应症：
- 询问用户需要提取哪一个
- 或为每个药品生成带对应 `drug_id` 的 summary 文件

### 数据表格缺失

如果无法找到数据表格：
- 在 "核心数据" 部分标注 "数据表格待补充"
- 保留 "数据来源" 链接，方便用户后续手动补充
