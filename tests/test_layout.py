from pathlib import Path
import tempfile
import unittest

from scripts.layout import (
    DrugLayout,
    discover_drugs,
    is_contained,
    is_valid_filename,
    is_valid_identifier,
    sanitize_filename,
)


class LayoutTests(unittest.TestCase):
    def test_discovers_only_complete_company_drug_layouts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / "企业甲" / "药物一"
            valid.mkdir(parents=True)
            (valid / "药物一.md").write_text("# 药物一", encoding="utf-8")
            (root / "企业甲" / "incomplete").mkdir()
            excluded = root / "attachments" / "fake"
            excluded.mkdir(parents=True)
            (excluded / "fake.md").write_text("# fake", encoding="utf-8")
            hidden = root / ".cache" / "hidden"
            hidden.mkdir(parents=True)
            (hidden / "hidden.md").write_text("# hidden", encoding="utf-8")

            self.assertEqual(discover_drugs(root), [DrugLayout(root, "企业甲", "药物一")])

    def test_excludes_all_reserved_root_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role in ("raw", "summary", "drug", "trials", ".anything"):
                candidate = root / role / "fake"
                candidate.mkdir(parents=True)
                (candidate / "fake.md").write_text("profile", encoding="utf-8")
            valid = root / "company" / "drug"
            valid.mkdir(parents=True)
            (valid / "drug.md").write_text("profile", encoding="utf-8")

            self.assertEqual(discover_drugs(root), [DrugLayout(root.resolve(), "company", "drug")])
            self.assertTrue(is_contained(valid, root))

    def test_windows_filename_validation_and_sanitization(self):
        self.assertTrue(is_valid_filename("中文研究.md"))
        self.assertFalse(is_valid_filename("CON.md"))
        self.assertFalse(is_valid_filename("trial:phase.md"))
        self.assertEqual(sanitize_filename("CON.md"), "_CON.md")
        self.assertEqual(sanitize_filename("trial:phase?.md"), "trial_phase_.md")
        self.assertTrue(is_valid_identifier("第一三共"))
        self.assertTrue(is_valid_identifier("Merck KGaA"))
        self.assertFalse(is_valid_identifier("Drug@A"))
        self.assertFalse(is_valid_identifier("Drug#A"))

    def test_reports_invalid_complete_drug_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = root / "Company@Bad" / "Drug"
            invalid.mkdir(parents=True)
            (invalid / "Drug.md").write_text("profile", encoding="utf-8")
            rejected = []
            self.assertEqual(discover_drugs(root, rejected), [])
            self.assertEqual(rejected, [root / "Company@Bad"])


if __name__ == "__main__":
    unittest.main()
