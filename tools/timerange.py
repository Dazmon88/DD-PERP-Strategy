"""
时间区间解析（对齐 Freqtrade timerange 风格）。

支持:
  20240615-20260701
  20240615-
  -20260701
  20240615-20240620
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


_TIMERANGE_RE = re.compile(
    r"^(?P<start>\d{8})?-(?P<stop>\d{8})?$"
)

_TF_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}


@dataclass(frozen=True)
class TimeRange:
    start_ms: Optional[int]
    stop_ms: Optional[int]

    @property
    def start_dt(self) -> Optional[datetime]:
        if self.start_ms is None:
            return None
        return datetime.fromtimestamp(self.start_ms / 1000.0, tz=timezone.utc)

    @property
    def stop_dt(self) -> Optional[datetime]:
        if self.stop_ms is None:
            return None
        return datetime.fromtimestamp(self.stop_ms / 1000.0, tz=timezone.utc)


def timeframe_to_ms(timeframe: str) -> int:
    tf = (timeframe or "").strip().lower()
    if tf not in _TF_MS:
        raise ValueError(
            f"不支持的 timeframe: {timeframe}，可选: {', '.join(_TF_MS)}"
        )
    return _TF_MS[tf]


def parse_timerange(value: str, *, default_days: int = 30) -> TimeRange:
    """
    解析 timerange。

    若起止都省略（空或 '-'），默认最近 default_days 天到现在。
    若只有起点，终点为现在；若只有终点，起点为终点往前 default_days。
    """
    raw = (value or "").strip()
    now = datetime.now(tz=timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    if not raw or raw == "-":
        start = now - timedelta(days=default_days)
        return TimeRange(start_ms=int(start.timestamp() * 1000), stop_ms=now_ms)

    m = _TIMERANGE_RE.match(raw)
    if not m:
        raise ValueError(
            f"timerange 格式错误: {value!r}，示例: 20240615-20260701"
        )

    start_s = m.group("start")
    stop_s = m.group("stop")

    def _day_ms(yyyymmdd: str, *, end_of_day: bool = False) -> int:
        dt = datetime.strptime(yyyymmdd, "%Y%m%d").replace(tzinfo=timezone.utc)
        if end_of_day:
            dt = dt + timedelta(days=1) - timedelta(milliseconds=1)
        return int(dt.timestamp() * 1000)

    start_ms = _day_ms(start_s) if start_s else None
    stop_ms = _day_ms(stop_s, end_of_day=True) if stop_s else None

    if start_ms is None and stop_ms is None:
        start = now - timedelta(days=default_days)
        return TimeRange(start_ms=int(start.timestamp() * 1000), stop_ms=now_ms)
    if start_ms is None and stop_ms is not None:
        start_ms = stop_ms - default_days * 86_400_000
    if stop_ms is None and start_ms is not None:
        stop_ms = now_ms
    if start_ms is not None and stop_ms is not None and start_ms >= stop_ms:
        raise ValueError(f"timerange 起点必须早于终点: {value!r}")
    return TimeRange(start_ms=start_ms, stop_ms=stop_ms)


def iter_windows(
    start_ms: int,
    stop_ms: int,
    *,
    timeframe: str,
    max_bars: int,
):
    """
    按最多 max_bars 根 K 线切窗口（正向：从旧到新）。

    Yields:
        (window_start_ms, window_stop_ms)
    """
    step = timeframe_to_ms(timeframe) * max(1, int(max_bars))
    cur = start_ms
    while cur < stop_ms:
        end = min(cur + step, stop_ms)
        yield cur, end
        cur = end
