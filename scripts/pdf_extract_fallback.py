"""Best-effort PDF text fallback using only the Python standard library.

This is intentionally limited. Use a harness PDF reader or pdftotext first.
"""

from __future__ import annotations

import argparse
import re
import sys
import zlib
from pathlib import Path


def extract(path: Path) -> str:
    data = path.read_bytes()
    streams = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        payload = match.group(1)
        try:
            payload = zlib.decompress(payload)
        except zlib.error:
            pass
        streams.append(payload)
    text = b"\n".join(streams).decode("latin-1", errors="ignore")
    values = re.findall(r"\((?:\\.|[^()])*\)", text)
    result = []
    for value in values:
        value = value[1:-1]
        value = re.sub(r"\\([()\\])", r"\1", value)
        if value.strip():
            result.append(value)
    return "\n".join(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="有限能力的标准库 PDF 文本 fallback")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    try:
        text = extract(args.pdf)
    except OSError as exc:
        print(f"[ERROR] 无法读取 PDF: {exc}", file=sys.stderr)
        return 1
    if not text.strip():
        print("[ERROR] 标准库 fallback 未提取到文本；可能是扫描型或复杂编码 PDF", file=sys.stderr)
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
