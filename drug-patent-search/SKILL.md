---
name: drug-patent-search
description: |
  药品/公司专利检索工具。当用户提到以下关键词时触发：
  - "查询{药品}专利" / "搜索{药品}专利" / "药品专利检索"
  - 药品名称 + "专利"（如 "Enhertu 专利"、"KT-621 专利"）
  - "查{公司}专利方向" / "{公司}近年专利" / "公司专利分析"
---

# 药品/公司专利检索

> 本文件由 clinical-research/SKILL.md 路由后读取执行。
> 职责：检索指定药品的原研专利（Mode A）或指定公司近年专利方向（Mode C），供赛道/护城河分析。

## 约束与固定规则

- 必须使用 `search_patents.py` 搜索和提取字段；agent 不得改写脚本生成的结构化字段。
- 数据源优先级为 Google Patents（GP）后 FreePatentsOnline（FPO）。`--source auto` 在 GP 网络、限流或屏蔽失败时整次降级 FPO，不重复询问。
- GP 覆盖全球且含 CN；FPO 以 US 为主、无 CN。降级时必须声明 CN/WO/EP 覆盖丢失。
- 先获得完整药品或公司别名，再搜索；身份无法唯一确认时停止询问，不猜测。
- 类型为 `compound`（核心物质）、`combo`（联合用药）、`use`（用途/生物标志物）、`other`（平台延伸/其他）。脚本优先按可得 CPC/IPC 映射，缺失时按标题启发式；GP XHR 无分类号时必须注明标题推断，不得声称使用 CPC。
- 脚本负责检索、字段、类型初判和聚合；agent 只负责明显噪声剔除、备注补充和最终排版。
- 不提取临床数据，不写 `raw/` 或 `summary/`。
- 不提供法律状态、失效/到期日或可仿时间，不作 FTO 法律结论。保护面与归属描述不能替代权利要求和法律状态分析。

## 模式

| 模式 | 触发与身份模式 | 查询对象 | 写入行为 |
|---|---|---|---|
| Mode A | 药品名称/代号 + “专利”；drug-identity `resolve_or_create` | 该药原研专利；可设时间窗 | 增量写入 `drug_page` 的 `## 药品专利`，并返回报告 |
| Mode C | 公司名 + “专利方向/近年专利”；根索引解析公司 | 公司近年专利方向；默认最近 5 年 | 只返回报告，不写研究文件 |

## 数据源

| 数据源 | 覆盖 | 查询方式 | 备注 |
|---|---|---|---|
| Google Patents（GP） | 全球含 CN/WO/EP/JP/US | Python 脚本（XHR） | 主力；唯一可靠 CN 来源 |
| FreePatentsOnline（FPO） | US 为主 | Python 脚本（专家检索） | GP 不可用时兜底 |

## Step 1: 输入与身份

提取模式、药品名称或公司名，以及可选时间窗。

### Mode A

以 **identity mode `resolve_or_create`** 调用 `../drug-identity/SKILL.md`，获取并原样使用完整标准身份与位置对象，包括 `drug_id`、`drug_aliases`、`target`、`company_ids`、`company_id`、`research_dir`、`drug_page`、`attachments_dir`、`mode`、`status`；兼容字段 `companies` 如存在，必须与 `company_ids` 相同。无法确认身份时停止并请用户确认。

### Mode C

1. 读取 `{clinical_research_dir}/config.yaml`，只取绝对 `research_dir`。配置缺失、无效或不可读时停止，不猜测目录。
2. 随后立即首先读取 `{research_dir}/index.md` 的集中公司表；不得查找、读取或创建 `company.md`，不得先扫描公司目录或查询专利。
3. 依次匹配 `company_id`、中文名、英文名和 aliases，解析唯一 canonical `company_id`、canonical company name 及完整 aliases。
4. 多义输入如 `Merck` 必须列出根索引候选并询问，不得按地区、知名度或搜索结果猜测。未命中或不能唯一解析时停止，不临时创建公司身份。
5. 查询覆盖 canonical company name 和全部 aliases。

## Step 2: 构造查询

### Mode A：多轴查询

| 轴 | 参数 | 目的 |
|---|---|---|
| 名称轴 | 对每个研发代号、通用名、商品名重复 `--query` | 直接提及药名的专利 |
| 组件轴 | 对 payload、linker、抗体组分名等重复 `--component` | ADC 等复合药的组件级专利 |
| 公司轴 | 对研发公司及合作方重复 `--assignee`，并覆盖每个相关药品别名 | 公司相关联用或平台专利 |

```text
python {skill_dir}/scripts/search_patents.py --mode drug \
  --query "trastuzumab deruxtecan" --query "DS-8201" --component "deruxtecan" \
  --assignee "Daiichi Sankyo" --assignee "AstraZeneca" \
  --format markdown
```

### Mode C：公司与时间窗

```text
python {skill_dir}/scripts/search_patents.py --mode company \
  --assignee "{canonical company name}" --assignee "{alias 1}" \
  --after 2021-01-01 \
  [--country CN] --format markdown
```

- `--assignee` 可重复。去除完全重复值后，一次运行逐个查询 canonical company name、中文名、英文名和全部 aliases，并按公开号合并；不得只查用户输入名称。
- FPO 降级时仍须逐个查询别名和组件，并逐个执行申请人 × 药品别名；不得用 `AND` 串联全部别名。
- `--after/--before` 限定申请日（filing date），脚本同时传给 GP 并按完整日期本地二次过滤。最早优先权日仅在来源明确提供时写入 `priority_date`；缺失时不得用申请日替代或将申请日称作最早优先权日。
- 时间窗默认最近 5 年，agent 可调整。

## Step 3: 源失败与输出处理

1. 原样运行脚本，读取 Markdown 或 JSON 输出。
2. 任一查询轴发生源错误时，不得把其他轴的部分结果表述为完整成功。显式 `--source gp` 必须以非零退出；只有 `auto` 可将整次查询降级 FPO。
3. 脚本负责公开号去重、查询轴 provenance、类型判定、类型/申请人分布聚合，以及 `compound → combo → use → other`、同组申请日倒序排序。JSON 的 `query_axis_hits` 用于查询轴审计。
4. agent 可剔除明显噪声，例如仅提及该药、实为其他分子的平台专利，并在备注标注“平台延伸，提及XX，非直接保护”。
5. 只有来源明确提供或人工核验最早优先权日后，备注才可写“核心物质族（2014 最早优先权）”等判断。

## Step 4: 增量写入（仅 Mode A）

Mode A 成功后必须写入；Mode C 不写。

若未返回 `drug_page` 或文件不存在，停止并报告 `"{drug_page} 不存在，无法写入专利章节"`，不得新建 drug 文件或猜测路径。文件存在时，在 `## 当前临床管线` 后定位或新增 `## 药品专利`，位置以 `drug-spec.md` 为准。

- 只写 `## 药品专利`，不修改其他章节，不创建或填充 `## 临床数据汇总`、`## 关键里程碑`、`## 当前临床管线`。
- 按公开号（publication identity）与现有表增量合并，不整表替换。
- 已有行保留人工备注等手工字段；同一公开号只更新本次来源明确提供的结构化字段。
- 合并必须考虑本次来源覆盖范围：FPO 覆盖低于 GP，本次未命中不表示已有专利消失。GP、FPO 或人工检索已有行均不得因本次未命中而删除；任何新结果只增不减。

## Step 5: 返回报告

```text
drug-patent-search 完成：
- 模式: Mode A（药品） / Mode C（公司）
- 药品/公司: {drug_id} / {company}
- Mode C 公司解析: {company_id} | canonical name: {name} | queried aliases: {列表}
- 数据源: GP / FPO（降级时说明原因）
- 各轴审计: 名称轴 N 条 · 公司轴 N 条 · 组件轴 N 条（Mode A）
- 命中: 去重后 N 件
- 类型分布: compound N · combo N · use N · other N
- 写入: {drug_page} ## 药品专利（Mode A）/ 报告返回（Mode C）
- 人工复核项: （明显噪声/平台延伸列表；如有）
- 盲区声明:
  - 数据源为 FPO 时 CN/WO/EP 未覆盖（GP 不可用）
  - 类型为 CPC/IPC 映射或标题推断，最终以权利要求为准
  - Markush 通式结构、18 个月内未公开申请不可见
  - 不提供法律状态与到期日，未做 FTO 结论
```
