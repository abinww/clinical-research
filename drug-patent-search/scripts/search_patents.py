#!/usr/bin/env python3
"""药物/公司专利检索脚本。

数据源：
- Google Patents XHR（主力，全球覆盖含 CN）
- FreePatentsOnline 专家检索（兜底，US 为主，无 CN）

模式：
- drug    按药品检索（名称轴/公司轴/组件轴），输出 drug-spec 的 ## 药品专利 表格
- company 按公司+时间窗检索，输出该公司近年专利方向分布

类型判定：
- 优先用 CPC/IPC 分类号映射（FPO 授权详情页可得）
- 缺失时用标题启发式兜底
- 类型：compound / combo / use / other（最终以权利要求为准）
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

GP_XHR_URL = "https://patents.google.com/xhr/query"
FPO_BASE = "https://www.freepatentsonline.com"
FPO_RESULT_URL = f"{FPO_BASE}/result.html"

TYPE_ORDER = ("compound", "combo", "use", "other")
TYPE_LABELS = {
    "compound": "核心物质",
    "combo": "联合用药",
    "use": "用途/生物标志物",
    "other": "平台延伸/其他",
}

# 标题用途特征（高于 CPC 结构码，用于"评分/标志物/预后"类用途专利）
TITLE_USE_PATTERNS = (
    r"methods? of treating|methods? for treating|use of .+ for|treatment of|in treating|"
    r"therapeutic method|scoring method|biomarker|predicting|prognos|diagnos"
)

# 结构线索备注时排除的纯用途/联用码
REMARK_EXCLUDE_PREFIX = ("A61K45", "A61K2300", "A61P")


class SourceUnavailable(Exception):
    """数据源不可用（网络失败/限流/被屏蔽）。"""


@dataclass
class PatentResult:
    publication_number: str = "—"
    title: str = "—"
    assignee: str = "—"
    filing_date: str = "—"
    priority_date: str = "—"
    grant_date: str = "—"
    publication_date: str = "—"
    url: str = "—"
    source: str = "—"
    cpc: list = field(default_factory=list)
    patent_type: str = "other"
    remark: str = "—"
    provenance: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "publication_number": self.publication_number,
            "title": self.title,
            "assignee": self.assignee,
            "filing_date": self.filing_date,
            "priority_date": self.priority_date,
            "grant_date": self.grant_date,
            "publication_date": self.publication_date,
            "url": self.url,
            "source": self.source,
            "cpc": self.cpc,
            "patent_type": self.patent_type,
            "remark": self.remark,
            "provenance": self.provenance,
        }


def display_value(value: object) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    return "—" if text in {"", "N/A", "-", "nan"} else text


def strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "").strip())


def norm_date(value: object) -> str:
    """统一日期为 YYYY-MM-DD；接受 ISO / YYYYMMDD / MM/DD/YYYY / 仅年份。"""
    text = str(value or "").strip()
    if not text or text == "—":
        return "—"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if m:
        return text
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{4})$", text)
    if m:
        return f"{text}-01-01"
    return text


def date_ym(value: str) -> tuple:
    m = re.match(r"^(\d{4})-(\d{2})-", norm_date(value))
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def date_ymd(value: str) -> tuple:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", norm_date(value))
    if m:
        return tuple(int(part) for part in m.groups())
    return 0, 0, 0


def validate_filter_date(value: Optional[str], option: str) -> Optional[str]:
    """Require complete, calendar-valid YYYY-MM-DD filter dates."""
    if value is None:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{option} 必须为 YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{option} 不是有效日期") from exc
    return value


def classify_patent(title: str, cpc_codes: Optional[list] = None) -> str:
    """判定专利类型。

    优先级：标题 combo → CPC 联用码 → 标题用途 → CPC 结构码 → CPC 治疗/制剂码
    → 标题结构词 → other。标题明确的组合/用途信息比 CPC 更可靠（联用专利
    常同时携带偶联结构码 A61K47/68，若 CPC 优先会被误判为 compound）。
    """
    codes = [c for c in (cpc_codes or []) if c]
    text = (title or "").lower()

    if re.search(r"combination|in combination with|combined therapy|combined use", text):
        return "combo"
    if any(c.startswith(key) for c in codes for key in ("A61K45/06", "A61K2300/00")):
        return "combo"
    if re.search(TITLE_USE_PATTERNS, text):
        return "use"
    for key in ("A61K47/68", "C07K16", "C07K19", "C07K7/06", "A61K31/4745"):
        if any(c.startswith(key) for c in codes):
            return "compound"
    if any(c.startswith(key) for c in codes for key in ("A61P", "A61K9")):
        return "use"
    if re.search(r"conjugate|antibody-drug|antibody drug|immunoconjugat|compound", text):
        return "compound"
    return "other"


def cpc_remark(cpc_codes: Optional[list] = None) -> str:
    """从 CPC 提取结构线索（排除纯用途/联用码），最多 2 个。"""
    seen = []
    for code in cpc_codes or []:
        if code.startswith(REMARK_EXCLUDE_PREFIX):
            continue
        if code not in seen:
            seen.append(code)
        if len(seen) >= 2:
            break
    return " · ".join(seen) if seen else "—"


def merge_results(results: list[PatentResult]) -> list[PatentResult]:
    """按公开号去重，并合并查询来源及首条记录缺失的结构化字段。"""
    merged = {}
    for pr in results:
        key = re.sub(r"[^A-Z0-9]", "", pr.publication_number.upper())
        if not key or key == "—":
            continue
        if key not in merged:
            merged[key] = pr
            continue
        current = merged[key]
        for name in ("title", "assignee", "filing_date", "priority_date",
                     "grant_date", "publication_date", "url", "remark"):
            if getattr(current, name) == "—" and getattr(pr, name) != "—":
                setattr(current, name, getattr(pr, name))
        current.cpc = list(dict.fromkeys(current.cpc + pr.cpc))
        current.provenance = list(dict.fromkeys(current.provenance + pr.provenance))
        if current.cpc:
            current.patent_type = classify_patent(current.title, current.cpc)
            current.remark = cpc_remark(current.cpc)
    return list(merged.values())


def _as_list(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def _fetch(url: str, headers: dict, timeout: int, delay: float,
           retries: int = 2) -> Optional[str]:
    """带重试与间隔的 GET，失败返回 None。"""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status < 200 or resp.status >= 300:
                    raise urllib.error.HTTPError(
                        url, resp.status, resp.reason, resp.headers, None)
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError,
                TimeoutError, OSError):
            if attempt < retries:
                time.sleep(delay * (attempt + 2))
            else:
                return None
    return None


class GooglePatents:
    """Google Patents XHR 检索（全球覆盖，含 CN）。"""

    BASE_URL = GP_XHR_URL
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    def __init__(self, delay: float = 2.0, timeout: int = 12, retries: int = 1):
        # timeout 较短：GP 不可达（如未配置代理直连被墙）时快速降级 FPO。
        # 代理不做专门设计：urllib 原生读取 HTTPS_PROXY/HTTP_PROXY 环境变量与系统代理。
        self.delay = delay
        self.timeout = timeout
        self.retries = retries

    def search(self, query_terms: Optional[list] = None,
               component_terms: Optional[list] = None,
               assignee=None, country: Optional[str] = None,
               after: Optional[str] = None, before: Optional[str] = None,
               max_results: int = 200) -> list[PatentResult]:
        """执行一个或多个查询并合并去重。

        - query_terms 为空时（公司模式）逐个按 assignee 检索。
        - after/before 传给 GP，并在 Python 侧严格按完整申请日二次过滤。
          priority_date 仅作为独立字段报告，不代替申请日。
        """
        if not query_terms and not component_terms and not assignee:
            raise ValueError("drug 模式至少需要一个 --query，company 模式至少需要 --assignee")

        all_patents: list[PatentResult] = []
        queries = self._build_queries(query_terms or [], _as_list(assignee),
                                      component_terms or [])
        first_error = None
        for q, asg, provenance in queries:
            try:
                page_patents = self._query_page(q=q, assignee=asg, country=country,
                                                 after=after, before=before,
                                                 max_results=max_results,
                                                 provenance=provenance)
                all_patents.extend(page_patents)
            except SourceUnavailable as exc:
                if first_error is None:
                    first_error = exc
                continue

        if first_error is not None:
            raise first_error

        results = merge_results(all_patents)
        if after or before:
            results = self._filter_by_date(results, after, before)
        return results[:max_results]

    def _build_queries(self, terms: list[str], assignees: list[str],
                       components: Optional[list[str]] = None) -> list[tuple]:
        """构造独立名称/组件轴，以及每个申请人 x 每个药品别名轴。"""
        pairs = []
        for term in terms:
            pairs.append((term, None, f"alias:{term}"))
        for term in components or []:
            pairs.append((term, None, f"component:{term}"))
        for assignee in assignees:
            if terms:
                for term in terms:
                    pairs.append((term, assignee,
                                  f"assignee:{assignee} x alias:{term}"))
            else:
                pairs.append((None, assignee, f"assignee:{assignee}"))
        # 去重
        seen = set()
        deduped = []
        for p in pairs:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        return deduped

    def _query_page(self, q, assignee, country, after, before,
                    max_results: int, provenance: str = "—") -> list[PatentResult]:
        patents: list[PatentResult] = []
        page = 1
        while True:
            inner = self._inner_params(q, assignee, country, after, before, page)
            data = self._call(inner)
            if data is None:
                raise SourceUnavailable("Google Patents 不可用（网络/限流/被屏蔽）")
            results_info = data.get("results") or {}
            total = int(results_info.get("total_num_results") or 0)
            page_patents = self._parse(data, provenance)
            patents.extend(page_patents)
            if not page_patents or len(patents) >= max_results or len(patents) >= total:
                break
            page += 1
            if page > 50:
                break
            time.sleep(self.delay)
        return patents[:max_results]

    @staticmethod
    def _inner_params(q, assignee, country, after, before, page) -> str:
        parts = []
        if q:
            parts.append(f'q="{q}"')
        if assignee:
            parts.append(f"assignee={assignee}")
        if country:
            parts.append(f"country={country}")
        if after:
            parts.append(f"after={GooglePatents._gp_date(after)}")
        if before:
            parts.append(f"before={GooglePatents._gp_date(before)}")
        if page and page > 1:
            parts.append(f"page={page}")
        return "&".join(parts)

    @staticmethod
    def _gp_date(value: str) -> str:
        return norm_date(value).replace("-", "")

    def _call(self, inner: str) -> Optional[dict]:
        url = f"{self.BASE_URL}?url={urllib.parse.quote(inner, safe='')}&exp="
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.HEADERS)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status < 200 or resp.status >= 300:
                        raise urllib.error.HTTPError(
                            url, resp.status, resp.reason, resp.headers, None)
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.HTTPError, urllib.error.URLError,
                    TimeoutError, json.JSONDecodeError, OSError):
                if attempt < self.retries:
                    time.sleep(self.delay * (attempt + 2))
                else:
                    return None
        return None

    @staticmethod
    def _parse(data: dict, provenance: str = "—") -> list[PatentResult]:
        patents = []
        clusters = data.get("results", {}).get("cluster") or []
        for cluster in clusters:
            for item in cluster.get("result") or []:
                p = item.get("patent") or {}
                pub = strip_html(p.get("publication_number", ""))
                if not pub:
                    continue
                raw_assignees = p.get("assignee") or []
                if isinstance(raw_assignees, str):
                    raw_assignees = [raw_assignees]
                assignees = [strip_html(a) for a in raw_assignees]
                title = strip_html(p.get("title", ""))
                filing = norm_date(p.get("filing_date") or p.get("application_date") or "")
                priority = norm_date(p.get("priority_date") or "")
                grant = norm_date(p.get("grant_date") or "")
                publication = norm_date(p.get("publication_date") or "")
                codes = GooglePatents._extract_codes(p)
                pr = PatentResult(
                    publication_number=pub,
                    title=display_value(title),
                    assignee="; ".join(a for a in assignees if a) or "—",
                    filing_date=filing,
                    priority_date=priority,
                    grant_date=grant,
                    publication_date=publication,
                    url=f"https://patents.google.com/patent/{pub}/en",
                    source="GP",
                    cpc=codes,
                    provenance=[] if provenance == "—" else [provenance],
                )
                pr.patent_type = classify_patent(title, codes)
                pr.remark = cpc_remark(codes)
                patents.append(pr)
        return patents

    @staticmethod
    def _extract_codes(patent: dict) -> list[str]:
        values = []
        for key in ("cpc", "cpc_code", "classification", "classifications"):
            raw = patent.get(key) or []
            if not isinstance(raw, list):
                raw = [raw]
            for item in raw:
                text = item if isinstance(item, str) else json.dumps(item)
                values.extend(FreePatentsOnline.CODE_RE.findall(strip_html(text)))
        return list(dict.fromkeys(values))

    @staticmethod
    def _filter_by_date(results: list[PatentResult],
                        after: Optional[str], before: Optional[str]) -> list[PatentResult]:
        a_date = date_ymd(after) if after else (0, 0, 0)
        b_date = date_ymd(before) if before else (9999, 12, 31)
        out = []
        for pr in results:
            filing_date = date_ymd(pr.filing_date)
            if filing_date == (0, 0, 0):
                continue
            if filing_date < a_date:
                continue
            if filing_date > b_date:
                continue
            out.append(pr)
        return out


class FreePatentsOnline:
    """FreePatentsOnline 专家检索（US 为主，兜底源，无 CN 覆盖）。"""

    BASE_URL = FPO_RESULT_URL
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Referer": FPO_BASE + "/",
    }
    LIST_ROW_RE = re.compile(
        r'(?s)valign="top">\s*([A-Z]{2}[A-Z0-9]{7,11})\s*</td>\s*'
        r'<td[^>]*>\s*<a\s+href="([^"]+\.html)"[^>]*>(.*?)</a>')
    CODE_RE = re.compile(r"[A-Z]\d{2}[A-Z]\d+/\d+")

    def __init__(self, delay: float = 6.0, detail_delay: float = 6.0,
                 timeout: int = 45, retries: int = 2):
        self.delay = delay
        self.detail_delay = detail_delay
        self.timeout = timeout
        self.retries = retries

    def search(self, query_terms: Optional[list] = None,
               component_terms: Optional[list] = None,
               assignee=None,
               after: Optional[str] = None, before: Optional[str] = None,
               max_results: int = 15) -> list[PatentResult]:
        if not query_terms and not component_terms and not assignee:
            raise ValueError("至少需要一个查询词或公司名")
        results = []
        first_error = None
        queries = self._build_queries(query_terms or [], _as_list(assignee),
                                      component_terms or [])
        for expr, provenance in queries:
            page = self._list_page(expr)
            if page is None:
                first_error = first_error or SourceUnavailable(
                    "FreePatentsOnline 不可用（网络/限流）")
                continue
            for pub, href, title in self._parse_list(page):
                time.sleep(self.detail_delay)
                detail = self._detail_page(f"{FPO_BASE}{href}")
                pr = self._parse_detail(pub, title, detail)
                pr.provenance = [provenance]
                filing_date = date_ymd(pr.filing_date)
                if (after or before) and filing_date == (0, 0, 0):
                    continue
                if after and filing_date < date_ymd(after):
                    continue
                if before and filing_date > date_ymd(before):
                    continue
                results.append(pr)
        if first_error is not None:
            raise first_error
        return merge_results(results)[:max_results]

    def _build_expr(self, terms: list[str], assignee: Optional[str]) -> str:
        parts = []
        if assignee:
            parts.append(f'AN/"{assignee}"')
        for term in terms:
            parts.append(f'SPEC/"{term}"')
        return " AND ".join(parts)

    def _build_queries(self, terms: list[str], assignees: list[str],
                       components: Optional[list[str]] = None) -> list[tuple[str, str]]:
        queries = []
        for term in terms:
            queries.append((self._build_expr([term], None), f"alias:{term}"))
        for term in components or []:
            queries.append((self._build_expr([term], None), f"component:{term}"))
        for assignee in assignees:
            if terms:
                for term in terms:
                    queries.append((self._build_expr([term], assignee),
                                    f"assignee:{assignee} x alias:{term}"))
            else:
                queries.append((self._build_expr([], assignee),
                                f"assignee:{assignee}"))
        return list(dict.fromkeys(queries))

    def _list_page(self, expr: str) -> Optional[str]:
        q = urllib.parse.quote(expr, safe="")
        url = (f"{self.BASE_URL}?srch=xprtsrch&query_txt={q}"
               f"&uspat=on&usapp=on")
        return _fetch(url, self.HEADERS, self.timeout, self.delay, self.retries)

    def _detail_page(self, url: str) -> Optional[str]:
        return _fetch(url, self.HEADERS, self.timeout, self.detail_delay, self.retries)

    @classmethod
    def _parse_list(cls, html: str) -> list[tuple[str, str, str]]:
        rows = []
        for m in cls.LIST_ROW_RE.finditer(html):
            pub = m.group(1).strip()
            href = m.group(2).strip()
            title = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            rows.append((pub, href, title))
        return rows

    @classmethod
    def _parse_detail(cls, pub: str, title: str,
                      html: Optional[str]) -> PatentResult:
        pr = PatentResult(
            publication_number=pub,
            title=display_value(title),
            url=f"https://patents.google.com/patent/{pub}/en",
            source="FPO",
        )
        if not html:
            return pr
        filing = re.search(r"Filing Date:</div>\s*<div class=\"disp_elm_text\">\s*([\d/]+)", html)
        priority = re.search(r"Priority Date:</div>\s*<div class=\"disp_elm_text\">\s*([\d/]+)", html)
        pubdate = re.search(r"Publication Date:</div>\s*<div class=\"disp_elm_text\">\s*([\d/]+)", html)
        issue = re.search(r"Issue Date:</div>\s*<div class=\"disp_elm_text\">\s*([\d/]+)", html)
        asg = re.search(r"Assignee:</div>\s*<div class=\"disp_elm_text\">\s*([^<]+)", html)
        pr.filing_date = norm_date(filing.group(1) if filing else "")
        pr.priority_date = norm_date(priority.group(1) if priority else "")
        pr.publication_date = norm_date(pubdate.group(1) if pubdate else "")
        pr.grant_date = norm_date(issue.group(1) if issue else "")
        if asg:
            pr.assignee = asg.group(1).strip()
        pr.cpc = list(dict.fromkeys(cls.CODE_RE.findall(html)))
        pr.patent_type = classify_patent(title, pr.cpc)
        pr.remark = cpc_remark(pr.cpc)
        return pr


class PatentSearch:
    """检索编排：GP 优先，失败自动降级 FPO。"""

    def __init__(self, source: str = "auto", gp_delay: float = 2.0,
                 fpo_delay: float = 8.0):
        self.source = source
        self.gp = GooglePatents(delay=gp_delay)
        self.fpo = FreePatentsOnline(delay=fpo_delay)

    def run(self, mode: str, query_terms: Optional[list] = None,
            component_terms: Optional[list] = None, assignee=None,
            country: Optional[str] = None,
            after: Optional[str] = None, before: Optional[str] = None,
            max_results: int = 100) -> tuple[list[PatentResult], str]:
        if self.source in ("auto", "gp"):
            try:
                results = self.gp.search(
                    query_terms=query_terms, component_terms=component_terms,
                    assignee=assignee, country=country,
                    after=after, before=before,
                    max_results=max(1, min(max_results, 200)))
                return results, "GP"
            except SourceUnavailable:
                if self.source == "gp":
                    raise
        results = self.fpo.search(
            query_terms=query_terms, component_terms=component_terms,
            assignee=assignee,
            after=after, before=before,
            max_results=max(1, min(max_results, 15)))
        return results, "FPO"


def aggregate_by_type(patents: list[PatentResult]) -> Counter:
    return Counter(pr.patent_type for pr in patents)


def aggregate_by_assignee(patents: list[PatentResult]) -> Counter:
    return Counter(pr.assignee for pr in patents)


def aggregate_type_year(patents: list[PatentResult]) -> dict:
    table = defaultdict(Counter)
    for pr in patents:
        year = date_ym(pr.filing_date)[0]
        if year:
            table[pr.patent_type][year] += 1
    return {t: dict(table[t]) for t in table}


def sort_key(pr: PatentResult) -> tuple:
    rank = {t: i for i, t in enumerate(TYPE_ORDER)}
    y, m = date_ym(pr.filing_date)
    return (rank.get(pr.patent_type, 99), -y, -m)


def _fmt_counter(counter: Counter, total: int) -> str:
    items = [(k, v) for k, v in counter.items() if v]
    items.sort(key=lambda kv: -kv[1])
    return " · ".join(f"{k} {v}" for k, v in items) or "—"


def classification_note(patents: list[PatentResult], source: str) -> str:
    if source != "GP":
        return "CPC/IPC（可获得时）或标题启发式"
    classified = sum(bool(pr.cpc) for pr in patents)
    if not classified:
        return "标题启发式（GP XHR 未返回 CPC）"
    if classified == len(patents):
        return "GP XHR 返回的 CPC/分类号 + 标题启发式"
    return f"混合：{classified} 件有 CPC/分类号，其余为标题启发式"


def provenance_note(patents: list[PatentResult]) -> str:
    counts = Counter(axis for patent in patents for axis in patent.provenance)
    return _fmt_counter(counts, len(patents))


def render_drug_markdown(patents: list[PatentResult], source: str) -> str:
    if not patents:
        return "未找到相关专利。\n"
    updated = datetime.now().strftime("%Y-%m-%d")
    source_note = {
        "GP": "Google Patents（覆盖 US/CN 等全球公开）",
        "FPO": "FreePatentsOnline（仅 US 为主；CN/WO/EP 未覆盖）",
    }.get(source, source)
    typecnt = aggregate_by_type(patents)
    assignee_cnt = aggregate_by_assignee(patents)
    type_str = " · ".join(f"{t} {typecnt[t]}" for t in TYPE_ORDER if typecnt[t]) or "—"
    lines = [
        "## 药品专利",
        "",
        f"> 更新时间: {updated}",
        f"> 数据来源: {source_note}",
        f"> 分类依据: {classification_note(patents, source)}",
        f"> 查询轴命中: {provenance_note(patents)}",
        "> 类型: compound=核心物质 · combo=联合用药 · use=用途/生物标志物 · other=平台延伸/其他",
        f"> 类型分布: {type_str}",
        f"> 申请人分布: {_fmt_counter(assignee_cnt, len(patents))}",
        "",
        "| 公开号 | 标题 | 类型 | 申请人 | 申请日 | 备注 |",
        "|--------|------|------|--------|--------|------|",
    ]
    for pr in sorted(patents, key=sort_key):
        linked = f"[{pr.publication_number}]({pr.url})"
        remark = pr.remark if pr.remark and pr.remark != "—" else "—"
        row = [
            linked,
            (pr.title or "—").replace("|", "\\|").replace("\n", " "),
            pr.patent_type,
            (pr.assignee or "—").replace("|", "\\|"),
            pr.filing_date,
            remark.replace("|", "\\|"),
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_company_markdown(patents: list[PatentResult], assignee: str,
                            after: str, before: str, country: str,
                            source: str) -> str:
    if not patents:
        return f"未找到 {assignee} 的相关专利。\n"
    updated = datetime.now().strftime("%Y-%m-%d")
    source_note = {
        "GP": "Google Patents",
        "FPO": "FreePatentsOnline（仅 US）",
    }.get(source, source)
    window = f"{after or '不限'} ~ {before or '不限'}"
    lines = [
        f"# {assignee} 专利方向",
        "",
        f"> 更新时间: {updated}",
        f"> 数据来源: {source_note}",
        f"> 分类依据: {classification_note(patents, source)}",
        f"> 查询轴命中: {provenance_note(patents)}",
        f"> 查询: assignee={assignee} · 时间窗 {window} · country={country or '全部'}",
        f"> 命中: {len(patents)} 件",
        "",
        "## 类型 × 年份分布",
        "",
        "| 类型 | " + " | ".join(str(y) for y in sorted(_all_years(patents))) + " |",
        "|------|" + "|".join(["---"] * len(_all_years(patents))) + "|",
    ]
    agg = aggregate_type_year(patents)
    years = _all_years(patents)
    for t in TYPE_ORDER:
        if t not in agg:
            continue
        row = [TYPE_LABELS.get(t, t)] + [str(agg[t].get(y, 0)) for y in years]
        lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        "## 专利清单",
        "",
        "| 公开号 | 标题 | 类型 | 申请日 | 备注 |",
        "|--------|------|------|--------|------|",
    ]
    for pr in sorted(patents, key=sort_key):
        linked = f"[{pr.publication_number}]({pr.url})"
        remark = pr.remark if pr.remark and pr.remark != "—" else "—"
        row = [
            linked,
            (pr.title or "—").replace("|", "\\|").replace("\n", " "),
            pr.patent_type,
            pr.filing_date,
            remark.replace("|", "\\|"),
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _all_years(patents: list[PatentResult]) -> list[int]:
    years = sorted({date_ym(pr.filing_date)[0] for pr in patents if date_ym(pr.filing_date)[0]})
    return years


def build_json(patents: list[PatentResult], source: str,
               mode: str, query: dict) -> dict:
    payload = {
        "mode": mode,
        "source": source,
        "query": query,
        "total": len(patents),
        "patents": [pr.to_dict() for pr in patents],
        "type_distribution": dict(aggregate_by_type(patents)),
        "assignee_distribution": dict(aggregate_by_assignee(patents)),
        "query_axis_hits": dict(Counter(
            axis for patent in patents for axis in patent.provenance)),
    }
    if mode == "company":
        payload["type_year"] = aggregate_type_year(patents)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="药物/公司专利检索")
    parser.add_argument("--mode", choices=["drug", "company"], default="drug")
    parser.add_argument("--query", "-q", action="append",
                        help="药品别名（可多次传入，每个别名单独查询）")
    parser.add_argument("--component", action="append",
                        help="组件名（可多次传入，每个组件单独查询）")
    parser.add_argument("--assignee", "-a", action="append",
                        help="申请人/公司名（可多次传入）")
    parser.add_argument("--country", help="国家代码过滤（如 CN、US）")
    parser.add_argument("--after", help="申请日下限 YYYY-MM-DD")
    parser.add_argument("--before", help="申请日上限 YYYY-MM-DD")
    parser.add_argument("--source", choices=["auto", "gp", "fpo"], default="auto")
    parser.add_argument("--max", type=int, default=100, help="最大结果数（drug 模式）")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()
    try:
        args.after = validate_filter_date(args.after, "--after")
        args.before = validate_filter_date(args.before, "--before")
    except ValueError as exc:
        parser.error(str(exc))
    if args.after and args.before and args.after > args.before:
        parser.error("--after 不得晚于 --before")

    if args.mode == "company" and not args.assignee:
        parser.error("company 模式必须提供 --assignee")
    if args.mode == "drug" and not (args.query or args.component):
        parser.error("drug 模式至少需要一个 --query 或 --component")

    runner = PatentSearch(source=args.source)
    max_results = args.max if args.max else (100 if args.mode == "drug" else 100)
    try:
        patents, used_source = runner.run(
            mode=args.mode, query_terms=args.query, component_terms=args.component,
            assignee=args.assignee,
            country=args.country, after=args.after, before=args.before,
            max_results=max_results)
    except SourceUnavailable as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    print(f"[INFO] 数据源: {used_source}，命中 {len(patents)} 件",
          file=sys.stderr)

    if args.format == "json":
        query_info = {
            "mode": args.mode, "query": args.query, "assignee": args.assignee,
            "component": args.component,
            "country": args.country, "after": args.after, "before": args.before,
        }
        print(json.dumps(build_json(patents, used_source, args.mode, query_info),
                         ensure_ascii=False, indent=2))
        return 0

    if args.mode == "company":
        print(render_company_markdown(patents, "; ".join(args.assignee or []),
                                      args.after or "", args.before or "",
                                      args.country or "", used_source))
    else:
        print(render_drug_markdown(patents, used_source))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
