---
name: drug-trials-search
description: |
  药品临床试验查询工具。当用户提到以下关键词时触发：
  - "查询药品临床试验"
  - "搜索临床试验"
  - 药品名称 + "临床试验"（如"PD-1临床试验"、"AstraZeneca临床试验"）
---

# 药品临床试验查询

> 本文件由 clinical-research/SKILL.md 路由后读取执行

## 执行约束

- ✅ 必须使用 Python 脚本执行搜索和字段提取
- ✅ 必须同时查询两个数据源
- ✅ 所有结果全部罗列，不去重
- ✅ 输出为表格格式
- ✅ 搜索完成后必须将结果写入 `drug/{药品名}.md` 的临床管线章节

## 数据源

| 网站 | 范围 | 查询方式 |
|-----|-----|---------|
| clinicaltrials.gov | 全球 | Python 脚本 (API) |
| chinadrugtrials.org.cn | 中国 | OpenClaw Browser Tool |

## Step 1: 输入识别

从用户输入中提取：
- **药品名称**：如 "Pembrolizumab"、"Keytruda"、"PD-1"
- **适应症**（可选）：如 "非小细胞肺癌"、"NSCLC"
- **Sponsor**（可选）：如 "Merck"、"AstraZeneca"

## Step 2: 查询 clinicaltrials.gov（自动）

调用 Python 脚本：
```bash
python3 {skill_dir}/search_trials.py --drug "<药品名称>" [--indication "<适应症>"] --source ctg
```

脚本使用 clinicaltrials.gov 官方 API，返回 JSON 格式数据。

## Step 3: 查询 chinadrugtrials.org.cn（半自动）

该网站使用**瑞数反爬机制**，无法用 requests 直接访问。
需要使用 OpenClaw Browser Tool 绕过：

### 3.1 启动浏览器
```
browser action=start
```

### 3.2 导航到搜索页
```
browser action=navigate url="https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml"
```

### 3.3 等待页面加载
等待 3-5 秒让瑞数 JS 执行完成。

### 3.4 输入搜索关键词
使用 snapshot 获取页面元素引用，然后在搜索框输入药品名称。

### 3.5 抓取结果
使用 snapshot 获取结果页面内容，解析表格数据。

### 3.6 解析并格式化
将抓取到的数据转换为标准 TrialResult 格式。

**注意：** 如果 browser tool 不可用或超时，提示用户手动访问：
https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml

## Step 4: 字段提取

每个临床试验提取以下字段：

| 字段 | 说明 |
|-----|-----|
| 临床ID | NCT编号 或 CTR编号 |
| 药品名称/代码 | 试验药物名称或代码 |
| 适应症 | 治疗的疾病 |
| Sponsor | 申办方 |
| 最近更新 | 最后更新日期 |
| 当前状态 | Recruiting/Completed/Terminated 等 |
| 临床阶段 | Phase I/II/III |
| 计划入组人数 | 目标招募人数 |
| 开始日期 | 试验开始时间 |
| 预计完成日期 | 预计结束时间 |
| 对照药物 | 对照组用药 |
| Primary Outcome | 主要终点指标 |
| Secondary Outcome | 次要终点指标 |
| 网址链接 | 试验详情页URL |
| 数据来源 | clinicaltrials.gov 或 chinadrugtrials |

## Step 5: 输出结果

### 5.1 表格格式

使用 Markdown 表格展示，每行一个临床试验：

```markdown
| 临床ID | 药品名称 | 适应症 | Sponsor | 状态 | 阶段 | 入组人数 | 开始日期 | 完成日期 | 对照药物 | Primary Outcome | Secondary Outcome | 链接 | 来源 |
|--------|---------|--------|---------|------|------|---------|---------|---------|---------|----------------|------------------|------|------|
| NCT048... | Keytruda | NSCLC | Merck | Recruiting | Phase III | 600 | 2024-01 | 2027-12 | Placebo | OS, PFS | ORR, Safety | [link](https://...) | CTG |
```

### 5.2 分源统计

在表格后显示：
```
---
clinicaltrials.gov: X 条记录
chinadrugtrials.org.cn: Y 条记录
总计: Z 条记录
```

## Step 6: 写入药品管线文件

> ⚠️ **强制步骤**：搜索完成后必须执行，不可跳过。

### 6.1 读取格式规范

管线表格的列定义、链接格式、排序规则等全部以 drug-spec.md 为准：
```bash
cat ../schema/drug-spec.md
```
关注「当前临床管线」章节的格式要求。

### 6.2 处理 drug/{药品名}.md

```
文件存在？
├── 是 → 读取内容，定位 ## 当前临床管线 章节
│         （不关心该章节在文件中的位置，位置由 drug-spec.md 定义）
│         找到 ### clinicaltrials.gov 子表
│         按 NCT编号 去重合并（同号更新，不同号追加）
│         不触碰其他章节（基本信息、临床数据汇总、关键里程碑）
│
└── 否 → 按 drug-spec.md 格式新建文件
         包含：frontmatter + 基本信息 + 临床数据汇总（空）
              + 关键里程碑（空） + 当前临床管线
```

### 6.3 去重合并策略

- **去重键**：NCT编号（从试验ID中提取）
- **已存在** → 更新可能变化的字段（状态、更新日期、入组数等），保留原有数据
- **不存在** → 追加新行
- **不删除已有行**（保护手动补充的数据）
- **排序**：按阶段（Phase III → II → I），同阶段按开始日期倒序
- **⚠️ trial_id 格式**：脚本返回的 trial_id 已包含完整标识符（如 `NCT06104566`），构造 Markdown 链接时直接使用 `[{trial_id}]({url})`，**不要额外添加 `NCT` 前缀**

### 6.4 写入

将合并后的内容写回 `{drug_dir}/{药品名}.md`。

### 6.5 可选：保存搜索结果到 trials/ 目录

如需保留原始搜索结果，可额外保存到：
```
{trials_dir}/search_{药品名称}_{日期}.md
```

## 技术说明

### clinicaltrials.gov API

- 文档：https://clinicaltrials.gov/api-guide/
- 端点：https://clinicaltrials.gov/api/v2/studies
- 方法：GET 请求，支持 JSON 响应
- 无需认证，无速率限制（合理使用）

### chinadrugtrials.org.cn（瑞数防护）

- **反爬技术**：瑞数信息 WAF（River Security）
- **特征**：HTTP 202 + 动态 JS Cookie + 浏览器指纹检测
- **绕过方式**：使用真实浏览器（DrissionPage / OpenClaw Browser Tool）
- **不推荐**：requests / curl / headless Selenium

## 常见问题

### Q: 查询无结果？
- 检查药品名称拼写
- 尝试通用名/商品名/代码不同写法
- 放宽搜索条件（去掉适应症限制）

### Q: 字段缺失？
- 部分字段在原始数据中可能为空
- 用 "N/A" 或 "-" 标记缺失字段

### Q: chinadrugtrials 无法访问？
- 确认 OpenClaw browser tool 可用
- 手动访问：https://www.chinadrugtrials.org.cn/
