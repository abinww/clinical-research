"""Semantic Markdown discovery for the clinical-research 2.0 layout."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote_to_bytes

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from config import load_config, restricted_scalar  # noqa: E402
from layout import EXCLUDED_NAMES, discover_drugs, is_contained, persistent_path  # noqa: E402


SOURCE_LINK = re.compile(r"^>\s*来源原文\s*:\s*\[([^\]\r\n]+)\]\((\.\./raw/[^\r\n]+)\)\s*$", re.MULTILINE)
SOURCE_DECLARATION = re.compile(r"^>\s*来源原文\s*:", re.MULTILINE)
FRONTMATTER_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")


@dataclass(frozen=True)
class ScanAnomaly:
    kind: str
    path: Path
    detail: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def source_raw_name(text: str) -> str | None:
    """Extract the canonical 2.0 source target as ``raw/file.md``."""
    matches = SOURCE_LINK.findall(text)
    if len(matches) != 1 or len(SOURCE_DECLARATION.findall(text)) != 1:
        return None
    target = matches[0][1]
    encoded = target[len("../raw/") :]
    if not encoded.lower().endswith(".md") or re.search(r"%(?![0-9A-Fa-f]{2})", encoded):
        return None
    try:
        filename = unquote_to_bytes(encoded).decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
        return None
    return f"raw/{filename}"


def source_link(filename: str, label: str | None = None) -> str:
    """Serialize a canonical summary source declaration."""
    if not filename or Path(filename).name != filename or not filename.lower().endswith(".md"):
        raise ValueError("source filename must be one Markdown path component")
    if label is None:
        label = filename[:-3]
    if not label or any(character in label for character in "]\r\n"):
        raise ValueError("source label is not valid in a one-line Markdown link")
    return f"> 来源原文: [{label}](../raw/{quote(filename, safe='-._~@')})"


def source_path(summary_path: Path) -> Path | None:
    """Resolve a summary's canonical source link without requiring it to exist."""
    source = source_raw_name(read_text(summary_path))
    if source is None:
        return None
    candidate = summary_path.parent.parent / source
    raw_root = summary_path.parent.parent / "raw"
    if not is_contained(candidate, raw_root):
        return None
    return candidate.resolve()


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
    """Return one restricted scalar, rejecting duplicate relevant keys."""
    values = []
    for line_number, line in enumerate(frontmatter.splitlines(), 1):
        match = FRONTMATTER_KEY.match(line)
        if match and match.group(1) == key:
            values.append(restricted_scalar(match.group(2), f"frontmatter {key} line {line_number}"))
    if len(values) > 1:
        raise ValueError(f"duplicate frontmatter key: {key}")
    return values[0] if values else None


def summary_audit_passed(text: str, require_verification_coverage: bool = True) -> bool:
    """Return whether a summary satisfies every final audit-state invariant."""
    frontmatter = read_frontmatter(text)
    try:
        verification = frontmatter_value(frontmatter, "verification")
        fail_count = frontmatter_value(frontmatter, "verification_fail_count")
        coverage = frontmatter_value(frontmatter, "verification_coverage")
    except ValueError:
        return False
    if verification != "passed" or fail_count != "0":
        return False
    fail_count_lines = re.findall(r"^verification_fail_count\s*:\s*(.*?)\s*$", frontmatter, re.MULTILINE)
    if len(fail_count_lines) != 1 or fail_count_lines[0].strip() != "0":
        return False
    if require_verification_coverage and coverage != "complete":
        return False

    visible = _outside_fences(text)
    try:
        expected_order = summary_indication_ids(text)
    except ValueError:
        return False
    section_order = re.findall(r"^##\s+\[([A-Za-z0-9][A-Za-z0-9._-]{0,79})\]\s+.+$", visible, re.MULTILINE)
    if not expected_order or section_order != expected_order:
        return False
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", visible, re.MULTILINE))
    if not headings or headings[-1].group(1) != "数据一致性审核":
        return False
    audit = visible[headings[-1].end() :]
    if re.search(r"^#{1,6}\s+", audit, re.MULTILINE):
        return False
    rows = [_split_table_row(line) for line in audit.splitlines() if line.strip().startswith("|")]
    rows = [row for row in rows if row is not None]
    if len(rows) < 3 or not _alignment_row(rows[1]) or any(not cell for cell in rows[0]):
        return False
    normalized = [re.sub(r"\s+", "", cell).casefold() for cell in rows[0]]
    indication = next(
        (index for index, cell in enumerate(normalized) if cell in {"indication_id", "适应症id"}), None
    )
    status = next((index for index, cell in enumerate(normalized) if cell in {"状态", "status"}), None)
    if indication is None or status is None:
        return False
    data_rows = rows[2:]
    if not data_rows or any(len(row) != len(rows[0]) or not row[indication] for row in data_rows):
        return False
    states = {row[status].upper() for row in data_rows}
    expected_indications = set(expected_order)
    audited_indications = {row[indication] for row in data_rows}
    return (
        bool(states)
        and states <= {"PASS", "WARN", "FAIL"}
        and "FAIL" not in states
        and bool(expected_indications)
        and audited_indications == expected_indications
    )


def summary_identity_valid(text: str, summary_path: str | Path) -> bool:
    """Validate the scalar identity fields that bind a summary to its path."""
    frontmatter = read_frontmatter(text)
    try:
        drug_id = frontmatter_value(frontmatter, "drug_id")
        source_label = frontmatter_value(frontmatter, "source_label")
        archive_company = frontmatter_value(frontmatter, "archive_company")
    except ValueError:
        return False
    path = Path(summary_path)
    if not drug_id or not source_label or not archive_company:
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", source_label):
        return False
    if path.name != f"{drug_id}@{source_label}.md":
        return False
    if path.parent.name != "summary" or path.parent.parent.name != drug_id:
        return False
    if path.parent.parent.parent.name != archive_company:
        return False
    try:
        indications = summary_indications(text)
    except ValueError:
        return False
    return bool(indications)


def summary_indication_ids(text: str) -> list[str]:
    """Return unique indication IDs from the restricted nested frontmatter shape."""
    frontmatter = read_frontmatter(text)
    values = []
    for line_number, line in enumerate(frontmatter.splitlines(), 1):
        match = re.match(r"^\s*-?\s*indication_id\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        value = restricted_scalar(match.group(1), f"frontmatter indication_id line {line_number}")
        if not value or value in values:
            raise ValueError("invalid or duplicate indication_id")
        values.append(value)
    return values


def summary_indications(text: str) -> list[tuple[str, str]]:
    """Return ``(indication_id, display_name)`` pairs from summary frontmatter."""
    frontmatter = read_frontmatter(text)
    pairs: list[tuple[str, str]] = []
    current_id = None
    for line_number, line in enumerate(frontmatter.splitlines(), 1):
        id_match = re.match(r"^\s*-?\s*indication_id\s*:\s*(.*?)\s*$", line)
        if id_match:
            if current_id is not None:
                raise ValueError("indication_id missing indication display name")
            current_id = restricted_scalar(id_match.group(1), f"frontmatter indication_id line {line_number}")
            continue
        name_match = re.match(r"^\s*indication\s*:\s*(.*?)\s*$", line)
        if name_match and current_id is not None:
            display = restricted_scalar(name_match.group(1), f"frontmatter indication line {line_number}")
            if not current_id or not display or any(item[0] == current_id for item in pairs):
                raise ValueError("invalid indication metadata")
            pairs.append((current_id, display))
            current_id = None
    if current_id is not None:
        raise ValueError("indication_id missing indication display name")
    return pairs


def _outside_fences(text: str) -> str:
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match and fence is None:
            fence = match.group(1)[0]
            lines.append("\n")
        elif match and fence == match.group(1)[0]:
            fence = None
            lines.append("\n")
        elif fence is None:
            lines.append(line)
        else:
            lines.append("\n")
    return "".join(lines)


def _split_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    cells, cell, escaped = [], [], False
    for character in stripped[1:-1]:
        if character == "|" and not escaped:
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(character)
        escaped = character == "\\" and not escaped
        if character != "\\":
            escaped = False
    cells.append("".join(cell).strip())
    return cells


def _alignment_row(row: list[str]) -> bool:
    return bool(row) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in row)


def raw_sources(
    raw_dir: Path, research_dir: Path | None = None, anomalies: list[ScanAnomaly] | None = None
) -> list[tuple[Path, str]]:
    """List immediate raw Markdown files and their persistent identities."""
    if not raw_dir.is_dir():
        return []
    root = research_dir.resolve() if research_dir else raw_dir.parent.resolve()
    if not is_contained(raw_dir, root):
        _anomaly(anomalies, "path_escape", raw_dir, "raw directory resolves outside research root")
        return []
    found = []
    for path in sorted(raw_dir.glob("*.md")):
        if not path.is_file():
            continue
        if not is_contained(path, root):
            _anomaly(anomalies, "path_escape", path, "raw file resolves outside research root")
            continue
        found.append((path, persistent_path(path, root)))
    return found


def processed_sources(
    summary_dir: Path, research_dir: Path | None = None, anomalies: list[ScanAnomaly] | None = None
) -> set[str]:
    """Return persistent identities of raw files referenced by summaries."""
    processed: set[str] = set()
    if not summary_dir.is_dir():
        return processed
    root = research_dir.resolve() if research_dir else summary_dir.parent.resolve()
    if not is_contained(summary_dir, root):
        _anomaly(anomalies, "path_escape", summary_dir, "summary directory resolves outside research root")
        return processed
    for summary in sorted(summary_dir.glob("*.md")):
        try:
            if not is_contained(summary, root):
                _anomaly(anomalies, "path_escape", summary, "summary resolves outside research root")
                continue
            source = source_path(summary)
            if source is None:
                _anomaly(anomalies, "invalid_source_link", summary, "missing or malformed canonical source link")
            elif source.name != summary.name:
                _anomaly(anomalies, "mismatched_summary", summary, f"links to {source.name}")
            elif is_contained(source, root):
                processed.add(persistent_path(source, root))
        except (OSError, UnicodeError, ValueError) as exc:
            _anomaly(anomalies, "scan_error", summary, str(exc))
    return processed


def semantic_markdown_files(directory: Path, min_depth: int = 0) -> list[Path]:
    """Find Markdown content while excluding infrastructure and index files."""
    base = directory.resolve()
    if not base.is_dir():
        return []
    files = []
    for path in base.rglob("*.md"):
        if not path.is_file() or not is_contained(path, base):
            continue
        relative = path.relative_to(base)
        if path.name.casefold() == "index.md" or any(
            part.startswith(".") or part.casefold() in EXCLUDED_NAMES for part in relative.parts[:-1]
        ):
            continue
        if len(relative.parts) - 1 >= min_depth:
            files.append(path)
    return sorted(files)


def research_sources(
    research_dir: Path, anomalies: list[ScanAnomaly] | None = None
) -> tuple[list[tuple[Path, str]], dict[str, str]]:
    """Return all raw files and the one-summary-per-source mapping."""
    raw: list[tuple[Path, str]] = []
    processed: dict[str, str] = {}
    linked: dict[str, str] = {}
    rejected: list[Path] = []
    drugs = discover_drugs(research_dir, rejected)
    for path in rejected:
        _anomaly(
            anomalies,
            "invalid_layout",
            path,
            "drug tree is invalid or resolves outside research root",
        )
    for drug in drugs:
        raw.extend(raw_sources(drug.raw, research_dir, anomalies))
        if not drug.summary.is_dir():
            continue
        if not is_contained(drug.summary, research_dir):
            _anomaly(anomalies, "path_escape", drug.summary, "summary directory resolves outside research root")
            continue
        for summary in sorted(drug.summary.glob("*.md")):
            try:
                if not is_contained(summary, research_dir):
                    _anomaly(anomalies, "path_escape", summary, "summary resolves outside research root")
                    continue
                source = source_path(summary)
                if source is None:
                    _anomaly(anomalies, "invalid_source_link", summary, "missing or malformed canonical source link")
                    continue
                if not is_contained(source, drug.raw):
                    _anomaly(anomalies, "path_escape", summary, "source link resolves outside drug raw directory")
                    continue
                source_id = persistent_path(source, research_dir)
                summary_id = persistent_path(summary, research_dir)
                if source_id in linked:
                    _anomaly(anomalies, "duplicate_summary", summary, f"also mapped by {linked[source_id]}")
                else:
                    linked[source_id] = summary_id
                if source.name != summary.name:
                    _anomaly(anomalies, "mismatched_summary", summary, f"links to {source.name}")
                    continue
                if source_id in processed:
                    pass
                else:
                    processed[source_id] = summary_id
            except (OSError, UnicodeError, ValueError) as exc:
                _anomaly(anomalies, "scan_error", summary, str(exc))
    return raw, processed


def _anomaly(anomalies: list[ScanAnomaly] | None, kind: str, path: Path, detail: str) -> None:
    if anomalies is not None:
        anomalies.append(ScanAnomaly(kind, path, detail))


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描 clinical-research 2.0 Markdown 来源")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--research-dir", type=Path)
    parser.add_argument("--summary-dir", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--dir", dest="directory", type=Path)
    parser.add_argument("--min-depth", type=int, default=0)
    parser.add_argument("--format", choices=("processed", "raw", "pending", "urls", "files"), default="processed")
    parser.add_argument("--strict", action="store_true", help="报告扫描异常并返回非零状态")
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
        anomalies: list[ScanAnomaly] = []
        raw, processed = research_sources(root.resolve(), anomalies)
        if args.format == "processed":
            values = processed
        elif args.format == "pending":
            values = (source for _, source in raw if source not in processed)
        elif args.format == "raw":
            values = (source for _, source in raw)
        else:
            values = _source_urls((path for path, _ in raw), anomalies)
        for value in sorted(values):
            print(value)
        return _report_anomalies(anomalies) if args.strict else 0

    anomalies = []
    if args.format == "processed":
        if args.summary_dir is None:
            parser.error("--summary-dir 是必需的")
        values = processed_sources(args.summary_dir, anomalies=anomalies)
    else:
        if args.raw_dir is None:
            parser.error("--raw-dir 是必需的")
        raw = raw_sources(args.raw_dir, anomalies=anomalies)
        if args.strict:
            sibling_summary = args.summary_dir or args.raw_dir.parent / "summary"
            processed_sources(sibling_summary, args.raw_dir.parent, anomalies)
        if args.format == "urls":
            values = _source_urls((path for path, _ in raw), anomalies)
        elif args.format == "pending":
            summary_dir = args.summary_dir or args.raw_dir.parent / "summary"
            processed = processed_sources(summary_dir, args.raw_dir.parent, anomalies)
            values = (source for _, source in raw if source not in processed)
        else:
            values = (source for _, source in raw)
    for value in sorted(values):
        print(value)
    return _report_anomalies(anomalies) if args.strict else 0


def _source_urls(paths, anomalies: list[ScanAnomaly] | None = None) -> list[str]:
    urls = []
    for path in paths:
        try:
            source = frontmatter_value(read_frontmatter(read_text(path)), "source")
            if source is not None:
                urls.append(source)
            else:
                _anomaly(anomalies, "invalid_frontmatter", path, "opening frontmatter has no source scalar")
        except (OSError, UnicodeError, ValueError) as exc:
            _anomaly(anomalies, "invalid_frontmatter", path, str(exc))
    return urls


def _report_anomalies(anomalies: list[ScanAnomaly]) -> int:
    for anomaly in sorted(anomalies, key=lambda item: (item.kind, str(item.path))):
        print(f"[{anomaly.kind}] {anomaly.path}: {anomaly.detail}", file=sys.stderr)
    return 2 if anomalies else 0


if __name__ == "__main__":
    raise SystemExit(main())
