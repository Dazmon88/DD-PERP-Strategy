"""Ondo Perps OHLCV 下载。

优先走公开接口 GET /v1/perps/history（无需 API Key）。
若配置了 key，也可走 GET /v1/perps/candles。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from exchange.exchange_ondoperp.ondoperp_protocol.perp_http import OndoPerpHTTP
from exchange.exchange_ondoperp.ondoperp_protocol.perps_auth import OndoPerpAuth
from tools.downloaders.base import BaseDownloader
from tools.ohlcv_store import normalize_ohlcv_df
from tools.timerange import TimeRange, iter_windows


def _to_ondo_resolution(timeframe: str) -> str:
    tf = timeframe.strip().lower()
    mapping = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "4h": "240",
        "1d": "1D",
        "1w": "1W",
    }
    if tf not in mapping:
        raise ValueError(f"Ondo 不支持 timeframe={timeframe}")
    return mapping[tf]


def _normalize_ondo_market(pair: str) -> str:
    """策略/合约风格: BTC-USD.P"""
    s = pair.strip()
    if s.upper().endswith(".P"):
        base, suf = s.rsplit(".", 1)
        return f"{base.upper()}.{suf.upper()}"
    s = s.replace("_", "-")
    if "-" not in s:
        s = f"{s}-USD"
    if not s.upper().endswith(".P"):
        s = f"{s}.P"
    base, suf = s.rsplit(".", 1)
    return f"{base.upper()}.{suf.upper()}"


def _to_history_symbol(market: str) -> str:
    """
    /v1/perps/history 的 symbol：去掉中间横杠。
    BTC-USD.P -> BTCUSD.P
    """
    m = _normalize_ondo_market(market)
    if m.upper().endswith(".P"):
        base, suf = m.rsplit(".", 1)
        return f"{base.replace('-', '').upper()}.{suf.upper()}"
    return m.replace("-", "").upper()


def _parse_ts_ms(value) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        ts = int(value)
        if ts < 10_000_000_000:
            return ts * 1000
        if ts > 10_000_000_000_000:
            return ts // 1000
        return ts
    s = str(value).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


class OndoDownloader(BaseDownloader):
    exchange = "ondo"
    # history 单窗约 2000 根；过大 from 会直接返回空，需分页
    MAX_BARS = 1500

    def __init__(
        self,
        *,
        network: str | None = None,
        timeout: float = 30.0,
        key_id: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(network=network or "mainnet", timeout=timeout, **kwargs)
        key_id = (
            key_id
            or kwargs.get("api_key_id")
            or os.getenv("ONDO_KEY_ID")
            or ""
        ).strip()
        api_secret = (
            api_secret
            or kwargs.get("secret")
            or os.getenv("ONDO_API_SECRET")
            or ""
        ).strip()
        if not key_id or not api_secret:
            try:
                from tools.generated_keys import load_generated

                secrets = load_generated("ondo")
                key_id = key_id or str(secrets.get("key_id") or "").strip()
                api_secret = api_secret or str(secrets.get("api_secret") or "").strip()
            except Exception:
                pass

        self.auth: Optional[OndoPerpAuth] = None
        if key_id and api_secret:
            self.auth = OndoPerpAuth(
                key_id=key_id,
                api_secret=api_secret,
                network=self.network,  # type: ignore[arg-type]
            )
        self.http = OndoPerpHTTP(
            network=self.network,
            auth=self.auth,
            timeout=timeout,
        )
        # 有 key 时可用 candles；默认仍优先公开 history（更稳、免鉴权）
        self.use_candles = bool(self.auth) and bool(kwargs.get("use_candles", False))

    def download(
        self,
        pair: str,
        timeframe: str,
        timerange: TimeRange,
    ) -> pd.DataFrame:
        if timerange.start_ms is None or timerange.stop_ms is None:
            raise ValueError("Ondo 下载需要完整 timerange")

        market = _normalize_ondo_market(pair)
        resolution = _to_ondo_resolution(timeframe)
        timerange = self._clamp_to_retention(market, timeframe, resolution, timerange)
        if self.use_candles:
            df = self._download_candles(market, timeframe, resolution, timerange)
        else:
            df = self._download_history(market, timeframe, resolution, timerange)
        if df.empty:
            raise ValueError(
                f"Ondo {market} {timeframe} 在请求区间内无数据。"
                f"公开 history 细周期留存约 5 周；请改用 --days N 或更近的 --timerange。"
            )
        return df

    def _probe_earliest_ms(
        self, symbol: str, resolution: str
    ) -> Optional[int]:
        """按周回退探测公开 history 最早可用时间（秒→毫秒）。"""
        now_s = int(datetime.now(tz=timezone.utc).timestamp())
        earliest: Optional[int] = None
        for i in range(0, 60):
            to = now_s - i * 7 * 86400
            fr = to - 7 * 86400
            try:
                raw = self.http.get_price_history(
                    symbol,
                    resolution=resolution,
                    **{"from": fr, "to": to},
                )
            except Exception:
                break
            ts_list = (raw or {}).get("t") if isinstance(raw, dict) else None
            if not ts_list:
                break
            ts_ms = _parse_ts_ms(ts_list[0])
            if ts_ms is not None:
                earliest = ts_ms
        return earliest

    def _clamp_to_retention(
        self,
        market: str,
        timeframe: str,
        resolution: str,
        timerange: TimeRange,
    ) -> TimeRange:
        symbol = _to_history_symbol(market)
        earliest = self._probe_earliest_ms(symbol, resolution)
        if earliest is None or timerange.stop_ms is None or timerange.start_ms is None:
            return timerange

        if timerange.stop_ms < earliest:
            earliest_dt = datetime.fromtimestamp(earliest / 1000, tz=timezone.utc)
            raise ValueError(
                f"Ondo {market} {timeframe} 在请求区间内无数据。"
                f"该周期最早约从 {earliest_dt.date()} 起有 K 线；"
                f"请把 --timerange 终点调到该日期之后，或改用 --days N。"
                f"（公开 history 细周期留存约 5 周，不能像币安拉两年 5m。）"
            )
        if timerange.start_ms < earliest:
            print(
                f"[ondo] 请求起点早于公开留存，"
                f"从 {datetime.fromtimestamp(earliest / 1000, tz=timezone.utc)} 起拉"
            )
            return TimeRange(start_ms=earliest, stop_ms=timerange.stop_ms)
        return timerange

    def _download_history(
        self,
        market: str,
        timeframe: str,
        resolution: str,
        timerange: TimeRange,
    ) -> pd.DataFrame:
        symbol = _to_history_symbol(market)
        rows: List[dict] = []
        windows = list(
            iter_windows(
                timerange.start_ms,  # type: ignore[arg-type]
                timerange.stop_ms,  # type: ignore[arg-type]
                timeframe=timeframe,
                max_bars=self.MAX_BARS,
            )
        )

        for i, (win_start, win_stop) in enumerate(windows, 1):
            fr = int(win_start // 1000)
            to = int(win_stop // 1000)

            def _fetch(_fr=fr, _to=to):
                return self.http.get_price_history(
                    symbol,
                    resolution=resolution,
                    **{"from": _fr, "to": _to},
                )

            raw = self._retry(
                _fetch, label=f"ondo history {symbol} {i}/{len(windows)}"
            )
            if not isinstance(raw, dict):
                raw = {}
            status = str(raw.get("s") or "")
            if status not in ("ok", "no_data", ""):
                raise ValueError(f"Ondo history error: {raw}")
            ts_list = raw.get("t") or []
            o_list = raw.get("o") or []
            h_list = raw.get("h") or []
            l_list = raw.get("l") or []
            c_list = raw.get("c") or []
            v_list = raw.get("v") or []
            for j, ts in enumerate(ts_list):
                ts_ms = _parse_ts_ms(ts)
                if ts_ms is None:
                    continue
                rows.append(
                    {
                        "date": pd.to_datetime(ts_ms, unit="ms", utc=True),
                        "open": o_list[j] if j < len(o_list) else None,
                        "high": h_list[j] if j < len(h_list) else None,
                        "low": l_list[j] if j < len(l_list) else None,
                        "close": c_list[j] if j < len(c_list) else None,
                        "volume": v_list[j] if j < len(v_list) else 0,
                    }
                )
            if i < len(windows):
                self._pace()

        return self._clip(normalize_ohlcv_df(pd.DataFrame(rows)), timerange)

    def _download_candles(
        self,
        market: str,
        timeframe: str,
        resolution: str,
        timerange: TimeRange,
    ) -> pd.DataFrame:
        if not self.auth:
            raise ValueError("candles 模式需要 API Key（.generated/ondo.json）")
        rows: List[dict] = []
        windows = list(
            iter_windows(
                timerange.start_ms,  # type: ignore[arg-type]
                timerange.stop_ms,  # type: ignore[arg-type]
                timeframe=timeframe,
                max_bars=self.MAX_BARS,
            )
        )
        for i, (win_start, win_stop) in enumerate(windows, 1):
            fr = int(win_start // 1000)
            to = int(win_stop // 1000)

            def _fetch(_fr=fr, _to=to):
                return self.http.get_candles(
                    market,
                    resolution=resolution,
                    **{"from": _fr, "to": _to},
                )

            raw = self._retry(
                _fetch, label=f"ondo candles {market} {i}/{len(windows)}"
            )
            data = raw
            if isinstance(raw, dict):
                data = raw.get("result") or raw.get("data") or raw.get("candles") or []
            if not isinstance(data, list):
                data = []
            for c in data:
                if not isinstance(c, dict):
                    continue
                ts_ms = _parse_ts_ms(
                    c.get("startTime") or c.get("time") or c.get("t")
                )
                if ts_ms is None:
                    continue
                rows.append(
                    {
                        "date": pd.to_datetime(ts_ms, unit="ms", utc=True),
                        "open": c.get("open"),
                        "high": c.get("high"),
                        "low": c.get("low"),
                        "close": c.get("close"),
                        "volume": c.get("volume") or 0,
                    }
                )
            if i < len(windows):
                self._pace()

        return self._clip(normalize_ohlcv_df(pd.DataFrame(rows)), timerange)

    @staticmethod
    def _clip(df: pd.DataFrame, timerange: TimeRange) -> pd.DataFrame:
        if df.empty:
            return df
        start = pd.to_datetime(timerange.start_ms, unit="ms", utc=True)
        stop = pd.to_datetime(timerange.stop_ms, unit="ms", utc=True)
        return df[(df["date"] >= start) & (df["date"] <= stop)].reset_index(drop=True)
