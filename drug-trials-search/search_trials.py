#!/usr/bin/env python3
"""药品临床试验查询脚本（当前支持 clinicaltrials.gov）。"""

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import requests
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# DrissionPage for anti-bot bypass (Chinese websites)
try:
    from DrissionPage import ChromiumPage
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False


class TrialResult:
    """临床试验结果数据结构"""
    
    def __init__(self):
        self.trial_id: str = "N/A"
        self.drug_name: str = "N/A"
        self.indication: str = "N/A"
        self.countries: str = "—"
        self.sponsor: str = "N/A"
        self.last_update: str = "N/A"
        self.status: str = "N/A"
        self.phase: str = "N/A"
        self.enrollment: str = "N/A"
        self.start_date: str = "N/A"
        self.completion_date: str = "N/A"
        self.control_drug: str = "N/A"
        self.primary_outcome: str = "N/A"
        self.secondary_outcome: str = "N/A"
        self.url: str = "N/A"
        self.source: str = "N/A"
    
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
               sponsor: Optional[str] = None, max_results: int = 100) -> list[TrialResult]:
        """
        搜索临床试验
        
        Args:
            drug: 药品名称
            indication: 适应症（可选）
            sponsor: 申办方（可选）
            max_results: 最大返回结果数
        """
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
            "pageSize": min(max_results, 100),  # API 限制每页最多100条
            "format": "json"
        }
        
        try:
            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            return self._parse_results(data)
            
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
            trial.trial_id = ident.get("nctId", "N/A")
            
            # 标题（提取药品名称）
            title = ident.get("briefTitle", "")
            trial.drug_name = self._extract_drug_from_title(title)
            
            # 状态
            status_mod = protocol.get("statusModule", {})
            trial.status = status_mod.get("overallStatus", "N/A")
            trial.last_update = status_mod.get("statusVerifiedDate", "N/A")
            
            # 日期
            start_struct = status_mod.get("startDateStruct", {})
            trial.start_date = start_struct.get("date", "N/A")
            
            completion_struct = status_mod.get("completionDateStruct", {})
            trial.completion_date = completion_struct.get("date", "N/A")
            
            # Sponsor
            sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
            lead_sponsor = sponsor_mod.get("leadSponsor", {})
            trial.sponsor = lead_sponsor.get("name", "N/A")
            
            # 设计（阶段、入组人数）
            design_mod = protocol.get("designModule", {})
            
            # 阶段
            phases = design_mod.get("phases", [])
            trial.phase = ", ".join(phases) if phases else "N/A"
            
            # 入组人数
            enrollment_info = design_mod.get("enrollmentInfo", {})
            trial.enrollment = str(enrollment_info.get("count", "N/A"))
            
            # 适应症（从 conditionsModule）
            conditions_mod = protocol.get("conditionsModule", {})
            conditions = conditions_mod.get("conditions", [])
            trial.indication = ", ".join(conditions[:3]) if conditions else "N/A"

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
        return title[:50] if title else "N/A"
    
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
        return title[:50] if title else "N/A"
    
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
        
        return ", ".join(control_drugs[:3]) if control_drugs else "N/A"
    
    def _extract_primary_outcome(self, outcomes_mod: dict) -> str:
        """提取主要终点"""
        primary = outcomes_mod.get("primaryOutcomes", [])
        if primary:
            measures = [o.get("measure", "")[:100] for o in primary[:2]]
            return "; ".join(m for m in measures if m) or "N/A"
        return "N/A"
    
    def _extract_secondary_outcome(self, outcomes_mod: dict) -> str:
        """提取次要终点"""
        secondary = outcomes_mod.get("secondaryOutcomes", [])
        if secondary:
            measures = [o.get("measure", "")[:100] for o in secondary[:2]]
            return "; ".join(m for m in measures if m) or "N/A"
        return "N/A"


class ChinaDrugTrials:
    """chinadrugtrials.org.cn 查询（Web Scraping + DrissionPage 反爬绕过）"""
    
    SEARCH_URL = "https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml"
    HOME_URL = "https://www.chinadrugtrials.org.cn/"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def search(self, drug: str, indication: Optional[str] = None,
               sponsor: Optional[str] = None, max_results: int = 100) -> list[TrialResult]:
        """
        搜索中国药物临床试验
        
        使用 DrissionPage 绕过瑞数反爬机制
        """
        results = []
        
        if not DRISSION_AVAILABLE:
            print("[WARN] DrissionPage 未安装，无法查询 chinadrugtrials.org.cn", file=sys.stderr)
            print("[INFO] 请运行: pip3 install DrissionPage", file=sys.stderr)
            return results
        
        try:
            print("      启动浏览器（绕过反爬）...", file=sys.stderr)
            
            # 配置浏览器选项
            from DrissionPage import ChromiumOptions
            co = ChromiumOptions()
            co.headless(True)
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--headless=new')
            
            # 使用 DrissionPage 启动浏览器
            page = ChromiumPage(addr_or_opts=co)
            
            try:
                # 访问首页（触发瑞数挑战）
                page.get(self.HOME_URL)
                
                # 等待瑞数 JS 执行完成
                import time
                time.sleep(3)
                
                # 构建搜索 URL
                search_url = f"{self.SEARCH_URL}?keywords={quote(drug)}"
                if indication:
                    search_url += f" {quote(indication)}"
                
                # 访问搜索页
                page.get(search_url)
                
                # 等待结果加载
                time.sleep(3)
                
                # 解析结果
                results = self._parse_drission_results(page, drug, max_results)
                
            finally:
                page.quit()
                
        except Exception as e:
            print(f"[WARN] chinadrugtrials.org.cn 查询失败: {e}", file=sys.stderr)
            print("[INFO] 请手动访问: https://www.chinadrugtrials.org.cn/", file=sys.stderr)
        
        return results
    
    def _parse_drission_results(self, page, drug: str, max_results: int) -> list[TrialResult]:
        """使用 DrissionPage 解析搜索结果"""
        results = []
        
        try:
            # 获取表格行
            rows = page.eles('css:table tbody tr, css:.search-result tr, css:.list-table tr')
            
            for row in rows[:max_results]:
                trial = TrialResult()
                trial.source = "CDT"
                trial.drug_name = drug
                
                try:
                    # 获取所有单元格
                    cells = row.eles('css:td')
                    
                    if len(cells) >= 5:
                        trial.trial_id = cells[0].text.strip() or "N/A"
                        trial.indication = cells[1].text.strip()[:30] if len(cells) > 1 else "N/A"
                        trial.sponsor = cells[2].text.strip()[:30] if len(cells) > 2 else "N/A"
                        trial.status = cells[3].text.strip()[:20] if len(cells) > 3 else "N/A"
                        trial.phase = cells[4].text.strip() if len(cells) > 4 else "N/A"
                        
                        # 尝试获取链接
                        link = cells[0].ele('css:a', timeout=0.5)
                        if link:
                            href = link.attr('href') or ''
                            if href:
                                trial.url = href if href.startswith('http') else f"https://www.chinadrugtrials.org.cn{href}"
                
                except Exception:
                    pass
                
                if trial.trial_id and trial.trial_id != "N/A":
                    results.append(trial)
                    
        except Exception as e:
            print(f"[WARN] 解析结果失败: {e}", file=sys.stderr)
        
        return results


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
        row = [
            f"[{d['临床ID']}]({d['链接']})",
            d["药品名称"],
            d["开展国家"],
            d["适应症"],
            normalize_phase(d["临床阶段"]),
            d["当前状态"],
            d["计划入组"],
            d["开始日期"],
            d["完成日期"],
            d["对照药物"],
            d["Sponsor"],
            d["Primary Outcome"],
            d["Secondary Outcome"],
            d["最近更新"],
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
    value = str(phase or "—").strip()
    return re.sub(r"^PHASE\s*([1-4])$", lambda match: f"Phase {['I', 'II', 'III', 'IV'][int(match.group(1)) - 1]}", value, flags=re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser(description="药品临床试验查询")
    parser.add_argument("--drug", "-d", required=True, help="药品名称")
    parser.add_argument("--indication", "-i", help="适应症")
    parser.add_argument("--sponsor", "-s", help="申办方")
    parser.add_argument("--max", "-m", type=int, default=100, help="最大结果数（默认100）")
    parser.add_argument("--output", "-o", help="输出文件路径（可选）")
    parser.add_argument("--source", choices=["ctg"], default="ctg",
                        help="数据源: ctg(clinicaltrials.gov)")
    parser.add_argument("--format", choices=["pipeline-markdown", "json"],
                        default="pipeline-markdown", help="输出格式")
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"药品临床试验查询")
    print(f"{'='*60}")
    print(f"药品名称: {args.drug}")
    if args.indication:
        print(f"适应症: {args.indication}")
    if args.sponsor:
        print(f"申办方: {args.sponsor}")
    print(f"数据源: {args.source}")
    print(f"{'='*60}\n")
    
    all_trials = []
    
    # 查询 clinicaltrials.gov
    if args.source == "ctg":
        print("[1/1] 查询 clinicaltrials.gov...")
        ctg = ClinicalTrialsGov()
        ctg_trials = ctg.search(
            drug=args.drug,
            indication=args.indication,
            sponsor=args.sponsor,
            max_results=args.max
        )
        print(f"      找到 {len(ctg_trials)} 条记录")
        all_trials.extend(ctg_trials)
    
    print(f"\n{'='*60}")
    print(f"总计: {len(all_trials)} 条临床试验记录")
    print(f"{'='*60}\n")
    
    if args.format == "json":
        print(json.dumps([trial.to_dict() for trial in all_trials], ensure_ascii=False, indent=2))
        return 0

    # 生成与 drug-spec.md 一致的管线表格
    all_trials.sort(key=lambda trial: phase_sort_key(trial.phase, trial.start_date))
    table_md = generate_pipeline_markdown(all_trials)
    
    # 统计信息
    ctg_count = sum(1 for t in all_trials if t.source == "CTG")
    stats = f"\n---\n"
    stats += f"clinicaltrials.gov: {ctg_count} 条记录\n"
    stats += f"总计: {len(all_trials)} 条记录\n"
    
    full_output = table_md + stats
    
    print(full_output)
    
    # 保存到文件
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(f"# {args.drug} 临床试验查询结果\n\n")
            f.write(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(full_output)
        print(f"\n结果已保存到: {args.output}")
    
    return 0


def phase_sort_key(phase: str, start_date: str = "") -> tuple[int, int, int]:
    """Sort Phase III before Phase II/I and newer start dates first."""
    normalized = normalize_phase(phase).lower()
    rank = {"phase iii": 0, "phase ii": 1, "phase i": 2, "phase iv": 3}.get(normalized, 4)
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
