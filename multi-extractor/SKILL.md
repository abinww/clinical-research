---
name: multi-extractor
description: |
  临床数据提取编排入口。接收一个或多个 URL/PDF，解析 2.0 身份与路径，
  按来源提取、独立验证，并按 summary 的多适应症内容派发索引。
---

# 临床数据提取编排

## 职责与边界

本 skill 是 URL/PDF 提取的唯一编排入口，负责身份、去重、单来源提取、独立验证和索引派发。`clinical-extractor` 永远 create-only；只有本编排层可在用户明确授权后替换准确重复来源。提取 agent 和主编排 agent 均不得代替独立 verifier 判定通过。

药品页的临床结构化内容只由 `clinical-indexer` 创建或更新。主编排层可以调用 `drug-identity` 创建身份骨架，但不得自行写入或改写药品页中的临床数值、要点、里程碑或来源块；验证通过后必须按第 8 步派发索引。

## 输入与共享契约

- 配置只读取绝对 `research_dir`。身份和完整路径上下文以 `../drug-identity/SKILL.md` 的标准对象为权威；已有完整对象则校验后使用，否则以 `mode: resolve_or_create` 调用该 skill。
- raw 的路径、frontmatter、canonical `source`、PDF 身份和正文形态以 `../schema/raw-spec.md` 为权威；summary 命名、字段、来源身份、链接和多适应症结构以 `../schema/summary-spec.md` 为权威。
- 索引资格只按 `../clinical-indexer/SKILL.md` 的完整门禁判定。
- 读取 `clinical-extractor/SKILL.md`、`data-verify/SKILL.md`、`clinical-indexer/SKILL.md` 及相关 schema；任一契约不可读时停止。
- 所有脚本用 `python`/`pathlib` 兼容方式，不假设 Bash、`grep`、`find` 或 `sed` 存在。

## 不变量与写边界

- 每个来源只生成一对同名 raw/summary；一个 summary 可包含多个适应症，不拆文件。
- 每个来源必须按固定状态推进：`identified` → `extracted` → `summarized` → `verified` → `indexed` → `completed`；状态由执行该步骤的现有 skill 在动作成功后直接返回，不另起验证 agent。图片完整性作为独立状态记录；任一来源图片不完整时，批次最终状态为 `completed_with_image_warning`，不得折算成无警告的 `completed`。
- canonical source、PDF 大小分流和准确重复键以 `../schema/raw-spec.md` 为权威；plan 与本批次比较使用 raw 中持久化的同一个准确值，跨药复用不扫描、不跳过、不阻塞、不替换。
- 不接受或生成 v1 目录、`drug@indication@source` 命名或 raw wikilink。
- 普通提取只写不存在的正式目标；replacement 必须 staging-first、验证通过后原子提交，绝不 delete-first。

## 工作流

1. **预检身份。** 校验 drug-identity 标准对象、所有绝对路径位于 `research_dir` 内并符合公司级布局，且 `drug_page == {company_dir}/{drug_id}.md`。身份歧义或路径不一致时停止。
2. **规范化与去重。** 提取 URL/PDF 列表；无来源时要求补充。先计算 canonical source 并在本批内精确去重，再运行：

```text
python "{clinical_research_dir}/scripts/scan_sources.py" --raw-dir "{raw_dir}" --format urls --strict
```

`raw_dir` 必须是公司级 `{research_dir}/{company_id}/raw`。strict 扫描发现损坏 frontmatter、路径逃逸或配对异常时停止，不得使用部分输出。近似重复只提示人工判断。

3. **处理重复。** 多来源模式静默跳过准确重复并记录匹配；单来源模式报告 canonical source、旧 raw/summary 路径及索引引用，并询问跳过或替换。没有对该准确来源的明确授权时不得覆盖或删除。授权替换时执行下表事务。

| 阶段 | 必须动作 |
|---|---|
| 枚举 | 唯一确定旧 pair、其引用或拥有的附件，以及药品页、全部相关适应症页和根索引中的准确引用；pair 不完整、候选不唯一、附件归属不清或引用无法完整枚举时停止，正式树不变 |
| 准备 | 创建唯一、Windows-safe 的 `{research_dir}/.temp/replacements/{run-id}/`，至少含 `manifest`、`new/`、`backup/`；manifest 持久记录 canonical source、正式目标、旧哈希、全部 managed index documents、附件和事务状态 |
| Staging | 将 staging 的 `raw_dir`、`summary_dir`、`attachments_dir` 交给 create-only extractor；提取后校验文件名、frontmatter、链接、`indications` 和附件引用，再由独立 verifier 审核；未通过 indexer 完整资格门禁时不改正式树 |
| 备份与构建 | 逐字节备份准确旧 pair、全部 managed index documents 和受影响附件到 `backup/` 并校验哈希；在 staging 生成全部新索引文档；manifest 将附件逐项标为复用、添加或移除，不得先删除，只能移除明确属于旧 pair、已备份且不再被引用的附件 |
| Commit | 使用同卷临时文件和原子 rename/replace 安装 raw、summary、managed index documents 和附件；每一步持久化 manifest |
| 恢复 | 任一步失败即恢复全部已改正式文件、移除本事务安装的新文件，并校验旧哈希和引用；崩溃后依据 manifest 完成 commit 或 rollback，不得留下混合状态 |
| 完成 | 最终复检全部文件、哈希和引用成功后才标记 `committed` |

4. **分配标签与检查来源。** URL 做轻量可达性检查，失败时尝试官方同文镜像；若改用镜像或重定向 final URL，持久化和比较统一使用选定字符串。PDF 不在预检重复提取；附件路径与 canonical source 按 `../schema/raw-spec.md` 执行，`<= 10 MiB` 时运行 `../scripts/attach_pdf.py`。按 summary-spec 分配药品内唯一、稳定的 `source_label`；冲突用 `_TrialABC`、`_Abstract1234`、`_FinalAnalysis` 等最短语义后缀，不得用 `_2`、`_3`。
5. **按来源提取。** 每个来源派发一个隔离的 clinical-extractor agent，每轮最多 5 个（或 harness 允许的上限），并注入来源、canonical source、`config_path`、`source_label` 及完整 drug-identity 对象；普通提取传正式写目录，replacement 传 staging 目录。要求只写指定 create-only 目标，并返回逐项 `image_audit` 和 `image_status`；PDF canonical source 按 `../schema/raw-spec.md` 传入。
6. **核对与重试。** 用 harness 文件工具确认返回的 raw/summary 存在、同名、canonical link 正确，且每来源只有一个 summary；逐项确认 image audit 中的 `include` 均以正确远程 URL/实际 PDF 附件出现在正确适应症分组，`none` 必须有完成盘点的依据。普通提取尚未创建 pair 且步骤失败时可携原因重试一次；若 pair 已创建但图片审计缺失、状态与内容不一致或计数不匹配，遵守 extractor 的 create-only 边界，不得对正式目标自动重跑、覆盖或删除，保留 pair 并记录为 `image_status: incomplete`。来源访问受限或图片工具失败时，继续独立数据验证及符合门禁时的索引，但最终不得报告为无警告的 `completed`，应使用 `completed_with_image_warning` 并列明未解决图号/表号及原因。需要修复已存在的 pair 时，只能走用户明确授权的 replacement 事务。返回 `无数据跳过` 的来源计为 skipped，不重试、不计失败，跳过原因写入输出。图片失败不伪造图片，也不因此重复文本提取。
7. **独立验证。** 只把本轮成功 summary 的明确路径派发给独立 data-verify agent，每轮最多 5 个（或 harness 允许的上限）；从 summary 的 canonical link 解析 raw，并覆盖全部 `indications`。verifier 不联网、不修改正文。data-verify 返回 `passed/0/complete` 后，该来源状态推进为 `verified`；`FAIL` 由主编排按证据问题修正文后交给新的独立 verifier；连续两轮仍失败则停止该项。`WARN` 可继续但须列为人工复核项。
8. **派发索引（不可跳过）。** 只将通过 data-verify 门禁的本轮 summary 以部分模式派发给 clinical-indexer。无论是 URL/PDF 直接提取还是批量建库，data-verify 通过后都不得结束；必须等待 clinical-indexer 返回药品页、药品页结构校验、全部适应症页和根 `index.md` 结果。`drug_page_schema: fail` 时该来源不得推进为 `indexed`；`warn` 必须报告，但不单独阻断。药品页、全部适应症页和根索引均为 `completed` 且结构校验无 `fail` 时，该来源状态才推进为 `indexed`；图片 `complete/none` 时由本编排推进为 `completed`，图片 `incomplete` 时推进为 `completed_with_image_warning`，同时保留图像待补警告。任一索引项为 `blocked` 或 `incomplete` 时返回对应索引状态，不得报告完成。索引失败不回滚已验证的 raw/summary。

## 失败与恢复

- 单项提取或验证失败不阻断其他独立来源；失败项遵守上述重试上限。
- replacement 的任何歧义或门禁失败都保持正式树不变；提交故障严格按 manifest 恢复，不允许部分替换。
- 普通索引失败保留已验证 pair 并报告 `verified_unindexed` 或 `blocked`；不得把未索引状态描述为完整成功。multi-extractor 不另起 subagent 复查索引，直接使用 clinical-indexer 的逐目标返回状态。

## 输出

```text
- 输入来源 / 跳过重复 / 无数据跳过 / 成功 / 失败数量
- 状态流转：`identified` / `extracted` / `summarized` / `verified` / `indexed` / `completed` / `completed_with_image_warning` / `blocked`
- canonical source 列表，具体 URL/PDF 身份格式以 `../schema/raw-spec.md` 为准
- 明确授权替换、run-id、备份的准确 pair、managed index documents、附件处置及 commit/rollback 结果
- 每个来源唯一的 raw 与 summary 路径
- 每个 summary 的 indications 数组
- 每个 summary 的 image_status、已识别/已写入/排除/未解决图片数，以及未解决的图号/表号和原因
- PDF 附件（`attachments/{drug_id}@{source_label}.pdf`）及未能渲染的重要图片警告
- PASS/WARN/FAIL 汇总与人工复核项
- clinical-indexer 门禁合格/不合格数量及原因
- drug_page: completed / incomplete / blocked
- drug_page_schema: pass / warn / fail（warn 不单独阻断 indexed；fail 阻断）
- indication_pages: completed / incomplete / blocked
- root_index: completed / incomplete / blocked
- overall_status: completed / completed_with_image_warning / verified_unindexed / blocked
- 失败项及原因
```
