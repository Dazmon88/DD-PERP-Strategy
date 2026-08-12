"""并行拉取各所公开资金费率。"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from normalize import canonical_base, normalize_rates, to_float

ONDO_URL = "https://api.ondoperps.xyz"
ARCUS_URL = "https://api.arcus.xyz"
STANDX_URL = "https://perps.standx.com"
HYPE_URL = "https://api.hyperliquid.xyz/info"
LIGHTER_URL = "https://mainnet.zklighter.elliot.ai"

# 各所当前结算周期（小时）。公开接口均为按小时结算口径。
INTERVAL_HOURS = {
    "ondo": 1.0,
    "arcus": 1.0,
    "standx": 1.0,
    "hype": 1.0,
    "lighter": 1.0,
}

STANDX_CRYPTO = {
    "BTC", "ETH", "BNB", "SOL", "HYPE", "XRP", "DOGE", "ADA", "AVAX", "LINK",
}

# Hype HIP-3 TradFi dex；xyz: 前缀即 RWA/TradFi 标识
HYPE_RWA_DEXES = ("xyz",)

HYPE_COMMODITY = {
    "GOLD", "SILVER", "CL", "COPPER", "NATGAS", "BRENTOIL", "PLATINUM",
    "PALLADIUM", "ALUMINIUM", "URANIUM", "CORN", "WHEAT", "TTF", "XAU",
    "XAG", "WTI", "BRENT", "PAXG", "XCU", "XPT", "XPD", "URA", "USO",
    "GLD", "SLV",
}
HYPE_INDEX = {
    "XYZ100", "SP500", "KR200", "JP225", "NIFTY", "IBOV", "DXY", "VIX",
    "US500", "US100",
}
HYPE_ETF = {
    "EWY", "EWJ", "EWZ", "EWT", "SMH", "XLE", "DRAM", "SOXL", "URNM",
}
REQUEST_TIMEOUT = 6.0  # 快所 HTTP 超时
EXCHANGE_TIMEOUT = 8.0  # 首屏等待各所的上限
LIGHTER_HTTP_TIMEOUT = 25.0  # Lighter 单次允许更久
LIGHTER_REFRESH_SECONDS = 120.0  # Lighter 最少间隔，避免打爆慢接口

HYPE_FX = {"EUR", "JPY", "GBP", "KRW"}
LIGHTER_FX = {
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD",
    "USDKRW", "USDHKD",
}
# 常见加密；避免无 strategy_index 时被误判为股票
LIGHTER_CRYPTO = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
    "LTC", "BCH", "UNI", "AAVE", "CRV", "LDO", "OP", "ARB", "SUI", "APT",
    "NEAR", "INJ", "TIA", "SEI", "WLD", "ENA", "HYPE", "TRUMP", "WIF", "PEPE",
    "BONK", "FLOKI", "SHIB", "TON", "TRX", "XLM", "HBAR", "ICP", "FIL", "ATOM",
    "DYDX", "GMX", "PENDLE", "JUP", "PYTH", "ONDO", "STRK", "ZK", "ZRO", "EIGEN",
    "GRASS", "BERA", "MOVE", "KAITO", "IP", "VIRTUAL", "AI16Z", "FARTCOIN",
    "POPCAT", "PNUT", "GOAT", "MOODENG", "CHILLGUY", "ACT", "MEW", "NEIRO",
    "TAO", "S", "MKR", "SKY", "MORPHO", "RESOLV", "ZORA", "SPX", "AERO",
    "JTO", "BIO", "PENGU", "SYRUP", "ETHFI", "ENA", "PUMP", "USELESS",
    "LAUNCHCOIN", "YZY", "WEN", "BIRB", "CASHCAT", "FOGO", "PIPPIN", "2Z",
    "XPL", "ASTER", "POL", "CRO", "MNT", "ZEC", "DASH", "XMR", "NMR", "QNT",
    "AXS", "RAIL", "CC", "DATA", "EDEN", "ADI", "MET", "FF", "AZTEC", "MYX",
    "WLFI", "LINEA", "DOLO", "MON", "MEGA", "PROVE", "0G", "SKR", "APEX",
    "STABLE", "STBL", "LIT", "ARC", "VVV", "AVNT", "FOLKS", "ROBO",
}

CATEGORY_ALIASES = {
    "stock": "stock",
    "stocks": "stock",
    "equity": "stock",
    "equities": "stock",
    "crypto": "crypto",
    "commodity": "commodity",
    "commodities": "commodity",
    "index": "index",
    "indices": "index",
    "etf": "etf",
}

# 前端「RWA」= 股票 + 商品 + ETF + 指数（不含纯加密）
RWA_CATEGORIES = ("stock", "commodity", "etf", "index")


def expand_categories(categories: Optional[List[str]]) -> Optional[List[str]]:
    if not categories:
        return None
    out: List[str] = []
    for c in categories:
        key = CATEGORY_ALIASES.get(c.lower(), c.lower())
        if key == "rwa":
            out.extend(RWA_CATEGORIES)
        else:
            out.append(key)
    # 去重且保序
    seen = set()
    uniq = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq or None


def _session_kwargs(timeout: float = REQUEST_TIMEOUT) -> dict:
    return {
        "timeout": timeout,
        "headers": {"Accept": "application/json", "Content-Type": "application/json"},
        "proxies": {"http": None, "https": None},
    }


def _get_json(url: str, timeout: float = REQUEST_TIMEOUT) -> Any:
    # 显式禁用代理，避免本机 HTTP(S)_PROXY 干扰公开行情请求
    resp = requests.get(url, **_session_kwargs(timeout))
    resp.raise_for_status()
    return resp.json()


def _post_json(url: str, body: dict, timeout: float = REQUEST_TIMEOUT) -> Any:
    resp = requests.post(url, json=body, **_session_kwargs(timeout))
    resp.raise_for_status()
    return resp.json()


def _classify_tradfi_ticker(ticker: str) -> str:
    t = (ticker or "").upper()
    if t in HYPE_COMMODITY:
        return "commodity"
    if t in HYPE_INDEX:
        return "index"
    if t in HYPE_ETF:
        return "etf"
    if t in HYPE_FX or t in LIGHTER_FX:
        return "other"
    return "stock"


def _classify_lighter_symbol(symbol: str) -> str:
    """不依赖慢接口 orderBookDetails；用 ticker 启发式分类。"""
    s = (symbol or "").upper()
    if not s or "/" in s:
        return "other"
    if s.startswith("1000") or s in LIGHTER_CRYPTO:
        return "crypto"
    if s in LIGHTER_FX or (len(s) == 6 and s.endswith("USD")):
        return "other"
    if s in HYPE_COMMODITY or s in {
        "XAU", "XAG", "WTI", "BRENT", "XCU", "XPT", "XPD", "URA", "NATGAS",
        "WHEAT", "PAXG", "GLD", "SLV", "USO",
    }:
        return "commodity"
    if s in HYPE_INDEX or s in {"US500", "US100", "SPX"}:
        return "index"
    if s in HYPE_ETF or s in {"SPY", "QQQ", "IWM", "SOXL", "SOXX", "BOTZ", "MAGS", "DRAM", "EWY"}:
        return "etf"
    # 其余短字母 ticker 按股权/RWA 处理（含美股、亚洲股、pre-IPO 题材）
    if s.isalpha() and 1 <= len(s) <= 12:
        return "stock"
    return "other"


def _snapshot(
    *,
    exchange: str,
    symbol: str,
    rate: Optional[float],
    interval_hours: float,
    category: str,
    name: str = "",
    next_funding_ts: Optional[int] = None,
    mark_price: Optional[float] = None,
) -> Dict[str, Any]:
    norms = normalize_rates(rate, interval_hours)
    return {
        "exchange": exchange,
        "symbol": symbol,
        "pair": canonical_base(symbol),
        "name": name,
        "category": category,
        "interval_hours": interval_hours,
        "next_funding_ts": next_funding_ts,
        "mark_price": mark_price,
        **norms,
    }


def _map_ondo_tags(tags: Optional[List[str]]) -> str:
    if not tags:
        return "other"
    t = tags[0].lower()
    return CATEGORY_ALIASES.get(t, t)


def _map_arcus_category(cat: Optional[str]) -> str:
    if not cat:
        return "other"
    return CATEGORY_ALIASES.get(cat.lower(), cat.lower())


def fetch_ondo() -> List[Dict[str, Any]]:
    data = _get_json(f"{ONDO_URL}/v1/perps/contracts")
    items = data.get("result") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    # markets 补充 longName / tags（contracts 里也可能有 tags）
    name_map: Dict[str, str] = {}
    tag_map: Dict[str, str] = {}
    try:
        markets = _get_json(f"{ONDO_URL}/v1/markets")
        pairs = (
            markets.get("result", {})
            .get("perps", {})
            .get("tradingPairs", [])
        )
        for m in pairs or []:
            market = m.get("market")
            if not market:
                continue
            name_map[market] = m.get("longName") or ""
            tag_map[market] = _map_ondo_tags(m.get("tags"))
    except Exception:
        pass

    out: List[Dict[str, Any]] = []
    for c in items:
        if not isinstance(c, dict) or c.get("disabled"):
            continue
        market = c.get("market") or ""
        if not market:
            continue
        next_ts = None
        ts_raw = c.get("nextFundingRateTimestamp")
        if ts_raw not in (None, ""):
            try:
                # 可能是 ISO 或毫秒
                if isinstance(ts_raw, (int, float)) or str(ts_raw).isdigit():
                    v = int(ts_raw)
                    next_ts = v // 1000 if v > 10_000_000_000 else v
                else:
                    next_ts = int(
                        datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")).timestamp()
                    )
            except Exception:
                next_ts = None

        category = tag_map.get(market) or _map_ondo_tags(c.get("tags"))
        # contracts.fundingRate = 上一小时已结算；UI/交易页展示的是当前区间预估
        # nextFundingRate（与 GET /funding_rates 的 rate 一致）
        rate = to_float(c.get("nextFundingRate"))
        if rate is None:
            rate = to_float(c.get("fundingRate"))
        out.append(
            _snapshot(
                exchange="ondo",
                symbol=str(market),
                rate=rate,
                interval_hours=INTERVAL_HOURS["ondo"],
                category=category,
                name=name_map.get(market) or str(c.get("displayName") or ""),
                next_funding_ts=next_ts,
                mark_price=to_float(c.get("lastPrice") or c.get("indexPrice")),
            )
        )
    return out


def fetch_arcus() -> List[Dict[str, Any]]:
    data = _get_json(f"{ARCUS_URL}/v1/markets")
    markets = data.get("markets") if isinstance(data, dict) else data
    if not isinstance(markets, list):
        return []

    out: List[Dict[str, Any]] = []
    for m in markets:
        if not isinstance(m, dict):
            continue
        status = str(m.get("status") or "").upper()
        if status and status not in ("ONLINE", "ACTIVE"):
            continue
        symbol = m.get("marketDisplayName") or ""
        if not symbol:
            continue
        next_ts = m.get("nextFundingAt")
        if isinstance(next_ts, (int, float)):
            next_ts = int(next_ts)
        else:
            next_ts = None
        out.append(
            _snapshot(
                exchange="arcus",
                symbol=str(symbol),
                rate=to_float(m.get("fundingRate")),
                interval_hours=INTERVAL_HOURS["arcus"],
                category=_map_arcus_category(m.get("category")),
                name=str(m.get("fullAssetName") or ""),
                next_funding_ts=next_ts,
                mark_price=to_float(m.get("markPrice") or m.get("oraclePrice")),
            )
        )
    return out


def _classify_standx_base(base: str) -> str:
    b = (base or "").upper()
    if b in STANDX_CRYPTO or b in LIGHTER_CRYPTO:
        return "crypto"
    return _classify_tradfi_ticker(b)


def fetch_standx() -> List[Dict[str, Any]]:
    """StandX 公开总览：含 funding_rate；结算周期 1h（next_funding_time 整点）。"""
    data = _get_json(f"{STANDX_URL}/api/query_market_overview")
    symbols = data.get("symbols") if isinstance(data, dict) else None
    if not isinstance(symbols, list):
        return []

    out: List[Dict[str, Any]] = []
    for row in symbols:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "")
        base = str(row.get("base") or "")
        if not symbol:
            continue
        if not base and "-" in symbol:
            base = symbol.split("-", 1)[0]
        out.append(
            _snapshot(
                exchange="standx",
                symbol=symbol,
                rate=to_float(row.get("funding_rate")),
                interval_hours=INTERVAL_HOURS["standx"],
                category=_classify_standx_base(base),
                name=base,
                mark_price=to_float(row.get("mark_price") or row.get("last_price")),
            )
        )
    return out


def _fetch_hype_dex(dex: Optional[str] = None) -> List[Dict[str, Any]]:
    body: Dict[str, Any] = {"type": "metaAndAssetCtxs"}
    if dex:
        body["dex"] = dex
    data = _post_json(HYPE_URL, body)
    if not isinstance(data, list) or len(data) < 2:
        return []
    meta, ctxs = data[0], data[1]
    universe = meta.get("universe") if isinstance(meta, dict) else None
    if not isinstance(universe, list) or not isinstance(ctxs, list):
        return []

    out: List[Dict[str, Any]] = []
    for asset, ctx in zip(universe, ctxs):
        if not isinstance(asset, dict) or not isinstance(ctx, dict):
            continue
        if asset.get("isDelisted"):
            continue
        name = str(asset.get("name") or "")
        if not name:
            continue
        raw_ticker = name.split(":")[-1] if ":" in name else name
        if dex:
            category = _classify_tradfi_ticker(raw_ticker)
        else:
            category = "crypto"
        out.append(
            _snapshot(
                exchange="hype",
                symbol=name,
                rate=to_float(ctx.get("funding")),
                interval_hours=INTERVAL_HOURS["hype"],
                category=category,
                name=raw_ticker,
                mark_price=to_float(ctx.get("markPx") or ctx.get("oraclePx")),
            )
        )
    return out


def fetch_hype() -> List[Dict[str, Any]]:
    """主簿加密 + HIP-3 xyz（TradFi/RWA，符号形如 xyz:AAPL）。"""
    out = _fetch_hype_dex(None)
    for dex in HYPE_RWA_DEXES:
        try:
            out.extend(_fetch_hype_dex(dex))
        except Exception:
            continue
    return out


def fetch_lighter() -> List[Dict[str, Any]]:
    """
    只打 funding-rates（过滤 exchange=lighter）。

    注意：该接口为多所对比接口，Lighter 条目的 rate 是 **8h 口径**（与 Binance/Bybit
    对齐）；实际每小时结算 = rate/8，与官网 UI、/fundings 历史一致。
    例：BOT rate=3.2e-05 → 小时费率 4e-06 → UI 显示 0.0004%。

    Lighter 网关常 10–60s+，调用方应使用 LIGHTER_HTTP_TIMEOUT，且勿高频重试。
    """
    rates_payload = _get_json(
        f"{LIGHTER_URL}/api/v1/funding-rates",
        timeout=LIGHTER_HTTP_TIMEOUT,
    )
    rows = rates_payload.get("funding_rates") if isinstance(rates_payload, dict) else []
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("exchange") or "").lower() != "lighter":
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol or symbol in seen or "/" in symbol:
            continue
        rate_8h = to_float(row.get("rate"))
        if rate_8h is None:
            continue
        rate_1h = rate_8h / 8.0
        seen.add(symbol)
        out.append(
            _snapshot(
                exchange="lighter",
                symbol=symbol,
                rate=rate_1h,
                interval_hours=INTERVAL_HOURS["lighter"],
                category=_classify_lighter_symbol(symbol),
                name="",
            )
        )
    return out


FETCHERS = {
    "ondo": fetch_ondo,
    "arcus": fetch_arcus,
    "standx": fetch_standx,
    "hype": fetch_hype,
    "lighter": fetch_lighter,
}


class FundingCollector:
    """
    快所短超时并行；Lighter 单独长超时 + 低频刷新，并用上次成功结果兜底，
    避免列经常为空。
    """

    def __init__(
        self,
        ttl_seconds: float = 45.0,
        exchange_timeout: float = EXCHANGE_TIMEOUT,
        lighter_refresh_seconds: float = LIGHTER_REFRESH_SECONDS,
    ):
        self.ttl_seconds = ttl_seconds
        self.exchange_timeout = exchange_timeout
        self.lighter_refresh_seconds = lighter_refresh_seconds
        self._cache: Optional[Dict[str, Any]] = None
        self._cached_at: float = 0.0
        self._by_exchange: Dict[str, List[Dict[str, Any]]] = {}
        self._exchange_fetched_at: Dict[str, float] = {}
        self._refreshing = False
        self._lighter_refreshing = False
        self._bg_pool = ThreadPoolExecutor(max_workers=2)

    def collect(
        self,
        exchanges: Optional[List[str]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        now = time.time()
        wanted = exchanges or list(FETCHERS.keys())
        cache_ok = (
            self._cache is not None
            and (now - self._cached_at) < self.ttl_seconds
        )

        if cache_ok and not force:
            # 缓存命中时仍可在后台补 Lighter（若过旧或缺失）
            self._maybe_schedule_lighter(wanted, force=False)
            return self._cache

        if self._cache is not None and not force:
            self._schedule_refresh(wanted, force=False)
            stale = dict(self._cache)
            stale["stale"] = True
            return stale

        return self._fetch_now(wanted, force=force)

    def _maybe_schedule_lighter(self, wanted: List[str], force: bool) -> None:
        if "lighter" not in wanted:
            return
        now = time.time()
        last = self._exchange_fetched_at.get("lighter", 0.0)
        has = bool(self._by_exchange.get("lighter"))
        # force=True 仅表示「允许在缺失/超时后续拉」，仍尊重进行中的锁
        due = (not has) or (now - last >= self.lighter_refresh_seconds) or (
            force and not has
        )
        if not due or self._lighter_refreshing:
            return
        self._lighter_refreshing = True

        def _job():
            try:
                rows = fetch_lighter()
                self._by_exchange["lighter"] = rows
                self._exchange_fetched_at["lighter"] = time.time()
                self._rebuild_cache_from_parts(wanted)
                if self._cache is not None:
                    errs = dict(self._cache.get("errors") or {})
                    errs.pop("lighter", None)
                    self._cache = {**self._cache, "errors": errs}
            except Exception as e:
                # 保留错误信息便于排查，但不清空旧缓存
                if self._cache is not None:
                    errs = dict(self._cache.get("errors") or {})
                    errs["lighter"] = str(e)
                    self._cache = {**self._cache, "errors": errs}
            finally:
                self._lighter_refreshing = False

        self._bg_pool.submit(_job)

    def _schedule_refresh(self, wanted: List[str], force: bool = False) -> None:
        if self._refreshing:
            return
        self._refreshing = True

        def _job():
            try:
                self._fetch_now(wanted, force=force)
            finally:
                self._refreshing = False

        self._bg_pool.submit(_job)

    def _rebuild_cache_from_parts(self, wanted: List[str]) -> None:
        snapshots: List[Dict[str, Any]] = []
        for ex in wanted:
            snapshots.extend(self._by_exchange.get(ex) or [])
        if not snapshots and self._cache is not None:
            return
        self._cache = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "snapshots": snapshots,
            "errors": (self._cache or {}).get("errors") or {},
            "stale": False,
        }
        self._cached_at = time.time()

    def _fetch_now(self, wanted: List[str], force: bool = False) -> Dict[str, Any]:
        errors: Dict[str, str] = {}
        # 快所：本次并行拉取。Lighter 从不挡首屏，只走后台长超时。
        fast = [ex for ex in wanted if ex != "lighter" and ex in FETCHERS]

        pool = ThreadPoolExecutor(max_workers=max(1, len(fast)))
        done_ex: set = set()
        try:
            futures = {pool.submit(FETCHERS[ex]): ex for ex in fast}
            try:
                for fut in as_completed(futures, timeout=self.exchange_timeout):
                    ex = futures[fut]
                    done_ex.add(ex)
                    try:
                        rows = fut.result(timeout=0.1)
                        self._by_exchange[ex] = rows
                        self._exchange_fetched_at[ex] = time.time()
                    except Exception as e:
                        errors[ex] = str(e)
            except TimeoutError:
                pass

            for fut, ex in futures.items():
                if ex in done_ex:
                    continue
                errors[ex] = f"timeout>{self.exchange_timeout}s"
                fut.cancel()
        finally:
            pool.shutdown(wait=False, cancel_futures=False)

        # Lighter：后台补齐 / 按 120s 刷新；有旧数据则继续展示
        if "lighter" in wanted:
            has = bool(self._by_exchange.get("lighter"))
            self._maybe_schedule_lighter(wanted, force=not has)
            if not has:
                errors["lighter"] = "pending"

        snapshots: List[Dict[str, Any]] = []
        for ex in wanted:
            rows = self._by_exchange.get(ex) or []
            snapshots.extend(rows)
            if not rows and ex not in errors:
                errors[ex] = "no data"

        payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "snapshots": snapshots,
            "errors": errors,
            "stale": False,
        }
        if not snapshots and self._cache is not None:
            merged = dict(self._cache)
            merged["errors"] = {**(self._cache.get("errors") or {}), **errors}
            merged["stale"] = True
            return merged

        self._cache = payload
        self._cached_at = time.time()
        return payload



def build_matrix(
    payload: Dict[str, Any],
    *,
    categories: Optional[List[str]] = None,
    pairs: Optional[List[str]] = None,
    exchanges: Optional[List[str]] = None,
    display: str = "rate_8h",
    min_venues: int = 1,
) -> Dict[str, Any]:
    """组装行=交易对、列=交易所的矩阵。"""
    snaps: List[Dict[str, Any]] = payload.get("snapshots") or []
    exch_filter = set(exchanges) if exchanges else None
    cat_expanded = expand_categories(categories)
    cat_filter = set(cat_expanded) if cat_expanded else set()
    pair_filter = {p.upper() for p in (pairs or [])}

    # pair -> exchange -> cell
    grid: Dict[str, Dict[str, Dict[str, Any]]] = {}
    meta: Dict[str, Dict[str, Any]] = {}

    for s in snaps:
        ex = s["exchange"]
        if exch_filter and ex not in exch_filter:
            continue
        cat = s.get("category") or "other"
        if cat_filter and cat not in cat_filter:
            continue
        pair = s.get("pair") or ""
        if not pair:
            continue
        if pair_filter and pair not in pair_filter:
            continue

        grid.setdefault(pair, {})[ex] = {
            "symbol": s.get("symbol"),
            "rate": s.get("rate"),
            "rate_1h": s.get("rate_1h"),
            "rate_8h": s.get("rate_8h"),
            "apr": s.get("apr"),
            "interval_hours": s.get("interval_hours"),
            "next_funding_ts": s.get("next_funding_ts"),
            "mark_price": s.get("mark_price"),
            "display_value": s.get(display),
        }
        info = meta.setdefault(pair, {"name": "", "category": cat})
        if s.get("name") and not info["name"]:
            info["name"] = s["name"]
        if cat and cat != "other":
            info["category"] = cat

    cols = sorted(exch_filter) if exch_filter else sorted({s["exchange"] for s in snaps})
    rows = []
    for pair in sorted(grid.keys()):
        cells = grid[pair]
        if len(cells) < min_venues:
            continue
        values = [
            cells[ex].get("display_value")
            for ex in cols
            if ex in cells and cells[ex].get("display_value") is not None
        ]
        arb = None
        if len(values) >= 2:
            hi = max(values)
            lo = min(values)
            arb = {
                "spread": hi - lo,
                "long_exchange": next(
                    ex for ex in cols if ex in cells and cells[ex].get("display_value") == lo
                ),
                "short_exchange": next(
                    ex for ex in cols if ex in cells and cells[ex].get("display_value") == hi
                ),
            }
        rows.append(
            {
                "pair": pair,
                "name": meta.get(pair, {}).get("name", ""),
                "category": meta.get(pair, {}).get("category", "other"),
                "cells": {ex: cells.get(ex) for ex in cols},
                "arb": arb,
                "venue_count": len(cells),
            }
        )

    # 可套利优先：有跨所差的排前面，再按 spread 降序
    rows.sort(
        key=lambda r: (
            0 if r.get("arb") else 1,
            -(r["arb"]["spread"] if r.get("arb") else 0),
            r["pair"],
        )
    )

    return {
        "fetched_at": payload.get("fetched_at"),
        "display": display,
        "exchanges": cols,
        "rows": rows,
        "errors": payload.get("errors") or {},
        "count": len(rows),
    }
