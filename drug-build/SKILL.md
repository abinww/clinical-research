---
name: drug-build
description: |
  创新药数据库建库编排。当用户提到以下关键词时触发：
  - "对{药品}建库"
  - "建库"
  本 skill 编排 drug-trials-search、data-search、multi-extractor 完成完整建库。多链接的提取、验证与索引归档由 multi-extractor 内部处理。
---

# 创新药建库编排

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 职责：为指定创新药建立完整的临床数据库条目，包括管线表、已公布临床数据摘要、验证和索引归档。

## 执行约束

- ✅ 按固定顺序编排各子 skill：身份锚定 → 管线 → 可续跑 plan 表 → 按状态恢复（提取/验证/索引）→ 复查完整索引维度
- ❌ 不重复实现各子 skill 的内部逻辑，只读取并执行对应 SKILL.md 的 workflow
- ❌ 跳过任意步骤（除非用户明确要求）
- ✅ 静默执行：除非遇到问题（身份无法确认、plan 表为空等），不向用户展示中间结果或要求确认

## 固化规则

1. **按状态委托，不整体重提取**：全新来源交给 multi-extractor；已有 raw、待审核 summary 和已验证未完整索引 summary 分别走精确恢复路径，不覆盖已有产物。
2. **完成包含全部索引维度**：进度脚本同时检查 raw/summary、完整审核门禁、药品页、全部应建适应症页和根索引；只有脚本返回 `已完成` 才是 fully indexed。
3. **重复范围是当前药品**：canonical source 只在当前 `drug_id` 下判重。同一 canonical source 可用于不同药品；其他药品目录中的匹配既不跳过本项，也不构成本药品歧义。
4. **重试上限**：可自动恢复的单项按其当前状态重试一次，每项总尝试上限 2 次；第二次仍失败则保留 plan 并报告，不改走覆盖式重提取。
5. **静默跳过与停下询问**：当前药品下已完整索引的重复来源静默跳过；身份、当前药品内来源配对或目标索引存在歧义时停下交由人工判断。
6. **搜不到药物身份就停**：沿用 drug-identity 规则，不猜测。

## Step 1: 药物身份锚定

以 `mode: resolve_or_create` 读取并执行 `../drug-identity/SKILL.md`，获取完整标准身份与位置对象（包括 `mode`、`drug_id`、`common_name`、`drug_aliases`、`target`、`company_ids`、`molecule_type`、`company_id`、`archive_company`、`research_dir`、`drug_dir`、`drug_page`、`raw_dir`、`summary_dir`、`attachments_dir`、`status`；兼容字段 `companies` 如存在必须与 `company_ids` 相同）。后续调用必须原样传递整个对象及绝对 `config_path`，不删字段、不改名、不重算路径。

如果无法确认药物身份，停下返回用户确认，不进入后续步骤。

## Step 2: 临床试验注册查询

读取 `../drug-trials-search/SKILL.md`，按其中 workflow 执行：

- 查询该药品在 ClinicalTrials.gov 的全部试验
- 写入身份对象已解析的 `drug_page` 的 `## 当前临床管线` 章节
- 不创建 `trials/` 目录或独立 trial 搜索输出文件

## Step 3: 搜索已公布临床数据

读取 `../data-search/SKILL.md`，按其中 workflow 执行：

- 分层搜索（注册库、公司渠道、学术会议、期刊、媒体线索）
- 内容判断与去重，输出 plan 表

## Step 4: 合并或保存可续跑 plan 表

确定性 plan 路径固定为绝对路径 `"{research_dir}/.temp/plans/search_plan_{drug_id}_{date}.md"`。这是本 workflow 唯一允许持久化的临时文件；不得在 drug 目录或其他位置创建临时文件，也不得用 `_2`、时间戳或随机后缀绕过路径碰撞。

写入前必须检查该确定性路径：

- 不存在：以本次 plan 创建。
- 已存在：视为未完成任务并续跑；读取旧 plan，以 canonical source 准确字符串为键合并本次搜索结果。保留旧行及其人工编辑，只追加新 canonical source，并对同一来源补齐空字段；不得截断、重建或覆盖旧 plan。
- 同一 canonical source 的非空字段冲突、一个来源出现多行而无法安全合并，或现有文件不是可识别的 plan：停止并列出歧义，交由人工处理。

canonical source 保持提取体系的准确值：URL 不改写大小写、查询参数、尾斜杠或编码；本地 PDF 使用 resolved absolute POSIX path。plan 内判重仅合并 plan 行；库内重复判定限定在当前药品，允许其他药品复用同一来源。

若 plan 表为空（无任何来源）：停下询问用户，不进入 Step 5。否则直接进入 Step 5。

## Step 5: 检查 plan 表进度并批量提取

### 5.1 运行进度检查脚本并检查索引维度

```text
python "{clinical_research_dir}/drug-build/scripts/check_plan_progress.py" --config "{clinical_research_dir}/config.yaml" --plan "{research_dir}/.temp/plans/search_plan_{drug_id}_{date}.md" --company-id "{company_id}" --drug-id "{drug_id}"
```

脚本按当前药品范围检查 raw/summary、完整审核门禁以及药品页、全部应建适应症页和根索引：

```text
plan 表进度：
- {url}: 已完成 / 已验证未索引 / 未提取 / 已提取未生成summary / 未审核 / 来源对应多个raw / 一个raw对应多个summary / summary文件名不匹配
```

脚本的 `已完成` 等于 fully indexed；`已验证未索引` 等于 verified-unindexed。由本 skill 按以下状态执行：

- **未提取**：当前 `raw_dir` 没有该 canonical source → multi-extractor 精确处理该项。
- **raw-only**：当前药品内唯一 raw、无 summary → batch-extractor 精确批处理该 raw，禁止扫描或处理其他项。
- **pending/failed audit**：raw/summary 唯一，但审核为 pending、failed 或不完整 → data-verify 精确审核该 summary；通过门禁后立即进入 clinical-indexer 部分模式，未通过则保留 plan。
- **verified-unindexed**：审核门禁已通过，但药品页、任一应建适应症页或根索引存在缺口 → clinical-indexer 以该 summary 的明确路径执行部分模式。
- **fully indexed**：审核门禁通过且上述全部索引维度完整 → 跳过。
- **ambiguity/manual**：仅指当前药品内多个 raw、一个 raw 对应多个 summary、字段/路径冲突、错误索引引用或无法唯一确定目标 → 不自动删除、覆盖或猜测，保留 plan 并报告人工处理。
- **数据完整性错误**：raw frontmatter、summary 来源链接或受管理索引结构损坏 → 停止自动恢复，保留 plan 并报告具体文件；不得按“未提取”重新抓取。

由于命令已传入 `company_id/drug_id`，其他药品下相同 canonical source 不参与匹配。`来源对应多个raw` 只表示当前药品树内异常。

### 5.2 展示待提取来源

根据 5.1 的状态输出，向用户展示所有需要自动恢复的行及其恢复动作：

- 必须以 markdown 表格形式**完整输出**到用户可见消息（不得只写概要或省略行）。

```text
本次将入库以下数据来源：
| # | 临床代码或NCT编号 | 适应症 | 临床阶段 | 来源类型 | 数据截止日 | 网址链接 | 备注 |
|---|------------------|--------|---------|---------|-----------|---------|------|
| ...（待自动恢复的行，完整列出；另附当前状态与恢复动作）... |

共 N 个来源待处理。将按当前状态自动恢复；如需增删来源可随时告知。
```

- **纯告知，不停顿**：展示后直接进入 5.3 提取。
- 全部行均 `fully indexed`：展示“本次无待恢复数据来源”，跳过 5.3，直接进入 Step 6。

### 5.3 按状态执行精确恢复

所有子 skill 均接收 Step 1 建立的**完整标准 identity/path context 原对象**，不得只摘取 `drug_id` 等部分字段，不得改名或重新解析路径。按状态分组执行：

- `未提取`：读取 `../multi-extractor/SKILL.md`，一次性传入这些 canonical source；其内部完成提取、验证和部分索引。
- `raw-only`：读取 `../batch-extractor/SKILL.md`，逐项传入唯一 raw 的绝对路径并明确“仅处理此准确 item”；不得用目录级扫描扩大范围。
- `pending/failed audit`：读取 `../data-verify/SKILL.md`，逐项传入唯一 summary 的绝对路径；只把通过完整审核门禁的项继续交给 clinical-indexer。
- `verified-unindexed`：读取 `../clinical-indexer/SKILL.md`，把明确 summary 绝对路径列表作为部分模式输入；不得扫描同目录或全库。
- `ambiguity/manual`：不自动执行恢复。
- `数据完整性错误`：不自动执行恢复；报告损坏文件并保留 plan。

收集每项的 raw/summary、审核门禁、药品页、逐适应症页和根索引结果。任何已有文件都不得因续跑而被覆盖；恢复动作必须从当前已持久化状态继续。

## Step 6: 复查完成情况

再次运行 Step 5.1 的绝对路径命令，并重新检查全部索引维度：

```text
- `未提取` → 重试一次 multi-extractor 精确项
- `raw-only` → 重试一次 batch-extractor 精确 item
- `pending/failed audit` → 重试一次 data-verify；通过后部分索引
- `verified-unindexed` → 重试一次 clinical-indexer 部分模式
- `ambiguity/manual` → 不重试，报告人工处理
- `数据完整性错误` → 不重试，报告损坏文件
- `fully indexed` → 该行完成
```

- 只有每一行均为 `fully indexed`，才删除绝对 plan 文件 `"{research_dir}/.temp/plans/search_plan_{drug_id}_{date}.md"` 并进入 Step 7。
- 仍有可自动恢复项时，先展示当前状态和对应恢复动作，再按该状态精确重试一次；不得把所有未完成行整体送回 multi-extractor。
- 第二轮后只要仍有任一非 `fully indexed` 行，保留原 plan 供下次按 canonical source 合并续跑。验证通过但任何索引维度缺失时也绝不删除 plan。

重跑前展示格式：

```text
第 2 轮复查：以下来源仍未完成，将按状态重试：
| ... 来源、状态、精确恢复动作 ... |

此前失败项：{列表}（将不再重试，记入最终报告）
```

## Step 7: 输出报告

```text
drug-build 完成：
- 药品: {drug_id} ({drug})
- 别名全集: {列表}
- 管线表: {drug_page}（CTG 试验 N 个）
- plan 表: 已删除（全部 fully indexed）/ "{research_dir}/.temp/plans/search_plan_{drug_id}_{date}.md"（未完成，保留 M 行）
- 提取: 成功 X 个 / 失败 Y 个 / 跳过 Z 个
- 验证: PASS/WARN/FAIL 汇总
- 索引: 药品页、逐适应症页与根 index.md 的完整性结果
- 人工复核项: （WARN 列表；如有）
- 失败项: （列表及原因；如有）
```

## 常见问题

### Q: 为什么不需要在 drug-build 里管理多链接并发？

只有 `未提取` 组的多链接提取与验证并发由 `multi-extractor` 内部处理（每轮 ≤5 个并发子 agent，OpenClaw 默认 `maxChildrenPerAgent=5`）。drug-build 负责按状态分组，并把 raw-only、pending/failed audit 和 verified-unindexed 精确派发到对应恢复 skill，不自行实现其内部并发。

### Q: 提取阶段未验证的 summary 已写入 summary/？

`clinical-indexer` 只接受完整通过审核门禁的 summary，未验证文件会被跳过。验证完成只代表可归档；还必须确认药品页、全部应建适应症页和根索引均已包含规范来源身份，才算建库完成。

### Q: 某行反复 FAIL 怎么办？

按该行持久状态恢复：未提取才调用 multi-extractor，raw-only 调 batch exact item，待审核调 data-verify，已验证未索引调 clinical-indexer partial。每行总尝试上限 2 次；之后保留 plan 并列入失败项，不覆盖已有产物。

### Q: 重复来源在静默模式下如何处理？

重复只在当前药品内按 canonical source 判断；其他药品可合法复用同一来源。当前药品内 `fully indexed` 的来源静默跳过，其他状态按恢复表续跑；只有配对、路径或索引目标不唯一时交由人工处理。
