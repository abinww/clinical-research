---
name: clinical-data-indexer
description: |
  索引更新执行步骤（供clinical-research主skill调用）
  
  当主skill路由到本文件时，按以下步骤执行：
---

# 索引更新 - 执行步骤

> 本文件由 clinical-research/SKILL.md 路由后读取执行
> 所有工具调用在当前session完成

## Configuration

读取 `../config.yaml` 获取数据目录路径：
- `source_dir`: 规范摘要目录
- `drug_dir`: 药品索引保存目录
- `indication_dir`: 适应症索引保存目录

## Step 1: 扫描 {source_dir} 目录

列出所有 `.md` 文件

## Step 2: 解析 frontmatter

对每个文件提取 YAML 字段：
- `drug`: 药品通用名
- `drug_aliases`: 别名列表
- `indication`: 适应症名称
- `companies`: 公司列表
- `phase`: 临床阶段
- `conference`: 会议名称
- `trial_name`: 试验名称
- `source_raw`: 关联的 raw 文件
- `source_date`: 数据日期
- `status`: 数据状态（空=正常，orphaned=来源丢失）

## Step 3: 构建结构化数据

按两个维度分组：

**按药品分组**:
```
drugs = {
  "药品A": [source1, source2, ...],
  "药品B": [source3, ...]
}
```

**按适应症分组**:
```
indications = {
  "适应症X": [source1, source3, ...],
  "适应症Y": [source2, ...]
}
```

## Step 4: 生成药品索引

为每个药品生成 {drug_dir}/{药品名}.md:

```markdown
---
drug: 药品通用名
aliases: [别名1, 别名2]
category: 药物类别
target: 作用靶点
companies: [公司A, 公司B]
---

# 药品名

## 基本信息

| 属性 | 内容 |
|------|------|
| 通用名 | ... |
| 靶点 | ... |
| 药物类别 | ... |
| 研发公司 | ... |

## 临床数据汇总

### 适应症A

| 试验 | 阶段 | 关键数据 | 来源 |
|------|------|----------|------|
| [试验名](#) | Phase III | ORR 41.4%, mPFS 11.3mo | [摘要](../source/药品@适应症A.md) |

### 适应症B

...

## 数据时间线

- YYYY-MM: 适应症A Phase III 数据发布
- YYYY-MM: 适应症B Phase II 数据发布
```

## Step 5: 生成适应症索引

为每个适应症生成 {indication_dir}/{适应症名}.md:

```markdown
---
indication: 适应症名称
category: 适应症类别
aliases: [别名1, 别名2]
---

# 适应症名称

## 概述

...

## 在研药品

| 药品 | 公司 | 阶段 | 关键数据 | 最新进展 |
|------|------|------|----------|----------|
| [药品A](../drug/药品A.md) | 公司A | Phase III | ORR 41.4% | 2024-05 ASCO |
| [药品B](../drug/药品B.md) | 公司B | Phase II | mPFS 8.5mo | 2024-03 |

## 标准治疗

...

## 数据时间线

- YYYY-MM: 药品A 获批
- YYYY-MM: 药品B Phase III 失败
```

## Step 6: 生成汇总清单

生成 {source_dir}/drug.md 和 {source_dir}/indication.md 索引清单：

**drug.md**:
```markdown
# 药品索引

| 药品 | 适应症数 | 最新数据 |
|------|---------|---------|
| [药品A](drug/药品A.md) | 3 | 2024-05 |
```

**indication.md**:
```markdown
# 适应症索引

| 适应症 | 药品数 | 最新数据 |
|--------|-------|---------|
| [适应症X](indication/适应症X.md) | 5 | 2024-05 |
```

## Output

报告：
```
索引更新完成:
- 扫描 {source_dir}: N 个文件
- 药品索引: 生成 M 个药品页
- 适应症索引: 生成 K 个适应症页
- 汇总清单: drug.md, indication.md
```

## 增量更新支持

支持增量更新：
- 对比已有索引文件的修改时间
- 只处理新增的或更新的 {source_dir} 文件
- 保留手动编辑的额外信息（如果不冲突）
