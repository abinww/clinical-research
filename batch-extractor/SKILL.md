---
name: batch-extractor
description: |
  扫描 clinical-research 2.0 布局中尚无 summary 引用的 raw，
  按药物身份与路径上下文批量生成、独立验证并索引摘要。
---

# 临床数据批量处理

## 职责与边界

本 skill 扫描现有 raw，批量生成 summary、独立验证并索引。不得重新抓取来源、改写 raw，或使用 v1 目录和命名兼容逻辑。

## 输入与共享契约

- `{clinical_research_dir}` 是包含顶层 `SKILL.md` 的目录。`config.yaml` 只提供绝对 `research_dir`。
- 身份对象和路径以 `../drug-identity/SKILL.md` 为权威；summary 格式以 `../schema/summary-spec.md` 为权威；索引资格以 `../clinical-indexer/SKILL.md` 的完整门禁为准。
- 读取上述契约、`data-verify/SKILL.md` 和相关 schema 后再处理。
- 输入模式二选一：`scan`（默认，可带 `company_id`、`drug_id` 过滤器）或 `single_raw`（调用方提供一个 raw 绝对路径，只处理该文件）。

## 不变量与写边界

- 一个 raw 只创建一个同名 summary，不因多适应症拆分。
- summary 严格 create-only，不覆盖、不追加序号、不写旧式 wikilink；生成阶段审核状态固定为 `pending/null/null`。
- verifier 必须独立于生成者，不联网、不修改正文。
- 每个 summary 对药品页只索引一次，并将同一来源派发到全部合格适应症页。

## 工作流

1. **确定待处理 raw。** `single_raw` 模式直接校验并使用调用方给出的唯一绝对路径，不执行目录扫描。`scan` 模式使用跨平台脚本，不得使用 `grep`、`find`、`sed` 或 Bash 管道：

```text
python {clinical_research_dir}/scripts/find_unprocessed.py --config "{config_path}" --quiet
python {clinical_research_dir}/scripts/find_unprocessed.py --config "{config_path}" --company-id "{company_id}" --drug-id "{drug_id}" --quiet
```

第二条仅在提供过滤器时使用。无输出表示没有待处理 raw，直接报告并结束。两种模式进入后续步骤前都必须得到明确 raw 路径列表；`single_raw` 列表长度必须为 1。

2. **建立上下文。** 脚本返回 `{company_id}/{drug_id}/raw/{drug_id}@{source_label}.md`。使用 `pathlib`/harness 解析路径组件，并派生同一药品树中的 `drug_dir`、`drug_page`、`raw_dir`、`summary_dir`、同名 `summary_file` 和根 `attachments_dir`。
3. **校验身份。** 写入前读取根 `index.md`，用 `drug_id`、别名和完整 vault 路径联合确认恰好一个条目映射到 `{company_id}/{drug_id}/{drug_id}.md`。读取药品页构造标准身份对象，必要时调用 drug-identity `resolve_only` 校验；不得从 raw 猜测身份。`companies` 如存在必须与 `company_ids` 相同。
4. **生成 summary。** 读取 raw，按 summary-spec 创建唯一 `summary_file`。只纳入 raw 支持的全部适应症和试验事实，保持分组、继承关系与 canonical 相对来源链接准确，不得串组或推断。
5. **处理 PDF 图片。** URL 图保持远程链接。已有 raw 对应 PDF 且缺少关键图时，可用 harness/PDF 工具优先裁剪、否则保存整页到 `{research_dir}/attachments/`，并从 summary 以 `../../../attachments/{file}` 引用。工具不可用时继续文本 summary，报告原因，不伪造附件。
6. **独立验证。** 每个新 summary 交给不同于生成者的 data-verify agent。verifier 从相对链接解析 raw，确认其为当前 `raw_dir` 的直接文件，并覆盖全部适应症分节。有 `FAIL` 时按问题修正文后交给新的独立 verifier；仍失败则不索引。保留并报告 `WARN`。
7. **派发索引。** 仅将通过 clinical-indexer 完整资格门禁的 summary 以部分模式派发。每份 summary 对 drug page 归档一次，再按全部 `indications` 更新适应症页。索引器不支持多适应症时报告不兼容，不拆 summary、不退回 v1。

可按来源并行生成，但每个 worker 必须获得该 raw 的完整 identity/path context，且写入目标互不重叠。

## 失败与恢复

- 根索引零匹配、多匹配、同一 `drug_id` 映射多路径、路径映射另一药物，或路径、文件名、标识符/标签、药品页不合规时，该项失败且不写 summary。
- 同名 summary 已存在时跳过。生成失败不得留下空或半成品 summary；任何情况下不得修改 raw 正文或无关文件。
- 单项文件异常、生成失败、验证失败或索引失败不阻断其他独立项，但必须逐项报告。

## 输出

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
