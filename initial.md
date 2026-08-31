# clinical-research 2.0 首次初始化

本文档指导 agent 在安装 skill 后创建全新的 2.0 研究目录。它不迁移、读取或改写 v1 数据。

用户可以发送：

```text
请按照 clinical-research/initial.md 初始化临床研究目录。
```

## 初始化约定

- 默认研究目录：`~/research`
- 本地配置：`{clinical_research_dir}/config.yaml`
- 配置只允许一个字段：`research_dir`
- `research_dir` 必须先展开并解析为当前系统的绝对路径；禁止将 `~` 原样写入配置
- 文件操作须兼容 Windows，使用 Python 3.10+ 标准库和 `pathlib`，不依赖 Unix 工具
- `research_dir` 本身是 Obsidian vault 根目录，不创建中间 `company/` 根容器
- 不执行 v1 迁移，不创建全局 `raw/`、`summary/`、`drug/`、`trials/` 或 `company.md`

初始化后的空目录结构：

```text
~/research/
├── index.md
├── indication/
├── attachments/
└── .temp/
    └── plans/
```

药品创建后的结构为：

```text
{research_dir}/{company_id}/{drug_id}/
├── {drug_id}.md
├── raw/{drug_id}@{source_label}.md
└── summary/{drug_id}@{source_label}.md
```

一个来源只允许一份 raw 和一份同名 summary。一份 summary 可以包含多个适应症。

## Agent 初始化步骤

### 1. 确认研究目录

询问用户：

```text
请提供 clinical-research 的研究目录。未指定时使用默认值：~/research
```

如果用户没有指定，使用 `Path.home() / "research"`。如果用户指定路径，用 `Path(...).expanduser().resolve()` 解析。解析结果必须为绝对路径；下面以 `{research_dir}` 表示该结果。

如果 `config.yaml` 已存在，不得直接覆盖。先验证它是否只含绝对路径字段 `research_dir`；有效时结束初始化，无效时说明原因并询问用户是否重新生成。不得把 v1 配置字段转换为 2.0，也不得迁移旧目录。

### 2. 生成 config.yaml

在当前 skill 顶层目录写入：

```yaml
research_dir: C:/Users/example/research
```

实际值使用当前系统解析出的绝对路径。Windows 路径推荐用 `Path.as_posix()` 的正斜杠形式，避免 YAML 反斜杠转义；POSIX 示例为 `/home/example/research`。不得添加派生子目录字段。

### 3. 创建目录与 index.md

优先使用 harness 的文件能力。需要脚本时，使用以下跨平台 Python 逻辑，不调用 shell 目录或文本工具：

```python
from pathlib import Path

research_dir = Path(r"{research_dir}").expanduser().resolve()
for relative in ("indication", "attachments", ".temp/plans"):
    (research_dir / relative).mkdir(parents=True, exist_ok=True)

index_path = research_dir / "index.md"
if not index_path.exists():
    index_path.write_text(INDEX_SKELETON, encoding="utf-8")
```

将下面内容作为 `INDEX_SKELETON`。只在 `index.md` 不存在时创建；存在时保留用户编辑，不覆盖。初始化不创建任何公司目录；公司目录只在创建药品时作为 vault 根目录的直接子目录出现。

```markdown
# Clinical Research Index

这是研究库的第一查询入口。Agent 和用户均可编辑；请保留别名、歧义说明和用户已有内容。

## 药品

| drug_id | 通用名 | aliases | 靶点 | 归档公司 |
|---------|--------|---------|------|----------|

## 公司

| company_id | 中文名 | 英文名 | aliases |
|------------|--------|--------|---------|
| 第一三共 | 第一三共 | Daiichi Sankyo | 第一三共株式会社; Daiichi Sankyo Co., Ltd. |
| 武田制药 | 武田制药 | Takeda Pharmaceutical | 武田; Takeda |
| 恒瑞医药 | 恒瑞医药 | Jiangsu Hengrui Pharmaceuticals | 恒瑞; Hengrui |
| 百济神州 | 百济神州 | BeOne Medicines | BeiGene; BeOne; 百济 |
| 石药集团 | 石药集团 | CSPC Pharmaceutical Group | CSPC; 石药 |
| 石药创新 | 石药创新 | CSPC Innovation | 新诺威; CSPC Innovation Pharmaceutical |
| AstraZeneca | 阿斯利康 | AstraZeneca | AZ |
| Roche | 罗氏 | Roche | Hoffmann-La Roche; 罗氏制药 |
| Novartis | 诺华 | Novartis | 诺华制药 |
| Pfizer | 辉瑞 | Pfizer | Pfizer Inc. |
| BMS | 百时美施贵宝 | Bristol Myers Squibb | BMS; Bristol-Myers Squibb |
| Eli Lilly | 礼来 | Eli Lilly and Company | Lilly; 礼来制药 |
| AbbVie | 艾伯维 | AbbVie | AbbVie Inc. |
| Amgen | 安进 | Amgen | Amgen Inc. |
| Gilead | 吉利德 | Gilead Sciences | 吉利德科学 |
| Sanofi | 赛诺菲 | Sanofi | Sanofi S.A. |
| GSK | 葛兰素史克 | GSK | GlaxoSmithKline |
| MSD | 默沙东 | Merck & Co. | MSD; Merck Sharp & Dohme; 美国默克 |
| Merck KGaA | 德国默克 | Merck KGaA | EMD Serono; EMD Electronics |

## 适应症

| indication_id | 适应症 | 类别 | 治疗线 | 生物标志物 | 更新 |
|---------------|--------|------|--------|------------|------|

## Editing Rules

- 查找公司或药品时先查本文件，再访问对应路径。
- 别名用分号分隔；匹配到多个实体时必须消歧，不得猜测。
- 创建药品时补充药品行；第一列使用 `[[{company_id}/{drug_id}/{drug_id}.md|{drug_id}]]`。
- 创建适应症页时补充适应症行；第一列使用 `[[indication/{indication_id}.md|{indication_id}]]`。
- Agent 更新时保留用户添加的行、别名和备注。
```

公司表条目不代表已创建公司实体，因此不得据此创建公司文件夹。`company_id` 使用 Windows-safe 的常见公司短名且可以包含中文：中日公司通常使用常见中文短名，西方公司通常使用常见英文短名。新增药品时才创建 `{research_dir}/{company_id}/{drug_id}/{raw,summary}` 和 `{drug_id}.md`，并更新药品表。

### 4. 验证结果

用 `pathlib` 检查：

```text
{research_dir}/index.md
{research_dir}/indication/
{research_dir}/attachments/
{research_dir}/.temp/plans/
```

同时验证：

- `config.yaml` 只包含绝对 `research_dir`。
- 没有因初始化而生成任何公司目录，也没有 `company/` 根容器。
- `index.md` 含药品、公司、适应症和 Editing Rules 四节，表头符合 `schema/index-spec.md`。
- 后续扫描 vault 根目录时排除 `indication/`、`attachments/`、`.temp/`、所有隐藏目录和其他已知基础设施目录，不能将其视为公司。
- 未创建 v1 全局内容目录或 `company.md`。

### 5. 完成提示

初始化完成后报告配置路径、绝对研究目录和已创建项目，并提示用户可使用：

```text
提取临床数据: <URL>
对某个药品建库
查询某个药品的临床试验
更新临床数据索引
```
