---
name: multi-extractor
description: |
  临床数据提取编排入口。接收一个或多个 URL/PDF，解析 2.0 身份与路径，
  按来源提取、独立验证，并按 summary 的多适应症内容派发索引。
---

# 临床数据提取 - 编排层

> 单来源提取由 `clinical-extractor` 完成。验证必须由独立 verifier agent 完成；提取 agent 和主编排 agent 均不得代替 verifier 判定通过。

## 2.0 不变量

- `config.yaml` 只提供 `research_dir`。
- 身份解析提供 `company_id`、`drug_id`、`aliases` 等身份字段，以及解析后的 `drug_dir`、`drug_page`、`raw_dir`、`summary_dir`。
- 目录固定为 `{research_dir}/{company_id}/{drug_id}/`，其中包含 `{drug_id}.md`、`raw/`、`summary/`；根附件目录为 `{research_dir}/attachments/`。
- 每个来源恰好对应一个 `{drug_id}@{source_label}.md` raw 和一个同名 summary。
- clinical-extractor 永远不得覆盖或删除；只有本编排层可在用户明确授权后执行下述准确替换流程。
- 单个 summary 可包含多个适应症，使用 `indications` 数组和正文分节表达；不得拆文件。
- 不接受或生成 v1 子目录、`drug@indication@source` 文件名或 raw wikilink。
- 所有脚本调用使用 `python`/`pathlib` 兼容方式；不得假设 `grep`、`find`、`sed` 或 Bash 存在。

## Step 1: 预检与身份

读取配置、`drug-identity/SKILL.md`、`clinical-extractor/SKILL.md`、`data-verify/SKILL.md`、`clinical-indexer/SKILL.md` 以及相关 schema。配置缺少 `research_dir` 或规范不可读时停止。

若调用方已提供完整 2.0 身份与路径上下文，校验后直接使用。否则调用 drug-identity 解析。最终上下文必须至少为：

```text
research_dir
company_id
drug_id
aliases
target / companies / molecule_type
drug_dir
drug_page
raw_dir
summary_dir
attachments_dir = {research_dir}/attachments
```

校验所有解析路径都位于 `research_dir` 内并符合 `company_id/drug_id` 布局，且 `drug_page == drug_dir/{drug_id}.md`。身份不明确或路径不一致时停止，不自行猜测。

## Step 2: 来源预检与去重

从输入提取 URL/PDF 列表；没有来源时要求补充。先计算 canonical source：URL 保持用户准确提供的字符串，或工作流明确采用的准确 canonical final URL，不得 percent decode 或改写查询参数、尾部斜杠、大小写及编码形式；本地 PDF 在 Windows 上使用 `Path.resolve().as_posix()` 得到 resolved absolute POSIX path。先按该值在本批内做准确去重，再扫描全库已有来源：

```text
python {clinical_research_dir}/scripts/scan_sources.py --config "{config_path}" --format urls
```

必须使用 `--config ... --format urls`，不得改为扫描某个旧 `raw_dir`。将结果与 raw frontmatter 持久化的 canonical `source` 做准确字符串比较，所有工作流必须使用同一个值。URL 不做 percent decoding 或额外归一化；PDF 只以 resolved absolute POSIX path 作准确身份，文件名及已知来源标识仅用于提示近似重复。同标题同日期、不同 PDF 路径或官方镜像与原文等近似重复需人工语义判断。

- 多来源模式：重复项静默跳过并记录已有匹配。
- 单来源模式：报告准确匹配的 canonical source、旧 raw/summary 路径和索引引用，并询问是否跳过或替换。没有用户对该准确来源的明确授权时绝不覆盖或删除。
- 获得明确授权后，必须先唯一确定同名的准确旧 raw/summary 对及其 research-root-relative POSIX 来源身份，枚举药品页、该 summary 涉及的全部适应症页和根索引中的所有准确身份引用。若旧配对不完整、存在多个候选或引用无法完整枚举，停止且不做任何删除。
- 确认替换集合后，只删除这一个准确旧 raw/summary 对和所有枚举出的准确索引引用，不删除附件、其他来源、近似文本或其他索引内容。清理后重新检查该配对和所有准确引用均不存在；有残留则停止，不调用 extractor。
- 仅在上述清理完整完成后，才以相同 canonical source 和目标 `source_label` 调用 clinical-extractor，将其视为不存在的全新目标。不得要求 extractor 覆盖、删除或清理。替换后续提取失败时如实报告，不恢复或改动其他来源。

对 URL 做轻量可达性检查，失败时尝试官方同文镜像；若明确改用镜像或重定向后的 canonical final URL，后续持久化和比较必须统一使用选定的准确 URL。PDF 不在预检中重复提取。为每个待处理来源分配一个 Windows 安全、在该药物下唯一且稳定的 `source_label`。目标文件名固定为 `{drug_id}@{source_label}.md`；存在冲突时使用描述 trial、abstract、analysis 等差异的最短语义稳定后缀，例如 `_TrialABC`、`_Abstract1234`、`_FinalAnalysis`，不得追加 `_2`、`_3` 等不透明序号。

## Step 3: 按来源提取

每个来源派发一个隔离的 clinical-extractor agent，每轮最多 5 个。prompt 注入完整身份和路径上下文：

```text
读取 clinical-extractor/SKILL.md，处理这一个来源：{URL 或 PDF}
配置与身份路径：
- config_path: {config_path}
- research_dir: {research_dir}
- company_id: {company_id}
- drug_id: {drug_id}
- aliases: {aliases}
- target / companies / molecule_type: {值}
- drug_dir: {drug_dir}
- drug_page: {drug_page}
- raw_dir: {raw_dir}
- summary_dir: {summary_dir}
- attachments_dir: {research_dir}/attachments
- source_label: {source_label}
- canonical source: {准确 URL 或 PDF resolved absolute POSIX path}
要求：一个来源只生成一对同名 raw/summary；一个 summary 用 indications 数组和正文分节容纳所有适应症。
```

成功后用 harness 文件工具核对两个返回路径存在、同名、summary canonical link 指向该 raw，并确认每个来源只返回一个 summary。失败项携带原因重试一次；仍失败则记录，不影响其他来源。PDF 图片工具不可用属于警告而不是伪造图片或重复整个文本提取的理由。

## Step 4: 独立验证

只使用本轮成功生成的 summary 路径，不扫描全目录。每个 summary 派发一个独立 data-verify agent，每轮最多 5 个：

```text
按 data-verify/SKILL.md 独立审核：{summary_path}
路径上下文：research_dir={research_dir}, raw_dir={raw_dir}, summary_dir={summary_dir}
从 canonical 来源链接按 summary 所在目录解析 raw；覆盖 indications 数组中所有适应症分节。
```

- verifier 与提取 agent 必须不同；不得把提取结论当作证据。
- verifier 不联网、不修改正文，只写审核章节和 verification 字段。
- `FAIL` 由主编排根据 verifier 指出的证据问题修正正文，再派发新的独立 verifier 复核该 summary。连续两轮仍失败则停止该项并报告。
- `WARN` 可继续，但必须列入最终人工复核项。

## Step 5: 多适应症索引派发

只将同时满足 `verification: passed`、`verification_fail_count: 0`、末尾审核章节存在且审核章节中没有任何 `FAIL` 的本轮 summary 派发给 clinical-indexer。任一条件不满足均记录为索引不合格，不得派发。索引以 summary 为工作单元，但必须展开其 `indications` 数组：

```text
读取 clinical-indexer/SKILL.md，以部分模式归档：
- summary: {summary_path}
- drug_page: {drug_page}
- identity/path context: {完整 2.0 上下文}
- indication dispatch: 读取 indications 数组及对应正文分节；同一 summary 更新一次 drug_page，并分别更新每个适应症索引页面；所有索引项引用同一个 summary 路径。
```

不得按适应症复制 summary 或多次重复写入 drug 页面。索引器若只支持单个 `indication_id`，视为不兼容 2.0：停止该 summary 的索引并报告，不得退回旧命名/布局。索引失败不回滚已验证的 raw/summary。

## Step 6: 报告

```text
- 输入来源 / 跳过重复 / 成功 / 失败数量
- canonical source 列表；URL 保留值及 PDF resolved absolute POSIX path
- 明确授权替换、已删除的准确 raw/summary 对、已清除的准确索引引用及替换结果
- 每个来源唯一的 raw 与 summary 路径
- 每个 summary 的 indications 数组
- PDF 附件及未能渲染的重要图片警告
- PASS/WARN/FAIL 汇总与人工复核项
- 索引合格/不合格数量及不合格条件（verification、fail_count、审核章节、审核 FAIL）
- drug 索引和逐适应症索引结果
- 失败项及原因
```
