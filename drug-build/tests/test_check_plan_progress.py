from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "check_plan_progress.py"
SPEC = spec_from_file_location("check_plan_progress", SCRIPT)
progress = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(progress)


def make_drug(root: Path, company: str = "公司", drug: str = "药物") -> Path:
    directory = root / company / drug
    (directory / "raw").mkdir(parents=True)
    (directory / "summary").mkdir()
    (directory / f"{drug}.md").write_text(f"# {drug}\n", encoding="utf-8")
    return directory


class CheckPlanProgressTests(unittest.TestCase):
    def test_extracts_plain_and_markdown_plan_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary) / "plan.md"
            plan.write_text(
                "| # | code | indication | phase | type | date | 网址链接 | note |\n"
                "|---|---|---|---|---|---|---|---|\n"
                "| 1 | x | x | x | x | x | https://example.test/plain | x |\n"
                "| 2 | x | x | x | x | x | [来源](https://example.test/a%20b) | x |\n",
                encoding="utf-8",
            )

            self.assertEqual(
                progress.extract_urls_from_plan(plan),
                ["https://example.test/plain", "https://example.test/a%20b"],
            )

    def test_plan_header_lookup_handles_alignment_and_escaped_pipes(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary) / "plan.md"
            plan.write_text(
                "| note | URL | id |\n"
                "|:---|:---:|---:|\n"
                "| a\\|b | <https://example.test/source> | 1 |\n",
                encoding="utf-8",
            )
            self.assertEqual(progress.extract_urls_from_plan(plan), ["https://example.test/source"])

    def test_checks_nested_drug_by_global_url_and_canonical_source_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "研究"
            drug = make_drug(root, "公司甲", "药甲")
            raw = drug / "raw" / "试验 原文.md"
            raw.write_text("---\nsource: https://example.test/trial\n---\n原文\n", encoding="utf-8-sig")
            summary = drug / "summary" / "试验 原文.md"
            summary.write_text(
                "---\nverification: passed\nverification_fail_count: 0\nverification_coverage: complete\n"
                "indications:\n  - indication_id: NSCLC_1L\n    indication: NSCLC 一线\n---\n"
                "> 来源原文: [试验原文](../raw/试验%20原文.md)\n"
                "## [NSCLC_1L] NSCLC 一线\n\n### 核心数据\n\n"
                "## 数据一致性审核\n\n| indication_id | 数据项 | 状态 |\n|---|---|---|\n"
                "| NSCLC_1L | ORR | PASS |\n",
                encoding="utf-8-sig",
            )

            self.assertEqual(progress.check_url(root, "https://example.test/trial"), "已验证未索引")
            (drug / "药甲.md").write_text(
                "<!-- source_identity: 公司甲/药甲/summary/试验 原文.md -->\n", encoding="utf-8"
            )
            index = root / "index.md"
            index.write_text(
                "## 药品\n<!-- clinical-research:begin drugs -->\n"
                "| drug_id | 通用名 | aliases | 靶点 | 归档公司 |\n|---|---|---|---|---|\n"
                "| [[公司甲/药甲/药甲.md\\|药甲]] | 药甲 | — | — | 公司甲 |\n"
                "<!-- clinical-research:end drugs -->\n"
                "## 适应症\n<!-- clinical-research:begin indications -->\n"
                "| indication_id | 适应症 | 类别 | 治疗线 | 生物标志物 | 更新 |\n"
                "|---|---|---|---|---|---|\n"
                "| [[indication/NSCLC_1L.md\\|NSCLC_1L]] | NSCLC 一线 | NSCLC | 1L | — | 2026-01-01 |\n"
                "<!-- clinical-research:end indications -->\n",
                encoding="utf-8",
            )
            indication = root / "indication" / "NSCLC_1L.md"
            indication.parent.mkdir()
            indication.write_text(
                "<!-- source_identity: 公司甲/药甲/summary/试验 原文.md -->\n", encoding="utf-8"
            )
            self.assertEqual(progress.check_url(root, "https://example.test/trial"), "已完成")
            indication.unlink()
            self.assertEqual(progress.check_url(root, "https://example.test/trial"), "已验证未索引")
            self.assertEqual(progress.check_url(root, "https://example.test/missing"), "未提取")

    def test_requires_exactly_one_summary_and_passed_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            drug = make_drug(root)
            raw = drug / "raw" / "source.md"
            raw.write_text("---\nsource: https://example.test/source\n---\n", encoding="utf-8")

            self.assertEqual(progress.check_url(root, "https://example.test/source"), "已提取未生成summary")
            first = drug / "summary" / "source.md"
            first.write_text(
                "---\nverification: pending\n---\n> 来源原文: [source](../raw/source.md)\n",
                encoding="utf-8",
            )
            self.assertEqual(progress.check_url(root, "https://example.test/source"), "未审核")
            (drug / "summary" / "source-copy.md").write_text(
                "---\nverification: passed\n---\n> 来源原文: [source](../raw/source.md)\n",
                encoding="utf-8",
            )
            self.assertEqual(progress.check_url(root, "https://example.test/source"), "一个raw对应多个summary")

    def test_completion_requires_consistent_audit_state(self):
        valid = (
            "---\nverification: passed\nverification_fail_count: 0\nverification_coverage: complete\n"
            "indications:\n  - indication_id: NSCLC_1L\n    indication: NSCLC 一线\n---\n"
            "## [NSCLC_1L] NSCLC 一线\n\n### 核心数据\n\n"
            "## 数据一致性审核\n\n| indication_id | 数据项 | 值 | 证据 | 状态 |\n"
            "|---|---|---|---|---|\n| NSCLC_1L | ORR | 42% | text | PASS |\n"
        )
        self.assertTrue(progress.summary_audit_passed(valid))
        self.assertTrue(progress.summary_audit_passed(valid.replace("verification_fail_count: 0", "verification_fail_count: '0'")))
        self.assertFalse(progress.summary_audit_passed(valid.replace("verification_fail_count: 0", "verification_fail_count: null")))
        self.assertFalse(progress.summary_audit_passed(valid.replace("verification_fail_count: 0", "verification_fail_count: 0\nverification_fail_count: 0")))
        self.assertFalse(progress.summary_audit_passed(valid.replace("verification: passed", "verification: passed\nverification: failed")))
        self.assertFalse(progress.summary_audit_passed(valid.replace("| PASS |", "| FAIL |")))
        self.assertFalse(progress.summary_audit_passed(valid + "\n## 后续章节\n"))
        self.assertFalse(progress.summary_audit_passed(valid.split("## 数据一致性审核", 1)[0]))

    def test_rejects_duplicate_global_source_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for company, drug_name in (("公司甲", "药甲"), ("公司乙", "药乙")):
                drug = make_drug(root, company, drug_name)
                (drug / "raw" / "source.md").write_text(
                    "---\nsource: https://example.test/duplicate\n---\n", encoding="utf-8"
                )

            self.assertEqual(progress.check_url(root, "https://example.test/duplicate"), "来源对应多个raw")
            self.assertEqual(
                progress.check_url(root, "https://example.test/duplicate", "公司甲", "药甲"),
                "已提取未生成summary",
            )

    def test_config_uses_only_absolute_research_dir(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            config = directory / "config.yaml"
            research_dir = directory / "研究"
            config.write_text(f"research_dir: {research_dir.as_posix()}\n", encoding="utf-8")

            self.assertEqual(progress.load_config(config).research_dir, research_dir.resolve())


if __name__ == "__main__":
    unittest.main()
