---
name: multi-extractor
description: |
  临床数据提取编排（供 clinical-research 主 skill 调用）。
  
  当用户提到"提取临床数据"且提供 URL/PDF 时触发，作为提取唯一入口：
  - 单链接/单文件 → spawn 1 个 subagent 执行 clinical-extractor
  - 多链接/多文件 → 分批 spawn subagent 并行执行 clinical-extractor
  提取完成后编排 data-verify 验证与 clinical-indexer 归档。
---

# 临床数据提取 - 编排层

> 本文件由 clinical-research/SKILL.md 路由后读取执行，或由 drug-build 编排调用。
> 职责：提取临床数据并完成验证与索引。单来源处理单元在 `clinical-extractor`，本文件只负责编排，不重复实现提取细节。
> 审核独立性由 `data-verify` 子 skill 保证：提取方不得自行判定数据通过，必须由独立 verifier 子 agent 执行 data-verify。

## 执行原则

- 必须按主步骤顺序执行,不得跳过（Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6）。
- `raw/` 是原始采集层,只保存工具提取结果,不允许大模型改写、总结、翻译、重排、删减或补全正文。
- `summary/` 是结构化摘要层,按药品分子目录组织(`summary/{drug_id}/{drug_id}@{indication_id}@{source_label}.md`)；summary 直接保存到正式目录，审核章节由 data-verify 后补；后续来源不得覆盖已有快照。
- 具体文件格式只以 `../schema/summary-spec.md` 和 `../schema/drug-spec.md` 为准;本 workflow 不重复定义格式细节。
- 如果任一步失败,按该步骤的失败处理规则终止或回修,不得继续污染后续索引。
- 每轮并发子 agent 数 ≤ 5（OpenClaw 默认 `maxChildrenPerAgent=5`），一轮完成后若还有剩余继续下一轮。
- **上下文隔离**：提取、验证、索引均通过 spawn subagent 执行，主 agent 只保留编排状态（进度、路径、结果汇总），避免上下文过长导致中断。

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
- ../drug-identity/SKILL.md read: yes
- ../data-verify/SKILL.md read: yes
- ../clinical-indexer/SKILL.md read: yes
```

如果任一必读文件无法读取,必须停止并报告原因,不得提取、写入或自行猜测目录/格式。

## Step 1: 身份解析

**若调用方已提供身份对象**（drug_id、drug_aliases、target、companies、molecule_type）：

- 直接使用传入值，**跳过 drug-identity 调用**。
- 例如 drug-build 在 Step 1 已解析身份，调用本 skill 时附上身份对象。

**否则**（如根 SKILL.md 直接路由、用户直接要求提取）：

- 读取 `../drug-identity/SKILL.md`，按其中 workflow 执行（主 agent），获取该药品的标准身份对象：

```text
drug_id: {按固定优先级确定}
drug_aliases: {研发代号/合作方代号/商品名等全集}
target: {最简形式}
companies: {研发公司及合作方}
molecule_type: {ADC/双抗/单抗/小分子}
```

- 身份确认后 drug-identity 会自动创建/更新 `drug/{drug_id}.md` 骨架。
- 如果无法确认药物身份，停下返回用户确认，不进入后续步骤。

## Step 2: 来源预检

对本次全部来源（URL/PDF 列表）统一执行预检：

### 2.1 识别来源

从当前或上一条对话中提取来源列表：

- 单个 URL 或 PDF：单来源模式，进入 2.2。
- 多个 URL/PDF：多来源模式，全部列出，进入 2.2。
- 不包含 URL 或 PDF:要求用户补充来源,终止执行。

### 2.2 统一去重

扫描 `{raw_dir}` 下所有 `.md` 文件的 YAML frontmatter `source:` 字段，与本次来源对比：

```bash
grep -h "^source:" {raw_dir}/*.md | sed 's/source: *//' | tr -d '"' | sort -u
```

去重规则：

- **URL 精确匹配**：直接对比 URL 字符串。
- **近似重复**：同标题+同日期，或同一事件的多门户发布（如 news.bms.com ↔ investors.biontech.de 同日同内容），识别为重复，只保留一个。
- **本次来源之间重复**：只保留一个，其余标记跳过。

重复来源处理：

- **单来源**：向用户询问（[1]跳过 / [2]重新提取并覆盖旧文件——级联删除旧 raw + 关联 summary 后重提）。
- **多来源（静默模式）**：重复来源一律跳过，不询问、不重新提取。

### 2.3 URL 可达性探测

对每个待提取 URL 做轻量可达性探测（HEAD 请求或 basic fetch）：

- 404/403/连接失败 → 立即标记为失败项（尝试找同文镜像，找不到则剔除），不进入提取队列。
- PDF 来源先 `pdftotext` 试提取 → 空输出（纯图片 PDF）提前标记，避免 subagent 白跑。

### 2.4 分配来源身份

为每个待提取来源分配：

- `raw_filename`（raw 基础名，确保本次来源间唯一）
- `source_label`（如 `ASCO2026`；本次来源间冲突时追加最短必要后缀 `_2`、`_3`，确保唯一）
- `indication_id`：按 `indication-spec.md` 的规范命名对每个来源的适应症统一规范化（如 `NSCLC 1L` → `NSCLC_1L`），确保多 subagent 结果一致；治疗线无法判断时保留 `line: null`，不得猜测为 1L
- 注明"本源主适应症"展示名（多适应症源时），供提取单元生成主/次 summary 参考

## Step 3: 并行提取

对预检后待提取的来源列表执行提取：

```text
- 多来源：每轮 spawn ≤5 个提取子 agent，每个子 agent 处理 1 个来源，
  读取并执行 clinical-extractor/SKILL.md
- 单来源：spawn 1 个提取子 agent 执行 clinical-extractor/SKILL.md
- 一轮完成后若还有剩余来源，开始下一轮
```

每个提取子 agent 的 prompt 必须包含（**注入完整上下文，子 agent 不重读 config/schema**）：

```text
读取 clinical-extractor/SKILL.md，处理以下单个来源：
{URL 或 PDF}

身份与命名参数（直接使用，不自行解析）：
- drug_id: {值}
- drug_aliases: {别名列表}
- target: {值}
- indication_id: {规范化值}
- 本源主适应症展示名: {值}（若含次要适应症也生成对应 summary，indication_id 按规范命名）
- raw_filename: {值}
- source_label: {值}

目录与格式（无需重新读取文件）：
- config.yaml 路径: ../config.yaml
- raw_dir: {raw_dir}
- summary_dir: {summary_dir}
- summary frontmatter 模板与命名格式、SUMMARY WRITE GATE 见 summary-spec.md（若需确认格式可读取该文件）

返回：来源、raw/ 路径、summary/ 路径列表、结果（成功/失败/跳过/发现重复）、失败原因
```

处理规则：

- 子 agent 返回"发现重复"：由主 agent 按 Step 2.2 处理。
- **失败重试**：某个来源失败（提取失败、空内容、非临床资料、超时）→ **立即带原因重试一次**；重试提示词附"上次失败原因 + 建议（换镜像/换提取方式）"。重试仍失败 → 记录失败项，不影响其他来源。
- **超时控制**：子 agent 单任务超时 12-15 分钟，超时自动 kill 并重试一次。
- 全部来源处理完毕后，汇总全部 summary 路径列表，进入 Step 4。
- **进度汇报**：每批完成时主动向用户汇报一次（"第 X/Y 批完成，N 成功 M 失败"）；失败项发现即说明处理方案，不等最终报告。

## Step 4: 并行验证

### 4.1 筛选待验证 summary

使用 **Step 3 汇总的本次 summary 路径列表**（不扫描全目录，避免误审其他药物的 summary），筛选出**未审核**的（frontmatter `verification` 非 `passed` 或缺失）：

得到待验证 summary 列表。

### 4.2 分批并行验证

```text
- 每轮 spawn ≤5 个 verifier 子 agent
- 每个 verifier 负责一批 summary（建议每批 2-3 个，按 4.1 扫描结果分配）
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
2. 每个 summary 必须由独立的 data verifier 子 agent 执行 data-verify workflow（提取方不得自行替代审核）。
3. 审核失败处理：
   - 存在 `FAIL`：主 agent 按 verifier 输出的问题修正对应 summary 正文（数据错误处），然后**只重新 spawn verifier 验证该 FAIL 的 summary**，已通过的 summary 不重跑。重复 FAIL 2 次 → 记入失败项报告人工处理。
   - 存在 `WARN`：可以继续，但必须在最终返回报告中列出 WARN 项，提示用户人工复核。

## Step 5: 调用 clinical-indexer

spawn 1 个 agent 执行增量归档：

```text
读取 clinical-indexer/SKILL.md，按其中增量归档 workflow 执行：
- 扫描全部 summary/，按身份字段计算期望页面并补齐 drug/ 与 indication/
- 返回归档统计
```

- 若 indexer 归档失败，报告 `summary/` 已生成但索引未更新；不回滚已写入的 `summary/` 文件。

## Step 6: 输出报告

```text
- 待提取来源: N 个（跳过 X 个 / 失败 Y 个）
- raw/ 文件路径列表
- summary/ 文件路径列表
- 数据一致性审核结果（PASS/WARN/FAIL 汇总；如有 WARN 列出人工复核项）
- indexer 归档结果
- 失败项: （列表及原因；如有）
- 提取的关键数据摘要
```

## 常见问题

### Q: 单链接也要 spawn 吗？

要。spawn 可以隔离上下文——提取任务 token 消耗大（40k-150k/任务），主 agent 亲自执行会导致上下文过长中断。单链接同样 spawn 1 个 subagent。

### Q: 验证和索引为什么也要 spawn？

同理，都是为了主 agent 上下文隔离。主 agent 只保留编排状态（进度、路径、结果汇总）。

### Q: 失败重试多少次？

提取失败：立即带原因重试一次，仍失败则记录失败项。验证 FAIL：修正后重验一次，重复 FAIL 2 次记入失败项。drug-build 流程末尾会对 plan 表未完成行整体重跑一次 multi-extractor；每行总尝试上限 2 次，之后不再重试。

### Q: 如何避免子 agent 重复读 schema 浪费时间？

派发 prompt 已注入身份参数、目录路径、格式要点；子 agent 无需重读 config。summary-spec 仅在生成 summary 需要确认格式细节时读取。
