"""Hyperliquid (Hype) OHLCV 下载。"""
from __future__ import annotations

from typing import List

import pandas as pd
import requests

from tools.downloaders.base import BaseDownloader
from tools.ohlcv_store import normalize_ohlcv_df
from tools.timerange import TimeRange, iter_windows

REST_URLS = {
    "mainnet": "https://api.hyperliquid.xyz/info",
    "testnet": "https://api.hyperliquid-testnet.xyz/info",
}


def _normalize_hype_coin(pair: str) -> str:
    s = pair.strip().upper()
    if "-" in s:
        s = s.split("-", 1)[0]
    if s.endswith("USDT"):
        s = s[:-4]
    elif s.endswith("USD"):
        s = s[:-3]
    return s


class HypeDownloader(BaseDownloader):
    exchange = "hype"
    MAX_BARS = 2000

    def __init__(self, *, network: str | None = None, timeout: float = 30.0, **kwargs):
        super().__init__(network=network or "mainnet", timeout=timeout, **kwargs)
        net = (self.network or "mainnet").lower()
        if net not in REST_URLS:
            net = "mainnet"
        self.url = kwargs.get("base_url") or REST_URLS[net]

    def download(
        self,
        pair: str,
        timeframe: str,
        timerange: TimeRange,
    ) -> pd.DataFrame:
        if timerange.start_ms is None or timerange.stop_ms is None:
            raise ValueError("Hype 下载需要完整 timerange")

        coin = _normalize_hype_coin(pair)
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
            body = {
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": timeframe,
                    "startTime": int(win_start),
                    "endTime": int(win_stop),
                },
            }

            def _fetch(_body=body):
                resp = requests.post(self.url, json=_body, timeout=self.timeout)
                if resp.status_code == 429:
                    raise ValueError(f"HTTP 429: {resp.text[:200]}")
                if not resp.ok:
                    raise ValueError(f"Hype HTTP {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                if not isinstance(data, list):
                    raise ValueError(f"意外的 Hype 响应: {data!r}")
                return data

            data = self._retry(_fetch, label=f"hype {coin} {i}/{len(windows)}")
            for c in data:
                if not isinstance(c, dict):
                    continue
                ts = c.get("t") or c.get("T")
                if ts is None:
                    continue
                rows.append(
                    {
                        "date": pd.to_datetime(int(ts), unit="ms", utc=True),
                        "open": c.get("o") or c.get("open"),
                        "high": c.get("h") or c.get("high"),
                        "low": c.get("l") or c.get("low"),
                        "close": c.get("c") or c.get("close"),
                        "volume": c.get("v") or c.get("volume") or 0,
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
