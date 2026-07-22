#!/usr/bin/env python3
"""药品临床试验查询脚本（当前支持 clinicaltrials.gov）。"""

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Optional

import requests


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


def extract_countries(locations: list[dict]) -> str:
    """Extract stable, de-duplicated country names from CTG locations."""
    countries = []
    for location in locations or []:
        country = str(location.get("country", "")).strip()
        if country and country not in countries:
            countries.append(country)
    return "、".join(countries) if countries else "—"


class ClinicalTrialsGov:
    """clinicaltrials.gov API 查询"""
    
    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    
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
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()
                page_results = self._parse_results(data)
                remaining = None if max_results is None else max_results - len(results)
                results.extend(page_results if remaining is None else page_results[:remaining])

                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                params["pageToken"] = next_token

            return results
        except requests.RequestException as e:
            print(f"[ERROR] clinicaltrials.gov API 请求失败: {e}", file=sys.stderr)
            return []
    
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
        """从干预措施中提取药品名称"""
        # 尝试从 interventions 中提取
        interventions = arms_mod.get("interventions", [])
        if interventions:
            # 查找 DRUG 类型的干预
            drug_names = []
            for interv in interventions:
                if interv.get("type") == "DRUG":
                    name = interv.get("name", "")
                    if name and name not in drug_names and len(drug_names) < 3:
                        drug_names.append(name)
            if drug_names:
                return " + ".join(drug_names)
        
        # 后备：从标题提取
        return title[:50] if title else "—"
    
    def _extract_control_drug(self, arms_mod: dict) -> str:
        """提取对照药物"""
        # CTG API v2 使用 armGroups，兼容旧字段名 arms
        arms = arms_mod.get("armGroups", arms_mod.get("arms", []))
        control_drugs = []
        
        for arm in arms:
            arm_type = arm.get("type", "").lower()
            arm_label = arm.get("label", "").lower()
            
            # 匹配对照组：类型包含 comparator/placebo，或标签包含 placebo
            if "placebo" in arm_label or "comparator" in arm_type or "placebo" in arm_type:
                # arm 对象使用 interventionNames（字符串列表），非 interventions（嵌套对象）
                intervention_names = arm.get("interventionNames", [])
                for name in intervention_names:
                    if name and name not in control_drugs:
                        control_drugs.append(name)
        
        return " + ".join(control_drugs[:3]) if control_drugs else "—"
    
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


def main():
    parser = argparse.ArgumentParser(description="药品临床试验查询")
    parser.add_argument("--drug", "-d", required=True, help="药品名称")
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

    print(f"查询 ClinicalTrials.gov: {args.drug}", file=sys.stderr)
    
    all_trials = []
    
    # 查询 clinicaltrials.gov
    if args.source == "ctg":
        print("查询 clinicaltrials.gov...", file=sys.stderr)
        ctg = ClinicalTrialsGov()
        ctg_trials = ctg.search(
            drug=args.drug,
            indication=args.indication,
            sponsor=args.sponsor,
            max_results=args.max
        )
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
