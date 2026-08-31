---
name: drug-trials-search
description: |
  药品临床试验查询工具。当用户提到以下关键词时触发：
  - "查询药品临床试验"
  - "搜索临床试验"
  - 药品名称 + "临床试验"（如"PD-1临床试验"、"AstraZeneca临床试验"）
---

# 药品临床试验查询

> 本文件由 clinical-research/SKILL.md 路由后读取执行。

## 约束与写入边界

- 必须使用 `search_trials.py` 搜索和提取字段；agent 不得从 API 原始数据自行提取、补全或改写临床字段。
- 当前只查询 clinicaltrials.gov。`chinadrugtrials.org.cn` 仅保留 schema 占位，不查询，也不手工补表。
- API 返回的所有结果均展示；写入时按 NCT 编号幂等合并。
- 成功搜索后必须写入已解析 `drug_page` 的 `## 当前临床管线`，且只更新 `### clinicaltrials.gov` 子表。
- 不创建 drug 文件或 `trials/` 目录，不保存独立搜索结果或其他 trial 输出文件。
- 不创建或填充 `## 临床数据汇总`、`## 关键里程碑`，不修改其他章节、`### chinadrugtrials.org.cn` 占位或人工内容。
- 数据源失败时不得展示或写入结果，现有管线保持不变。

## 数据源

| 网站 | 范围 | 查询方式 |
|---|---|---|
| clinicaltrials.gov | 全球 | Python 脚本（官方 API） |
| chinadrugtrials.org.cn | 中国 | 当前不查询，仅由 drug-spec.md 保留占位 |

## Step 1: 输入与身份

从用户输入提取药品名称，以及可选的适应症和 Sponsor。

以 **identity mode `resolve_or_create`** 调用 `../drug-identity/SKILL.md`，获取并原样使用完整标准身份与位置对象，包括 `drug_id`、`drug_aliases`、`target`、`company_ids`、`company_id`、`research_dir`、`drug_page`、`attachments_dir`、`mode`、`status`；兼容字段 `companies` 如存在，必须与 `company_ids` 相同。身份无法确认或未返回已解析 `drug_page` 时停止询问用户。

将 `drug_id` 和全部已确认的 `drug_aliases` 去重后分别作为独立 CTG 查询词，避免商品名与研发代号登记不一致导致漏检。脚本按 NCT 编号确定性合并多别名结果。

## Step 2: 执行查询

```text
python {skill_dir}/search_trials.py --drug "<drug_id>" --drug "<alias1>" [--drug "<alias2>" ...] [--indication "<适应症>"] --source ctg --format pipeline-markdown
```

脚本使用 clinicaltrials.gov 官方 API，负责字段提取、治疗方案整理、注册国家去重、排序和 schema 对齐的 Markdown 渲染。

退出码 `0` 表示成功，包括真实零结果。非零退出码或 stderr 中的 `[ERROR]` 表示 API/数据源失败；不得将空输出解释为“未找到”，应报告数据源失败且不展示、不写入。

## Step 3: 处理输出

- 原样读取脚本输出的 `### clinicaltrials.gov` 管线子表。
- 按 `../schema/drug-spec.md` 的“当前临床管线”格式展示；不得新增“来源”或“链接”列，试验 URL 已嵌入试验 ID。
- 不重排表格，不修改数字，不补全缺失值，不按常识推断国家；脚本缺失字段统一为 `—`。
- 药品列和对照列由脚本按 CTG `armGroups` 生成：所有不同的 EXPERIMENTAL arm 均保留，arm 内联用以 ` + ` 分隔，arm 之间以 `; ` 分隔，ACTIVE_COMPARATOR/PLACEBO_COMPARATOR 映射为对照。agent 不得改写。

## Step 4: 合并写入

先读取 `../schema/drug-spec.md`，以其“当前临床管线”列定义、链接格式和排序规则为准。

若 `drug_page` 不存在，停止并报告 `"{drug_page} 不存在，无法写入管线章节"`，不得新建或猜测路径。文件存在时定位 `## 当前临床管线` 中的 `### clinicaltrials.gov` 子表，并将与 Step 3 完全相同的 schema 对齐表格合并写回：

- 去重键为从试验 ID 提取的 NCT 编号。
- 已存在的 NCT 更新状态、更新日期、入组数等可能变化且本次提供的字段，并保留原有数据。
- 新 NCT 追加；不删除已有行，以保护人工补充数据。
- 按阶段 Phase III → II → I 排序，同阶段按开始日期倒序。
- 脚本返回的 `trial_id` 已含完整标识符，如 `NCT06104566`。链接直接使用 `[{trial_id}]({url})`，不得再添加 `NCT` 前缀。

脚本标准输出仅用于本次展示和写入，不另行持久化。

## 技术说明

- API 文档：https://clinicaltrials.gov/api-guide/
- API 端点：https://clinicaltrials.gov/api/v2/studies
- 请求方式：GET、JSON，无需认证；合理使用。
- CDT 因瑞数反爬机制暂未接入。恢复时须单独设计并验证 Python 抓取与解析流程。
