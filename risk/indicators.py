"""
Technical Indicators Tool
技术指标工具类（币安 K 线）
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests
import talib


_KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
]

# 币安 K 线 interval：https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
BINANCE_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
}
_INTERVAL_ALIASES = {
    "15min": "15m",
    "15mins": "15m",
    "1hr": "1h",
    "1hour": "1h",
    "4hr": "4h",
    "4hour": "4h",
    "4hours": "4h",
}


def normalize_kline_interval(interval: str) -> str:
    raw = (interval or "").strip()
    if not raw:
        return "4h"
    if raw in BINANCE_INTERVALS:
        return raw
    key = raw.lower().replace(" ", "")
    if key in BINANCE_INTERVALS:
        return key
    if key in _INTERVAL_ALIASES:
        return _INTERVAL_ALIASES[key]
    raise ValueError(
        f"不支持的 K 线周期: {interval!r}，可选: {sorted(BINANCE_INTERVALS)}"
    )


def to_binance_symbol(symbol: str) -> str:
    """交易所符号 → 币安现货符号（USD/USDC 报价一律映射 USDT）。"""
    s = (symbol or "").strip().upper()
    if ":" in s:
        s = s.split(":")[-1]
    s = (
        s.replace("_PERP", "")
        .replace(".P", "")
        .replace("-", "")
        .replace("_", "")
        .replace("/", "")
    )
    for quote in ("USDT", "USDC", "BUSD", "USD"):
        if s.endswith(quote):
            return s[: -len(quote)] + "USDT"
    if s:
        return s + "USDT"
    return s


class IndicatorTool:
    """技术指标工具类"""

    def __init__(self, cache_ttl_sec: float = 120.0):
        self.cache_ttl_sec = float(cache_ttl_sec)
        self._kline_cache: Dict[Tuple[str, str, int], Tuple[float, pd.DataFrame]] = {}

    def get_adx(
        self,
        symbol: str,
        resolution: str,
        period: int = 14,
        limit: int = 72,
    ) -> Optional[float]:
        adx, _ = self.get_adx_rsi(symbol, resolution, adx_period=period, limit=limit)
        return adx

    def get_rsi(
        self,
        symbol: str,
        resolution: str,
        period: int = 14,
        limit: int = 72,
    ) -> Optional[float]:
        _, rsi = self.get_adx_rsi(symbol, resolution, rsi_period=period, limit=limit)
        return rsi

    def get_adx_rsi(
        self,
        symbol: str,
        resolution: str = "4h",
        *,
        adx_period: int = 14,
        rsi_period: int = 14,
        limit: int = 72,
    ) -> Tuple[Optional[float], Optional[float]]:
        """同一批 K 线分别计算 ADX、RSI，返回最新值。"""
        df = self._fetch_klines(symbol, resolution, limit)
        if df is None or df.empty:
            return None, None
        try:
            adx_s = talib.ADX(
                df["high"], df["low"], df["close"], timeperiod=int(adx_period)
            )
            rsi_s = talib.RSI(df["close"], timeperiod=int(rsi_period))
            adx = float(adx_s.iloc[-1]) if not pd.isna(adx_s.iloc[-1]) else None
            rsi = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else None
            return adx, rsi
        except Exception as e:
            print(f"指标计算失败: {e}")
            return None, None

    def _fetch_klines(
        self, symbol: str, resolution: str, limit: int
    ) -> Optional[pd.DataFrame]:
        binance_symbol = to_binance_symbol(symbol)
        if not binance_symbol:
            print("指标: 无法从交易对解析币安符号")
            return None

        resolution = normalize_kline_interval(resolution)
        cache_key = (binance_symbol, str(resolution), int(limit))
        now = time.time()
        cached = self._kline_cache.get(cache_key)
        if cached and now - cached[0] < self.cache_ttl_sec:
            return cached[1]

        url = "https://api.binance.com/api/v3/klines"
        params: Dict[str, Any] = {
            "symbol": binance_symbol,
            "interval": resolution,
            "limit": int(limit),
        }
        try:
            response = requests.get(url, params=params, timeout=8)
        except requests.exceptions.RequestException as e:
            print(f"指标: 无法连接币安 API - {type(e).__name__}")
            return None

        if not response.ok:
            print(
                f"指标: 币安 API 错误 HTTP {response.status_code} "
                f"symbol={binance_symbol} interval={resolution}"
            )
            return None

        data = response.json()
        if not data:
            print(f"指标: 币安返回空 K 线 symbol={binance_symbol}")
            return None

        df = pd.DataFrame(data, columns=_KLINE_COLUMNS)
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        self._kline_cache[cache_key] = (now, df)
        return df
