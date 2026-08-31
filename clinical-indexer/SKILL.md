---
name: clinical-indexer
description: |
  按 clinical-research 2.0 布局扫描已验证 summary，增量维护药品页、适应症页和根索引。
---

# 临床索引增量归档

## 责任与边界

- 由 `clinical-research/SKILL.md` 路由执行，也可由 cron 直接执行。
- 本 skill 是 summary 可归档资格的唯一完整门禁。一个合格 summary 更新一个药品页、`indications` 数组中的每个适应症页，再串行维护根 `index.md`。
- 不修改 summary 或 raw，不重新验证 raw 数据，不重新选择归档公司，不迁移目录。
- 只支持 2.0 药品树；不兼容扫描旧版布局，不创建 `company.md`。

## 输入与共享契约

只读取 `../config.yaml` 中的 `research_dir`，不读取 `summary_dir`、`drug_dir` 或 `indication_dir` 配置项：

```text
root_index     = {research_dir}/index.md
indication_dir = {research_dir}/indication
drug_page      = {research_dir}/{company_id}/{drug_id}/{drug_id}.md
raw_dir        = {research_dir}/{company_id}/{drug_id}/raw
summary_dir    = {research_dir}/{company_id}/{drug_id}/summary
```

| 模式 | 输入范围 | 约束 |
|---|---|---|
| 全量（默认） | 语义扫描且只扫描 `{research_dir}/*/*/summary/*.md` | 用项目 Python 脚本或 `pathlib` 扫描并验证目录语义；不得依赖 shell `grep`、`find`、glob 展开或 Unix 命令 |
| 部分 | 调用方传入明确 summary 路径列表 | 只处理给定路径，不扩展同目录或全库；执行与全量相同的校验和写入规则 |

summary 必须是药品目录的直接子目录，药品页必须是相邻 `{drug_id}.md`。`research_dir` 是 vault 根，不含 `company/` 容器。跳过 `index.md`、隐藏目录、`indication/`、`attachments/`、`.temp/`、其他已知基础设施目录和不符合 2.0 药品树的 Markdown；这些根目录绝不能识别为公司。扫描按 research-root-relative POSIX 路径稳定排序。

Cron 从流程第 1 步开始，自行读取配置、当前 drug/indication schema 和根索引，不等待确认。可独立处理的失败项记录后继续；结构冲突不得猜测或静默修复，最终返回完整统计和失败清单。

## 不变量与写入策略

### 不变量

- 根索引是 `drug_id`、通用名、aliases、药品链接、公司 aliases 和所有权规则的权威快速索引；既有归档公司优先。
- 每个 summary 仅对应所在药品树的一个药品页，但其非空 `indications` 数组可对应多个独立适应症页，必须全部处理。
- 仅同时通过严格 frontmatter、完整解析、充分覆盖和内部一致审核章节的 summary 可归档。
- 不按修改时间、hash 或索引更新时间判断归档状态，只按规范 `source_identity` 判断。
- 更新必须增量、幂等、串行；不破坏用户内容，不做全量重建或自动删除冲突内容。

### 写策略

| 规则 | 药品页 | 适应症页 | 根 `index.md` |
|---|---|---|---|
| 写入范围 | 每个 summary 一个来源块；按 indications、trial identity、披露时间组织，保留全部适应症归属 | 每个 indication 的该药品/试验/来源块 | 仅对应 managed markers 内当前主键行 |
| 来源标记 | 块首行写唯一规范 `source_identity` | 块首行写同一规范 `source_identity` | 不复制来源块，以 managed 药品/适应症表链接验证完整性 |
| 链接 | summary/raw 使用相对路径，如 `summary/file.md`、`raw/file.md` | summary 和药品使用完整 vault 路径 wikilink | 药品和适应症使用完整 vault 路径 wikilink |
| wikilink pipe | 表内 alias `|` 写为 `\|`，表外用普通 `|`；解析时等价 | 同左 | 同左 |
| 保留内容 | 保留章节、未知 frontmatter、人工注释和手工排序 | 保留旧来源、未知字段、人工内容和手工排序 | 保留用户段落、注释、自定义列/单元格、既有行顺序和无关格式 |
| 合并与冲突 | 相同来源不重复；只补 schema 明确缺失内容；同 cohort/指标/披露时间冲突时并列保留来源并标记“数据差异待人工确认” | 相同来源不重复；冲突保留双方并标记待人工确认 | 按主键最小合并，等价条目/alias/链接不重复；公司或链接变化视为冲突，不覆盖或迁移 |
| 新建/排序 | 不在未知位置新建第二个药品页 | 不存在时按 indication schema 创建 | 新行按本轮稳定顺序追加；仅新初始化或 pristine 空表可整体排序 |
| 并发保护 | 写前重读并复查来源身份 | 写前重读并复查来源身份，写后验证 | 每次 upsert 前重读；不得并行写 Markdown 索引文件 |

完整 vault 路径不使用 `../`，不添加 `research/` 或 `company/` 前缀，例如 `[[第一三共/DS-8201/DS-8201.md|DS-8201]]`、`[[indication/NSCLC_1L.md|NSCLC_1L]]`。显示文本可变，去重始终依据规范来源身份。

### 目标矩阵

| 目标 | 每个合格 summary 的期望状态 | 失败影响 |
|---|---|---|
| 药品页 `{research_dir}/{company_id}/{drug_id}/{drug_id}.md` | 规范来源身份恰好一次 | 停止该 summary，不继续适应症页和根索引 |
| 每个非 schema 排除的 `{research_dir}/indication/{indication_id}.md` | 同一规范来源身份恰好一次 | 记录该项，继续其他 indication；summary 标为未完整归档 |
| 根药品表 | `drug_id`、通用名、aliases 唯一链接正确药品页 | 当前条目未完整归档 |
| 根适应症表 | 仅在对应页面成功写入并验证后 upsert | 不创建或更新失败页面的索引行 |

## 流程

### 1. 读取配置、schema、根索引并预协调

1. 读取 `../config.yaml`，只取 `research_dir`。
2. 读取当前 2.0 drug schema 和 indication schema；输出结构以 schema 为准。
3. 首先读取 `{research_dir}/index.md`，按 index schema 的 managed markers 建立 `drug_id`、通用名、aliases、药品链接和 `company_id` 映射。
4. 读取集中公司 aliases 和所有权规则，仅校验既有归档，不迁移目录。

配置、根索引或 schema 不可读时停止。核心标题重复、managed marker 重复/不配对/错序或 marker 内表格畸形时，按 index schema 阻断受影响表，不重建、不猜测；药品表不可读时不得处理 summary。重复 `drug_id`、alias 指向多个药品或链接与 ID 不一致时记录结构冲突，阻断受影响药品，其他药品可继续。

读取 summary 前，按 research-root-relative POSIX 路径稳定排序扫描 `{research_dir}/{company_id}/{drug_id}/{drug_id}.md` 语义的直接药品树。仅目录组件 Windows-safe、药品页可解析、页内 `drug_id` 与目录一致、`company_id` 与直接父目录一致，且无同 ID 多树、索引冲突或 alias 歧义的树有效。

将有效树与根药品表预协调：已有行仅做 schema 允许的最小字段合并；缺失行从药品页身份和已知字段补建，使“药品树有效但索引漏行”可恢复。不得要求缺失行预先存在，也不得仅从 summary 创建身份。未知公司仅在目录身份明确且公司表可安全 upsert 时追加；公司身份冲突则阻断该树。既有行保持顺序，本轮缺失行按 `drug_id` 稳定追加；仅新初始化或 pristine 空表可整体排序。写后重读验证根索引。

### 2. 获取列表并执行完整资格门禁

按模式用 Python 获取路径，转换为 research-root-relative POSIX 身份，并拒绝解析后逃逸 `research_dir` 的路径。每个 summary 至少包含：

- `drug_id`、`indications` 数组、`verification`、`verification_fail_count`、`verification_coverage`
- schema 要求的来源、日期、试验、公司、阶段和展示字段
- 来源原文链接及临床有效性/安全性数据

每个 `indications` 对象以唯一 `indication_id` 作为稳定 `section_id`，与正文中同序的一个 `## [{indication_id}] {indication}` 分组一一对应；显示标题不是唯一身份。

本 skill 的完整资格门禁如下，必须全部通过：

1. `verification` 严格等于 `passed`。
2. `verification_fail_count` 严格为整数 `0`。
3. `verification_coverage` 严格等于 `complete`。
4. 正文恰有一个二级 `## 数据一致性审核`，且为最后一个二级章节；其中审核表具有 schema 要求列、结构完整且至少一行。每行状态必须精确解析为 `PASS`、`WARN` 或 `FAIL`，禁止子串、大小写模糊匹配或自由文本推断。
5. `drug_id` 存在，且与目录名和相邻药品页身份一致。
6. `indications` 是非空数组；每项具备 schema 要求的稳定 identity 和展示字段。`indication_id` 唯一，对象数、顺序与正文分组严格一致；不得去重或静默合并。
7. 原文链接指向同一药品树的 `raw/`，且符合 schema。
8. 经第 1 步预协调后，根索引唯一链接该 `drug_id` 到当前药品页。
9. 审核表覆盖每个适应症分组、临床数值、试验事实和关键 cohort/方案。空状态、未知状态、畸形行、重复且冲突的审核项或无法映射 section identity 的行均失败。
10. `verification_fail_count` 等于审核表中精确 `FAIL` 行数；可归档时计数为 `0`，所有行仅为 `PASS`/`WARN`，且表外审核结论不得声明 `FAIL`。三者不一致即失败。

失败时不修改 summary，并分别记录 `verification`、`verification_fail_count`、审核章节缺失/重复/非末节、审核表畸形或覆盖不足、审核含 `FAIL`、section identity 不一致或其他结构原因。通过门禁后无需再次对照 raw，但禁止仅凭 `verification: passed` 判定合格。

### 3. 计算目标与归档缺口

```text
expected_drug_page = {research_dir}/{company_id}/{drug_id}/{drug_id}.md
expected_indication_pages = indications 中每项对应的 {research_dir}/indication/{indication_id}.md
source_identity = {company_id}/{drug_id}/summary/{filename}.md
```

来源身份必须是相对 `research_dir` 的 POSIX 路径，不使用绝对路径、文件名、反斜杠或 URL 编码，例如：

```text
恒瑞/SHR-1701/summary/SHR-1701@ASCO2026.md
```

每个 managed 来源块首行写：

```markdown
<!-- source_identity: {company_id}/{drug_id}/summary/{filename}.md -->
```

同一目标页中该 identity 必须恰好一次。`company_id` 和药品链接以预协调后的根索引为准；summary 路径不一致时记录冲突，不移动文件或改写归属。独立检查目标矩阵各维度；来源位于错误药品页或适应症页时，不视为已归档，也不自动删除。

### 4. 串行更新每个 summary

按稳定顺序逐项处理：

1. 按写策略更新唯一药品页。路径必须来自已验证药品树；药品页缺失是身份错误，只有索引漏项由预协调修复。一个 summary 无论含多少 indications，只归档一次；直接保留 schema 要求的有效性与安全性，不虚构字段。
2. 药品页写入失败时记录并停止该 summary；其他 summary 不回滚。
3. 按稳定 indication identity 顺序处理每项。schema 明确排除建档的探索性泛瘤种记录跳过，药品页归档仍有效。
4. 每个适应症页成功创建/更新并重读验证后，立即重读根索引并 upsert 该 `indication_id` 行；失败则不更新其索引行，记录后继续其他 indication。
5. 药品页完成后，重读根索引并最小 upsert 当前药品的 `drug_id`、常用通用名、aliases、`company_id`、药品页完整 vault wikilink，以及 schema 要求且可由已验证内容确定的信息。公司 aliases 和所有权规则仍集中保存。
6. 适应症失败不撤销已成功的药品或其他适应症 upsert，但 summary 必须标为未完整归档。当前根条目已完整且无新信息时不写文件。

### 5. 验证幂等性与完整性

重读所有本轮目标并验证目标矩阵、链接类型、表内/表外 pipe 规则；三个根核心表的标题、managed markers 和结构仍唯一有效；自定义列/单元格与既有行序未改变；重复运行不新增数据块、链接、aliases 或页面。某一维度已归档不得掩盖另一维度缺失。

## 失败与恢复

- 资格失败只跳过该 summary 并记录精确原因，不修改源文件。
- 重复来源、错误页面引用、身份/索引歧义、结构损坏或并发变化均报告冲突，不猜测、不覆盖、不自动删除。
- 可独立处理的页面失败不回滚已完成目标；按目标矩阵标记 summary 未完整归档。
- 下次运行按规范来源身份重新计算缺口并仅补缺失维度；不得用模板重建整个 `index.md`。

## 输出

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

报告中的来源路径使用 research-root-relative POSIX identity。所有合格 summary 在药品页、全部适应症页和根索引均无缺口时，报告 `无变化: yes`，且不得写入任何文件。
