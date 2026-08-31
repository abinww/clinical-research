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
> 本 skill 不提取临床数据、不写入 raw/ 或 summary/；Mode A 写入 drug-identity 返回的 `drug_page` 的 `## 药品专利` 章节，Mode C 只返回报告。

## 执行约束

- ✅ 必须使用 Python 脚本执行搜索和字段提取（`search_patents.py`），agent 不得自行手工改写脚本生成的字段
- ✅ 数据源优先级：**先 Google Patents（GP）**，GP 不可用（网络/限流/被屏蔽）时自动降级 FreePatentsOnline（FPO）
- ✅ GP 覆盖全球含 CN；FPO 仅 US 为主、无 CN —— 降级时必须在报告中声明 CN 覆盖丢失
- ✅ 类型由脚本按可获得的 CPC/IPC 分类号映射、缺失时按标题启发式判定；GP XHR 未返回分类号时必须明确为标题推断，不得声称使用了 CPC
- ❌ 本 skill 不提供法律状态（有效/失效/到期）、不输出到期日、不做 FTO 法律结论
- ❌ 不猜测药品身份（沿用 drug-identity 规则）

## 数据源

| 数据源 | 覆盖 | 查询方式 | 备注 |
|--------|------|---------|------|
| Google Patents (GP) | 全球含 CN/WO/EP/JP/US | Python 脚本 (XHR) | 主力；CN 覆盖的唯一可靠来源 |
| FreePatentsOnline (FPO) | US 为主 | Python 脚本 (专家检索) | 兜底；GP 不可用时启用 |

## 固化规则

1. **GP 优先、FPO 兜底**：脚本 `--source auto` 默认先 GP，失败自动降级 FPO，不重复询问。
2. **别名全集先于搜索**（沿用 data-search 原则）：漏别名 = 漏专利。药品身份经 `drug-identity` 解析。
3. **类型四类**：`compound`(核心物质) / `combo`(联合用药) / `use`(用途/生物标志物) / `other`(平台延伸/其他)。
4. **CN 依赖 GP**：GP 不可用时 CN 专利系统性缺失，必须在报告盲区声明中明确写出。
5. **搜不到身份就停**：drug-identity 无法确认时停下询问，不猜测。
6. **脚本只出数据，judgment 在 agent**：脚本负责检索/字段/类型初判；agent 负责备注补充、明显噪声剔除、最终排版。

## Step 1: 输入识别与模式分发

从用户输入提取：

- **模式**：
  - 药品名称/代号 + "专利" → **Mode A**（该药的原研专利）
  - 公司名 + "专利方向/近年专利" → **Mode C**（公司近年专利方向）
- **药品名称 / 公司名**
- **时间窗**（Mode C 常用，默认最近 5 年；也可用于 Mode A 限定）

## Step 2: 身份锚定

### Mode A

以 `mode: resolve_or_create` 读取并执行 `../drug-identity/SKILL.md`，获取并原样使用完整标准身份与位置对象（包括 `drug_id`、`drug_aliases`、`target`、`company_ids`、`company_id`、`research_dir`、`drug_page`、`attachments_dir`、`mode`、`status`；兼容字段 `companies` 如存在必须与 `company_ids` 相同）。

无法确认身份时停下返回用户确认，不进入后续步骤。

### Mode C

1. 先读取 `{clinical_research_dir}/config.yaml`，只从配置取得绝对 `research_dir`；配置缺失、无效或路径不可读时停止，不得猜测目录。
2. 随后首先读取 `{research_dir}/index.md` 的集中公司表。公司身份只以该表为准；不得查找、读取或创建 `company.md`，也不得先扫描公司目录或开始专利查询。
3. 用用户输入依次匹配公司表中的 `company_id`、中文名、英文名和 aliases，得到唯一 canonical `company_id`、canonical company name 及完整 aliases。
4. 若输入可对应多个实体或品牌，例如 `Merck` 可能指 Merck & Co./MSD 或 Merck KGaA，必须列出根索引中的候选并询问用户选择，不得自行按地区、知名度或搜索结果猜测。
5. 未命中或不能唯一解析时停止并询问用户；不得临时创建公司身份。解析成功后，Mode C 的查询必须覆盖 canonical company name 和全部 aliases。

## Step 3: 构造查询计划

### Mode A（药品专利）—— 多轴查询

| 轴 | 查询词（--query） | 目的 |
|----|------------------|------|
| 名称轴 | drug_aliases 逐个（研发代号、通用名、商品名） | 直接提及药名的专利 |
| 组件轴 | `--component` 逐个传入 payload/linker/抗体组分名（ADC 等复合药） | 组件级专利（如 deruxtecan/DXd） |
| 公司轴 | 重复 `--assignee` 传入研发公司及合作方 × 每个相关药品别名 | 该公司相关专利（联用/平台） |

示例（Enhertu）：
```text
python {skill_dir}/scripts/search_patents.py --mode drug \
  --query "trastuzumab deruxtecan" --query "DS-8201" --component "deruxtecan" \
  --assignee "Daiichi Sankyo" --assignee "AstraZeneca" \
  --format markdown
```

### Mode C（公司方向）—— 公司 × 时间窗

```text
python {skill_dir}/scripts/search_patents.py --mode company \
  --assignee "{canonical company name}" --assignee "{alias 1}" \
  --after 2021-01-01 \
  [--country CN] --format markdown
```

- `--assignee` 可重复传入。查询词来自根索引公司表，包含 canonical company name 和全部中文名、英文名及 aliases；先去除完全重复值，一次运行即可逐个查询并按公开号合并，不得只查询用户输入的一个名称
- FPO 降级也必须逐个别名/组件独立查询，并逐个执行申请人 × 药品别名；不得把全部别名用 `AND` 串联
- 任一查询轴发生源错误时，不得把未报错轴的部分结果伪装成完整成功；显式 `--source gp` 必须非零退出，`auto` 才可整次降级 FPO
- `--after/--before` 限定申请日（filing date）时间窗；脚本同时传给 GP 并在本地按完整日期二次过滤。最早优先权日仅在数据源明确提供时写入 `priority_date`，不可用时保留缺失值，不得将申请日称作最早优先权日
- 时间窗默认最近 5 年（agent 可调整）

## Step 4: 执行脚本并处理输出

1. 原样运行脚本，读取其 markdown/JSON 输出。
2. 脚本已做：公开号去重、查询轴 provenance、类型判定、类型分布/申请人分布聚合、排序（compound → combo → use → other，同组按申请日倒序）。JSON 的 `query_axis_hits` 用于各轴审计。
3. agent 的职责（不覆盖脚本字段）：
   - 剔除明显噪声（如仅"提及"该药名、实为其他分子的平台专利，可在 备注 标注"平台延伸，提及XX，非直接保护"）
   - 备注列补充人工判断；只有来源明确提供或人工核验最早优先权日后，才可写如"核心物质族（2014 最早优先权）"

## Step 5: 写入 drug_page（仅 Mode A）

> ⚠️ 强制步骤（Mode A）。本 skill **不新建** drug 文件，只写入已解析 `drug_page` 的 `## 药品专利` 章节；未返回路径或文件不存在则停止并报告，不猜测路径。

```
文件存在？
├── 是 → 读取内容，定位或新增 ## 药品专利 章节（位置在 ## 当前临床管线 之后，由 drug-spec.md 定义）
│         按公开号（publication identity）与现有表增量合并，不得整表替换：已有行保留人工备注等手工字段，同一公开号只更新本次来源明确提供的结构化字段
│         FPO 降级结果覆盖较低，绝不能删除 GP/人工检索已有而本次未命中的行；任何新结果都只增不减
│         不触碰其他章节
└── 否 → 停止并报告："{drug_page} 不存在，无法写入专利章节"；不自行新建
```

写入边界：只写 `## 药品专利`；**不得**创建或填充 `## 临床数据汇总`、`## 关键里程碑`、`## 当前临床管线`。

## Step 6: 输出报告

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
  - 类型为 CPC/标题推断，最终以权利要求为准
  - Markush 通式结构、18 个月内未公开申请不可见
  - 不提供法律状态与到期日，未做 FTO 结论
```

## 常见问题

### Q: GP 不可用时怎么办？
脚本 `--source auto` 自动降级 FPO（仅 US）。报告必须声明 CN 覆盖丢失；如需 CN 专利，待 GP 恢复后重跑或人工 web 检索补充。

### Q: 专利类型准确吗？
类型由可获得的 CPC/IPC 分类号映射优先（FPO 详情页、部分 GP XHR 结果可得），缺失时按标题启发式；GP 无分类号时报告为标题推断，不声称 CPC。均为推断，最终以权利要求书为准。

### Q: Mode A 结果里为什么有大量 combo？
联用专利（该药 + 各靶点抑制剂）数量真实多于核心专利，属于正常现象，也是护城河形状的一部分（combo 多 = 公司正在铺联用保护面）。

### Q: 能判断"何时可仿/能否绕过"吗？
不能。本 skill 不收录法律状态、不推算到期日、不做 FTO 法律结论；只描述保护面形状与归属。如需 FTO 需结合法律状态与权利要求逐条比对（超出本 skill 范围）。
