from pathlib import Path
import tempfile
import unittest

from scripts.find_unprocessed import find_unprocessed


class FindUnprocessedTests(unittest.TestCase):
    def test_pending_and_role_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for company, drug in (("c1", "d1"), ("c2", "d2")):
                directory = root / company / drug
                (directory / "raw").mkdir(parents=True)
                (directory / "summary").mkdir()
                (directory / f"{drug}.md").write_text("profile", encoding="utf-8")
                (directory / "raw" / "source.md").write_text("raw", encoding="utf-8")
            (root / "c1" / "d1" / "summary" / "source.md").write_text(
                "> 来源原文: [source](../raw/source.md)\n", encoding="utf-8"
            )

            self.assertEqual(find_unprocessed(root), ["c2/d2/raw/source.md"])
            self.assertEqual(find_unprocessed(root, company_id="c1"), [])
            self.assertEqual(find_unprocessed(root, drug_id="d2"), ["c2/d2/raw/source.md"])


if __name__ == "__main__":
    unittest.main()
