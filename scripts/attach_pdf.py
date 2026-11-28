"""Copy a submitted source PDF into the vault as a source-named attachment.

Implements the ``<= 10 MiB`` attachment branch defined by
../schema/raw-spec.md. The caller handles the ``> 10 MiB`` text-extraction branch.
The copy is idempotent: an existing target is never overwritten.
Only the Python standard library is used; the file operations are Windows-safe.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

DEFAULT_MAX_MIB = 10


def attach(pdf: Path, attachments_dir: Path, stem: str, max_mib: int = DEFAULT_MAX_MIB) -> tuple[str, str]:
    """Return ``(status, path)`` where status is ``attached`` or ``too_large``."""
    pdf = pdf.expanduser().resolve()
    if not pdf.is_file():
        raise ValueError(f"PDF 不存在或不可读: {pdf}")
    if not stem or Path(stem).name != stem or stem.endswith((".", " ")):
        raise ValueError(f"附件文件名不合法: {stem}")
    size = pdf.stat().st_size
    threshold = max_mib * 1024 * 1024
    if size > threshold:
        return "too_large", pdf.as_posix()
    target = attachments_dir / f"{stem}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(pdf, target)
    return "attached", target.resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="把提交的来源 PDF 复制为按来源命名的附件")
    parser.add_argument("pdf", type=Path, help="用户提交的 PDF 路径")
    parser.add_argument("attachments_dir", type=Path, help="研究库根目录的 attachments/ 绝对路径")
    parser.add_argument("stem", type=str, help="附件文件名主干，通常为 {drug_id}@{source_label}")
    parser.add_argument("--max-mb", type=int, default=DEFAULT_MAX_MIB, help=f"附件阈值（MiB，默认 {DEFAULT_MAX_MIB}）")
    args = parser.parse_args()
    try:
        status, path = attach(args.pdf, args.attachments_dir, args.stem, args.max_mb)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(f"{status} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())