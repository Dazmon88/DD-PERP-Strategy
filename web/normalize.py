"""资金费率周期归一化与符号统一。"""
from __future__ import annotations

from typing import Optional

# 跨所同标的别名 → 统一 base
PAIR_ALIASES = {
    "GOLD": "XAU",
    "SILVER": "XAG",
    "PAXG": "XAU",
    "CL": "WTI",
    "USO": "WTI",
    "BRENTOIL": "BRENT",
    "SP500": "US500",
    "XYZ100": "US100",
    "NAS100": "US100",
    "SKHX": "SKHY",
    "SKHYNIX": "SKHY",
    "SPACEX": "SPCX",
}


def to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_rates(rate: Optional[float], interval_hours: float) -> dict:
    """将结算周期费率换算为 1h / 8h / APR。"""
    if rate is None or interval_hours <= 0:
        return {"rate": None, "rate_1h": None, "rate_8h": None, "apr": None}

    rate_1h = rate / interval_hours
    return {
        "rate": rate,
        "rate_1h": rate_1h,
        "rate_8h": rate_1h * 8.0,
        "apr": rate_1h * 24.0 * 365.0,
    }


def canonical_base(symbol: str) -> str:
    """把各所符号压成统一 base，如 AAPL / BTC / XAU。"""
    s = (symbol or "").strip().upper()
    if not s:
        return ""
    # HIP-3 / builder：xyz:AAPL、flx:NVDA
    if ":" in s:
        s = s.split(":")[-1]
    for sep in ("-USD.P", "-USDT", "-USD", "_USDT_PERP", "_USD_PERP", "USDT", "USD.P"):
        if s.endswith(sep):
            s = s[: -len(sep)]
            break
    s = s.replace("-", "").replace("_", "").replace("/", "")
    if s.endswith("USD") and len(s) > 3 and not s.startswith("USD"):
        # HYUNDAIUSD → HYUNDAI；保留 US500/US100
        if not (len(s) > 3 and s[2:].isdigit()):
            s = s[:-3]
    return PAIR_ALIASES.get(s, s)
