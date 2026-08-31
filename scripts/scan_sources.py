"""Semantic Markdown discovery for the clinical-research 2.0 layout."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from config import load_config  # noqa: E402
from layout import EXCLUDED_NAMES, discover_drugs, persistent_path  # noqa: E402


SOURCE_LINK = re.compile(
    r"^>\s*来源原文\s*:\s*\[[^\]\r\n]+\]\((\.\./raw/[^/\\)\r\n]+\.md)\)\s*$",
    re.MULTILINE,
)
SOURCE_DECLARATION = re.compile(r"^>\s*来源原文\s*:", re.MULTILINE)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def source_raw_name(text: str) -> str | None:
    """Extract the canonical 2.0 source target as ``raw/file.md``."""
    matches = SOURCE_LINK.findall(text)
    if len(matches) != 1 or len(SOURCE_DECLARATION.findall(text)) != 1:
        return None
    filename = unquote(matches[0][len("../raw/") :])
    if "/" in filename or "\\" in filename:
        return None
    return f"raw/{filename}"


def source_path(summary_path: Path) -> Path | None:
    """Resolve a summary's canonical source link without requiring it to exist."""
    source = source_raw_name(read_text(summary_path))
    if source is None or Path(source).name != summary_path.name:
        return None
    return (summary_path.parent.parent / source).resolve()


def read_frontmatter(text: str) -> str:
    """Return only YAML frontmatter delimited at the start of a document."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return ""


def frontmatter_value(frontmatter: str, key: str) -> str | None:
    """Return one simple scalar from an already isolated frontmatter block."""
    match = re.search(rf"^{re.escape(key)}\s*:\s*(.*?)\s*$", frontmatter, re.MULTILINE)
    return match.group(1).strip().strip("\"'") if match else None


def summary_audit_passed(text: str) -> bool:
    """Return whether a summary satisfies every final audit-state invariant."""
    frontmatter = read_frontmatter(text)
    verification = re.findall(r"^verification\s*:\s*(.*?)\s*$", frontmatter, re.MULTILINE)
    if len(verification) != 1 or verification[0].strip().strip("\"'") != "passed":
        return False
    fail_counts = re.findall(r"^verification_fail_count\s*:\s*(.*?)\s*$", frontmatter, re.MULTILINE)
    if len(fail_counts) != 1 or not re.fullmatch(r"0\s*(?:#.*)?", fail_counts[0]):
        return False

    headings = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    if not headings or headings[-1].group(1) != "数据一致性审核":
        return False
    audit = text[headings[-1].end() :]
    for line in audit.splitlines():
        if line.lstrip().startswith("|") and "FAIL" in {cell.strip() for cell in line.strip().strip("|").split("|")}:
            return False
    return True


def raw_sources(raw_dir: Path, research_dir: Path | None = None) -> list[tuple[Path, str]]:
    """List immediate raw Markdown files and their persistent identities."""
    if not raw_dir.is_dir():
        return []
    root = research_dir.resolve() if research_dir else raw_dir.parent.resolve()
    return [(path, persistent_path(path, root)) for path in sorted(raw_dir.glob("*.md")) if path.is_file()]


def processed_sources(summary_dir: Path, research_dir: Path | None = None) -> set[str]:
    """Return persistent identities of raw files referenced by summaries."""
    processed: set[str] = set()
    if not summary_dir.is_dir():
        return processed
    root = research_dir.resolve() if research_dir else summary_dir.parent.resolve()
    for summary in sorted(summary_dir.glob("*.md")):
        try:
            source = source_path(summary)
            if source is not None and source.is_relative_to(root):
                processed.add(persistent_path(source, root))
        except (OSError, UnicodeError, ValueError):
            continue
    return processed


def semantic_markdown_files(directory: Path, min_depth: int = 0) -> list[Path]:
    """Find Markdown content while excluding infrastructure and index files."""
    base = directory.resolve()
    if not base.is_dir():
        return []
    files = []
    for path in base.rglob("*.md"):
        relative = path.relative_to(base)
        if path.name.casefold() == "index.md" or any(part.casefold() in EXCLUDED_NAMES for part in relative.parts[:-1]):
            continue
        if len(relative.parts) - 1 >= min_depth:
            files.append(path)
    return sorted(files)


def research_sources(research_dir: Path) -> tuple[list[tuple[Path, str]], dict[str, str]]:
    """Return all raw files and the one-summary-per-source mapping."""
    raw: list[tuple[Path, str]] = []
    processed: dict[str, str] = {}
    for drug in discover_drugs(research_dir):
        raw.extend(raw_sources(drug.raw, research_dir))
        if not drug.summary.is_dir():
            continue
        for summary in sorted(drug.summary.glob("*.md")):
            try:
                source = source_path(summary)
                if source is None or not source.is_relative_to(drug.raw.resolve()):
                    continue
                source_id = persistent_path(source, research_dir)
                processed.setdefault(source_id, persistent_path(summary, research_dir))
            except (OSError, UnicodeError, ValueError):
                continue
    return raw, processed


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描 clinical-research 2.0 Markdown 来源")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--research-dir", type=Path)
    parser.add_argument("--summary-dir", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--dir", dest="directory", type=Path)
    parser.add_argument("--min-depth", type=int, default=0)
    parser.add_argument("--format", choices=("processed", "raw", "pending", "urls", "files"), default="processed")
    args = parser.parse_args()

    if args.format == "files":
        directory = args.directory or args.summary_dir or args.raw_dir
        if directory is None:
            parser.error("--dir、--summary-dir 或 --raw-dir 至少需要一个")
        for path in semantic_markdown_files(directory, args.min_depth):
            print(path)
        return 0

    root = args.research_dir or (load_config(args.config).research_dir if args.config else None)
    if root is not None:
        raw, processed = research_sources(root)
        if args.format == "processed":
            values = processed
        elif args.format == "pending":
            values = (source for _, source in raw if source not in processed)
        elif args.format == "raw":
            values = (source for _, source in raw)
        else:
            values = _source_urls(path for path, _ in raw)
        for value in sorted(values):
            print(value)
        return 0

    if args.format == "processed":
        if args.summary_dir is None:
            parser.error("--summary-dir 是必需的")
        values = processed_sources(args.summary_dir)
    else:
        if args.raw_dir is None:
            parser.error("--raw-dir 是必需的")
        raw = raw_sources(args.raw_dir)
        values = _source_urls(path for path, _ in raw) if args.format == "urls" else (source for _, source in raw)
    for value in sorted(values):
        print(value)
    return 0


def _source_urls(paths) -> list[str]:
    urls = []
    for path in paths:
        try:
            source = frontmatter_value(read_frontmatter(read_text(path)), "source")
            if source is not None:
                urls.append(source)
        except (OSError, UnicodeError):
            continue
    return urls


if __name__ == "__main__":
    raise SystemExit(main())
