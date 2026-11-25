from pathlib import Path
import tempfile
import unittest

from scripts.check_drug_page import check_drug_page


class DrugPageCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.company = self.root / "Company"
        self.summary_dir = self.company / "summary"
        self.summary_dir.mkdir(parents=True)
        self.drug_page = self.company / "DRUG.md"

    def tearDown(self):
        self.temporary.cleanup()

    def write_summary(self, filename="DRUG@S1.md", indications=("IND_A",), efficacy=True):
        summary_path = self.summary_dir / filename
        groups = []
        audit_rows = []
        for indication_id in indications:
            if efficacy:
                core = (
                    "### 核心数据\n\n"
                    "> S1\n\n"
                    "| 指标 | Cohort A |\n"
                    "|------|----------|\n"
                    "| N / 可评估 n | 20 / 18 |\n"
                    "| ORR | 50.0% |\n\n"
                )
            else:
                core = (
                    "### 核心数据\n\n"
                    "| 指标 | Cohort A |\n"
                    "|------|----------|\n"
                    "| N | 20 |\n"
                    "| TRAE | 40% |\n\n"
                )
            groups.append(f"## [{indication_id}] Display {indication_id}\n\n{core}")
            audit_rows.append(
                f"| {indication_id} | ORR | 50.0% | evidence | PASS | — |"
            )
        audit_text = "\n".join(audit_rows)
        summary_path.write_text(
            "---\n"
            "drug_id: DRUG\n"
            f"indications: [{', '.join(indications)}]\n"
            "source_label: S1\n"
            "archive_company: Company\n"
            "verification: passed\n"
            "verification_fail_count: 0\n"
            "verification_coverage: complete\n"
            "---\n\n"
            "# DRUG@S1\n\n"
            "> 来源原文: [Source](../raw/DRUG@S1.md)\n\n"
            f"{''.join(groups)}"
            "## 数据一致性审核\n\n"
            "| indication_id | 数据项 | summary 中的值 | raw 证据 | 状态 | 问题 |\n"
            "|---|---|---|---|---|---|\n"
            f"{audit_text}\n",
            encoding="utf-8",
        )
        return summary_path

    def write_page(self, data_groups, extra_sections=""):
        self.drug_page.write_text(
            "---\n"
            "drug_id: DRUG\n"
            "drug: DRUG\n"
            "target: TARGET\n"
            "archive_company: Company\n"
            "company_ids: [Company]\n"
            "created: 2026-11-25\n"
            "updated: 2026-11-25\n"
            "---\n\n"
            "# DRUG\n\n"
            "## 基本信息\n\n"
            "## 临床数据汇总\n\n"
            f"{data_groups}\n"
            "## 关键里程碑\n\n"
            "## 当前临床管线\n\n"
            "### clinicaltrials.gov\n\n"
            "### chinadrugtrials.org.cn\n\n"
            "## 药品专利\n\n"
            f"{extra_sections}",
            encoding="utf-8",
        )

    @staticmethod
    def source_group(indication_id, table=True, link="summary/DRUG@S1.md"):
        table_text = (
            "> S1\n\n"
            "| 指标 | Cohort A |\n"
            "|------|----------|\n"
            "| N / 可评估 n | 20 / 18 |\n"
            "| ORR | 50.0% |\n\n"
            if table
            else ""
        )
        return (
            f"### [{indication_id}] Display {indication_id}\n\n"
            f"{table_text}"
            f"> 来源: [S1]({link})\n"
        )

    def test_passes_for_embedded_efficacy_table_and_sample_size_variant(self):
        summary = self.write_summary()
        self.write_page(self.source_group("IND_A"))

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["errors"], [])

    def test_fails_when_bullet_points_replace_efficacy_table(self):
        summary = self.write_summary()
        body = (
            "### [IND_A] Display IND_A\n\n"
            "- ORR 50%; mPFS 8.2\n\n"
            "> 来源: [S1](summary/DRUG@S1.md)\n"
        )
        self.write_page(body)

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("缺少" in error and "有效性主表" in error for error in result["errors"]))

    def test_multi_indication_source_link_occurs_once_per_group(self):
        summary = self.write_summary(indications=("IND_A", "IND_B"))
        self.write_page(self.source_group("IND_A") + "\n" + self.source_group("IND_B"))

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "pass")

    def test_safety_only_summary_does_not_require_embedded_table(self):
        summary = self.write_summary(efficacy=False)
        self.write_page(
            "### [IND_A] Display IND_A\n\n"
            "> 来源: [S1](summary/DRUG@S1.md)\n"
        )

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "pass")

    def test_duplicate_source_link_in_same_indication_fails(self):
        summary = self.write_summary()
        group = self.source_group("IND_A") + "\n> 来源: [S1](summary/DRUG@S1.md)\n"
        self.write_page(group)

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("恰好出现一次" in error for error in result["errors"]))

    def test_raw_link_fails(self):
        summary = self.write_summary()
        self.write_page(self.source_group("IND_A") + "\n[raw](raw/DRUG@S1.md)\n")

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("raw/" in error for error in result["errors"]))

    def test_nonstandard_heading_warns_without_blocking(self):
        summary = self.write_summary()
        self.write_page(self.source_group("IND_A"), "## 要点\n\n保留人工备注。\n")

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "warn")
        self.assertEqual(result["errors"], [])

    def test_standalone_remarks_heading_warns_without_blocking(self):
        summary = self.write_summary()
        self.write_page(self.source_group("IND_A"), "## 备注\n\n保留人工内容。\n")

        result = check_drug_page(self.drug_page, [summary])

        self.assertEqual(result["status"], "warn")
        self.assertTrue(any("备注" in warning for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
