from pathlib import Path
import tempfile
import unittest

from scripts.find_unprocessed import find_unprocessed


class FindUnprocessedTests(unittest.TestCase):
    def test_pending_and_role_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for company, drug in (("c1", "d1"), ("c2", "d2")):
                company_dir = root / company
                (company_dir / "raw").mkdir(parents=True)
                (company_dir / "summary").mkdir()
                (company_dir / f"{drug}.md").write_text("profile", encoding="utf-8")
                (company_dir / "raw" / f"{drug}@source.md").write_text("raw", encoding="utf-8")
            (root / "c1" / "summary" / "d1@source.md").write_text(
                "> 来源原文: [source](../raw/d1@source.md)\n", encoding="utf-8"
            )

            self.assertEqual(find_unprocessed(root), ["c2/raw/d2@source.md"])
            self.assertEqual(find_unprocessed(root, company_id="c1"), [])
            self.assertEqual(find_unprocessed(root, drug_id="d2"), ["c2/raw/d2@source.md"])


if __name__ == "__main__":
    unittest.main()
