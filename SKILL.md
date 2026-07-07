---
name: clinical-research
description: |
  临床数据研究与分析工具集的路由入口。**触发后负责路由到正确的子skill并执行其workflow！**
  
  ### 何时触发（满足任一即触发）
  - 用户提到"提取临床数据"
  - 用户提到"扫描/批处理临床数据"  
  - 用户提到"更新/同步/重建索引"
  - 用户提到"整理临床数据" / "归档临床数据" / "整理数据" / "归档数据"
  - 用户提到"扫描未整理的临床数据" / "同步临床数据到索引"
  - 用户提到"更新药品索引" / "更新适应症索引" / "clinical-wiki"
  - 用户提到"汇总药品临床数据"
  - 用户提到"生成药品索引"
  - 用户提到"整理{药品名}的所有数据"
  - 用户提到"把{药品名}的数据汇总到drug/下面"
  - 用户提到"drug summarizer"
  - 用户提供URL/PDF并要求提取临床数据
  - 用户提到"查询药品临床试验" / "搜索临床试验"
  - 用户提到药品名称 + "临床试验"（如"PD-1临床试验"）
  - 用户提到"评价临床数据" / "评估临床试验" / "怎么看这个数据"
---

# Clinical Research

## ⚠️ 执行约束（触发后必须遵守）

### 强制流程
1. **立即读取对应子skill的SKILL.md**（禁止直接回答！）
2. **按子skill的workflow逐步执行**
3. **必须完成所有steps**

### 禁止事项
- ❌ 禁止直接调用工具提取内容
- ❌ 禁止不读子skill就直接回答
- ❌ 禁止跳过workflow步骤
- ❌ 默认禁止spawn子agent；除非对应子skill的workflow明确要求 reviewer/verifier subagent

## 数据目录

数据统一存放在：`/mnt/ur/notes/资料/clinical/`

```
/mnt/ur/notes/资料/clinical/
├── raw/          # 原始资料（带YAML frontmatter）
├── source/       # 规范摘要（按 schema/summary-spec.md 格式）
├── drug/         # 药品索引
├── indication/   # 适应症索引
├── trials/       # 临床试验查询结果
└── attachments/  # 图片附件
```

## 路由规则

根据用户输入判断应读取哪个子skill：

| 用户输入 | 子 Skill | 动作 |
|---------|---------|------|
| "提取临床数据"、包含 URL | clinical-extractor | 完整流程: URL → raw/ → source/ |
| 包含 PDF | clinical-extractor | 提取 PDF 并生成摘要 |
| "扫描/批处理临床数据" | batch-extractor | 批量: raw/ → source/ |
| "更新/同步/扫描/重建索引" | clinical-indexer | source/ → drug/, indication/ |
| "整理临床数据" / "归档临床数据" / "整理数据" | clinical-wiki | 扫描未整理的source → 按药品/适应症归档 |
| "扫描未整理的临床数据" / "同步临床数据到索引" | clinical-wiki | 增量整理未归档的数据 |
| "更新药品索引" / "更新适应症索引" | clinical-wiki | 按 drug/indication 维度更新索引 |
| **"汇总药品临床数据" / "生成药品索引" / "整理{药品名}的所有数据"** | **clinical-drug-summarizer** | **扫描source/下某药品的所有数据 → 生成drug/{药品名}.md** |
| "查询药品临床试验" / "搜索临床试验" | drug-trials-search | Python脚本查询 CTG + CDT |
| 药品名称 + "临床试验" | drug-trials-search | 生成表格，列出所有结果 |
| "评价临床数据" / "评估临床试验" / "怎么看这个数据" | clinical-trial-evaluator | 提供系统化的试验数据评价框架 |
| 无明确指令 | clinical-indexer | 批量扫描并更新所有索引 |

## 核心原则

- **Source-first**: 原始资料绝不修改，只写入 clinical/ 目录
- **Incremental**: 支持增量更新，避免重复处理
- **Structured**: 严格的命名规范和数据格式
- **Controlled-spawn**: 默认在当前session完成；仅当子skill明确要求独立审核/验证时，允许spawn受限subagent

## 常见错误（避免）

❌ **错误**：看到URL就直接 `tavily_extract` 提取内容给用户  
✅ **正确**：先读 `clinical-extractor/SKILL.md`，按workflow执行

❌ **错误**：跳过YAML frontmatter直接保存内容  
✅ **正确**：严格添加 `source:` 和 `created:` 到raw/文件

❌ **错误**：source/文件命名随意  
✅ **正确**：使用 `{药品}@{适应症}.md` 格式
