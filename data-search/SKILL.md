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
> 职责：搜索某创新药已公布的临床数据来源，输出一个 plan 表。
> 本 skill 不提取数据、不写入研究目录，只产出候选 URL 清单；plan 表直接返回，不保存文件。只有 `drug-build` 可将 plan 持久化到根 `{research_dir}/.temp/plans/`。

## 执行约束

- ✅ 搜索已公布的临床疗效/安全性数据来源（期刊、会议、公司公告、注册库）
- ✅ 输出 plan 表，直接返回给用户或下一步调用
- ✅ 搜不到药物代号时停下询问用户，不猜测
- ❌ 不提取临床数据（由 `multi-extractor` 负责）
- ❌ 不写入 `raw/`、`summary/`、药品页、`indication/` 或 `.temp/plans/`
- ❌ 不调用 `multi-extractor`
- ❌ 不评价临床数据质量
- ❌ 不用二手媒体数字作为数据源
- ❌ 不读取或兼容 v1 路径，不创建全局 `raw/`、`summary/`、`drug/` 或 `trials/`

所有文件和目录操作必须兼容 Windows。脚本使用 Python 3.10+ 标准库与 `pathlib`；不得依赖 shell 的 `grep`、`find`、`sed` 或其他 Unix 文件搜索命令。

## 固化规则

1. **别名全集先于一切搜索**（漏别名 = 漏数据）
2. **来源分级**：会议摘要 / 期刊 / 公司公告 = 原始；媒体 = 只做线索；**CTG 注册信息只作搜索索引骨架，其注册页不进 plan 表**（CTG 只有方案无临床数据，由 drug-trials-search 单独处理写入管线表）
3. **多版本管理**：同一试验按数据截止日排序，不同 cutoff 都保留
4. **搜不到就停**：drug-identity 无法确认身份时返回确认，不猜测
5. **内容质量优先于来源等级**：付费墙期刊不如可获取的会议摘要
6. **无 NCT 来源纳入**，填 `—`
7. **每个数字必须能溯源到原始来源**，二手媒体数字不直接用
8. **一个来源只占一行**：同一来源只生成一个 summary，因此同一 URL 在 plan 中只出现一次；该行可列出多个适应症，不得按适应症复制 URL

## Step 1: 配置、根索引与药物身份锚定

1. 首先读取 `{clinical_research_dir}/config.yaml`，配置只能提供一个绝对路径 `research_dir`。配置缺失、无效或路径不可读时停止，按顶层 skill 的初始化流程处理；不得从旧字段或目录结构推断路径。
2. 配置解析成功后，立即首先读取 `{research_dir}/index.md`。根索引不可读时停止；不得先扫描目录或搜索 web。
3. 读取 `../drug-identity/SKILL.md`，只以 `mode: resolve_only` 调用：用根索引解析输入名称，未命中时才搜索可靠来源补充确认。即使是新药，也只返回拟议身份/路径；不得创建目录、药品页或根索引条目。
4. 获取包含规范身份和已解析目录的完整上下文：

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

（drug 展示名从 drug_aliases 中选取通用名。）

校验所有解析目录都位于 `research_dir` 内并符合当前 2.0 布局。后续步骤原样传递该上下文，不得自行重选 `company_id`、`drug_id` 或目录。此 workflow 不支持 v1 路径，不执行兼容查找或迁移。

如果无法唯一确认药物身份或归档公司，停下返回用户确认，不进入后续步骤。整个 data-search 保持 no-write：identity、扫描和搜索均不得创建、修改或删除研究文件。

## Step 2: 官方临床试验注册库

1. 复用 `drug-trials-search` 脚本查 ClinicalTrials.gov，使用身份对象中的 `drug_id` 或主要别名作为查询词：

```text
python {skill_dir}/../drug-trials-search/search_trials.py --drug "{drug_id 或主要别名}" --format json
```

2. 从 JSON 结果中提取 NCT 编号、阶段、适应症、状态清单，作为后续搜索的索引骨架。
3. chinadrugtrials.org.cn：当前未实现，跳过并记录 "CDT 未查询"。
4. **CTG 查询结果仅用于提取试验代号/适应症/阶段作为索引骨架，CTG 注册页本身不作为 plan 表来源**（只有方案信息、无已公布临床数据）。

## Step 3: 公司官方渠道

1. 官网 IR 管线页、新闻中心、业绩报告、PPT
2. 上市公司公告（港交所披露易 / 巨潮）
3. **合作方公告也要搜**（如阿斯利康公布 DS-8201/Enhertu 的数据）
4. 搜索：`{公司名} {drug} phase OR results press release`
5. 对每个候选 URL，用 `web_fetch` 快速判断是否包含临床数据。

## Step 4: 学术会议

1. 逐个会议搜：ASCO / ESMO / ESMO Asia / WCLC / SABCS / ASH / AACR / CSCO
2. 搜索词：`{代号} {会议名}`（不带年份，以列出该会议所有包含该代号的内容）
3. 查会议摘要库原文：
   - ASCO / JCO：ascopubs.org
   - ESMO：oncologypro.esmo.org、annalsofoncology.org
   - WCLC：iaslc.org
   - ASH：ashpublications.org
   - AACR：aacrjournals.org
4. 记录：摘要号、数据截止日期
5. 对每个候选 URL，用 `web_fetch` 快速判断是否包含临床数据。

## Step 5: 期刊

1. PubMed 检索：`{drug}` 或 `{drug} {indication}`

```text
搜索 site:pubmed.ncbi.nlm.nih.gov {drug}
```

2. 定向 site search：`{drug} site:nejm.org OR site:thelancet.com OR site:jco.org OR site:nature.com`
3. 对每个候选 URL，用 `web_fetch` 快速判断是否包含临床数据。

## Step 6: 行业媒体线索

1. 来源：医药魔方、Insight、药融云、Endpoints、Fierce Biotech
2. **只用于发现线索**：哪个会议将公布、哪个数据刚发布
3. 发现线索后回到 Step 3/4/5 查原始来源
4. 二手媒体的数字一律不直接用，不作为 plan 表来源
5. 媒体 URL 不进入 plan 表

## Step 6.5: 排除当前药品已提取来源（增量建档）

使用配置只读扫描整个 2.0 研究库中所有来源的 YAML frontmatter `source:` 字段；结果必须保留 raw 相对路径，以筛选当前药品。URL 保持 raw 中的准确字符串；本地 PDF 身份必须是 `Path.resolve(strict=True).as_posix()` 得到的 resolved absolute POSIX path。不得传入或推断旧全局 `raw_dir`：

```text
python "{clinical_research_dir}/scripts/scan_sources.py" --raw-dir "{raw_dir}" --format urls --strict
```

这里的 `raw_dir` 是 `resolve_only` 返回的当前药品拟议/既有目录，不是旧版全局 raw；目录不存在时已提取集合为空。strict 扫描出现损坏 frontmatter、路径逃逸或配对异常时停止并报告，不能用部分结果做排除。以 `(company_id, drug_id, source)` 为准确重复键。对 Step 3-6 收集的候选 URL：

- **已在当前药品树中提取过**（canonical source 准确字符串匹配）→ 剔除，不进入 plan 表
- **未提取过** → 保留，进入 Step 7

相同 `source` 位于其他药品树时属于允许的跨药复用，必须保留，不得阻塞。所有工作流都比较 raw 中同一个 canonical 值；不得用 percent-decoded URL、PDF 文件名、相对路径或反斜杠路径替代。

## Step 7: 内容判断与去重

对每个候选 URL：

- **可达性预检**：先做轻量可达性探测（HEAD 请求或 basic fetch），403/404/连接失败 → 尝试找同文镜像，找不到则排除，不进入后续判断。
- 用 `web_fetch` 快速判断是否确实包含临床疗效或安全性数据（ORR/PFS/OS/AE 等）
- 排除：二手转述、百科、聚合数据库页、不含疗效/安全性数据的纯新闻
- 排除：无法获取内容的页面（付费墙且无摘要、反爬、空页面）
- 排除：CTG/注册库的试验注册页（无已公布临床数据，只有方案信息）

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

最终按来源 URL 再去重：

- 一个 URL 只能对应一行 plan，也只会产生一个 raw/summary 来源对
- URL 去重使用将被持久化的准确 supplied/canonical-final 字符串，不做 percent decoding；仅语义等价但字符串不同的 URL 作为近似重复交由人工判断
- 同一来源覆盖多个适应症时，在该行“适应症”列列出全部适应症（以 `<br>` 或 `；` 分隔），不得为每个适应症复制一行
- 同一来源同时报告多个试验时，也优先合并在一个来源行中，并在“临床代码或NCT编号”列列出全部代码
- “同一试验不同数据截止日都保留”是保留不同来源版本，不得导致同一 URL 重复

## Step 8: 输出 plan 表

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

列说明：

| 列 | 说明 |
|---|---|
| # | 序号 |
| 临床代码或NCT编号 | NCT 编号或公司试验代号；无则填 `—` |
| 适应症 | 精确适应症，含治疗线；同一来源涉及多个适应症时全部列在同一单元格，不拆行 |
| 临床阶段 | Phase I / II / III / IV |
| 来源类型 | `journal`、`conference`、`company_release`、`regulatory`、`other` |
| 数据截止日 | 数据截止日（cutoff），用于区分同一试验的不同披露版本；来源未给出则填 `—` |
| 网址链接 | 原始来源 URL |
| 备注 | 来源特点说明，如"NEJM 全文"、"ASCO2025 摘要"、"首次人体数据" |

## Step 9: 输出报告

plan 表不保存到文件，直接返回给用户或调用方使用。`data-search` 在独立调用和被编排调用时都不得自行持久化 plan；只有 `drug-build` 可按其 workflow 将收到的 plan 保存到根 `{research_dir}/.temp/plans/`。

```text
data-search 完成：
- 药品: {drug_id} ({drug})
- 别名全集: {列表}
- 搜索候选: N 个
- 含临床数据: M 个
- 去重后保留: K 个
- plan 表: （直接返回）
- 下一步: 用户确认 plan 表后，逐个调用 multi-extractor 提取
```

## 常见问题

### Q: 药物代号搜不到任何信息？

按 Step 1 规则停下，返回用户确认，不猜测。

### Q: 同一试验有期刊全文和会议摘要，选哪个？

以实际内容质量为准：期刊可获取全文 → 选期刊；期刊付费墙且会议摘要可获取 → 选会议摘要；两来源覆盖度相当 → 选可靠性更高的。不同数据截止日的版本都保留。

### Q: 媒体报道了数据，可以进 plan 表吗？

不可以。媒体只用于发现线索，必须回到原始来源（期刊/会议/公司公告/注册库）核实。媒体 URL 不进 plan 表。
