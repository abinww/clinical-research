---
name: drug-trials-search
description: |
  药品临床试验查询工具。当用户提到以下关键词时触发：
  - "查询药品临床试验"
  - "搜索临床试验"
  - 药品名称 + "临床试验"（如"PD-1临床试验"、"AstraZeneca临床试验"）
---

# 药品临床试验查询

> 本文件由 clinical-research/SKILL.md 路由后读取执行

## 执行约束

- ✅ 必须使用 Python 脚本执行搜索和字段提取
- ✅ 当前版本只查询 clinicaltrials.gov；chinadrugtrials.org.cn 仅保留 schema 占位，暂不查询
- ✅ 所有结果全部罗列，不去重
- ✅ 输出为表格格式
- ✅ 搜索完成后必须将结果写入 `drug/{药品名}.md` 的临床管线章节

## 数据源

| 网站 | 范围 | 查询方式 |
|-----|-----|---------|
| clinicaltrials.gov | 全球 | Python 脚本 (API) |
| chinadrugtrials.org.cn | 中国 | 当前版本不查询，仅由 drug-spec.md 保留占位 |

## Step 1: 输入识别

从用户输入中提取：
- **药品名称**：如 "Pembrolizumab"、"Keytruda"、"PD-1"
- **适应症**（可选）：如 "非小细胞肺癌"、"NSCLC"
- **Sponsor**（可选）：如 "Merck"、"AstraZeneca"

## Step 2: 执行 clinicaltrials.gov 查询

调用 Python 脚本：
```bash
python3 {skill_dir}/search_trials.py --drug "<药品名称>" [--indication "<适应症>"] --source ctg --format pipeline-markdown
```

脚本使用 clinicaltrials.gov 官方 API，负责字段提取、治疗方案整理、注册国家去重、排序和 schema 对齐的 Markdown 渲染。agent 不得从 API 原始数据自行提取、补全或改写临床字段。

## Step 3: 处理脚本输出

- 原样读取 Python 输出的 `### clinicaltrials.gov` 管线子表。
- 按 `../schema/drug-spec.md` 的“当前临床管线”格式向用户展示。
- 不得新增“来源”或“链接”列；试验 URL 已嵌入试验 ID。
- 不得自行重排表格、修改数字、补全缺失值或根据常识推断国家。
- 脚本无法获得的字段统一保留为 `—` 或 API 返回的规范空值。

## Step 4: 写入药品管线文件

> ⚠️ **强制步骤**：搜索完成后必须执行，不可跳过。

### 4.1 读取格式规范

管线表格的列定义、链接格式、排序规则等全部以 drug-spec.md 为准：
```bash
cat ../schema/drug-spec.md
```
关注「当前临床管线」章节的格式要求。

### 4.2 处理 drug/{药品名}.md

```
文件存在？
├── 是 → 读取内容，定位 ## 当前临床管线 章节
│         （不关心该章节在文件中的位置，位置由 drug-spec.md 定义）
│         找到 ### clinicaltrials.gov 子表
│         按 NCT编号 去重合并（同号更新，不同号追加）
│         不触碰其他章节（基本信息、临床数据汇总、关键里程碑）
│
└── 否 → 按 drug-spec.md 格式新建文件
         包含：frontmatter + 基本信息 + 临床数据汇总（空）
              + 关键里程碑（空） + 当前临床管线
```

### 4.3 去重合并策略

- **去重键**：NCT编号（从试验ID中提取）
- **已存在** → 更新可能变化的字段（状态、更新日期、入组数等），保留原有数据
- **不存在** → 追加新行
- **不删除已有行**（保护手动补充的数据）
- **排序**：按阶段（Phase III → II → I），同阶段按开始日期倒序
- **⚠️ trial_id 格式**：脚本返回的 trial_id 已包含完整标识符（如 `NCT06104566`），构造 Markdown 链接时直接使用 `[{trial_id}]({url})`，**不要额外添加 `NCT` 前缀**

### 4.4 写入

将与 Step 3 完全相同的 schema 对齐表格写回 `{drug_dir}/{药品名}.md`。只更新 `### clinicaltrials.gov` 子表，保留 `### chinadrugtrials.org.cn` 占位和人工内容不变。

### 4.5 可选：保存搜索结果到 trials/ 目录

如需保留原始搜索结果，可额外保存到：
```
{trials_dir}/search_{药品名称}_{日期}.md
```

## 技术说明

### clinicaltrials.gov API

- 文档：https://clinicaltrials.gov/api-guide/
- 端点：https://clinicaltrials.gov/api/v2/studies
- 方法：GET 请求，支持 JSON 响应
- 无需认证，无速率限制（合理使用）

### chinadrugtrials.org.cn（暂未启用）

该数据源因瑞数反爬机制暂未接入当前 workflow。恢复时应单独设计并验证 Python 抓取与解析流程，不得由 agent 临时手工补表。

## 常见问题

### Q: 查询无结果？
- 检查药品名称拼写
- 尝试通用名/商品名/代码不同写法
- 放宽搜索条件（去掉适应症限制）

### Q: 字段缺失？
- 部分字段在原始数据中可能为空
- 用 "N/A" 或 "-" 标记缺失字段

### Q: chinadrugtrials 无法访问？
- 确认 OpenClaw browser tool 可用
- 手动访问：https://www.chinadrugtrials.org.cn/
