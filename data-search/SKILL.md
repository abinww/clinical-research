---
name: data-search
description: |
  搜索已公布的临床数据来源。当用户提到以下关键词时触发：
  - "搜索已公布的临床数据"
  - "查找临床数据来源"
  - 药品名称 + "建库"流程中由编排调用
  建库编排时先返回临床候选清单，由编排选择或自动全选，再为选中试验查找最佳来源。
---

# 临床数据来源搜索 2.0

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 职责：搜索某创新药已公布的临床数据；建库时先输出候选临床清单，用户选定后输出最佳来源 plan；不提取数据。

## 约束与固定规则

- 搜索已公布的临床疗效/安全性数据来源：期刊、会议、公司公告及其他原始披露。
- 先获得别名全集，再搜索；身份无法确认时停止询问，不猜测。
- `data-search` 全程只读：不调用 `multi-extractor`，不创建、修改或删除研究文件，不写 `raw/`、`summary/`、药品页、`indication/` 或 `.temp/plans/`。
- 不读取或兼容 v1 路径，不创建全局 `raw/`、`summary/`、`drug/` 或 `trials/`。
- ClinicalTrials.gov（CTG）注册页只提供搜索索引骨架，不进入 plan；注册试验由 `drug-trials-search` 单独处理。
- 媒体、百科和聚合页只作线索，不进入 plan，不直接采用其中数字。每个数字都应可追溯到原始来源。
- 内容质量优先于来源等级；无法获取的期刊不优于可获取且数据更完整的会议摘要或公司公告。
- 同一试验的不同数据截止日都参与比较，但最终每个试验只选一个数据最完整的来源；无 NCT 的合格来源也纳入，编号填 `—`。
- 一个来源 URL 只占 plan 一行，对应一个 raw/summary 来源对；多个适应症或试验代码合并在该行。
- 建库流程由 `drug-build` 先取得候选清单并确定纳入范围（少量候选可自动全选）；本 skill 不自行替用户选择要纳入的临床试验。
- 不评价临床数据质量。

## 调用模式

| 模式 | 调用方 | 输入 | 输出 |
|---|---|---|---|
| `discover` | `drug-build` 建库前 | 药品身份 | 只含试验、适应症/线、阶段和最近公开年月的候选清单；不含 URL |
| `resolve` | `drug-build` 用户选定后 | 选中的试验 ID 清单 | 只为选中试验选择最佳来源，返回对应 plan 行 |
| `full` | 独立调用 | 药品身份 | 先发现全部候选，再为全部试验选最佳来源，返回完整 plan |

`discover` 不比较全文，不判断最佳链接。`resolve` 必须使用调用方给出的选中试验范围；不得自行扩展、缩减或替换试验。`drug-build` 必须显式传入 `discover` 或 `resolve`，不得以 `full` 绕过选择流程。

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
company_dir: {research_dir}/{company_id}
drug_page: {company_dir}/{drug_id}.md
raw_dir: {company_dir}/raw
summary_dir: {company_dir}/summary
attachments_dir: {research_dir}/attachments
```

drug 展示名从 `drug_aliases` 中选择通用名。校验所有目录位于 `research_dir` 内并符合 2.0 布局；不得重选身份或路径。无法唯一确认药物或归档公司时，停止并请用户确认。

独立调用默认使用 `full`。被 `drug-build` 或任何编排调用时必须显式提供 `discover` 或 `resolve`；`resolve` 还必须附上选中的试验 ID 清单。编排模式缺失或选中清单为空时停止，不得猜测或退回 `full`。

## Step 2: 建立试验索引

复用 `drug-trials-search` 脚本查询 CTG，将 `drug_id` 和全部已确认、去重后的 `drug_aliases` 分别作为 `--drug` 参数：

```text
python {skill_dir}/../drug-trials-search/search_trials.py --drug "{drug_id}" --drug "{alias1}" [--drug "{alias2}"] --format json
```

从 JSON 提取 NCT 编号、试验代号、阶段、适应症和状态，作为后续搜索索引。CTG 注册页不进入 plan。`chinadrugtrials.org.cn` 当前未实现，跳过并记录 `CDT 未查询`。

## Step 3: 搜索原始来源

按以下来源搜索。`discover` 只做足以判断存在哪些临床试验的轻量检索；`resolve`/`full` 才逐个打开候选并核对临床内容。

| 来源 | 搜索方式 |
|---|---|
| 公司官方渠道 | 官网 IR 管线页、新闻中心、网页版业绩/新闻稿、合作方公告；优先网页链接，**上市公司公告类 PDF（港交所披露易、巨潮等披露的公告 PDF）不作为来源**，有对应网页版时收录网页链接；关键词 `{公司名} {drug} phase OR results press release` |
| 学术会议 | 逐个搜索 ASCO、ESMO、ESMO Asia、WCLC、SABCS、ASH、AACR、CSCO；关键词 `{代号} {会议名}`，不带年份；优先摘要库原文：ASCO/JCO `ascopubs.org`，ESMO `oncologypro.esmo.org`/`annalsofoncology.org`，WCLC `iaslc.org`，ASH `ashpublications.org`，AACR `aacrjournals.org`；记录摘要号和数据截止日 |
| 期刊 | PubMed 搜索 `{drug}` 或 `{drug} {indication}`；定向搜索 `{drug} site:nejm.org OR site:thelancet.com OR site:jco.org OR site:nature.com` |
| 行业媒体线索 | 医药魔方、Insight、药融云、Endpoints、Fierce Biotech；仅发现线索，随后回到公司、会议或期刊原始来源 |

### 3.1 候选临床发现（仅 `discover`）

- 以 NCT 编号或试验代号为键归并来源线索；同一试验的多次公开披露合并为一项。
- 只纳入至少有一条公开临床疗效/安全性数据来源的试验；仅有 CTG 注册、无公开结果的试验不进入候选，留在药品页管线表。
- 候选清单只列 `#`、临床试验（NCT/代号）、适应症与治疗线、阶段、最近公开年月；不列 URL，不比较全文完整度，也不生成 plan 表。
- 候选 ID 优先用 NCT 编号，其次试验代号；两者都没有时用本次运行内稳定的编号 `未命名-{n}`（跨运行不保证相同，以调用方 plan 中记录为准），并在返回给调用方的内部数据中附带来源线索 URL（清单本身仍不展示 URL），供 `resolve` 定位。
- 年月只写到月：完整年月写 `YYYY-MM`；只有年份写 `YYYY（月份未披露）`；年月均未知写“未披露”。不得把检索日期当作发布日期。
- 按阶段 Phase III、Phase II、Phase I/II、Phase I、未披露排序；同阶段按最近公开年月倒序，再按试验 ID 稳定排序。
- 没有任何合格候选时返回空清单并停止，不得虚构试验或 URL。
- `discover` 可执行 Step 4 的只读已提取来源排除，但不得执行 Step 5–6，也不判断最佳链接。

### 3.2 最佳来源检索（`resolve` 和 `full`）

- `resolve` 只处理调用方给出的选中试验；`full` 为全部候选试验执行。不得把未选试验写入 plan。
- `resolve` 的输入是试验 ID 清单；`未命名-{n}` 必须同时收到其来源线索 URL，否则停止，不得靠序号重新推断。
- 对每个试验检索并打开候选来源，按“数据完整度”选一个主链接：核心疗效、安全性、样本量/分析集、试验设计和关键亚组越完整越优先。
- 完整度相近时，优先最终或更新分析，再优先数据截止日较新者；来源可获取性和可靠性用于避免选择无法核验的候选，不用于压过明显更完整的数据。
- 同一试验的早期或补充披露不静默丢弃；若它们含主链接没有的关键数据，把完整备选 URL 和差异写入该行备注，不为每个披露单独建行；无法确定主链接时停止并报告候选。
- 同一 URL 覆盖多个选中试验时只保留一个来源对，并在 plan 行中合并试验代码；若该 URL 还覆盖未选试验，不得把未选试验当作本次建库目标。
- 选中试验的最佳来源若命中 Step 4 的当前药品已提取集合，视为已覆盖：不重复写 plan 行，在返回结果中列为“已提取”，不计入未能确定来源。

## Step 4: 排除当前药品已提取来源

只读扫描 **当前药品的公司级 `raw_dir`** 中 YAML frontmatter 的 `source:`。canonical source 与本地 PDF 身份以 `../schema/raw-spec.md` 为权威，只使用 raw 中持久化的准确值。不得扫描整个研究库，也不得传入或推断旧全局 `raw_dir`。

```text
python "{clinical_research_dir}/scripts/scan_sources.py" --raw-dir "{raw_dir}" --format urls --strict
```

`raw_dir` 是 `resolve_only` 返回的公司级 `{research_dir}/{company_id}/raw`；目录不存在时集合为空。strict 扫描发现损坏 frontmatter、路径逃逸或配对异常时停止并报告，不得使用部分结果。

准确重复键与比较方式以 `../schema/raw-spec.md` 为准。当前公司布局中 canonical `source` 准确匹配的候选应剔除；其他药品下的相同来源允许跨药复用，不得阻塞。

## Step 5: 筛选与去重

1. 先做轻量可达性预检（HEAD 或 basic fetch）。403、404 或连接失败时寻找同文镜像；仍不可达则排除。
2. 用 `web_fetch` 确认内容包含 ORR、PFS、OS、AE 等临床疗效或安全性数据。**公司公告与新闻来源必须包含具体临床数值**（样本量、ORR/PFS/OS/HR/CI、AE 百分比等）；仅定性表述（如“临床成功”“耐受性良好”“数据将择期公布”）的公告不进 plan。
3. 排除二手转述、百科、聚合页、纯新闻、CTG/注册页，以及付费墙无摘要、反爬或空页面等无法获取内容的来源。**上市公司公告的 PDF 载体一律不作为来源**（公告内容应通过网页版新闻稿、IR 页面或摘要库获取），避免 PDF 提取乱码。
4. 同一试验按数据完整度选择主链接：优先覆盖样本量/分析集、核心疗效、安全性、试验设计和关键亚组的来源；完整度相近时，再优先最终/更新分析和较新数据截止，最后才按期刊全文 > 会议摘要 > 公司公告/新闻稿排序。来源类型不得压过明显更完整的数据；选公司公告或新闻稿为主链接时，备注写明缺少的设计或方法信息。早期或补充披露含主链接没有的关键数据时，在备注写入完整备选 URL 和差异；无法确定唯一主链接时停止并报告候选。
5. 公告/新闻溯源：当某试验的最优候选为公司公告或新闻来源时，检查原文是否提及学术会议（ASCO/ESMO/WCLC/ASH/EHA/SABCS/AACR/CSCO 等）或期刊（含 DOI、“published in”/“presented at”）；有线索则用“试验代号/药品 + 会议/期刊”定向检索（最多 2 次），找到数据更完整的一手来源则替换；未提及或检索无果时保留公告。溯源仅一层、不递归；公告提的是未来会议（数据尚未公布）视为检索无果。
6. 无 NCT 或试验代号但确含临床数据的来源纳入 plan，编号填 `—`。**Phase I 来源保留但排最低优先级**，排序位于全部 Phase II/III 之后（适应症页不设 1 期表，Phase I 数据通常仅时间线使用）。
7. 最后按将持久化的准确 supplied/canonical-final URL 字符串去重，不做 percent decoding；仅语义等价但字符串不同的 URL 交人工判断。同一 URL 涉及多个适应症或试验时合并单元格，可用 `<br>` 或 `；` 分隔。

## Step 6: Plan 合同

`discover` 不生成 plan。`resolve`/`full` 只为最终选中的试验生成 plan；每行是一个 raw/summary 来源对，备注须能说明该试验为何选择此链接。`drug-build` 会在同一文件头部追加 `> 临床选择` 标记和尾部候选区；本 skill 不生成或修改这两部分。

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
| 备注 | 写明选择该链接的完整度理由；如有补充披露，写完整备选 URL 和差异 |

主表排序：

1. 临床阶段：Phase III > Phase II > Phase I > 其他/未知。
2. 同阶段：详细/最终分析 > 预披露/期中。
3. 再按数据截止日：新 > 旧。

## Step 7: 返回结果

- **`discover`**：只返回候选临床清单和内部选择数据，不向用户展示 URL，也不生成 plan；`未命名-{n}` 的来源线索 URL 只在内部数据中返回。等待 `drug-build` 完成选择或自动全选。
- **`resolve`**：只返回选中试验的 plan 行和未解决项；不扩展未选试验。
- **`full` / 独立调用**：返回全部试验的 plan 表，不保存文件。

候选临床清单：

```text
data-search 候选临床：
- 药品: {drug_id} ({drug})
- 候选试验: N 个

| # | 临床试验 | 适应症（含线） | 阶段 | 最近公开年月 |
|---|---|---|---|---|
| 1 | NCT04521625 / EXAMPLE-301 | NSCLC 1L；NSCLC 2L+ | III | 2025-06 |
| 2 | EXAMPLE-101 | NSCLC 后线 | II | 2024（月份未披露） |
```

`resolve` / `full` 结果：

```text
data-search 完成：
- 药品: {drug_id} ({drug})
- 模式: resolve / full
- 选中试验: N 个
- 已确定最佳来源: M 个
- 已提取复用: K 个
- 未能确定来源: {试验 ID 及原因；如有}
- plan 表: （返回调用方或用户，不自行持久化）
- 下一步: 由 drug-build 或用户决定是否提取
```
