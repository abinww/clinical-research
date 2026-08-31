#!/usr/bin/env python3
"""检查 drug-build plan 表的完成进度（纯数据工具，不参与流程控制）。

对 plan 表每一行的 URL，按三级判断确定状态：
1. 在 research_dir 的所有药品 raw/ 中按 frontmatter source 全局定位唯一 raw
2. 在该药品 summary/ 中按规范相对 Markdown 链接定位唯一 summary
3. 对应 summary 的 verification 字段是否为 passed

只输出每个 URL 的状态（plan 表进度），不输出"待处理/失败项"等流程分类——
分类由调用方（drug-build）根据状态自行决定。

用法：
    python check_plan_progress.py --config ../config.yaml --plan {plan表路径}

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
from layout import discover_drugs  # noqa: E402
from scan_sources import (  # noqa: E402
    frontmatter_value,
    read_frontmatter,
    source_path,
    summary_audit_passed,
)


MARKDOWN_LINK = re.compile(r"^\[[^\]\r\n]*\]\(([^\r\n]+)\)$")


def extract_urls_from_plan(plan_path: str | Path) -> list[str]:
    """从 plan 表 markdown 表格中提取"网址链接"列（第 7 列）的 URL。"""
    urls = []
    with Path(plan_path).open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 7:
                continue
            if cells[6] in {"网址链接", "---"} or re.fullmatch(r"-+", cells[6]):
                continue
            url = cells[6].strip()
            match = MARKDOWN_LINK.fullmatch(url)
            if match:
                url = match.group(1).strip()
            elif url.startswith("<") and url.endswith(">"):
                url = url[1:-1].strip()
            if url and url != "—":
                urls.append(url)
    return urls


def find_raws_for_source(research_dir: str | Path, source: str) -> list[Path]:
    """Find every nested drug raw whose semantic source identity is *source*."""
    matches = []
    for drug in discover_drugs(research_dir):
        if not drug.raw.is_dir():
            continue
        for path in sorted(drug.raw.glob("*.md")):
            try:
                if frontmatter_value(read_frontmatter(path.read_text(encoding="utf-8-sig")), "source") == source:
                    matches.append(path)
            except (OSError, UnicodeError):
                continue
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
            if source_path(path) == raw:
                matches.append(path)
        except (OSError, UnicodeError, ValueError):
            continue
    return matches


def check_url(research_dir: str | Path, url: str) -> str:
    """对单个 URL 执行三级判断，返回状态。"""
    raw_paths = find_raws_for_source(research_dir, url)
    if not raw_paths:
        return "未提取"
    if len(raw_paths) != 1:
        return "来源对应多个raw"

    summaries = find_summaries_for_raw(raw_paths[0])
    if not summaries:
        return "已提取未生成summary"
    if len(summaries) != 1:
        return "一个raw对应多个summary"

    try:
        summary_content = summaries[0].read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return "已提取未生成summary"

    if summary_audit_passed(summary_content):
        return "已完成"
    return "未审核"


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 drug-build plan 表完成进度")
    parser.add_argument("--config", required=True, help="config.yaml 路径")
    parser.add_argument("--plan", required=True, help="plan 表 markdown 路径")
    args = parser.parse_args()

    research_dir = load_config(args.config).research_dir
    urls = extract_urls_from_plan(args.plan)
    if not urls:
        print("plan 表没有可检查的 URL")
        return 0

    results = [(url, check_url(research_dir, url)) for url in urls]

    print("plan 表进度：")
    for url, status in results:
        print(f"- {url}: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
