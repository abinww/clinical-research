# clinical-research Skill 合规审计

- 审计日期：2026-11-28
- 审计依据：`skill-spec.md`
- 范围：全部 `SKILL.md`、`schema/*.md`、Python 脚本、测试及项目说明文档
- 测试基线：主测试 35 项、drug-build 9 项、drug-trials-search 27 项、drug-patent-search 46 项，共 117 项通过
- 说明：测试通过不代表规范合规；部分测试固化了当前不合规行为

## 一、高风险问题

| 编号 | 问题 | 主要位置 | 违反点与风险 | 建议 |
|---|---|---|---|---|
| H1 | raw 缺少独立权威 spec | `schema/` 中缺少独立 raw spec；`schema/summary-spec.md:18-26,41-45`；`clinical-extractor/SKILL.md:45-53` | `skill-spec.md` 要求 raw、summary 分别由独立 spec 定义。raw 的路径、frontmatter、正文和 PDF 分流规则被拆在 summary spec 与 workflow 中。 | 新增最小 `schema/raw-spec.md`，迁移 raw 持久化格式；提取操作仍留在 extractor。 |
| H2 | `indications` 类型冲突 | `schema/summary-spec.md:78,99,132`；`schema/indication-spec.md:47`；`schema/index-spec.md:120`；`clinical-indexer/SKILL.md:94` | summary spec 要求标量字符串数组，其他文件按对象数组解析，indexer 自身又改回标量数组。 | 统一为标量字符串数组，显示名只来自正文分组头。 |
| H3 | 脚本接受 spec 禁止的标量 `indications` | `scripts/scan_sources.py:207-208`；`tests/test_scan_sources.py:127-128` | 标量 `indications: NSCLC_1L` 被当作合法单元素数组。 | 只接受 YAML 数组；标量报错并增加负向测试。 |
| H4 | `indication_id` 语法冲突 | `schema/summary-spec.md:35`；`schema/indication-spec.md:20-22,189`；`schema/index-spec.md:116`；`scripts/scan_sources.py:23` | summary spec/脚本要求 ASCII ID，indication spec 允许中文并推荐 `_3L+`，index spec 又给出中文文件名示例。 | 由 `indication-spec.md` 唯一规范；建议保留 ASCII 机器 ID，中文仅作显示名。 |
| H5 | plan 检查器可误报 `已完成` | `drug-build/scripts/check_plan_progress.py:198-275`；`clinical-indexer/SKILL.md:96-109`；根 `SKILL.md:46` | 检查器使用简化审核和链接判断，不执行 indexer 完整十项门禁；药品页、适应症页、根索引结构不完整时仍可能返回 `已完成`。 | 完成状态必须消费 indexer 的权威资格结果，或调用其共享校验入口。 |
| H6 | 损坏 raw 会被误报为 `未提取` | `check_plan_progress.py:108,239-240` | raw 缺 frontmatter 或 `source` 时不报数据完整性错误，可能触发重新抓取。 | 扫描范围内逐个校验 raw；损坏项返回 `数据完整性错误`。 |
| H7 | replacement staging 索引无合法生成者 | `multi-extractor/SKILL.md:49-51`；`clinical-indexer/SKILL.md:18-31` | multi 要求生成 staging 索引文档，但 indexer 只支持正式 `research_dir`，无 staging/target-root 输入。 | 为 indexer 增加显式目标根输入，或由 indexer 拥有 staging 索引生成契约。 |
| H8 | 公司级 raw 扫描破坏按药品判重 | `multi-extractor/SKILL.md:28,38-41`；`data-search/SKILL.md:113-121`；`scripts/scan_sources.py:288-306,465-466` | 规则要求 `(company_id, drug_id, source)`，但扫描整个公司 `raw/` 且只输出 source；可能误判跨药同 URL，或被其他药品损坏文件阻断。 | 扫描器增加 `--drug-id` 过滤并保留完整身份；strict 异常按药品隔离。 |
| H9 | PDF 附件创建职责与校验不一致 | `multi-extractor/SKILL.md:49,55-56`；`clinical-extractor/SKILL.md:55,77-95`；`scripts/attach_pdf.py:31-41` | multi 提前写正式附件，extractor 又负责附件创建；附件脚本不校验 `{drug_id}@{source_label}`，也不比较同名文件内容；失败/跳过可能留下孤儿附件。 | 明确附件创建 owner；校验 stem 与内容；记录并清理本次未提交附件。 |
| H10 | 试验脚本截断方案药物 | `drug-trials-search/search_trials.py:347,376` | 药品和对照药最多取 3 个，违反 drug spec 保留全部药物的要求。 | 删除上限；无法可靠提取时写 `—`，不得静默丢失。 |
| H11 | 专利脚本伪造日期精度 | `drug-patent-search/scripts/search_patents.py:103-120,623-626` | 仅有年份时补成 `YYYY-01-01`，排序只比较年月，会制造不存在的申请日期和错误顺序。 | 展示原始精度；内部使用带精度标记的排序键，年份-only 稳定置后。 |

## 二、职责与权威边界问题

| 编号 | 问题 | 主要位置 | 违反点 | 建议 |
|---|---|---|---|---|
| R1 | 身份对象被重建或裁剪 | `batch-extractor/SKILL.md:39-40`；`data-search/SKILL.md:47-65`；`drug-identity/SKILL.md:12,140-161` | batch 从路径构造身份对象；data-search 定义不完整对象并自行选择展示名。 | 统一调用 `drug-identity`，完整对象原样传递。 |
| R2 | plan 格式有两个 owner | `data-search/SKILL.md:133-161`；`drug-build/SKILL.md:24-55,137-147` | data-search 定义完整 plan 模板，drug-build 又定义文件名、标记、候选区和合并规则。 | drug-build 唯一渲染 plan；data-search 只返回结构化行。 |
| R3 | 根 preflight 成为第二身份解析入口 | 根 `SKILL.md:59`；`drug-identity/SKILL.md:12,37-42` | 根层要求路由前解析身份，却未规定调用 drug-identity；可能阻断新药创建。 | preflight 显式调用 `resolve_only`，或允许身份延迟到子 skill 解析。 |
| R4 | orchestrator 复制 verifier 内部流程 | `batch-extractor/SKILL.md:25,43`；`multi-extractor/SKILL.md:58`；`data-verify/SKILL.md:30-43` | 调用方规定 verifier 如何定位 raw、覆盖 indications、是否联网和修改正文。 | 调用方只传 summary 路径、要求独立验证并消费返回状态。 |
| R5 | drug-build 复制并可能覆盖 multi 的并发/重试策略 | `drug-build/SKILL.md:17,59,66`；`multi-extractor/SKILL.md:56-58` | drug-build 复制并发常量，且“每项总尝试上限 2 次”未区分外层与子 skill 内部重试。 | 删除内部并发常量；明确外层重试上限，子 skill 内部规则优先。 |
| R6 | multi 改写 extractor 的 `image_status` | `multi-extractor/SKILL.md:57`；`clinical-extractor/SKILL.md:57,116` | 生产者字段被编排层直接覆盖。 | 原样保留生产者状态；编排层使用独立警告字段。 |
| R7 | drug-build 建立第二套索引资格门禁 | `drug-build/SKILL.md:54,62-72,163,195`；`check_plan_progress.py:198-275` | 进度脚本自行判断审核与索引完成，权威门禁在 clinical-indexer。 | drug-build 只映射权威结果，不另设资格规则。 |
| R8 | clinical-indexer 复制 schema 写规则并产生排序冲突 | `clinical-indexer/SKILL.md:49-60,148,153`；`schema/index-spec.md:81,128` | 本地维护一套格式策略；药品表重排与“保留既有行顺序”表述冲突。 | 删除本地格式表，引用 drug/indication/index schema。 |
| R9 | drug-trials-search 创建边界自相矛盾 | `drug-trials-search/SKILL.md:20,35`；`drug-identity/SKILL.md:42,119` | 一方面禁止创建 drug 文件，一方面调用会创建身份骨架的 `resolve_or_create`。 | 明确身份骨架由 drug-identity 创建，本 skill 不自行创建。 |
| R10 | 提取失败恢复未覆盖已创建附件 | `clinical-extractor/SKILL.md:55,77-95,105-107`；`batch-extractor/SKILL.md:42,53` | 小 PDF 附件可能先于 summary 创建；跳过/失败时只清理 raw 或半成品 summary。 | 记录本次创建附件；跳过/失败时删除仅本次创建且未提交的附件。 |
| R11 | 配置、plan、身份对象存在多个格式所有者 | `README.md:78-84`；`install.md:168,181`；根 `SKILL.md:22-24`；`data-search/SKILL.md:49-63,133-161` | 配置应只由 initial 定义；plan 应由 drug-build 定义；身份对象应由 drug-identity 定义。 | 非 owner 文件只引用，不复制格式。 |
| R12 | 说明文档重复持久化格式 | `initial.md:85-145,162`；`README.md:48-86`；`install.md:168-181`；根 `SKILL.md:26-54` | 内嵌 index 骨架、表头、markers、排序、wikilink、PDF/raw 规则；initial 还新增 schema 未定义的 `Editing Rules`。 | 说明文档只引用 schema；初始化按 schema 生成骨架。 |

## 三、schema、脚本与实现一致性问题

| 编号 | 问题 | 主要位置 | 违反点 | 建议 |
|---|---|---|---|---|
| S1 | `company_id` 尾部字符规则冲突 | `schema/index-spec.md:97`；`scripts/layout.py:17,23,36-38`；`drug-identity/SKILL.md:54` | index spec 允许尾部 `.`/`-`，layout 禁止尾部 `.`。 | index spec 引用 `is_valid_identifier`，删除平行语法。 |
| S2 | index spec 公司表示例违反空行规则 | `schema/index-spec.md:88-90` vs `:52,57` | companies begin marker 后缺空行。 | 补空行。 |
| S3 | README 错称三类来源块都用 managed markers | `README.md:73` | 药品页用相对来源链接，适应症页用 `source_identity`，只有根索引核心表用 HTML markers。 | 分别描述三种来源身份。 |
| S4 | clinical-indexer 保留错误药品页 vault 路径 | `clinical-indexer/SKILL.md:60` | 示例多一层药品目录。 | 改为 `[[第一三共/DS-8201.md|DS-8201]]`。 |
| S5 | 配置读取器接受 `~` | `scripts/config.py:91-95,121-127` | 持久配置调用 `expanduser()`，与“先展开再保存”冲突。 | 读取持久配置时禁止展开；仅 initial 负责展开。 |
| S6 | summary 审核门禁接受非规范审核表 | `scripts/scan_sources.py:126-155`；`tests/test_scan_sources.py:149-152`；`drug-build/tests/test_check_plan_progress.py:84-85,190-193` | 只要求两列并接受别名；未拒绝重复审核章节或表外 FAIL。 | 按 summary spec 校验唯一末节、六列、首列 `indication_id`、FAIL 计数和表外结论。 |
| S7 | 来源扫描器不执行 raw/summary 命名和 source 规则 | `scripts/scan_sources.py:55-63,288-306,478-489` | 接受非法文件名和任意 source 标量。 | 校验 `{valid_drug_id}@{valid_source_label}.md` 与合法 URL/PDF 路径。 |
| S8 | plan 检查器发明替代表头 | `check_plan_progress.py:69-85`；`drug-build/tests/test_check_plan_progress.py:27-48` | 接受 `URL`、`source`、`来源链接` 等别名和任意列顺序。 | 只识别 drug-build 定义的主表 schema。 |
| S9 | plan 检查器把跨药品同源误判为重复 | `check_plan_progress.py:89-112,226-242` | 不带公司/药品范围时全局搜索，跨药复用会返回多个 raw。 | 工作流强制范围；诊断模式不得将跨药复用标为歧义。 |
| S10 | plan 检查器未完整验证三个索引目标 | `check_plan_progress.py:140-223`；`drug-build/tests/test_check_plan_progress.py:90-113` | 只检查部分链接和注释，不验证公司表、标题、marker、列位置、页面结构和疗效表。 | 调用药品页结构校验，并按 index/indication spec 完整验证。 |
| S11 | 附件脚本不校验 stem 且静默复用不同内容 | `scripts/attach_pdf.py:31-41`；`tests/test_attach_pdf.py:15-33,62-67` | 接受非法 source_label、缺少/多个 `@`；同名附件不比较内容。 | 校验 `{drug_id}@{source_label}`；同名不同内容报错。 |
| S12 | 布局脚本额外排除未定义的 `temp/` | `scripts/layout.py:10`；`tests/test_scan_sources.py:159-176` | schema 只定义 `.temp/`。 | 删除裸 `temp` 排除，或先在权威布局中定义。 |
| S13 | 试验国家格式和阶段排序只存在于脚本/测试 | `drug-trials-search/search_trials.py:97-141,557-563` | 五国阈值、`EU`/`ETC` 合并、国家代码表、Phase IV 排序未在 drug spec 定义。 | 将渲染与排序规则写入 drug spec。 |
| S14 | 零结果管线不是 schema 表格，脚本允许独立输出文件 | `search_trials.py:407-410,446-453,500,548-552` | 零结果输出文本而非规范表；`--output` 可创建独立 trial 文件。 | 零结果输出规范表/占位行；删除 `--output` 写文件能力。 |
| S15 | 专利脚本新增未定义元数据 | `search_patents.py:646-668`；`tests/test_search_patents.py:382-386` | `分类依据`、`查询轴命中` 被写入持久化专利节，drug spec 未定义。 | 仅放运行时报告，或先修改 drug spec。 |
| S16 | 药品页校验器未执行全部来源块规则 | `scripts/check_drug_page.py:380-420,443-478` | 不拒绝禁止的 `source_identity`；source label 只做子串搜索，不验证块顺序。 | 按 drug spec 解析来源块并严格校验 label/table/link 顺序。 |

## 四、相对路径引用错误

以下引用从当前文件目录无法解析：

| 位置 | 当前引用 | 正确引用 |
|---|---|---|
| `batch-extractor/SKILL.md:18` | `data-verify/SKILL.md` | `../data-verify/SKILL.md` |
| `multi-extractor/SKILL.md:21` | `clinical-extractor/SKILL.md`、`data-verify/SKILL.md`、`clinical-indexer/SKILL.md` | 分别加 `../` |
| `multi-extractor/SKILL.md:55` | `scripts/attach_pdf.py` | `../scripts/attach_pdf.py` |
| `clinical-indexer/SKILL.md:11` | `clinical-research/SKILL.md` | `../SKILL.md` |
| `data-search/SKILL.md:13` | `clinical-research/SKILL.md` | `../SKILL.md` |
| `drug-build/SKILL.md:14` | `clinical-research/SKILL.md` | `../SKILL.md` |
| `drug-trials-search/SKILL.md:12` | `clinical-research/SKILL.md` | `../SKILL.md` |
| `drug-patent-search/SKILL.md:12` | `clinical-research/SKILL.md` | `../SKILL.md` |
| `drug-identity/SKILL.md:54` | `scripts/layout.py` | `../scripts/layout.py` |
| `schema/drug-spec.md:36` | `scripts/layout.py` | `../scripts/layout.py` |
| `schema/summary-spec.md:34` | `scripts/layout.py` | `../scripts/layout.py` |
| `drug-trials-search/SKILL.md:29` | `drug-spec.md` | `../schema/drug-spec.md` |
| `drug-patent-search/SKILL.md:99` | `drug-spec.md` | `../schema/drug-spec.md` |

## 五、本轮处理范围

- 已处理：H1，新增 `schema/raw-spec.md`，并将 raw 持久化格式的引用收敛到该文件；34 处对该 spec 的引用均已验证可解析。
- 未处理：其余问题保留在本审计中，后续按风险逐项修复。
