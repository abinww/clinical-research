---
name: clinical-batch-extractor
description: |
  批量处理执行步骤（供clinical-research主skill调用）
  
  当主skill路由到本文件时，按以下步骤执行：
---

# 批量处理 - 执行步骤

> 本文件由 clinical-research/SKILL.md 路由后读取执行
> 所有工具调用在当前session完成

## Step 1: 扫描未处理文件

调用：
```
exec command="bash scripts/find_unprocessed.sh"
```

**脚本输出解析**：
- 列出所有未处理的 raw/ 文件
- 如果无未处理文件，终止执行

## Step 2: 遍历未处理文件

对每个未处理文件，依次执行：

### 2.1 读取文件内容

调用 `read` 读取 raw/ 文件

### 2.2 生成摘要

参考 `../schema/summary-spec.md` 的格式要求，分析内容并生成摘要

### 2.3 保存到 summary/

摘要按药品分子目录组织。先按摘要 YAML 里的 `drug` 字段确定药品名（沿用 drug-spec.md 优先级规则：开发代码 > 短名 > 中文通用名 > 英文通用名），再创建对应的子目录。

调用：
```
mkdir -p {summary_dir}/{药品名}
write path={summary_dir}/{药品名}/{文件名}.md content={摘要内容}
```

**文件名冲突处理**：
- 如果文件名已存在，追加序号：
  - `药品@适应症_P2.md` → `药品@适应症_P2_1.md`

### 2.4 记录结果

记录处理结果：
- raw_file: "raw/xxx.md"
- summary_file: "{药品名}/药品@适应症_P2.md"
- status: success 或 failed

## Step 3: 输出报告

处理完成后，输出批量处理报告：

```
批量处理完成:
- 扫描 {raw_dir}: N 个文件
- 待处理: K 个文件

处理结果:
✓ {raw文件名1}.md → {summary子目录}/{summary文件名1}.md
✓ {raw文件名2}.md → {summary子目录}/{summary文件名2}.md
✗ {raw文件名3}.md → 处理失败

总计: 成功 X 个, 失败 Y 个
```

## 边缘情况处理

### {summary_dir} 文件无 "> 来源原文:" 行

如果 {summary_dir} 文件的正文中没有 `> 来源原文: [[raw/...]]` wikilink 行：
- 跳过该文件，不纳入已处理列表
- 该文件被视为独立生成的摘要，不参与去重判断

### {raw_dir} 文件格式异常

如果 {raw_dir} 文件读取失败或格式异常：
- 记录为处理失败
- 继续处理下一个文件

### 摘要生成失败

如果生成摘要失败或返回空内容：
- 记录为处理失败
- 继续处理下一个文件
- 不保存空文件到 {summary_dir}