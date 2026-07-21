# clinical-research

一个面向临床研究资料整理、结构化提取、索引更新和临床数据评价的通用 Skill。它根据用户请求自动路由到对应的子 Skill，帮助把 URL、PDF、公告、会议资料等来源整理为可追溯的临床数据知识库。

适用于任何支持 SKILL.md 路由机制的 AI Coding Agent（如 Codex、OpenCode、OpenClaw 等）。

## 主要功能

- 从 URL 或 PDF 提取临床研究资料，保存为原始资料。
- 将原始资料整理成结构化临床摘要。
- 按药品和适应症生成或更新索引。
- 批量扫描未处理资料，增量生成摘要。
- 查询药品相关临床试验注册信息。
- 按统一框架评价临床试验设计、疗效、安全性和竞争格局。

## 子 Skill 说明

| 目录 | 用途 |
| --- | --- |
| `clinical-extractor/` | 从 URL 或 PDF 提取临床资料，并生成结构化摘要。 |
| `batch-extractor/` | 批量处理 raw 目录下尚未整理的临床资料。 |
| `clinical-indexer/` | 定时或手动扫描全部 summary，分别查漏补缺 drug/ 和 indication/ 索引。 |
| `drug-trials-search/` | 查询临床试验注册信息，并写入药品管线表。 |
| `clinical-trial-evaluator/` | 按结构化框架评价临床试验数据。 |
| `schema/` | 临床摘要、药品索引、适应症索引的 Markdown 格式规范。 |

## 安装方式

### 方式一：让 Agent 自动安装

直接对当前 agent 发送：

```text
请按照 https://github.com/abinww/clinical-research/blob/main/install.md 安装 clinical-research skill。
```

Agent 会读取 `install.md` 并自动识别自身所属环境的 skill 目录，完成下载与初始化。

### 方式二：手动 Git 克隆

```bash
git clone https://github.com/abinww/clinical-research.git
```

将 `clinical-research` 目录放入当前 agent 的 skill 根目录（常见名称：`skills/`、`tools/`、`plugins/` 等，以当前 agent 的文档为准）：

```text
{skill_root}/clinical-research/
```

### 首次初始化

安装完成后，如果目录下不存在 `config.yaml`，agent 会自动读取 `initial.md` 询问数据目录并生成配置。默认数据目录是 `~/clinical`。

## 使用示例

可用类似下面的中文请求触发：

```text
提取临床数据: <URL>
```

```text
查询某个药品的临床试验
```

```text
更新药品索引
```

```text
整理某个药品的所有临床数据
```

```text
评价这项临床试验数据
```

顶层 `SKILL.md` 会根据请求内容路由到对应子 skill。每个子 skill 都有自己的 workflow，执行时会先读取对应目录下的 `SKILL.md`。

## 数据目录

默认临床数据目录为：

```text
~/clinical
```

目录结构通常为：

```text
~/clinical/
├── raw/          # 原始资料（带 YAML frontmatter）
├── summary/      # 结构化摘要（按药品分子目录组织：summary/{药品名}/）
├── drug/         # 药品索引（平铺：{药品名}.md）
├── indication/   # 适应症索引
├── trials/       # 临床试验查询结果
└── attachments/  # 图片附件
```

各子目录的职责：

| 目录 | 职责 | 写入方 |
| --- | --- | --- |
| `raw/` | 工具（tavily_extract / pdftotext 等）的原始输出，禁止大模型改写 | clinical-extractor、batch-extractor |
| `summary/` | 结构化临床摘要，按药品分子目录组织，必须通过数据一致性审核 | clinical-extractor、batch-extractor |
| `drug/` | 药品索引，按药品平铺，一药一文件 | clinical-extractor、clinical-indexer、drug-trials-search |
| `indication/` | 适应症索引，按适应症平铺 | clinical-indexer |
| `trials/` | 临床试验注册查询的原始结果 | drug-trials-search |
| `attachments/` | 图片附件 | clinical-extractor（多模态提取） |

共享配置位于：

```text
clinical-research/config.yaml
```

## 注意事项

- 不要提交患者隐私数据、API key、账号凭证、未公开资料或商业敏感文件。
- 生成数据的 `.gitignore` 已默认排除 `raw/`、`summary/`、`drug/`、`indication/`、`trials/`、`attachments/`，避免把生产数据写入仓库。
- 生成的摘要和索引应保留来源链接，重要数据建议人工复核。
- 本 skill 用于研究资料整理和分析辅助，不构成医学建议、投资建议或监管判断。

## 许可证

本项目使用 MIT License，详见 `LICENSE`。
