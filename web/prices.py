"""多所收盘价/中间价时间序列（折线图用）。"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import requests

from normalize import PAIR_ALIASES, canonical_base

ONDO_URL = "https://api.ondoperps.xyz"
ARCUS_URL = "https://api.arcus.xyz"
STANDX_URL = "https://perps.standx.com"
HYPE_URL = "https://api.hyperliquid.xyz/info"
LIGHTER_URL = "https://mainnet.zklighter.elliot.ai"

DEFAULT_EXCHANGES = ["ondo", "arcus", "standx", "hype", "lighter"]

REQUEST_TIMEOUT = 12.0
LIVE_TIMEOUT = 5.0  # 实时轮询要快，避免 WSS 首帧卡在慢所（如 Lighter）

# 图表默认颜色（前端也会用）
EXCHANGE_COLORS = {
    "ondo": "#1ce783",
    "arcus": "#5b8cff",
    "hype": "#f0c14a",
    "lighter": "#ff7ab8",
    "standx": "#9b8cff",
}


def _session_get(url: str, **kwargs) -> Any:
    kw = {
        "timeout": REQUEST_TIMEOUT,
        "headers": {"Accept": "application/json"},
        "proxies": {"http": None, "https": None},
    }
    kw.update(kwargs)
    resp = requests.get(url, **kw)
    resp.raise_for_status()
    return resp.json()


def _session_post(url: str, body: dict, **kwargs) -> Any:
    kw = {
        "timeout": REQUEST_TIMEOUT,
        "headers": {"Accept": "application/json", "Content-Type": "application/json"},
        "proxies": {"http": None, "https": None},
    }
    kw.update(kwargs)
    resp = requests.post(url, json=body, **kw)
    resp.raise_for_status()
    return resp.json()


# Arcus 无原油/贵金属现货永续，资金费率矩阵把这些 ETF 归到同一 pair
ARCUS_PROXY = {
    "WTI": "USO",  # United States Oil Fund
    "XAU": "GLD",
    "XAG": "SLV",
}


def pair_symbols(pair: str) -> Dict[str, str]:
    """统一 pair → 各所符号。"""
    p = canonical_base(pair)
    # 反向别名：XAU 在 hype 是 GOLD
    rev = {v: k for k, v in PAIR_ALIASES.items()}
    hype_ticker = rev.get(p, p)
    if p == "XAU":
        hype_ticker = "GOLD"
    elif p == "XAG":
        hype_ticker = "SILVER"
    elif p == "WTI":
        hype_ticker = "CL"
    elif p == "BRENT":
        hype_ticker = "BRENTOIL"
    # StandX：WTI 用 CL-USD
    standx_base = "CL" if p == "WTI" else p
    arcus_base = ARCUS_PROXY.get(p, p)
    lighter_sym = "BRENTOIL" if p == "BRENT" else p
    return {
        "ondo_history": f"{p}USD.P",
        "ondo_market": f"{p}-USD.P",
        "arcus": f"{arcus_base}-USD",
        "hype": f"xyz:{hype_ticker}",
        "hype_main": hype_ticker,  # 主簿加密币
        "lighter": lighter_sym,
        "standx": f"{standx_base}-USD",
    }


def _points_from_ohlc(rows: List[Tuple[int, float]]) -> List[Dict[str, Any]]:
    """[(time_sec, close), ...] → TV line series points."""
    out = []
    for t, c in rows:
        if c is None:
            continue
        out.append({"time": int(t), "value": float(c)})
    out.sort(key=lambda x: x["time"])
    return out


def fetch_ondo_history(pair: str, interval: str, hours: float) -> List[Dict[str, Any]]:
    syms = pair_symbols(pair)
    res_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240"}
    resolution = res_map.get(interval, "5")
    now = int(time.time())
    fr = now - int(hours * 3600)
    data = _session_get(
        f"{ONDO_URL}/v1/perps/history",
        params={"symbol": syms["ondo_history"], "resolution": resolution, "from": fr, "to": now},
    )
    # TradingView UDF: {s,t,o,h,l,c,v} 或包在 result
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    if not isinstance(data, dict) or data.get("s") not in ("ok", None):
        if isinstance(data, dict) and data.get("s") == "no_data":
            return []
    ts = data.get("t") or []
    closes = data.get("c") or []
    rows = []
    for t, c in zip(ts, closes):
        try:
            rows.append((int(t), float(c)))
        except (TypeError, ValueError):
            continue
    return _points_from_ohlc(rows)


def fetch_arcus_history(pair: str, interval: str, hours: float) -> List[Dict[str, Any]]:
    syms = pair_symbols(pair)
    now = int(time.time())
    fr = now - int(hours * 3600)
    # Arcus openTime 为微秒；未知市场返回 400，软失败为空
    try:
        data = _session_get(
            f"{ARCUS_URL}/v1/candles",
            params={
                "market": syms["arcus"],
                "timeframe": interval,
                "from": fr * 1_000_000,
                "to": now * 1_000_000,
            },
        )
    except Exception:
        return []
    candles = []
    if isinstance(data, dict):
        candles = data.get("candles") or data.get("data") or []
    elif isinstance(data, list):
        candles = data
    rows = []
    for c in candles:
        if not isinstance(c, dict):
            continue
        ot = c.get("openTime") or c.get("t")
        close = c.get("close") or c.get("c")
        if ot is None or close in (None, ""):
            continue
        ot = int(ot)
        if ot > 10_000_000_000_000:  # µs
            t_sec = ot // 1_000_000
        elif ot > 10_000_000_000:  # ms
            t_sec = ot // 1000
        else:
            t_sec = ot
        rows.append((t_sec, float(close)))
    return _points_from_ohlc(rows)


def fetch_hype_history(pair: str, interval: str, hours: float) -> List[Dict[str, Any]]:
    syms = pair_symbols(pair)
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(hours * 3600 * 1000)
    # 先试 HIP-3 xyz，再试主簿
    for coin in (syms["hype"], syms["hype_main"]):
        try:
            data = _session_post(
                HYPE_URL,
                {
                    "type": "candleSnapshot",
                    "req": {
                        "coin": coin,
                        "interval": interval,
                        "startTime": start_ms,
                        "endTime": now_ms,
                    },
                },
            )
        except Exception:
            continue
        if not isinstance(data, list) or not data:
            continue
        rows = []
        for c in data:
            if not isinstance(c, dict):
                continue
            ts = c.get("t") or c.get("T")
            close = c.get("c") or c.get("close")
            if ts is None or close in (None, ""):
                continue
            rows.append((int(ts) // 1000, float(close)))
        if rows:
            return _points_from_ohlc(rows)
    return []


def _lighter_market_id(symbol: str) -> Optional[int]:
    try:
        data = _session_get(f"{LIGHTER_URL}/api/v1/orderBooks")
    except Exception:
        return None
    books = data.get("order_books") or data.get("order_book_details") or []
    want = symbol.upper()
    for b in books:
        if str(b.get("symbol") or "").upper() == want and str(b.get("market_type") or "perp").lower() == "perp":
            try:
                return int(b["market_id"])
            except Exception:
                return None
    return None


def _interval_seconds(interval: str) -> int:
    return {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}.get(interval, 300)


def _lighter_mark_row(symbol: str) -> Optional[Tuple[int, float]]:
    try:
        data = _session_get(f"{LIGHTER_URL}/api/v1/orderBookDetails", timeout=LIVE_TIMEOUT)
    except Exception:
        return None
    want = symbol.upper()
    for d in data.get("order_book_details") or []:
        if str(d.get("symbol") or "").upper() != want:
            continue
        for k in ("mark_price", "last_trade_price", "index_price"):
            if d.get(k) not in (None, ""):
                return int(time.time()), float(d[k])
    return None


def _lighter_history_from_trades(market_id: int, interval: str) -> List[Tuple[int, float]]:
    """candlesticks 常 403：用 recentTrades 聚合成最近一段时间收盘点。"""
    try:
        data = _session_get(
            f"{LIGHTER_URL}/api/v1/recentTrades",
            params={"market_id": market_id, "limit": 100},
            timeout=LIVE_TIMEOUT,
        )
    except Exception:
        return []
    trades = data.get("trades") if isinstance(data, dict) else None
    if not isinstance(trades, list) or not trades:
        return []
    bucket = _interval_seconds(interval)
    # timestamp ms → 桶内最后一笔价
    by_bucket: Dict[int, float] = {}
    for t in trades:
        if not isinstance(t, dict):
            continue
        ts = t.get("timestamp") or t.get("transaction_time")
        px = t.get("price")
        if ts is None or px in (None, ""):
            continue
        ts = int(ts)
        if ts > 10_000_000_000_000:  # µs
            ts //= 1_000_000
        elif ts > 10_000_000_000:  # ms
            ts //= 1000
        b = (ts // bucket) * bucket
        by_bucket[b] = float(px)
    return sorted(by_bucket.items())


def fetch_lighter_history(pair: str, interval: str, hours: float) -> List[Dict[str, Any]]:
    syms = pair_symbols(pair)
    mid = _lighter_market_id(syms["lighter"])
    if mid is None:
        # 仍尝试用 mark 点，避免图上整列空白
        mark = _lighter_mark_row(syms["lighter"])
        return _points_from_ohlc([mark] if mark else [])
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(hours * 3600 * 1000)
    rows: List[Tuple[int, float]] = []
    try:
        data = _session_get(
            f"{LIGHTER_URL}/api/v1/candlesticks",
            params={
                "market_id": mid,
                "resolution": interval,
                "start_timestamp": start_ms,
                "end_timestamp": now_ms,
                "count_back": 500,
            },
            timeout=12.0,
        )
        candles = []
        if isinstance(data, dict):
            candles = data.get("candlesticks") or data.get("cands") or data.get("data") or []
        for c in candles:
            if not isinstance(c, dict):
                continue
            ts = c.get("timestamp") or c.get("t") or c.get("time")
            close = c.get("close") or c.get("c")
            if ts is None or close in (None, ""):
                continue
            ts = int(ts)
            if ts > 10_000_000_000:
                ts = ts // 1000
            rows.append((ts, float(close)))
    except Exception:
        rows = []

    if not rows:
        rows = _lighter_history_from_trades(mid, interval)
    mark = _lighter_mark_row(syms["lighter"])
    if mark:
        if not rows or rows[-1][0] < mark[0]:
            rows.append(mark)
        else:
            rows[-1] = (rows[-1][0], mark[1])
    return _points_from_ohlc(rows)


def fetch_standx_history(pair: str, interval: str, hours: float) -> List[Dict[str, Any]]:
    """StandX UDF K 线：/api/kline/history resolution=1|5|15|60…，from/to 为秒。"""
    syms = pair_symbols(pair)
    res_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240"}
    resolution = res_map.get(interval, "5")
    now = int(time.time())
    fr = now - int(hours * 3600)
    # 不带 countback 时接口只回最近几根；小写 countback 才能拉满区间
    countback = max(100, min(2000, int(hours * 60 / max(1, int(resolution))) + 10))
    data = _session_get(
        f"{STANDX_URL}/api/kline/history",
        params={
            "symbol": syms["standx"],
            "resolution": resolution,
            "from": fr,
            "to": now,
            "countback": countback,
        },
    )
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    if not isinstance(data, dict):
        return []
    if data.get("s") == "no_data":
        return []
    ts = data.get("t") or []
    closes = data.get("c") or []
    rows = []
    for t, c in zip(ts, closes):
        try:
            rows.append((int(t), float(c)))
        except (TypeError, ValueError):
            continue
    return _points_from_ohlc(rows)


HISTORY_FETCHERS = {
    "ondo": fetch_ondo_history,
    "arcus": fetch_arcus_history,
    "standx": fetch_standx_history,
    "hype": fetch_hype_history,
    "lighter": fetch_lighter_history,
}


def fetch_multi_history(
    pair: str,
    *,
    exchanges: Optional[List[str]] = None,
    interval: str = "5m",
    hours: float = 24.0,
) -> Dict[str, Any]:
    wanted = exchanges or list(DEFAULT_EXCHANGES)
    series: Dict[str, List[Dict[str, Any]]] = {}
    errors: Dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(wanted)) as pool:
        futs = {
            pool.submit(HISTORY_FETCHERS[ex], pair, interval, hours): ex
            for ex in wanted
            if ex in HISTORY_FETCHERS
        }
        for fut in as_completed(futs):
            ex = futs[fut]
            try:
                series[ex] = fut.result()
            except Exception as e:
                series[ex] = []
                errors[ex] = str(e)

    return {
        "pair": canonical_base(pair),
        "interval": interval,
        "hours": hours,
        "symbols": pair_symbols(pair),
        "series": series,
        "colors": {ex: EXCHANGE_COLORS.get(ex, "#aaa") for ex in series},
        "errors": errors,
    }


# ---------- 实时中间价（供 WSS hub 轮询） ----------

def fetch_live_mids(pair: str, exchanges: Optional[List[str]] = None) -> Dict[str, Optional[float]]:
    wanted = exchanges or list(DEFAULT_EXCHANGES)
    syms = pair_symbols(pair)
    out: Dict[str, Optional[float]] = {ex: None for ex in wanted}

    def _ondo():
        data = _session_get(f"{ONDO_URL}/v1/perps/contracts", timeout=LIVE_TIMEOUT)
        items = data.get("result") if isinstance(data, dict) else data
        market = syms["ondo_market"]
        for c in items or []:
            if isinstance(c, dict) and c.get("market") == market:
                for k in ("lastPrice", "indexPrice"):
                    if c.get(k) not in (None, ""):
                        return float(c[k])
                bid, ask = c.get("bid"), c.get("ask")
                if bid not in (None, "") and ask not in (None, ""):
                    return (float(bid) + float(ask)) / 2.0
        return None

    def _arcus():
        data = _session_get(f"{ARCUS_URL}/v1/markets", timeout=LIVE_TIMEOUT)
        markets = data.get("markets") if isinstance(data, dict) else data
        want = syms["arcus"]
        for m in markets or []:
            if isinstance(m, dict) and m.get("marketDisplayName") == want:
                for k in ("markPrice", "oraclePrice", "lastTradePrice"):
                    if m.get(k) not in (None, ""):
                        return float(m[k])
        return None

    def _standx():
        data = _session_get(
            f"{STANDX_URL}/api/query_symbol_price",
            params={"symbol": syms["standx"]},
            timeout=LIVE_TIMEOUT,
        )
        if not isinstance(data, dict):
            return None
        for k in ("mid_price", "mark_price", "last_price", "index_price"):
            if data.get(k) not in (None, ""):
                return float(data[k])
        bid, ask = data.get("spread_bid"), data.get("spread_ask")
        if bid not in (None, "") and ask not in (None, ""):
            return (float(bid) + float(ask)) / 2.0
        return None

    def _hype():
        for dex, coin in ((None, syms["hype_main"]), ("xyz", syms["hype"].split(":")[-1])):
            body: Dict[str, Any] = {"type": "metaAndAssetCtxs"}
            if dex:
                body["dex"] = dex
                coin_name = f"xyz:{coin}"
            else:
                coin_name = coin
            try:
                data = _session_post(HYPE_URL, body, timeout=LIVE_TIMEOUT)
            except Exception:
                continue
            if not isinstance(data, list) or len(data) < 2:
                continue
            uni, ctxs = data[0].get("universe") or [], data[1]
            for i, u in enumerate(uni):
                name = u.get("name") if isinstance(u, dict) else None
                if name == coin_name or name == coin:
                    ctx = ctxs[i] if i < len(ctxs) else {}
                    for k in ("midPx", "markPx", "oraclePx"):
                        if ctx.get(k) not in (None, ""):
                            return float(ctx[k])
        return None

    def _lighter():
        try:
            data = _session_get(f"{LIGHTER_URL}/api/v1/orderBookDetails", timeout=LIVE_TIMEOUT)
        except Exception:
            return None
        details = data.get("order_book_details") or []
        want = syms["lighter"]
        for d in details:
            if str(d.get("symbol") or "").upper() == want:
                for k in ("mark_price", "index_price", "last_trade_price"):
                    if d.get(k) not in (None, ""):
                        return float(d[k])
        return None

    fetchers = {
        "ondo": _ondo,
        "arcus": _arcus,
        "standx": _standx,
        "hype": _hype,
        "lighter": _lighter,
    }
    with ThreadPoolExecutor(max_workers=len(wanted)) as pool:
        futs = {pool.submit(fetchers[ex]): ex for ex in wanted if ex in fetchers}
        for fut in as_completed(futs):
            ex = futs[fut]
            try:
                out[ex] = fut.result()
            except Exception:
                out[ex] = None
    return out
