---
name: drug-identity
description: |
  药品身份与 2.0 归档位置解析工具。不从主接口直接触发，由编排层按需调用。
---

# 药品身份与归档位置解析

## 责任与边界

- 本 skill 不从主接口直接触发，由编排层按需调用。
- 本 skill 是完整标准身份与位置对象，以及 `drug_id`、归档公司和药品目录的唯一确定入口。其他 skill 只能原样传递该对象，不得自行决定、删改字段、重算路径或迁移归档。
- 只支持 2.0 布局；不支持旧版平铺目录，不迁移或兼容查找。
- `company_id` 仅表示归档公司目录，不是公司实体页；不创建、读取或链接 `company.md`。

## 输入与共享契约

只读取 `../config.yaml` 中的 `research_dir`。它是 Obsidian vault 根目录，所有路径由它派生：

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

```text
drug_dir = {research_dir}/{company_id}/{drug_id}
drug_page = {drug_dir}/{drug_id}.md
raw_dir = {drug_dir}/raw
summary_dir = {drug_dir}/summary
```

调用方必须显式传入模式；缺失时停止，不得猜测：

| 模式 | 读取与解析 | 创建/写入 | 新药返回 |
|---|---|---|---|
| `resolve_only` | 配置、根索引、可靠 web 来源 | 禁止创建目录，禁止写药品页或根索引 | 可返回 `status: resolved` 和拟议路径，但不得暗示路径存在 |
| `resolve_or_create` | 与 `resolve_only` 相同 | 可按流程幂等创建布局并更新根索引 | 返回实际创建或更新状态 |

完整对象中容易混淆的公司字段：

| 字段 | 含义 | 约束 |
|---|---|---|
| `archive_company` | 归档公司短名 | 必须与 `company_id` 一致 |
| `company_id` | 唯一归档目录名 | 决定路径，不表达永久所有权 |
| `company_ids` | 原研方、当前权利方及合作方对应的根索引规范 ID 列表 | 不参与归档路径选择 |
| `companies` | 兼容字段 | 如返回，必须与 `company_ids` 完全相同，不得包含展示名或关系描述 |
| `company_relationships` | 可选的 `company_id + role` 对象列表 | 不参与路径解析 |

`company_id`、`drug_id` 必须通过 `scripts/layout.py:is_valid_identifier`：长度 1-80，首字符为 Unicode 字母或数字，内部仅允许 Unicode 字母/数字、空格、`.`、`_`、`-`，不得以空格或句点结尾，也不得是 Windows 保留设备名。既有索引值不合规时停止并报告，不得静默改写。

## 不变量与写入策略

| 不变量 | 策略 |
|---|---|
| 根 `index.md` 是 `drug_id`、通用名、aliases、药品链接、归档公司、公司 aliases 和所有权规则的权威快速索引 | 始终先读根索引；公司规则只集中维护在此 |
| 同一药品的研发代号、合作方代号、通用名和商品名共享一个 `drug_id` | 匹配忽略无语义的大小写和首尾空白，但禁止模糊相似度合并 |
| 既有归档优先 | 沿用索引中的公司和链接，不因股权、授权或上市状态变化迁移目录 |
| 身份和归属不得猜测 | 无法可靠消歧时停止并询问；确认前不创建内容 |
| 创建和更新必须幂等 | 不生成第二套目录、第二个药品页或重复索引项 |
| 用户内容优先 | 只补明确缺失字段；冲突不覆盖，保留人工内容和无关排版 |
| 写入串行且防并发覆盖 | 药品布局成功后才更新根索引；写前重读并复查冲突 |

## 流程

### 1. 读取配置与根索引

读取 `../config.yaml` 的唯一配置项 `research_dir`，然后首先读取 `{research_dir}/index.md`。任一不可读时停止并报告；不得猜测路径、跳过根索引搜索目录或 web。

用输入名称匹配 `drug_id`、通用名和 `drug_aliases`。唯一命中时以索引中的 `drug_id` 和链接为准，从链接解析 `company_id`、`drug_dir`、`drug_page`，派生 `raw_dir`、`summary_dir`，并校验链接符合 `{company_id}/{drug_id}/{drug_id}.md`。多个条目命中、字段冲突或链接与 `drug_id` 不一致时，列出冲突并停止。

### 2. 补充确认身份

根索引未命中时：

1. 搜索 `{名称} 公司`、`{名称} clinical trial`。
2. 优先核对公司官网管线、监管文件、试验注册和可靠文献。
3. 收集研发代号、合作方代号、中文/英文通用名和商品名。
4. 确认靶点、分子类型、原研方、合作方和当前所有权关系。
5. 用全部已确认别名再次查询根索引，防止重复建档。

所有身份字段必须有根索引或 web 来源，不得从命名形式猜测。无法唯一确认时返回候选和歧义点并询问用户。

### 3. 确定 `drug_id`

仅对根索引无既有条目的药品，按以下优先级选择稳定、简短且 Windows-safe 的 ID：

```text
开发代码 > 短名称/缩写 > 中文通用名 > 英文通用名
```

其他名称写入 `drug_aliases`，通用名单独作为常用展示名。候选被另一药物占用时停止并询问，不自动加后缀。

### 4. 选择归档公司

根索引无既有归档时，依次选择唯一 `company_id`：

1. 其他已确认别名命中的既有分配。
2. 所有权或运营链条中离药品最近的中国上市实体；直接持有/运营实体优先于上市母公司或更高层公司。
3. 距离相同时选原研方。
4. 无合适中国上市实体时选海外上市原研方。
5. 相关实体均未上市时选原研方。
6. 所有权链不清、授权与持有关系冲突或候选并列时，列出依据并询问用户。

使用公司常用短名而非法律全称：中国和日本公司通常用常见中文短名，西方公司通常用常见英文短名；根索引已有 alias 映射时必须用其规范短名。名称可含中文，但必须满足标识符语法。公司选择只确定归档位置；所有权变化可更新信息，但不自动迁移目录。

`resolve_only` 至此直接执行只读验证与返回。只有 `resolve_or_create` 继续第 5-6 步。

### 5. 幂等创建布局（仅 `resolve_or_create`）

身份和归档公司确认后，创建或补齐 `drug_dir`、`drug_page`、`raw_dir` 和 `summary_dir`。药品页不存在时按当前 2.0 drug schema 创建最小骨架，仅写已确认身份字段；存在时保留人工内容，仅补缺失身份字段和新确认 aliases。冲突不覆盖，改为记录并询问。

### 6. 串行更新根索引（仅 `resolve_or_create`）

布局成功后重读 `{research_dir}/index.md` 并复查冲突，再最小更新：新药新增可由 `drug_id`、通用名和任一 alias 命中的条目；记录规范 `company_id`；药品链接固定为完整 vault 路径 `[[{company_id}/{drug_id}/{drug_id}.md|{drug_id}]]`，不得添加 `research/` 或 `company/` 前缀；公司 aliases 和所有权规则写入集中区域。等价条目合并缺失信息，不重复追加，不重排无关内容，不迁移既有目录。

### 7. 验证

重新读取根索引和药品页，验证全部已确认 aliases 唯一命中同一 `drug_id`，索引链接、`company_id` 和实际路径一致，`drug_page` 存在，`raw_dir`、`summary_dir` 为目录，且重复执行不会新增条目、页面或目录。`resolve_only` 只验证既有路径；拟议路径不得按已存在验证。

## 失败与恢复

- 配置、根索引、身份、公司、标识符或链接存在问题时，停止并报告具体原因和候选；不返回可供写入的成功对象。
- 任一步创建或写入失败时停止，报告已完成路径和失败路径，不让调用方假定布局完整。
- 根索引更新失败时整体返回失败；仅创建目录不算完整成功。
- 冲突必须由用户消歧；恢复后从第 1 步重读当前状态，禁止依赖旧快照。

## 输出

本 skill 是以下完整标准身份与位置对象的唯一契约：

```text
drug_id: {drug_id}
common_name: {通用名}
drug_aliases: {别名列表}
target: {最简形式}
archive_company: {归档公司短名，与 company_id 一致}
company_ids: {原研方、当前权利方及合作方对应的根索引规范 company_id 列表}
companies: {仅兼容字段；如返回，必须与 company_ids 完全相同}
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

身份、归档公司或冲突尚未解决时，只返回问题和候选，不返回成功对象。
