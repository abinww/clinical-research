"""Read-only structural validation for a clinical-research 2.0 drug page."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from layout import is_contained, is_valid_identifier  # noqa: E402
from scan_sources import (  # noqa: E402
    frontmatter_value,
    read_frontmatter,
    summary_audit_passed,
    summary_identity_valid,
    summary_indications,
)


REQUIRED_FIELDS = ("drug_id", "drug", "target", "archive_company", "created", "updated")
REQUIRED_SECTIONS = (
    "基本信息",
    "临床数据汇总",
    "关键里程碑",
    "当前临床管线",
    "药品专利",
)
INDICATION_HEADING = re.compile(
    r"^###\s+\[([A-Za-z0-9][A-Za-z0-9._-]{0,79})\]\s+(.+?)\s*$"
)
H2_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
H3_HEADING = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARKDOWN_LINK = re.compile(r"\[([^\]\r\n]+)\]\(([^)\r\n]+)\)")
SOURCE_LINE = re.compile(r"^\s*>\s*来源\s*:\s*(.*?)\s*$")
EFFICACY_METRIC = re.compile(
    r"(?i)^(?:c?ORR|DCR|BOR|CR|PR|SD|PD|m?PFS|rPFS|m?OS|m?DOR|DOR|"
    r"PSA50|PSA90|CBR|EFS|TTR|TTF)(?:$|[\s(/（，:：])"
)
EFFICACY_METRIC_CN = re.compile(r"客观缓解率|总缓解率|疾病控制率|无进展生存|总生存|缓解持续时间")
NONSTANDARD_DATA_HEADINGS = {"关键数据", "要点", "备注", "待补", "待核"}
ALIGNMENT_CELL = re.compile(r"^:?-{3,}:?$")


def _visible_markdown(text: str) -> str:
    """Blank fenced code blocks so examples don't satisfy or break checks."""
    visible: list[str] = []
    fence_char: str | None = None
    fence_length = 0
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence_char is None:
                fence_char, fence_length = token[0], len(token)
            elif token[0] == fence_char and len(token) >= fence_length:
                fence_char, fence_length = None, 0
            visible.append("")
        elif fence_char is not None:
            visible.append("")
        else:
            visible.append(line)
    return "\n".join(visible)


def _section_body(text: str, title: str) -> tuple[str | None, str | None]:
    """Return a unique H2 section body, or an explanatory error."""
    headings = list(H2_HEADING.finditer(text))
    matches = [heading for heading in headings if heading.group(1).strip() == title]
    if len(matches) != 1:
        return None, f"`## {title}` 应恰好出现一次，实际 {len(matches)} 次"
    heading = matches[0]
    next_heading = next((item for item in headings if item.start() > heading.start()), None)
    end = next_heading.start() if next_heading else len(text)
    return text[heading.end() : end], None


def _indication_groups(section: str) -> tuple[dict[str, str], list[str], list[str]]:
    """Map stable indication IDs to their body text and report malformed H3s."""
    headings = list(H3_HEADING.finditer(section))
    valid_headings = [
        (heading, INDICATION_HEADING.match(heading.group(0)))
        for heading in headings
        if INDICATION_HEADING.match(heading.group(0))
    ]
    groups: dict[str, str] = {}
    errors: list[str] = []
    warnings: list[str] = []
    for heading in headings:
        if not INDICATION_HEADING.match(heading.group(0)):
            title = heading.group(1).strip()
            if title in NONSTANDARD_DATA_HEADINGS:
                warnings.append(f"临床数据区出现非规范小节 `### {title}`")
            else:
                errors.append(f"适应症章节标题格式错误：{heading.group(0).strip()}")
    for index, (heading, match) in enumerate(valid_headings):
        assert match is not None
        next_start = (
            valid_headings[index + 1][0].start()
            if index + 1 < len(valid_headings)
            else len(section)
        )
        indication_id = match.group(1)
        if indication_id in groups:
            errors.append(f"重复的 indication_id：{indication_id}")
            continue
        groups[indication_id] = section[heading.end() : next_start]
    return groups, errors, warnings


def _split_table_row(line: str) -> list[str]:
    content = line.strip().strip("|")
    cells = re.split(r"(?<!\\)\|", content)
    return [cell.replace(r"\|", "|").strip() for cell in cells]


def _is_alignment_row(row: list[str]) -> bool:
    return bool(row) and all(ALIGNMENT_CELL.fullmatch(cell.replace(" ", "")) for cell in row)


def _markdown_tables(text: str) -> list[tuple[int, list[list[str]]]]:
    """Extract pipe tables with a valid Markdown separator row."""
    lines = text.splitlines()
    tables: list[tuple[int, list[list[str]]]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith("|"):
            index += 1
            continue
        start = index
        rows: list[list[str]] = []
        while index < len(lines) and lines[index].strip().startswith("|"):
            rows.append(_split_table_row(lines[index]))
            index += 1
        if len(rows) >= 3 and len(rows[0]) == len(rows[1]) and _is_alignment_row(rows[1]):
            if all(len(row) == len(rows[0]) for row in rows[2:]):
                tables.append((start, rows))
    return tables


def _is_sample_size_label(label: str) -> bool:
    normalized = re.sub(r"\s+", " ", label.strip()).upper()
    return bool(
        normalized == "N"
        or re.match(r"^N\s*(?:/|（|\().+", normalized)
        or normalized in {"样本量", "入组人数"}
    )


def _table_has_efficacy(rows: list[list[str]]) -> bool:
    if not rows or not rows[0] or rows[0][0].strip() not in {"指标", "Metric", "Endpoint"}:
        return False
    return any(
        EFFICACY_METRIC.search(row[0].strip()) or EFFICACY_METRIC_CN.search(row[0])
        for row in rows[2:]
        if row
    )


def _summary_efficacy_tables(summary_text: str) -> dict[str, list[list[list[str]]]]:
    """Return efficacy main tables in each summary indication's 核心数据 section."""
    visible = _visible_markdown(summary_text)
    indication_headings = list(
        re.finditer(
            r"^##\s+\[([A-Za-z0-9][A-Za-z0-9._-]{0,79})\]\s+.+$",
            visible,
            re.MULTILINE,
        )
    )
    result: dict[str, list[list[list[str]]]] = {}
    for heading in indication_headings:
        indication_id = heading.group(1)
        next_h2 = re.search(r"^##\s+", visible[heading.end() :], re.MULTILINE)
        end = heading.end() + next_h2.start() if next_h2 else len(visible)
        indication_body = visible[heading.end() : end]
        core = re.search(r"^###\s+核心数据\s*$", indication_body, re.MULTILINE)
        tables: list[list[list[str]]] = []
        if core:
            next_h3 = re.search(r"^###\s+", indication_body[core.end() :], re.MULTILINE)
            core_end = core.end() + next_h3.start() if next_h3 else len(indication_body)
            tables = [
                rows
                for _, rows in _markdown_tables(indication_body[core.end() : core_end])
                if _table_has_efficacy(rows)
            ]
        result[indication_id] = tables
    return result


def _parse_frontmatter_list(frontmatter: str, key: str) -> list[str]:
    lines = frontmatter.splitlines()
    matches: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = FRONTMATTER_KEY.match(line)
        if match and match.group(1) == key:
            matches.append((index, match.group(2).strip()))
    if len(matches) != 1:
        raise ValueError(f"frontmatter `{key}` 应恰好出现一次")
    index, value = matches[0]
    if value.startswith("["):
        if not value.endswith("]"):
            raise ValueError(f"frontmatter `{key}` 列表格式错误")
        contents = value[1:-1].strip()
        return [item.strip().strip("'\"") for item in contents.split(",") if item.strip()]
    if value:
        raise ValueError(f"frontmatter `{key}` 必须是 YAML 列表")
    items: list[str] = []
    for line in lines[index + 1 :]:
        match = re.match(r"^\s+-\s*(.+?)\s*$", line)
        if not match:
            break
        items.append(match.group(1).strip().strip("'\""))
    return items


def _load_summary(
    path: Path, page_path: Path, report_errors: list[str]
) -> tuple[str, str, list[tuple[str, str]], str] | None:
    try:
        resolved = path.resolve(strict=True)
        text = resolved.read_text(encoding="utf-8-sig")
    except (OSError, RuntimeError) as exc:
        report_errors.append(f"无法读取 summary `{path}`：{exc}")
        return None

    company_dir = page_path.parent.resolve()
    if not is_contained(resolved, company_dir) or resolved.parent.name != "summary":
        report_errors.append(f"summary 必须位于药品页同公司的 `summary/`：{path}")
        return None
    if not summary_identity_valid(text, resolved):
        report_errors.append(f"summary 身份或路径不符合 2.0 规范：{resolved.name}")
        return None
    if not summary_audit_passed(text):
        report_errors.append(f"summary 未通过完整一致性审核门禁：{resolved.name}")
        return None

    try:
        fm = read_frontmatter(text)
        drug_id = frontmatter_value(fm, "drug_id")
        source_label = frontmatter_value(fm, "source_label")
        indications = summary_indications(text)
    except ValueError as exc:
        report_errors.append(f"summary frontmatter 无效 `{resolved.name}`：{exc}")
        return None
    if drug_id != page_path.stem:
        report_errors.append(f"summary drug_id 与药品页文件名不一致：{resolved.name}")
        return None
    return source_label or "", resolved.name, indications, text


def check_drug_page(drug_page: str | Path, summaries: list[str | Path] | None = None) -> dict[str, object]:
    """Validate drug-page structure and its supplied, already-indexed summaries."""
    errors: list[str] = []
    warnings: list[str] = []
    page_path = Path(drug_page).resolve()
    if not page_path.is_file():
        return {"status": "fail", "errors": [f"药品页不存在：{page_path}"], "warnings": []}

    try:
        text = page_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return {"status": "fail", "errors": [f"无法读取药品页：{exc}"], "warnings": []}

    frontmatter = read_frontmatter(text)
    if not frontmatter:
        errors.append("缺少 YAML frontmatter")
    else:
        values: dict[str, str] = {}
        for field in REQUIRED_FIELDS:
            try:
                value = frontmatter_value(frontmatter, field)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if not value:
                errors.append(f"frontmatter 缺少必填字段 `{field}`")
            else:
                values[field] = value
        try:
            company_ids = _parse_frontmatter_list(frontmatter, "company_ids")
        except ValueError as exc:
            errors.append(str(exc))
            company_ids = []
        if not company_ids:
            errors.append("frontmatter `company_ids` 必须是非空列表")
        elif any(not is_valid_identifier(value) for value in company_ids):
            errors.append("frontmatter `company_ids` 含不符合标识符规范的值")
        if len(company_ids) != len(set(company_ids)):
            errors.append("frontmatter `company_ids` 不得重复")
        try:
            companies_value = frontmatter_value(frontmatter, "companies")
            if companies_value is not None:
                companies = _parse_frontmatter_list(frontmatter, "companies")
                if companies != company_ids:
                    errors.append("兼容字段 `companies` 必须与 `company_ids` 完全相同")
        except ValueError as exc:
            errors.append(str(exc))

        drug_id = values.get("drug_id", "")
        if drug_id and (drug_id != page_path.stem or not is_valid_identifier(drug_id)):
            errors.append("frontmatter drug_id 必须与药品页文件名一致且符合标识符规范")
        archive_company = values.get("archive_company", "")
        if archive_company and archive_company != page_path.parent.name:
            errors.append("frontmatter archive_company 必须与药品页直接父目录一致")
        for field in ("created", "updated"):
            value = values.get(field, "")
            if value:
                try:
                    if not DATE_VALUE.fullmatch(value):
                        raise ValueError
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"frontmatter `{field}` 必须是有效的 YYYY-MM-DD 日期")

    visible = _visible_markdown(text)
    h2_titles = [match.group(1).strip() for match in H2_HEADING.finditer(visible)]
    h1_titles = re.findall(r"^#\s+.+?\s*$", visible, re.MULTILINE)
    if len(h1_titles) != 1:
        errors.append(f"药品页必须恰有一个一级标题，实际 {len(h1_titles)} 个")
    for title in REQUIRED_SECTIONS:
        count = h2_titles.count(title)
        if count != 1:
            errors.append(f"`## {title}` 应恰好出现一次，实际 {count} 次")

    pipeline_body, pipeline_error = _section_body(visible, "当前临床管线")
    if pipeline_error:
        errors.append(pipeline_error)
    elif pipeline_body is not None:
        for source in ("clinicaltrials.gov", "chinadrugtrials.org.cn"):
            count = sum(
                1
                for match in H3_HEADING.finditer(pipeline_body)
                if match.group(1).strip() == source
            )
            if count != 1:
                errors.append(f"`## 当前临床管线` 下 `### {source}` 应恰好出现一次，实际 {count} 次")

    clinical_body, section_error = _section_body(visible, "临床数据汇总")
    groups: dict[str, str] = {}
    if section_error:
        errors.append(section_error)
    elif clinical_body is not None:
        groups, group_errors, group_warnings = _indication_groups(clinical_body)
        errors.extend(group_errors)
        warnings.extend(group_warnings)
        if summaries and not groups:
            errors.append("`## 临床数据汇总` 下缺少带 indication_id 的适应症分组")
        for indication_id, body in groups.items():
            for _, rows in _markdown_tables(body):
                if any(not cell for row in rows for cell in row):
                    errors.append(f"[{indication_id}] 表格存在空单元格")
                if not _table_has_efficacy(rows):
                    errors.append(
                        f"[{indication_id}] 含非有效性表格；安全性/亚组表应只通过 summary 链接查看"
                    )
                elif len(rows) < 3 or not _is_sample_size_label(rows[2][0]):
                    errors.append(
                        f"[{indication_id}] 有效性表首行必须是样本量行（如 N 或 N / 可评估 n）"
                    )
        data_headings = {
            match.group(1).strip()
            for pattern in (H2_HEADING, H3_HEADING)
            for match in pattern.finditer(visible)
            if match.group(1).strip() in NONSTANDARD_DATA_HEADINGS
        }
        if data_headings:
            warnings.append(
                "发现独立的非规范小节（"
                + "、".join(sorted(data_headings))
                + "）；人工补充应并入对应规范章节，并确认未用文字要点替代主表"
            )

    if re.search(r"(?i)(?:\]\(|\[\[)[^\]\)]*raw/", visible):
        errors.append("药品页不得包含指向 raw/ 的链接")

    source_lines = list(SOURCE_LINE.finditer(visible))
    if clinical_body is not None:
        clinical_heading = next(
            match
            for match in H2_HEADING.finditer(visible)
            if match.group(1).strip() == "临床数据汇总"
        )
        next_clinical_heading = next(
            (match for match in H2_HEADING.finditer(visible) if match.start() > clinical_heading.start()),
            None,
        )
        clinical_start = clinical_heading.end()
        clinical_end = next_clinical_heading.start() if next_clinical_heading else len(visible)
        for match in source_lines:
            if not (clinical_start <= match.start() < clinical_end):
                errors.append("summary 来源链接必须位于 `## 临床数据汇总` 的适应症组内")

    linked_summaries: dict[Path, Path] = {}
    for link in MARKDOWN_LINK.finditer(visible):
        target = link.group(2)
        if "summary/" not in target:
            continue
        line_start = visible.rfind("\n", 0, link.start()) + 1
        line_end = visible.find("\n", link.end())
        if line_end < 0:
            line_end = len(visible)
        line = visible[line_start:line_end]
        if not SOURCE_LINE.match(line):
            errors.append("summary 链接只能写在 `> 来源:` 行")
        if not re.fullmatch(r"summary/[^/\\]+\.md", target):
            errors.append(f"summary 链接必须是同级 `summary/{{file}}.md` 相对路径：{target}")
        elif not (page_path.parent / target).is_file():
            errors.append(f"summary 链接目标不存在：{target}")
        else:
            candidate = page_path.parent / target
            linked_summaries[candidate.resolve()] = candidate
    if re.search(r"\[\[[^\]]*summary/", visible, re.IGNORECASE):
        errors.append("药品页 summary 来源必须使用 Markdown 相对链接，不得使用 wikilink")

    summary_candidates = dict(linked_summaries)
    for summary_arg in summaries or []:
        summary_path = Path(summary_arg)
        try:
            summary_candidates[summary_path.resolve()] = summary_path
        except OSError:
            summary_candidates[summary_path] = summary_path

    for summary_path in summary_candidates.values():
        loaded = _load_summary(summary_path, page_path, errors)
        if loaded is None:
            continue
        source_label, filename, indications, summary_text = loaded
        relative_link = f"summary/{filename}"
        efficacy_tables = _summary_efficacy_tables(summary_text)
        expected_ids = [indication_id for indication_id, _ in indications]
        for indication_id in expected_ids:
            body = groups.get(indication_id)
            if body is None:
                errors.append(f"{filename} 覆盖的适应症组缺失：[{indication_id}]")
                continue
            group_links = [
                match.group(2)
                for line in body.splitlines()
                if SOURCE_LINE.match(line)
                for match in MARKDOWN_LINK.finditer(line)
            ]
            if group_links.count(relative_link) != 1:
                errors.append(
                    f"[{indication_id}] 中 `{relative_link}` 来源链接应恰好出现一次，"
                    f"实际 {group_links.count(relative_link)} 次"
                )
            source_tables = efficacy_tables.get(indication_id, [])
            for rows in source_tables:
                if len(rows) < 3 or not _is_sample_size_label(rows[2][0]):
                    errors.append(
                        f"{filename} [{indication_id}] 有效性主表首行必须是样本量行"
                    )
            if source_tables:
                destination_tables = [
                    (start, rows)
                    for start, rows in _markdown_tables(body)
                    if _table_has_efficacy(rows)
                ]
                if not destination_tables:
                    errors.append(
                        f"[{indication_id}] 缺少 {filename} 中的有效性主表；不得以要点文字替代"
                    )
                elif not any(
                    source_label in line
                    for start, _ in destination_tables
                    for line in body.splitlines()[:start]
                    if line.strip().startswith(">")
                ):
                    errors.append(
                        f"[{indication_id}] 有效性主表上方缺少 source_label：{source_label}"
                    )

        page_link_count = sum(
            1
            for match in MARKDOWN_LINK.finditer(visible)
            if match.group(2) == relative_link
        )
        if page_link_count != len(expected_ids):
            errors.append(
                f"`{relative_link}` 应在每个适应症组各出现一次（共 {len(expected_ids)} 次），"
                f"全页实际 {page_link_count} 次"
            )

    status = "fail" if errors else "warn" if warnings else "pass"
    return {"status": status, "errors": errors, "warnings": warnings}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drug-page", required=True, help="药品页路径")
    parser.add_argument(
        "--summary",
        action="append",
        default=[],
        help="本轮已通过 indexer 资格门禁的 summary 路径，可重复传入",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = check_drug_page(args.drug_page, args.summary)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["status"].upper())
        for error in result["errors"]:
            print(f"FAIL: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
