---
name: clinical-indexer
description: |
  按 clinical-research 2.0 布局扫描已验证 summary，增量维护药品页、适应症页和根索引。
---

# 临床索引增量归档

> 本文件由 `clinical-research/SKILL.md` 路由执行，也可由 cron 直接执行。
> 一个 summary 更新一个药品页及其 `indications` 数组中的每一个适应症页，最后串行维护根 `index.md`。

## 配置与布局

只读取 `../config.yaml` 中的 `research_dir`。从它派生：

```text
root_index    = {research_dir}/index.md
indication_dir = {research_dir}/indication
drug_page     = {research_dir}/{company_id}/{drug_id}/{drug_id}.md
raw_dir       = {research_dir}/{company_id}/{drug_id}/raw
summary_dir   = {research_dir}/{company_id}/{drug_id}/summary
```

不读取 `summary_dir`、`drug_dir` 或 `indication_dir` 配置项。不支持旧版平铺布局，不执行迁移、兼容扫描或所有权迁移。不存在 `company.md`。

## 调用模式

### 全量模式（默认）

语义扫描且只扫描：

```text
{research_dir}/*/*/summary/*.md
```

必须使用适当的 Python 路径扫描（项目脚本或 `pathlib`）并验证目录语义：summary 必须是药品目录的直接子目录，药品页必须是相邻的 `{drug_id}.md`。不得依赖 shell 的 `grep`、`find`、glob 展开或 Unix 命令。

`research_dir` 本身是 vault 根目录，不存在中间 `company/` 容器。跳过 `index.md`、所有隐藏目录、`indication/`、`attachments/`、`.temp/`、其他已知基础设施目录及不符合 2.0 药品树的 Markdown 文件；这些根目录绝不能被识别为公司。扫描顺序按 research-root-relative POSIX 路径稳定排序。

### 部分模式

调用方必须传入本次要归档的**明确 summary 路径列表**。只处理这些路径，不扩展到同目录或全库；每个路径仍须位于 `{research_dir}/{company_id}/{drug_id}/summary/*.md` 并通过与全量模式相同的校验。

两种模式执行完全相同的资格、幂等、冲突和写入规则。

## Cron 直接调用

Cron 从 Step 1 开始：自行读取配置、当前 drug/indication schema 和根索引，不等待用户确认。可独立处理的失败项应记录后继续；结构冲突不得猜测或静默修复。最终返回完整统计和失败清单。

## 不变量

- 根 `{research_dir}/index.md` 是 `drug_id`、通用名、aliases、药品链接、公司 aliases 和所有权规则的权威快速索引。
- 根索引中已有的归档公司分配优先；indexer 不重新选择公司，也不迁移药品目录。
- 每个 summary 只对应其所在药品树中的一个药品页。
- 每个 summary 的 `indications` 是数组，并对应零个或多个独立适应症页；不得只处理第一项。
- 只有同时满足 `verification: passed`、`verification_fail_count: 0`、审核章节存在且其中没有任何 `FAIL` 的 summary 可归档。
- 不修改 summary 或 raw 原始内容。
- 不依据修改时间、hash 或索引更新时间判断归档状态；以规范来源身份是否已存在为准。
- 保留用户编辑，更新现有页所需的最小范围，不做全量重建或破坏性删除。

## 路径与链接规则

每个 summary 的持久来源身份是相对于 `research_dir` 的 POSIX 路径，例如：

```text
恒瑞/SHR-1701/summary/SHR-1701@ASCO2026.md
```

来源比较和去重必须使用该规范身份，不使用绝对路径、文件名、反斜杠或 URL 编码形式。

Markdown 链接按页面位置生成：

- 药品页中的内部链接使用相对路径，例如 `summary/file.md` 和 `raw/file.md`。
- 适应症页和根 `index.md` 使用完整 vault 路径 wikilink，例如 `[[第一三共/DS-8201/DS-8201.md|DS-8201]]` 和 `[[indication/NSCLC_1L.md|NSCLC_1L]]`；不使用 `../`，也不添加 `research/` 或 `company/` 前缀。
- 链接显示文本可调整，但去重依据始终是规范来源身份。

## Step 1: 读取配置、schema 与根索引

1. 读取 `../config.yaml`，只获取 `research_dir`。
2. 读取当前 2.0 drug schema 和 indication schema；输出结构以 schema 为准，本文件不重复定义表格格式。
3. 首先读取 `{research_dir}/index.md`，建立 `drug_id`、通用名、aliases、药品链接和 `company_id` 映射。
4. 读取根索引中的集中公司 aliases 和所有权规则，仅用于校验既有归档，不据此迁移目录。

配置、根索引或 schema 无法读取时停止并报告。根索引中重复 `drug_id`、alias 指向多个药品、链接与 ID 不一致时，记录结构冲突；受影响药品不得写入，其他药品可继续。

## Step 2: 获取并验证 summary 列表

按调用模式用 Python 获取路径，并转换成 research-root-relative POSIX 身份。拒绝解析后逃逸出 `research_dir` 的路径。

对每个 summary 读取 YAML 和正文，至少需要：

- `drug_id`
- `indications` 数组
- `verification`
- `verification_fail_count`
- schema 要求的来源、日期、试验、公司、阶段和展示字段
- 来源原文链接及临床有效性/安全性数据

资格检查：

1. `verification` 必须严格为 `passed`。
2. `verification_fail_count` 必须严格为整数 `0`。
3. 正文必须存在 schema 定义的 `## 数据一致性审核` 章节，且该审核章节中不得出现任何 `FAIL` 状态；只检查已写审核结果，不重新执行数据验证。
4. `drug_id` 必须存在，并与目录名及相邻药品页身份一致。
5. `indications` 必须是数组；每个元素必须具有 schema 要求的稳定 indication identity 和展示字段。
6. summary 的原文链接必须指向同一药品树的 `raw/`，且格式符合 schema。
7. 根索引必须把该 `drug_id` 唯一链接到当前药品页。

任何检查失败时不修改该 summary；分别记录是 `verification`、`verification_fail_count`、审核章节缺失、审核含 `FAIL` 或其他结构条件不合格。通过这三项审核门禁后无需重复执行数据验证，但不得仅凭 `verification: passed` 推定合格。

空 `indications` 数组不符合 summary schema，必须跳过并报告。数组内重复 indication identity 先按身份去重；内容冲突则标记失败，不静默合并。

## Step 3: 计算期望目标与归档缺口

对每个合格 summary 计算：

```text
expected_drug_page = {research_dir}/{company_id}/{drug_id}/{drug_id}.md
expected_indication_pages = indications 数组中每项对应的 {research_dir}/indication/{indication_id}.md
source_identity = {company_id}/{drug_id}/summary/{filename}.md
```

`company_id` 和药品链接以根索引现有分配为准。summary 所在路径与索引分配不一致是冲突，不移动文件、不改写归属。

分别检查来源身份是否已出现在：

- 期望药品页的对应数据块；
- `indications` 中每一个期望适应症页的对应数据块；
- 根索引中该药品的条目和链接。

三个维度独立计算缺口。来源出现在错误药品页或错误适应症页时记录完整性冲突，不能视为已归档，也不得自动删除错误内容。

## Step 4: 串行处理 summary

严格按稳定排序后的 summary 逐个处理。单个 summary 的写入顺序是：

1. 更新其唯一药品页。
2. 按稳定的 indication identity 顺序更新 `indications` 数组中的每一个适应症页。
3. 前两步完成后，更新根 `index.md` 中该药品的快速查询信息。

不得并行写 Markdown 索引文件。每次写入前重新读取目标文件并重新检查来源身份，以保留用户或其他进程刚完成的编辑。

## Step 5: 更新药品页

药品页路径必须来自根索引并已在 Step 2 校验。indexer 不在未知位置创建第二个药品页；缺页或索引缺项属于身份错误，应调用 `drug-identity` 解决后再归档。

按 drug schema 增量更新：

- 一个 summary 无论含多少 indications，只在该药品页归档一次。
- 按 indications、trial identity 和披露时间组织临床数据，但保留 summary 的全部适应症归属和来源。
- 直接保留 schema 要求的有效性与安全性信息，不虚构缺失字段。
- 药品页中的 summary/raw 链接使用相对于药品页的内部路径。
- 保留已有章节、未知 frontmatter、人工注释和手工排序；只修改对应数据块及必要身份字段。
- 已存在相同来源身份时不重复追加；仅补齐 schema 明确缺失的内容。
- 同一 cohort、指标和披露时间数值冲突时，不覆盖任一值；并列保留来源并标记“数据差异待人工确认”。

写入失败时记录失败；该 summary 不继续写适应症页和根索引，避免报告成完整归档。已完成的其他 summary 不回滚。

## Step 6: 更新每个适应症页

对 summary 的每个唯一 indication 项分别执行：

- 目标固定为 `{research_dir}/indication/{indication_id}.md`。
- schema 明确排除建档的探索性泛瘤种则记录跳过；药品页归档仍有效。
- 页面不存在时按 indication schema 创建；存在时只增量更新该药品/试验/来源数据块。
- summary 来源链接和药品链接使用完整 vault 路径 wikilink，不添加 `research/` 或 `company/` 前缀。
- 保留旧来源、未知字段、人工内容和手工排序。
- 写入前再次检查规范来源身份；同一来源不得重复追加。
- 数据冲突不静默覆盖，保留双方来源并标记待人工确认。

一个 indication 写入失败时记录该项失败，并继续该 summary 的其他 indication。根索引更新仍可执行，但最终报告必须明确该 summary 尚未完整归档。

## Step 7: 串行维护根 index.md

根索引允许用户编辑。每个 summary 的页面更新结束后，重新读取 `{research_dir}/index.md`，仅对当前药品执行最小更新：

- 保证 `drug_id`、常用通用名和 aliases 可快速查找。
- 保证 `company_id` 及药品页完整 vault 路径 wikilink 与现有归档一致。
- 补充当前 schema 要求、且能从已验证内容确定的索引信息。
- 公司 aliases 和所有权规则继续集中保存在根索引，不创建 `company.md`。
- 保留用户段落、注释、未知字段、手工排序和无关格式。
- 写入前若现有归档公司或链接发生变化，视为并发/身份冲突，停止该条目更新；不迁移目录，不覆盖用户决定。
- 等价条目、alias 和链接不得重复追加。

只要当前条目已完整且无新信息，就不写根索引。不得用模板重建整个 `index.md`。

## Step 8: 验证幂等性与完整性

写入后重新读取所有本轮目标，验证：

- 每个已完成 summary 在唯一药品页恰有一个规范来源身份。
- 除 schema 排除项外，它在 `indications` 数组对应的每个适应症页恰有一个规范来源身份。
- 根索引中 `drug_id`、通用名和 aliases 唯一指向正确药品页。
- 链接类型正确：药品内部使用相对 Markdown 链接，适应症和 index 使用完整 vault 路径 wikilink。
- 再次运行不会产生额外数据块、链接、aliases 或页面。

发现重复、错误页面引用或并发修改时报告冲突，不自动删除用户内容。某一维度已归档不能掩盖另一维度缺失。

## Step 9: 输出报告

```text
clinical-indexer 2.0 增量归档完成：
模式: full | partial
扫描 summary: N
合格: A
跳过: B
资格跳过明细:
- verification 非 passed: B1
- verification_fail_count 非 0: B2
- 审核章节缺失: B3
- 审核含 FAIL: B4
- 其他结构/身份问题: B5

drug pages:
- 新建: 0
- 更新: C
- 已完整: D
- 失败: E

indication pages:
- 新建: F
- 更新: G
- 已完整: H
- schema 跳过: I
- 失败: J

index.md:
- 更新条目: K
- 已完整: L
- 冲突/失败: M

未完整归档 summary: {路径及原因}
完整性冲突: {路径、目标及原因}
无变化: yes | no
```

来源路径在报告中使用 research-root-relative POSIX 身份。所有合格 summary 在药品页、全部适应症页和根索引均无缺口时，报告 `无变化: yes` 且不得写入任何文件。
