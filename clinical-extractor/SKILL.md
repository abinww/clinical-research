---
name: clinical-extractor
description: |
  临床数据单来源提取单元。由 multi-extractor 或 batch-extractor 调用，
  将一个 URL 或 PDF 写成一个 raw 和一个支持多适应症的 summary。
---

# 临床数据单来源提取

## 职责与边界

本 skill 只处理一个 URL 或 PDF，创建一对 raw/summary；不从主接口触发，不解析身份、不独立验证、不索引，也不负责替换 commit 或清理。

## 输入与共享契约

调用方必须提供来源、`config_path`、`source_label`，以及符合 `../drug-identity/SKILL.md` 标准返回对象的完整身份与路径上下文。`config.yaml` 只能提供绝对 `research_dir`；不得读取或推测其他目录配置。`companies` 如存在，必须与 `company_ids` 完全相同。

- 普通提取使用正式 `raw_dir`、`summary_dir` 和根 `attachments_dir`。
- replacement 使用 orchestrator 明确提供、且同属一个 staging 根的三个对应目录。
- `source_label`、文件名、frontmatter、正文结构和字段继承以 `../schema/summary-spec.md` 为权威契约。

写入前输出并确认：

```text
EXTRACT WRITE GATE:
- config_path 已读取且只有 research_dir 参与路径解析: yes
- 身份对象与全部路径键齐全；普通路径符合正式布局，或三个写目录属于同一 replacement staging 根: yes
- drug_page 存在: yes
- summary-spec.md 已读取: yes
- raw 与 summary 目标文件名均为 {drug_id}@{source_label}.md: yes
- 两个目标文件均不存在: yes
```

## 不变量与写边界

- 一个来源恰好创建一个 `{drug_id}@{source_label}.md` raw 和一个同名 summary；单份 summary 承载来源支持的全部适应症，不按适应症拆分。
- 严格 create-only：不得覆盖、删除或修改任何既有 raw、summary、附件或索引引用。正式目录和 staging 目录都要求目标不存在。
- canonical source、配对命名和 summary 来源链接严格遵守 summary-spec，不支持 v1 布局、命名或 wikilink。
- raw 正文只能是工具返回的完整原始输出；summary 初写审核状态必须为 `pending/null/null`，不得自行验证。

## 工作流

1. **校验门禁与来源身份。** 任一门禁不是 `yes` 即停止。目标已存在时返回“发现重复”，不得覆盖、删除、修改、追加序号或清理索引，即使调用方声称已授权替换。标签冲突只能使用 trial、abstract、analysis 等语义稳定后缀，不得使用 `_2` 等序号。
2. **提取来源。** 记录 canonical source、来源明确披露的 `published_date`、实际提取日 `created` 和来源类型；发布日期或 phase 不明写 `null`。
3. **写入 raw。** 创建 `{raw_dir}/{drug_id}@{source_label}.md`，仅添加以下 frontmatter，随后原样保存完整工具输出：

```yaml
---
source: {准确 URL，或 PDF 的 resolved absolute POSIX path}
published_date: {YYYY-MM-DD 或 null}
created: {YYYY-MM-DD}
---
```

4. **写入 summary。** 从刚创建的 raw 生成唯一同名 summary，完整遵守 summary-spec。写入前再次确认 raw 存在、canonical 相对链接精确指向它、文件名匹配且只生成一个 summary。
5. **核对配对。** 确认两个文件同名、来源身份一致，并列出本次实际创建的附件和警告。

### URL 提取

- 优先使用当前 harness 的高级网页提取能力并包含图片，失败后使用可用网页抓取工具；403、反爬或空正文时可尝试同文官方镜像，仍失败则停止，不得由模型重建 raw。
- URL 保存用户准确提供或工作流明确采用的 canonical final URL，不得改写；后续比较使用该持久字符串，不做 percent decode 或其他归一化。
- raw 保存完整正文。URL 图片保持远程 URL；summary 只保留重要临床图，排除广告和站点装饰图。

### PDF 提取

- canonical source 固定为输入路径经 `Path.resolve(strict=True).as_posix()` 得到的绝对 POSIX 路径；预检、去重、写入和报告均使用同一值。
- 按可用性依次使用 harness/PDF 工具、系统 `pdftotext` 或 `nano-pdf`，最后可运行：

```text
python {clinical_research_dir}/scripts/pdf_extract_fallback.py "{pdf_path}"
```

- 命令须可在 Windows PowerShell 运行，不依赖 Bash；所有方式失败时停止，不得由模型重建 raw。
- 对关键临床表格、Kaplan-Meier 曲线或试验设计图，使用可用工具优先裁剪图表，否则保存整页到调用方 `attachments_dir`。名称如 `{drug_id}@{source_label}@figure-01.png`，不得覆盖；summary 以 `../../../attachments/{file}` 引用。
- 渲染不可用或失败不阻断文本提取；省略图片并报告“PDF 重要图片未生成”及原因，不得伪造附件。

### 内容要求

- raw 正文不得压缩、总结、翻译、重排、去重、润色或补全。官方 API 补充缺失 metadata 时，只能在末尾追加注明来源和获取日期的独立章节。
- summary 只纳入原文支持的适应症，按 summary-spec 表达身份、`indications`、试验继承和正文分节；phase、cohort、方案、治疗线或 cutoff 不明时写“未披露”或 `null`，不得推断或串组。
- summary 的 URL 图仅引用远程地址，PDF 图仅引用实际生成的附件。

## 失败与恢复

- raw 为空、明显不是目标资料或无法原样保留时，删除仅由本次创建且尚未配对的输出并返回失败。
- summary 写入失败时，报告配对失败并移除仅由本次创建的 raw；不得触碰任何既有文件。
- replacement 失败只报告 staging 结果，由 orchestrator 按其事务规则恢复；本 skill 不 commit、不清理正式树。

## 输出

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
