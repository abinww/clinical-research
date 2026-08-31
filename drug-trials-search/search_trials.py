#!/usr/bin/env python3
"""药品临床试验查询脚本（当前支持 clinicaltrials.gov）。"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional


def display_value(value: object) -> str:
    """Normalize missing API values for persisted Markdown tables."""
    if value is None:
        return "—"
    text = str(value).strip()
    return "—" if text in {"", "N/A", "-"} else text


class TrialResult:
    """临床试验结果数据结构"""
    
    def __init__(self):
        self.trial_id: str = "—"
        self.drug_name: str = "—"
        self.indication: str = "—"
        self.countries: str = "—"
        self.sponsor: str = "—"
        self.last_update: str = "—"
        self.status: str = "—"
        self.phase: str = "—"
        self.enrollment: str = "—"
        self.start_date: str = "—"
        self.completion_date: str = "—"
        self.control_drug: str = "—"
        self.primary_outcome: str = "—"
        self.secondary_outcome: str = "—"
        self.url: str = "—"
        self.source: str = "—"
        self.query_aliases: list[str] = []
    
    def to_dict(self) -> dict:
        return {
            "临床ID": self.trial_id,
            "药品名称": self.drug_name,
            "开展国家": self.countries,
            "适应症": self.indication,
            "Sponsor": self.sponsor,
            "最近更新": self.last_update,
            "当前状态": self.status,
            "临床阶段": self.phase,
            "计划入组": self.enrollment,
            "开始日期": self.start_date,
            "完成日期": self.completion_date,
            "对照药物": self.control_drug,
            "Primary Outcome": self.primary_outcome,
            "Secondary Outcome": self.secondary_outcome,
            "链接": self.url,
            "来源": self.source
        }


COMMON_COUNTRY_CODES = {
    "United States": "US",
    "China": "CN",
    "Japan": "JP",
    "United Kingdom": "UK",
    "United Kingdom of Great Britain and Northern Ireland": "UK",
    "Australia": "AU",
    "South Korea": "KR",
    "France": "FR",
    "Germany": "DE",
    "Italy": "IT",
    "India": "IN",
    "Hong Kong": "HK",
}

EUROPEAN_COUNTRIES = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
    "Malta", "Moldova", "Netherlands", "Norway", "Poland", "Portugal",
    "Romania", "Serbia", "Slovakia", "Slovenia", "Spain", "Sweden",
    "Switzerland", "Turkey", "Turkey (Türkiye)", "Ukraine", "Georgia",
}

CORE_COUNTRY_ORDER = ("US", "CN", "JP", "UK", "AU")


class ClinicalTrialsGovError(RuntimeError):
    """Raised when ClinicalTrials.gov cannot provide a valid response."""


def extract_countries(locations: list[dict]) -> str:
    """Condense CTG country lists for compact table display.

    Rules:
    - De-duplicate raw country names first.
    - When the raw country count is <= 5: list all countries; common
      countries use two-letter codes (US/CN/JP/UK/AU/KR/FR/DE/...), others
      keep their full names, in original order.
    - When the raw country count is > 5: US/CN/JP/UK/AU use two-letter codes
      in fixed order, remaining European countries merge into "EU", other
      countries merge into "ETC", and "(total N)" is appended.
    - No countries -> "—".
    """
    raw_countries = []
    for location in locations or []:
        country = str(location.get("country", "")).strip()
        if country and country not in raw_countries:
            raw_countries.append(country)
    if not raw_countries:
        return "—"

    if len(raw_countries) <= 5:
        return "、".join(COMMON_COUNTRY_CODES.get(c, c) for c in raw_countries)

    parts = []
    for code in CORE_COUNTRY_ORDER:
        if any(COMMON_COUNTRY_CODES.get(c) == code for c in raw_countries):
            parts.append(code)

    european_rest = [
        c for c in raw_countries
        if COMMON_COUNTRY_CODES.get(c) not in CORE_COUNTRY_ORDER
        and c in EUROPEAN_COUNTRIES
    ]
    other_rest = [
        c for c in raw_countries
        if COMMON_COUNTRY_CODES.get(c) not in CORE_COUNTRY_ORDER
        and c not in EUROPEAN_COUNTRIES
    ]
    if european_rest:
        parts.append("EU")
    if other_rest:
        parts.append("ETC")

    return "、".join(parts) + f"(total {len(raw_countries)})"


class ClinicalTrialsGov:
    """clinicaltrials.gov API 查询"""
    
    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    @staticmethod
    def _open(request: urllib.request.Request, timeout: int):
        return urllib.request.urlopen(request, timeout=timeout)
    
    def search(self, drug: str, indication: Optional[str] = None,
               sponsor: Optional[str] = None,
               max_results: Optional[int] = None) -> list[TrialResult]:
        """
        搜索临床试验
        
        Args:
            drug: 药品名称
            indication: 适应症（可选）
            sponsor: 申办方（可选）
            max_results: 最大返回结果数；为 None 时返回 API 分页中的全部结果
        """
        if max_results is not None and max_results < 1:
            raise ValueError("max_results 必须为正整数")

        # 构建查询词
        query_parts = [drug]
        if indication:
            query_parts.append(indication)
        if sponsor:
            query_parts.append(f"AREA[LeadSponsorName]{sponsor}")
        
        query_term = " AND ".join(query_parts)
        
        # API 参数
        params = {
            "query.term": query_term,
            "pageSize": min(max_results, 100) if max_results is not None else 100,
            "format": "json"
        }

        results = []
        try:
            while max_results is None or len(results) < max_results:
                query = urllib.parse.urlencode(params)
                request = urllib.request.Request(
                    f"{self.BASE_URL}?{query}", headers=self.headers
                )
                with self._open(request, self.timeout) as response:
                    if response.status < 200 or response.status >= 300:
                        raise urllib.error.HTTPError(
                            request.full_url, response.status, response.reason,
                            response.headers, None
                        )
                    data = json.loads(response.read().decode("utf-8"))
                page_results = self._parse_results(data)
                remaining = None if max_results is None else max_results - len(results)
                results.extend(page_results if remaining is None else page_results[:remaining])

                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                params["pageToken"] = next_token

            return results
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError) as e:
            raise ClinicalTrialsGovError(
                f"clinicaltrials.gov API 请求失败: {e}"
            ) from e
    
    def _parse_results(self, data: dict) -> list[TrialResult]:
        """解析 API 返回结果"""
        results = []
        
        studies = data.get("studies", [])
        
        for study in studies:
            trial = TrialResult()
            trial.source = "CTG"
            
            # 基本信息
            protocol = study.get("protocolSection", {})
            
            # ID
            ident = protocol.get("identificationModule", {})
            trial.trial_id = display_value(ident.get("nctId"))
            
            # 标题（提取药品名称）
            title = ident.get("briefTitle", "")
            trial.drug_name = self._extract_drug_from_title(title)
            
            # 状态
            status_mod = protocol.get("statusModule", {})
            trial.status = display_value(status_mod.get("overallStatus"))
            trial.last_update = display_value(status_mod.get("statusVerifiedDate"))
            
            # 日期
            start_struct = status_mod.get("startDateStruct", {})
            trial.start_date = display_value(start_struct.get("date"))
            
            completion_struct = status_mod.get("completionDateStruct", {})
            trial.completion_date = display_value(completion_struct.get("date"))
            
            # Sponsor
            sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
            lead_sponsor = sponsor_mod.get("leadSponsor", {})
            trial.sponsor = display_value(lead_sponsor.get("name"))
            
            # 设计（阶段、入组人数）
            design_mod = protocol.get("designModule", {})
            
            # 阶段
            phases = design_mod.get("phases", [])
            trial.phase = ", ".join(phases) if phases else "—"
            
            # 入组人数
            enrollment_info = design_mod.get("enrollmentInfo", {})
            trial.enrollment = display_value(enrollment_info.get("count"))
            
            # 适应症（从 conditionsModule）
            conditions_mod = protocol.get("conditionsModule", {})
            conditions = conditions_mod.get("conditions", [])
            trial.indication = ", ".join(conditions[:3]) if conditions else "—"

            locations_mod = protocol.get("contactsLocationsModule", {})
            trial.countries = extract_countries(locations_mod.get("locations", []))
            
            # Arms/Interventions（药品名称、对照药物）
            arms_mod = protocol.get("armsInterventionsModule", {})            
            # 从干预措施中提取药品名称
            trial.drug_name = self._extract_drug_from_interventions(arms_mod, ident.get("briefTitle", ""))
            
            # 对照药物
            trial.control_drug = self._extract_control_drug(arms_mod)
            
            # Outcomes
            outcomes_mod = protocol.get("outcomesModule", {})
            trial.primary_outcome = self._extract_primary_outcome(outcomes_mod)
            trial.secondary_outcome = self._extract_secondary_outcome(outcomes_mod)
            
            # URL
            trial.url = f"https://clinicaltrials.gov/study/{trial.trial_id}"
            
            results.append(trial)
        
        return results
    
    def _extract_drug_from_title(self, title: str) -> str:
        """从标题中提取药品名称（简化版）"""
        # 这是一个简化实现，实际可能需要更复杂的逻辑
        # 优先返回标题前50个字符
        return title[:50] if title else "—"
    
    def _extract_drug_from_interventions(self, arms_mod: dict, title: str) -> str:
        """从 armGroups 中提取试验药物（EXPERIMENTAL arm）。

        规则：
        - 取所有不同的 type == EXPERIMENTAL 的 arm，并用 "; " 保留 arm 边界
        - 优先使用 arm label（保留完整联用信息，如 "HS-20093 and adebrelimab"），
          把 " and " 清洗为 " + "
        - label 不可用时用 interventionNames（剥 "Drug: "/"Biological: " 前缀）
        - 无 EXPERIMENTAL arm 时，回退到 interventions 中非对照类型的干预名
        """
        arms = arms_mod.get("armGroups", arms_mod.get("arms", []))
        experimental_arms = [a for a in arms if str(a.get("type", "")).upper() == "EXPERIMENTAL"]
        if experimental_arms:
            regimens = []
            for arm in experimental_arms:
                label = str(arm.get("label", "")).strip()
                if label:
                    regimen = " + ".join(
                        p.strip() for p in label.split(" and ") if p.strip()
                    )
                else:
                    names = self._strip_intervention_prefixes(arm.get("interventionNames", []))
                    regimen = " + ".join(names)
                if regimen and regimen not in regimens:
                    regimens.append(regimen)
            if regimens:
                return "; ".join(regimens)
            return title[:50] if title else "—"

        # 回退：interventions 中排除对照 arm 使用的干预
        control_names = set()
        for arm in arms:
            if str(arm.get("type", "")).upper() in {"ACTIVE_COMPARATOR", "PLACEBO_COMPARATOR"}:
                control_names.update(self._strip_intervention_prefixes(arm.get("interventionNames", [])))
                label = str(arm.get("label", "")).strip()
                if label:
                    control_names.update(p.strip() for p in label.split(" and ") if p.strip())
        interventions = arms_mod.get("interventions", [])
        drug_names = []
        for interv in interventions:
            name = str(interv.get("name", "")).strip()
            if name in control_names:
                continue
            if name and name not in drug_names and len(drug_names) < 3:
                drug_names.append(name)
        if drug_names:
            return " + ".join(drug_names)

        return title[:50] if title else "—"

    def _extract_control_drug(self, arms_mod: dict) -> str:
        """提取对照药物（ACTIVE_COMPARATOR / PLACEBO_COMPARATOR arm）。"""
        arms = arms_mod.get("armGroups", arms_mod.get("arms", []))
        control_drugs = []

        for arm in arms:
            arm_type = str(arm.get("type", "")).upper()
            if arm_type not in {"ACTIVE_COMPARATOR", "PLACEBO_COMPARATOR"}:
                continue
            label = str(arm.get("label", "")).strip()
            names = self._strip_intervention_prefixes(arm.get("interventionNames", []))
            # label 优先（保留完整对照方案），其次 interventionNames
            if label:
                for part in label.split(" and "):
                    part = part.strip()
                    if part and part not in control_drugs:
                        control_drugs.append(part)
            else:
                for name in names:
                    if name and name not in control_drugs:
                        control_drugs.append(name)

        return " + ".join(control_drugs[:3]) if control_drugs else "—"

    @staticmethod
    def _strip_intervention_prefixes(names: list) -> list:
        """剥离 interventionNames 的类型前缀（"Drug: X" -> "X"）。"""
        cleaned = []
        for name in names or []:
            text = str(name).strip()
            if text.lower().startswith(("drug:", "biological:", "device:", "procedure:")):
                text = text.split(":", 1)[1].strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned
    
    def _extract_primary_outcome(self, outcomes_mod: dict) -> str:
        """提取主要终点"""
        primary = outcomes_mod.get("primaryOutcomes", [])
        if primary:
            measures = [o.get("measure", "")[:100] for o in primary[:2]]
            return "; ".join(m for m in measures if m) or "—"
        return "—"
    
    def _extract_secondary_outcome(self, outcomes_mod: dict) -> str:
        """提取次要终点"""
        secondary = outcomes_mod.get("secondaryOutcomes", [])
        if secondary:
            measures = [o.get("measure", "")[:100] for o in secondary[:2]]
            return "; ".join(m for m in measures if m) or "—"
        return "—"


def generate_markdown_table(trials: list[TrialResult]) -> str:
    """Generate a clinicaltrials.gov table matching schema/drug-spec.md."""
    if not trials:
        return "未找到符合条件的临床试验。\n"
    
    headers = ["试验ID", "药品", "开展国家", "适应症", "阶段", "状态", "入组",
               "开始", "预计完成", "对照", "Sponsor", "主要终点", "次要终点", "更新"]
    
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    
    for trial in trials:
        d = trial.to_dict()
        trial_id = display_value(d["临床ID"])
        url = display_value(d["链接"])
        linked_trial_id = f"[{trial_id}]({url})" if url != "—" else trial_id
        row = [
            linked_trial_id,
            display_value(d["药品名称"]),
            display_value(d["开展国家"]),
            display_value(d["适应症"]),
            normalize_phase(d["临床阶段"]),
            display_value(d["当前状态"]),
            display_value(d["计划入组"]),
            display_value(d["开始日期"]),
            display_value(d["完成日期"]),
            display_value(d["对照药物"]),
            display_value(d["Sponsor"]),
            display_value(d["Primary Outcome"]),
            display_value(d["Secondary Outcome"]),
            display_value(d["最近更新"]),
        ]
        # 转义表格中的特殊字符
        row = [cell.replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(row) + " |")
    
    return "\n".join(lines)


def generate_pipeline_markdown(trials: list[TrialResult]) -> str:
    """Generate the currently supported CTG pipeline subsection."""
    updated = datetime.now().strftime("%Y-%m-%d")
    return (
        "### clinicaltrials.gov\n\n"
        f"> 更新时间: {updated}\n\n"
        f"{generate_markdown_table(trials)}"
    )


def normalize_phase(phase: str) -> str:
    """Format CTG phase values for the drug pipeline schema."""
    values = [value.strip() for value in str(phase or "").split(",") if value.strip()]
    phase_map = {
        "PHASE1": "Phase I",
        "PHASE2": "Phase II",
        "PHASE3": "Phase III",
        "PHASE4": "Phase IV",
    }
    formatted = [phase_map.get(value.upper(), display_value(value)) for value in values]
    return ", ".join(formatted) if formatted else "—"


def search_aliases(client: ClinicalTrialsGov, aliases: list[str],
                   indication: Optional[str] = None,
                   sponsor: Optional[str] = None,
                   max_results: Optional[int] = None) -> list[TrialResult]:
    """Query each distinct alias and deterministically union results by NCT ID."""
    unique_aliases = list(dict.fromkeys(alias.strip() for alias in aliases if alias.strip()))
    by_id = {}
    for alias in unique_aliases:
        for trial in client.search(
            drug=alias,
            indication=indication,
            sponsor=sponsor,
            max_results=max_results,
        ):
            trial_id = trial.trial_id
            if trial_id not in by_id:
                trial.query_aliases = [alias]
                by_id[trial_id] = trial
            elif alias not in by_id[trial_id].query_aliases:
                by_id[trial_id].query_aliases.append(alias)
    merged = [by_id[trial_id] for trial_id in sorted(by_id)]
    return merged[:max_results] if max_results is not None else merged


def main():
    parser = argparse.ArgumentParser(description="药品临床试验查询")
    parser.add_argument("--drug", "-d", required=True, action="append",
                        help="药品名称或别名（可重复指定）")
    parser.add_argument("--indication", "-i", help="适应症")
    parser.add_argument("--sponsor", "-s", help="申办方")
    parser.add_argument("--max", "-m", type=int, help="最大结果数（默认返回全部分页结果）")
    parser.add_argument("--output", "-o", help="输出文件路径（可选）")
    parser.add_argument("--source", choices=["ctg", "cdt"], default="ctg",
                        help="数据源: ctg(clinicaltrials.gov), cdt(预留接口，当前未实现)")
    parser.add_argument("--format", choices=["pipeline-markdown", "json"],
                        default="pipeline-markdown", help="输出格式")
    
    args = parser.parse_args()
    
    if args.max is not None and args.max < 1:
        parser.error("--max 必须为正整数")
    if args.source == "cdt":
        parser.error("--source cdt 是预留接口，当前尚未实现")

    aliases = list(dict.fromkeys(alias.strip() for alias in args.drug if alias.strip()))
    if not aliases:
        parser.error("--drug 不能为空")
    print(f"查询 ClinicalTrials.gov: {', '.join(aliases)}", file=sys.stderr)
    
    all_trials = []
    
    # 查询 clinicaltrials.gov
    if args.source == "ctg":
        print("查询 clinicaltrials.gov...", file=sys.stderr)
        ctg = ClinicalTrialsGov()
        try:
            ctg_trials = search_aliases(
                ctg,
                aliases=aliases,
                indication=args.indication,
                sponsor=args.sponsor,
                max_results=args.max,
            )
        except ClinicalTrialsGovError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 1
        print(f"找到 {len(ctg_trials)} 条记录", file=sys.stderr)
        all_trials.extend(ctg_trials)
    
    if args.format == "json":
        print(json.dumps([trial.to_dict() for trial in all_trials], ensure_ascii=False, indent=2))
        return 0

    # 生成与 drug-spec.md 一致的管线表格
    all_trials.sort(key=lambda trial: phase_sort_key(trial.phase, trial.start_date))
    table_md = generate_pipeline_markdown(all_trials)
    
    print(table_md)
    
    # 保存到文件
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(table_md)
        print(f"结果已保存到: {args.output}", file=sys.stderr)
    
    return 0


def phase_sort_key(phase: str, start_date: str = "") -> tuple[int, int, int]:
    """Sort Phase III before Phase II/I and newer start dates first."""
    normalized = normalize_phase(phase).lower().split(", ")
    ranks = {"phase iii": 0, "phase ii": 1, "phase i": 2, "phase iv": 3}
    rank = min((ranks.get(value, 4) for value in normalized), default=4)
    year, month = normalize_date_for_sort(start_date)
    return rank, -year, -month


def normalize_date_for_sort(value: str) -> tuple[int, int]:
    """Return year and month for descending date sorting."""
    parts = str(value or "").split("-")
    if len(parts) >= 2 and all(part.isdigit() for part in parts[:2]):
        return int(parts[0]), int(parts[1])
    return 0, 0


if __name__ == "__main__":
    sys.exit(main())
