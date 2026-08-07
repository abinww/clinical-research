import io
import sys
import types
import unittest
from unittest.mock import patch


class _RequestsStub:
    class RequestException(Exception):
        pass

    class Session:
        def __init__(self):
            self.headers = {}

        def update(self, _headers):
            pass


sys.modules.setdefault("requests", _RequestsStub)

import search_trials
from search_trials import (
    ClinicalTrialsGov,
    TrialResult,
    display_value,
    extract_countries,
    generate_markdown_table,
    generate_pipeline_markdown,
    normalize_phase,
)


class SearchTrialsTests(unittest.TestCase):
    def test_extract_countries_deduplicates_api_locations(self):
        locations = [
            {"country": "United States"},
            {"country": "China"},
            {"country": "United States"},
            {"city": "Unknown"},
        ]

        self.assertEqual(extract_countries(locations), "US、CN")

    def test_extract_countries_lists_all_when_five_or_less(self):
        locations = [
            {"country": "United States"},
            {"country": "Denmark"},
            {"country": "Japan"},
            {"country": "Spain"},
        ]

        self.assertEqual(extract_countries(locations), "US、Denmark、JP、Spain")

    def test_extract_countries_keeps_uncommon_full_name_when_five_or_less(self):
        locations = [
            {"country": "United States"},
            {"country": "China"},
            {"country": "Puerto Rico"},
        ]

        self.assertEqual(extract_countries(locations), "US、CN、Puerto Rico")

    def test_extract_countries_uses_fixed_order_for_core_codes_over_five(self):
        locations = [
            {"country": "Japan"},
            {"country": "United States"},
            {"country": "United Kingdom"},
            {"country": "China"},
            {"country": "Australia"},
            {"country": "France"},
        ]

        self.assertEqual(extract_countries(locations), "US、CN、JP、UK、AU、EU(total 6)")

    def test_extract_countries_merges_european_rest_into_eu_over_five(self):
        locations = [
            {"country": "United States"},
            {"country": "Denmark"},
            {"country": "Japan"},
            {"country": "Spain"},
            {"country": "France"},
            {"country": "Poland"},
        ]

        self.assertEqual(extract_countries(locations), "US、JP、EU(total 6)")

    def test_extract_countries_merges_other_rest_into_etc_over_five(self):
        locations = [
            {"country": "China"},
            {"country": "Australia"},
            {"country": "South Korea"},
            {"country": "Brazil"},
            {"country": "India"},
            {"country": "Singapore"},
        ]

        self.assertEqual(extract_countries(locations), "CN、AU、ETC(total 6)")

    def test_extract_countries_no_total_at_exactly_five(self):
        locations = [
            {"country": "United States"},
            {"country": "China"},
            {"country": "Japan"},
            {"country": "France"},
            {"country": "Australia"},
        ]

        self.assertEqual(extract_countries(locations), "US、CN、JP、FR、AU")

    def test_extract_countries_returns_dash_when_empty(self):
        self.assertEqual(extract_countries([]), "—")
        self.assertEqual(extract_countries(None), "—")

    def test_extract_countries_treats_turkey_as_european_over_five(self):
        locations = [
            {"country": "Turkey (Türkiye)"},
            {"country": "China"},
            {"country": "Japan"},
            {"country": "United States"},
            {"country": "United Kingdom"},
            {"country": "Australia"},
        ]

        self.assertEqual(extract_countries(locations), "US、CN、JP、UK、AU、EU(total 6)")

    def test_markdown_uses_schema_columns_and_embeds_trial_url(self):
        trial = TrialResult()
        trial.trial_id = "NCT00000001"
        trial.drug_name = "ABC123 + Pembrolizumab"
        trial.countries = "US、CN"
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
        self.assertIn("US、CN", output)

    def test_pipeline_output_contains_only_ctg_subtable(self):
        output = generate_pipeline_markdown([])

        self.assertIn("### clinicaltrials.gov", output)
        self.assertNotIn("### chinadrugtrials.org.cn", output)

    def test_normalize_phase_formats_combined_ctg_phases(self):
        self.assertEqual(normalize_phase("PHASE2, PHASE3"), "Phase II, Phase III")

    def test_display_value_normalizes_missing_values(self):
        self.assertEqual(display_value(None), "—")
        self.assertEqual(display_value(""), "—")
        self.assertEqual(display_value("N/A"), "—")
        self.assertEqual(display_value("value"), "value")

    def test_search_follows_next_page_token_until_max_results(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                pass

            def json(self):
                return self.payload

        class Session:
            def __init__(self):
                self.headers = {}
                self.calls = []

            def get(self, _url, params, timeout):
                self.calls.append(params.copy())
                if len(self.calls) == 1:
                    return Response({"studies": [{}], "nextPageToken": "page-2"})
                return Response({"studies": [{}]})

        client = ClinicalTrialsGov()
        client.session = Session()
        client._parse_results = lambda payload: [payload["studies"][0]]

        results = client.search("ABC123", max_results=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(client.session.calls[1]["pageToken"], "page-2")

    def test_search_follows_all_pages_when_max_results_is_omitted(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                pass

            def json(self):
                return self.payload

        class Session:
            def __init__(self):
                self.headers = {}
                self.calls = []

            def get(self, _url, params, timeout):
                self.calls.append(params.copy())
                if len(self.calls) == 1:
                    return Response({"studies": [{}], "nextPageToken": "page-2"})
                return Response({"studies": [{}]})

        client = ClinicalTrialsGov()
        client.session = Session()
        client._parse_results = lambda payload: [payload["studies"][0]]

        results = client.search("ABC123")

        self.assertEqual(len(results), 2)
        self.assertEqual(len(client.session.calls), 2)

    def test_json_format_writes_only_json_to_stdout(self):
        trial = TrialResult()
        trial.trial_id = "NCT00000001"
        trial.source = "CTG"

        class Client:
            def search(self, **_kwargs):
                return [trial]

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(search_trials, "ClinicalTrialsGov", return_value=Client()), \
             patch.object(sys, "argv", ["search_trials.py", "--drug", "ABC123", "--format", "json"]), \
             patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            search_trials.main()

        payload = __import__("json").loads(stdout.getvalue())
        self.assertEqual(payload[0]["临床ID"], "NCT00000001")
        self.assertIn("查询 ClinicalTrials.gov", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
