"""本周财报 + 经济数据日历（Nasdaq 公开接口，无需 API Key）。"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
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
# 已过公布点但仍缺 actual 时，缩短缓存以便尽快拉到公布值
CACHE_TTL_PENDING_ACTUAL = 90.0
_FF_DISK = Path(__file__).resolve().parents[1] / "data" / "calendar" / "ff_align.json"

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


def _eco_family_key(name: str) -> str:
    """事件族键，用于跨数据源对齐（忽略 m/m、y/y 等后缀）。"""
    n = (name or "").lower().replace("-", " ").replace(",", " ")
    n = re.sub(r"\b(m/m|y/y|mom|yoy|sa|n\.?s\.?a\.?)\b", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    rules = (
        ("core cpi", "core_cpi"),
        ("cpi", "cpi"),
        ("core ppi", "core_ppi"),
        ("ppi", "ppi"),
        ("nonfarm payroll", "nfp"),
        ("non farm payroll", "nfp"),
        ("nonfarm employment", "nfp"),
        ("non farm employment", "nfp"),
        ("unemployment rate", "unemployment"),
        ("average hourly earnings", "ahe"),
        ("initial jobless", "jobless"),
        ("jobless claims", "jobless"),
        ("core pce", "core_pce"),
        ("pce price", "pce"),
        ("pce", "pce"),
        ("retail sales", "retail"),
        ("existing home sales", "ehs"),
        ("new home sales", "nhs"),
        ("gdp", "gdp"),
        ("ism manufacturing", "ism_mfg"),
        ("ism services", "ism_svc"),
        ("adp", "adp"),
        ("fomc", "fomc"),
        ("interest rate decision", "fomc"),
        ("real earnings", "real_earnings"),
    )
    for needle, key in rules:
        if needle in n:
            if key == "cpi" and "core" in n:
                continue
            if key == "ppi" and "core" in n:
                continue
            if key == "pce" and "core" in n:
                continue
            return key
    # 退化：取前两个实词
    words = [w for w in n.split() if len(w) > 2][:2]
    return "_".join(words) if words else n


_FF_WEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FF_HTML_URL = "https://www.forexfactory.com/calendar?week=this"
_ff_cache: Dict[str, Any] = {"at": 0.0, "items": [], "source": None}


def _extract_js_array(text: str, key: str) -> Optional[str]:
    m = re.search(rf"{re.escape(key)}\s*:\s*\[", text)
    if not m:
        return None
    i = m.end() - 1
    depth = 0
    in_str = False
    esc = False
    for j, ch in enumerate(text[i:], i):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
    return None


def _ff_item(title: str, dt_et: datetime, impact: str = "") -> Dict[str, Any]:
    return {
        "title": title,
        "family": _eco_family_key(title),
        "dt_et": dt_et,
        "day": dt_et.date(),
        "impact": impact,
    }


def _parse_ff_json_list(raw: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return items
    for it in raw:
        if not isinstance(it, dict):
            continue
        if str(it.get("country") or "").upper() not in ("USD", "US"):
            continue
        title = str(it.get("title") or "").strip()
        ds = str(it.get("date") or "").strip()
        if not title or not ds:
            continue
        try:
            dt = datetime.fromisoformat(ds)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ET)
        else:
            dt = dt.astimezone(ET)
        items.append(_ff_item(title, dt, str(it.get("impact") or "")))
    return items


def _parse_ff_html(html: str) -> List[Dict[str, Any]]:
    """从 ForexFactory 页面嵌入的 days 数组解析 USD 事件。"""
    arr = _extract_js_array(html, "days")
    if not arr:
        return []
    try:
        days = json.loads(arr)
    except json.JSONDecodeError:
        return []
    items: List[Dict[str, Any]] = []
    if not isinstance(days, list):
        return items
    for day in days:
        if not isinstance(day, dict):
            continue
        day_dl = day.get("dateline")
        for ev in day.get("events") or []:
            if not isinstance(ev, dict):
                continue
            if str(ev.get("currency") or "").upper() != "USD":
                continue
            title = str(ev.get("name") or "").strip()
            if not title:
                continue
            dl = ev.get("dateline") or day_dl
            try:
                ts = int(dl)
            except (TypeError, ValueError):
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(ET)
            impact = str(ev.get("impactTitle") or ev.get("impact") or "")
            items.append(_ff_item(title, dt, impact))
    return items


def _load_ff_disk() -> List[Dict[str, Any]]:
    try:
        if not _FF_DISK.exists():
            return []
        data = json.loads(_FF_DISK.read_text(encoding="utf-8"))
        items: List[Dict[str, Any]] = []
        for it in data.get("items") or []:
            title = str(it.get("title") or "").strip()
            iso = str(it.get("dt_et") or "").strip()
            if not title or not iso:
                continue
            try:
                dt = datetime.fromisoformat(iso)
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ET)
            else:
                dt = dt.astimezone(ET)
            items.append(_ff_item(title, dt, str(it.get("impact") or "")))
        return items
    except Exception:
        return []


def _save_ff_disk(items: List[Dict[str, Any]], source: str, offset_days: Optional[int] = None) -> None:
    try:
        _FF_DISK.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "offset_days": offset_days,
            "items": [
                {
                    "title": it["title"],
                    "dt_et": it["dt_et"].isoformat(),
                    "impact": it.get("impact") or "",
                    "family": it.get("family") or "",
                }
                for it in items
            ],
        }
        _FF_DISK.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_ff_disk_offset() -> Optional[int]:
    try:
        if not _FF_DISK.exists():
            return None
        data = json.loads(_FF_DISK.read_text(encoding="utf-8"))
        off = data.get("offset_days")
        return int(off) if off is not None else None
    except Exception:
        return None


def _fetch_ff_usd_refs(force: bool = False) -> List[Dict[str, Any]]:
    """ForexFactory USD 日程（日期更准）；JSON → HTML → 内存/磁盘缓存。"""
    now = time.time()
    if not force and _ff_cache["items"] and now - _ff_cache["at"] < CACHE_TTL:
        return list(_ff_cache["items"])

    items: List[Dict[str, Any]] = []
    source = ""

    # 1) 公开 JSON（可能 429）
    try:
        resp = requests.get(
            _FF_WEEK_URL,
            headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
            proxies={"http": None, "https": None},
        )
        if resp.status_code == 200:
            items = _parse_ff_json_list(resp.json())
            if items:
                source = "ff_json"
    except Exception:
        pass

    # 2) 页面嵌入 days 数组（更稳）
    if not items:
        try:
            resp = requests.get(
                _FF_HTML_URL,
                headers={
                    "User-Agent": HEADERS["User-Agent"],
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.forexfactory.com/",
                },
                timeout=REQUEST_TIMEOUT,
                proxies={"http": None, "https": None},
            )
            if resp.status_code == 200:
                items = _parse_ff_html(resp.text)
                if items:
                    source = "ff_html"
        except Exception:
            pass

    if items:
        _ff_cache["at"] = now
        _ff_cache["items"] = items
        _ff_cache["source"] = source
        _save_ff_disk(items, source)
        return list(items)

    # 3) 回退：内存 → 磁盘
    if _ff_cache["items"]:
        return list(_ff_cache["items"])
    disk = _load_ff_disk()
    if disk:
        _ff_cache["at"] = now
        _ff_cache["items"] = disk
        _ff_cache["source"] = "disk"
        return list(disk)
    return []


def _median_int(vals: List[int]) -> Optional[int]:
    if not vals:
        return None
    xs = sorted(vals)
    return xs[len(xs) // 2]


def _clock_from_time_et(time_et: Any) -> Optional[Tuple[int, int]]:
    if not time_et or not isinstance(time_et, str) or ":" not in time_et:
        return None
    try:
        hh, mm = time_et.split(":")[:2]
        return int(hh), int(mm)
    except ValueError:
        return None


def _align_us_macro_events(
    events: List[Dict[str, Any]], *, force: bool = False
) -> Dict[str, Any]:
    """用 FF 锚点自适应校正 Nasdaq 美国宏观日期；推算全局偏移用于未匹配事件。"""
    refs = _fetch_ff_usd_refs(force=force)
    meta: Dict[str, Any] = {
        "ff_refs": len(refs),
        "ff_source": _ff_cache.get("source"),
        "matched": 0,
        "offset_days": None,
        "mode": "nasdaq",
    }
    if not events:
        return meta

    # 第一遍：能直接对上 FF 的，记下 Nasdaq 源日相对官方日的偏移（通常为 +1）
    offsets: List[int] = []
    match_by_id: Dict[int, Dict[str, Any]] = {}
    for ev in events:
        if ev.get("country_code") != "US":
            continue
        fam = _eco_family_key(str(ev.get("name") or ""))
        try:
            src_day = date.fromisoformat(str(ev.get("source_date") or ev.get("date")))
        except ValueError:
            continue
        cands = [
            r for r in refs if r["family"] == fam and abs((r["day"] - src_day).days) <= 3
        ]
        if not cands:
            cands = [r for r in refs if r["family"] == fam]
        if not cands:
            continue
        best = min(cands, key=lambda r: (abs((r["day"] - src_day).days), r["dt_et"]))
        offsets.append((src_day - best["day"]).days)
        match_by_id[id(ev)] = best

    offset = _median_int(offsets)
    if offset is None:
        # 本周未能匹配时，沿用上次成功推断的偏移（仍属自适应，非写死）
        offset = _load_ff_disk_offset()
        if offset is not None:
            meta["offset_from"] = "disk"

    meta["offset_days"] = offset
    meta["matched"] = len(match_by_id)
    if match_by_id:
        meta["mode"] = "ff+offset" if offset not in (None, 0) else "ff"
    elif offset not in (None, 0):
        meta["mode"] = "offset"

    if refs and offset is not None:
        _save_ff_disk(refs, str(_ff_cache.get("source") or "ff"), offset_days=offset)

    for ev in events:
        if ev.get("country_code") != "US":
            continue
        src = str(ev.get("source_date") or ev.get("date") or "")
        try:
            src_day = date.fromisoformat(src)
        except ValueError:
            continue

        best = match_by_id.get(id(ev))
        clock: Optional[Tuple[int, int]] = None
        if best is not None:
            event_day = best["day"]
            clock = (best["dt_et"].hour, best["dt_et"].minute)
            ev["date_align"] = "forexfactory"
        elif offset not in (None, 0):
            event_day = src_day - timedelta(days=int(offset))
            clock = _clock_from_time_et(ev.get("time_et"))
            ev["date_align"] = f"nasdaq_offset:{offset}"
        else:
            continue

        if not clock:
            continue

        tfields = _to_hkt_fields(event_day, clock[0], clock[1])
        ev["date"] = event_day.isoformat()
        ev["hour_label"] = tfields["time_hkt"]
        ev.update(tfields)
        ev["sort_key"] = (tfields["sort_ts"], -int(ev.get("score") or 0), ev.get("name") or "")

    return meta


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
        # 先按 Nasdaq 日历日解析；美国事件稍后用 FF 锚点自适应校正
        event_day = day
        clock = _parse_eco_clock(gmt)
        if clock:
            tfields = _to_hkt_fields(event_day, clock[0], clock[1])
            hour_label = tfields["time_hkt"]
        else:
            tfields = {
                "time_et": None,
                "time_hkt": "—",
                "time_hkt_short": "—",
                "datetime_hkt": None,
                "sort_ts": int(
                    datetime(
                        event_day.year, event_day.month, event_day.day, 12, 0, tzinfo=ET
                    ).timestamp()
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
                "date": event_day.isoformat(),
                "source_date": day.isoformat(),
                "consensus": _clean_html(r.get("consensus")),
                "previous": _clean_html(r.get("previous")),
                "actual": _clean_html(r.get("actual")),
                "score": score,
                "date_align": "nasdaq",
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


def _has_pending_actual(payload: Dict[str, Any], now_ts: Optional[float] = None) -> bool:
    """已过公布时间（留 2 分钟缓冲）但仍无 actual 的数据类宏观（有预期/前值）。"""
    now = now_ts if now_ts is not None else time.time()
    for col in payload.get("columns") or []:
        for ev in col.get("events") or []:
            if ev.get("type") != "economic":
                continue
            actual = str(ev.get("actual") or "").strip()
            if actual:
                continue
            # 演讲等无数字项的事件不会出 actual，不因此缩短缓存
            has_print = str(ev.get("consensus") or "").strip() or str(
                ev.get("previous") or ""
            ).strip()
            if not has_print:
                continue
            try:
                ts = int(ev.get("sort_ts") or 0)
            except (TypeError, ValueError):
                continue
            if ts and ts < now - 120:
                return True
    return False


def fetch_week_calendar(
    *,
    perps_pairs: Optional[Set[str]] = None,
    force: bool = False,
    days: Optional[List[date]] = None,
) -> Dict[str, Any]:
    now = time.time()
    if not force and _cache["payload"]:
        age = now - _cache["at"]
        pending = _has_pending_actual(_cache["payload"], now)
        ttl = CACHE_TTL_PENDING_ACTUAL if pending else CACHE_TTL
        if age < ttl:
            payload = _cache["payload"]
            if perps_pairs is not None:
                return _retag(payload, perps_pairs)
            return payload

    week = days or _week_days()
    perps = {p.upper() for p in (perps_pairs or set())}
    columns: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    # Nasdaq 美国宏观常挂在官方日次日：多拉周六，校准后再按官方日归桶
    eco_fetch_days = list(week) + [week[-1] + timedelta(days=1)]

    def one(day: date):
        earn, eco = [], []
        err = None
        try:
            if day in week:
                earn = _fetch_earnings_day(day)
        except Exception as e:
            err = f"earnings: {e}"
        try:
            eco = _fetch_economic_day(day)
        except Exception as e:
            err = (err + "; " if err else "") + f"economic: {e}"
        return day, earn, eco, err

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(one, d) for d in eco_fetch_days]
        results = [f.result() for f in as_completed(futs)]
    results.sort(key=lambda x: x[0])

    earn_by_day: Dict[str, List[Dict[str, Any]]] = {d.isoformat(): [] for d in week}
    eco_all: List[Dict[str, Any]] = []
    for day, earn, eco, err in results:
        if err:
            errors[day.isoformat()] = err
        if day in week:
            earn_by_day[day.isoformat()] = earn
        eco_all.extend(eco)

    align_meta = _align_us_macro_events(eco_all, force=force)

    # 宏观按校准后的日期归桶
    eco_by_day: Dict[str, List[Dict[str, Any]]] = {d.isoformat(): [] for d in week}
    for e in eco_all:
        key = str(e.get("date") or "")
        if key in eco_by_day:
            eco_by_day[key].append(e)

    for day in week:
        day_key = day.isoformat()
        earn = earn_by_day.get(day_key) or []
        eco = eco_by_day.get(day_key) or []
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
            key=lambda x: (
                int(x.get("sort_ts") or 0),
                0 if x.get("type") == "economic" else 1,
                x.get("symbol") or x.get("name") or "",
            ),
        )

        columns.append(
            {
                "date": day_key,
                "label": _day_label(day),
                "events": events,
                "counts": {
                    "earnings": len(earn_picked),
                    "economic": len(eco_picked),
                    "earnings_total": len(earn),
                },
            }
        )

    note = "展示为香港时间；财报 BMO≈美东08:00、AMC≈美东16:05"
    if align_meta.get("matched"):
        note = (
            "展示为香港时间；美国宏观日期对照 ForexFactory 自适应校准"
            f"（匹配 {align_meta['matched']} 条"
            + (
                f"，Nasdaq 相对偏移 {align_meta['offset_days']} 天"
                if align_meta.get("offset_days") not in (None, 0)
                else ""
            )
            + "）；财报 BMO≈美东08:00、AMC≈美东16:05"
        )
    elif align_meta.get("offset_days") not in (None, 0):
        note = (
            f"展示为香港时间；美国宏观按推断偏移 {align_meta['offset_days']} 天校准；"
            "财报 BMO≈美东08:00、AMC≈美东16:05"
        )

    payload = {
        "week_start": week[0].isoformat(),
        "week_end": week[-1].isoformat(),
        "timezone": "Asia/Hong_Kong",
        "timezone_note": note,
        "columns": columns,
        "errors": errors,
        "source": "nasdaq",
        "align": align_meta,
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
