# Clinical Research Codex Skill

Clinical Research is a Codex skill for routing and executing clinical research data workflows. It is designed to help collect, normalize, index, summarize, and evaluate clinical trial materials while keeping source data, structured summaries, and drug or indication indexes separated.

## What It Does

- Routes clinical research requests to the correct sub-skill.
- Extracts clinical data from URLs or PDFs into raw source files.
- Converts raw materials into structured clinical summaries.
- Updates drug and indication indexes from normalized summaries.
- Searches clinical trial registries for drug trial pipelines.
- Provides a structured framework for evaluating clinical trial data.

## Included Sub-Skills

| Directory | Purpose |
| --- | --- |
| `clinical-extractor/` | Extract clinical data from URLs or PDFs. |
| `batch-extractor/` | Batch process raw clinical materials into structured summaries. |
| `clinical-indexer/` | Build or update drug and indication indexes. |
| `clinical-wiki/` | Organize unarchived clinical summaries into wiki-style indexes. |
| `clinical-drug-summarizer/` | Summarize all available clinical data for a drug. |
| `drug-trials-search/` | Search clinical trial registries and update trial pipeline tables. |
| `clinical-trial-evaluator/` | Evaluate clinical trial data using a structured framework. |
| `schema/` | Markdown specifications for summaries, drug indexes, and indication indexes. |

## Installation

Copy the `clinical-research` directory into your Codex skills directory.

Typical layouts are:

```text
<CODEX_HOME>/skills/clinical-research/
```

or, for a repository-based workflow:

```bash
git clone https://github.com/<your-username>/clinical-research.git
```

Then place or link the cloned `clinical-research` directory under your Codex skills directory.

## Usage

Trigger the top-level skill with requests such as:

```text
提取临床数据: <URL>
```

```text
查询某个药品的临床试验
```

```text
更新药品索引
```

```text
评价这项临床试验数据
```

The top-level `SKILL.md` routes the request to the relevant sub-skill. Each sub-skill contains its own workflow and must be read before execution.

## Data Directory

By default, the skill expects clinical data under:

```text
/mnt/ur/notes/资料/clinical/
```

The shared directory configuration lives in:

```text
config.yaml
```

Update `config.yaml` if your local data directory is different.

## Safety Notes

- Do not commit private patient data, API keys, credentials, unpublished clinical materials, or proprietary documents.
- Review generated summaries before relying on them for research decisions.
- This skill is for research organization and analysis support. It is not medical advice.

## License

MIT License. See `LICENSE`.
