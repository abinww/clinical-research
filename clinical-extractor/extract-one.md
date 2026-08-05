# 单来源处理单元（extract-one）

> 本文件由 `clinical-extractor/SKILL.md` 派发调用，**不单独路由，不在其他任何地方调用**。
> 去重与 source_label / raw 基础名分配由编排层 Step 1 统一完成，本文件**不执行去重**。
> 职责：把单个来源（URL 或 PDF）处理为 `raw/` 文件 + `summary/` 文件，供后续 data-verify 审核与 indexer 归档。

## 输入

- 单个来源：一个 URL 或一个 PDF 文件路径
- 调用方分配的 `raw_filename`（raw 基础名）与 `source_label`（已含冲突后缀，直接使用，不再检查）

## 执行门禁

处理前必须确认：

```text
- ../config.yaml read: yes
- raw_dir:
- summary_dir:
- ../schema/summary-spec.md read: yes
```

任一必读文件无法读取，停止并报告原因。

## Step 1: 确认输入

- 单个 URL：进入 Step 2。
- 单个 PDF 文件路径：进入 Step 2。
- 其他输入：返回错误，终止。

同时准备以下信息：

- 原始来源标识:URL 或 PDF 文件名。
- 来源发布日期:从原文提取明确的发布日期、会议日期或期刊在线发表日期；无法确认时写 `published_date: null`，不得用当前日期代替。
- summary 生成日期:写入 `created`，使用实际生成日期。
- `drug_id`: 按 `drug-spec.md` 的优先级确定，用于 summary 目录与文件名。
- `indication_id`: 按 `indication-spec.md` 的规范命名确定；治疗线无法判断时保留 `line: null`，不得猜测为 1L。
- `source_label`: 使用调用方分配的值，不自行生成。
- `source_type`: 标准化为 `journal`、`conference`、`company_release`、`regulatory` 或 `other`。
- `published_date`: 只记录来源明确的发布日期、会议日期或期刊在线发表日期；无法确认时写 `null`，不得用提取日期代替。
- `combination_regimen`: 标准化联合用药方案；单药也必须明确记录。
- `clinical_match_key`: 按 `drug_id|combination_regimen|indication_id|phase` 生成；临床试验代码只能作为参考字段。
- `target`: 必填，使用最简形式（如 `PD-1`、`HER3/EGFR`），不带括号别名或机制注释；多靶点用 `/` 连接。

## Step 2: 生成并写入 raw/

### 2.1 提取原始内容

URL 来源调用:

```
tavily_extract urls=<URL> extract_depth=advanced include_images=true
```

PDF 来源优先使用:

```
pdftotext <pdf路径> -
```

如果 `pdftotext` 不可用或效果差,再使用:

```
nano-pdf --file <pdf路径> --action read
```

### 2.2 写入 raw 文件

在提取结果前添加 YAML frontmatter:

```yaml
---
source: {URL 或 PDF文件名}
published_date: {YYYY-MM-DD 或 null}
created: {YYYY-MM-DD}
---
```

`created` 是 raw 实际提取日期，不是来源发布日期；`published_date` 只能填写原文明确提供的来源日期。

写入:

```
write path={raw_dir}/{raw_filename}.md content={YAML frontmatter + 原始提取内容}
```

### 2.3 raw 质量要求

- `raw/` 正文必须是 `tavily_extract` / `pdftotext` / `nano-pdf` 返回内容的完整原始输出。
- 禁止使用大模型对正文做任何压缩、总结、翻译、重排、去重、润色、结构化或补全。
- 只允许添加 YAML frontmatter。
- 如果无法保留工具原始输出,必须终止;不得用模型重建 raw。
- 如果提取失败、正文为空、或明显不是临床资料,返回错误报告并终止后续步骤。

## Step 3: 生成并保存 summary/

目标:从 `raw/` 生成规范化临床摘要,保存到 `summary/{drug_id}/` 子目录下。审核在保存后由 data-verify 完成，不在本步骤执行。

### 3.1 生成 summary 内容

读取 `../schema/summary-spec.md`。

基于 Step 2 写入的 `raw/` 文件生成 summary。摘要结构、字段、章节、表格均必须遵守 `summary-spec.md`。摘要的 H1 标题后必须包含 `> 来源原文: [[raw/{当前 raw 文件名}.md]]` 一行,用于在 Obsidian 中建立 direct wikilink。

生成的 summary **不包含** 数据一致性审核章节和 verification 字段（由 data-verify 在后续步骤写入），其余内容完整。

### 3.2 写入 summary 文件

写入前必须通过:

```text
SUMMARY WRITE GATE:
- summary-spec.md read: yes
- summary filename matches {drug_id}@{indication_id}@{source_label}.md: yes
- "> 来源原文:" wikilink points to current raw file: yes
```

如果任一项不是 `yes`,不得写入 `summary/` 文件。

写入前必须确保子目录存在:

```
mkdir -p {summary_dir}/{drug_id}
write path={summary_dir}/{drug_id}/{summary_filename} content={符合 summary-spec.md 的完整 summary 内容}
```

## 返回

返回给调用方（编排层）：

```text
- 来源: {URL 或 PDF 文件名}
- raw/ 路径: {raw_dir}/{raw_filename}.md
- summary/ 路径: {summary_dir}/{drug_id}/{summary_filename}
- 结果: 成功 / 失败 / 跳过 / 发现重复
- 失败原因或重复信息: （如有）
```

**发现重复**：若执行中发现该来源已在 `raw/` 存在（编排层预检后新增的极端情况），不得询问用户，直接返回"发现重复"及匹配到的已有 raw/summary 路径，由主 agent 处理。
