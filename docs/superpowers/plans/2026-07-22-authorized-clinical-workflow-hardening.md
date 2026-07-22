# Authorized Clinical Workflow Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply only the user-authorized workflow, identity, CTG reliability, evaluator-boundary, and local-configuration changes.

**Architecture:** Schemas define the stable identity and summary eligibility contract. Extractor and indexer consume that contract to write the permitted drug-page sections, while the CTG tool independently owns only the pipeline subsection. Python behavior is protected by unit tests; workflow documents are verified through targeted static scans.

**Tech Stack:** Markdown skill workflows, YAML frontmatter/configuration, Python 3, `requests`, `unittest`, git.

## Global Constraints

- Do not modify `batch-extractor/SKILL.md`.
- Do not change the summary "专家点评" responsibility.
- Do not change shell command portability; OpenClaw runs on Debian.
- Use `drug_id` for summary/drug paths and `indication_id` for indication paths.
- Use `line: null` when a treatment line cannot be determined; do not infer 1L.
- Only summaries with `verification: passed`, `verification_fail_count: 0`, and `## 数据一致性审核` can be indexed.
- `clinical-extractor` and `clinical-indexer` may create basic information and update clinical data/milestones; `drug-trials-search` updates only `## 当前临床管线`.
- Retain `--source cdt` as an explicit unimplemented CLI interface; do not retain CDT scraping code.
- Use `—` for missing displayed values.

---

### Task 1: Align schemas and index workflows with stable identities

**Files:**
- Modify: `schema/drug-spec.md`
- Modify: `schema/indication-spec.md`
- Modify: `schema/summary-spec.md`
- Modify: `clinical-extractor/SKILL.md`
- Modify: `clinical-indexer/SKILL.md`
- Modify: `SKILL.md`

**Interfaces:**
- Consumes: YAML fields from `schema/summary-spec.md`.
- Produces: qualified summary paths as `summary/{drug_id}/{drug_id}@{indication_id}.md`, expected drug pages as `drug/{drug_id}.md`, and expected indication pages as `indication/{indication_id}.md`.

- [ ] **Step 1: Record the expected contracts before changing docs**

The three schemas and two workflows must contain all of the following exact identity or verification tokens:

```text
drug_id
indication_id
verification: passed
verification_fail_count: 0
```

`clinical-indexer/SKILL.md` must additionally contain:

```text
expected_drug_page = drug/{drug_id}.md
expected_indication_page = indication/{indication_id}.md
```

- [ ] **Step 2: Check the current contract scan**

Run:

```powershell
rg -n "drug_id|indication_id|verification_fail_count" schema clinical-extractor/SKILL.md clinical-indexer/SKILL.md
```

Expected: use the scan to identify any identity, verification, or expected-target wording still missing from the current worktree.

- [ ] **Step 3: Define the normalized identity and eligibility contract**

Update the schemas and workflows so that:

```markdown
drug_id: {开发代码或规范短名}
drug: {药品通用名}
indication_id: {规范适应症ID}
indication: {适应症}
verification: passed
verification_fail_count: 0
```

The indexer must reject a summary unless it has the four identity/display fields, passed verification, zero failures, and `## 数据一致性审核`. It must treat a source link on any non-expected page as an integrity error, not as successful archival.

Ensure `drug-spec.md` says that either the extractor or indexer may create basic information and update clinical data/milestones; CTG-originated registration data may update only the pipeline section.

- [ ] **Step 4: Check the contract scan after the edits**

Run:

```powershell
rg -n "expected_drug_page = drug/\{drug_id\}\.md|expected_indication_page = indication/\{indication_id\}\.md|verification: passed|verification_fail_count: 0" schema clinical-extractor/SKILL.md clinical-indexer/SKILL.md
```

Expected: every pattern appears in its relevant schema or workflow.

- [ ] **Step 5: Review the schema/index diff**

Run:

```powershell
git diff -- SKILL.md schema/drug-spec.md schema/indication-spec.md schema/summary-spec.md clinical-extractor/SKILL.md clinical-indexer/SKILL.md
```

Expected: only the authorized identity, eligibility, writer-boundary, and safe-default changes are present.

### Task 2: Make CTG search pagination and outputs reliable

**Files:**
- Modify: `drug-trials-search/search_trials.py`
- Modify: `drug-trials-search/tests/test_search_trials.py`
- Create: `drug-trials-search/tests/__init__.py`
- Create: `drug-trials-search/requirements.txt`
- Modify: `drug-trials-search/SKILL.md`

**Interfaces:**
- Consumes: CTG v2 `studies` responses and optional `nextPageToken`.
- Produces: `ClinicalTrialsGov.search(...) -> list[TrialResult]`, pure JSON on stdout with `--format json`, and a CTG-only `### clinicaltrials.gov` pipeline subsection.

- [ ] **Step 1: Add failing tests for pagination and stdout purity**

In `drug-trials-search/tests/test_search_trials.py`, add tests that assert:

```python
self.assertEqual(client.session.calls[1]["pageToken"], "page-2")
payload = json.loads(stdout.getvalue())
self.assertEqual(payload[0]["临床ID"], "NCT00000001")
self.assertIn("查询 ClinicalTrials.gov", stderr.getvalue())
```

- [ ] **Step 2: Run the current CTG test suite**

Run:

```powershell
python -m unittest discover -v
```

Expected: existing behavior is recorded before changes; add or revise tests only if an authorized behavior remains uncovered.

- [ ] **Step 3: Implement the minimal CTG behavior**

In `search_trials.py`:

```python
while len(results) < max_results:
    response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
    response.raise_for_status()
    data = response.json()
    results.extend(self._parse_results(data)[:max_results - len(results)])
    next_token = data.get("nextPageToken")
    if not next_token:
        break
    params["pageToken"] = next_token
```

Send progress/errors to `sys.stderr`; for JSON format write only `json.dumps(...)` to stdout. Normalize missing display values to `—`, support combined phase values, preserve `--source cdt` but call `parser.error("--source cdt 是预留接口，当前尚未实现")`, and remove CDT scraping imports/classes.

Create `requirements.txt` with:

```text
requests>=2.31,<3
```

- [ ] **Step 4: Run CTG tests and compilation after implementation**

Run:

```powershell
python -m unittest discover -v
python -m py_compile search_trials.py
```

Expected: all CTG tests pass and compilation has no output.

- [ ] **Step 5: Confirm removed dependencies and preserved interface**

Run:

```powershell
rg -n "ChinaDrugTrials|DrissionPage|BeautifulSoup|BS4_AVAILABLE|ChromiumPage" .
python search_trials.py --drug ABC123 --source cdt
```

Expected: the `rg` command returns no code matches; the CLI exits with an explicit unimplemented-CDT error.

- [ ] **Step 6: Review the CTG diff**

Run:

```powershell
git diff -- drug-trials-search/search_trials.py drug-trials-search/tests/test_search_trials.py drug-trials-search/tests/__init__.py drug-trials-search/requirements.txt drug-trials-search/SKILL.md
```

Expected: only CTG pagination/output/schema changes and explicit CDT-interface handling are present.

### Task 3: Restrict evaluator output to evidence-based drug assessment

**Files:**
- Modify: `clinical-trial-evaluator/SKILL.md`

**Interfaces:**
- Consumes: user-provided or verifiable trial design, efficacy, safety, and comparator sources.
- Produces: conditional clinical-evidence evaluation with explicit missing-data limits; no investment or commercial forecast.

- [ ] **Step 1: Identify the prohibited legacy claims**

Run:

```powershell
rg -n "投资建议|股价|市场份额|定价能力|商业化|Me-Too|A级|优秀" clinical-trial-evaluator/SKILL.md
```

Expected: legacy definitive example claims or commercial assessment headings are found.

- [ ] **Step 2: Replace definitive framework language and the example**

Keep clinical endpoints as non-decision reference ranges, but add this constraint:

```markdown
下列阈值仅作非决策性参考，必须结合适应症、治疗线、对照、基线风险、样本量与把握度、95% CI、随访时长、estimand、缺失数据和监管语境解释。信息未报告时必须写“无法判断”，不得补全或猜测。
```

Replace the example result with a conditional assessment: it may discuss the reported PFS/ORR/safety observations, must identify missing OS/CI/follow-up/comparator-source information, and must not assign A-grade, “优秀”, “Me-Too”, investment, commercial, pricing, market-share, or regulatory-outcome conclusions.

- [ ] **Step 3: Run the evaluator residual scan**

Run:

```powershell
rg -n "商业化潜力|Me-Too|A级|赛道拥挤|失去机会" clinical-trial-evaluator/SKILL.md
```

Expected: no results.

- [ ] **Step 4: Review evaluator boundaries**

Run:

```powershell
git diff -- clinical-trial-evaluator/SKILL.md
```

Expected: the diff removes commercial/investment conclusions and unsupported definitive example ratings while retaining clinical-evidence guidance.

### Task 4: Make local configuration explicit and safe

**Files:**
- Modify: `.gitignore`
- Create: `config.template.yaml`
- Modify: `initial.md`
- Modify: `README.md`
- Modify: `install.md`

**Interfaces:**
- Consumes: an absolute local data directory chosen during initialization.
- Produces: ignored `config.yaml` and a tracked absolute-path template with `raw_dir`, `summary_dir`, `drug_dir`, `indication_dir`, `trials_dir`, and `attachments_dir`.

- [ ] **Step 1: Add a tracked local configuration template**

Create `config.template.yaml`:

```yaml
# Copy this file to config.yaml and replace every path with an absolute local path.
data_dir: /absolute/path/to/clinical
raw_dir: /absolute/path/to/clinical/raw
summary_dir: /absolute/path/to/clinical/summary
drug_dir: /absolute/path/to/clinical/drug
indication_dir: /absolute/path/to/clinical/indication
trials_dir: /absolute/path/to/clinical/trials
attachments_dir: /absolute/path/to/clinical/attachments
```

Add `config.yaml` to `.gitignore`.

- [ ] **Step 2: Align initialization and installation documentation**

Update `initial.md` to resolve the selected data directory to an absolute path before generating `config.yaml`; do not write `~` literally. Update README/install instructions to direct users to copy the template and install CTG dependencies:

```bash
pip install -r drug-trials-search/requirements.txt
```

- [ ] **Step 3: Verify configuration behavior and documentation references**

Run:

```powershell
git check-ignore -v config.yaml
rg -n "config.template.yaml|requirements.txt|absolute" README.md install.md initial.md
```

Expected: `config.yaml` is ignored and all three documents reference the template or absolute-path requirement where applicable.

- [ ] **Step 4: Review configuration documentation changes**

Run:

```powershell
git diff -- .gitignore config.template.yaml initial.md README.md install.md
```

Expected: the diff introduces a tracked template, ignores only the local config, and documents dependency installation without changing shell portability rules.

### Task 5: Verify the authorized scope and final diff

**Files:**
- Verify: all files modified by Tasks 1-4

**Interfaces:**
- Consumes: completed workflow documentation and CTG implementation.
- Produces: verification evidence without edits to deferred scopes.

- [ ] **Step 1: Confirm deferred scopes are untouched**

Run:

```powershell
git diff -- batch-extractor/SKILL.md
rg -n "专家点评" schema/summary-spec.md
```

Expected: no diff for `batch-extractor/SKILL.md`; the existing expert-commentary material remains in `summary-spec.md`.

- [ ] **Step 2: Run all executable verification**

Run:

```powershell
python -m unittest discover -v
python -m py_compile search_trials.py
```

Working directory for both commands: `drug-trials-search`.

Expected: all tests pass and compilation has no output.

- [ ] **Step 3: Run static contract and whitespace checks**

Run:

```powershell
git diff --check
rg -n "ChinaDrugTrials|DrissionPage|BeautifulSoup|BS4_AVAILABLE|ChromiumPage|默认.*1L|无明确指令 \| clinical-indexer" .
```

Expected: `git diff --check` has no output; no prohibited legacy code or unsafe default routing is found.

- [ ] **Step 4: Inspect final status**

Run:

```powershell
git status --short
git log --oneline -5
```

Expected: only authorized files are included in the completed changes; no commit is created unless explicitly requested by the user.
