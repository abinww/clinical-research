---
name: clinical-wiki
description: |
  临床数据整理工具。**触发后按workflow整理未归档的临床数据！**
  
  ### 何时触发（满足任一即触发）
  - 用户提到"整理临床数据" / "整理数据"
  - 用户提到"归档临床数据" / "归档数据"
  - 用户提到"同步临床数据到索引"
  - 用户提到"扫描未整理的临床数据"
  - 用户提到"更新药品索引" / "更新适应症索引"
  - 用户提到"clinical-source-organizer"
---

# Clinical Source Organizer

> 本文件由 clinical-research/SKILL.md 路由后读取执行
> 所有工具调用在当前session完成

## ⚠️ 执行约束（触发后必须遵守）

### 强制流程
1. **必须按步骤执行**：读取配置 → 扫描 → 对比 → 整理
2. **必须读取schema文件**：整理前先读取格式规范
3. **必须增量处理**：只处理未整理的文件

### 禁止事项
- ❌ 禁止跳过schema格式检查
- ❌ 禁止重复处理已整理的文件
- ❌ 禁止修改 source_dir/ 下的原始文件

---

## Workflow

### Step 0: 读取配置和格式规范

**配置文件**：`../config.yaml`

提取配置：
- `source_dir`: 规范摘要存放目录
- `drug_dir`: 药品索引存放目录
- `indication_dir`: 适应症索引存放目录

**格式规范文件**：
- `../schema/drug-spec.md`: 药品索引格式规范
- `../schema/indication-spec.md`: 适应症索引格式规范

**执行操作**：
```bash
# 读取配置
cat ../config.yaml

# 读取格式规范（稍后在生成文件时使用）
cat ../schema/drug-spec.md
cat ../schema/indication-spec.md
```

---

### Step 1: 扫描已整理的文件

**目的**：确定哪些 source 文件已经被整理到索引中

**操作**：
```bash
# 列出 drug_dir 下所有 .md 文件（排除 schema.md）
find ${drug_dir} -name "*.md" ! -name "schema.md" -type f

# 列出 indication_dir 下所有 .md 文件（排除 schema.md）
find ${indication_dir} -name "*.md" ! -name "schema.md" -type f
```

**提取已整理的 source 列表**：
- 读取每个 drug/*.md 文件，提取所有 `> 来源:` 行中的 `[[source/...]]` 链接
- 读取每个 indication/*.md 文件，提取所有 `> 来源:` 行中的 `[[source/...]]` 链接
- 合并去重，得到 `organized_sources` 列表

---

### Step 2: 扫描待整理的文件

**目的**：找出 source_dir 中未被整理的文件

**操作**：
```bash
# 列出 source_dir 下所有 .md 文件
find ${source_dir} -name "*.md" -type f
```

**计算未整理文件**：
```
unorganized = source_dir 所有文件 - organized_sources
```

**输出**：
- 显示未整理文件列表
- 如果没有未整理文件，报告完成并结束

---

### Step 3: 解析未整理的 source 文件

对每个未整理的文件：

**提取 frontmatter 字段**：
- `drug`: 药品通用名（必需）
- `drug_aliases`: 别名列表
- `indication`: 适应症（必需）
- `companies`: 公司列表
- `phase`: 临床阶段
- `trial_name`: 试验名称
- `conference`: 会议名称
- `created`: 数据日期
- `source_raw`: 原始文件路径

**提取核心数据表格**：
- 读取文件中的有效性和安全性数据表格
- 用于后续生成适应症对比表格

---

### Step 4: 按**药品**维度整理

对每个药品（drug）：

**检查是否存在药品索引文件**：
```bash
ls ${drug_dir}/${drug}.md
```

**情况A：文件不存在 → 新建**
- 按照 `../schema/drug-spec.md` 格式创建新文件
- 填充基本信息（drug, aliases, companies, target等）
- 添加当前临床数据到"临床数据汇总"部分，表格后添加 `> 来源: [[source/{文件名}.md]]`

**情况B：文件已存在 → 更新**
- 读取现有文件内容
- 提取现有 `> 来源:` 行，确认当前 source 是否已在其中
- 更新"临床数据汇总"部分：
  - 按时间顺序排列（根据 `created` 或 `conference` 日期）
  - 如有新适应症，添加新的适应症章节，表格后添加 `> 来源:` 行
  - 如有同一适应症的新数据，追加到表格，用 `|` 分隔追加到对应的 `> 来源:` 行

**药品索引文件命名规则**：
- 文件名：`${drug}.md`
- 如有多个别名，使用最常用的名称
- 特殊字符替换：空格→下划线，括号等特殊字符移除

---

### Step 5: 按**适应症**维度整理

对每个适应症（indication）：

**检查是否存在适应症索引文件**：
```bash
ls ${indication_dir}/${indication}.md
```

**情况A：文件不存在 → 新建**
- 按照 `../schema/indication-spec.md` 格式创建新文件
- 将当前药品加入"在研药品"表格
- 表格后添加 `> 来源: [[source/{文件名}.md]]`

**情况B：文件已存在 → 更新**
- 读取现有文件内容
- 检查当前药品是否已在"在研药品"表格中
- 如不在，添加新行，追加到 `> 来源:` 行（用 `|` 分隔）
- 如已存在，更新该药品的数据（如新数据更近），检查并更新 `> 来源:` 行

**适应症索引文件命名规则**：
- 文件名：`${indication}.md`
- 一线/二线/三线治疗视为不同适应症，分开文件
- 示例：
  - `NSCLC_1L.md` (非小细胞肺癌一线)
  - `NSCLC_2L.md` (非小细胞肺癌二线)
  - `胃癌一线.md`
  - `HER2阳性胃癌.md`

**适应症对比表格生成规则**：
- 表格列：药品 | 公司 | 阶段 | ORR | mPFS | mOS | 安全性要点 | 数据来源
- 数据来源列链接到 source 文件
- 按临床阶段排序（Phase III → Phase II → Phase I）

---

## Output

### 完成报告

```
临床数据整理完成：

📊 扫描结果：
  - source_dir: N 个文件
  - 已整理: M 个文件
  - 待整理: K 个文件

💊 药品索引更新：
  - 新建: X 个文件
  - 更新: Y 个文件
  - 跳过: Z 个文件（已在索引中）

🏥 适应症索引更新：
  - 新建: A 个文件
  - 更新: B 个文件
  - 跳过: C 个文件（已在索引中）

📁 涉及文件：
  [列出新建/更新的文件路径]
```

---

## 错误处理

### 字段缺失

如果 source 文件缺少必需字段：
- 缺 `drug`: 跳过该文件，记录警告
- 缺 `indication`: 跳过该文件，记录警告
- 其他字段缺失: 继续处理，字段留空

### 命名冲突

如果药品名或适应症名存在多个别名：
- 优先使用 source 文件中的 `drug` 字段值
- 在索引文件中记录所有别名
- 后续遇到别名时，映射到已有文件

### 数据不一致

如果同一药品/适应症的不同 source 数据冲突：
- 以 `created` 日期最新的为准
- 在"数据时间线"中记录所有版本
- 保留历史数据但不覆盖

---

## 增量更新

本技能支持增量更新：

1. **首次运行**：
   - 扫描所有 source 文件
   - 生成所有药品和适应症索引

2. **后续运行**：
   - 只处理新增的 source 文件
   - 更新已有的索引文件
   - 不重复处理已整理的文件

3. **全量重建**：
   - 如果用户要求"重建索引"，删除所有 drug/*.md 和 indication/*.md（保留 schema.md）
   - 重新处理所有 source 文件
