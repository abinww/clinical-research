# data-search 子 skill 设计文档

## 目标

搜索某创新药已公布的临床数据来源，输出一个 plan 表，供 `clinical-extractor` 后续逐个提取。本 skill 不提取数据、不写入 `raw/`/`summary/`/`drug/`/`indication/`，只产出候选 URL 清单。

## 触发词

- "搜索已公布的临床数据"
- "查找临床数据来源"
- "建库"流程中由编排 skill 调用

## 输入

- 药品名称或代号（必填）
- 适应症（可选，缩小范围）
- 可选：NCT 编号列表（若已有 `drug-trials-search` 结果）

## 输出

一个 plan 表，直接返回给用户或下一步（`clinical-extractor`）调用，不保存到文件。

plan 表格式：

```markdown
# {drug_id} 临床数据来源 plan

> 生成时间: {YYYY-MM-DD}
> 药品身份: {drug_id} | {drug} | target: {target} | 公司: {companies}
> 别名全集: {别名列表}
> 搜索范围: {使用的搜索词}

| # | 临床代码或NCT编号 | 适应症 | 临床阶段 | 来源类型 | 数据截止日 | 网址链接 | 备注 |
|---|------------------|--------|---------|---------|-----------|---------|------|
| 1 | NCT04521625 | NSCLC 1L | Phase III | journal | 2025-06-01 | https://... | NEJM 全文 |
| 2 | EXAMPLE-101 | NSCLC 后线 | Phase II | conference | 2024-12-01 | https://... | ASCO2025 摘要 |
| 3 | — | 实体瘤 | Phase I | company_release | — | https://... | 首次人体数据 |
```

列说明：

| 列 | 说明 |
|---|---|
| # | 序号 |
| 临床代码或NCT编号 | NCT 编号或公司试验代号；无则填 `—` |
| 适应症 | 精确适应症，含治疗线 |
| 临床阶段 | Phase I / II / III / IV |
| 来源类型 | `journal`、`conference`、`company_release`、`regulatory`、`other` |
| 数据截止日 | 数据截止日（cutoff），用于区分同一试验的不同披露版本；来源未给出则填 `—` |
| 网址链接 | 原始来源 URL |
| 备注 | 来源特点说明，如"NEJM 全文"、"ASCO2025 摘要"、"首次人体数据" |

## Workflow

### Step 1: 药物身份锚定

搜不到代号就停下问用户，不猜测。

1. 搜索 `{代号} + 公司名`、`{代号} + clinical trial`
2. 查公司官网管线页
3. 收集**别名全集**：研发代号、合作方代号、通用名、商品名
4. 识别：靶点、分子类型（ADC/双抗/单抗/小分子）、研发公司、合作方
5. 搜不到代号 → 停下，返回用户确认，不继续后续步骤

输出（内部记录，不单独保存文件）：

```text
drug_id: {按 drug-spec.md 优先级确定}
drug: {通用名}
target: {最简形式}
aliases: {别名全集}
companies: {研发公司及合作方}
molecule_type: {ADC/双抗/单抗/小分子}
```

### Step 2: 官方临床试验注册库

1. 复用现有 `drug-trials-search` 脚本查 ClinicalTrials.gov
   - `python3 {skill_dir}/../drug-trials-search/search_trials.py --drug "{药品名称或别名}" --format json`
   - 从 JSON 结果中提取 NCT 编号、阶段、适应症、状态
2. chinadrugtrials.org.cn：当前未实现，跳过并记录"CDT 未查询"
3. 输出：NCT 编号、阶段、适应症、状态清单（作为后续搜索的索引骨架）

### Step 3: 公司官方渠道

1. 官网 IR 管线页、新闻中心、业绩报告、PPT
2. 上市公司公告（港交所披露易 / 巨潮）
3. **合作方公告也要搜**（如阿斯利康公布 DS-8201/Enhertu 的数据）
4. 搜索：`{公司名} {drug} phase OR results press release`
5. 对每个候选 URL，用 `web_fetch` 快速判断是否包含临床数据

### Step 4: 学术会议

1. 逐个会议搜：ASCO / ESMO / ESMO Asia / WCLC / SABCS / ASH / AACR / CSCO
2. 搜索词：`{代号} {会议名}`（不带年份，以列出该会议所有包含该代号的内容）
3. 查会议摘要库原文：
   - ASCO / JCO：ascopubs.org
   - ESMO：oncologypro.esmo.org、annalsofoncology.org
   - WCLC：iaslc.org
   - ASH：ashpublications.org
   - AACR：aacrjournals.org
4. 记录：摘要号、数据截止日期
5. 对每个候选 URL，用 `web_fetch` 快速判断是否包含临床数据

### Step 5: 期刊

1. PubMed 检索：`{drug}` 或 `{drug} {indication}`
   - 通过 web_search 搜索 `site:pubmed.ncbi.nlm.nih.gov {drug}`
2. 定向 site search：`{drug} site:nejm.org OR site:thelancet.com OR site:jco.org OR site:nature.com`
3. 对每个候选 URL，用 `web_fetch` 快速判断是否包含临床数据

### Step 6: 行业媒体线索

1. 来源：医药魔方、Insight、药融云、Endpoints、Fierce Biotech
2. **只用于发现线索**：哪个会议将公布、哪个数据刚发布
3. 发现线索后回到 Step 3/4/5 查原始来源
4. 二手媒体的数字一律不直接用，不作为 plan 表来源
5. 媒体 URL 不进入 plan 表

### Step 7: 内容判断与去重

对每个候选 URL：

- 用 `web_fetch` 快速判断是否确实包含临床疗效或安全性数据（ORR/PFS/OS/AE 等）
- 排除：二手转述、百科、聚合数据库页、不含疗效/安全性数据的纯新闻
- 排除：无法获取内容的页面（付费墙且无摘要、反爬、空页面）

对同一 NCT 或同一临床试验代码的多个来源：

- 可靠性层级：期刊全文 > 会议摘要 > 公司公告 > 新闻稿
- **以实际内容质量为准**：
  - 期刊付费墙/无摘要 → 降级，改用可获取的会议摘要
  - 会议只有基本信息，公司公告有更详细数据 → 保留公司公告
  - 两来源覆盖度相当 → 选可靠性更高的
- 只保留一个最优来源，静默丢弃其余
- **同一试验不同数据截止日**（早期简版 vs 后期详版）都保留

对于无 NCT 也无试验代号的来源：

- 纳入 plan 表
- "临床代码或NCT编号"列填 `—`
- 只要内容确实包含临床数据

### Step 8: 输出 plan 表

按上方"输出"章节的格式生成 plan 表。

### Step 9: 输出报告

plan 表不保存到文件，直接返回给用户或下一步（`clinical-extractor`）调用使用。

```text
data-search 完成：
- 药品: {drug_id} ({drug})
- 别名全集: {列表}
- 搜索候选: N 个
- 含临床数据: M 个
- 去重后保留: K 个
- plan 表: （直接返回）
- 下一步: 用户确认 plan 表后，逐个调用 clinical-extractor 提取
```

## 固化规则

1. **别名全集先于一切搜索**（漏别名 = 漏数据）
2. **来源分级**：CTG / 会议摘要 / 期刊 / 公司公告 = 原始；媒体 = 只做线索
3. **多版本管理**：同一试验按数据截止日排序，不同 cutoff 都保留
4. **搜不到就停**：Step 1 验证失败 → 返回确认，不猜测
5. **内容质量优先于来源等级**：付费墙期刊不如可获取的会议摘要
6. **无 NCT 来源纳入**，填 `—`
7. **每个数字必须能溯源到原始来源**，二手媒体数字不直接用

## 不做的事

- 不提取临床数据（由 `clinical-extractor` 负责）
- 不写入 `raw/`、`summary/`、`drug/`、`indication/`
- 不调用 `clinical-extractor`
- 不评价临床数据质量
- 不修改任何已有文件
- 不用二手媒体数字

## 与其他子 skill 的关系

```
drug-trials-search → 输出 CTG 注册信息到 drug/ 管线
data-search        → 输出 plan 表到 trials/（本 skill）
clinical-extractor → 读 plan 表中的 URL，逐个提取到 raw/ → summary/
```

"建库"编排 skill（将来设计）会按顺序调用这三个子 skill。

## 文件结构

```text
data-search/
└── SKILL.md          # 触发词 + 10 步 workflow
```

不新增脚本：复用 `drug-trials-search/search_trials.py` 的 JSON 输出和 `web_search` / `web_fetch` 工具。

## 与现有 skill 的边界

| 职责 | skill |
|---|---|
| 查 CTG 注册信息 | drug-trials-search |
| 搜索已公布的临床数据来源 | data-search（本 skill） |
| 提取 URL/PDF 临床数据 | clinical-extractor |
| 增量归档 summary 到索引 | clinical-indexer |
| 评价临床数据 | clinical-trial-evaluator |
| 批量 raw → summary | batch-extractor |

## 根 skill 路由表更新

在 `clinical-research/SKILL.md` 路由表中新增：

```markdown
| "搜索已公布的临床数据" / "查找临床数据来源" | data-search | 搜索期刊/会议/公告，输出 plan 表 |
| 药品名称 + "建库" | data-search → clinical-extractor | 先搜索数据来源，再逐个提取 |
```

## 不修改的部分

- 现有子 skill 不修改
- schema 不修改
- `drug-trials-search/search_trials.py` 不修改（只复用其 JSON 输出）
- batch-extractor、专家点评、shell 跨平台命令不修改
