---
name: clinical-drug-summarizer
description: |
  药品临床数据汇总工具。**触发后扫描 summary/{药品名}/ 下所有该药品的临床数据，按适应症和时间线汇总生成 drug/{药品名}.md！**
  
  ### 何时触发（满足任一即触发）
  - 用户提到"汇总药品临床数据"
  - 用户提到"生成药品索引"
  - 用户提到"整理{药品名}的所有数据"
  - 用户提到"把{药品名}的数据汇总到drug/下面"
  - 用户提到"drug summarizer"
---

# Clinical Drug Summarizer

> 本文件由 clinical-research/SKILL.md 路由后读取执行
> 所有工具调用在当前session完成

## ⚠️ 执行约束（触发后必须遵守）

### 强制流程
1. **必须按步骤执行**：扫描 → 解析 → 汇总 → 生成
2. **必须读取schema格式规范**：生成前读取 ../schema/drug-spec.md
3. **必须增量处理**：只处理该药品相关的summary文件

### 禁止事项
- ❌ 禁止跳过schema格式检查
- ❌ 禁止修改 summary/ 下的原始文件
- ❌ 禁止遗漏任何适应症的数据

---

## Workflow

### Step 0: 读取格式规范

**格式规范文件**：`../schema/drug-spec.md`

执行操作：
```bash
cat ../schema/drug-spec.md
```

提取关键格式要求：
- frontmatter字段（drug, aliases, companies, target, sources等）
- 正文结构（基本信息、临床数据汇总、数据时间线、数据来源）
- 表格格式规范

---

### Step 1: 扫描该药品的所有summary文件

摘要文件按药品分子目录存放于 `summary/{药品名}/`。需先按药品名或别名匹配子目录，再枚举子目录下所有 `.md` 文件。

**操作**：
```bash
# 1) 按药品名/别名匹配子目录
find ${summary_dir} -maxdepth 1 -type d -name "*{药品名}*" -o -name "*{别名}*"

# 2) 对每个匹配的子目录，列出其中所有 .md 文件
find ${summary_dir}/{匹配子目录} -maxdepth 1 -name "*.md" -type f
```

**匹配规则**：
- 第一步按子目录名匹配：子目录名包含药品通用名或任一别名
- 第二步枚举每个匹配子目录下的全部 `.md` 文件（同一药品的全部摘要都归在该子目录下）

**输出**：
- 显示找到的文件列表
- 如果没有找到文件，报告错误并结束

---

### Step 2: 解析每个summary文件

对每个找到的summary文件：

**提取 frontmatter 字段**：
- `drug`: 药品通用名
- `drug_aliases`: 别名列表
- `indication`: 适应症
- `companies`: 公司列表
- `phase`: 临床阶段
- `trial_name`: 试验名称
- `conference`: 会议名称
- `created`: 数据日期
- `source_raw`: 原始文件路径（指向 raw/ 目录下的对应文件，字段名保留不变）

**提取核心数据表格**：
- 读取文件中的有效性和安全性数据表格
- 提取关键指标：ORR、DCR、mPFS、mOS、mDoR、PSA50等
- 提取安全性数据：任何TRAE、G≥3 TRAE、减量、停药、死亡

**按适应症分组**：
- 同一适应症的数据归为一组
- 同一适应症内按时间排序（created日期或conference日期）

---

### Step 3: 生成药品汇总文件

**文件路径**：`${drug_dir}/${drug}.md`

**Frontmatter**：
```yaml
---
drug: {药品通用名}
drug_aliases: [{别名1}, {别名2}]
companies: [{公司1}, {公司2}]
target: {靶点}
payload: {载荷}
DAR: {DAR值}
fast_track: {适应症} ({日期})
orphan_drug: {适应症} ({日期})
trial: {试验编号}
phase3: {Phase 3试验信息}
---
```

**正文结构**：

#### 1. 按适应症分章节

每个适应症一个二级标题（##）：

```markdown
## 1. {适应症A}

| 时点 | 会议 | n | ORR | DCR | mPFS | 关键备注 |
|------|------|:-:|:---:|:---:|:----:|---------|
| 2024-12 | ESMO Asia | 73 | 56.2% | 89.0% | — | 首次数据 |
| 2025-06 | ASCO | 52 | 42.3% | 90.4% | 6m rPFS 67.7% | 更新数据 |

> 来源: [[summary/{药品名}/{文件名1}.md]] | [[summary/{药品名}/{文件名2}.md]]
```

**表格规范**：
- 同一适应症按时间顺序排列（从早到晚）
- 列名：时点、会议、n、ORR、DCR、mPFS、关键备注
- 时间指标写数字+单位（如 `11.3mo`）
- 百分比保留一位小数
- 关键备注列简要标注数据特点

#### 2. 关键里程碑

```markdown
## 关键里程碑

| 时间 | 事件 |
|------|------|
| 2024-06 | FDA Fast Track (mCRPC) |
| 2024-12 | ESMO Asia: 首次人体数据 |
```

---

### Step 4: 写入文件

**操作**：
```bash
# 确保 drug/ 目录存在
mkdir -p ${drug_dir}

# 写入汇总文件
cat > ${drug_dir}/${drug}.md << 'EOF'
{生成的内容}
EOF
```

---

## 数据提取规则

### 有效性数据提取

从summary文件的表格中提取：
- **ORR/cORR/uORR**: 优先取cORR，其次uORR
- **DCR**: 疾病控制率
- **mPFS/rPFS**: 中位无进展生存期
- **mOS**: 中位总生存期
- **mDoR**: 中位缓解持续时间
- **PSA50/PSA90**: PSA缓解率（前列腺癌）

### 安全性数据提取

从summary文件的表格中提取：
- **任何TRAE**: 治疗相关不良事件发生率
- **G≥3 TRAE**: 3级及以上TRAE
- **减量**: 剂量减少率
- **停药**: 因TRAE停药率
- **死亡**: 治疗相关死亡率

### 亚组数据

如果summary文件包含亚组分析（如Lu-177经治 vs 未治）：
- 在关键备注列标注
- 或单独一行展示

---

## 输出

### 完成报告

```
药品临床数据汇总完成：

💊 药品: {药品名}
📁 扫描文件: N 个summary文件
🏥 适应症: M 个
📊 生成文件: {drug_dir}/{药品名}.md

📋 适应症列表:
  1. {适应症A} - K 个时点
  2. {适应症B} - L 个时点
  ...

🔗 来源链接:
  - summary/{药品名}/{文件1}.md
  - summary/{药品名}/{文件2}.md
  ...
```

---

## 错误处理

### 字段缺失

如果summary文件缺少关键字段：
- 缺 `drug` 或 `indication`: 跳过该文件，记录警告
- 缺 `created` 或 `conference`: 使用文件名推断日期，或标注"日期未知"
- 缺数据表格: 在汇总中标注"数据待补充"

### 数据冲突

如果同一适应症、同一时点的数据不一致：
- 以最新summary文件为准
- 在备注中标注数据来源差异

### 文件已存在

如果 `${drug_dir}/${drug}.md` 已存在：
- 读取现有文件
- 合并新旧数据（增量更新）
- 更新 `updated` 字段

---

## 增量更新

本技能支持增量更新：

1. **首次运行**：
   - 扫描所有相关summary文件
   - 生成完整汇总文件

2. **后续运行**：
   - 读取现有drug/文件
   - 只处理新增的summary文件
   - 更新已有适应症的数据

3. **强制重建**：
   - 如果用户要求"重建汇总"
   - 删除现有drug/文件，重新生成
