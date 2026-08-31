# 根索引格式规范 (2.0)

本文件定义 `{research_dir}/index.md`。`research_dir` 本身是 Obsidian vault 根目录。该文件由 agent 生成和更新，同时允许用户直接编辑；自动更新必须保留用户新增的有效内容，不得整文件覆盖。

## 职责

`index.md` 是全库导航入口和公司身份中心，包含：

- 药品表：定位每个药品及其通用名、别名、靶点和归档公司。
- 公司表：集中维护 `company_id`、中英文名和全部公司别名。
- 适应症表：定位已建立的具体适应症页。

不建立 `company.md`。任何公司别名解析都以根索引的公司表为唯一来源，不得在药品页、摘要页或适应症页维护重复映射。

## 文件属性

- 固定路径：`{research_dir}/index.md`，即 vault 根目录的 `index.md`。
- 不要求 YAML frontmatter；如项目需要元数据，只允许稳定的文件级字段，不得把公司别名拆入 frontmatter。
- agent 更新前必须解析现有表格，按稳定 ID 合并，不得删除用户添加的列、说明或仍有效的行。
- 用户内容与自动数据冲突时，不得静默覆盖；应保留现值并标记待确认。

## 正文结构

```markdown
# Clinical Research Index

## 药品

<!-- clinical-research:begin drugs -->
| drug_id | 通用名 | aliases | 靶点 | 归档公司 |
|---------|--------|---------|------|----------|
<!-- clinical-research:end drugs -->

## 公司

<!-- clinical-research:begin companies -->
| company_id | 中文名 | 英文名 | aliases |
|------------|--------|--------|---------|
<!-- clinical-research:end companies -->

## 适应症

<!-- clinical-research:begin indications -->
| indication_id | 适应症 | 类别 | 治疗线 | 生物标志物 | 更新 |
|---------------|--------|------|--------|------------|------|
<!-- clinical-research:end indications -->
```

三个核心表不得省略。每张表由上述一对 HTML 注释标记管理，标记内只放一张连续 Markdown 表；可在标记外增加用户说明或其他章节。标记界定 agent 可合并的范围，不表示可以重建整张表：用户添加的列、行和单元格仍须保留。

### 结构识别与阻断

- `## 药品`、`## 公司`、`## 适应症` 每个二级标题必须恰好出现一次；对应的 begin/end 标记也必须各恰好出现一次、顺序正确、不得嵌套或跨章节。
- 每对标记内必须恰有一张语法完整的 Markdown 表，表头、分隔行和每个数据行的单元格数必须一致。wikilink alias 中的 `|` 不计为列分隔符，但在表格内必须写成 `\|`。
- 旧文件若没有某表标记，仅当对应标题唯一、标题下恰有一张可无歧义识别且格式完整的核心表时，才可在不改变表内容的前提下为其补加标记。不得用空模板覆盖旧表。
- 标题重复、标记重复/缺失一端/错序、标记内有多张表、必需主键列缺失或表格畸形时，阻断该核心表的一切自动写入并报告结构冲突。其他结构有效且互不依赖的核心表可继续处理；不得猜测目标、删除重复内容或自动重建。

## 药品表

```markdown
## 药品

<!-- clinical-research:begin drugs -->
| drug_id | 通用名 | aliases | 靶点 | 归档公司 |
|---------|--------|---------|------|----------|
| [[第一三共/DS-8201/DS-8201.md\|DS-8201]] | 德曲妥珠单抗 | T-DXd; trastuzumab deruxtecan; Enhertu | HER2 | 第一三共 |
| [[Pfizer/PF-0001/PF-0001.md\|PF-0001]] | 示例单抗 | PF0001; Examplemab | HER3 | Pfizer |
<!-- clinical-research:end drugs -->
```

- 第一列固定为 `drug_id`，显示值必须是规范 `drug_id`，并在同一单元格链接药品页。
- 不得另建“链接”列，也不得把链接从 `drug_id` 列拆出。
- 链接使用完整 vault 路径 wikilink `[[{company_id}/{drug_id}/{drug_id}.md|{drug_id}]]`，不得添加 `research/` 或 `company/` 前缀。
- `通用名` 使用常用通用名；`aliases` 收录研发代码、其他通用名和商品名，以 `; ` 分隔。
- `归档公司` 必须等于目录的 `company_id`，并存在于公司表。
- 每个 `drug_id` 只保留一行。更新已有表时保持全部现有行的用户顺序，新行按 `drug_id` 的稳定升序组成一个批次并追加到末尾；不得借更新重排旧行。只有新初始化的表，或只有规范表头且没有数据行、自定义列和自定义单元格的 pristine 表，才可对首次生成的全部行排序。

## 公司表

```markdown
## 公司

<!-- clinical-research:begin companies -->
| company_id | 中文名 | 英文名 | aliases |
|------------|--------|--------|---------|
| 第一三共 | 第一三共 | Daiichi Sankyo | Daiichi Sankyo Co., Ltd.; 第一三共株式会社 |
| Pfizer | 辉瑞 | Pfizer | Pfizer Inc.; 辉瑞制药 |
<!-- clinical-research:end companies -->
```

- `company_id` 是稳定、全库唯一的常见公司短名，也是 vault 根目录下的公司目录名。中日公司通常使用常见中文短名，西方公司通常使用常见英文短名。
- `company_id` 长度为 1-80，首尾必须是 Unicode 字母或数字（尾部也可为 `.`/`-`），中间只允许 Unicode 字母/数字/空格/下划线/`.`/`-`；同时不得是 Windows 保留设备名。可以包含中文和内部空格。
- `中文名` 和 `英文名` 分别保存公司的常用中英文名称；没有可靠名称时使用 `—`，不得猜测。
- `aliases` 收录历史名称、简称、中英文名和常见拼写，以 `; ` 分隔；不得把药品别名或证券代码混入。
- 一个别名只能明确归属一个 `company_id`。存在歧义时标记待确认，不得自动合并公司。
- 公司更名时，若目录已存在且无需重命名，保持 `company_id` 稳定，只更新中英文名和 aliases。
- 公司表不链接 `company.md`，因为 2.0 不存在公司页。
- 更新已有表时保持现有行顺序，新公司按 `company_id` 稳定升序批量追加；只有新初始化或 pristine 空表才排序首次生成的全部行。

## 适应症表

```markdown
## 适应症

<!-- clinical-research:begin indications -->
| indication_id | 适应症 | 类别 | 治疗线 | 生物标志物 | 更新 |
|---------------|--------|------|--------|------------|------|
| [[indication/NSCLC_1L.md\|NSCLC_1L]] | 非小细胞肺癌一线 | NSCLC | 1L | — | YYYY-MM-DD |
| [[indication/胃癌_2L.md\|胃癌_2L]] | 胃癌二线 | 胃癌 | 2L | — | YYYY-MM-DD |
<!-- clinical-research:end indications -->
```

- 第一列固定为 `indication_id`，显示值为规范 ID，并在同一单元格链接适应症页。
- 链接使用完整 vault 路径 wikilink `[[indication/{indication_id}.md|{indication_id}]]`，不得添加 `research/` 前缀。
- 只收录已经建立页面的具体适应症；不收录仅存在于摘要中的泛瘤种探索项。
- 每个 `indication_id` 只保留一行。更新已有表时保持现有行顺序，新行按 `indication_id` 稳定升序批量追加；只有新初始化或 pristine 空表才排序首次生成的全部行。

## Agent 更新规则

1. 读取现有 `{research_dir}/index.md`，按 managed markers 定位核心表，并保留标记外全部内容、表内自定义列、已有行顺序和无法由扫描重建的单元格。
2. 扫描有效药品树和适应症页，以 `drug_id`、`indication_id` 为主键 upsert 对应行；药品树有效但药品行缺失时允许补行，不得要求缺失行预先存在。
3. 使用公司表解析药品 frontmatter 中的 `archive_company` 和 `company_ids`；兼容字段 `companies` 如存在必须与 `company_ids` 相同。遇到未知 `company_id` 时标记待确认，不得自行创造别名归并。
4. 新公司只有在身份明确时才追加公司表；不创建公司目录说明页或 `company.md`。
5. 自动更新单元格时只修改可由对应规范文件确认的字段。冲突、重复 ID、失效链接或用户自定义值应报告而非静默覆盖。
6. 保持表头中用户添加的列，并保留这些列的已有单元格内容；新增行的自定义列写空值，不得臆造。
7. 写入后验证所有链接目标、ID 唯一性和公司别名唯一归属。
8. 发现公司目录时只接受符合 `{company_id}/{drug_id}/{drug_id}.md` 语义的直接根子目录；排除 `indication/`、`attachments/`、`.temp/`、所有隐藏目录和其他已知基础设施目录。
9. 表格内 wikilink alias 分隔符必须写成 `\|`；表格外使用普通 `|`，不得把转义形式扩散到正文、引用或列表。

## 验证清单

- [ ] 文件位于 `{research_dir}/index.md`，并包含药品、公司、适应症三个表。
- [ ] 三个核心表分别位于唯一、配对且结构有效的 managed markers 内。
- [ ] 药品表列为 linked `drug_id`、通用名、aliases、靶点、归档公司；公司表列为 `company_id`、中文名、英文名、aliases。
- [ ] 药品表第一列为 `drug_id`，ID 和药品链接位于同一单元格。
- [ ] 适应症表第一列为 `indication_id`，ID 和适应症链接位于同一单元格。
- [ ] 药品和适应症链接均使用完整 vault 路径 wikilink，且不含 `research/` 或 `company/` 前缀。
- [ ] 公司别名只存在于公司表，且每个别名唯一归属一个 `company_id`。
- [ ] 未创建或链接任何 `company.md`。
- [ ] agent 更新保留用户说明、自定义列和无法安全重建的值。
- [ ] 已有行顺序未改变；新增行确定性追加，且表内 wikilink alias pipe 已转义。
- [ ] 药品、公司、适应症 ID 均唯一，链接目标存在。
- [ ] 基础设施根目录未被识别为公司。
