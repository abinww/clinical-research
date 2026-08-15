---
name: drug-identity
description: |
  药品身份解析工具。不从主接口直接触发，由编排层按需调用。
---

# 药品身份解析

> 本文件不从主接口直接触发，由编排层按需调用。
> 职责：给定任意药品名称/代号/商品名，统一解析该药品的标准身份（drug_id、drug_aliases、target、companies、molecule_type）。
> 本 skill 是 drug_id 的唯一确定入口：所有子 skill 不得自行决定 drug_id，必须经本 skill 解析。

## 执行约束

- ✅ 输入：任意药品名称、研发代号、合作方代号、通用名或商品名
- ✅ 输出：标准身份对象（见 Step 5），调用方按需取用其中字段
- ✅ 优先读取 drug/ 已有页面缓存，无缓存再 web 搜索确认
- ✅ 身份确认后自动创建/更新 `drug/{drug_id}.md` 骨架文件（幂等）
- ❌ 搜不到药品身份时不猜测、不创建文件，停下询问用户
- ❌ 不自行编造身份字段；所有字段必须有来源（缓存或 web 确认）

## 固化规则

1. **drug_id 唯一确定**：所有子 skill 不得自行决定 drug_id，必须经本 skill 解析。
2. **别名归一**：同一药品的任何别名输入都返回同一个 drug_id（靠 drug_aliases 缓存匹配）。
3. **不重复建文件**：`drug/{drug_id}.md` 已存在（含别名命中）时不创建新文件。
4. **搜不到就停**：无法确认身份时返回用户确认，不猜测、不创建文件。

## Step 1: 输入药品名称

从用户输入或调用方获得药品名称/代号/商品名（如 "Enhertu"、"DS-8201"、"T-DXd"）。

## Step 2: 查 drug/ 缓存

扫描 `{drug_dir}` 下所有 `.md` 文件的 YAML frontmatter：

```bash
find ${drug_dir} -name "*.md" -type f
```

匹配键（任一命中即视为同一药品）：

- `drug_id`
- `drug_aliases`（列表中的任一别名，含通用名）

命中 → 返回该文件的完整身份（drug_id、drug_aliases、target、companies、molecule_type），不创建新文件，结束。

未命中 → 进入 Step 3。

## Step 3: web 搜索确认身份

> ⚠️ 搜不到代号就停下问用户，不猜测，不进入后续步骤。

1. 搜索 `{名称} + 公司名`、`{名称} + clinical trial`
2. 查公司官网管线页
3. 收集**别名全集**：研发代号、合作方代号、通用名、商品名
4. 识别：靶点、分子类型（ADC/双抗/单抗/小分子）、研发公司、合作方

示例：Enhertu（DS-8201）的别名全集可能是：

```text
研发代号: DS-8201
合作方代号: T-DXd
通用名: trastuzumab deruxtecan（德曲妥珠单抗）
商品名: Enhertu（优赫得）
```

## Step 4: 身份确认失败处理

如果无法确认药物身份（代号搜不到、别名无法收集），停下返回：

```text
无法确认药物身份：{名称}
请确认：是否指 {候选1} 或其他药物？
```

不创建文件，等待用户确认后继续。

## Step 5: 确定 drug_id 并输出身份对象

按 `drug-spec.md` 的固定优先级确定 `drug_id`：

```text
开发代码 > 短名称/缩写 > 中文通用名 > 英文通用名
```

输出标准身份对象：

```text
drug_id: {按固定优先级确定}
drug_aliases: {研发代号/合作方代号/通用名/商品名等全集}
target: {最简形式}
companies: {研发公司及合作方}
molecule_type: {ADC/双抗/单抗/小分子}
```

说明：`drug_id` 是唯一识别名（用于文件命名）；所有其他名称统一放在 `drug_aliases` 全集。展示名 `drug` 由调用方从 `drug_aliases` 中选取通用名（本 skill 不单独维护 drug 字段）。

## Step 6: 创建/更新 drug/ 骨架文件

按 `drug-spec.md` 创建或更新 `drug/{drug_id}.md`（幂等）：

- **文件不存在**：只创建 YAML frontmatter 和 `## 基本信息`，**不补全后续临床章节**：
  - frontmatter：`drug_id`、`drug`（从 drug_aliases 选取通用名）、`drug_aliases`、`target`、`companies`、`created`、`updated`
  - `## 基本信息`（身份对象字段）
  - 其他章节（临床数据汇总、关键里程碑、当前临床管线）**不得创建或填充**（即使 drug-spec.md 定义了这些章节格式）；由各章节负责的 writer 按需补充
- **文件已存在**：不覆盖现有内容，只补充缺失的 frontmatter 字段（如新增别名并入 `drug_aliases`），更新 `updated` 日期。
- **创建失败处理**：若 `drug/{drug_id}.md` 骨架创建失败（写入失败、目录不可写等），停止执行并返回错误报告；不得静默返回身份对象、不得让调用方继续以为骨架已存在。

幂等规则：

- 按 `drug_id` 或 `drug_aliases` 命中已有文件 → 不创建新文件，返回该文件身份
- 基本信息字段必须有来源（缓存或 web 确认），不得编造

## 返回

返回给调用方：

```text
drug-identity: {名称} → drug_id: {drug_id}
- drug_aliases: {别名列表}
- target: {最简形式}
- companies: {列表}
- molecule_type: {类型}
- drug/ 文件: {drug_dir}/{drug_id}.md（新建/已存在）
```

