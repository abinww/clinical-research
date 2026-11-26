# clinical-research Skill 维护规范

本文件规定本仓库各文件如何分工，避免同一规则在多个文件中重复或冲突。它不定义研究库数据格式。

## 职责分界

- `SKILL.md`：触发条件、身份解析、工作流程、工具调用、来源获取与转换、失败恢复、运行时状态。
- `schema/*-spec.md`：研究库中持久化文档的格式，包括路径、字段、章节、表格、链接和允许内容。每种持久化文件只能有一个权威 spec。
- `scripts/`、`tests/`：实现并机械校验 spec；不得自行引入新的格式规则。
- `README.md`、`install.md`、`initial.md`：项目说明、安装和一次性初始化；不重复定义持久化格式。
- 本文件：Skill 的维护规则，不是研究数据 schema。

## 写作边界

- 格式放 spec：新增或修改 frontmatter、章节、表格、列、链接写法时，只修改对应 spec；SKILL 只引用。
- 操作放 SKILL：URL/PDF 获取、PDF 大小分流、附件复制、文本/图表提取、重试和替换事务属于工作流程，写在执行它的 SKILL。
- spec 不规定来源怎么处理，只规定处理后的文件应是什么样。
- raw 和 summary 是不同持久化文件，分别由独立 spec 定义；不得在 summary spec 中定义 raw 格式。
- 临时状态不另立 spec：`config.yaml` 由初始化文档定义；临时 plan 由拥有续跑和持久化流程的 workflow 定义；运行时报告由产出它的 SKILL 定义。
- 跨 skill 共用的规范 ID 和路径规则集中在一个共享 spec；运行时对象字段由产出对象的 skill 定义，其他 skill 原样传递。

## 引用与修改

- 引用其他文件时写明相对路径，不只写文件名：
  - 根目录文件引用 schema：`schema/summary-spec.md`
  - 子目录 skill 引用 schema：`../schema/summary-spec.md`
  - schema 之间引用：`summary-spec.md`
- 修改前先定位权威 spec，再同步其调用方、脚本和测试；不得在调用方复制同一规则。
- 同一规则出现冲突时，以对应 spec 为唯一裁决；SKILL 只描述何时、如何调用，不另设格式例外。
- 修改后检查：是否新增了重复定义、是否仍有旧规则残留、路径引用是否可解析、脚本/测试是否仍与 spec 一致。
