#!/usr/bin/env python3
"""检查 drug-build plan 表的完成进度（纯数据工具，不参与流程控制）。

对 plan 表每一行的 URL，按三级判断确定状态：
1. raw_dir 下是否有 frontmatter source: 匹配该 URL
2. 该 raw 是否被 summary_dir 下的 `> 来源原文:` 引用
3. 对应 summary 的 verification 字段是否为 passed

只输出每个 URL 的状态（plan 表进度），不输出"待处理/失败项"等流程分类——
分类由调用方（drug-build）根据状态自行决定。

用法：
    python3 check_plan_progress.py --config ../config.yaml --plan {plan表路径}

纯标准库实现，无第三方依赖。
"""

import argparse
import os
import re
import sys


def parse_config(config_path: str) -> tuple[str, str]:
    """从 config.yaml 解析 raw_dir 与 summary_dir。"""
    raw_dir = None
    summary_dir = None
    with open(config_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line.startswith("raw_dir:"):
                raw_dir = extract_value(line)
            elif line.startswith("summary_dir:"):
                summary_dir = extract_value(line)
    if not raw_dir or not summary_dir:
        raise ValueError("config.yaml 缺少 raw_dir 或 summary_dir")
    return expand_path(raw_dir), expand_path(summary_dir)


def extract_value(line: str) -> str:
    """提取 `键: 值` 行中的值，去掉引号与行内注释。"""
    value = line.split(":", 1)[1].strip()
    value = value.split("#")[0].strip()
    value = value.strip("\"'")
    return value


def expand_path(path: str) -> str:
    """展开 ~ 为用户主目录。"""
    return os.path.expanduser(path)


def read_frontmatter(text: str) -> str:
    """提取 markdown 文件的 YAML frontmatter（--- 之间的内容），无则返回空串。"""
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]


def frontmatter_has_key(frontmatter: str, key: str, expected_value: str = None) -> bool:
    """检查 frontmatter 中是否存在 `key: value` 行。"""
    pattern = re.compile(rf"^{re.escape(key)}\s*:\s*(.*)$", re.MULTILINE)
    match = pattern.search(frontmatter)
    if not match:
        return False
    if expected_value is None:
        return True
    value = match.group(1).strip().strip("\"'")
    return value == expected_value


def extract_urls_from_plan(plan_path: str) -> list[str]:
    """从 plan 表 markdown 表格中提取"网址链接"列（第 7 列）的 URL。"""
    urls = []
    with open(plan_path, "r", encoding="utf-8-sig") as f:
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
            if url and url != "—":
                urls.append(url)
    return urls


def find_raw_for_source(raw_dir: str, source: str) -> str | None:
    """在 raw_dir 下查找 frontmatter source: 匹配的文件路径。"""
    for filename in os.listdir(raw_dir):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(raw_dir, filename)
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        fm = read_frontmatter(content)
        if frontmatter_has_key(fm, "source", source):
            return path
    return None


def find_summary_for_raw(summary_dir: str, raw_filename: str) -> str | None:
    """在 summary_dir 下查找 `> 来源原文: [[raw/{raw_filename}]]` 引用的 summary 路径。"""
    pattern = re.compile(rf">\s*来源原文\s*:\s*\[\[raw/{re.escape(raw_filename)}\]\]")
    for root, _dirs, files in os.walk(summary_dir):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            path = os.path.join(root, filename)
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            if pattern.search(content):
                return path
    return None


def check_url(raw_dir: str, summary_dir: str, url: str) -> str:
    """对单个 URL 执行三级判断，返回状态。"""
    raw_path = find_raw_for_source(raw_dir, url)
    if raw_path is None:
        return "未提取"

    raw_filename = os.path.basename(raw_path)
    summary_path = find_summary_for_raw(summary_dir, raw_filename)
    if summary_path is None:
        return "已提取未生成summary"

    try:
        with open(summary_path, "r", encoding="utf-8-sig") as f:
            summary_content = f.read()
    except (OSError, UnicodeDecodeError):
        return "已提取未生成summary"

    fm = read_frontmatter(summary_content)
    if frontmatter_has_key(fm, "verification", "passed"):
        return "已完成"
    return "未审核"


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 drug-build plan 表完成进度")
    parser.add_argument("--config", required=True, help="config.yaml 路径")
    parser.add_argument("--plan", required=True, help="plan 表 markdown 路径")
    args = parser.parse_args()

    raw_dir, summary_dir = parse_config(args.config)
    urls = extract_urls_from_plan(args.plan)
    if not urls:
        print("plan 表没有可检查的 URL")
        return 0

    results = [(url, check_url(raw_dir, summary_dir, url)) for url in urls]

    print("plan 表进度：")
    for url, status in results:
        print(f"- {url}: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
