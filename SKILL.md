---
name: clinical-research
description: |
  用户提到"提取临床数据"/提供URL或PDF要求提取数据，或提到"扫描/批处理"/"更新/同步/整理临床数据索引"/"查询临床试验"/"评价临床试验"/"对{药品}建库"/"建库"/"搜索已公布的临床数据"/"查找临床数据来源"/"验证summary"/"审核summary"/"检查summary数据"/"查询{药品}专利"/"搜索{药品}专利"/"查{公司}专利方向" → 触发本skill。本skill用于创新药临床数据的研究，并整理为可追溯的临床数据知识库，完整路由表见正文。
---

# Clinical Research

## 执行约束（触发后必须遵守）

文档中的 `{clinical_research_dir}` 指包含本文件的顶层 `clinical-research/` 目录，不是当前正在执行的子 skill 目录。

### 初始化检查

0. **先检查 `{clinical_research_dir}/config.yaml` 是否存在**：
   - 如果存在：读取配置。配置只能包含一个 `research_dir`，且其值必须是当前系统的绝对路径。
   - 如果不存在、字段不符合要求或路径不是绝对路径：立即读取并执行 `initial.md`。已有但无效的配置不得静默覆盖，先向用户说明并确认重新初始化。
   - 禁止猜测研究目录，禁止从旧字段推断路径，禁止执行 v1 数据迁移。

完成检查后，必须在继续执行前输出：

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

如果 `config.yaml` 为 `missing` 或 `invalid`，必须停止路由并执行 `initial.md`。初始化完成前禁止读取用户提供的 URL/PDF、提取内容或创建研究数据。若请求涉及具体药品，先用根 `index.md` 解析 `company_id` 和 `drug_id`；仍不能唯一确定时询问用户，不得猜测路径。

### 强制流程

1. 完成初始化检查后，立即读取对应子 skill 的 `SKILL.md`（禁止直接回答）。
2. 按子 skill 的 workflow 逐步执行。
3. 必须完成所有 steps。
4. 文件和目录操作必须兼容 Windows；脚本使用 Python 3.10+ 标准库与 `pathlib`，不得依赖 `cp`、`mv`、`mkdir`、`find`、`grep`、`sed` 等 Unix 工具。

### 禁止事项

- 禁止直接调用工具提取内容。
- 禁止不读子 skill 就直接回答。
- 禁止跳过 workflow 步骤。
- 默认禁止 spawn 子 agent；除非对应子 skill 的 workflow 明确要求 reviewer/verifier subagent。
- 禁止创建 v1 的全局 `raw/`、`summary/`、`drug/`、`trials/` 内容根目录或 `company.md`。

## 2.0 数据目录

默认研究目录为 `~/research`。`config.yaml` 中保存展开后的绝对路径，而不是字面量 `~`。

```text
~/research/
├── index.md
├── {company_id}/
│   └── {drug_id}/
│       ├── {drug_id}.md
│       ├── raw/
│       │   └── {drug_id}@{source_label}.md
│       └── summary/
│           └── {drug_id}@{source_label}.md
├── indication/
│   └── {indication_id}.md
├── attachments/
└── .temp/
    └── plans/
```

- `index.md` 是所有任务的第一查询入口，记录公司和药品的规范 ID、别名与定位。它由 agent 生成和维护，也允许用户手工编辑；修改时保留用户已有内容。
- `research_dir` 本身就是 Obsidian vault 根目录；公司目录是其直接子目录，不存在中间 `company/` 容器。
- 初始化不创建任何公司目录。首次创建药品时才创建 `{company_id}/{drug_id}/`。扫描根目录时必须排除 `indication/`、`attachments/`、`.temp/`、所有隐藏目录和其他已知基础设施目录，不能把它们识别为公司。
- `company_id` 也是公司目录名，使用常见公司短名：中日公司通常使用常见中文短名，西方公司通常使用常见英文短名。它必须是单个 Windows-safe 路径组件，但不要求仅含 ASCII。
- 每个药品只有一个 `{drug_id}.md`，不存在 `company.md`。
- 一个来源严格对应同一药品目录中的一个 `raw/{drug_id}@{source_label}.md` 和一个 `summary/{drug_id}@{source_label}.md`。两者同名，不得按适应症复制来源文件。
- 一份 summary 可以覆盖多个适应症，并在内容/元数据中列出全部规范 `indication_id`；适应症聚合写入根 `indication/`。
- `raw` 保留来源原文，不由模型改写；`summary` 是该来源的结构化摘要。
- 临床注册查询写入相应 `{drug_id}.md`。独立 `data-search` 只返回 plan，不写文件；`drug-build` 才将其 plan 持久化到 `.temp/plans/`。不创建全局 `trials/` 或其他全局内容根目录。

## 路由规则

根据用户输入判断应读取哪个子 skill：

| 用户输入 | 子 Skill | 动作 |
|---------|---------|------|
| 明确要求“提取临床数据”且提供 URL/PDF | multi-extractor | 提取唯一入口，按来源生成一对 raw/summary，含验证与索引 |
| “扫描/批处理临床数据” | batch-extractor | 批量处理各药品目录中的 raw → summary |
| “更新/同步/扫描索引” | clinical-indexer | 增量扫描全部药品 summary，更新 `{drug_id}.md`、根 index.md 与 indication/ |
| “整理临床数据” / “归档临床数据” / “整理数据” | clinical-indexer | 增量处理未归档 summary 并更新索引 |
| “扫描未整理的临床数据” / “同步临床数据到索引” | clinical-indexer | 增量处理未归档 summary |
| “更新药品索引” / “更新适应症索引” | clinical-indexer | 更新 root index、`{drug_id}.md` 或 indication/ |
| “查询药品临床试验” / “搜索临床试验” | drug-trials-search | Python 脚本查询 CTG，结果写入对应 `{drug_id}.md` |
| 药品名称 + “临床试验” | drug-trials-search | 生成表格并更新对应 `{drug_id}.md` |
| “搜索已公布的临床数据” / “查找临床数据来源” | data-search | 搜索期刊/会议/公告，只返回 plan，不写入文件 |
| “验证这个summary” / “审核summary” / “检查summary数据” | data-verify | 核对 summary 数据来源并写入审核章节 |
| “对{药品}建库” / “建库” | drug-build | 编排管线、搜索、提取、验证与索引，完整建库 |
| “查询{药品}专利” / “搜索{药品}专利” / 药品名+“专利” | drug-patent-search | Mode A：原研专利，写入 `{drug_id}.md` |
| “查{公司}专利方向” / “{公司}近年专利” | drug-patent-search | Mode C：只返回公司近年专利方向报告，不写入文件，不创建 `company.md` |
| “评价临床数据” / “评估临床试验” / “怎么看这个数据” | clinical-trial-evaluator | 提供系统化的试验数据评价框架 |
| 无明确指令 | — | 要求用户说明要提取、归档、查询还是评价；不得默认写入索引 |

## 核心原则

- **Index-first**：任何实体定位先查根 `index.md`，并明确处理别名和歧义。
- **Source-first**：原始资料绝不修改；每来源恰好一个 raw 和一个 summary。
- **Incremental**：支持增量更新，避免重复处理并保留用户编辑。
- **Structured**：严格使用规范 ID、目录和数据格式。
- **Controlled-spawn**：默认在当前 session 完成；仅当子 skill 明确要求独立审核/验证时，允许 spawn 受限 subagent。

## 常见错误（避免）

错误：看到 URL 就直接提取内容给用户。

正确：先查配置与 `index.md`，再读 `multi-extractor/SKILL.md` 并按 workflow 执行。

错误：按适应症为同一来源保存多份 raw 或 summary。

正确：同一来源只保存一对同名文件，单份 summary 可列出多个适应症。

错误：创建全局 `raw/summary/drug/trials` 或公司说明文件。

正确：内容放入 `{company_id}/{drug_id}/`，公司别名维护在根 `index.md`，且不创建 `company.md` 或 `company/` 根容器。
