from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "attach_pdf.py"
SPEC = spec_from_file_location("attach_pdf", SCRIPT)
attach_pdf = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(attach_pdf)


class AttachPdfTests(unittest.TestCase):
    def test_attaches_small_pdf_with_source_named_stem_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "report.pdf"
            payload = b"%PDF-1.4\nfake pdf bytes\n"
            pdf.write_bytes(payload)
            attachments = Path(temporary) / "attachments"

            status, path = attach_pdf.attach(pdf, attachments, "药甲@ASCO2026")
            self.assertEqual(status, "attached")
            expected = attachments / "药甲@ASCO2026.pdf"
            self.assertEqual(Path(path), expected.resolve())
            self.assertEqual(expected.read_bytes(), payload)

            payload_before = expected.read_bytes()
            status, path = attach_pdf.attach(pdf, attachments, "药甲@ASCO2026")
            self.assertEqual(status, "attached")
            self.assertEqual(Path(path), expected.resolve())
            self.assertEqual(expected.read_bytes(), payload_before)
            self.assertEqual(len(list(attachments.glob("*.pdf"))), 1)

    def test_distinct_stems_create_distinct_attachments(self):
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "report.pdf"
            pdf.write_bytes(b"%PDF-1.4\ncontent\n")
            attachments = Path(temporary) / "attachments"

            attach_pdf.attach(pdf, attachments, "药甲@ASCO2026")
            attach_pdf.attach(pdf, attachments, "药甲@ESMO2026")
            self.assertEqual(sorted(path.name for path in attachments.glob("*.pdf")), ["药甲@ASCO2026.pdf", "药甲@ESMO2026.pdf"])

    def test_oversized_pdf_is_not_copied_and_reports_too_large(self):
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "big.pdf"
            pdf.write_bytes(b"\x00" * (11 * 1024 * 1024))
            attachments = Path(temporary) / "attachments"

            status, path = attach_pdf.attach(pdf, attachments, "药甲@Big")
            self.assertEqual(status, "too_large")
            self.assertEqual(path, pdf.resolve().as_posix())
            self.assertFalse(attachments.exists())

    def test_missing_pdf_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.pdf"
            with self.assertRaisesRegex(ValueError, "不存在"):
                attach_pdf.attach(missing, Path(temporary) / "attachments", "药甲@X")

    def test_invalid_stem_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "ok.pdf"
            pdf.write_bytes(b"%PDF\n")
            with self.assertRaisesRegex(ValueError, "文件名不合法"):
                attach_pdf.attach(pdf, Path(temporary) / "attachments", "a/b")


if __name__ == "__main__":
    unittest.main()