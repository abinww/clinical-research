# clinical-research 2.0

面向创新药临床研究的可追溯知识库 Skill。它根据用户请求路由到对应子 Skill，把 URL、PDF、公告和会议资料按公司/药品整理，并支持提取、验证、索引、检索、专利研究和临床数据评价。

适用于支持 `SKILL.md` 路由机制的 AI Coding Agent，例如 Codex、OpenCode 和 OpenClaw。

## 主要功能

- 从 URL 或 PDF 保存来源原文并生成结构化摘要。
- 一个来源对应一份 raw 和一份 summary；单份 summary 可覆盖多个适应症。
- 通过根 `index.md` 解析公司/药品规范 ID 和别名。
- 按药品维护 `{drug_id}.md`，按适应症维护根索引。
- 查询临床试验、搜索公开数据和专利，并评价试验设计、疗效与安全性。

## 子 Skill

| 目录 | 用途 |
| --- | --- |
| `multi-extractor/` | 单/多链接提取、验证与索引的唯一入口。 |
| `clinical-extractor/` | 单来源提取单元：来源 → raw → summary。 |
| `batch-extractor/` | 批量处理药品目录中未整理的 raw。 |
| `clinical-indexer/` | 扫描 summary 并更新 `{drug_id}.md`、根 `index.md` 和 `indication/`。 |
| `drug-trials-search/` | 查询临床试验注册信息并更新 `{drug_id}.md`。 |
| `drug-patent-search/` | 检索药品或公司专利。 |
| `data-search/` | 搜索已公布数据来源并返回计划，不写入文件。 |
| `drug-identity/` | 解析规范药品身份、别名、靶点与公司归属。 |
| `data-verify/` | 对照 raw/来源验证 summary。 |
| `drug-build/` | 编排查询、搜索、提取、验证和索引。 |
| `clinical-trial-evaluator/` | 结构化评价临床试验数据。 |
| `schema/` | Markdown 数据规范。 |

## 安装

让当前 Agent 按安装文档执行：

```text
请按照 https://github.com/abinww/clinical-research/blob/main/install.md 安装 clinical-research skill。
```

也可克隆完整仓库，并将 `clinical-research/` 放入当前 Agent 文档指定的 skill 根目录：

```text
git clone https://github.com/abinww/clinical-research.git
```

安装后若没有 `config.yaml`，Agent 会执行 `initial.md`。默认研究目录是 `~/research`；配置中会保存展开后的绝对路径。

## 2.0 数据模型

```text
~/research/
├── index.md                         # 第一查询入口：公司/药品 ID、别名与路径
├── {company_id}/
│   └── {drug_id}/
│       ├── {drug_id}.md
│       ├── raw/{drug_id}@{source_label}.md
│       └── summary/{drug_id}@{source_label}.md
├── indication/{indication_id}.md
├── attachments/
└── .temp/plans/
```

核心规则：

- `index.md` 是任何实体定位的第一查询入口，由 Agent 生成和维护，也允许用户编辑。Agent 更新时必须保留用户内容。
- 根索引包含公司和药品别名。歧义别名必须明确区分，例如 MSD 指向 Merck & Co./默沙东，Merck KGaA/德国默克在美国和加拿大使用 EMD 品牌，不得合并两者。
- `research_dir` 本身是 Obsidian vault 根目录，不存在中间 `company/` 容器。
- 初始化只创建 `indication/`、`attachments/`、`.temp/plans/` 和 `index.md`。创建首个药品时才在 vault 根目录直接创建对应公司和药品目录。
- `company_id` 和公司目录使用常见短名，可以包含中文；中日公司通常用常见中文短名，西方公司通常用常见英文短名。名称必须 Windows-safe，但不要求仅含 ASCII。
- 每个药品一个 `{drug_id}.md`，不创建 `company.md`。
- 每个来源使用稳定 `source_label`，并恰好对应同一药品下同名的 `raw/{drug_id}@{source_label}.md` 与 `summary/{drug_id}@{source_label}.md`。
- summary 可以列出多个适应症；不得为了不同适应症复制同一来源。
- `indication/` 是根级适应症索引；`attachments/` 保存附件；`.temp/plans/` 只保存 `drug-build` 持久化的临时计划。独立 `data-search` 只返回 plan。
- 根目录扫描必须排除 `indication/`、`attachments/`、`.temp/`、隐藏目录和其他已知基础设施目录，不能将它们误判为公司。
- 不存在全局 `raw/`、`summary/`、`drug/`、`trials/` 或其他全局内容根目录。试验注册结果进入对应 `{drug_id}.md`；公司专利 Mode C 只返回报告，不写临时文件。

共享配置位于 `clinical-research/config.yaml`，且只包含：

```yaml
research_dir: C:/Users/example/research
```

路径必须为当前系统的绝对路径。所有自动化应使用 Python 3.10+ 标准库和 `pathlib`，兼容 Windows，不依赖 Unix 文本或文件工具。

2.0 初始化不提供 v1 数据迁移，也不会从旧配置推导目录。

## 使用示例

```text
提取临床数据: <URL>
对某个药品建库
查询某个药品的临床试验
更新药品索引
评价这项临床试验数据
```

顶层 `SKILL.md` 先进行配置和索引预检，再按请求读取对应子 skill 的完整 workflow。

## 安全

- 不要提交患者隐私数据、API key、账号凭证、未公开资料或商业敏感文件。
- `config.yaml` 和误放在 skill 仓库内的研究数据均被 `.gitignore` 排除；研究数据应存放在配置的外部目录。
- raw 保留来源原文，summary 和索引保留来源链接；重要结论应人工复核。
- 本 Skill 用于研究整理和分析辅助，不构成医学、投资或监管建议。

## 许可证

本项目使用 MIT License，详见 `LICENSE`。
