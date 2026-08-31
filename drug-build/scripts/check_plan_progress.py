#!/usr/bin/env python3
"""检查 drug-build plan 表的完成进度（纯数据工具，不参与流程控制）。

对 plan 表每一行的 URL，按完整状态判断：
1. 在指定药品（或诊断模式下全库）的 raw/ 中按 frontmatter source 定位唯一 raw
2. 在该药品 summary/ 中按规范相对 Markdown 链接定位唯一 summary
3. 对应 summary 是否通过完整审核门禁
4. 药品页、全部应建适应症页和根索引是否完整

只输出每个 URL 的状态（plan 表进度），不输出"待处理/失败项"等流程分类——
分类由调用方（drug-build）根据状态自行决定。

用法：
    python check_plan_progress.py --config {绝对config路径} --plan {绝对plan路径} --company-id {公司} --drug-id {药品}

纯标准库实现，无第三方依赖。
"""

import argparse
from pathlib import Path
import re
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SHARED_SCRIPTS = REPOSITORY_ROOT / "scripts"
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from config import load_config  # noqa: E402
from layout import discover_drugs, is_contained, persistent_path  # noqa: E402
from scan_sources import (  # noqa: E402
    _alignment_row,
    _split_table_row,
    frontmatter_value,
    read_frontmatter,
    source_path,
    summary_audit_passed,
    summary_indication_ids,
    summary_indications,
)


MARKDOWN_LINK = re.compile(r"^\[[^\]\r\n]*\]\((?:<([^>\r\n]+)>|([^\s\r\n]+))(?:\s+['\"].*['\"])?\)$")
SOURCE_IDENTITY = re.compile(r"<!--\s*source_identity\s*:\s*(.*?)\s*-->")
GENERIC_INDICATIONS = frozenset({"实体瘤", "多瘤种", "泛瘤种", "晚期实体瘤", "晚期恶性肿瘤"})
MANAGED_MARKERS = {
    "drugs": ("<!-- clinical-research:begin drugs -->", "<!-- clinical-research:end drugs -->"),
    "indications": (
        "<!-- clinical-research:begin indications -->",
        "<!-- clinical-research:end indications -->",
    ),
}


class ProgressIntegrityError(RuntimeError):
    pass


def extract_urls_from_plan(plan_path: str | Path) -> list[str]:
    """Extract URLs by table header, handling escaped pipes and alignment rows."""
    urls = []
    url_column = None
    with Path(plan_path).open("r", encoding="utf-8-sig") as f:
        for line in f:
            cells = _split_table_row(line)
            if cells is None:
                continue
            normalized = [re.sub(r"\s+", "", cell).casefold() for cell in cells]
            if url_column is None:
                url_column = next(
                    (index for index, cell in enumerate(normalized) if cell in {"网址链接", "url", "source", "来源链接"}),
                    None,
                )
                continue
            if _alignment_row(cells) or url_column >= len(cells):
                continue
            url = cells[url_column].replace("\\|", "|").strip()
            match = MARKDOWN_LINK.fullmatch(url)
            if match:
                url = (match.group(1) or match.group(2)).strip()
            elif url.startswith("<") and url.endswith(">"):
                url = url[1:-1].strip()
            if url and url != "—":
                urls.append(url)
    return urls


def find_raws_for_source(
    research_dir: str | Path, source: str, company_id: str | None = None, drug_id: str | None = None
) -> list[Path]:
    """Find every nested drug raw whose semantic source identity is *source*."""
    matches = []
    for drug in discover_drugs(research_dir):
        if company_id is not None and drug.company_id != company_id:
            continue
        if drug_id is not None and drug.drug_id != drug_id:
            continue
        if not drug.raw.is_dir():
            continue
        for path in sorted(drug.raw.glob("*.md")):
            try:
                if not is_contained(path, research_dir):
                    continue
                if frontmatter_value(read_frontmatter(path.read_text(encoding="utf-8-sig")), "source") == source:
                    matches.append(path)
            except (OSError, UnicodeError, ValueError) as exc:
                raise ProgressIntegrityError(f"无法读取 raw 元数据: {path}: {exc}") from exc
    return matches


def find_summaries_for_raw(raw_path: str | Path) -> list[Path]:
    """Find summaries canonically linked to one raw in the same drug tree."""
    raw = Path(raw_path).resolve()
    summary_dir = raw.parent.parent / "summary"
    if not summary_dir.is_dir():
        return []
    matches = []
    for path in sorted(summary_dir.glob("*.md")):
        try:
            if is_contained(path, summary_dir) and path.name == raw.name and source_path(path) == raw:
                matches.append(path)
        except (OSError, UnicodeError, ValueError):
            continue
    return matches


def _contains_source_identity(path: Path, identity: str, research_dir: Path) -> bool:
    if not path.is_file() or not is_contained(path, research_dir):
        return False
    try:
        return SOURCE_IDENTITY.findall(path.read_text(encoding="utf-8-sig")).count(identity) == 1
    except (OSError, UnicodeError):
        return False


def _managed_region(text: str, name: str) -> str | None:
    begin, end = MANAGED_MARKERS[name]
    if text.count(begin) != 1 or text.count(end) != 1:
        return None
    start, finish = text.index(begin) + len(begin), text.index(end)
    return text[start:finish] if start < finish else None


def _contains_managed_wikilink(path: Path, table: str, target: str, alias: str) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return False
    region = _managed_region(text, table)
    if region is None:
        return False
    nonempty = [line for line in region.splitlines() if line.strip()]
    rows = [_split_table_row(line) for line in nonempty]
    if (
        len(rows) < 2
        or any(row is None for row in rows)
        or not _alignment_row(rows[1])
        or any(len(row) != len(rows[0]) for row in rows)
    ):
        return False
    plain = f"[[{target}|{alias}]]"
    escaped = f"[[{target}\\|{alias}]]"
    return sum((plain in line) + (escaped in line) for line in nonempty[2:]) == 1


def _indexed_for_summary(research_dir: Path, summary: Path, summary_text: str) -> bool:
    identity = persistent_path(summary, research_dir)
    drug_dir = summary.parent.parent
    drug_page = drug_dir / f"{drug_dir.name}.md"
    index = research_dir / "index.md"
    if not _contains_source_identity(drug_page, identity, research_dir):
        return False
    drug_target = persistent_path(drug_page, research_dir)
    if not _contains_managed_wikilink(index, "drugs", drug_target, drug_dir.name):
        return False
    try:
        indications = summary_indications(summary_text)
    except ValueError:
        return False
    if not indications:
        return False
    for indication_id, display in indications:
        if display in GENERIC_INDICATIONS:
            continue
        page = research_dir / "indication" / f"{indication_id}.md"
        if not _contains_source_identity(page, identity, research_dir):
            return False
        if not _contains_managed_wikilink(
            index, "indications", f"indication/{indication_id}.md", indication_id
        ):
            return False
    return True


def check_url(
    research_dir: str | Path,
    url: str,
    company_id: str | None = None,
    drug_id: str | None = None,
    require_verification_coverage: bool = True,
) -> str:
    """对单个 URL 执行三级判断，返回状态。"""
    root = Path(research_dir).resolve()
    try:
        raw_paths = find_raws_for_source(root, url, company_id, drug_id)
    except ProgressIntegrityError:
        return "数据完整性错误"
    if not raw_paths:
        return "未提取"
    if len(raw_paths) != 1:
        return "来源对应多个raw"

    raw = raw_paths[0]
    summary_dir = raw.parent.parent / "summary"
    linked_summaries = []
    if summary_dir.is_dir():
        for candidate in sorted(summary_dir.glob("*.md")):
            try:
                linked = source_path(candidate)
                if candidate.name == raw.name and linked is None:
                    return "数据完整性错误"
                if linked == raw:
                    linked_summaries.append(candidate)
            except (OSError, UnicodeError, ValueError):
                return "数据完整性错误"
    if len(linked_summaries) > 1:
        return "一个raw对应多个summary"
    if linked_summaries and linked_summaries[0].name != raw.name:
        return "summary文件名不匹配"
    summaries = find_summaries_for_raw(raw)
    if not summaries:
        return "已提取未生成summary"
    if len(summaries) != 1:
        return "一个raw对应多个summary"

    try:
        summary_content = summaries[0].read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return "已提取未生成summary"

    if summary_audit_passed(summary_content, require_verification_coverage):
        return "已完成" if _indexed_for_summary(root, summaries[0], summary_content) else "已验证未索引"
    return "未审核"


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 drug-build plan 表完成进度")
    parser.add_argument("--config", required=True, help="config.yaml 路径")
    parser.add_argument("--plan", required=True, help="plan 表 markdown 路径")
    parser.add_argument("--company-id")
    parser.add_argument("--drug-id")
    args = parser.parse_args()

    research_dir = load_config(args.config).research_dir
    urls = extract_urls_from_plan(args.plan)
    if not urls:
        print("plan 表没有可检查的 URL")
        return 0

    results = [
        (
            url,
            check_url(
                research_dir,
                url,
                args.company_id,
                args.drug_id,
                True,
            ),
        )
        for url in urls
    ]

    print("plan 表进度：")
    for url, status in results:
        print(f"- {url}: {status}")

    return 2 if any(status == "数据完整性错误" for _, status in results) else 0


if __name__ == "__main__":
    sys.exit(main())
