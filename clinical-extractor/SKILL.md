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
- `source_label`、文件名、frontmatter 和正文结构以 `../schema/summary-spec.md` 为权威契约。

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
- raw 正文只能是工具返回的完整原始输出；唯一的例外是 `<= 10 MiB` 的附件化 PDF，其 raw 正文为一行嵌入引用 `![[attachments/{drug_id}@{source_label}.pdf]]`。summary 初写审核状态必须为 `pending/null/null`，不得自行验证。

## 工作流

1. **校验门禁与来源身份。** 任一门禁不是 `yes` 即停止。目标已存在时返回“发现重复”，不得覆盖、删除、修改、追加序号或清理索引，即使调用方声称已授权替换。标签冲突只能使用 trial、abstract、analysis 等语义稳定后缀，不得使用 `_2` 等序号。
2. **提取来源。** 记录 canonical source、来源明确披露的 `published_date`、实际提取日 `created` 和来源类型；发布日期或 phase 不明写 `null`。
3. **写入 raw。** 创建 `{raw_dir}/{drug_id}@{source_label}.md`，仅添加以下 frontmatter，随后原样保存完整工具输出（`<= 10 MiB` 的附件化 PDF 例外：正文只写嵌入引用 `![[attachments/{drug_id}@{source_label}.pdf]]`）：

```yaml
---
source: {准确 URL，或 PDF 的附件绝对路径（<= 10 MiB）/ resolved absolute POSIX path（> 10 MiB）}
published_date: {YYYY-MM-DD 或 null}
created: {YYYY-MM-DD}
---
```

4. **无数据跳过（兜底门禁）。** 来源为公司公告或新闻媒体（`source_type` 为 `company_release`，或 `other` 且为新闻/公告页）时，检查刚创建的 raw：若不含任何具体临床数值（样本量 N、ORR/PFS/OS/HR/CI、AE 发生率等），删除仅由本次创建的 raw 并返回 `无数据跳过`，不生成 summary，不写入任何文件。期刊与会议来源无数值时按提取失败处理，不适用本门禁。
5. **盘点图片并写入 summary。** 在生成 summary 前完成来源图片盘点，按 summary-spec 将所有应收录图片写入对应适应症的 `### 临床数据图片`。URL 来源使用原图远程 URL；PDF 来源只引用实际生成的附件。若有候选图片但地址/图像未能确认，保留可确认的图号、标题和失败原因，并将图片审计标记为 `incomplete`，不得按“无图片”处理。
6. **核对配对和图片审计。** 确认 raw/summary 同名、来源身份一致、canonical 链接正确且只创建一个 summary；逐项核对图片审计中标为 `include` 的项目均出现在正确适应症分组。输出 `image_status: complete / none / incomplete` 和逐项处置。只有盘点完成、所有应收录图片均已引用时为 `complete`；只有盘点完成且没有应收录图片时为 `none`；来源无法检查、有应收录图片缺少引用或图像无法生成/定位时为 `incomplete`。

### URL 提取

- 优先使用当前 harness 的高级网页提取能力并包含图片，失败后使用可用网页抓取工具；403、反爬或空正文时可尝试同文官方镜像，仍失败则停止，不得由模型重建 raw。网页提取器返回了正文，不代表图片已完整提取，必须单独执行下述图片盘点。
- URL 保存用户准确提供或工作流明确采用的 canonical final URL，不得改写；后续比较使用该持久字符串，不做 percent decode 或其他归一化。
- raw 保存完整工具输出，不为补图片清单而改写或追加内容。

#### URL 图片盘点

1. 只检查文章正文区域。结合正文中的 Figure/Table 引用和图注，检查网页提取结果；若结果没有图片元数据且浏览器/页面 DOM 工具可用，再检查原来源页正文 DOM（包括 `figure`、表格图像及其图注）。403/反爬时优先使用可用的浏览器会话读取页面，不反复请求被拦截的端点。不能只靠纯文本正文或 `<img>` 搜索结果判断图片齐全。
2. 对正文内的 `<figure>`、表格图像及其图片元素检查 `src`、`srcset`、`data-src`、`data-srcset` 等懒加载属性；`srcset` 有多个尺寸时选原图/最大尺寸。相对地址按来源页面地址解析为绝对地址，保留来源给出的 URL 参数和编码。
3. 对候选项逐一记录图号/表号、来源标题、类型、适应症归属、处理结果（`include` / `exclude` / `unresolved`）及理由。按 `../schema/summary-spec.md` 纳入主要/重要次要终点、安全性、基线、患者流程、试验设计等临床图表；图片化 Table 即使数值已转录也必须纳入。排除页面装饰、广告、无关图片及重复缩略图。
4. 每个 `include` 项都在对应适应症的 `### 临床数据图片` 中用 Markdown 图片语法引用来源实际使用的原图 URL，例如 `![Figure 1. 来源标题](https://publisher.example/.../figure1.jpg)`。只写图号/表号和来源标题，不自行补充图中数值或结论；不得下载、截图、转存到 `attachments/` 或使用第三方图床；本地化由 Obsidian 插件在打开时完成。
5. URL 已确认但访问受限时仍写入该 URL；只有确认是登录/机构权限/来源站访问限制时才加访问提示。原图地址无法确认时不得猜 URL 或伪造链接；在图片章节写明图号/标题和未解决原因，审计状态设为 `incomplete`。
6. 只有实际检查了来源正文图片清单、全部应收录项目都已写入且没有未解决项时，`image_status` 才是 `complete`。只有同样完成检查并确认无应收录图片时才是 `none`。无法检查来源、疑似缺图或 URL 未解析时均为 `incomplete`，不得静默省略图片章节。

### PDF 提取

- 先按大小分流，决定 raw 的正文形态与 `source` 值：
  - `<= 10 MiB`：运行以下脚本把 PDF 复制为根 `attachments/{drug_id}@{source_label}.pdf` 附件（与配对 raw/summary 同名）：

    ```text
    python {clinical_research_dir}/scripts/attach_pdf.py "{pdf_path}" "{attachments_dir}" "{drug_id}@{source_label}"
    ```

    输出 `attached {附件绝对 POSIX 路径}` 时，canonical source 固定为该附件路径；输出 `too_large` 时按 `> 10 MiB` 分支处理。
  - `> 10 MiB`：canonical source 固定为输入路径经 `Path.resolve(strict=True).as_posix()` 得到的绝对 POSIX 路径。预检、去重、写入和报告均使用同一值。
- `<= 10 MiB` 的 raw 只写 frontmatter（`source` 为附件绝对路径）和一行嵌入引用 `![[attachments/{drug_id}@{source_label}.pdf]]`，不保存提取文本。
- `> 10 MiB` 的 raw 按可用性依次使用 harness/PDF 工具、系统 `pdftotext` 或 `nano-pdf`，最后可运行：

```text
python {clinical_research_dir}/scripts/pdf_extract_fallback.py "{pdf_path}"
```

- 命令须可在 Windows PowerShell 运行，不依赖 Bash；所有方式失败时停止，不得由模型重建 raw。
- 无论哪种大小，都要从 PDF 读取文本用于生成 summary（`<= 10 MiB` 时读取附件或原 PDF）。
- 对 summary-spec 定义的应收录 PDF 图表，使用可用工具优先裁剪图表，否则保存整页到调用方 `attachments_dir`。名称如 `{drug_id}@{source_label}@figure-01.png`，不得覆盖；summary 以 `../../attachments/{file}` 引用。
- 渲染不可用或失败不阻断文本提取；不得伪造附件或写入不存在的图片链接。图片章节写明受影响图号/表号和失败原因，报告 `image_status: incomplete` 及“PDF 重要图片未生成”警告。

### 内容要求

- raw 正文不得压缩、总结、翻译、重排、去重、润色或补全。官方 API 补充缺失 metadata 时，只能在末尾追加注明来源和获取日期的独立章节。
- summary 只纳入原文支持的适应症：frontmatter `indications` 用标量 ID 列表、顺序与正文分节一致；治疗线、生物标志物与试验信息写入 `试验设计`（多试验分表）；raw 含患者基线数据时生成 `### 患者基线` 表（cohort 与核心数据对齐），无基线则省略。phase、cohort、方案、治疗线或 cutoff 不明时写“未披露”或 `null`，不得推断或串组。
- summary 图片必须遵守 `../schema/summary-spec.md` 的纳入范围、来源地址、适应症分组和失败标记规则；URL 图只引用原图远程地址，PDF 图只引用实际生成的附件。

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
- image_status: complete / none / incomplete
- image_audit: {检查范围、候选图逐项 include/exclude/unresolved 及理由；include 项注明 summary 分组}
- attachments: {本次实际生成的 PDF 附件及 PDF 图片列表}
- warnings: {图片不可用等非致命问题}
- 结果: 成功（图片完整或确认无应收录图片） / 部分成功（图片待补） / 失败 / 发现重复 / 无数据跳过
- 原因: {如有}
```
