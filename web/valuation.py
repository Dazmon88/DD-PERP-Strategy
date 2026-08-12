"""自建 Trailing P/E（TTM）日频序列：SEC 季度 EPS + 公开日线价格，本地 CSV 缓存。"""
from __future__ import annotations

import csv
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import SSLError as Urllib3SSLError
from urllib3.util.retry import Retry

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
TWELVE_URL = "https://api.twelvedata.com/time_series"
# SEC 要求带可联系信息的 UA，否则易被断开/限流
UA = "FundRateBot/0.1 (research; contact: fundrate-local@example.com)"
CACHE_TTL = 20 * 3600  # 20h
CACHE_VERSION = "v8-splits"
ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "valuation"

_ticker_map: Dict[str, Dict[str, Any]] = {}
_ticker_map_at = 0.0
_http: Optional[requests.Session] = None

RANGE_DAYS = {
    "1y": 365,
    "3y": 365 * 3,
    "5y": 365 * 5,
    "max": 365 * 20,
}


def _session() -> requests.Session:
    global _http
    if _http is not None:
        return _http
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json,text/csv,*/*",
            "Accept-Encoding": "gzip, deflate",
            # 避免复用被中间盒掐断的 keep-alive 连接触发 SSLEOF
            "Connection": "close",
        }
    )
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    _http = s
    return s


def _is_transient_http_error(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            Urllib3SSLError,
        ),
    ):
        return True
    msg = str(exc).lower()
    needles = (
        "ssleoferror",
        "unexpected_eof",
        "connection reset",
        "remotely closed",
        "timed out",
        "temporarily unavailable",
        "max retries exceeded",
    )
    return any(n in msg for n in needles)


def _sec_get(url: str, *, timeout: float = 60.0) -> requests.Response:
    """带退避的 SEC GET；消化偶发 SSL EOF / 连接重置。"""
    global _http
    last: Optional[BaseException] = None
    for attempt in range(5):
        try:
            resp = _session().get(url, timeout=timeout)
            # 429/5xx 也退避
            if resp.status_code in (429, 500, 502, 503, 504):
                raise requests.exceptions.HTTPError(
                    f"SEC HTTP {resp.status_code}", response=resp
                )
            resp.raise_for_status()
            return resp
        except Exception as e:
            last = e
            if not _is_transient_http_error(e) and not (
                isinstance(e, requests.exceptions.HTTPError)
                and getattr(e.response, "status_code", None) in (429, 500, 502, 503, 504)
            ):
                raise
            if attempt >= 4:
                break
            # 换新 session，丢掉可能坏掉的连接池
            _http = None
            time.sleep(0.7 * (2**attempt))
    assert last is not None
    raise last


def _ensure_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _cache_path(symbol: str) -> Path:
    return _ensure_cache_dir() / f"{symbol.upper()}-pe-ttm-{CACHE_VERSION}.csv"


def _load_ticker_map(force: bool = False) -> Dict[str, Dict[str, Any]]:
    global _ticker_map, _ticker_map_at
    now = time.time()
    if not force and _ticker_map and now - _ticker_map_at < CACHE_TTL:
        return _ticker_map
    resp = _sec_get(SEC_TICKERS_URL, timeout=30)
    raw = resp.json()
    out: Dict[str, Dict[str, Any]] = {}
    for item in raw.values() if isinstance(raw, dict) else raw:
        if not isinstance(item, dict):
            continue
        tick = str(item.get("ticker") or "").upper().strip()
        if not tick:
            continue
        cik = int(item.get("cik_str") or item.get("cik") or 0)
        if not cik:
            continue
        out[tick] = {
            "cik": cik,
            "title": str(item.get("title") or tick),
        }
    _ticker_map = out
    _ticker_map_at = now
    return out


def resolve_symbol(symbol: str) -> Dict[str, Any]:
    sym = symbol.upper().strip()
    info = _load_ticker_map().get(sym)
    if not info:
        raise ValueError(f"未在 SEC 公司列表找到代码：{sym}")
    return {"symbol": sym, **info}


# 美股市值前列（常见股），用于估值页搜索默认下拉；顺序可随市场更新
_TOP_BY_MARKET_CAP = (
    "NVDA",
    "MSFT",
    "AAPL",
    "GOOG",
    "AMZN",
    "META",
    "AVGO",
    "TSLA",
    "BRK-B",
    "JPM",
)


def list_top_tickers(limit: int = 10) -> List[Dict[str, Any]]:
    """返回市值前列标的（SEC 名称 enrichment）。"""
    m = _load_ticker_map()
    out: List[Dict[str, Any]] = []
    for sym in _TOP_BY_MARKET_CAP:
        info = m.get(sym)
        if not info:
            # 少数代码在 SEC 列表写法不同
            alt = m.get(sym.replace("-", ".")) or m.get(sym.replace(".", "-"))
            if not alt:
                continue
            info = alt
            sym = next(
                (k for k, v in m.items() if v.get("cik") == alt.get("cik") and k.startswith(sym[:3])),
                sym,
            )
        out.append(
            {
                "symbol": sym,
                "name": info.get("title") or sym,
                "cik": info.get("cik"),
                "group": "top_mktcap",
            }
        )
        if len(out) >= max(1, min(int(limit), 20)):
            break
    return out


def search_tickers(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    """按代码/公司名搜索 SEC 美股列表。"""
    q = (query or "").strip().upper()
    if not q:
        return list_top_tickers(limit=min(limit, 10))
    m = _load_ticker_map()
    top_rank = {s: i for i, s in enumerate(_TOP_BY_MARKET_CAP)}
    scored: List[Tuple[Tuple, Dict[str, Any]]] = []
    for sym, info in m.items():
        title = str(info.get("title") or "")
        title_u = title.upper()
        words = [w for w in title_u.replace(",", " ").replace(".", " ").split() if w]
        if sym == q:
            rank: Tuple = (0, 0, sym)
        elif sym in top_rank and (
            sym.startswith(q) or title_u.startswith(q) or any(w.startswith(q) for w in words)
        ):
            rank = (1, top_rank[sym], sym)
        elif sym.startswith(q):
            rank = (2, len(sym), sym)
        elif title_u.startswith(q) or any(w.startswith(q) for w in words):
            rank = (3, len(sym), sym)
        elif q in sym:
            rank = (4, len(sym), sym)
        elif q in title_u:
            rank = (5, len(title_u), sym)
        else:
            continue
        scored.append(
            (
                rank,
                {
                    "symbol": sym,
                    "name": title or sym,
                    "cik": info.get("cik"),
                    "group": "search",
                },
            )
        )
    scored.sort(key=lambda x: x[0])
    out: List[Dict[str, Any]] = []
    seen = set()
    for _, it in scored:
        if it["symbol"] in seen:
            continue
        seen.add(it["symbol"])
        out.append(it)
        if len(out) >= max(1, min(int(limit), 30)):
            break
    return out


def _fetch_sec_eps_points(cik: int) -> List[Dict[str, Any]]:
    url = SEC_FACTS_URL.format(cik=f"{int(cik):010d}")
    resp = _sec_get(url, timeout=60)
    data = resp.json()
    us = ((data.get("facts") or {}).get("us-gaap") or {})
    node = us.get("EarningsPerShareDiluted") or us.get("EarningsPerShareBasic")
    if not node:
        raise ValueError("SEC 无 EarningsPerShareDiluted / Basic")
    units = node.get("units") or {}
    arr = units.get("USD/shares") or next(iter(units.values()), [])
    return [x for x in arr if isinstance(x, dict)]


def _parse_day(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


_SPLIT_FACTORS = (2, 3, 4, 5, 7, 10, 20, 25, 40)


def _median(vals: List[float]) -> float:
    xs = sorted(vals)
    return xs[len(xs) // 2]


def _robust_ref(vals: List[float]) -> Optional[float]:
    xs = [abs(float(v)) for v in vals if abs(float(v)) > 1e-9]
    if len(xs) < 3:
        return _median(xs) if xs else None
    med = _median(xs)
    core = [v for v in xs if 0.45 * med <= v <= 2.2 * med]
    if len(core) >= 3:
        return _median(core)
    return med


def _nearest_split_factor(ratio: float) -> Optional[float]:
    if ratio < 1.5:
        return None
    best = min(_SPLIT_FACTORS, key=lambda f: abs(f - ratio))
    if abs(ratio - best) / best <= 0.14:
        return float(best)
    return None


def _collect_split_pair_hits(
    q_cands: Dict[date, List[Dict[str, Any]]],
) -> List[Tuple[date, float]]:
    """同一期末若同时存在拆股前/后重述值，记录 (季末, 因子)。"""
    hits: List[Tuple[date, float]] = []
    for end, cs in q_cands.items():
        vals = sorted({abs(float(c["val"])) for c in cs if abs(float(c["val"])) > 1e-9})
        if len(vals) < 2:
            continue
        fac = _nearest_split_factor(vals[-1] / vals[0])
        if fac:
            hits.append((end, fac))
    return hits


def _detect_split_events(
    q_cands: Dict[date, List[Dict[str, Any]]],
) -> List[Tuple[date, float]]:
    """自适应识别多次拆股：返回按时间排序的 [(cutoff, factor), ...]。

    cutoff = 该次拆股相关重述对的最后季末 + ~2 季；
    对 end<=cutoff 的财报，需再乘上该 factor 才能对齐到下一档口径。
    多次拆股时，历史季度的累计因子 = 之后所有 event.factor 的乘积。
    """
    hits = _collect_split_pair_hits(q_cands)
    if not hits:
        return []
    hits = sorted(hits)
    groups: List[List[Tuple[date, float]]] = [[hits[0]]]
    for h in hits[1:]:
        prev_end = groups[-1][-1][0]
        group_fac = _median([x[1] for x in groups[-1]])
        same_regime = abs(h[1] - group_fac) / max(group_fac, 1.0) <= 0.28
        if (h[0] - prev_end).days <= 750 and same_regime:
            groups[-1].append(h)
        else:
            groups.append([h])

    events: List[Tuple[date, float]] = []
    for g in groups:
        # 单次偶然比值噪声（尤其早期财报）不立事件
        if len(g) < 2:
            continue
        fac = float(min(_SPLIT_FACTORS, key=lambda f: abs(f - _median([x[1] for x in g]))))
        # 截止日落在「最后一对拆股前重述」之后约 1.5 个月，覆盖拆股日、
        # 又不吞掉拆股后首个已按新股本披露的季度（如 NVDA 2024-07）
        cutoff = max(e for e, _ in g) + timedelta(days=50)
        if events and events[-1][1] == fac and (cutoff - events[-1][0]).days < 400:
            events[-1] = (max(events[-1][0], cutoff), fac)
        else:
            events.append((cutoff, fac))
    return events


def _factor_to_current(end: Optional[date], events: List[Tuple[date, float]]) -> float:
    """把 end 当期口径换算到「最新拆股后」口径的累计除数。"""
    if not end or not events:
        return 1.0
    f = 1.0
    for cutoff, fac in events:
        if end <= cutoff:
            f *= float(fac)
    return f


def _detect_split_factor(q_cands: Dict[date, List[Dict[str, Any]]]) -> Optional[float]:
    """兼容旧接口：若只有一次拆股则返回该因子。"""
    events = _detect_split_events(q_cands)
    if not events:
        return None
    return events[-1][1]


def _detect_split_cutoff(
    q_cands: Dict[date, List[Dict[str, Any]]],
    split_factor: Optional[float],
) -> Optional[date]:
    """兼容旧接口：最后一次拆股过渡期截止日。"""
    events = _detect_split_events(q_cands)
    if not events:
        return None
    return events[-1][0]


def _has_split_pair(cands: List[Dict[str, Any]]) -> bool:
    vals = sorted({abs(float(c["val"])) for c in cands if abs(float(c["val"])) > 1e-9})
    if len(vals) < 2:
        return False
    return _nearest_split_factor(vals[-1] / vals[0]) is not None


def _scale_eps_to_current(
    val: float,
    end: Optional[date],
    events: List[Tuple[date, float]],
    ref: Optional[float],
    had_pair: bool = False,
) -> Tuple[float, Optional[float]]:
    """按拆股事件链把 EPS 对齐到最新口径；已是新口径则不重复除。"""
    F = _factor_to_current(end, events)
    if F <= 1.01:
        return val, None
    cand = val / F
    # 成对重述取到的是拆股前大值：直接按累计因子归一
    if had_pair:
        return cand, F
    if ref and ref > 0:
        # 无成对证据时：若已经像现行口径，且再除会被压得过小，则视为已重述
        if abs(val) <= 1.8 * ref and abs(cand) < 0.18 * ref:
            return val, None
        # 尝试事件链前缀，选更贴近现行 ref 的部分因子（防过度连乘）
        if abs(cand) > 1e-12 and not (0.04 * ref <= abs(cand) <= 8.0 * ref):
            partial = 1.0
            best_v, best_s, best_f = val, abs(abs(val) - ref), None
            for cutoff, fac in events:
                if end and end <= cutoff:
                    partial *= float(fac)
                    pv = val / partial
                    sc = abs(abs(pv) - ref)
                    if sc < best_s and 0.04 * ref <= abs(pv) <= 8.0 * ref:
                        best_v, best_s, best_f = pv, sc, partial
            return best_v, best_f
    return cand, F


def _pick_eps_candidate(
    cands: List[Dict[str, Any]],
    ref: Optional[float] = None,
    split_factor: Optional[float] = None,
    split_cutoff: Optional[date] = None,
    split_events: Optional[List[Tuple[date, float]]] = None,
) -> Dict[str, Any]:
    """同一期末多条 XBRL：取拆股前原始口径再按事件链归一到最新口径。"""
    events = split_events or []
    if not events and split_factor and split_cutoff:
        events = [(split_cutoff, float(split_factor))]

    # 存在成对重述时优先取较大值（拆股前原始），再统一 / 累计因子
    if _has_split_pair(cands):
        best = max(cands, key=lambda c: (abs(float(c["val"])), c["filed"]))
    else:

        def score(it: Dict[str, Any]) -> Tuple:
            v = abs(float(it["val"]))
            scale_fit = 0.0
            if ref and ref > 0:
                F = _factor_to_current(it.get("end"), events)
                adj = v / F if F > 1.01 else v
                ratio = adj / ref
                scale_fit = -abs(ratio - 1.0) if ratio <= 8 else -ratio
            return (
                scale_fit,
                1 if it.get("frame") else 0,
                it["filed"],
                -v,
            )

        best = sorted(cands, key=score, reverse=True)[0]

    out = dict(best)
    scaled, used_f = _scale_eps_to_current(
        float(best["val"]), best.get("end"), events, ref, had_pair=_has_split_pair(cands)
    )
    if used_f and scaled != float(best["val"]):
        out["raw_val"] = best["val"]
        out["val"] = scaled
        out["split_factor"] = used_f
    return out


def _estimate_eps_ref(quarters: List[Dict[str, Any]]) -> Optional[float]:
    if not quarters:
        return None
    ordered = sorted(quarters, key=lambda z: z["end"])
    window = ordered[-10:-2] if len(ordered) >= 10 else ordered[-8:]
    vals = [float(q["val"]) for q in window]
    return _robust_ref(vals)


def _normalize_split_scale(
    quarters: List[Dict[str, Any]],
    split_factor: Optional[float] = None,
    split_cutoff: Optional[date] = None,
    split_events: Optional[List[Tuple[date, float]]] = None,
) -> List[Dict[str, Any]]:
    """把历史 EPS 对齐到与近期（已复权）口径一致；支持多次拆股事件链。"""
    if len(quarters) < 4:
        return quarters
    ordered = sorted(quarters, key=lambda z: z["end"])
    ref = _estimate_eps_ref(ordered)
    if not ref or ref <= 0:
        return ordered

    events = list(split_events or [])
    if not events and split_factor and split_cutoff:
        events = [(split_cutoff, float(split_factor))]

    threshold = 2.5 * ref
    if events:
        threshold = max(2.2 * ref, 0.12 * max(f for _, f in events))

    out: List[Dict[str, Any]] = []
    for q in ordered:
        # pick 阶段已按事件链缩放过的，避免二次连除
        if q.get("split_factor"):
            out.append(dict(q))
            continue
        v = float(q["val"])
        best = v
        used_f: Optional[float] = None
        if events:
            scaled, used_f = _scale_eps_to_current(v, q.get("end"), events, ref)
            if used_f:
                best = scaled
        elif abs(v) > threshold:
            ratio = abs(v) / ref
            nearest = min(_SPLIT_FACTORS, key=lambda f: abs(f - ratio))
            candidates = [float(nearest)]
            for f in _SPLIT_FACTORS:
                if float(f) not in candidates:
                    candidates.append(float(f))
            best_score = abs(abs(v) - ref)
            for f in candidates:
                cand = v / f
                if not (0.15 * ref <= abs(cand) <= 4.5 * ref):
                    continue
                score = abs(abs(cand) - ref)
                if score < best_score:
                    best, best_score, used_f = cand, score, float(f)
        item = dict(q)
        if best != v:
            item["val"] = best
            item["raw_val"] = v
            item["split_factor"] = used_f or (round(v / best, 4) if best else None)
        out.append(item)
    return out


def build_quarterly_eps(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """抽取单季 EPS（约 90 天窗口），并用年报推导 Q4；自适应处理拆股重述口径。"""
    q_cands: Dict[date, List[Dict[str, Any]]] = {}
    a_cands: Dict[date, List[Dict[str, Any]]] = {}

    for x in raw:
        start = _parse_day(x.get("start"))
        end = _parse_day(x.get("end"))
        filed = _parse_day(x.get("filed")) or end
        val = x.get("val")
        if start is None or end is None or val is None or filed is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        days = (end - start).days
        item = {
            "start": start,
            "end": end,
            "filed": filed,
            "val": num,
            "frame": x.get("frame"),
            "form": x.get("form"),
        }
        if 80 <= days <= 100:
            q_cands.setdefault(end, []).append(item)
        elif 350 <= days <= 380:
            a_cands.setdefault(end, []).append(item)

    split_events = _detect_split_events(q_cands)
    split_factor = split_events[-1][1] if split_events else None
    split_cutoff = split_events[-1][0] if split_events else None

    probe = []
    for cs in q_cands.values():
        framed = [c for c in cs if c.get("frame")]
        probe.extend(framed or cs)
    ref = _robust_ref([float(c["val"]) for c in probe if abs(float(c["val"])) < 8])
    if ref is None:
        ref = _estimate_eps_ref(probe)

    quarterly = {
        end: _pick_eps_candidate(cs, ref, split_factor, split_cutoff, split_events)
        for end, cs in q_cands.items()
    }
    annual = {
        end: _pick_eps_candidate(
            cs, (ref * 4 if ref else None), split_factor, split_cutoff, split_events
        )
        for end, cs in a_cands.items()
    }
    for end, cs in q_cands.items():
        q = quarterly[end]
        first = min(cs, key=lambda c: c["filed"])
        if first["filed"] <= end + timedelta(days=100):
            q["filed"] = first["filed"]
    for end, cs in a_cands.items():
        a = annual[end]
        first = min(cs, key=lambda c: c["filed"])
        if first["filed"] <= end + timedelta(days=100):
            a["filed"] = first["filed"]

    q_list = _normalize_split_scale(
        list(quarterly.values()), split_factor, split_cutoff, split_events
    )
    quarterly = {q["end"]: q for q in q_list}
    a_list = _normalize_split_scale(
        list(annual.values()), split_factor, split_cutoff, split_events
    )
    annual = {a["end"]: a for a in a_list}

    for ann in sorted(annual.values(), key=lambda z: z["end"]):
        if not ann.get("frame"):
            continue
        qs = sorted(
            [q for q in quarterly.values() if ann["start"] < q["end"] <= ann["end"]],
            key=lambda z: z["end"],
        )
        if len(qs) < 3:
            continue
        three = qs[-3:]
        if any(q["end"] == ann["end"] for q in three):
            continue
        vals = [abs(float(q["val"])) for q in three]
        med = _median(vals)
        if med > 0 and (max(vals) > 3.5 * med or min(vals) < 0.25 * med):
            continue
        q4_val = float(ann["val"]) - sum(float(q["val"]) for q in three)
        if med > 0 and (q4_val <= 0 or abs(q4_val) > 3.5 * med):
            continue
        end = ann["end"]
        if end in quarterly:
            continue
        quarterly[end] = {
            "start": three[-1]["end"],
            "end": end,
            "filed": ann["filed"],
            "val": q4_val,
            "frame": "derived-Q4",
            "form": ann.get("form"),
        }

    return _normalize_split_scale(
        sorted(quarterly.values(), key=lambda z: z["end"]),
        split_factor,
        split_cutoff,
        split_events,
    )


def _twelvedata_key() -> str:
    env = (os.environ.get("TWELVEDATA_API_KEY") or "").strip()
    if env:
        return env
    # 可选本地配置：.generated/twelvedata.json → {"api_key":"..."}
    cfg = ROOT / ".generated" / "twelvedata.json"
    if cfg.exists():
        try:
            import json

            data = json.loads(cfg.read_text(encoding="utf-8"))
            key = str((data or {}).get("api_key") or "").strip()
            if key:
                return key
        except Exception:
            pass
    return ""


def _fetch_prices_yfinance(symbol: str, start: date) -> List[Tuple[date, float]]:
    import yfinance as yf

    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            t = yf.Ticker(symbol)
            hist = t.history(start=start.isoformat(), auto_adjust=True, actions=False)
            if hist is None or hist.empty:
                return []
            out: List[Tuple[date, float]] = []
            for idx, row in hist.iterrows():
                try:
                    d = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
                    px = float(row["Close"])
                except Exception:
                    continue
                if px > 0:
                    out.append((d, px))
            return out
        except Exception as e:
            last_err = e
            time.sleep(1.2 * (attempt + 1))
    if last_err:
        raise last_err
    return []


def _fetch_prices_twelvedata(symbol: str, start: date) -> List[Tuple[date, float]]:
    key = _twelvedata_key()
    # demo 仅可靠支持 AAPL；有 key 则通用
    if not key:
        if symbol.upper() != "AAPL":
            return []
        key = "demo"
    params = {
        "symbol": symbol.upper(),
        "interval": "1day",
        "outputsize": 5000,
        "apikey": key,
        "start_date": start.isoformat(),
    }
    resp = _session().get(TWELVE_URL, params=params, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    values = data.get("values") or []
    if not values:
        return []
    out: List[Tuple[date, float]] = []
    for row in values:
        d = _parse_day(row.get("datetime"))
        try:
            px = float(row.get("close"))
        except (TypeError, ValueError):
            continue
        if d and px > 0:
            out.append((d, px))
    out.sort(key=lambda z: z[0])
    return out


def fetch_daily_closes(symbol: str, start: date) -> Tuple[List[Tuple[date, float]], str]:
    errors: List[str] = []
    try:
        rows = _fetch_prices_yfinance(symbol, start)
        if rows:
            return rows, "yfinance"
    except Exception as e:
        errors.append(f"yfinance: {e}")
    try:
        rows = _fetch_prices_twelvedata(symbol, start)
        if rows:
            src = "twelvedata" if _twelvedata_key() else "twelvedata-demo"
            return rows, src
    except Exception as e:
        errors.append(f"twelvedata: {e}")
    detail = " | ".join(errors) if errors else "无数据"
    hint = (
        "；可免费申请 Twelve Data key 并设置环境变量 TWELVEDATA_API_KEY"
        "，或写入 .generated/twelvedata.json 的 api_key 字段"
    )
    raise RuntimeError("日线价格获取失败：" + detail + hint)


def _eps_available_on(q: Dict[str, Any]) -> date:
    """EPS 进入 TTM 的日期：优先用及时披露的 filed；多年后重述则回退季末+40天。"""
    end = q["end"]
    filed = q.get("filed") or end
    if isinstance(filed, str):
        filed = _parse_day(filed) or end
    # 正常 10-Q/10-K 通常在季末后 ~30–60 天披露；此时按披露日更新 PE（与市面一致）
    if end < filed <= end + timedelta(days=100):
        return filed
    # 拆股重述等远期 filed 会把历史点拖到错误年份，改用季末近似可得日
    return end + timedelta(days=40)


def build_pe_series(
    prices: List[Tuple[date, float]],
    quarters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not prices or not quarters:
        return []
    enriched = [{**q, "available": _eps_available_on(q)} for q in quarters]
    q_sorted = sorted(enriched, key=lambda z: z["available"])
    out: List[Dict[str, Any]] = []
    q_i = 0
    available: List[Dict[str, Any]] = []

    for d, close in prices:
        while q_i < len(q_sorted) and q_sorted[q_i]["available"] <= d:
            available.append(q_sorted[q_i])
            q_i += 1
        if len(available) < 4:
            continue
        last4 = available[-4:]
        eps_ttm = sum(float(q["val"]) for q in last4)
        pe = None
        if eps_ttm > 0:
            pe = close / eps_ttm
            # 过滤明显未洗净的异常点（拆股残留）；放宽上限以覆盖 TSLA 等高估值标的
            if pe < 3 or pe > 500:
                pe = None
        out.append(
            {
                "date": d.isoformat(),
                "close": round(close, 6),
                "eps_ttm": round(eps_ttm, 6),
                "pe": None if pe is None else round(pe, 4),
            }
        )
    return out


def _write_cache(symbol: str, rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> None:
    path = _cache_path(symbol)
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# symbol={meta.get('symbol')}\n")
        f.write(f"# name={meta.get('name')}\n")
        f.write(f"# cik={meta.get('cik')}\n")
        f.write(f"# price_source={meta.get('price_source')}\n")
        f.write(f"# built_at={meta.get('built_at')}\n")
        w = csv.DictWriter(f, fieldnames=["date", "close", "eps_ttm", "pe"])
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "date": r["date"],
                    "close": r["close"],
                    "eps_ttm": r["eps_ttm"],
                    "pe": "" if r["pe"] is None else r["pe"],
                }
            )


def _read_cache(symbol: str) -> Optional[Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    path = _cache_path(symbol)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > CACHE_TTL:
        return None
    meta: Dict[str, Any] = {"symbol": symbol.upper(), "cached": True}
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                if "=" in line:
                    k, v = line[1:].strip().split("=", 1)
                    meta[k.strip()] = v.strip()
                continue
            break
        f.seek(0)
        # skip comments for DictReader
        content = [ln for ln in f if not ln.startswith("#")]
    from io import StringIO

    r = csv.DictReader(StringIO("".join(content)))
    for row in r:
        pe_raw = row.get("pe")
        pe = None if pe_raw in (None, "") else float(pe_raw)
        rows.append(
            {
                "date": row["date"],
                "close": float(row["close"]),
                "eps_ttm": float(row["eps_ttm"]),
                "pe": pe,
            }
        )
    if not rows:
        return None
    return rows, meta


def _percentile(sorted_vals: List[float], p: float) -> float:
    """p in [0,1]，线性插值分位。"""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    p = min(1.0, max(0.0, p))
    idx = (len(sorted_vals) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    w = idx - lo
    return float(sorted_vals[lo]) * (1 - w) + float(sorted_vals[hi]) * w


def _zone_for_pe(pe: float, bands: Dict[str, float]) -> Dict[str, Any]:
    """按历史分位：极度低估 / 低估 / 中性 / 高估 / 极度高估。"""
    p10, p30, p70, p90 = bands["p10"], bands["p30"], bands["p70"], bands["p90"]
    if pe < p10:
        return {
            "key": "extreme_undervalued",
            "id": "extreme_undervalued",
            "label": "极度低估",
            "tone": "deep-green",
            "color": "#22c55e",
        }
    if pe < p30:
        return {
            "key": "undervalued",
            "id": "undervalued",
            "label": "低估",
            "tone": "green",
            "color": "#86efac",
        }
    if pe <= p70:
        return {
            "key": "neutral",
            "id": "neutral",
            "label": "中性",
            "tone": "gray",
            "color": "#93c5fd",
        }
    if pe <= p90:
        return {
            "key": "overvalued",
            "id": "overvalued",
            "label": "高估",
            "tone": "orange",
            "color": "#fbbf24",
        }
    return {
        "key": "extreme_overvalued",
        "id": "extreme_overvalued",
        "label": "极度高估",
        "tone": "red",
        "color": "#ef4444",
    }


def _stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    pes = [float(r["pe"]) for r in rows if r.get("pe") is not None]
    empty = {
        "latest_pe": None,
        "mean_pe": None,
        "median_pe": None,
        "min_pe": None,
        "max_pe": None,
        "percentile": None,
        "points": 0,
        "bands": None,
        "zone": None,
        "zone_method": "percentile_10_30_70_90",
    }
    if not pes:
        return empty
    pes_sorted = sorted(pes)
    latest = pes[-1]
    mean = sum(pes) / len(pes)
    mid = pes_sorted[len(pes_sorted) // 2]
    below = sum(1 for x in pes if x <= latest)
    pct = below / len(pes)
    bands = {
        "p10": round(_percentile(pes_sorted, 0.10), 4),
        "p30": round(_percentile(pes_sorted, 0.30), 4),
        "p50": round(_percentile(pes_sorted, 0.50), 4),
        "p70": round(_percentile(pes_sorted, 0.70), 4),
        "p90": round(_percentile(pes_sorted, 0.90), 4),
    }
    zone = _zone_for_pe(latest, bands)
    zones = [
        {
            "key": "extreme_undervalued",
            "label": "极度低估",
            "pe_min": round(pes_sorted[0], 4),
            "pe_max": bands["p10"],
            "pct_min": 0,
            "pct_max": 10,
            "color": "#22c55e",
        },
        {
            "key": "undervalued",
            "label": "低估",
            "pe_min": bands["p10"],
            "pe_max": bands["p30"],
            "pct_min": 10,
            "pct_max": 30,
            "color": "#86efac",
        },
        {
            "key": "neutral",
            "label": "中性",
            "pe_min": bands["p30"],
            "pe_max": bands["p70"],
            "pct_min": 30,
            "pct_max": 70,
            "color": "#93c5fd",
        },
        {
            "key": "overvalued",
            "label": "高估",
            "pe_min": bands["p70"],
            "pe_max": bands["p90"],
            "pct_min": 70,
            "pct_max": 90,
            "color": "#fbbf24",
        },
        {
            "key": "extreme_overvalued",
            "label": "极度高估",
            "pe_min": bands["p90"],
            "pe_max": round(pes_sorted[-1], 4),
            "pct_min": 90,
            "pct_max": 100,
            "color": "#ef4444",
        },
    ]
    return {
        "latest_pe": round(latest, 4),
        "mean_pe": round(mean, 4),
        "median_pe": round(mid, 4),
        "min_pe": round(pes_sorted[0], 4),
        "max_pe": round(pes_sorted[-1], 4),
        "percentile": round(pct, 4),
        "points": len(pes),
        "bands": bands,
        "zone": zone,
        "zones": zones,
        "zone_method": "percentile_10_30_70_90",
        "zone_note": "基于所选区间历史 Trailing P/E 分位：<10% 极度低估，10–30% 低估，30–70% 中性，70–90% 高估，>90% 极度高估",
        "zone_guide": [
            {"id": "extreme_undervalued", "label": "极度低估", "rule": "< P10", "pe_lt": bands["p10"]},
            {"id": "undervalued", "label": "低估", "rule": "P10–P30", "pe_gte": bands["p10"], "pe_lt": bands["p30"]},
            {"id": "neutral", "label": "中性", "rule": "P30–P70", "pe_gte": bands["p30"], "pe_lte": bands["p70"]},
            {"id": "overvalued", "label": "高估", "rule": "P70–P90", "pe_gt": bands["p70"], "pe_lte": bands["p90"]},
            {"id": "extreme_overvalued", "label": "极度高估", "rule": "> P90", "pe_gt": bands["p90"]},
        ],
    }


def fetch_trailing_pe(
    symbol: str,
    *,
    range_key: str = "5y",
    force: bool = False,
) -> Dict[str, Any]:
    sym = symbol.upper().strip()
    if not sym:
        raise ValueError("symbol 不能为空")
    range_key = (range_key or "5y").lower()
    if range_key not in RANGE_DAYS:
        range_key = "5y"

    cached = None if force else _read_cache(sym)
    if cached:
        rows, meta = cached
    else:
        info = resolve_symbol(sym)
        # 多取一段历史以便凑满 4 季 EPS
        start = date.today() - timedelta(days=RANGE_DAYS["max"] + 400)
        raw_eps = _fetch_sec_eps_points(int(info["cik"]))
        quarters = build_quarterly_eps(raw_eps)
        if len(quarters) < 4:
            raise ValueError(f"{sym} 季度 EPS 不足 4 期，无法计算 TTM PE")
        prices, price_source = fetch_daily_closes(sym, start)
        rows = build_pe_series(prices, quarters)
        if not rows:
            raise ValueError(f"{sym} 未能生成 PE 序列（价格或 EPS 对齐失败）")
        meta = {
            "symbol": sym,
            "name": info["title"],
            "cik": info["cik"],
            "price_source": price_source,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }
        _write_cache(sym, rows, meta)

    # 按 range 截取
    if range_key != "max":
        cut = date.today() - timedelta(days=RANGE_DAYS[range_key])
        rows = [r for r in rows if date.fromisoformat(r["date"]) >= cut]

    stats = _stats(rows)
    latest = rows[-1] if rows else None
    pe_points = sum(1 for r in rows if r.get("pe") is not None)
    latest_eps = None if not latest else latest.get("eps_ttm")
    loss_making = pe_points == 0 and latest_eps is not None and float(latest_eps) <= 0
    empty_reason = None
    if pe_points == 0:
        if loss_making:
            empty_reason = (
                f"近四季 TTM EPS 为 {latest_eps}（亏损），Trailing P/E 无意义；已展示股价曲线供参考"
            )
        else:
            empty_reason = "区间内无有效 Trailing P/E 点"
    return {
        "symbol": meta.get("symbol") or sym,
        "name": meta.get("name") or sym,
        "cik": meta.get("cik"),
        "metric": "trailing_pe_ttm",
        "metric_label": "Trailing P/E (TTM)",
        "note": "自建：日收盘价 ÷ 近四季已披露稀释 EPS（SEC）；非 Bloomberg BEst / Forward P/E",
        "range": range_key,
        "price_source": meta.get("price_source"),
        "cached": bool(meta.get("cached")),
        "built_at": meta.get("built_at"),
        "stats": stats,
        "latest": latest,
        "pe_points": pe_points,
        "loss_making": loss_making,
        "empty_reason": empty_reason,
        "series": [
            {
                "t": r["date"],
                "pe": r["pe"],
                "close": r["close"],
                "eps_ttm": r["eps_ttm"],
            }
            for r in rows
        ],
    }
