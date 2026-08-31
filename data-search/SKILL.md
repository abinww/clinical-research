---
name: data-search
description: |
  搜索已公布的临床数据来源。当用户提到以下关键词时触发：
  - "搜索已公布的临床数据"
  - "查找临床数据来源"
  - 药品名称 + "建库"流程中由编排调用
---

# 临床数据来源搜索 2.0

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 职责：搜索某创新药已公布的临床数据原始来源，输出候选 URL plan；不提取数据。

## 约束与固定规则

- 搜索已公布的临床疗效/安全性数据来源：期刊、会议、公司公告及其他原始披露。
- 先获得别名全集，再搜索；身份无法确认时停止询问，不猜测。
- `data-search` 全程只读：不调用 `multi-extractor`，不创建、修改或删除研究文件，不写 `raw/`、`summary/`、药品页、`indication/` 或 `.temp/plans/`。
- 不读取或兼容 v1 路径，不创建全局 `raw/`、`summary/`、`drug/` 或 `trials/`。
- ClinicalTrials.gov（CTG）注册页只提供搜索索引骨架，不进入 plan；注册试验由 `drug-trials-search` 单独处理。
- 媒体、百科和聚合页只作线索，不进入 plan，不直接采用其中数字。每个数字都应可追溯到原始来源。
- 内容质量优先于来源等级；无法获取的期刊不优于可获取且数据更完整的会议摘要或公司公告。
- 同一试验的不同数据截止日都保留；无 NCT 的合格来源也纳入，编号填 `—`。
- 一个来源 URL 只占 plan 一行，对应一个 raw/summary 来源对；多个适应症或试验代码合并在该行。
- 不评价临床数据质量。

所有文件和目录操作必须兼容 Windows。脚本使用 Python 3.10+ 标准库与 `pathlib`；不得依赖 shell 的 `grep`、`find`、`sed` 或其他 Unix 文件搜索命令。

## Step 1: 配置与身份

1. 读取 `{clinical_research_dir}/config.yaml`。配置只能提供一个绝对路径 `research_dir`；缺失、无效或不可读时停止，按顶层 skill 的初始化流程处理，不从旧字段或目录推断。
2. 配置解析后立即首先读取 `{research_dir}/index.md`。根索引不可读时停止，不得先扫描目录或搜索 web。
3. 读取 `../drug-identity/SKILL.md`，仅以 **identity mode `resolve_only`** 调用。先用根索引解析输入，未命中才搜索可靠来源确认；即使是新药，也只返回拟议身份和路径，不得创建目录、药品页或索引条目。
4. 获取并原样传递完整身份与路径：

```text
research_dir: {配置解析后的绝对路径}
company_id: {规范归档公司 ID}
drug_id: {按固定优先级确定}
drug_aliases: {研发代号/合作方代号/商品名等全集}
target: {最简形式}
archive_company: {规范归档公司 ID}
company_ids: {研发公司及合作方的规范 company_id 列表}
molecule_type: {ADC/双抗/单抗/小分子}
drug_dir: {research_dir}/{company_id}/{drug_id}
drug_page: {drug_dir}/{drug_id}.md
raw_dir: {drug_dir}/raw
summary_dir: {drug_dir}/summary
attachments_dir: {research_dir}/attachments
```

drug 展示名从 `drug_aliases` 中选择通用名。校验所有目录位于 `research_dir` 内并符合 2.0 布局；不得重选身份或路径。无法唯一确认药物或归档公司时，停止并请用户确认。

## Step 2: 建立试验索引

复用 `drug-trials-search` 脚本查询 CTG，将 `drug_id` 和全部已确认、去重后的 `drug_aliases` 分别作为 `--drug` 参数：

```text
python {skill_dir}/../drug-trials-search/search_trials.py --drug "{drug_id}" --drug "{alias1}" [--drug "{alias2}"] --format json
```

从 JSON 提取 NCT 编号、试验代号、阶段、适应症和状态，作为后续搜索索引。CTG 注册页不进入 plan。`chinadrugtrials.org.cn` 当前未实现，跳过并记录 `CDT 未查询`。

## Step 3: 搜索原始来源

按以下来源搜索，并对每个候选 URL 用 `web_fetch` 快速确认是否含临床数据：

| 来源 | 搜索方式 |
|---|---|
| 公司官方渠道 | 官网 IR 管线页、新闻中心、业绩报告、PPT、港交所披露易、巨潮；同时搜索合作方公告；关键词 `{公司名} {drug} phase OR results press release` |
| 学术会议 | 逐个搜索 ASCO、ESMO、ESMO Asia、WCLC、SABCS、ASH、AACR、CSCO；关键词 `{代号} {会议名}`，不带年份；优先摘要库原文：ASCO/JCO `ascopubs.org`，ESMO `oncologypro.esmo.org`/`annalsofoncology.org`，WCLC `iaslc.org`，ASH `ashpublications.org`，AACR `aacrjournals.org`；记录摘要号和数据截止日 |
| 期刊 | PubMed 搜索 `{drug}` 或 `{drug} {indication}`；定向搜索 `{drug} site:nejm.org OR site:thelancet.com OR site:jco.org OR site:nature.com` |
| 行业媒体线索 | 医药魔方、Insight、药融云、Endpoints、Fierce Biotech；仅发现线索，随后回到公司、会议或期刊原始来源 |

## Step 4: 排除当前药品已提取来源

只读扫描 **当前药品的 `raw_dir`** 中 YAML frontmatter 的 `source:`。保留 raw 中的准确 URL 字符串；本地 PDF 身份使用 `Path.resolve(strict=True).as_posix()` 得到的 resolved absolute POSIX path。不得扫描整个研究库，也不得传入或推断旧全局 `raw_dir`。

```text
python "{clinical_research_dir}/scripts/scan_sources.py" --raw-dir "{raw_dir}" --format urls --strict
```

`raw_dir` 是 `resolve_only` 返回的当前药品拟议或既有目录；目录不存在时集合为空。strict 扫描发现损坏 frontmatter、路径逃逸或配对异常时停止并报告，不得使用部分结果。

以 `(company_id, drug_id, source)` 为准确重复键。当前药品树中 canonical `source` 准确匹配的候选应剔除；其他药品树中的相同来源允许跨药复用，不得阻塞。所有流程比较 raw 中同一个 canonical 值，不得用 percent-decoded URL、PDF 文件名、相对路径或反斜杠路径替代。

## Step 5: 筛选与去重

1. 先做轻量可达性预检（HEAD 或 basic fetch）。403、404 或连接失败时寻找同文镜像；仍不可达则排除。
2. 用 `web_fetch` 确认内容包含 ORR、PFS、OS、AE 等临床疗效或安全性数据。
3. 排除二手转述、百科、聚合页、纯新闻、CTG/注册页，以及付费墙无摘要、反爬或空页面等无法获取内容的来源。
4. 同一 NCT 或试验代码默认按“期刊全文 > 会议摘要 > 公司公告 > 新闻稿”选择，但以实际可获取内容为准：付费墙期刊可降级为会议摘要；公司公告数据更完整时可保留公司公告；覆盖相当时选更可靠来源。相同截止日只保留一个最优来源，不同截止日均保留。
5. 无 NCT 或试验代号但确含临床数据的来源纳入 plan，编号填 `—`。
6. 最后按将持久化的准确 supplied/canonical-final URL 字符串去重，不做 percent decoding；仅语义等价但字符串不同的 URL 交人工判断。同一 URL 涉及多个适应症或试验时合并单元格，可用 `<br>` 或 `；` 分隔。

## Step 6: Plan 合同

```markdown
# {drug_id} 临床数据来源 plan

> 生成时间: {YYYY-MM-DD}
> 药品身份: {drug_id} | {drug} | target: {target} | 归档公司: {archive_company} | 公司 IDs: {company_ids}
> 别名全集: {别名列表}
> 搜索范围: {使用的搜索词}

| # | 临床代码或NCT编号 | 适应症 | 临床阶段 | 来源类型 | 数据截止日 | 网址链接 | 备注 |
|---|------------------|--------|---------|---------|-----------|---------|------|
| 1 | NCT04521625 | NSCLC 1L；NSCLC 2L+ | Phase III | journal | 2025-06-01 | https://... | 同一来源覆盖多个适应症；NEJM 全文 |
| 2 | EXAMPLE-101 | NSCLC 后线 | Phase II | conference | 2024-12-01 | https://... | ASCO2025 摘要 |
| 3 | — | 实体瘤 | Phase I | company_release | — | https://... | 首次人体数据 |
```

| 列 | 规则 |
|---|---|
| # | 序号 |
| 临床代码或NCT编号 | NCT 编号或公司试验代号；无则 `—`；多个代码合并在同一格 |
| 适应症 | 精确适应症，含治疗线；同一来源的多个适应症不拆行 |
| 临床阶段 | Phase I / II / III / IV |
| 来源类型 | `journal`、`conference`、`company_release`、`regulatory`、`other` |
| 数据截止日 | cutoff；来源未给出则 `—` |
| 网址链接 | 原始来源 URL |
| 备注 | 如“NEJM 全文”“ASCO2025 摘要”“首次人体数据” |

## Step 7: 返回结果

- **独立调用**：直接向用户返回 plan 表，不保存文件。
- **被编排调用**：直接向调用方返回同一 plan 表，不自行持久化；只有 `drug-build` 可按其 workflow 保存到根 `{research_dir}/.temp/plans/`。

```text
data-search 完成：
- 药品: {drug_id} ({drug})
- 别名全集: {列表}
- 搜索候选: N 个
- 含临床数据: M 个
- 去重后保留: K 个
- plan 表: （独立调用返回用户；编排调用返回调用方）
- 下一步: 独立调用由用户决定是否提取；编排调用直接交还调用方继续其 workflow
```
