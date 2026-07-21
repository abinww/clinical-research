---
name: clinical-data-indexer
  临床索引增量归档执行步骤（供clinical-research主skill调用）

  当主skill路由到本文件时，按以下步骤执行：
---

# 临床索引增量归档

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 本 workflow 面向手动或 cron 定时运行，只按来源链接存在性查漏补缺。

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

两种调用都遵守相同的幂等规则：已有 `> 来源: [[summary/...]]` 链接的 summary 跳过，没有链接的才归档。

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
summary/{药品名}/{文件名}.md
```

对每个 summary 读取：

- YAML：`drug`、`drug_aliases`、`indication`、`companies`、`phase`、`trial_name`、`conference`、`created`
- 正文：`> 来源原文: [[raw/...]]` 行
- 临床有效性和安全性数据表

缺少 `drug` 或 `indication` 的 summary 记录警告，不纳入对应维度的本轮更新；不要修改该 summary。

## Step 3: 计算 drug 归档缺口

扫描 `drug_dir` 根目录下所有药品索引文件，提取所有来源链接：

```text
> 来源: [[summary/{药品}/{文件}.md]]
```

将目标路径规范化并去重，得到：

```text
organized_for_drug
```

计算：

```text
missing_from_drug = all_summaries - organized_for_drug
```

只要 summary 路径已经出现在任一 `drug/*.md` 的 `> 来源:` 行中，就视为 drug 维度已归档。

## Step 4: 计算 indication 归档缺口

扫描 `indication_dir` 根目录下所有适应症索引文件，提取所有来源链接：

```text
> 来源: [[summary/{药品}/{文件}.md]]
```

将目标路径规范化并去重，得到：

```text
organized_for_indication
```

计算：

```text
missing_from_indication = all_summaries - organized_for_indication
```

只要 summary 路径已经出现在任一 `indication/*.md` 的 `> 来源:` 行中，就视为 indication 维度已归档。

## Step 5: 更新 drug 索引

如果 `missing_from_drug` 为空：

- 不读取或修改任何 drug 索引文件。

否则：

1. 按 summary 的 `drug` 字段分组。
2. 按 `drug-spec.md` 的药品名称优先级确定 `drug/{药品名}.md`。
3. 文件不存在时，按 `drug-spec.md` 创建完整药品索引。
4. 文件存在时，只追加本轮缺失 summary 对应的适应症、临床数据、关键里程碑和来源链接。
5. 保留已有内容和人工补充。
6. 写入前再次确认来源链接未存在，确保重复运行不会重复追加。
7. 某个药品写入失败时记录错误，继续处理其他药品。

单个 summary 已归档到 drug/，但仍未归档到 indication/ 时，不因 drug 已归档而跳过 indication 维度。

## Step 6: 更新 indication 索引

如果 `missing_from_indication` 为空：

- 不读取或修改任何 indication 索引文件。

否则：

1. 按 summary 的 `indication` 字段分组。
2. 按 `indication-spec.md` 的命名规则确定 `indication/{适应症名}.md`。
3. 文件不存在时，按 `indication-spec.md` 创建完整适应症索引。
4. 文件存在时，只追加本轮缺失 summary 对应的药品数据和来源链接。
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
