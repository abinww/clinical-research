---
name: multi-extractor
description: |
  临床数据提取编排入口。接收一个或多个 URL/PDF，解析 2.0 身份与路径，
  按来源提取、独立验证，并按 summary 的多适应症内容派发索引。
---

# 临床数据提取编排

## 职责与边界

本 skill 是 URL/PDF 提取的唯一编排入口，负责身份、去重、单来源提取、独立验证和索引派发。`clinical-extractor` 永远 create-only；只有本编排层可在用户明确授权后替换准确重复来源。提取 agent 和主编排 agent 均不得代替独立 verifier 判定通过。

## 输入与共享契约

- 配置只读取绝对 `research_dir`。身份和完整路径上下文以 `../drug-identity/SKILL.md` 的标准对象为权威；已有完整对象则校验后使用，否则以 `mode: resolve_or_create` 调用该 skill。
- summary 命名、字段、来源身份、链接和多适应症结构以 `../schema/summary-spec.md` 为权威。
- 索引资格只按 `../clinical-indexer/SKILL.md` 的完整门禁判定。
- 读取 `clinical-extractor/SKILL.md`、`data-verify/SKILL.md`、`clinical-indexer/SKILL.md` 及相关 schema；任一契约不可读时停止。
- 所有脚本用 `python`/`pathlib` 兼容方式，不假设 Bash、`grep`、`find` 或 `sed` 存在。

## 不变量与写边界

- 每个来源只生成一对同名 raw/summary；一个 summary 可包含多个适应症，不拆文件。
- URL 使用用户准确提供或明确采用的 canonical final URL；PDF 使用 `Path.resolve(strict=True).as_posix()`。准确重复键仅为当前药品树中的 `(company_id, drug_id, source)`，跨药复用不扫描、不跳过、不阻塞、不替换。
- 不接受或生成 v1 目录、`drug@indication@source` 命名或 raw wikilink。
- 普通提取只写不存在的正式目标；replacement 必须 staging-first、验证通过后原子提交，绝不 delete-first。

## 工作流

1. **预检身份。** 校验 drug-identity 标准对象、所有绝对路径位于 `research_dir` 内并符合 `company_id/drug_id` 布局，且 `drug_page == drug_dir/{drug_id}.md`。身份歧义或路径不一致时停止。
2. **规范化与去重。** 提取 URL/PDF 列表；无来源时要求补充。先计算 canonical source 并在本批内精确去重，再运行：

```text
python "{clinical_research_dir}/scripts/scan_sources.py" --raw-dir "{raw_dir}" --format urls --strict
```

`raw_dir` 必须是当前药品目录。strict 扫描发现损坏 frontmatter、路径逃逸或配对异常时停止，不得使用部分输出。近似重复只提示人工判断。

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

4. **分配标签与检查来源。** URL 做轻量可达性检查，失败时尝试官方同文镜像；若改用镜像或重定向 final URL，持久化和比较统一使用选定字符串。PDF 不在预检重复提取。按 summary-spec 分配药品内唯一、稳定的 `source_label`；冲突用 `_TrialABC`、`_Abstract1234`、`_FinalAnalysis` 等最短语义后缀，不得用 `_2`、`_3`。
5. **按来源提取。** 每个来源派发一个隔离的 clinical-extractor agent，每轮最多 5 个，并注入来源、canonical source、`config_path`、`source_label` 及完整 drug-identity 对象；普通提取传正式写目录，replacement 传 staging 目录。要求只写指定 create-only 目标。
6. **核对与重试。** 用 harness 文件工具确认返回的 raw/summary 存在、同名、canonical link 正确，且每来源只有一个 summary。失败项携原因重试一次；仍失败则记录，不影响其他来源。PDF 图片工具不可用只记警告，不伪造图片，也不因此重复文本提取。
7. **独立验证。** 只把本轮成功 summary 的明确路径派发给独立 data-verify agent，每轮最多 5 个；从 summary 的 canonical link 解析 raw，并覆盖全部 `indications`。verifier 不联网、不修改正文。`FAIL` 由主编排按证据问题修正文后交给新的独立 verifier；连续两轮仍失败则停止该项。`WARN` 可继续但须列为人工复核项。
8. **派发索引。** 只将通过 clinical-indexer 完整资格门禁的本轮 summary 以部分模式派发。每个 summary 对药品页只更新一次，并展开全部 `indications` 更新对应适应症页；所有索引项引用同一 summary。索引器不支持多适应症时停止该项并报告，不拆 summary、不退回旧格式。索引失败不回滚已验证的 raw/summary。

## 失败与恢复

- 单项提取或验证失败不阻断其他独立来源；失败项遵守上述重试上限。
- replacement 的任何歧义或门禁失败都保持正式树不变；提交故障严格按 manifest 恢复，不允许部分替换。
- 普通索引失败保留已验证 pair 并报告；不得把未索引状态描述为完整成功。

## 输出

```text
- 输入来源 / 跳过重复 / 成功 / 失败数量
- canonical source 列表；URL 保留值及 PDF resolved absolute POSIX path
- 明确授权替换、run-id、备份的准确 pair、managed index documents、附件处置及 commit/rollback 结果
- 每个来源唯一的 raw 与 summary 路径
- 每个 summary 的 indications 数组
- PDF 附件及未能渲染的重要图片警告
- PASS/WARN/FAIL 汇总与人工复核项
- clinical-indexer 门禁合格/不合格数量及原因
- drug 索引和逐适应症索引结果
- 失败项及原因
```
