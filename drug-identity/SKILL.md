---
name: drug-identity
description: |
  药品身份与 2.0 归档位置解析工具。不从主接口直接触发，由编排层按需调用。
---

# 药品身份与归档位置解析

> 本文件不从主接口直接触发，由编排层按需调用。
> 本 skill 是 `drug_id`、归档公司和药品目录的唯一确定入口；其他 skill 不得自行决定或迁移这些值。

## 配置与 2.0 布局

配置只读取 `../config.yaml` 中的 `research_dir`。所有路径均由它派生：

```text
{research_dir}/
├── index.md
├── indication/
└── {company_id}/
    └── {drug_id}/
        ├── {drug_id}.md
        ├── raw/
        └── summary/
```

定义：

- `company_id` 是归档公司目录名，不是单独的公司实体页。
- `research_dir` 本身是 Obsidian vault 根目录，不存在中间 `company/` 容器。
- 不创建、读取或链接 `company.md`。
- `drug_dir = {research_dir}/{company_id}/{drug_id}`。
- `drug_page = {drug_dir}/{drug_id}.md`。
- `raw_dir = {drug_dir}/raw`。
- `summary_dir = {drug_dir}/summary`。
- 本 workflow 不支持旧版平铺目录，不执行迁移或兼容查找。

## 核心规则

1. **先查根索引**：始终先读 `{research_dir}/index.md`。它是 `drug_id`、通用名、别名、药品链接和现有归档公司的权威快速查询入口。
2. **集中维护公司规则**：公司别名和所有权规则只在根 `index.md` 中集中维护，不分散到药品页或公司页。
3. **同药同 ID**：同一药品的任意研发代号、合作方代号、通用名或商品名都解析为同一个 `drug_id`。
4. **保留既有归档**：根索引已有明确归档公司时必须沿用；不因股权、授权或上市状态变化迁移目录。
5. **不猜测**：身份、公司归属或冲突无法可靠消解时，停止并询问用户；确认前不创建文件或目录。
6. **幂等创建**：重复解析不得产生第二套目录、第二个药品页或重复索引项。

## 调用模式

调用方必须显式传入模式；未传入时停止，不得猜测：

- `resolve_only`：只读解析配置、根索引和可靠 web 来源，返回身份及既有或拟议的完整路径；不创建目录，不写药品页或根索引。供 `data-search` 等 no-write 工作流使用。
- `resolve_or_create`：解析后可按 Step 5-6 幂等创建布局并更新根索引。仅写入型编排可使用。

两种模式共用 Step 1-4。`resolve_only` 在 Step 4 后直接执行只读版 Step 7；新药可返回 `status: resolved` 和拟议路径，但不得暗示路径已存在。只有 `resolve_or_create` 执行 Step 5-6。

## 标识符语法

`company_id`、`drug_id` 必须是 1-80 个 Unicode 字符的单一路径组件。允许中文、ASCII 字母、数字、空格、`.`、`_`、`-`；禁止控制字符及 `< > : " / \\ | ? * @ # % [ ] ^`，不得为 `.` 或 `..`，不得以空格或句点结尾，也不得是 Windows 保留设备名（不区分大小写，包括带扩展名形式）。既有索引值不合规时停止并报告，不得静默改写。

## Step 1: 读取配置与根索引

读取 `../config.yaml` 的唯一配置项 `research_dir`，然后首先读取 `{research_dir}/index.md`。

如果配置、`research_dir` 或根索引不可读，停止并报告具体原因。不得从其他配置项猜测路径，也不得跳过根索引直接搜索目录或 web。

使用输入名称对根索引中的以下字段进行规范化匹配：

- `drug_id`
- 通用名
- `drug_aliases`（研发代号、合作方代号、其他通用名和商品名）

匹配应忽略无语义的大小写和首尾空白差异，但不得用模糊相似度把两个药物合并。

命中一个唯一条目时：

- 以索引中的 `drug_id` 和药品链接为准。
- 从链接解析 `company_id`、`drug_dir` 和 `drug_page`，并派生 `raw_dir`、`summary_dir`。
- 校验链接必须符合 `{company_id}/{drug_id}/{drug_id}.md` 的 2.0 布局。
- 不重新选择公司，不迁移现有归档。

若多个条目命中同一输入、索引字段互相冲突，或链接与记录的 `drug_id` 不一致，停止并向用户列出冲突，不静默选取或修改。

## Step 2: 补充确认药品身份

根索引未命中时，使用可靠 web 来源确认身份：

1. 搜索 `{名称} 公司`、`{名称} clinical trial`。
2. 优先核对公司官网管线、监管文件、试验注册和可靠文献。
3. 收集研发代号、合作方代号、中文/英文通用名和商品名。
4. 确认靶点、分子类型、原研方、合作方和当前所有权关系。
5. 再次用已确认的全部别名查询根索引，防止重复建档。

所有身份字段必须有根索引或 web 来源，不得从命名形式猜测。若无法唯一确认，返回候选和歧义点并询问用户；不创建任何内容。

## Step 3: 确定 drug_id

仅在根索引没有既有条目时，按以下优先级确定稳定、简短且 Windows-safe 的 `drug_id`：

```text
开发代码 > 短名称/缩写 > 中文通用名 > 英文通用名
```

`drug_id` 是目录名和药品页文件名。其他名称统一作为 `drug_aliases`；通用名单独作为常用展示名。候选必须满足上述严格标识符语法。

如果候选 `drug_id` 已被根索引中的另一药物占用，停止并询问用户，不自动加后缀。

## Step 4: 选择归档公司

根索引没有既有归档时，按以下顺序选择唯一 `company_id`：

1. **现有分配优先**：若根索引通过其他已确认别名命中，沿用该条目的公司目录；此规则高于以下全部规则。
2. **最接近药品的中国上市实体**：选择所有权或运营链条中离药品最近的中国上市实体。直接持有/运营该药品的上市经营实体优先于其上市母公司或更高层上市公司。
3. **同层级原研优先**：多个候选与药品距离相同时，选择原研方。
4. **海外上市原研**：不存在合适的中国上市实体时，选择海外上市原研方。
5. **全部私有时选原研**：相关实体均为未上市公司时，选择原研方。
6. **仍无法确定则询问**：所有权链不清、授权与持有关系冲突或候选仍并列时，列出依据并请用户决定。

`company_id` 和目录使用公司的常用短名称，而非法律全称：

- 中国和日本公司通常使用常见中文短名。
- 西方公司通常使用常见英文短名。
- 名称必须是单个 Windows-safe 路径组件。
- 名称可以包含中文，不要求仅含 ASCII；不得含 Windows 禁止字符、保留设备名，也不得以空格或句点结尾。
- 根索引已有公司别名映射时，必须使用其规范短名。

公司选择只确定归档位置，不表达永久所有权。后续所有权变化更新根索引规则或药品信息，但不自动迁移已有目录。

## Step 5: 创建药品布局（仅 `resolve_or_create`）

身份和归档公司均确认后，创建或补齐：

```text
{research_dir}/{company_id}/{drug_id}/
{research_dir}/{company_id}/{drug_id}/{drug_id}.md
{research_dir}/{company_id}/{drug_id}/raw/
{research_dir}/{company_id}/{drug_id}/summary/
```

幂等行为：

- 目录不存在时创建 `drug_dir`、`raw_dir` 和 `summary_dir`。
- 药品页不存在时，按当前 2.0 drug schema 创建最小骨架，写入已确认的身份字段；不虚构临床内容。
- 药品页存在时保留人工内容，只补充明确缺失的身份字段和新确认别名。
- 已有值与新证据冲突时不覆盖，记录冲突并询问用户。
- 任一步创建或写入失败时停止，报告已完成和失败的路径；不得让调用方假定布局完整。

## Step 6: 串行更新根索引（仅 `resolve_or_create`）

药品布局成功后再更新 `{research_dir}/index.md`：

- 新药新增一个可由 `drug_id`、通用名和任一 alias 快速命中的条目。
- 记录规范 `company_id` 和指向药品页的完整 vault 路径 wikilink。
- 链接使用完整 vault 路径 wikilink `[[{company_id}/{drug_id}/{drug_id}.md|{drug_id}]]`，不得添加 `research/` 或 `company/` 前缀。
- 公司新别名或本次确认的所有权规则写入根索引的集中区域。
- 保留用户编辑、未知字段和无关排版；仅修改本次条目所需的最小范围。
- 写入前重新读取根索引并重新检查冲突，避免覆盖并发编辑。
- 已有等价条目或别名时合并缺失信息，不重复追加。
- 不因所有权变化迁移既有药品目录。

根索引更新失败时返回失败，不得把仅创建了目录视为完整成功。

## Step 7: 验证并返回

完成后重新读取根索引和药品页，验证：

- 输入名称和全部已确认 `drug_aliases` 唯一命中同一 `drug_id`。
- 索引链接、`company_id` 和实际路径一致。
- `drug_page` 存在，`raw_dir` 与 `summary_dir` 是目录。
- 重复执行不会创建额外条目、页面或目录。

返回标准身份与位置对象：

```text
drug_id: {drug_id}
common_name: {通用名}
drug_aliases: {别名列表}
target: {最简形式}
archive_company: {归档公司短名，与 company_id 一致}
company_ids: {原研方、当前权利方及合作方对应的根索引规范 company_id 列表}
companies: {仅兼容字段；如返回，必须与 company_ids 完全相同，不得放展示名或关系描述}
company_relationships: {可选；company_id + role 对象列表，不参与路径解析}
molecule_type: {类型}
company_id: {归档公司短名}
research_dir: {配置解析后的绝对路径}
drug_dir: {research_dir/company_id/drug_id 的绝对路径}
drug_page: {drug_dir/drug_id.md 的绝对路径}
raw_dir: {drug_dir/raw 的绝对路径}
summary_dir: {drug_dir/summary 的绝对路径}
attachments_dir: {research_dir/attachments 的绝对路径}
mode: {resolve_only|resolve_or_create}
status: {resolved|created|existing|updated}
```

若尚未解决身份、归档公司或冲突，只返回问题和候选，不返回可供后续写入使用的成功对象。
