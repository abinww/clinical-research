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
> 本 skill 不提取临床数据、不写入 raw/ 或 summary/；Mode A 写入 drug/{drug_id}.md 的 `## 药品专利` 章节，Mode C 只返回报告。

## 执行约束

- ✅ 必须使用 Python 脚本执行搜索和字段提取（`search_patents.py`），agent 不得自行手工改写脚本生成的字段
- ✅ 数据源优先级：**先 Google Patents（GP）**，GP 不可用（网络/限流/被屏蔽）时自动降级 FreePatentsOnline（FPO）
- ✅ GP 覆盖全球含 CN；FPO 仅 US 为主、无 CN —— 降级时必须在报告中声明 CN 覆盖丢失
- ✅ 类型由脚本按 CPC/IPC 分类号映射、缺失时按标题启发式判定；类型为推断，最终以权利要求为准
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

## Step 2: 身份锚定（仅 Mode A）

读取 `../drug-identity/SKILL.md`，按 workflow 获取标准身份对象（drug_id、drug_aliases、target、companies、molecule_type；展示名从 drug_aliases 选取）。

无法确认身份时停下返回用户确认，不进入后续步骤。

## Step 3: 构造查询计划

### Mode A（药品专利）—— 多轴查询

| 轴 | 查询词（--query） | 目的 |
|----|------------------|------|
| 名称轴 | drug_aliases 逐个（研发代号、通用名、商品名） | 直接提及药名的专利 |
| 组件轴 | payload/linker/抗体组分名（ADC 等复合药） | 组件级专利（如 deruxtecan/DXd） |
| 公司轴 | `--assignee` 传入研发公司及合作方 × 主别名 | 该公司相关专利（联用/平台） |

示例（Enhertu）：
```text
python {skill_dir}/scripts/search_patents.py --mode drug \
  --query "trastuzumab deruxtecan" --query "DS-8201" --query "deruxtecan" \
  --assignee "Daiichi Sankyo" --assignee "AstraZeneca" \
  --format markdown
```

### Mode C（公司方向）—— 公司 × 时间窗

```text
python {skill_dir}/scripts/search_patents.py --mode company \
  --assignee "Kymera Therapeutics" --after 2021-01-01 \
  [--country CN] --format markdown
```

- `--after/--before` 限定申请日时间窗；脚本同时传给 GP 并在本地按申请日二次过滤
- 时间窗默认最近 5 年（agent 可调整）

## Step 4: 执行脚本并处理输出

1. 原样运行脚本，读取其 markdown/JSON 输出。
2. 脚本已做：公开号去重、类型判定、类型分布/申请人分布聚合、排序（compound → combo → use → other，同组按申请日倒序）。
3. agent 的职责（不覆盖脚本字段）：
   - 剔除明显噪声（如仅"提及"该药名、实为其他分子的平台专利，可在 备注 标注"平台延伸，提及XX，非直接保护"）
   - 备注列补充人工判断（如"核心物质族（2014 优先权）"）

## Step 5: 写入 drug/{drug_id}.md（仅 Mode A）

> ⚠️ 强制步骤（Mode A）。本 skill **不新建** drug 文件，只写入 `## 药品专利` 章节；文件不存在则停止并报告。

```
文件存在？
├── 是 → 读取内容，定位或新增 ## 药品专利 章节（位置在 ## 当前临床管线 之后，由 drug-spec.md 定义）
│         章节内整表替换为本次脚本输出（含更新时间/来源/类型/申请人分布行）
│         不触碰其他章节
└── 否 → 停止并报告："drug/{drug_id}.md 不存在，无法写入专利章节"；不自行新建
```

写入边界：只写 `## 药品专利`；**不得**创建或填充 `## 临床数据汇总`、`## 关键里程碑`、`## 当前临床管线`。

## Step 6: 输出报告

```text
drug-patent-search 完成：
- 模式: Mode A（药品） / Mode C（公司）
- 药品/公司: {drug_id} / {company}
- 数据源: GP / FPO（降级时说明原因）
- 各轴审计: 名称轴 N 条 · 公司轴 N 条 · 组件轴 N 条（Mode A）
- 命中: 去重后 N 件
- 类型分布: compound N · combo N · use N · other N
- 写入: drug/{drug_id}.md ## 药品专利（Mode A）/ 报告返回（Mode C）
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
类型由 CPC/IPC 分类号映射优先（FPO 授权详情页可得），缺失时按标题启发式；均为推断，最终以权利要求书为准。`compound` 判定最可靠（A61K47/68+C07K16/* 等结构码）。

### Q: Mode A 结果里为什么有大量 combo？
联用专利（该药 + 各靶点抑制剂）数量真实多于核心专利，属于正常现象，也是护城河形状的一部分（combo 多 = 公司正在铺联用保护面）。

### Q: 能判断"何时可仿/能否绕过"吗？
不能。本 skill 不收录法律状态、不推算到期日、不做 FTO 法律结论；只描述保护面形状与归属。如需 FTO 需结合法律状态与权利要求逐条比对（超出本 skill 范围）。