---
name: clinical-indexer
description: |
  定时或手动扫描全部 summary，分别查漏补缺 drug/ 和 indication/ 索引。
---

# 临床索引增量归档

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 本 workflow 面向手动或 cron 定时运行，按 summary 身份字段计算期望页面，再检查来源链接是否存在。

## 调用接口

本 skill 支持两种调用方式，执行同一套增量归档 workflow。

### 用户请求调用

由 `clinical-research/SKILL.md` 根据用户请求路由到本文件。适用请求包括：

- 归档临床数据
- 整理临床数据
- 扫描未整理的临床数据
- 同步临床数据到索引
- 更新药品索引
- 更新适应症索引

通过根 skill 调用时，根 skill 负责初始化检查、读取配置和输出 `PREFLIGHT`；本文件从 Step 1 开始执行增量归档。

### Cron 直接调用

Cron 可以直接读取并执行本文件，不需要重新读取或经过根 `clinical-research/SKILL.md` 路由。

Cron 直接调用时必须：

- 从本文件 Step 1 开始执行
- 自行读取 `../config.yaml`
- 自行读取 `../schema/drug-spec.md` 和 `../schema/indication-spec.md`
- 执行完整的 drug/ 与 indication/ 双维度增量归档
- 不等待用户确认
- 记录失败项并继续处理其他可处理项目
- 最后返回完整归档统计

Cron 调用提示词应明确要求直接执行本文件，不要只发送“更新索引”等模糊指令。

两种调用都遵守相同的幂等规则：只有当 summary 来源链接已存在于按身份字段计算出的期望 drug 页面和期望 indication 页面时，该维度才跳过；链接出现在其他页面不算已归档。

## 定位与约束

- 每次扫描全部 `summary/`，分别检查 summary 是否已归档到 `drug/` 和 `indication/`。
- `drug/` 和 `indication/` 两个归档维度独立计算、独立更新。
- 只处理目标维度缺失来源链接的 summary；已归档内容不重复追加。
- 不比较 summary 修改时间、内容 hash 或索引更新时间。
- 不修改 `summary/` 原始摘要。
- 不执行单药模式、全量重建或破坏性删除。
- 不默认生成或更新 `summary/INDEX.md`。
- 所有输出格式必须遵守 `../schema/drug-spec.md` 和 `../schema/indication-spec.md`；本 workflow 不重复定义 Markdown 格式。

如果一个维度写入失败，记录失败并继续处理其他药品和另一个维度；最终报告必须列出失败项。

## Step 1: 读取配置和格式规范

读取 `../config.yaml`，获取：

- `summary_dir`
- `drug_dir`
- `indication_dir`

读取：

- `../schema/drug-spec.md`
- `../schema/indication-spec.md`

如果任一文件或目录配置无法读取，停止执行并报告原因。

## Step 2: 扫描全部 summary

扫描各药品子目录下的摘要文件：

```bash
find ${summary_dir} -mindepth 2 -name "*.md" -type f
```

跳过 `summary_dir/INDEX.md` 等顶层文件。每个 summary 的唯一标识是相对于数据根目录的路径：

```text
summary/{drug_id}/{文件名}.md
```

对每个 summary 读取：

- YAML：`drug_id`、`drug`、`drug_aliases`、`indication_id`、`indication`、`source_label`、`source_type`、`published_date`、`combination_regimen`、`clinical_match_key`、`companies`、`phase`、`trial_name`、`conference`、`created`、`verification`、`verification_fail_count`
- 正文：`> 来源原文: [[raw/...]]` 行
- 临床有效性和安全性数据表

只接受同时满足下列条件的 summary：

- `drug_id`、`indication_id` 存在
- `verification: passed`

不满足任一条件时记录跳过原因，不纳入 drug 或 indication 的本轮更新；不要修改该 summary。

说明：

- `verification: passed` 已隐含审核章节存在与 FAIL=0（data-verify 仅在两者满足时写入 passed），不再单独检查。
- `clinical_match_key` 缺失时，drug 页按"独立追加记录"降级处理（不执行合并），不阻塞归档。
- 其他身份字段（source_label 等）从文件名或正文读取，不参与资格检查。

## Step 3: 计算 drug 归档缺口

递归扫描 `drug_dir` 下所有药品索引文件（包括子文件夹），按 frontmatter `drug_id` 建立映射：

```bash
find ${drug_dir} -name "*.md" -type f
```

```text
drug_id -> drug 文件路径
```

提取所有来源链接：

```text
> 来源: [[summary/{drug_id}/{文件}.md]]
```

对每个合格 summary，按 `drug_id` 在映射中查找期望目标：

```text
expected_drug_page = 映射中 drug_id 对应的文件路径
```

仅检查该期望 drug 页面中的 `> 来源:` 行是否包含该 summary 路径：

```text
missing_from_drug = summaries whose path is absent from expected_drug_page
```

同一 summary 若出现在其他 drug 页面，记录为来源链接完整性错误；不能视为已归档到期望 drug 页面。

## Step 4: 计算 indication 归档缺口

扫描 `indication_dir` 根目录下所有适应症索引文件，提取所有来源链接：

```text
> 来源: [[summary/{drug_id}/{文件}.md]]
```

对每个合格 summary，按 `indication_id` 计算期望目标：

```text
expected_indication_page = indication/{indication_id}.md
```

仅检查该期望 indication 页面中的 `> 来源:` 行是否包含该 summary 路径：

```text
missing_from_indication = summaries whose path is absent from expected_indication_page
```

同一 summary 若出现在其他 indication 页面，记录为来源链接完整性错误；不能视为已归档到期望 indication 页面。

## Step 5: 更新 drug 索引

如果 `missing_from_drug` 为空：

- 不读取或修改任何 drug 索引文件。

否则：

1. 按 summary 的 `drug_id` 字段分组。
2. 使用 Step 3 映射中 `drug_id` 对应的文件路径作为唯一目标文件；映射中不存在时按 `drug-spec.md` 创建新文件。
3. 文件不存在时，按 `drug-spec.md` 创建完整药品索引。
4. 文件存在时，按 `clinical_match_key` 合并本轮 summary：匹配时补充新增指标、分组、样本量和随访，不新增重复临床记录；不匹配时追加独立记录。
5. 保留已有内容和人工补充。
6. 同一字段数值冲突时不得静默覆盖；并列保留不同值、各自来源和“数据差异待人工确认”标记。
7. 无论是否合并，都保留所有 summary 来源链接；写入前再次确认当前来源链接未存在，确保重复运行不会重复追加。
8. 某个药品写入失败时记录错误，继续处理其他药品。

单个 summary 已归档到 drug/，但仍未归档到 indication/ 时，不因 drug 已归档而跳过 indication 维度。

## Step 6: 更新 indication 索引

如果 `missing_from_indication` 为空：

- 不读取或修改任何 indication 索引文件。

否则：

1. 按 summary 的 `indication_id` 字段分组。
2. 使用 `indication/{indication_id}.md` 作为唯一目标文件。
3. 文件不存在时，按 `indication-spec.md` 创建完整适应症索引。
4. 文件存在时，按 summary 的 `indication_id` 归档药品数据和来源链接；不删除旧来源。
5. 保留已有内容和人工补充。
6. 写入前再次确认来源链接未存在，确保重复运行不会重复追加。
7. 某个适应症写入失败时记录错误，继续处理其他适应症。

## Step 7: 输出报告

输出：

```text
clinical-indexer 增量归档完成：

扫描 summary: N 个

drug 归档：
- 已归档: A 个
- 待归档: B 个
- 新建药品页: C 个
- 更新药品页: D 个
- 失败: E 个

indication 归档：
- 已归档: F 个
- 待归档: G 个
- 新建适应症页: H 个
- 更新适应症页: I 个
- 失败: J 个

无变化: yes / no
```

当两个缺口都为空时，必须报告 `无变化: yes`，且不得写入任何 drug/indication 文件。
