---
name: clinical-extractor
description: |
  临床数据提取执行步骤（供clinical-research主skill调用）
  
  当主skill路由到本文件时，按以下步骤执行：
---

# 临床数据提取 - 执行步骤

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 总流程：检测输入 → 生成 raw/ 原文文件 → 生成、审核并写入 source/ → 生成或更新 drug/。

## 执行原则

- 必须按 4 个主步骤顺序执行，不得跳过。
- `raw/` 是原始采集层，只保存工具提取结果，不允许大模型改写、总结、翻译、重排、删减或补全正文。
- `source/` 是结构化摘要层，必须先通过数据一致性审核，再写入正式文件。
- 具体文件格式只以 `../schema/summary-spec.md` 和 `../schema/drug-spec.md` 为准；本 workflow 不重复定义格式细节。
- 如果任一步失败，按该步骤的失败处理规则终止或回修，不得继续污染后续索引。

## Step 1: 检测输入

检测当前或上一条对话，确定输入类型：

- 包含 URL：进入 Step 2，按 URL 提取。
- 包含 PDF 文件路径：进入 Step 2，按 PDF 提取。
- 同时包含多个 URL/PDF：逐个处理，每个来源独立执行 Step 2-4。
- 不包含 URL 或 PDF：要求用户补充来源，终止执行。

同时准备以下信息：

- 原始来源标识：URL 或 PDF 文件名。
- 数据来源日期：优先使用资料发布日期，否则使用当前日期。
- 文件基础名：用于 `raw/` 和 `source/` 文件命名。

文件基础名确定规则：

- URL：优先使用 HTML `<title>`，其次页面第一个 `<h1>`，其次 URL 路径最后一段，最后自动生成 `网址资料_{日期}`。
- PDF：优先使用 PDF 元数据标题，其次正文第一行标题，其次文件名，最后自动生成 `PDF资料_{日期}`。
- 清理文件名中的 `/\?%*:|<>`，替换为 `_`，长度限制 50 字符。

## Step 2: 生成并写入 raw/

目标：把来源内容完整保存为原始资料文件，供后续摘要和审核使用。

### 2.1 提取原始内容

URL 来源调用：

```
tavily_extract urls=<URL> extract_depth=advanced include_images=true
```

PDF 来源优先使用：

```
pdftotext <pdf路径> -
```

如果 `pdftotext` 不可用或效果差，再使用：

```
nano-pdf --file <pdf路径> --action read
```

### 2.2 写入 raw 文件

读取 `../config.yaml` 获取 `raw_dir`。

在提取结果前添加 YAML frontmatter：

```yaml
---
source: {URL 或 PDF文件名}
created: {YYYY-MM-DD}
---
```

写入：

```
write path={raw_dir}/{文件基础名}.md content={YAML frontmatter + 原始提取内容}
```

### 2.3 raw 质量要求

- `raw/` 正文必须来自提取工具返回结果。
- 禁止使用大模型对正文做任何压缩、总结、翻译、重排、去重、润色或补全。
- 只允许添加 YAML frontmatter。
- 如果提取失败、正文为空、或明显不是临床资料，返回错误报告并终止后续步骤。

## Step 3: 生成、审核并写入 source/

目标：从 `raw/` 生成规范化临床摘要，并在正式写入前完成数据一致性审核。

### 3.1 生成 source 草稿

读取 `../schema/summary-spec.md`。

基于 Step 2 写入的 `raw/` 文件生成 source 摘要草稿。摘要结构、字段、章节、表格、数据一致性审核章节均必须遵守 `summary-spec.md`。

### 3.2 数据一致性审核

在保存正式 `source/` 文件前，必须 spawn 一个受限的 **data verifier subagent**，独立检查 source 草稿与 raw 文件是否数据一致。

data verifier subagent 只能：

- 读取本次生成的 `raw/` 文件。
- 读取或接收 Step 3.1 生成的 source 摘要草稿。
- 按 `../schema/summary-spec.md` 的数据一致性审核规范输出审核结果。

data verifier subagent 禁止：

- 联网。
- 修改任何文件。
- 补充新数据。
- 评价临床价值。
- 改写摘要正文。
- 基于常识、外部知识或推测判定为通过。

审核只检查 source 草稿中的临床数据和试验事实是否能在 raw 中找到依据，尤其关注样本量、疗效指标、统计量、安全性数据、phase、trial name、cohort、剂量、治疗组、对照组、适应症、治疗线数、会议/发布日期。

### 3.3 审核失败处理

- 如果存在 `FAIL`：不得保存正式 `source/` 文件，不得进入 Step 4。必须回到 Step 3.1 修正 source 草稿，然后重新执行 Step 3.2。
- 如果存在 `WARN`：可以继续，但必须在最终返回报告中列出 WARN 项，提示用户人工复核。
- 只有 `FAIL = 0` 时，才能写入正式 `source/` 文件。

### 3.4 写入 source 文件

读取 `../config.yaml` 获取 `source_dir`。

确认 source 摘要正文和数据一致性审核结果已经按 `../schema/summary-spec.md` 组织为完整内容。

写入：

```
write path={source_dir}/{文件基础名}.md content={符合 summary-spec.md 的完整 source 内容}
```

不得单独生成审核报告文件；审核内容必须按 `summary-spec.md` 保存在同一个 `source/` 文件中。

## Step 4: 生成或更新 drug/

目标：把本次通过审核的 source 数据合并进药品索引。

### 4.1 读取规范和配置

读取：

- `../schema/drug-spec.md`
- `../config.yaml`

从配置中获取 `drug_dir`。

### 4.2 确定药品文件名

从 Step 3 生成的 source YAML 中提取 `drug` 和 `drug_aliases` 字段。

按 `drug-spec.md` 的药品名称优先级选择文件名：

```
开发代码 > 短名称/缩写 > 中文通用名 > 英文通用名
```

示例：摘要中 `drug="Examplemab"`，`aliases=["示例ADC", "ABC123", "exa-mab"]`，文件名选 `ABC123.md`。

### 4.3 新建或增量更新

检查：

```bash
ls {drug_dir}/{药品名称}.md
```

如果文件不存在：

- 按 `drug-spec.md` 创建新药品索引文件。
- 纳入本次 source 的适应症、核心临床数据、来源链接和时间线。

如果文件已存在：

- 读取现有文件。
- 只更新与本次 source 相关的适应症、数据行、来源链接和时间线。
- 如果同一 source 已经存在于来源列表，避免重复追加。
- 更新 frontmatter 的 `updated` 日期。
- 保留与本次任务无关的手动补充内容。

如果 drug 更新失败：

- 报告 `source/` 已生成但 `drug/` 更新失败。
- 不回滚已经通过审核并写入的 `source/` 文件。

## 返回

报告：

- raw/ 文件路径
- source/ 文件路径
- drug/ 文件路径 + 操作类型（新建、更新、跳过或失败）
- 数据一致性审核结果（PASS/WARN/FAIL 数量；如有 WARN，列出需要人工复核的数据项）
- 提取的关键数据摘要
