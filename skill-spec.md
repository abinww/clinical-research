# clinical-research Skill 维护规范

本文件规定仓库文档的职责与维护方式，不定义研究库数据格式。

## 职责与权威

- `SKILL.md` 定义本 skill 的触发条件、职责、流程、工具、失败恢复和运行时状态。调用其他 skill 时，只说明本 skill 的调用时机、输入传递、调用顺序和返回处理，并引用其相对路径；不得复制、改写或覆盖被调用 skill 的内部规则。
- `schema/*-spec.md` 定义研究库持久化文档的格式，包括路径、字段、章节、表格、链接和允许内容；每种文档只有一个权威 spec。`raw` 和 `summary` 分别由 `schema/raw-spec.md` 和 `schema/summary-spec.md` 定义。
- `scripts/` 实现已定义的流程和格式，`tests/` 验证其行为与规范，二者不得另行创设格式规则。`README.md`、`install.md`、`initial.md` 说明项目、安装和初始化，不重复定义 schema 已规定的研究库文档格式。
- 跨 skill 共用规则集中在一个权威 spec 或 skill 中；运行时对象由产出它的 skill 定义，其他 skill 原样传递。临时状态不另立 spec：配置由初始化文档定义，plan 由负责续跑的 workflow 定义，运行时报告由产出它的 skill 定义。
- 规则冲突时，以对应的权威 spec 或 skill 为准；其他文件不得另设例外。

## 引用与修改

- 引用文件时使用相对于引用文档所在目录的路径，例如根目录引用 `schema/summary-spec.md`，子 skill 引用 `../schema/summary-spec.md`，schema 之间引用 `summary-spec.md`。
- 修改前先确认权威文件。持久化文档的格式只在对应 spec 中维护，配置和临时状态的格式由上述规则指定的文件定义；工作流程、来源处理、转换和恢复规则写在负责执行的 skill 中。修改后同步调用方、脚本和测试，并检查重复或过时规则、路径有效性及实现一致性。
