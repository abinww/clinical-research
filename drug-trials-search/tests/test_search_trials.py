import sys
import types
import unittest


class _RequestsStub:
    class RequestException(Exception):
        pass

    class Session:
        def __init__(self):
            self.headers = {}

        def update(self, _headers):
            pass


sys.modules.setdefault("requests", _RequestsStub)

from search_trials import TrialResult, extract_countries, generate_markdown_table, generate_pipeline_markdown


class SearchTrialsTests(unittest.TestCase):
    def test_extract_countries_deduplicates_api_locations(self):
        locations = [
            {"country": "United States"},
            {"country": "China"},
            {"country": "United States"},
            {"city": "Unknown"},
        ]

        self.assertEqual(extract_countries(locations), "United States、China")

    def test_markdown_uses_schema_columns_and_embeds_trial_url(self):
        trial = TrialResult()
        trial.trial_id = "NCT00000001"
        trial.drug_name = "ABC123 + Pembrolizumab"
        trial.countries = "United States、China"
        trial.indication = "Example Cancer"
        trial.phase = "PHASE2"
        trial.status = "RECRUITING"
        trial.enrollment = "120"
        trial.start_date = "2023-06"
        trial.completion_date = "2025-12"
        trial.control_drug = "Placebo"
        trial.sponsor = "BigPharma"
        trial.primary_outcome = "ORR"
        trial.secondary_outcome = "PFS"
        trial.last_update = "2025-06"
        trial.url = "https://clinicaltrials.gov/study/NCT00000001"
        trial.source = "CTG"

        output = generate_markdown_table([trial])

        self.assertIn(
            "| 试验ID | 药品 | 开展国家 | 适应症 | 阶段 | 状态 | 入组 | 开始 | 预计完成 | 对照 | Sponsor | 主要终点 | 次要终点 | 更新 |",
            output,
        )
        self.assertIn(
            "[NCT00000001](https://clinicaltrials.gov/study/NCT00000001)",
            output,
        )
        self.assertNotIn("| 来源 |", output)
        self.assertNotIn("| 链接 |", output)
        self.assertIn("United States、China", output)

    def test_pipeline_output_contains_only_ctg_subtable(self):
        output = generate_pipeline_markdown([])

        self.assertIn("### clinicaltrials.gov", output)
        self.assertNotIn("### chinadrugtrials.org.cn", output)


if __name__ == "__main__":
    unittest.main()
