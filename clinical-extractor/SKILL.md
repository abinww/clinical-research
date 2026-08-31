---
name: clinical-extractor
description: |
  临床数据单来源提取单元。由 multi-extractor 或 batch-extractor 调用，
  将一个 URL 或 PDF 写成一个 raw 和一个支持多适应症的 summary。
---

# 临床数据提取 - 单来源单元

> 不从主接口直接触发。本 skill 只负责单来源提取，不负责身份解析、独立验证或索引。

## 2.0 不变量

- 配置只有 `research_dir`。不得从配置读取或推测 `raw_dir`、`summary_dir`、`drug_dir`。
- 调用方必须提供规范共享身份对象和完整路径键：至少包含 `research_dir`、`company_id`、`drug_id`、`drug_aliases`、`archive_company`、`company_ids`、`drug_dir`、`drug_page`、`raw_dir`、`summary_dir`、`attachments_dir`；其他身份字段原样使用。兼容字段 `companies` 如存在，必须与 `company_ids` 完全相同。
- 一个来源恰好创建一个 raw 和一个 summary。两者文件名均为 `{drug_id}@{source_label}.md`。
- 一个 summary 通过 frontmatter 的 `indications` 数组及对应正文分节承载该来源的全部适应症；不得按适应症拆成多个 summary。
- summary 的规范来源行只能是相对 Markdown 链接：`> 来源原文: [label](../raw/file.md)`。不得写 wikilink、绝对路径或旧布局路径。
- 本 extractor 是严格 create-only：不得覆盖、删除或修改任何既有 raw、summary、附件或索引引用。普通提取写正式目标；事务替换可写 orchestrator 明确传入的 staging `raw_dir`、`summary_dir`、`attachments_dir`。两者都要求目标不存在；extractor 不负责 commit、清理或替换。
- 不提供 v1 布局、文件名或链接兼容逻辑。

## 输入与门禁

输入为一个 URL 或一个 PDF 路径，以及调用方提供的：

```text
config_path: {clinical_research_dir}/config.yaml
research_dir: {配置解析后的绝对路径}
company_id: {值}
drug_id: {值}
drug_aliases: {别名全集}
archive_company: {归档公司短名，与 company_id 一致}
company_ids: {根索引规范公司 ID 列表}
target / molecule_type: {如有}
drug_dir: {research_dir}/{company_id}/{drug_id}
drug_page: {drug_dir}/{drug_id}.md
raw_dir: {正式 drug_dir/raw，或 replacement staging raw 目录}
summary_dir: {正式 drug_dir/summary，或同一 replacement staging summary 目录}
attachments_dir: {正式 research_dir/attachments，或同一 replacement staging attachments 目录}
source_label: {Windows 安全且在该药物下唯一的短标签}
```

处理前确认：

```text
EXTRACT WRITE GATE:
- config_path 已读取且只有 research_dir 参与路径解析: yes
- 身份对象与全部路径键齐全；普通路径符合正式布局，或三个写目录属于同一 replacement staging 根: yes
- drug_page 存在: yes
- summary-spec.md 已读取: yes
- raw 与 summary 目标文件名均为 {drug_id}@{source_label}.md: yes
- 两个目标文件均不存在: yes
```

任一项不是 `yes` 时停止。任一目标已存在时返回“发现重复”，不得覆盖、删除、修改、追加序号或清理索引，即使调用方声称替换已获授权也一样。标识符和 `source_label` 必须满足 summary-spec 的严格语法；冲突标签只能改为描述 trial、abstract、analysis 等差异的语义稳定标签，不得使用 `_2` 等不透明序号。

## Step 1: 提取来源

同时记录：canonical source、原文明确给出的 `published_date`、实际提取日期 `created`、来源类型。URL 保持用户准确提供或工作流明确采用的 canonical final URL 字符串，不得改写。本地 PDF 的 canonical source 必须是对输入执行 `Path.resolve(strict=True).as_posix()` 后的绝对 POSIX 路径。无法确认发布日期或 phase 时写 `null`。

### URL

优先使用当前 harness 的高级网页提取能力并包含图片；失败后使用可用的网页抓取工具。遇到 403、反爬或空正文时可尝试同文官方镜像；仍失败则报告，不得由模型重建 raw。

- raw 保存成功提取工具返回的完整正文，只允许增加 YAML frontmatter。
- raw `source` 保存上述准确 URL。后续去重和替换必须与该持久值做准确字符串比较，不得使用 percent-decoded 或其他归一化变体。
- URL 图片保持远程 URL。重要临床图可在 summary 中直接嵌入远程 URL，不下载到 `attachments/`。
- 抓取到的广告、站点装饰图不写入 summary。

### PDF

按可用性优先使用当前 harness/PDF 工具读取；其次使用系统 `pdftotext` 或 `nano-pdf`；最后可运行：

```text
python {clinical_research_dir}/scripts/pdf_extract_fallback.py "{pdf_path}"
```

命令必须可在 Windows PowerShell 中运行，不依赖 Bash。所有文本提取方式均失败时停止，不得由模型重建 raw。

读取和写入前解析 PDF 路径，raw `source` 固定保存 resolved absolute POSIX path；Windows 上必须是 `Path.resolve(strict=True).as_posix()` 的结果。调用方预检、药品树内去重和本 skill 返回报告都使用这同一个 canonical 值，不得退化为文件名或相对路径。

对包含关键临床表格、Kaplan-Meier 曲线或试验设计图的 PDF：

1. 使用可用 harness/PDF 渲染或截图工具输出到调用方提供的 `attachments_dir`；普通提取时为根附件目录，replacement 时为 staging 附件目录。
2. 优先裁剪到图表区域；无法可靠裁剪时保存包含该图的完整页面。
3. 使用 Windows 安全且可追溯的名称，例如 `{drug_id}@{source_label}@figure-01.png`，不得覆盖已有附件。
4. summary 从自身目录以相对路径引用根附件，例如 `../../../attachments/{file}`。
5. 若没有可用渲染/截图能力或渲染失败，文本提取仍可继续；省略无法生成的本地图片，并在返回报告中明确列出“PDF 重要图片未生成”及原因，不得伪造附件。

## Step 2: 写入 raw

写入 `{raw_dir}/{drug_id}@{source_label}.md`：

```yaml
---
source: {准确 URL，或 PDF 的 resolved absolute POSIX path}
published_date: {YYYY-MM-DD 或 null}
created: {YYYY-MM-DD}
---
```

frontmatter 后必须是工具提取的完整原始输出。禁止压缩、总结、翻译、重排、去重、润色或补全正文。若需从官方 API 补充缺失 metadata，只能在原文末尾追加注明来源和获取日期的独立章节，不得修改原始输出。

正文为空、明显不是目标临床资料或无法原样保留时，删除本次尚未配对完成的输出并返回失败，不能留下孤立的新文件。

## Step 3: 写入单个 summary

从刚写入的 raw 生成 `{summary_dir}/{drug_id}@{source_label}.md`，格式遵守 `../schema/summary-spec.md`，并以本文件的 2.0 不变量覆盖其中任何旧布局示例。

- H1 后紧接：`> 来源原文: [{source_label}](../raw/{drug_id}@{source_label}.md)`。
- frontmatter 使用规范身份对象，并包含 `indications` 数组。每项至少给出稳定 `indication_id` 和展示名，可携带 `trials`；只纳入原文实际支持的适应症。
- 正文标题固定为 `## [{indication_id}] {indication}`。适应症/试验级 phase、regimen、cutoff 按 summary-spec 的继承规则填写；数据不得串组。
- `combination_regimen`、phase、cohort、治疗线和数据时间点无法确认时明确写“未披露”或 `null`，不得推断。
- 图片遵循 Step 1：URL 图保留远程链接；PDF 图只引用已实际生成的根附件。
- 提取方不得写 `verification: passed`，也不得自行完成审核。初次写入固定使用 `verification: pending`、`verification_fail_count: null` 和 `verification_coverage: null`；末尾审核章节及最终状态由独立 data-verify agent 写入。

写入前再次确认 raw 已存在、canonical source link 精确指向它、summary 只有一个且文件名匹配。summary 写入失败时，报告配对失败并移除仅由本次任务新建的 raw；不得触碰任何既有文件。

## 返回

```text
- 来源: {raw frontmatter 中持久化的 canonical source}
- raw: {raw_dir}/{drug_id}@{source_label}.md
- summary: {summary_dir}/{drug_id}@{source_label}.md
- indications: {数组}
- attachments: {本次实际生成的 PDF 图片列表}
- warnings: {图片不可用等非致命问题}
- 结果: 成功 / 失败 / 发现重复
- 原因: {如有}
```
