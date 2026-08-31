# 临床摘要格式规范 (2.0)

本文件定义从单一临床来源生成摘要文件的格式。摘要位于药品目录内，是 `raw` 原文与药品页、适应症页之间唯一的结构化临床数据层。

## 一对一来源模型

```text
{research_dir}/{company_id}/{drug_id}/
  raw/{drug_id}@{source_label}.md
  summary/{drug_id}@{source_label}.md
```

- 一个来源生成一个 `raw` 文件，再生成一个 `summary` 文件：`1 source -> 1 raw -> 1 summary`。
- 不得将多个网页、PDF、会议摘要或新闻稿合并为一个 raw 或 summary。
- extractor 永远只创建新文件，不得覆盖既有 raw 或 summary。它可创建 orchestrator 指定的 replacement staging 路径，但不得 commit 或删除。
- 替换只能由 multi-extractor 执行，且必须在 `{research_dir}/.temp/replacements/{run-id}` 中先提取、结构校验并由独立 verifier 通过。commit 前逐字节备份准确旧 pair、全部 managed index documents（药品页、涉及的适应症页、根索引）及受影响附件并校验哈希；附件在 manifest 中记录复用/新增/移除，绝不先删除。正式安装使用可恢复的原子 replace 和持久化事务状态，任一步失败回滚全部已改文件并校验旧状态。
- 实质不同的来源必须使用不同 `source_label`。
- summary 文件名固定为 `{drug_id}@{source_label}.md`，不包含 `indication_id`，也不使用网页标题或 raw 文件名。
- 一个来源涉及一个或多个适应症时，全部写在同一 summary，通过 YAML `indications` 对象列表和正文适应症分组表达。
- 摘要必须链接同目录的唯一 raw 原文，规范链接为 `> 来源原文: [label](../raw/file.md)`。

## 命名

`source_label` 是稳定、简短、人工可读的来源标签，通常为来源简称和年份，如 `ASCO2026`、`ESMO2026`、`NEJM2026`、`CompanyRelease2025`。同一基础标签对应多个实质不同来源时，必须添加最短的语义稳定后缀来描述来源差异，例如 `ASCO2026_TrialABC`、`ASCO2026_Abstract1234` 或 `ASCO2026_FinalAnalysis`；不得使用 `_2`、`_3` 等不透明顺序号。

严格语法如下，不得静默清洗输入：

- `company_id`、`drug_id`：1-80 个 Unicode 字符的单一路径组件，允许中文、ASCII 字母、数字、空格、`.`、`_`、`-`；禁止控制字符及 `< > : " / \\ | ? * @ # % [ ] ^`，不得为 `.`/`..`，不得以空格或句点结尾，不得是 Windows 保留设备名（不区分大小写，包括带扩展名形式）。
- `indication_id`：稳定 ASCII ID，语法 `[A-Za-z0-9][A-Za-z0-9._-]{0,79}`；同一规范适应症/治疗线跨来源保持不变。
- `source_label`：语法 `[A-Za-z0-9][A-Za-z0-9._-]{0,79}`，明确禁止 `@`、空格、中文和路径/Markdown 特殊字符。冲突只能加 trial/abstract/analysis 等稳定语义后缀。
- `drug_id` 必须与药品页一致；文件基名由唯一分隔符 `@` 连接 `drug_id` 与 `source_label`。

## 来源身份

raw frontmatter 的 `source` 是来源去重、替换和工作流比较使用的持久来源身份：

- URL 来源保存用户准确提供的 URL；若工作流明确采用重定向后的 canonical final URL，则保存该准确 final URL。不得 percent decode，也不得为比较而改写大小写、查询参数、尾部斜杠或编码形式；所有工作流比较 raw 中持久化的同一个准确字符串。
- 本地 PDF 来源只保存 `Path.resolve(strict=True).as_posix()` 得到的绝对 POSIX 路径，例如 `C:/reports/trial.pdf`；路径必须实际存在，不得只保存文件名、相对路径、反斜杠路径或另造路径标识。
- raw 与 summary 的配对身份由同一 `{drug_id}@{source_label}` 文件名确定；准确重复键是当前药品树中的 `(company_id, drug_id, source)`。相同 source 在另一药品树属于允许的跨药复用，不阻塞创建。近似来源只能提示人工判断。

## Frontmatter

```yaml
---
drug_id: ABC123
drug: 示例单抗
drug_aliases: [ABC-123, Examplemab]
indications:
  - indication_id: NSCLC_1L
    indication: 非小细胞肺癌一线
    line: 1L
    biomarker: null
    trials:
      - trial_name: EXAMPLE-01
        phase: Phase II
        regimen: ABC123 + Pembrolizumab
        cutoff: YYYY-MM-DD
  - indication_id: NSCLC_2L
    indication: 非小细胞肺癌二线
    line: 2L
    biomarker: null
source_label: ASCO2026
source_type: conference
published_date: YYYY-MM-DD
combination_regimen: ABC123 + Pembrolizumab
archive_company: 第一三共
company_ids: [第一三共, AstraZeneca]
phase: Phase II
trial_name: EXAMPLE-01
conference: ASCO 2026
created: YYYY-MM-DD
verification: passed
verification_fail_count: 0
verification_coverage: complete
---
```

### 字段规则

| 字段 | 类型 | 规则 |
|------|------|------|
| `drug_id` | 字符串 | 必填，与所属目录和药品页一致 |
| `drug` | 字符串 | 必填，药品展示名 |
| `drug_aliases` | 数组 | 可选，药品别名和商品名 |
| `indications` | 对象列表 | 必填，至少一个对象；每项含稳定 `indication_id`、`indication`，可含 `line`、`biomarker`、`trials` |
| `source_label` | 字符串 | 必填，与文件名一致 |
| `source_type` | 枚举 | `journal`、`conference`、`company_release`、`regulatory`、`other` |
| `published_date` | 日期或 null | 来源明确的发表、会议或发布日期；不能用提取日期代替 |
| `combination_regimen` | 字符串 | 必填，标准化写明单药或联合方案 |
| `archive_company` | 字符串 | 必填，归档目录使用的规范 `company_id`，等于路径中的 `company_id` |
| `company_ids` | 数组 | 必填，原研方、权利方和合作方的根索引规范 company IDs |
| `companies` | 数组 | 可选兼容字段；如存在必须与 `company_ids` 完全相同，只含规范 IDs |
| `phase` | 字符串或 null | `Phase I/II/III/IV`；无法确认写 `null`，不得猜测 |
| `trial_name` | 字符串或 null | 来源披露的试验名称；无名称写 `null` |
| `conference` | 字符串或 null | 学术会议或披露场合 |
| `created` | 日期 | 摘要生成日期 |
| `verification` | 枚举 | 必填；提取器初写 `pending`，独立审核后改为 `passed` 或 `failed` |
| `verification_fail_count` | 整数或 null | `pending` 时为 `null`；审核后写实际 FAIL 数；可供下游使用的摘要必须为 `0` |
| `verification_coverage` | 枚举或 null | `pending` 时为 `null`；独立审核覆盖完整后写 `complete`，否则不得标记为 passed |

- `indications` 中不同治疗线数是不同对象；无法判断线数时 `line: null`，不得猜测为 `1L`。
- indication 可含 `trials` 列表；每项至少用 `trial_name`（未知为 `null`）区分，并可含 `phase`、`regimen`、`cutoff`。cutoff 仅用来源明确的 `YYYY-MM-DD`，未知为 `null`。
- 继承顺序为 trial 显式值 > indication 同名值 > 顶层共同值。indication 可用 `phase`、`regimen`、`cutoff` 作为其 trials 默认值。顶层 `phase`、`combination_regimen` 和来源级 cutoff 只有在所有适应症/试验相同时才作共同默认，否则写 `null`；显式 `null` 表示未知，不得从其他 trial 横向继承。
- 探索性泛瘤种可以出现在 `indications` 中，但不会因此建立适应症页。
- 同一来源对不同适应症采用不同方案、阶段或试验时，在对应正文的 `试验设计` 中明确差异；顶层字段写来源整体最准确的共同值，不能概括时写 `null`。
- 不使用单数 `indication_id`、`indication` 字段，也不使用将适应症编码进文件名的设计。
- summary 初次生成时必须写 `verification: pending`、`verification_fail_count: null` 和 `verification_coverage: null`，不得预先写 `passed`；示例中的 `passed/0/complete` 表示独立审核完成后的最终状态。

## 正文结构

```markdown
# {drug_id}@{source_label}

> 来源原文: [ASCO 2026 abstract](../raw/ABC123@ASCO2026.md)

## [{indication_id A}] {适应症 A}

### 核心数据

### 临床数据图片

### 试验设计

### 专家点评

## [{indication_id B}] {适应症 B}

### 核心数据

### 试验设计

### 专家点评

## 数据一致性审核
```

- 正文必须按 `indications` 顺序分组，每个 `## [{indication_id}] {indication}` 与一个对象一一对应；稳定 ID 是机器映射键。
- 来源链接紧随一级标题且全文件只写一次，必须采用 `[label](../raw/file.md)`，其中 label 是可读来源名。
- 每个适应症独立包含核心数据和试验设计；不得把多适应症数值混入同一张无明确分组的表。
- 没有临床图片时省略 `临床数据图片`。`专家点评` 必须明确为分析性内容，不得冒充来源事实。
- `数据一致性审核` 位于整个文件末尾，覆盖所有适应症。

## 核心临床表

每个适应症的主要有效性和安全性数据使用 Markdown 表格。表格上方只写 `source_label`：

```markdown
## [NSCLC_1L] 非小细胞肺癌一线

### 核心数据

> ASCO2026

| 指标 | ABC123 + Pembrolizumab | 对照组 | HR | p-value |
|------|-------------------------|--------|----|---------|
| N | 100 | 50 | — | — |
| ORR | 41.4% | 25.3% | — | <0.0001 |
| cORR | 34.5% | — | — | <0.0001 |
| DCR | 87.9% | — | — | <0.0001 |
| mPFS | 11.3 | 6.8 | 0.62 | <0.0001 |
| mOS | 22.1 | 14.2 | 0.73 | <0.0001 |
| 最常见 AE | 恶心、血液事件（1-2级） | — | — | — |
```

### 表格组织规则

- 优先单表：有效性、安全性和亚组数据尽量合并为指标行，cohort 为列。
- 仅当列结构无法对齐时分成有效性主表和安全性或亚组分表；含有效性数据的表定义为主表。
- 第一条数据行为 `N`。同一列的数据必须属于列标题指明的 cohort。
- cohort 标题必须写明剂量、方案或分析人群，不能使用“高剂量组”“最大效果”等模糊描述。
- 不同分析人群分别分列，不得将总人群和可评估人群数据混用。
- 常见终点可使用 `ORR`、`cORR`、`DCR`、`mPFS`、`rPFS`、`mOS`、`mDOR`、`PSA50`、`PSA90`、`CR`、`PR`、`SD`、`PD`、`AE`；不常见终点写清中文全称。
- 原则上不在主表写 95% CI；审核表仍需核验来源中的 CI 和摘要引用的统计事实。
- 时间指标 PFS、OS、DOR 等只写数字，不在单元格重复单位；单位必须在表格上下文或备注中明确，且不得擅自转换。
- 百分比保留一位小数。可在值后注明分析样本量，如 `11.3 (N=82)`。
- 缺失数据用 `—`；明确未成熟或未评估可用 `NE` 并在备注中解释。
- `TEAE`、`TRAE`、`AE`、`SAE` 必须严格沿用来源术语，不得互换。

## 试验设计

每个适应症至少记录可由来源支持的设计事实。多适应症来源必须分别说明人群、cohort 和方案。

```markdown
### 试验设计

| 设计要素 | 内容 |
|----------|------|
| 研究类型 | {随机、开放标签等} |
| 试验名称 | {trial_name} |
| 阶段 | {phase} |
| 入组人数 | {来源值} |
| 入组人群 | {适应症、治疗线和关键标志物} |
| 用药方案 | {剂量、频次、联合方案} |
| 对照 | {对照方案或 —} |
| 主要终点 | {来源值} |
| 数据截止 | {来源值或 —} |
```

基线人群数据可追加到本节。来源未披露的事实写 `—`，不得推测。

## 专家点评

专家点评仅供参考，应与提取事实分开。可讨论疗效、安全性、研究设计、局限性和后续方向，但不得引入未经来源支持的确定性临床数据，也不得给出诊疗建议。

## 数据一致性审核

独立 data verifier 必须逐项对照唯一 raw 原文。审核只判断摘要中的临床数值和试验事实是否有依据，不评价临床价值，也不补充新数据。

必须审核：

- 样本量：`N`、`n`。
- 疗效：ORR、cORR、DCR、CR、PR、SD、mPFS、rPFS、mOS、mDOR、DOR。
- 统计量：HR、p-value、CI。
- 安全性：AE、TEAE、TRAE、SAE、>=3 级事件、减量、停药、死亡。
- 试验事实：适应症、治疗线、phase、trial name、cohort、剂量、方案、对照、会议或发布日期、数据截止时间。

状态定义：

- `PASS`：raw 中有直接证据或明确等价表达，且组别、剂量、单位和时间点一致。
- `WARN`：raw 中有近似依据，但术语、组别、单位、时间点或上下文需要人工确认。
- `FAIL`：raw 中无依据，或组别、剂量、单位、适应症、治疗线、时间点对应错误。

```markdown
## 数据一致性审核

| indication_id | 数据项 | summary 中的值 | raw 证据 | 状态 | 问题 |
|---------------|--------|----------------|----------|------|------|
| NSCLC_1L | ORR | 42.3% | "...ORR was 42.3%..." | PASS | — |
| NSCLC_2L | mPFS | 11.3 | 未找到 | FAIL | raw 中未出现该数值 |
| NSCLC_2L | >=3 TRAE | 25.0% | "...grade 3 or higher TEAEs..." | WARN | raw 为 TEAE，summary 写 TRAE |
```

- summary 中每个临床数值、试验事实和关键分组都必须有审核行；第一列必须填写与 frontmatter 完全一致的 `indication_id`，且审核表覆盖全部 indication IDs。
- cohort、剂量、治疗组、对照组和适应症不得串列或串组。
- 原文单位为 weeks 而摘要改写为 months 时为 `FAIL`。
- 原文没有的数据不得写成确定值。
- 审核出现任何 `FAIL` 时，`verification` 不得为 `passed`，`verification_fail_count` 必须等于实际 FAIL 数。
- 只有 `verification: passed`、`verification_fail_count: 0`、`verification_coverage: complete`、审核章节存在且审核章节中没有任何 `FAIL` 的摘要，才可更新药品页、适应症页或根索引。

## 验证清单

- [ ] 路径和文件名为 `{research_dir}/{company_id}/{drug_id}/summary/{drug_id}@{source_label}.md`，且没有 `company/` 中间层。
- [ ] 此摘要只对应一个 raw，且使用规范来源链接 `> 来源原文: [label](../raw/file.md)`。
- [ ] raw `source` 为准确 URL（不 percent decode）或 PDF 的 resolved absolute POSIX path，且去重与替换比较使用同一个持久值。
- [ ] `indications` 是至少含一个对象的列表，正文以 `## [{indication_id}] {indication}` 分组，trial 字段遵守继承规则。
- [ ] 未使用单数适应症字段，也未在文件名中编码适应症。
- [ ] 每个适应症的主表以指标为行、cohort 为列，第一条数据行为 `N`。
- [ ] 多适应症数据、cohort、剂量和对照没有串组。
- [ ] 试验设计事实可在 raw 中追溯，缺失事实未被猜测。
- [ ] 审核位于文件末尾并覆盖全部数值和试验事实。
- [ ] `verification_fail_count` 与审核结果一致；存在 FAIL 的摘要未标记为 passed。
