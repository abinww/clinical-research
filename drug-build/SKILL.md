---
name: drug-build
description: |
  创新药数据库建库编排。当用户提到以下关键词时触发：
  - "对{药品}建库"
  - "建库"
  本 skill 编排 drug-trials-search、data-search、multi-extractor 完成完整建库。多链接的提取、验证与索引归档由 multi-extractor 内部处理。
---

# 创新药建库编排

## 责任与边界

- 由 `clinical-research/SKILL.md` 路由后执行，为指定创新药编排身份锚定、临床管线、数据搜索、提取、验证和完整索引归档。
- 固定顺序为：身份锚定 → 管线 → 可续跑 plan → 按状态恢复 → 复查全部索引维度。
- 不重复实现子 skill 内部逻辑；读取并执行对应 `SKILL.md`。除非用户明确要求，不跳步。
- 多链接提取、验证与索引由 `multi-extractor` 内部处理，每轮最多 5 个并发子 agent（OpenClaw 默认 `maxChildrenPerAgent=5`）；本 skill 只按状态分组和精确派发。
- 静默执行；仅在身份无法确认、plan 为空或出现歧义等问题时停下。待恢复来源表按流程要求纯告知，不等待确认。

## 输入与共享契约

第 1 步必须以 `mode: resolve_or_create` 调用 `../drug-identity/SKILL.md`，取得其定义的完整标准 identity/path context。后续子 skill 必须原样接收整个对象及绝对 `config_path`；不得摘取部分字段、删字段、改名或重算路径。兼容字段 `companies` 如存在，必须与 `company_ids` 相同。

plan 文件名格式为：

```text
"{research_dir}/.temp/plans/search_plan_{drug_id}_{date}.md"
```

canonical source 保持提取体系的准确值：URL 不改写大小写、查询参数、尾斜杠或编码；本地 PDF 使用 resolved absolute POSIX path。plan 内按 canonical source 准确字符串合并；库内判重只限当前 `drug_id`，其他药品可合法复用同一来源。

开始本次建库前，先扫描 `.temp/plans/search_plan_{drug_id}_*.md`：恰有一个未完成 plan 时继续使用其绝对路径；多个匹配时停止并请用户选择；没有匹配时才创建当天路径。下文 `{plan_path}` 指最终选定的绝对路径。

进度检查必须使用以下绝对路径命令，不得改变：

```text
python "{clinical_research_dir}/drug-build/scripts/check_plan_progress.py" --config "{clinical_research_dir}/config.yaml" --plan "{plan_path}" --company-id "{company_id}" --drug-id "{drug_id}"
```

## 不变量与写入策略

- `已完成` 等于 fully indexed：raw/summary、完整审核门禁、药品页、全部应建适应症页和根索引均完整。只有全部 plan 行 `fully indexed` 才删除 plan。
- 当前药品内已完整索引的重复来源静默跳过；其他药品中的相同来源不参与匹配，也不构成歧义。
- 续跑从当前持久状态恢复，不覆盖已有产物，不把未完成项整体重新提取。
- 可自动恢复的单项按当前状态重试一次，每项总尝试上限 2 次；第二轮后仍失败则保留 plan 并报告。
- 身份、当前药品内来源配对、路径或索引目标存在歧义时，停止该项自动恢复，不删除、覆盖或猜测。

以下是唯一规范的状态 → 动作 → 重试策略；流程第 5、6 步均引用此表：

| 脚本状态 | 规范状态 | 判定 | 精确动作 | 第 2 轮重试 |
|---|---|---|---|---|
| `未提取` | `unextracted` | 当前 `raw_dir` 无该 canonical source | `multi-extractor` 一次性处理该组 canonical source；内部完成提取、验证和部分索引 | 同动作精确重试一次 |
| `已提取未生成summary` | `raw-only` | 当前药品内唯一 raw、无 summary | `batch-extractor` 使用 `single_raw` 模式接收唯一 raw 绝对路径；禁止目录扫描 | 同动作精确重试一次 |
| `未审核` 或审核 pending/failed/incomplete | `pending/failed audit` | raw/summary 唯一，但未通过完整审核门禁 | `data-verify` 逐项接收唯一 summary 绝对路径；通过后立即交 `clinical-indexer` 部分模式，未通过则保留 plan | 同动作精确重试一次；通过后部分索引 |
| `已验证未索引` | `verified-unindexed` | 审核通过，但药品页、任一应建适应症页或根索引有缺口 | `clinical-indexer` 接收明确 summary 绝对路径列表执行部分模式；不得扩展扫描 | 同动作精确重试一次 |
| `已完成` | `fully indexed` | 审核和全部索引维度完整 | 跳过 | 不重试，完成 |
| `来源对应多个raw`、`一个raw对应多个summary`、`summary文件名不匹配`，或字段/路径冲突、错误索引引用、目标不唯一 | `ambiguity/manual` | 仅指当前药品树内歧义 | 不自动恢复；保留 plan，报告人工处理 | 不重试 |
| raw frontmatter、summary 来源链接或 managed 索引结构损坏 | `数据完整性错误` | 持久数据结构损坏 | 停止自动恢复；报告具体文件并保留 plan，禁止按“未提取”重抓 | 不重试 |

命令已传入 `company_id/drug_id`，因此 `来源对应多个raw` 只表示当前药品树异常。

## 流程

### 1. 锚定药品身份

按输入契约执行 `../drug-identity/SKILL.md`。无法确认身份时停下，请用户确认，不进入后续步骤。

### 2. 查询临床试验注册

读取 `../drug-trials-search/SKILL.md` 并执行其 workflow：查询该药品在 ClinicalTrials.gov 的全部试验，写入 identity 对象中 `drug_page` 的 `## 当前临床管线`；不创建 `trials/` 目录或独立 trial 搜索输出文件。

### 3. 搜索已公布临床数据

读取 `../data-search/SKILL.md` 并执行其 workflow：分层搜索注册库、公司渠道、学术会议、期刊和媒体线索，完成内容判断与去重，输出 plan 表。

### 4. 合并或保存可续跑 plan

按输入契约先确定 `{plan_path}`，再检查该路径：

1. 不存在时，用本次 plan 创建。
2. 已存在时视为未完成任务并续跑。读取旧 plan，以 canonical source 为键合并；保留旧行及人工编辑，只追加新来源，并为同一来源补齐空字段。不得截断、重建、覆盖，或用 `_2`、时间戳、随机后缀绕过碰撞。
3. 同一来源的非空字段冲突、一个来源有多行且无法安全合并，或文件不是可识别 plan 时，停止并列出歧义，交人工处理。

plan 无任何来源时停下询问，不进入第 5 步；否则继续。

### 5. 检查进度并精确恢复

#### 5.1 检查

运行输入契约中的绝对命令。脚本按当前药品检查 raw/summary、完整审核门禁、药品页、全部应建适应症页和根索引，并输出：

```text
plan 表进度：
- {url}: 已完成 / 已验证未索引 / 未提取 / 已提取未生成summary / 未审核 / 来源对应多个raw / 一个raw对应多个summary / summary文件名不匹配
```

#### 5.2 告知待恢复来源

按规范状态表列出所有需自动恢复的行及动作，必须完整输出为用户可见 Markdown 表格，不得只给概要或省略行：

```text
本次将入库以下数据来源：
| # | 临床代码或NCT编号 | 适应症 | 临床阶段 | 来源类型 | 数据截止日 | 网址链接 | 备注 |
|---|------------------|--------|---------|---------|-----------|---------|------|
| ...（待自动恢复的行，完整列出；另附当前状态与恢复动作）... |

共 N 个来源待处理。将按当前状态自动恢复；如需增删来源可随时告知。
```

这是纯告知，输出后不暂停。全部行均 `fully indexed` 时展示“本次无待恢复数据来源”，跳过恢复并进入第 6 步。

#### 5.3 恢复

按唯一规范状态表分组执行精确动作。所有子 skill 接收完整 identity/path context 原对象。收集每项 raw/summary、审核门禁、药品页、逐适应症页和根索引结果；任何已有文件不得因续跑被覆盖。

### 6. 复查与单次重试

再次运行第 5.1 节的同一绝对路径命令，并重新检查全部索引维度。仍可自动恢复的项先展示当前状态及规范表中的动作，再按该表“第 2 轮重试”列精确重试一次；不得把所有未完成行整体送回 `multi-extractor`。

```text
第 2 轮复查：以下来源仍未完成，将按状态重试：
| ... 来源、状态、精确恢复动作 ... |
此前失败项：{列表}（将不再重试，记入最终报告）
```

只有每行均为 `fully indexed`，才删除绝对 plan 文件 `"{plan_path}"` 并进入第 7 步。第二轮后任一行仍未完成，保留原 plan，供下次按 canonical source 合并续跑；验证通过但任一索引维度缺失时也不得删除。

### 7. 汇总

汇总身份、管线、plan、提取、审核、全部索引维度、人工复核和失败项，按输出契约返回。

## 失败与恢复

- 身份无法确认：停下询问，不继续。
- plan 为空：停下询问，不执行提取。
- plan 合并、来源配对、路径或索引目标有歧义：保留文件和产物，列出冲突，交人工处理。
- 数据完整性错误：保留 plan，报告损坏文件，不以重新抓取掩盖损坏。
- 自动恢复第二次仍失败：不覆盖已有产物，不再重试；保留 plan 并写入最终失败项。
- 下次运行读取确定性 plan，以 canonical source 合并最新搜索结果，再从脚本报告的持久状态继续。

## 输出

```text
drug-build 完成：
- 药品: {drug_id} ({drug})
- 别名全集: {列表}
- 管线表: {drug_page}（CTG 试验 N 个）
- plan 表: 已删除（全部 fully indexed）/ "{plan_path}"（未完成，保留 M 行）
- 提取: 成功 X 个 / 失败 Y 个 / 跳过 Z 个
- 验证: PASS/WARN/FAIL 汇总
- 索引: 药品页、逐适应症页与根 index.md 的完整性结果
- 人工复核项: （WARN 列表；如有）
- 失败项: （列表及原因；如有）
```
