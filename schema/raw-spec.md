# 临床原文格式规范 (2.0)

本文件定义研究库中 `raw` 原文文件的持久化格式。

## 文件与命名

- 路径固定为 `{research_dir}/{company_id}/raw/{drug_id}@{source_label}.md`。
- 一个临床来源对应一个 raw；不得把多个网页、PDF、会议摘要或新闻稿合并进同一 raw。
- `drug_id` 必须通过 `../scripts/layout.py:is_valid_identifier`；`source_label` 的语义和语法以 `summary-spec.md` 为权威。
- 文件基名由唯一分隔符 `@` 连接 `drug_id` 与 `source_label`，不包含 `indication_id`。

## Frontmatter

raw frontmatter 固定包含以下三项：

```yaml
---
source: {canonical source}
published_date: {YYYY-MM-DD 或 null}
created: {YYYY-MM-DD}
---
```

| 字段 | 规则 |
|---|---|
| `source` | 必填字符串，持久化来源身份；具体取值见“来源身份”。 |
| `published_date` | 来源明确披露的发布日期，格式 `YYYY-MM-DD`；未披露时为 `null`，不得猜测。 |
| `created` | raw 创建日期，格式 `YYYY-MM-DD`。 |

raw frontmatter 不得增加其他字段。

## 来源身份

`source` 是 raw 的持久来源身份：

- URL 来源保存用户准确提供或明确采用的 canonical final URL。不得 percent decode，也不得为比较而改写大小写、查询参数、尾部斜杠或编码形式。
- `<= 10 MiB` 的本地 PDF：`source` 为附件绝对 POSIX 路径 `{research_dir}/attachments/{drug_id}@{source_label}.pdf`；该附件必须实际存在。
- `> 10 MiB` 的本地 PDF：保存原 PDF 经 `Path.resolve(strict=True).as_posix()` 得到的绝对 POSIX 路径。
- 本地 PDF 不得只保存文件名、相对路径、反斜杠路径或另造路径标识。
- 准确重复键为当前公司布局中的 `(company_id, drug_id, source)`。

## 正文形态

### URL 来源

- 正文为来源抓取结果的完整原始输出。
- 不得压缩、总结、翻译、重排、去重、润色或补全。
- 官方 API 补充缺失 metadata 时，只能在末尾追加独立章节，并注明来源和获取日期。

### `<= 10 MiB` PDF

- 附件路径固定为 `{research_dir}/attachments/{drug_id}@{source_label}.pdf`，且必须实际存在。
- raw 正文只写一行嵌入引用：

```markdown
![[attachments/{drug_id}@{source_label}.pdf]]
```

- 不在 raw 中保存提取文本，避免乱码污染。

### `> 10 MiB` PDF

- raw 正文保存从原 PDF 提取的文本。
- `source` 使用原 PDF 的 resolved absolute POSIX path。

## 验证清单

- [ ] 路径和文件名符合 `{company_id}/raw/{drug_id}@{source_label}.md`。
- [ ] frontmatter 恰好包含 `source`、`published_date`、`created`，类型和格式正确。
- [ ] `source` 是准确 URL，或符合规定的 PDF 绝对 POSIX 路径。
- [ ] `<= 10 MiB` PDF 的附件存在，raw 正文只有嵌入引用。
- [ ] `> 10 MiB` PDF 的 raw 正文保存提取文本。
- [ ] URL raw 正文保留完整工具输出，未被模型改写。
- [ ] 同一来源未合并多个文件，也未按适应症拆分成多个 raw。
