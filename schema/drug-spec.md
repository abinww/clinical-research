# 药品页格式规范 (2.0)

本文件定义药品页 `{research_dir}/{company_id}/{drug_id}/{drug_id}.md`。`research_dir` 本身是 Obsidian vault 根目录；药品页汇总同目录下已审核的临床摘要，并维护官方注册管线和药品专利。

## 目录与边界

```text
{research_dir}/
  index.md
  indication/
    {indication_id}.md
  {company_id}/
    {drug_id}/
      {drug_id}.md
      raw/
        {raw_file}.md
      summary/
        {drug_id}@{source_label}.md
```

- 一个来源对应一个 `raw` 文件和一个 `summary` 文件，不得将多个来源合并进同一文件，也不得从一个来源拆出多个摘要。
- 药品页的 `基本信息` 可在建档时填写，但已有事实必须可追溯，不得依靠模型记忆补全。
- `临床数据汇总` 和 `关键里程碑` 只能来自同药品 `summary/` 中通过一致性审核的摘要，不得直接来自 `raw/`、外部网页、PDF 或模型记忆。
- `当前临床管线` 可直接使用 ClinicalTrials.gov 官方 API 或 chinadrugtrials.org.cn 官方注册数据，但注册信息不得用于补充临床疗效或安全性。
- `药品专利` 可直接使用 Google Patents 或 FreePatentsOnline 检索结果，但专利信息不得用于补充临床疗效或安全性。
- 摘要缺失、审核章节缺失、`verification` 不是 `passed`、`verification_fail_count` 不是 `0`、`verification_coverage` 不是 `complete`，或审核含 `FAIL` 时，不得将其数据写入药品页。
- 公司中英文名和别名只在根 `index.md` 集中维护，不建立 `company.md`，药品页不重复维护公司别名。

## 文件与身份

- 文件路径固定为 `{research_dir}/{company_id}/{drug_id}/{drug_id}.md`，文件名必须与 `drug_id` 一致；不存在中间 `company/` 目录。
- `drug_id` 优先级：开发代码、短名称或缩写、中文通用名、英文通用名。
- `drug_id` 中空格和斜杠替换为 `_`，括号移除；优先使用简洁、稳定、易读的标识。
- 同一药品只有一个规范 `drug_id`；商品名、通用名和旧代码写入 `drug_aliases`。
- `company_id` 必须引用根索引中已有的规范公司 ID。合作开发在 `company_ids` 列出多个规范 ID，目录归属采用 `archive_company`。
- `company_id` 和 `drug_id` 必须通过 `scripts/layout.py:is_valid_identifier`：长度 1-80，首字符为 Unicode 字母或数字，内部仅允许 Unicode 字母/数字、空格、`.`、`_`、`-`，不得以空格或句点结尾，也不得是 Windows 保留设备名。可以包含中文和内部空格。

## Frontmatter

```yaml
---
drug_id: ABC123
drug: 示例单抗
drug_aliases: [ABC-123, Examplemab]
category: 单克隆抗体
target: HER3/EGFR
archive_company: 第一三共
company_ids: [第一三共, AstraZeneca]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

必需字段为 `drug_id`、`drug`、`target`、`archive_company`、`company_ids`、`created`、`updated`。兼容字段 `companies` 如存在必须与 `company_ids` 完全相同。

### target 规则

- 只写靶点名或组合，不写括号别名和机制说明。
- 多靶点用 `/` 连接并按机制主次排序，不加空格。
- 保留约定大小写，如 `PD-1`、`B7-H3`、`HER3/EGFR`。
- 靶点别名不得放入 `drug_aliases`；`drug_aliases` 仅记录药品身份别名。

## 正文结构

```markdown
# {药品展示名}

## 基本信息

## 临床数据汇总

### {适应症 A}

### {适应症 B}

## 关键里程碑

## 当前临床管线

### clinicaltrials.gov

### chinadrugtrials.org.cn

## 药品专利
```

新建药品页时只填写 frontmatter 和 `基本信息`；其他章节保留空标题，等待相应数据流程更新。

## 基本信息

```markdown
## 基本信息

| 属性 | 内容 |
|------|------|
| 通用名 | {drug} |
| 靶点 | {target} |
| 药物类别 | {category} |
| 研发公司 | {company_ids 对应的规范公司名} |
| 最高阶段 | {phase} |
```

公司展示名由根 `index.md` 解析；此处不得创建另一套公司别名映射。

## 临床数据汇总

按适应症分组。一个摘要涉及多个适应症时，只将该适应症标题下的数据放入对应章节，不得复制其他适应症的数据。

```markdown
### {适应症名称}

<!-- source_identity: {company_id}/{drug_id}/summary/{drug_id}@{source_label}.md -->

> {source_label}

| 指标 | {cohort 1} | {cohort 2} | {对照组} |
|------|:----------:|:----------:|:------:|
| N | ... | ... | ... |
| ORR | ... | ... | ... |
| >=3 TRAE | ... | ... | ... |

> 来源: [ABC123@ASCO2026.md](summary/ABC123@ASCO2026.md)
```

### 表格规则

- 直接嵌入摘要中该适应症的有效性主表，保持指标为行、cohort 为列，不转置、不重新计算数值。
- 药品页只嵌入含有效性数据的主表；仅安全性或亚组分表通过摘要链接查看。
- 表格上方只写 `> {source_label}`；表格下方使用相对药品页的兄弟目录链接 `summary/{file}.md`。
- 不同 `trial_name` 分成不同表格。
- 同一 `trial_name` 的不同数据成熟度可合成一表：同一 cohort 保持同列，不同披露点新增指标行并在指标名注明标签，如 `cORR (ASCO 2026)`。
- 合并表的来源行列出全部摘要链接，以 ` | ` 分隔。一个摘要可同时为多个适应症章节提供各自的数据。
- 同一 cohort、同一披露时间的数值冲突不得静默覆盖，应并列保留并明确来源差异。
- 第一条数据行为 `N`。不同分析人群必须分列，不能串列。
- 百分比保留一位小数。PFS、OS、DOR 等时间指标只写数字；表格语境中统一使用 `mo` 或 `yr` 说明单位。
- 无数据用 `—`；明确未成熟或未评估可写 `NE` 并说明原因。

## 关键里程碑

仅从已通过审核的摘要提取，按时间倒序排列；无法确认月份时不得猜测。

```markdown
## 关键里程碑

| 时间 | 事件 |
|------|------|
| 2026-05 | sq-NSCLC 1L Phase III PFS 阳性 (ASCO 2026) |
| 2025-06 | NSCLC 3L Phase II 数据发布 (ASCO 2025) |
```

## 当前临床管线

收录官方查询返回的全部注册试验状态，包括进行中、计划中、完成、终止和撤回记录，并按来源分表；`状态` 列用于区分。注册信息和已披露临床结果可以同时存在，但注册表不能代替临床数据汇总。

### clinicaltrials.gov

```markdown
### clinicaltrials.gov

> 更新时间: YYYY-MM-DD

| 试验ID | 药品 | 开展国家 | 适应症 | 阶段 | 状态 | 入组 | 开始 | 预计完成 | 对照 | Sponsor | 主要终点 | 次要终点 | 更新 |
|--------|------|----------|--------|------|------|------|------|----------|------|---------|----------|----------|------|
| [NCT00000001](https://clinicaltrials.gov/study/NCT00000001) | ABC123 + Pembrolizumab + 化疗 | US、CN | Example Cancer 1L | Phase II | Recruiting | 120 | 2023-06 | 2025-12 | — | BigPharma | ORR, DOR | PFS, OS, Safety | 2025-06 |
```

- `试验ID` 必须链接官方详情页。
- `药品` 写实际方案中的全部药物，联合方案以 ` + ` 连接。
- 国家格式由生成脚本统一处理；缺失写 `—`。
- 按阶段 Phase III、II、I 排序，同阶段按开始日期倒序。

### chinadrugtrials.org.cn

```markdown
### chinadrugtrials.org.cn

> 更新时间: YYYY-MM-DD

| 试验ID | 药品 | 开展国家 | 适应症 | 阶段 | 状态 | 入组 | 开始 | 预计完成 | 对照 | Sponsor | 主要终点 | 次要终点 | 更新 |
|--------|------|----------|--------|------|------|------|------|----------|------|---------|----------|----------|------|
| — | — | — | — | — | — | — | — | — | — | — | — | — | — |
```

- `试验ID` 链接中国临床试验注册中心官方详情页。
- 列定义与 ClinicalTrials.gov 表一致；尚无数据时允许保留占位行。

## 药品专利

只收录与药品直接相关或明确关联的原研、合作方专利，用于描述保护面，不提供法律意见或 FTO 结论。

```markdown
## 药品专利

> 更新时间: YYYY-MM-DD
> 数据来源: Google Patents（覆盖 US/CN 等全球公开）
> 类型: compound=核心物质 · combo=联合用药 · use=用途/生物标志物 · other=平台延伸/其他
> 类型分布: compound 2 · combo 8 · use 1 · other 2
> 申请人分布: Company A 5 · Company B 6

| 公开号 | 标题 | 类型 | 申请人 | 申请日 | 备注 |
|--------|------|------|--------|--------|------|
| [US11185594B2](https://patents.google.com/patent/US11185594B2/en) | (Anti-HER2 antibody)-drug conjugate | compound | Company A | 2015-04-06 | 核心物质族（2014 优先权）美国成员 |
```

- 公开号链接 Google Patents 详情页。
- 类型仅允许 `compound`、`combo`、`use`、`other`，按该顺序分组，同组按申请日倒序。
- 类型可由 CPC/IPC 或标题推断，但必须说明为推断值，最终以权利要求为准。
- `申请日` 使用最早 filing date；A1 申请公开号和 B2 授权号均可收录。
- 备注可记录分类号、核心物质族、联用或平台延伸等事实。
- `类型分布` 和 `申请人分布` 为表内记录的聚合结果。
- 不收录法律状态、到期日或 FTO 结论。
- 优先使用 Google Patents。降级到 FreePatentsOnline 时，`数据来源` 必须注明其以 US 为主且未覆盖 CN/WO/EP。

## 验证清单

- [ ] 路径为 `{research_dir}/{company_id}/{drug_id}/{drug_id}.md`，文件名与 `drug_id` 一致，且没有 `company/` 中间层。
- [ ] `company_id` 和公司展示名可在根 `index.md` 找到，未建立 `company.md` 或局部别名表。
- [ ] frontmatter 必需字段完整，`target` 使用最简形式。
- [ ] 临床数据和里程碑只来自审核通过且 `FAIL=0` 的同药品摘要。
- [ ] 临床数据按适应症分组，多适应症摘要的数据未串组。
- [ ] 不同试验分表；同试验不同成熟度按规则合并且保留全部来源。
- [ ] 药品页摘要链接使用兄弟路径 `summary/{file}.md`。
- [ ] 管线表保留官方试验链接、更新时间、完整方案和开展国家。
- [ ] 专利类型、排序、来源和排除规则均满足本规范。
- [ ] 表格无空单元格；缺失值使用 `—`。
