---
name: clinical-research
description: |
  用户提到"提取临床数据"/提供URL或PDF要求提取数据，或提到"扫描/批处理"/"更新/同步/整理临床数据索引"/"查询临床试验"/"评价临床试验"/"对{药品}建库"/"建库"/"搜索已公布的临床数据"/"查找临床数据来源"/"验证summary"/"审核summary"/"检查summary数据"/"查询{药品}专利"/"搜索{药品}专利"/"查{公司}专利方向" → 触发本skill。本skill用于创新药临床数据的研究，并整理为可追溯的临床数据知识库，完整路由表见正文。
---

# Clinical Research

## 职责与边界

本 skill 负责初始化预检、身份定位和任务路由，不代替子 skill 执行。`{clinical_research_dir}` 始终指包含本文件的顶层 `clinical-research/`，不是当前子 skill 目录。

- 触发后必须读取并完整执行所选子 skill 的 `SKILL.md`，不得直接提取或跳步回答。
- 默认在当前 session 执行；仅当子 skill 明确要求独立 reviewer/verifier 时才可 spawn 受限 subagent。
- 文件操作须兼容 Windows；脚本使用 Python 3.10+ 标准库与 `pathlib`，不得依赖 `cp`、`mv`、`mkdir`、`find`、`grep`、`sed` 等 Unix 工具。
- 不支持 v1 迁移或兼容布局，不创建全局 `raw/`、`summary/`、`drug/`、`trials/`、`company/` 或 `company.md`。

## 输入与共享契约

### 初始化与运行路径

`~/research` 仅是首次初始化时的推荐默认值。初始化必须展开它并将绝对路径写入 `{clinical_research_dir}/config.yaml`；此后所有运行时路径只取自配置中的绝对 `research_dir`，不得按 `~/research`、旧字段或当前目录推断。

配置只能包含一个 `research_dir`。配置缺失、字段不合规或值不是当前系统绝对路径时，立即读取并执行 `initial.md`；已有但无效的配置不得静默覆盖，须先说明并确认重新初始化。

### 紧凑布局

```text
{research_dir}/
├── index.md
├── {company_id}/{drug_id}/
│   ├── {drug_id}.md
│   ├── raw/{drug_id}@{source_label}.md
│   └── summary/{drug_id}@{source_label}.md
├── indication/{indication_id}.md
├── attachments/
└── .temp/plans/
```

- `research_dir` 就是 Obsidian vault 根目录；公司目录是其直接子目录，初始化时不创建，首次创建药品时才生成。
- 根 `index.md` 是实体定位第一入口，记录规范 ID、别名和路径。agent 可增量维护 managed index markers 内的数据，必须保留 markers 外的用户内容；索引或扫描并非只读。
- 扫描根目录必须排除 `indication/`、`attachments/`、`.temp/`、所有隐藏目录及其他已知基础设施目录。
- 身份对象及路径以 `drug-identity/SKILL.md` 为权威契约；标识不唯一时询问用户，不得猜测或迁移既有归档。
- summary 的结构、命名、来源身份和链接以 `schema/summary-spec.md` 为权威契约。
- summary 是否可归档以 `clinical-indexer/SKILL.md` 的完整资格门禁为准，不得用简化状态判断替代。

## 不变量与写边界

- **Index-first**：先查根 `index.md`，明确处理别名和歧义。
- **Source-first**：raw 保留来源原文，不由模型改写；summary 是同一来源的结构化摘要。
- 每个 canonical source 在单个药品目录中严格对应一对同名 raw/summary；不得按适应症复制。跨药品允许复用同一来源。
- 单份 summary 可覆盖多个规范 `indication_id`；药品页、适应症页和根索引中的 managed blocks 由 indexer 增量维护，并保留人工内容。
- 每个药品只有一个 `{drug_id}.md`。临床注册查询写入该页；独立 `data-search` 只返回 plan，`drug-build` 才把 plan 持久化到 `.temp/plans/`。

## 工作流

1. 检查 `{clinical_research_dir}/config.yaml`。缺失或无效时，先按下列格式报告 `missing/invalid`，再停止路由并执行 `initial.md`；初始化完成前禁止读取用户 URL/PDF、提取内容或创建研究数据。
2. 配置有效时读取根 `index.md`。请求涉及具体药品时解析 `company_id`、`drug_id` 和目标目录；不能唯一确定时询问用户。
3. 在继续路由前输出：

```text
PREFLIGHT:
- config.yaml: found / missing / invalid
- research_dir: <absolute path> / unresolved
- index.md: found / missing / unresolved
- company_id: <canonical id> / unresolved / not-applicable
- drug_id: <canonical id> / unresolved / not-applicable
- target_drug_dir: <absolute path> / unresolved / not-applicable
- selected_subskill:
- reason:
```

4. 配置和必要身份均已解决后，按路由表选择子 skill，立即读取其 `SKILL.md` 并完成全部 workflow。

| 用户输入 | 子 Skill | 动作 |
|---|---|---|
| 明确要求“提取临床数据”且提供 URL/PDF | multi-extractor | 唯一提取入口；按来源生成 raw/summary、验证并索引 |
| “扫描/批处理临床数据” | batch-extractor | 批量处理各药品目录中的 raw → summary |
| “更新/同步/扫描索引” | clinical-indexer | 增量扫描 summary，更新药品页、根 index.md 与 indication/ |
| “整理/归档临床数据”“整理数据” | clinical-indexer | 增量处理未归档 summary 并更新索引 |
| “扫描未整理的临床数据”“同步临床数据到索引” | clinical-indexer | 增量处理未归档 summary |
| “更新药品索引”“更新适应症索引” | clinical-indexer | 更新 root index、药品页或 indication/ |
| “查询药品临床试验”“搜索临床试验”或药品名称 + “临床试验” | drug-trials-search | Python 脚本查询 CTG，生成表格并写入药品页 |
| “搜索已公布的临床数据”“查找临床数据来源” | data-search | 搜索期刊/会议/公告，只返回 plan，不写文件 |
| “验证这个summary”“审核summary”“检查summary数据” | data-verify | 核对来源并写入审核章节 |
| “对{药品}建库”“建库” | drug-build | 编排搜索、提取、验证和索引 |
| “查询/搜索{药品}专利”或药品名 + “专利” | drug-patent-search | Mode A：原研专利，写入药品页 |
| “查{公司}专利方向”“{公司}近年专利” | drug-patent-search | Mode C：返回方向报告，不写文件、不创建 `company.md` |
| “评价临床数据”“评估临床试验”“怎么看这个数据” | clinical-trial-evaluator | 提供系统化评价框架 |
| 无明确指令 | 无 | 询问要提取、归档、查询还是评价，不默认写索引 |

## 失败与恢复

- 配置、根索引或身份未解决时停止对应写入，不读取来源、不猜路径。
- 子 skill 的重复、重试、事务和恢复规则优先，顶层不得绕过或降级。
- 任一 workflow 未完成时明确报告阻断步骤和原因，不把部分结果描述为完成。

## 输出

先输出规定的 `PREFLIGHT`，再按所选子 skill 的输出契约报告结果、失败和未完成项。
