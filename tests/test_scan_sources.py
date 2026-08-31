from pathlib import Path
import tempfile
import unittest

from scripts.scan_sources import (
    ScanAnomaly,
    frontmatter_value,
    processed_sources,
    raw_sources,
    research_sources,
    semantic_markdown_files,
    _source_urls,
    source_raw_name,
    source_link,
    summary_audit_passed,
)


def make_drug(root: Path, company: str, drug: str) -> Path:
    directory = root / company / drug
    (directory / "raw").mkdir(parents=True)
    (directory / "summary").mkdir()
    (directory / f"{drug}.md").write_text(f"# {drug}\n", encoding="utf-8")
    return directory


class ScanSourcesTests(unittest.TestCase):
    def test_parses_only_canonical_source_link(self):
        text = "# 摘要\n> 来源原文: [试验原文](../raw/试验%20一.md)\n"
        self.assertEqual(source_raw_name(text), "raw/试验 一.md")
        self.assertIsNone(source_raw_name("> 来源原文: [[raw/legacy.md]]"))
        self.assertIsNone(source_raw_name("> 来源原文: [wrong](raw/file.md)"))
        self.assertIsNone(source_raw_name("> 来源原文: [nested](../raw/nested/file.md)"))
        self.assertIsNone(source_raw_name("> 来源原文: [encoded](../raw/nested%2Ffile.md)"))
        self.assertIsNone(source_raw_name(text + text))
        self.assertIsNone(source_raw_name(text + "> 来源原文: [[raw/legacy.md]]\n"))
        generated = source_link("试验 #1 (final).md", "source")
        self.assertEqual(generated, "> 来源原文: [source](../raw/%E8%AF%95%E9%AA%8C%20%231%20%28final%29.md)")
        self.assertEqual(source_raw_name(generated), "raw/试验 #1 (final).md")

    def test_processed_and_pending_use_distinct_root_relative_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "研究"
            first = make_drug(root, "公司甲", "药甲")
            second = make_drug(root, "公司乙", "药乙")
            for drug in (first, second):
                (drug / "raw" / "same.md").write_text("source: https://example.test\n", encoding="utf-8-sig")
            (first / "summary" / "same.md").write_text(
                "# 摘要\n> 来源原文: [same](../raw/same.md)\n", encoding="utf-8-sig"
            )

            raw, processed = research_sources(root)
            identities = {identity for _, identity in raw}

            self.assertEqual(identities, {"公司甲/药甲/raw/same.md", "公司乙/药乙/raw/same.md"})
            self.assertEqual(processed, {"公司甲/药甲/raw/same.md": "公司甲/药甲/summary/same.md"})
            self.assertEqual(identities - processed.keys(), {"公司乙/药乙/raw/same.md"})

    def test_direct_directory_scanners_use_drug_relative_posix_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            drug = make_drug(Path(temporary), "company", "drug")
            raw = drug / "raw" / "源.md"
            raw.write_text("text", encoding="utf-8")
            summary = drug / "summary" / "源.md"
            summary.write_text("> 来源原文: [源](../raw/源.md)\n", encoding="utf-8")

            self.assertEqual(raw_sources(drug / "raw"), [(raw, "raw/源.md")])
            self.assertEqual(processed_sources(drug / "summary"), {"raw/源.md"})

    def test_mismatched_summary_filename_remains_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            drug = make_drug(root, "company", "drug")
            (drug / "raw" / "source.md").write_text("raw", encoding="utf-8")
            (drug / "summary" / "different.md").write_text(
                "> 来源原文: [source](../raw/source.md)\n", encoding="utf-8"
            )

            raw, processed = research_sources(root)
            self.assertEqual([identity for _, identity in raw], ["company/drug/raw/source.md"])
            self.assertEqual(processed, {})

    def test_reports_mismatch_and_duplicate_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            drug = make_drug(root, "company", "drug")
            (drug / "raw" / "source.md").write_text("raw", encoding="utf-8")
            for name in ("different.md", "other.md"):
                (drug / "summary" / name).write_text(
                    "> 来源原文: [source](../raw/source.md)\n", encoding="utf-8"
                )
            anomalies: list[ScanAnomaly] = []

            research_sources(root, anomalies)

            self.assertEqual(sum(item.kind == "mismatched_summary" for item in anomalies), 2)
            self.assertEqual(sum(item.kind == "duplicate_summary" for item in anomalies), 1)

    def test_urls_read_source_only_from_opening_frontmatter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frontmatter = root / "frontmatter.md"
            body = root / "body.md"
            frontmatter.write_text("---\nsource: https://example.test/front\n---\nsource: body\n", encoding="utf-8")
            body.write_text("# Raw\nsource: https://example.test/body\n", encoding="utf-8")

            self.assertEqual(_source_urls([frontmatter, body]), ["https://example.test/front"])

    def test_frontmatter_scalar_rejects_duplicate_and_preserves_hash(self):
        self.assertEqual(frontmatter_value("source: https://example.test/a#b", "source"), "https://example.test/a#b")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            frontmatter_value("source: one\nsource: two", "source")

    def test_audit_requires_real_final_heading_and_nonempty_canonical_table(self):
        prefix = (
            "---\nverification: passed\nverification_fail_count: '0'\nverification_coverage: complete\n"
            "indications:\n  - indication_id: NSCLC_1L\n    indication: NSCLC 一线\n---\n"
        )
        valid = (
            prefix
            + "## [NSCLC_1L] NSCLC 一线\n\n### 核心数据\n\n"
            "## 数据一致性审核\n| indication_id | 数据项 | 状态 |\n|---|---|---|\n"
            "| NSCLC_1L | ORR | WARN |\n"
        )
        self.assertTrue(summary_audit_passed(valid))
        self.assertFalse(summary_audit_passed(prefix + "```\n" + valid.split("---\n", 2)[-1] + "```\n"))
        self.assertFalse(summary_audit_passed(valid.replace("NSCLC_1L | ORR", " | ORR")))
        self.assertFalse(summary_audit_passed(valid.replace("WARN", "UNKNOWN")))
        self.assertFalse(summary_audit_passed(valid + "### 后续\n"))
        self.assertFalse(summary_audit_passed(valid.replace("verification_coverage: complete\n", "")))

    def test_semantic_scan_excludes_infrastructure_and_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            included = root / "公司" / "药" / "药.md"
            included.parent.mkdir(parents=True)
            included.write_text("content", encoding="utf-8")
            excluded = [
                root / "index.md",
                root / "indication" / "one.md",
                root / "attachments" / "two.md",
                root / ".temp" / "plans" / "three.md",
                root / "TEMP" / "four.md",
            ]
            for path in excluded:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("content", encoding="utf-8")

            self.assertEqual(semantic_markdown_files(root), [included])


if __name__ == "__main__":
    unittest.main()
