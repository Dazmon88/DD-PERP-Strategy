"""PopDEX OHLCV 下载。"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, List, Optional

import pandas as pd

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from exchange.exchange_popdex.popdex_protocol.perp_http import PopDEXPerpHTTP
from tools.downloaders.base import BaseDownloader
from tools.downloaders.retry import is_rate_limit_error
from tools.ohlcv_store import normalize_ohlcv_df
from tools.timerange import TimeRange, iter_windows


def _normalize_popdex_symbol(pair: str) -> str:
    s = pair.strip().upper().replace("-", "").replace("_", "")
    if s.endswith("USD") and not s.endswith("USDT"):
        s = s[:-3] + "USDT"
    return s


def _parse_candle_row(row: Any) -> dict | None:
    if isinstance(row, (list, tuple)) and len(row) >= 6:
        ts = int(row[0])
        if ts < 10_000_000_000:
            ts *= 1000
        return {
            "date": pd.to_datetime(ts, unit="ms", utc=True),
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
        }
    if isinstance(row, dict):
        ts = row.get("startTime") or row.get("openTime") or row.get("t") or row.get("time")
        if ts is None:
            return None
        ts = int(ts)
        if ts < 10_000_000_000:
            ts *= 1000
        return {
            "date": pd.to_datetime(ts, unit="ms", utc=True),
            "open": row.get("open") or row.get("o"),
            "high": row.get("high") or row.get("h"),
            "low": row.get("low") or row.get("l"),
            "close": row.get("close") or row.get("c"),
            "volume": row.get("volume") or row.get("v") or 0,
        }
    return None


def _extract_list(raw: Any) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        data = raw.get("data") or raw.get("list") or raw.get("candles") or []
        return data if isinstance(data, list) else []
    return []


class PopDEXDownloader(BaseDownloader):
    exchange = "popdex"
    MAX_BARS = 900

    def __init__(self, *, network: str | None = None, timeout: float = 30.0, **kwargs):
        super().__init__(network=network or "mainnet", timeout=timeout, **kwargs)
        self.category = kwargs.get("category") or "Futures"
        self.http = PopDEXPerpHTTP(network=self.network, timeout=timeout)

    def _fetch_window(self, symbol: str, timeframe: str, win_start: int, win_stop: int):
        def _public():
            return self.http.get_candles(
                category=self.category,
                symbol=symbol,
                interval=timeframe,
                startTime=win_start,
                endTime=win_stop,
                limit=1000,
            )

        public_err: Exception | None = None
        try:
            raw = self._retry(_public, label=f"popdex public {symbol}")
            if _extract_list(raw):
                return raw
        except Exception as e:
            if is_rate_limit_error(e):
                raise
            public_err = e

        def _hist():
            return self.http.get_history_candles(
                category=self.category,
                symbol=symbol,
                interval=timeframe,
                startTime=win_start,
                endTime=win_stop,
                limit=1000,
            )

        try:
            return self._retry(_hist, label=f"popdex history {symbol}")
        except Exception:
            if public_err is not None:
                raise public_err
            raise

    def _probe_earliest_ms(self, symbol: str, timeframe: str) -> Optional[int]:
        """粗测该周期最早可用 K 线（按周回退）。"""
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        earliest: Optional[int] = None
        for i in range(0, 104):
            to = now_ms - i * 7 * 86_400_000
            fr = to - 7 * 86_400_000
            try:
                raw = self.http.get_candles(
                    category=self.category,
                    symbol=symbol,
                    interval=timeframe,
                    startTime=fr,
                    endTime=to,
                    limit=1000,
                )
            except Exception:
                break
            data = _extract_list(raw)
            if not data:
                break
            parsed = _parse_candle_row(data[0])
            if parsed is not None:
                earliest = int(parsed["date"].timestamp() * 1000)
        return earliest

    def download(
        self,
        pair: str,
        timeframe: str,
        timerange: TimeRange,
    ) -> pd.DataFrame:
        if timerange.start_ms is None or timerange.stop_ms is None:
            raise ValueError("PopDEX 下载需要完整 timerange")

        symbol = _normalize_popdex_symbol(pair)

        # 先探测留存起点，避免对两年空区间疯狂翻页
        earliest = self._probe_earliest_ms(symbol, timeframe)
        if earliest is not None and timerange.stop_ms is not None:
            if timerange.stop_ms < earliest:
                earliest_dt = datetime.fromtimestamp(earliest / 1000, tz=timezone.utc)
                raise ValueError(
                    f"PopDEX {symbol} {timeframe} 在请求区间内无数据。"
                    f"该周期最早约从 {earliest_dt.date()} 起有 K 线；"
                    f"请把 --timerange 终点调到该日期之后，或改用 --days N。"
                    f"（PopDEX 细周期留存很短，不能像币安拉两年 5m。）"
                )
            # 起点早于留存：从最早可用处开始，少打空请求
            if timerange.start_ms is not None and timerange.start_ms < earliest:
                print(
                    f"[popdex] 本地请求起点早于交易所留存，"
                    f"从 {datetime.fromtimestamp(earliest/1000, tz=timezone.utc)} 起拉"
                )
                timerange = TimeRange(start_ms=earliest, stop_ms=timerange.stop_ms)

        rows: List[dict] = []
        windows = list(
            iter_windows(
                timerange.start_ms,
                timerange.stop_ms,
                timeframe=timeframe,
                max_bars=self.MAX_BARS,
            )
        )
        nonempty_windows = 0
        for i, (win_start, win_stop) in enumerate(windows, 1):
            raw = self._fetch_window(symbol, timeframe, win_start, win_stop)
            data = _extract_list(raw)
            if data:
                nonempty_windows += 1
            for item in data:
                parsed = _parse_candle_row(item)
                if parsed:
                    rows.append(parsed)
            if i < len(windows):
                self._pace()

        df = normalize_ohlcv_df(pd.DataFrame(rows))
        if not df.empty:
            start = pd.to_datetime(timerange.start_ms, unit="ms", utc=True)
            stop = pd.to_datetime(timerange.stop_ms, unit="ms", utc=True)
            df = df[(df["date"] >= start) & (df["date"] <= stop)].reset_index(drop=True)

        if df.empty:
            if earliest is not None:
                earliest_dt = datetime.fromtimestamp(earliest / 1000, tz=timezone.utc)
                raise ValueError(
                    f"PopDEX {symbol} {timeframe} 在请求区间内无数据。"
                    f"该周期最早约从 {earliest_dt.date()} 起有 K 线；"
                    f"请把 --timerange 终点调到该日期之后，或改用 --days N。"
                    f"（PopDEX 细周期留存很短，不能像币安拉两年 5m。）"
                )
            raise ValueError(
                f"PopDEX {symbol} {timeframe} 返回空数据"
                f"（windows={len(windows)}, nonempty={nonempty_windows}）"
            )
        return df
