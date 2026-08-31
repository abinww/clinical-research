from pathlib import Path
import tempfile
import unittest

from scripts.config import load_config, read_config, restricted_scalar


class ConfigTests(unittest.TestCase):
    def test_requires_research_dir(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.yaml"
            config.write_text("other: value\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "research_dir"):
                read_config(config)

    def test_derives_paths_from_absolute_chinese_research_dir(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.yaml"
            research_dir = Path(temporary) / "研究资料"
            config.write_text(f"\ufeffresearch_dir: {research_dir.as_posix()}\n", encoding="utf-8")

            paths = load_config(config)

            self.assertEqual(paths.research_dir, research_dir.resolve())
            self.assertEqual(paths.index, paths.research_dir / "index.md")
            self.assertEqual(paths.indication, paths.research_dir / "indication")
            self.assertEqual(paths.attachments, paths.research_dir / "attachments")
            self.assertEqual(paths.plans, paths.research_dir / ".temp" / "plans")

    def test_rejects_relative_path_and_extra_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.yaml"
            config.write_text("research_dir: research\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "绝对路径"):
                load_config(config)

            config.write_text(f"research_dir: {Path(temporary).as_posix()}\nraw_dir: old\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "不支持的字段"):
                load_config(config)

    def test_rejects_duplicate_and_malformed_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.yaml"
            root = Path(temporary).as_posix()
            config.write_text(f"research_dir: {root}\nresearch_dir: {root}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "重复字段"):
                read_config(config)

            config.write_text(f"research_dir: {root}\nmalformed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "格式无效"):
                read_config(config)

    def test_preserves_hash_in_quoted_absolute_path_and_ignores_inline_comment(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.yaml"
            research_dir = Path(temporary) / "研究#资料"
            config.write_text(
                f'research_dir: "{research_dir.as_posix()}" # local research root\n', encoding="utf-8"
            )

            self.assertEqual(load_config(config).research_dir, research_dir.resolve())

    def test_restricted_scalar_preserves_url_fragments_and_apostrophes(self):
        self.assertEqual(restricted_scalar("https://example.test/a#fragment"), "https://example.test/a#fragment")
        self.assertEqual(restricted_scalar("O'Brien # comment"), "O'Brien")
        self.assertEqual(restricted_scalar("# comment only"), "")
        self.assertEqual(restricted_scalar("'O''Brien # literal' # comment"), "O'Brien # literal")
        self.assertEqual(restricted_scalar(r'"a\tb" # comment'), "a\tb")
        with self.assertRaises(ValueError):
            restricted_scalar("'unterminated")


if __name__ == "__main__":
    unittest.main()
