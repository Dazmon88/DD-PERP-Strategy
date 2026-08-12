"""Arcus OHLCV 下载。"""
from __future__ import annotations

import os
import sys
from typing import List

import pandas as pd

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from exchange.exchange_arcus.arcus_protocol.perp_http import ArcusPerpHTTP
from tools.downloaders.base import BaseDownloader
from tools.ohlcv_store import normalize_ohlcv_df
from tools.timerange import TimeRange, iter_windows


class ArcusDownloader(BaseDownloader):
    exchange = "arcus"
    # 实测单次约 1500 根
    MAX_BARS = 1400

    def __init__(self, *, network: str | None = None, timeout: float = 30.0, **kwargs):
        super().__init__(network=network or "mainnet", timeout=timeout, **kwargs)
        self.http = ArcusPerpHTTP(network=self.network, timeout=timeout)

    def download(
        self,
        pair: str,
        timeframe: str,
        timerange: TimeRange,
    ) -> pd.DataFrame:
        if timerange.start_ms is None or timerange.stop_ms is None:
            raise ValueError("Arcus 下载需要完整 timerange")

        market = pair.strip().upper()
        if "-" not in market:
            market = f"{market}-USD" if not market.endswith("USD") else market
        market = market.replace("USDT", "USD")

        rows: List[dict] = []
        windows = list(
            iter_windows(
                timerange.start_ms,
                timerange.stop_ms,
                timeframe=timeframe,
                max_bars=self.MAX_BARS,
            )
        )
        for i, (win_start, win_stop) in enumerate(windows, 1):
            fr = int(win_start * 1000)
            to = int(win_stop * 1000)

            def _fetch(_fr=fr, _to=to):
                return self.http.get_candles(
                    market=market,
                    timeframe=timeframe,
                    **{"from": _fr, "to": _to},
                )

            raw = self._retry(_fetch, label=f"arcus {market} {i}/{len(windows)}")
            candles = []
            if isinstance(raw, dict):
                candles = raw.get("candles") or raw.get("data") or []
            elif isinstance(raw, list):
                candles = raw
            for c in candles:
                if not isinstance(c, dict):
                    continue
                open_time = c.get("openTime") or c.get("t") or c.get("timestamp")
                if open_time is None:
                    continue
                ot = int(open_time)
                if ot > 10_000_000_000_000:
                    ot_ms = ot // 1000
                elif ot > 10_000_000_000:
                    ot_ms = ot
                else:
                    ot_ms = ot * 1000
                rows.append(
                    {
                        "date": pd.to_datetime(ot_ms, unit="ms", utc=True),
                        "open": c.get("open"),
                        "high": c.get("high"),
                        "low": c.get("low"),
                        "close": c.get("close"),
                        "volume": c.get("volume") or c.get("baseVolume") or 0,
                    }
                )
            if i < len(windows):
                self._pace()

        df = normalize_ohlcv_df(pd.DataFrame(rows))
        if not df.empty:
            start = pd.to_datetime(timerange.start_ms, unit="ms", utc=True)
            stop = pd.to_datetime(timerange.stop_ms, unit="ms", utc=True)
            df = df[(df["date"] >= start) & (df["date"] <= stop)].reset_index(drop=True)
        return df
