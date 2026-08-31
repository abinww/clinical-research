---
name: data-verify
description: |
  独立审核一个或多个 clinical-research 2.0 summary，确认其中所有适应症的
  临床数据均可追溯到 canonical source link 指向的 raw。
---

# 数据一致性审核 - 2.0

> verifier 必须独立于提取/摘要生成 agent。本 skill 不联网、不评价临床价值，只修改审核章节和 verification 字段。

## 安全与独立性约束

- 输入由调用方明确给出；不自行扫描全库。
- 每个 summary 独立执行定位、核对和写入。批量输入不能共享结论或证据。
- 只允许修改 YAML 的 `verification`、`verification_fail_count`、`verification_coverage` 和文件末尾 `## 数据一致性审核` 章节。
- 不得修改身份字段、`indications` 数组、临床正文、图片、试验设计或专家点评。
- 不联网、不补充数据、不用常识或外部知识弥补 raw 证据。
- 不审核专家点评的观点；审核正文中的临床数值、试验事实、分组和图片所声称的数据。
- 不支持 v1 wikilink或旧目录解析。无法满足 2.0 canonical link 时直接拒绝该项。

## Step 1: 安全解析来源

读取 summary 并只接受一行 canonical source link：

```markdown
> 来源原文: [label](../raw/{drug_id}@{source_label}.md)
```

解析规则：

1. 将 URL 编码后的文件名安全解码，以 summary 所在目录为基准解析相对路径。
2. 拒绝绝对路径、wikilink、反斜杠、嵌套 raw 子目录、`..` 越界和一个文件内多个来源行。
3. 若调用方提供 `raw_dir`，解析结果必须是其直接子文件；否则从 2.0 路径 `{research_dir}/{company_id}/{drug_id}/summary/` 推导相邻 `raw/` 并做同样校验。
4. raw 与 summary 文件名必须完全相同，且匹配 `{drug_id}@{source_label}.md`；summary frontmatter 的 `drug_id`、`source_label` 必须与文件名一致。
5. 解析后的 raw 必须存在且可读。任何校验失败都不尝试搜索同名文件或旧目录，只报告无法安全定位来源。

## Step 2: 读取规范与范围

读取 `../schema/summary-spec.md` 的数据一致性规则。读取 frontmatter `indications` 数组，并确认正文对每个数组项存在对应分节。数组缺失、为空、重复，或正文适应症与数组不一致，均记为 `FAIL`。

逐适应症审核以下内容，包括但不限于：

- 样本量和分析集：`N`、`n`、ITT、可评估人群。
- 疗效：ORR、cORR、DCR、CR、PR、SD、PFS、OS、DoR 及时间点。
- 统计量：HR、p-value、CI。
- 安全性：AE、TEAE、TRAE、SAE、等级、减量、停药和死亡。
- 试验事实：phase、trial、cohort、剂量、治疗组、对照组、适应症、治疗线、联合方案和发布日期。
- 临床图片中被正文或图注作为数据事实陈述的内容；只以 raw 文本和可读取的实际附件为证据，不因图片存在就自动通过。

## Step 3: 逐项核对

- `PASS`：raw 中有直接证据或明确等价表达，且适应症、组别、剂量、分析集、单位和时间点一致。
- `WARN`：raw 有近似依据，但术语、上下文、单位或时间点需要人工确认。
- `FAIL`：无依据，或适应症/组别/剂量/单位/时间点对应错误。

每个临床数值和关键试验事实必须有审核行。多适应症来源必须在审核表中标明适应症，避免同一数值被错误复用于另一分节。`AE`、`TEAE`、`TRAE`、`SAE` 不得混用；单位不得擅自换算；“未披露”不应被审核成确定值。

URL 远程图片无需下载；若 summary 仅依赖远程图片而 raw 没有相应文本证据，标记 `WARN` 或 `FAIL`，不得联网取证。PDF 附件缺失或渲染工具不可用不自动导致全文失败，但任何仅存在于缺失图片中的数值不能判为 `PASS`。

## Step 4: 写入审核结果

只覆盖文件末尾的审核章节，表格增加适应症列：

```markdown
## 数据一致性审核

| indication_id | 数据项 | summary中的值 | raw证据 | 状态 | 问题 |
|---------------|--------|---------------|---------|------|------|
| NSCLC_1L | ORR | 42.3% | "...ORR was 42.3%..." | PASS | - |
| SCLC_1L | mPFS | 11.3 | 未找到 | FAIL | raw 中未出现该数值 |
```

审核覆盖完整且无 FAIL（允许 WARN）：

```yaml
verification: passed
verification_fail_count: 0
verification_coverage: complete
```

存在 FAIL 或审核无法覆盖完整：

```yaml
verification: failed
verification_fail_count: {FAIL 数量}
verification_coverage: incomplete
```

来源无法安全定位时不得伪造审核表或写 `passed`；返回定位失败。若文件已有审核章节，只替换最后的规范审核章节，正文中的同名文本或引用不得误删。

## Step 5: 返回

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

FAIL 的正文修正只能由调用方完成，再交给新的独立 verifier 审核；本 skill 不自行修正后自证通过。
