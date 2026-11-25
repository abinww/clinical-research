# 临床摘要格式规范 (2.0)

本文件定义从单一临床来源生成摘要文件的格式。摘要位于药品目录内，是 `raw` 原文与药品页、适应症页之间唯一的结构化临床数据层。

## 一对一来源模型

```text
{research_dir}/{company_id}/
  {drug_id}.md
  raw/{drug_id}@{source_label}.md
  summary/{drug_id}@{source_label}.md
```

- 药品页 `{drug_id}.md` 直接位于公司目录根；`raw/`、`summary/` 是公司级共享目录，跨药品按文件名前缀 `{drug_id}@` 区分归属。

- 一个来源生成一个 `raw` 文件，再生成一个 `summary` 文件：`1 source -> 1 raw -> 1 summary`。
- 不得将多个网页、PDF、会议摘要或新闻稿合并为一个 raw 或 summary。
- 来源为 PDF 时按大小分流，两种分支都仍保持一个 raw 对应一个 summary：
  - `<= 10 MiB`（用户提交的 PDF）：PDF 复制到根 `attachments/{drug_id}@{source_label}.pdf`（与配对 raw/summary 同名），raw 正文只写嵌入引用 `![[attachments/{drug_id}@{source_label}.pdf]]`，不保存提取文本（避免乱码污染）；`source` 写附件绝对 POSIX 路径。summary 仍基于对该 PDF 的提取生成，审核证据以附件 PDF 为准。
  - `> 10 MiB`：维持文本提取，raw 正文保存提取文本，`source` 写原 PDF 的 resolved absolute POSIX path。
- extractor 永远只创建新文件，不得覆盖既有 raw 或 summary。它可创建 orchestrator 指定的 replacement staging 路径，但不得 commit 或删除。
- 替换只能由 multi-extractor 执行，且必须在 `{research_dir}/.temp/replacements/{run-id}` 中先提取、结构校验并由独立 verifier 通过。commit 前逐字节备份准确旧 pair、全部 managed index documents（药品页、涉及的适应症页、根索引）及受影响附件并校验哈希；附件在 manifest 中记录复用/新增/移除，绝不先删除。正式安装使用可恢复的原子 replace 和持久化事务状态，任一步失败回滚全部已改文件并校验旧状态。
- 实质不同的来源必须使用不同 `source_label`。
- summary 文件名固定为 `{drug_id}@{source_label}.md`，不包含 `indication_id`，也不使用网页标题或 raw 文件名。
- 一个来源涉及一个或多个适应症时，全部写在同一 summary，通过 YAML `indications` 标量列表和正文适应症分组表达。
- 摘要必须链接同目录的唯一 raw 原文，规范链接为 `> 来源原文: [label](../raw/file.md)`。

## 命名

`source_label` 是稳定、简短、人工可读的来源标签，通常为来源简称和年份，如 `ASCO2026`、`ESMO2026`、`NEJM2026`、`CompanyRelease2025`。同一基础标签对应多个实质不同来源时，必须添加最短的语义稳定后缀来描述来源差异，例如 `ASCO2026_TrialABC`、`ASCO2026_Abstract1234` 或 `ASCO2026_FinalAnalysis`；不得使用 `_2`、`_3` 等不透明顺序号。

严格语法如下，不得静默清洗输入：

- `company_id`、`drug_id`：必须通过 `scripts/layout.py:is_valid_identifier`；长度 1-80，首字符为 Unicode 字母或数字，内部仅允许 Unicode 字母/数字、空格、`.`、`_`、`-`，不得以空格或句点结尾，也不得是 Windows 保留设备名。
- `indication_id`：稳定 ASCII ID，语法 `[A-Za-z0-9][A-Za-z0-9._-]{0,79}`；同一规范适应症/治疗线跨来源保持不变。
- `source_label`：语法 `[A-Za-z0-9][A-Za-z0-9._-]{0,79}`，明确禁止 `@`、空格、中文和路径/Markdown 特殊字符。冲突只能加 trial/abstract/analysis 等稳定语义后缀。
- `drug_id` 必须与药品页一致；文件基名由唯一分隔符 `@` 连接 `drug_id` 与 `source_label`。

## 来源身份

raw frontmatter 的 `source` 是来源去重、替换和工作流比较使用的持久来源身份：

- URL 来源保存用户准确提供的 URL；若工作流明确采用重定向后的 canonical final URL，则保存该准确 final URL。不得 percent decode，也不得为比较而改写大小写、查询参数、尾部斜杠或编码形式；所有工作流比较 raw 中持久化的同一个准确字符串。
- 本地 PDF 来源：`<= 10 MiB` 时保存复制后的附件绝对路径 `{research_dir}/attachments/{drug_id}@{source_label}.pdf`（该附件必须实际存在）；`> 10 MiB` 时保存原 PDF 的 `Path.resolve(strict=True).as_posix()` 得到的绝对 POSIX 路径，例如 `C:/reports/trial.pdf`。两者都不得只保存文件名、相对路径、反斜杠路径或另造路径标识。
- raw 与 summary 的配对身份由同一 `{drug_id}@{source_label}` 文件名确定；准确重复键是当前公司布局中的 `(company_id, drug_id, source)`。相同 source 在另一药品下属于允许的跨药复用，不阻塞创建。近似来源只能提示人工判断。

## Frontmatter

```yaml
---
drug_id: ABC123
drug: 示例单抗
drug_aliases: [ABC-123, Examplemab]
indications: [NSCLC_1L, NSCLC_2L]
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
| `indications` | 字符串数组 | 必填，至少一个元素；元素为唯一稳定 `indication_id`，顺序与正文 `## [{indication_id}] {适应症}` 分组严格一致；不得嵌套对象（Obsidian 属性面板兼容） |
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

- 适应症显示名以正文 `## [{indication_id}] {适应症}` 分组头为准，不在 frontmatter 重复。
- 治疗线、生物标志物与试验信息（试验名称、阶段、方案、数据截止）一律写入正文 `试验设计`，不在 frontmatter 表达。
- 顶层 `phase`、`combination_regimen`、`trial_name` 只有在所有适应症/试验相同时才作共同默认，否则写 `null`；显式 `null` 表示未知。
- 探索性泛瘤种可以出现在 `indications` 中，但不会因此建立适应症页。
- 同一来源对不同适应症采用不同方案、阶段或试验时，在对应正文的 `试验设计` 中明确差异。
- 不使用单数 `indication_id`、`indication` 顶层字段，不使用嵌套对象或对象列表，也不使用将适应症编码进文件名的设计。
- summary 初次生成时必须写 `verification: pending`、`verification_fail_count: null` 和 `verification_coverage: null`，不得预先写 `passed`；示例中的 `passed/0/complete` 表示独立审核完成后的最终状态。

## 正文结构

```markdown
# {drug_id}@{source_label}

> 来源原文: [ASCO 2026 abstract](../raw/ABC123@ASCO2026.md)

## [{indication_id A}] {适应症 A}

### 核心数据

### 患者基线

### 临床数据图片

### 试验设计

### 专家点评

## [{indication_id B}] {适应症 B}

### 核心数据

### 试验设计

### 专家点评

## 数据一致性审核
```

- 正文必须按 `indications` 顺序分组，每个 `## [{indication_id}] {适应症}` 与列表中一个 ID 一一对应；稳定 ID 是机器映射键，适应症显示名以分组头为准。
- 来源链接紧随一级标题且全文件只写一次，必须采用 `[label](../raw/file.md)`，其中 label 是可读来源名。
- 来源为 `<= 10 MiB` 的附件化 PDF 时，raw 正文只是嵌入引用；summary 的来源链接仍指向该 raw，审核证据从附件 PDF 读取。
- 每个适应症独立包含核心数据、基线（如有）和试验设计；不得把多适应症数值混入同一张无明确分组的表。
- raw 未提供基线数据时省略 `### 患者基线`；只有在完成来源图片盘点并确认没有应收录的临床图片时，才可省略 `### 临床数据图片`。图片盘点未完成或图片地址无法确认，不得当作“没有图片”。`专家点评` 必须明确为分析性内容，不得冒充来源事实。
- `数据一致性审核` 位于整个文件末尾，覆盖所有适应症。

## 临床数据图片

### 纳入范围

- 图片盘点只检查来源正文/文章内容区域，不把页面导航、广告、Logo、图标和装饰图片当作临床图片。
- 必须收录正文中的关键临床图表：以图片发布的 Table（包括患者基线、疗效和安全性表）、主要或重要次要终点图、患者流程图、Kaplan-Meier 曲线、森林图、瀑布图、随时间变化曲线及与试验设计直接相关的图。
- 补充材料中的图片仅在正文明确引用其关键结果，或 summary 使用了该图所支持的数据时收录；同一图的缩略图和原图只收录原图一次。
- 不得因图中数值已转录到 `核心数据` 或 `患者基线` 表格而省略原图。

### URL 来源图片

- 必须使用 Markdown 图片语法和来源页面实际使用的原图地址，例如：
  `![Figure 1. 主要终点](https://publisher.example/article/figure1.jpg)`
- 地址必须来自来源页面对应的图片元素（如 `src`、`srcset`、懒加载属性）或出版方提供的 canonical 图片地址。相对地址按来源页面地址解析为绝对地址；`srcset` 提供多种尺寸时选原图/最大尺寸。除解析相对地址外，不改写 URL、查询参数或编码。
- 不得用截图、搜索引擎缓存、第三方图床、`blob:`/`data:` 地址或已失效的临时签名地址替代原图；URL 来源图片不得下载、转存至 `attachments/` 或改写成本地路径，由 Obsidian 插件在打开时负责本地化。
- 图注仅写来源中的图号/表号和标题，不添加来源未支持的解读或数值。图片本身不是数值审核证据；summary 中引用的临床数值仍须能由 raw 文本或实际可读取的 PDF 附件支持。
- 图片 URL 已确认但访问受限时仍保留原 URL；只在确认存在登录、机构权限或来源站访问限制时，在图片下标注相应提示，不因访问失败而删除图片。
- 已确认应收录但原图 URL 无法从来源确认时，不得猜测或造链接；在 `### 临床数据图片` 中注明图号/表号、标题及未能确认地址的原因，并将图片审计标记为不完整。

### PDF 来源图片

- PDF 图片只引用实际生成且存在的附件；summary 与 vault 根 `attachments/` 的相对路径为 `../../attachments/{file}`，使用 Markdown 图片语法，例如 `![Figure 1. 来源标题](../../attachments/{file})`。不得引用未生成的附件。
- PDF 图表渲染失败时不得伪造图片或 broken link；在图片章节说明图号/表号及失败原因，并将图片审计标记为不完整。

### 分组

- 每张图只放在其数据所属的适应症分组；同一张图适用于多个适应症时放在最相关的一个分组，并在图注中说明其适用范围，不重复嵌入。
- 同一适应症中的图片按来源正文首次引用顺序排列；没有正文引用顺序时按图号/表号排列。
- 来源完成盘点且没有应收录图片时可以省略图片章节。存在未解决的候选图片时，图片章节不得省略，也不得将审计标记为“无图片”。

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
- 第一条数据行为样本量行，通常为 `N`；若来源区分入组与可评估人群，可沿用 `N / 可评估 n` 等明确写法。同一列的数据必须属于列标题指明的 cohort。
- cohort 标题必须写明剂量、方案或分析人群，不能使用“高剂量组”“最大效果”等模糊描述。
- 不同分析人群分别分列，不得将总人群和可评估人群数据混用。
- 常见终点可使用 `ORR`、`cORR`、`DCR`、`mPFS`、`rPFS`、`mOS`、`mDOR`、`PSA50`、`PSA90`、`CR`、`PR`、`SD`、`PD`、`AE`；不常见终点写清中文全称。
- 原则上不在主表写 95% CI；审核表仍需核验来源中的 CI 和摘要引用的统计事实。
- 时间指标 PFS、OS、DOR 等只写数字，不在单元格重复单位；单位必须在表格上下文或备注中明确，且不得擅自转换。
- 百分比保留一位小数。可在值后注明分析样本量，如 `11.3 (N=82)`。
- 缺失数据用 `—`；明确未成熟或未评估可用 `NE` 并在备注中解释。
- `TEAE`、`TRAE`、`AE`、`SAE` 必须严格沿用来源术语，不得互换。

## 患者基线

每个适应症在 `### 患者基线` 中用 Markdown 表格记录来源披露的基线人群特征；**raw 未提供基线数据时整节省略该节**。

```markdown
### 患者基线

| 基线特征 | ABC123 + Pembrolizumab | 对照组 |
|----------|------------------------|--------|
| 年龄（中位） | 62 | 61 |
| 男性 | 55.0% | 52.0% |
| ECOG 0-1 | 78.0% | 80.0% |
| 既往治疗线数（中位） | 2 | 2 |
| 脑转移 | 12.0% | 10.0% |
| PD-L1 >=1% | 45.0% | 44.0% |
```

- 指标为行、cohort 为列，cohort 划分必须与 `核心数据` 主表一致，不得串组。
- 按来源实际披露收录，常见指标如年龄（中位/范围）、性别、ECOG、既往治疗线数、关键转移部位、生物标志物基线（如 PD-L1）等；不得臆造指标。
- 百分比保留一位小数；数值保留来源单位；缺失写 `—`；不使用空白单元格。

## 试验设计

每个适应症至少记录可由来源支持的设计事实；治疗线与生物标志物只在本节表达。多适应症来源必须分别说明人群、cohort 和方案；同一适应症涉及多个试验时按试验分表，每表首行写明 `试验名称`。

```markdown
### 试验设计

| 设计要素 | 内容 |
|----------|------|
| 研究类型 | {随机、开放标签等} |
| 试验名称 | {trial_name} |
| 阶段 | {phase} |
| 治疗线 | {1L/2L/3L+/Later 或 —} |
| 生物标志物 | {入组标志物要求或 —} |
| 入组人数 | {来源值} |
| 入组人群 | {适应症、治疗线和关键标志物} |
| 用药方案 | {剂量、频次、联合方案} |
| 对照 | {对照方案或 —} |
| 主要终点 | {来源值} |
| 数据截止 | {来源值或 —} |
```

来源未披露的事实写 `—`，不得推测。

## 专家点评

专家点评仅供参考，应与提取事实分开。可讨论疗效、安全性、研究设计、局限性和后续方向，但不得引入未经来源支持的确定性临床数据，也不得给出诊疗建议。

## 数据一致性审核

独立 data verifier 必须逐项对照唯一 raw 原文。审核只判断摘要中的临床数值和试验事实是否有依据，不评价临床价值，也不补充新数据。

必须审核：

- 样本量：`N`、`n`。
- 疗效：ORR、cORR、DCR、CR、PR、SD、mPFS、rPFS、mOS、mDOR、DOR。
- 统计量：HR、p-value、CI。
- 安全性：AE、TEAE、TRAE、SAE、>=3 级事件、减量、停药、死亡。
- 基线：年龄、性别、ECOG、既往治疗线数、关键基线特征（转移、生物标志物基线等）等来源披露的数值。
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

- [ ] 路径和文件名为 `{research_dir}/{company_id}/summary/{drug_id}@{source_label}.md`，药品页为 `{research_dir}/{company_id}/{drug_id}.md`，且没有 `company/` 中间层。
- [ ] 此摘要只对应一个 raw，且使用规范来源链接 `> 来源原文: [label](../raw/file.md)`。
- [ ] raw `source` 为准确 URL（不 percent decode），或 PDF 的附件绝对路径（`<= 10 MiB`）/ 原 PDF resolved absolute POSIX path（`> 10 MiB`），且去重与替换比较使用同一个持久值。
- [ ] PDF 来源 `<= 10 MiB` 时：`attachments/{drug_id}@{source_label}.pdf` 存在且内容与 raw `source` 一致，raw 正文为嵌入引用；PDF 来源 `> 10 MiB` 时：raw 正文保存提取文本。
- [ ] `indications` 是至少含一个元素的标量字符串数组，无嵌套对象，顺序与正文 `## [{indication_id}] {适应症}` 分组一一对应；显示名以正文分组头为准。
- [ ] 未使用单数适应症字段、嵌套 frontmatter 对象，也未在文件名中编码适应症。
- [ ] 每个适应症的主表以指标为行、cohort 为列，第一条数据行为样本量行（如 `N` 或 `N / 可评估 n`）。
- [ ] 多适应症数据、cohort、剂量和对照没有串组。
- [ ] 治疗线、生物标志物与试验信息在正文 `试验设计` 中可追溯；raw 含基线数据时 `### 患者基线` 存在且 cohort 与核心数据对齐，无基线时省略。
- [ ] 图片盘点已完成；所有应收录的来源正文临床图表都在正确的适应症分组中出现，且图号/表号与来源一致。盘点未完成或有未解决图片时不得标记为“无图片”。
- [ ] URL 来源图片使用来源原图的 Markdown 远程 URL，未下载、转存或改写成本地路径；PDF 图片引用实际存在的 `../../attachments/{file}` 附件。
- [ ] 试验设计事实与基线数值可在 raw 中追溯，缺失事实未被猜测。
- [ ] 审核位于文件末尾并覆盖全部数值（含基线）和试验事实。
- [ ] `verification_fail_count` 与审核结果一致；存在 FAIL 的摘要未标记为 passed。
