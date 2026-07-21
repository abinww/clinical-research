# Consolidate Indexing Subskills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `clinical-indexer` the single owner of summary-to-index workflows, then remove the redundant `clinical-drug-summarizer` and `clinical-wiki` subskills.

**Architecture:** `clinical-indexer` supports three scopes: full rebuild/update, one-drug update, and unorganized-summary incremental update. `clinical-extractor` and `batch-extractor` remain extraction workflows; `drug-trials-search` and `clinical-trial-evaluator` remain independent specialist workflows.

**Tech Stack:** Markdown SKILL workflows, YAML routing documentation, shell discovery commands.

## Global Constraints

- Keep table and document formats in `schema/`, not in SKILL workflow files.
- Keep `drug/{药品名}.md` flat and `summary/{药品名}/` grouped by drug.
- Use `drug-spec.md` and `indication-spec.md` as the only index format sources.
- Do not migrate production data in this change.
- Preserve `clinical-extractor` and `batch-extractor` behavior except for routing documentation.

## Tasks

### Task 1: Add single-drug index mode

**Files:**
- Modify: `clinical-indexer/SKILL.md`

- [ ] Add input scope detection before scanning:
  - explicit drug name -> scan only `summary/{药品名}/`, update only `drug/{药品名}.md`
  - no drug name -> retain full scan and update drug/indication indexes
- [ ] State that single-drug mode must not update indication indexes or unrelated drug pages.
- [ ] Remove inline Markdown table examples and refer to schemas for all output format.
- [ ] Add single-drug completion report.

### Task 2: Reroute and remove drug summarizer

**Files:**
- Modify: `SKILL.md`, `README.md`, `install.md`
- Delete: `clinical-drug-summarizer/SKILL.md`

- [ ] Route summarizer phrases to `clinical-indexer` single-drug mode.
- [ ] Update README and install completeness checks.
- [ ] Delete the obsolete subskill directory.

### Task 3: Add unorganized-summary mode

**Files:**
- Modify: `clinical-indexer/SKILL.md`, `SKILL.md`

- [ ] Add incremental scope that extracts `[[summary/...]]` references from drug/ and indication/.
- [ ] Compute `all summaries - organized summaries`.
- [ ] Process only unorganized summaries and update corresponding drug/indication pages.
- [ ] Route archive/sync/unorganized phrases to this indexer mode.

### Task 4: Remove clinical-wiki

**Files:**
- Modify: `README.md`, `install.md`
- Delete: `clinical-wiki/SKILL.md`

- [ ] Remove the obsolete directory and documentation entries.

### Task 5: Verify consolidation

**Files:**
- Verify: `SKILL.md`, `README.md`, `install.md`, `clinical-indexer/SKILL.md`

- [ ] Confirm no route points to deleted subskills.
- [ ] Confirm no README/install completeness entry names deleted subskills.
- [ ] Confirm all seven old route categories map to the remaining five subskills.
- [ ] Run `git diff --check` and inspect `git status`.
