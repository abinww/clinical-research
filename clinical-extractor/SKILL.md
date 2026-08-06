---
name: clinical-extractor
description: |
  临床数据提取编排执行步骤（供clinical-research主skill调用）
  
  当主skill路由到本文件时，按以下步骤执行：
---

# 临床数据提取 - 编排层

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 总流程：来源预检 → 并行提取（extract-one.md）→ data-verify 验证 → clinical-indexer 归档。
> 单来源处理单元在 `extract-one.md`，本文件只负责编排，不重复实现提取细节。

## 执行原则

- 必须按主步骤顺序执行,不得跳过（Step 1 → Step 2 → Step 3 → Step 4 → Step 5）。
- `raw/` 是原始采集层,只保存工具提取结果,不允许大模型改写、总结、翻译、重排、删减或补全正文。
- `summary/` 是结构化摘要层,按药品分子目录组织(`summary/{drug_id}/{drug_id}@{indication_id}@{source_label}.md`)；summary 直接保存到正式目录，审核章节由 data-verify 后补；后续来源不得覆盖已有快照。
- 具体文件格式只以 `../schema/summary-spec.md` 和 `../schema/drug-spec.md` 为准;本 workflow 不重复定义格式细节。
- 如果任一步失败,按该步骤的失败处理规则终止或回修,不得继续污染后续索引。
- 审核独立性由 `data-verify` 子 skill 保证：提取方不得自行判定数据通过，必须由独立 verifier 子 agent 执行 data-verify。
- 多来源并行：每轮并发子 agent 数 ≤ 5（OpenClaw 默认 `maxChildrenPerAgent=5`），一轮完成后若还有剩余继续下一轮。

## 执行门禁

处理任何 URL/PDF 前,必须完成并确认:

```text
EXTRACTOR PREFLIGHT:
- ../config.yaml read: yes
- raw_dir:
- summary_dir:
- drug_dir:
- ../schema/summary-spec.md read: yes
- ../schema/drug-spec.md read: yes
- ../data-verify/SKILL.md read: yes
- ../clinical-indexer/SKILL.md read: yes
```

如果任一必读文件无法读取,必须停止并报告原因,不得提取、写入或自行猜测目录/格式。

## Step 1: 来源预检

主 agent 对本次全部来源（URL/PDF 列表）统一执行预检：

### 1.1 识别来源

从当前或上一条对话中提取来源列表：

- 单个 URL 或 PDF：进入 1.2。
- 多个 URL/PDF：全部列出，进入 1.2。
- 不包含 URL 或 PDF:要求用户补充来源,终止执行。

### 1.2 统一去重

扫描 `{raw_dir}` 下所有 `.md` 文件的 YAML frontmatter `source:` 字段，与本次来源对比：

- URL 来源：直接对比 URL 字符串
- PDF 来源：对比 PDF 文件名

```bash
grep -h "^source:" {raw_dir}/*.md | sed 's/source: *//' | tr -d '"' | sort -u
```

标记两类重复：

- **与已有 raw 重复的来源**：按 1.3 处理。
- **本次来源之间重复的来源**：只保留一个，其余标记跳过。

### 1.3 重复来源处理

按来源数量分流：

**单来源**：向用户询问：

```text
检测到该来源已提取过：
- 来源: {URL 或 PDF 文件名}
- 已有 raw 文件: {raw_dir}/{raw_filename}.md

请选择：
[1] 跳过（保留已有文件，不再处理）
[2] 重新提取并覆盖旧文件（删除旧 raw + 关联的 summary 文件，再执行 Step 2 提取）
```

- 选项 [1]：该来源标记为跳过，不再提取。
- 选项 [2]：级联删除：
  1. 查找指向该 raw 的 summary 文件（遍历 `{summary_dir}` 下 `.md` 文件，匹配 `> 来源原文: [[raw/{raw 文件名}]]` 行）。
  2. 删除已匹配的 summary 文件。
  3. 删除当前 raw 文件。
  4. 该来源保留为待提取。

**多来源（静默模式）**：重复来源**一律跳过**，不询问用户、不重新提取。修复不依赖本步骤。

**关于 drug 索引的说明**：

- 若重新提取后 summary 文件名与旧文件相同，indexer 归档时会按来源链接幂等合并，不重复追加。
- 若文件名发生变化，drug 索引中旧的 `> 来源:` 行会指向已删除的 summary 文件，成为断链；断链由 `clinical-indexer` 清理或用户人工处理。

### 1.4 分配来源身份

为每个待提取来源分配：

- `raw_filename`（raw 基础名，确保本次来源间唯一）
- `source_label`（如 `ASCO2026`；本次来源间冲突时追加最短必要后缀 `_2`、`_3`，确保唯一）

`drug_id` 与 `indication_id` 不在本步骤分配，由每个提取子 agent 在 extract-one.md 中按固定优先级规则自行确定（固定规则保证任何 subagent 结果一致）。

## Step 2: 并行提取

对预检后待提取的来源列表执行提取：

```text
- 多来源：每轮 spawn ≤5 个提取子 agent，每个子 agent 处理 1 个来源，
  读取并执行 extract-one.md（使用 Step 1.4 分配的 raw_filename / source_label）
- 单来源：spawn 1 个提取子 agent 执行 extract-one.md
- 一轮完成后若还有剩余来源，开始下一轮
- 降级：当前环境无法 spawn 子 agent 时，主 agent 顺序执行 extract-one.md
  （逐个来源处理，效果相同）
```

每个提取子 agent 的 prompt 必须包含：

```text
读取 clinical-extractor/extract-one.md，处理以下单个来源：
{URL 或 PDF}
- 使用已分配的 raw_filename: {值}，source_label: {值}
- 按 extract-one.md 的 Step 1-3 执行
- 返回：来源、raw/ 路径、summary/ 路径、结果（成功/失败/跳过/发现重复）、失败原因
```

处理规则：

- 子 agent 返回"发现重复"：由主 agent 按 Step 1.3 处理（询问用户或跳过）。
- 某个来源失败（提取失败、空内容、非临床资料）：记录失败项，不影响其他来源继续处理。
- 全部来源处理完毕后，汇总全部 summary 路径列表，进入 Step 3。

## Step 3: 调用 data-verify 验证

对 Step 2 汇总的全部 summary 执行审核：

```text
- 按批并行 spawn verifier 子 agent（每轮 ≤5 个并发）
- 每个 verifier 负责一批 summary（建议每批 2-3 个）
- 一轮完成后若还有剩余 summary，开始下一轮
```

每个 verifier 的 prompt 必须包含：

```text
按 data-verify/SKILL.md 验证以下 summary 列表（每个 summary 独立审核）：
{批次内的 summary 路径列表}
对每个 summary：读取其 `> 来源原文:` 指向的 raw 文件，写入审核章节
与 verification 字段；返回每个 summary 的 PASS/WARN/FAIL 数量
```

规则：

1. 读取 `../data-verify/SKILL.md`，按其中 workflow 执行。
2. 每个 summary 必须由独立的 data verifier 子 agent 执行 data-verify workflow（提取方不得自行替代审核）：
   - 输入：该 summary 文件 + 对应 raw 文件
   - 由 verifier 子 agent 将审核结果写入 summary 末尾的 `## 数据一致性审核` 章节，并更新 YAML 的 `verification` / `verification_fail_count` 字段
3. 如果当前环境无法 spawn data verifier 子 agent，必须停止并报告无法满足审核要求；不得由主 agent 自行替代审核。
4. 审核失败处理：
   - 存在 `FAIL`：按 verifier 输出的问题修正对应 summary 正文（数据错误处），然后**只重新 spawn verifier 验证该 FAIL 的 summary**，已通过的 summary 不重跑。
   - 存在 `WARN`：可以继续，但必须在最终返回报告中列出 WARN 项，提示用户人工复核。
   - 全部通过：`verification: passed` / `verification_fail_count: 0` 由 verifier 写入，进入 Step 4。

## Step 4: 调用 clinical-indexer

目标:把本次通过的 summary 归档到 drug/ 与 indication/ 索引。

1. 读取 `../clinical-indexer/SKILL.md`，按其中增量归档 workflow 执行。
2. indexer 扫描全部 `summary/`，按身份字段计算期望页面并补齐 `drug/` 与 `indication/`，天然支持本次处理的多个 summary。
3. 若 indexer 归档失败，报告 `summary/` 已生成但索引未更新；不回滚已写入的 `summary/` 文件。

## Step 5: 返回汇总报告

```text
- 待提取来源: N 个（跳过 X 个 / 重新提取 Y 个）
- raw/ 文件路径列表
- summary/ 文件路径列表
- 数据一致性审核结果（PASS/WARN/FAIL 汇总；如有 WARN 列出人工复核项）
- indexer 归档结果
- 失败项: （列表及原因；如有）
- 提取的关键数据摘要
```
