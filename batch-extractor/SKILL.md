---
name: clinical-batch-extractor
description: |
  扫描 clinical-research 2.0 布局中尚无 summary 引用的 raw，
  按药物身份与路径上下文批量生成、独立验证并索引摘要。
---

# 批量处理 - 2.0

> 处理已存在的 raw。不得重新抓取来源、改写 raw，或使用 v1 目录和命名兼容逻辑。

## Step 1: 预检

读取 `config.yaml`，只获取 `research_dir`；同时读取 `summary-spec.md`、`drug-identity/SKILL.md`、`data-verify/SKILL.md` 和 `clinical-indexer/SKILL.md`。`{clinical_research_dir}` 是包含顶层 `SKILL.md` 的 skill 目录。

扫描命令必须使用跨平台 Python 脚本：

```text
python {clinical_research_dir}/scripts/find_unprocessed.py --config "{config_path}" --quiet
```

如调用方提供 `company_id` 或 `drug_id`，将身份过滤器传给脚本：

```text
python {clinical_research_dir}/scripts/find_unprocessed.py --config "{config_path}" --company-id "{company_id}" --drug-id "{drug_id}" --quiet
```

不得使用 `grep`、`find`、`sed` 或 Bash 管道。无输出表示没有待处理 raw，直接报告并结束。

## Step 2: 建立身份与路径上下文

`find_unprocessed` 返回相对 `research_dir` 的持久路径：

```text
{company_id}/{drug_id}/raw/{drug_id}@{source_label}.md
```

对每项用 `pathlib`/harness 路径能力解析并校验：

```text
company_id = 第 1 个路径组件
drug_id = 第 2 个路径组件
drug_dir = research_dir/company_id/drug_id
drug_page = drug_dir/{drug_id}.md
raw_dir = drug_dir/raw
summary_dir = drug_dir/summary
raw_file = raw_dir/{drug_id}@{source_label}.md
summary_file = summary_dir/{drug_id}@{source_label}.md
```

写入前必须读取根 `{research_dir}/index.md`，以 `drug_id`、别名和完整 vault 路径联合查找，确认恰好一个条目映射到 `{company_id}/{drug_id}/{drug_id}.md`。零个、多个、同一 `drug_id` 映射多路径或该路径映射另一药物时，该项失败且不得写 summary。

读取 `drug_page` 获得 `drug_aliases`、`target`、`archive_company`、`company_ids`、`molecule_type`；兼容字段 `companies` 如存在必须与 `company_ids` 相同。必要时以 drug-identity 的 `resolve_only` 模式校验。上下文必须含 `research_dir`、`drug_dir`、`drug_page`、`raw_dir`、`summary_dir`、`attachments_dir`。不得从 raw 猜测身份。路径、文件名、标识符/标签不合规，drug page 缺失或同名 summary 已存在时，记录失败/跳过并继续。

## Step 3: 每个 raw 生成一个 summary

读取 raw 和 `summary-spec.md`，写入唯一的 `summary_file`：

- 一个 raw 只生成一个 summary，不因多个适应症拆分文件。
- frontmatter 包含身份字段和 `indications` 数组。
- 正文按数组使用 `## [{indication_id}] {indication}` 标题分别建立分节；对象可携带 trial 级 phase/regimen/cutoff 并按 summary-spec 继承，数据组别不得串列。
- H1 后必须写精确 canonical link：`> 来源原文: [{source_label}](../raw/{drug_id}@{source_label}.md)`。
- URL 图保持远程链接。已有 raw 若对应 PDF 且缺少关键图，可使用可用 harness/PDF 工具将裁剪图（优先）或完整页面保存到 `{research_dir}/attachments/`，并从 summary 以 `../../../attachments/{file}` 引用。
- PDF 渲染/截图不可用时继续生成文本 summary，在结果中明确报告图片缺失原因；不得伪造附件。
- 不覆盖文件、不追加序号、不写旧式 wikilink。生成失败时不得保存空或半成品 summary。
- 提取阶段固定写 `verification: pending`、`verification_fail_count: null`、`verification_coverage: null`，不得预先写 `passed` 或自行审核。

可按来源并行，但每个 worker 必须收到该 raw 的完整 identity/path context，且写入目标互不重叠。

## Step 4: 独立验证与索引

每个新 summary 由不同于生成者的独立 data-verify agent 审核。verifier 根据 summary 的相对 Markdown 来源链接解析 raw，校验该链接仍位于当前 `raw_dir`，并覆盖 `indications` 数组中的所有正文分节。verifier 不联网、不修改正文。

有 FAIL 时按问题修正 summary 后交给新的独立 verifier 重验；仍失败则不索引。WARN 保留并报告。

仅将通过项以部分模式派发给 clinical-indexer：每个 summary 对 drug page 只归档一次，并按 `indications` 数组分别派发到所有适应症索引；所有条目引用同一个 summary。索引器不能处理多适应症时报告不兼容，不得拆 summary 或退回 v1 格式。

## Step 5: 报告

```text
批量处理完成：
- 扫描根目录: {research_dir}
- 待处理: N
- 成功 / 失败 / 跳过: X / Y / Z
- raw -> summary: {逐项路径}
- indications: {逐 summary 数组}
- verification: {PASS/WARN/FAIL 汇总}
- attachments/warnings: {PDF 图片与不可用原因}
- indexing: {drug 与逐适应症结果}
```

单项文件异常、摘要生成失败或验证失败不阻塞其他独立项；任何情况下都不得修改 raw 正文或无关文件。
