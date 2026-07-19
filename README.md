# 临床研究 Codex Skill

这是一个面向临床研究资料整理、结构化提取、索引更新和临床数据评价的 Codex skill。它会根据用户请求自动路由到对应的子 skill，帮助把 URL、PDF、公告、会议资料等来源整理为可追溯的临床数据知识库。

## 主要功能

- 从 URL 或 PDF 中提取临床研究资料，保存为原始资料。
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
| `clinical-indexer/` | 根据 summary 摘要生成或更新药品、适应症索引。 |
| `clinical-wiki/` | 将未归档的 summary 摘要整理到 drug 和 indication 维度。 |
| `clinical-drug-summarizer/` | 汇总某个药品的全部临床数据，生成药品页。 |
| `drug-trials-search/` | 查询临床试验注册信息，并写入药品管线表。 |
| `clinical-trial-evaluator/` | 按结构化框架评价临床试验数据。 |
| `schema/` | 临床摘要、药品索引、适应症索引的 Markdown 格式规范。 |

## 安装方式

将 `clinical-research` 目录放到 Codex 的 skills 目录下：

```text
<CODEX_HOME>/skills/clinical-research/
```

也可以通过 Git 克隆后，再复制或链接到 skills 目录：

```bash
git clone https://github.com/abinww/clinical-research.git
```

如果希望让 agent 自动安装，可以让 agent 读取仓库根目录下的 `install.md`。安装完成后，再让 agent 按 `initial.md` 完成首次初始化。

## 使用示例

可以用类似下面的中文请求触发：

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

顶层 `SKILL.md` 会根据请求内容选择对应子 skill。每个子 skill 都有自己的 workflow，执行时应先读取对应目录下的 `SKILL.md`。

## 数据目录

默认临床数据目录为：

```text
~/clinical
```

目录结构通常为：

```text
~/clinical/
├── raw/          # 原始资料
├── summary/      # 结构化摘要（按药品分子目录组织：summary/{药品名}/）
├── drug/         # 药品索引（平铺：{药品名}.md）
├── indication/   # 适应症索引
├── trials/       # 临床试验查询结果
└── attachments/  # 图片附件
```

共享配置位于：

```text
config.yaml
```

首次运行时如果尚未生成 `config.yaml`，skill 会按 `initial.md` 询问数据目录并生成配置。默认数据目录是 `~/clinical`。

## 注意事项

- 不要提交患者隐私数据、API key、账号凭证、未公开资料或商业敏感文件。
- 生成的摘要和索引应保留来源链接，重要数据建议人工复核。
- 本 skill 用于研究资料整理和分析辅助，不构成医学建议、投资建议或监管判断。

## 许可证

本项目使用 MIT License，详见 `LICENSE`。
