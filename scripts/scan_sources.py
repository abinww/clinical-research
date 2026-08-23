"""Dependency-free Markdown source scanning shared by skill workflows."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SOURCE_LINK = re.compile(r"^>\s*来源原文\s*:\s*\[\[raw/([^]]+)\]\]", re.MULTILINE)
LEGACY_SOURCE = re.compile(r"^source_raw:\s*[\"']?([^\"'\s]+)", re.MULTILINE)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def source_raw_name(text: str) -> str | None:
    match = SOURCE_LINK.search(text)
    if match:
        return f"raw/{match.group(1)}"
    match = LEGACY_SOURCE.search(text)
    if match:
        return match.group(1)
    return None


def processed_sources(summary_dir: Path) -> set[str]:
    processed = set()
    if not summary_dir.is_dir():
        return processed
    for path in summary_dir.rglob("*.md"):
        try:
            source = source_raw_name(read_text(path))
        except (OSError, UnicodeError):
            continue
        if source:
            processed.add(source)
    return processed


def raw_sources(raw_dir: Path) -> list[tuple[Path, str]]:
    if not raw_dir.is_dir():
        return []
    return [(path, f"raw/{path.name}") for path in sorted(raw_dir.glob("*.md"))]


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描 clinical-research Markdown 来源")
    parser.add_argument("--summary-dir", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--dir", dest="directory", type=Path)
    parser.add_argument("--min-depth", type=int, default=0)
    parser.add_argument("--format", choices=("processed", "raw", "urls", "files"), default="processed")
    args = parser.parse_args()

    if args.format == "files":
        directory = args.directory or args.summary_dir or args.raw_dir
        if directory is None:
            parser.error("--dir、--summary-dir 或 --raw-dir 至少需要一个")
        base = directory.resolve()
        for path in sorted(base.rglob("*.md")):
            if path.is_file() and len(path.relative_to(base).parts) - 1 >= args.min_depth:
                print(path)
        return 0
    if args.format == "processed":
        if args.summary_dir is None:
            parser.error("--summary-dir 是必需的")
        for source in sorted(processed_sources(args.summary_dir)):
            print(source)
        return 0
    if args.raw_dir is None:
        parser.error("--raw-dir 是必需的")
    if args.format == "raw":
        for _, source in raw_sources(args.raw_dir):
            print(source)
        return 0
    for path, _ in raw_sources(args.raw_dir):
        try:
            text = read_text(path)
        except (OSError, UnicodeError):
            continue
        for line in text.splitlines():
            if line.startswith("source:"):
                print(line.split(":", 1)[1].strip().strip("\"'"))
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
