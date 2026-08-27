"""search_patents 离线测试（不发起网络请求）。"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import search_patents
from search_patents import (
    FreePatentsOnline,
    GooglePatents,
    PatentResult,
    aggregate_by_assignee,
    aggregate_by_type,
    aggregate_type_year,
    classify_patent,
    cpc_remark,
    display_value,
    merge_results,
    norm_date,
    render_company_markdown,
    render_drug_markdown,
    sort_key,
)


class ClassifyTests(unittest.TestCase):
    def test_cpc_combo_rule_wins_over_compound(self):
        # 联用专利常同时含 A61K47/68，combo 规则必须优先
        self.assertEqual(
            classify_patent("X", ["A61K47/68", "A61K45/06", "A61P35/00"]),
            "combo",
        )
        self.assertEqual(
            classify_patent("X", ["A61K47/68", "A61K2300/00"]), "combo"
        )

    def test_cpc_compound_by_structure_codes(self):
        self.assertEqual(
            classify_patent("(Anti-HER2 antibody)-drug conjugate",
                            ["A61K47/68", "C07K16/32", "A61K31/4745"]),
            "compound",
        )

    def test_cpc_use_when_only_therapeutic_codes(self):
        self.assertEqual(
            classify_patent("Scoring method", ["A61P35/00", "A61K9/00"]),
            "use",
        )

    def test_cpc_fallback_to_other(self):
        self.assertEqual(classify_patent("A kit for measuring a sample", ["C12Q1/68"]), "other")

    def test_use_title_wins_over_cpc_compound(self):
        # 评分/标志物类用途专利常携带结构码 A61K47/68，标题用途应优先
        self.assertEqual(
            classify_patent("A Scoring Method for an Anti-HER2 ADC Therapy",
                            ["G01N33/574", "A61K47/68"]),
            "use",
        )

    def test_combo_title_wins_over_cpc_compound(self):
        # 联用专利标题"combination of..."优先于 CPC 结构码
        self.assertEqual(
            classify_patent(
                "COMBINATION OF ANTIBODY-DRUG CONJUGATE AND BISPECIFIC CHECKPOINT INHIBITOR",
                ["A61K47/68", "A61K39/00"]),
            "combo",
        )

    def test_title_combo_heuristic(self):
        self.assertEqual(
            classify_patent("COMBINATION OF ANTIBODY-DRUG CONJUGATE AND ATR INHIBITOR"),
            "combo",
        )

    def test_title_use_heuristic(self):
        self.assertEqual(
            classify_patent("METHOD FOR TREATING CANCER BY USING ANTIBODY-DRUG CONJUGATE"),
            "use",
        )
        self.assertEqual(
            classify_patent("USE OF AN RXR AGONIST IN TREATING HER2+ CANCERS"),
            "use",
        )

    def test_title_compound_heuristic(self):
        self.assertEqual(
            classify_patent("ANTI-HER2 ANTIBODY-DRUG CONJUGATES AND USES THEREOF"),
            "compound",
        )

    def test_title_unknown_is_other(self):
        self.assertEqual(classify_patent("A kit for measuring a sample"), "other")


class RemarkTests(unittest.TestCase):
    def test_cpc_remark_skips_pure_use_combo_codes(self):
        self.assertEqual(
            cpc_remark(["A61K45/06", "A61K2300/00", "A61P35/00", "C07K16/32", "A61K47/68"]),
            "C07K16/32 · A61K47/68",
        )

    def test_cpc_remark_empty(self):
        self.assertEqual(cpc_remark([]), "—")
        self.assertEqual(cpc_remark(None), "—")


class NormDateTests(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(norm_date("2021-01-02"), "2021-01-02")

    def test_compact(self):
        self.assertEqual(norm_date("20210102"), "2021-01-02")

    def test_us_slash(self):
        self.assertEqual(norm_date("09/21/2023"), "2023-09-21")

    def test_year_only(self):
        self.assertEqual(norm_date("2021"), "2021-01-01")

    def test_missing(self):
        self.assertEqual(norm_date(None), "—")
        self.assertEqual(norm_date(""), "—")


class MergeTests(unittest.TestCase):
    def test_merge_dedups_by_publication_number(self):
        a = PatentResult(publication_number="US11185594B2", title="T1")
        b = PatentResult(publication_number="US11185594B2", title="T1")
        c = PatentResult(publication_number="CN105829346B", title="T2")
        out = merge_results([a, b, c])
        self.assertEqual(len(out), 2)
        numbers = {pr.publication_number for pr in out}
        self.assertEqual(numbers, {"US11185594B2", "CN105829346B"})

    def test_merge_drops_empty(self):
        out = merge_results([PatentResult(publication_number="")])
        self.assertEqual(out, [])


class GooglePatentsParseTests(unittest.TestCase):
    def test_parse_extracts_fields_and_strips_html(self):
        data = {
            "results": {
                "total_num_results": 1,
                "cluster": [
                    {"result": [
                        {"patent": {
                            "publication_number": "<b>US11185594B2</b>",
                            "title": "(Anti-HER2 <b>antibody</b>)-drug conjugate",
                            "assignee": ["Daiichi <b>Sankyo</b> Company"],
                            "filing_date": "2015-04-06",
                            "grant_date": "2021-11-16",
                        }}
                    ]}
                ],
            }
        }
        patents = GooglePatents._parse(data)
        self.assertEqual(len(patents), 1)
        pr = patents[0]
        self.assertEqual(pr.publication_number, "US11185594B2")
        self.assertEqual(pr.title, "(Anti-HER2 antibody)-drug conjugate")
        self.assertEqual(pr.assignee, "Daiichi Sankyo Company")
        self.assertEqual(pr.filing_date, "2015-04-06")
        self.assertEqual(pr.grant_date, "2021-11-16")
        self.assertEqual(pr.source, "GP")
        self.assertEqual(pr.patent_type, "compound")
        self.assertIn("patents.google.com/patent/US11185594B2", pr.url)

    def test_parse_skips_empty_publication(self):
        data = {"results": {"total_num_results": 1, "cluster": [
            {"result": [{"patent": {"publication_number": "", "title": "x"}}]}]}}
        self.assertEqual(GooglePatents._parse(data), [])

    def test_parse_handles_string_assignee(self):
        # GP 的 assignee 字段可能是字符串而非列表
        data = {
            "results": {
                "cluster": [
                    {"result": [{"patent": {
                        "publication_number": "US123",
                        "title": "Camptothecin drug &amp; conjugate &hellip;",
                        "assignee": "<b>Daiichi</b> Sankyo Company, Limited",
                        "filing_date": "2021-01-01",
                    }}]}
                ]
            }
        }
        patents = GooglePatents._parse(data)
        self.assertEqual(patents[0].assignee, "Daiichi Sankyo Company, Limited")
        self.assertEqual(patents[0].title, "Camptothecin drug & conjugate …")

    def test_title_use_plural_methods(self):
        self.assertEqual(
            classify_patent("Methods of treating lung cancer"), "use"
        )


class FreePatentsOnlineParseTests(unittest.TestCase):
    def test_parse_list_extracts_rows(self):
        html = (
            '<table><tr class=rowalt><td width="5%"><label>1</label></td>'
            '<td width="15%" valign="top"> US20230330243 </td>'
            '<td width="60%" valign="top"> <a href="/y2023/0330243.html">'
            "COMBINATION OF ANTIBODY-DRUG CONJUGATE AND ATR INHIBITOR</a>"
            "</td></tr>"
            '<tr class=>'
            '<td width="15%" valign="top"> US11185594 </td>'
            '<td width="60%" valign="top"> <a href="/11185594.html">'
            "(Anti-HER2 antibody)-drug conjugate</a>"
            "</td></tr></table>"
        )
        rows = FreePatentsOnline._parse_list(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "US20230330243")
        self.assertEqual(rows[0][2], "COMBINATION OF ANTIBODY-DRUG CONJUGATE AND ATR INHIBITOR")
        self.assertEqual(rows[1][1], "/11185594.html")

    def test_parse_detail_granted_with_cpc(self):
        html = (
            '<div class="disp_elm_title">Application Number:</div>'
            '<div class="disp_elm_text"> 15/955,432 </div>'
            '<!-- Filing Date --><div class="disp_doc2">'
            '<div class="disp_elm_title">Filing Date:</div>'
            '<div class="disp_elm_text"> 04/06/2015 </div></div>'
            '<!-- Publication Date --><div class="disp_doc2">'
            '<div class="disp_elm_title">Publication Date:</div>'
            '<div class="disp_elm_text"> 09/21/2023 </div></div>'
            '<!-- Issue Date --><div class="disp_doc2">'
            '<div class="disp_elm_title">Issue Date:</div>'
            '<div class="disp_elm_text"> 11/16/2021 </div></div>'
            '<!-- Assignee --><div class="disp_doc2">'
            '<div class="disp_elm_title">Assignee:</div>'
            '<div class="disp_elm_text"> DAIICHI SANKYO COMPANY, LIMITED <br/></div></div>'
            "A61K47/68 A61K31/4745 C07K16/32"
        )
        pr = FreePatentsOnline._parse_detail("US11185594", "Anti-HER2 conjugate", html)
        self.assertEqual(pr.filing_date, "2015-04-06")
        self.assertEqual(pr.publication_date, "2023-09-21")
        self.assertEqual(pr.grant_date, "2021-11-16")
        self.assertEqual(pr.assignee, "DAIICHI SANKYO COMPANY, LIMITED")
        self.assertIn("A61K47/68", pr.cpc)
        self.assertEqual(pr.patent_type, "compound")
        self.assertEqual(pr.remark, "A61K47/68 · A61K31/4745")

    def test_parse_detail_application_no_cpc(self):
        html = (
            '<!-- Filing Date --><div class="disp_doc2">'
            '<div class="disp_elm_title">Filing Date:</div>'
            '<div class="disp_elm_text"> 06/23/2021 </div></div>'
            '<!-- Publication Date --><div class="disp_doc2">'
            '<div class="disp_elm_title">Publication Date:</div>'
            '<div class="disp_elm_text"> 08/17/2023 </div></div>'
            '<!-- Assignee --><div class="disp_doc2">'
            '<div class="disp_elm_title">Assignee:</div>'
            '<div class="disp_elm_text"> AstraZeneca UK Limited </div></div>'
        )
        pr = FreePatentsOnline._parse_detail("US20230256110", "COMBINATION ... ATM INHIBITOR", html)
        self.assertEqual(pr.patent_type, "combo")
        self.assertEqual(pr.cpc, [])

    def test_parse_detail_none_html(self):
        pr = FreePatentsOnline._parse_detail("US1", "t", None)
        self.assertEqual(pr.filing_date, "—")
        self.assertEqual(pr.assignee, "—")


class RenderTests(unittest.TestCase):
    def _patents(self):
        combo = PatentResult(
            publication_number="US20230330243A1", title="COMBINATION OF ADC AND ATR INHIBITOR",
            assignee="Daiichi Sankyo", filing_date="2021-06-23", url="u1",
            source="GP", patent_type="combo",
        )
        core = PatentResult(
            publication_number="US11185594B2", title="(Anti-HER2 antibody)-drug conjugate",
            assignee="Daiichi Sankyo", filing_date="2015-04-06", url="u2",
            source="GP", patent_type="compound",
        )
        return [combo, core]

    def test_drug_markdown_has_required_columns_and_summaries(self):
        out = render_drug_markdown(self._patents(), "GP")
        self.assertIn("## 药品专利", out)
        self.assertIn("| 公开号 | 标题 | 类型 | 申请人 | 申请日 | 备注 |", out)
        self.assertIn("> 类型分布: compound 1 · combo 1", out)
        self.assertIn("> 申请人分布: Daiichi Sankyo 2", out)
        self.assertIn("> 数据来源: Google Patents", out)

    def test_drug_markdown_sorts_compound_first(self):
        out = render_drug_markdown(self._patents(), "GP")
        core_idx = out.index("US11185594B2")
        combo_idx = out.index("US20230330243A1")
        self.assertLess(core_idx, combo_idx)

    def test_company_markdown_has_type_year_aggregation(self):
        out = render_company_markdown(self._patents(), "Kymera", "2020-01-01",
                                      "2026-12-31", "CN", "GP")
        self.assertIn("# Kymera 专利方向", out)
        self.assertIn("## 类型 × 年份分布", out)
        self.assertIn("| 类型 | 2015 | 2021 |", out)
        self.assertIn("| 核心物质 | 1 | 0 |", out)
        self.assertIn("| 联合用药 | 0 | 1 |", out)


class AggregateTests(unittest.TestCase):
    def _patents(self):
        return [
            PatentResult(patent_type="compound", assignee="A", filing_date="2021-06-23"),
            PatentResult(patent_type="combo", assignee="A", filing_date="2021-06-23"),
            PatentResult(patent_type="combo", assignee="B", filing_date="2022-01-10"),
        ]

    def test_by_type(self):
        self.assertEqual(dict(aggregate_by_type(self._patents())),
                         {"compound": 1, "combo": 2})

    def test_by_assignee(self):
        self.assertEqual(dict(aggregate_by_assignee(self._patents())), {"A": 2, "B": 1})

    def test_type_year(self):
        self.assertEqual(aggregate_type_year(self._patents()),
                         {"compound": {2021: 1}, "combo": {2021: 1, 2022: 1}})


class SortKeyTests(unittest.TestCase):
    def test_compound_sorts_before_combo(self):
        combo = PatentResult(publication_number="X1", patent_type="combo",
                             filing_date="2023-01-01")
        core = PatentResult(publication_number="X2", patent_type="compound",
                            filing_date="2021-01-01")
        self.assertLess(sort_key(core), sort_key(combo))

    def test_same_type_newer_filing_first(self):
        old = PatentResult(publication_number="X1", patent_type="combo",
                           filing_date="2021-01-01")
        new = PatentResult(publication_number="X2", patent_type="combo",
                           filing_date="2023-01-01")
        self.assertLess(sort_key(new), sort_key(old))


class DisplayValueTests(unittest.TestCase):
    def test_normalizes(self):
        self.assertEqual(display_value(None), "—")
        self.assertEqual(display_value(""), "—")
        self.assertEqual(display_value("nan"), "—")
        self.assertEqual(display_value("x"), "x")


if __name__ == "__main__":
    unittest.main()