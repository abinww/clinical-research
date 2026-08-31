---
name: data-verify
description: |
  独立审核一个或多个 clinical-research 2.0 summary，确认其中所有适应症的
  临床数据均可追溯到 canonical source link 指向的 raw。
---

# 临床数据一致性审核

## 职责与边界

本 skill 独立核对 summary 与其唯一 raw。verifier 必须独立于提取或摘要生成 agent；不联网、不评价临床价值、不补充或修正正文，只写审核状态和末尾审核章节。

## 输入与共享契约

- 调用方明确提供一个或多个 summary 路径；不自行扫描全库。批量输入逐文件独立定位、取证和写入，不共享结论或证据。
- 来源链接、文件命名、`indications` 和审核格式以 `../schema/summary-spec.md` 为权威。
- 可选上下文包括绝对 `research_dir` 和 `raw_dir`；路径身份须符合 `../drug-identity/SKILL.md` 的布局契约。
- 本 skill 不支持 v1 wikilink 或旧目录解析。

## 不变量与写边界

- 只允许修改 YAML 的 `verification`、`verification_fail_count`、`verification_coverage`，以及文件末尾的规范 `## 数据一致性审核` 章节。
- 不得修改身份字段、`indications`、临床正文、图片、试验设计或专家点评；不审核专家点评观点。
- 只以 raw 文本和可读取的实际附件为证据，不用常识、外部知识或联网内容补证。
- 每个临床数值、关键试验事实和分组都必须有审核行，并覆盖全部适应症。

## 工作流

1. **安全定位来源。** 只接受全文件唯一的规范相对 Markdown 来源链接。对 URL 编码文件名安全解码，以 summary 目录为基准解析；拒绝绝对路径、wikilink、反斜杠、嵌套 raw 子目录、`..` 越界和多个来源行。
2. **校验配对。** 若提供 `raw_dir`，结果必须是其直接子文件；否则从 `{research_dir}/{company_id}/{drug_id}/summary/` 推导相邻 `raw/`。raw 与 summary 文件名必须完全相同并匹配规范命名；summary frontmatter 的 `drug_id`、`source_label` 必须与文件名一致，raw frontmatter 只校验 summary-spec 定义的来源字段。raw 必须存在且可读；失败时不搜索同名文件或旧目录。
3. **确定范围。** 读取 summary-spec 的数据一致性规则和 `indications`。数组缺失、为空、重复，或与正文分节不一一对应时记 `FAIL`。逐适应症覆盖样本量/分析集、疗效、安全性、统计量、试验阶段与设计、cohort、剂量、组别、治疗线、联合方案、日期，以及正文或图注声称的数据事实。
4. **逐项核对。** 按以下精确定义记录每一项，并在多适应症来源中明确 `indication_id`：

| 状态 | 判定 |
|---|---|
| `PASS` | raw 有直接证据或明确等价表达，且适应症、组别、剂量、分析集、单位和时间点一致 |
| `WARN` | raw 有近似依据，但术语、上下文、单位或时间点需人工确认 |
| `FAIL` | 无依据，或适应症、组别、剂量、单位、时间点对应错误 |

`AE`、`TEAE`、`TRAE`、`SAE` 不得混用，单位不得擅自换算，“未披露”不得审核为确定值。远程图片无需下载；若事实仅依赖远程图片而 raw 无文本证据，记 `WARN` 或 `FAIL`。PDF 附件缺失不自动使全文失败，但仅存在于缺失图片中的数值不能判 `PASS`。

5. **写入结果。** 只替换文件末尾最后一个规范审核章节，不误删正文中的同名文本或引用。表格结构遵守 summary-spec，并包含适应症列。覆盖完整且无 `FAIL` 时写 `passed/0/complete`；存在 `FAIL` 或覆盖不完整时写 `failed/{实际 FAIL 数}/incomplete`。
6. **复核写入。** 确认审核表覆盖全部数值、事实和 indication IDs，FAIL 数与 frontmatter 一致，审核章节仍为文件末尾。

## 失败与恢复

- 来源无法安全定位时不得伪造审核表或写 `passed`；返回 `unresolved`，不搜索替代 raw。
- 审核不完整必须标记失败，不得因无已识别 FAIL 而通过。
- `FAIL` 的正文只能由调用方修正，再交给新的独立 verifier；本 skill 不自行修正后自证通过。

## 输出

```text
data-verify: {summary路径}
- source: {解析后的 raw 路径或 unresolved}
- indications checked: {数量/列表}
- verification: passed / failed / unresolved
- verification_coverage: complete / incomplete / unresolved
- PASS / WARN / FAIL: x / y / z
- coverage complete: yes / no
- warnings: {需人工复核项}
```
