"""本周财报 + 经济数据日历（Nasdaq 公开接口，无需 API Key）。"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo

import requests

NASDAQ = "https://api.nasdaq.com/api/calendar"
ET = ZoneInfo("America/New_York")
HKT = ZoneInfo("Asia/Hong_Kong")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}
REQUEST_TIMEOUT = 12.0
CACHE_TTL = 1800.0  # 30 min

# 财报无精确钟点时用美股惯例时刻（美东）
_EARNINGS_ET_CLOCK = {
    "bmo": (8, 0),   # 盘前常见窗口
    "amc": (16, 5),  # 收盘后常见窗口
}

_HOUR_RANK = {"bmo": 0, "tbd": 1, "amc": 2, "eco": -1}
_cache: Dict[str, Any] = {"at": 0.0, "payload": None}


def _get(url: str) -> Any:
    resp = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        proxies={"http": None, "https": None},
    )
    resp.raise_for_status()
    return resp.json()


def _week_days(anchor: Optional[date] = None) -> List[date]:
    """本周一到周五（美东）。"""
    today = anchor or datetime.now(ET).date()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(5)]


def _parse_market_cap(raw: Optional[str]) -> float:
    if not raw:
        return 0.0
    s = str(raw).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _map_hour(time_code: Optional[str]) -> str:
    t = (time_code or "").lower()
    if "pre-market" in t or t == "bmo":
        return "bmo"
    if "after-hours" in t or t == "amc":
        return "amc"
    return "tbd"


def _clean_html(text: Optional[str]) -> str:
    if not text:
        return ""
    s = str(text).replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"<[^>]+>", "", s)
    return " ".join(s.split())


def _to_hkt_fields(day: date, hour: int, minute: int) -> Dict[str, Any]:
    """美东日历日 + 钟点 → 香港时间展示字段。"""
    et_dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)
    hkt_dt = et_dt.astimezone(HKT)
    time_hkt = hkt_dt.strftime("%H:%M")
    return {
        "time_et": f"{hour:02d}:{minute:02d}",
        "time_hkt": time_hkt,
        "time_hkt_short": time_hkt,
        "datetime_hkt": hkt_dt.isoformat(),
        "sort_ts": int(hkt_dt.timestamp()),
    }


def _earnings_time_fields(day: date, hour_code: str) -> Dict[str, Any]:
    clock = _EARNINGS_ET_CLOCK.get(hour_code)
    if not clock:
        return {
            "time_et": None,
            "time_hkt": "—",
            "time_hkt_short": "—",
            "datetime_hkt": None,
            "sort_ts": int(datetime(day.year, day.month, day.day, 12, 0, tzinfo=ET).timestamp()),
        }
    return _to_hkt_fields(day, clock[0], clock[1])


def _parse_eco_clock(raw: Optional[str]) -> Optional[tuple[int, int]]:
    s = (raw or "").strip()
    if not s or s in ("99:99", "TBD", "tbd"):
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h, mi


def _fetch_earnings_day(day: date) -> List[Dict[str, Any]]:
    data = _get(f"{NASDAQ}/earnings?date={day.isoformat()}")
    rows = ((data or {}).get("data") or {}).get("rows") or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or "").upper().strip()
        if not sym:
            continue
        hour = _map_hour(r.get("time"))
        tfields = _earnings_time_fields(day, hour)
        out.append(
            {
                "type": "earnings",
                "symbol": sym,
                "name": str(r.get("name") or ""),
                "hour": hour,
                "hour_label": hour.upper(),
                "date": day.isoformat(),
                "market_cap": _parse_market_cap(r.get("marketCap")),
                "eps_forecast": _clean_html(r.get("epsForecast")),
                **tfields,
                "sort_key": (
                    _HOUR_RANK[hour],
                    tfields["sort_ts"],
                    -_parse_market_cap(r.get("marketCap")),
                    sym,
                ),
            }
        )
    return out


_ECO_PRIORITY = (
    "fomc", "fed ", "interest rate decision", "cpi", "core cpi", "ppi", "core ppi",
    "nonfarm", "payroll", "gdp", "pce", "jobless", "initial jobless", "ism",
    "retail sales", "adp employment", "existing home", "pmi",
    "eia crude", "eia weekly crude",
)

_JP_ECO_PRIORITY = (
    "boj", "interest rate", "tankan", "cpi", "core cpi", "ppi", "gdp",
    "current account", "bank lending", "money stock", "m2 money", "m3 money",
    "industrial production", "economy watchers", "retail sales", "unemployment",
    "machine tool", "foreign bonds", "foreign investments", "trade balance",
)

_ECO_BLOCK = (
    "opec", "auction", "redbook", "nfib", "api weekly", "mba ", "beige book",
    "cleveland", "refinery", "distillates", "utilization", "short-term",
    "energy outlook", "employment change weekly", "mountain day", "holiday",
    "ipsos", "cftc",
)


def _eco_country_code(country: str) -> Optional[str]:
    c = country.lower().strip()
    if c in ("united states", "us", "usa"):
        return "US"
    if c in ("japan", "jp", "jpn"):
        return "JP"
    return None


def _eco_score(name: str, country: str = "US") -> int:
    n = name.lower()
    if any(b in n for b in _ECO_BLOCK):
        return -100
    priority = _JP_ECO_PRIORITY if country == "JP" else _ECO_PRIORITY
    score = 0
    for i, k in enumerate(priority):
        if k in n:
            score += 50 - i
            break
    # 弱匹配才扣分，避免 Tankan Index / Current Account n.s.a. 被误杀
    if score < 40 and any(
        x in n
        for x in (
            " purchase index",
            "refinance index",
            "market index",
            "index, n.s.a",
            "index, s.a",
            " n.s.a",
            "ex tobacco",
            " index",
        )
    ):
        score -= 25
    return score


def _eco_dedupe_key(name: str, country: str) -> str:
    n = name.lower().replace(",", "").replace(".", "").strip()
    # 归并 CPI / Core CPI 变体
    if "core cpi" in n:
        base = "core cpi"
    elif n == "cpi" or n.startswith("cpi "):
        base = "cpi"
    elif "core ppi" in n:
        base = "core ppi"
    elif n == "ppi" or n.startswith("ppi "):
        base = "ppi"
    else:
        base = n
    return f"{country}:{base}"


def _fetch_economic_day(day: date) -> List[Dict[str, Any]]:
    data = _get(f"{NASDAQ}/economicevents?date={day.isoformat()}")
    rows = ((data or {}).get("data") or {}).get("rows") or []
    candidates: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        country_raw = str(r.get("country") or "")
        country = _eco_country_code(country_raw)
        if not country:
            continue
        name = _clean_html(r.get("eventName"))
        if not name:
            continue
        score = _eco_score(name, country)
        if score < 30:
            continue
        gmt = str(r.get("gmt") or "99:99")
        # Nasdaq 字段名 gmt，美/日事件实际按美东日历日+钟点给出
        clock = _parse_eco_clock(gmt)
        if clock:
            tfields = _to_hkt_fields(day, clock[0], clock[1])
            hour_label = tfields["time_hkt"]
        else:
            tfields = {
                "time_et": None,
                "time_hkt": "—",
                "time_hkt_short": "—",
                "datetime_hkt": None,
                "sort_ts": int(
                    datetime(day.year, day.month, day.day, 12, 0, tzinfo=ET).timestamp()
                ),
            }
            hour_label = "TBD"
        candidates.append(
            {
                "type": "economic",
                "symbol": "",
                "name": name,
                "country": "Japan" if country == "JP" else "United States",
                "country_code": country,
                "hour": "eco",
                "hour_label": hour_label,
                "date": day.isoformat(),
                "consensus": _clean_html(r.get("consensus")),
                "previous": _clean_html(r.get("previous")),
                "actual": _clean_html(r.get("actual")),
                "score": score,
                **tfields,
                "sort_key": (tfields["sort_ts"], -score, name),
            }
        )

    candidates.sort(key=lambda x: (-int(x.get("score") or 0), int(x.get("sort_ts") or 0), x.get("name") or ""))
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for item in candidates:
        key = _eco_dedupe_key(item["name"], item["country_code"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=lambda x: x["sort_key"])
    return out


def _looks_us_ticker(symbol: str, name: str) -> bool:
    s = (symbol or "").upper()
    if not s or len(s) > 5 or "." in s or "/" in s:
        return False
    return s.isalpha()


def _pick_earnings(items: List[Dict[str, Any]], perps: Set[str], limit: int = 6) -> List[Dict[str, Any]]:
    """只展示有永续的美股财报，保持日历干净。"""
    us_items = [it for it in items if _looks_us_ticker(it["symbol"], it.get("name") or "")]
    picked = []
    for it in us_items:
        if it["symbol"] not in perps:
            continue
        it["has_perps"] = True
        it["market_tag"] = "Spot + Perps"
        hour_rank = _HOUR_RANK.get(it["hour"], 1)
        it["sort_key"] = (
            hour_rank,
            int(it.get("sort_ts") or 0),
            -float(it.get("market_cap") or 0),
            it["symbol"],
        )
        picked.append(it)
    picked.sort(key=lambda x: x["sort_key"])
    return picked[:limit]


def fetch_week_calendar(
    *,
    perps_pairs: Optional[Set[str]] = None,
    force: bool = False,
    days: Optional[List[date]] = None,
) -> Dict[str, Any]:
    now = time.time()
    if not force and _cache["payload"] and now - _cache["at"] < CACHE_TTL:
        # 仍用最新 perps 标记刷新 has_perps
        payload = _cache["payload"]
        if perps_pairs is not None:
            return _retag(payload, perps_pairs)
        return payload

    week = days or _week_days()
    perps = {p.upper() for p in (perps_pairs or set())}
    columns: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    def one(day: date):
        earn, eco = [], []
        err = None
        try:
            earn = _fetch_earnings_day(day)
        except Exception as e:
            err = f"earnings: {e}"
        try:
            eco = _fetch_economic_day(day)
        except Exception as e:
            err = (err + "; " if err else "") + f"economic: {e}"
        return day, earn, eco, err

    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = [pool.submit(one, d) for d in week]
        results = [f.result() for f in as_completed(futs)]
    results.sort(key=lambda x: x[0])

    for day, earn, eco, err in results:
        if err:
            errors[day.isoformat()] = err
        earn_picked = _pick_earnings(earn, perps, limit=6)
        # 美/日宏观各取重要度 Top2，再按香港时间排
        us_eco = [e for e in eco if e.get("country_code") == "US"]
        jp_eco = [e for e in eco if e.get("country_code") == "JP"]
        eco_top = sorted(us_eco, key=lambda x: x["sort_key"])[:2] + sorted(
            jp_eco, key=lambda x: x["sort_key"]
        )[:2]
        eco_picked = sorted(
            eco_top, key=lambda x: (int(x.get("sort_ts") or 0), x.get("name") or "")
        )
        for e in eco_picked:
            e["has_perps"] = False
            code = e.get("country_code") or "US"
            e["market_tag"] = "JP" if code == "JP" else "US"

        # 同日按香港时间排序（宏观+财报混排更直观）
        events: List[Dict[str, Any]] = sorted(
            [*eco_picked, *earn_picked],
            key=lambda x: (int(x.get("sort_ts") or 0), 0 if x.get("type") == "economic" else 1, x.get("symbol") or x.get("name") or ""),
        )

        columns.append(
            {
                "date": day.isoformat(),
                "label": _day_label(day),
                "events": events,
                "counts": {
                    "earnings": len(earn_picked),
                    "economic": len(eco_picked),
                    "earnings_total": len(earn),
                },
            }
        )

    payload = {
        "week_start": week[0].isoformat(),
        "week_end": week[-1].isoformat(),
        "timezone": "Asia/Hong_Kong",
        "timezone_note": "展示为香港时间；财报 BMO≈美东08:00、AMC≈美东16:05",
        "columns": columns,
        "errors": errors,
        "source": "nasdaq",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _cache["at"] = now
    _cache["payload"] = payload
    return payload


def _day_label(day: date) -> str:
    # 跨平台避免 %-d：手动去前导零
    return f"{day.strftime('%a %b')} {day.day}"


def _retag(payload: Dict[str, Any], perps: Set[str]) -> Dict[str, Any]:
    perps_u = {p.upper() for p in perps}
    cols = []
    for col in payload.get("columns") or []:
        events = []
        for ev in col.get("events") or []:
            e = dict(ev)
            if e.get("type") == "earnings":
                e["has_perps"] = e.get("symbol", "").upper() in perps_u
                e["market_tag"] = "Spot + Perps" if e["has_perps"] else "Spot"
            events.append(e)
        c = dict(col)
        c["events"] = events
        cols.append(c)
    out = dict(payload)
    out["columns"] = cols
    return out
