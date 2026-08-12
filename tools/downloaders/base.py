"""下载器基类。"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Callable, Optional, TypeVar

import pandas as pd

from tools.downloaders.retry import call_with_retry
from tools.timerange import TimeRange

T = TypeVar("T")


class BaseDownloader(ABC):
    exchange: str = "unknown"

    def __init__(
        self,
        *,
        network: Optional[str] = None,
        timeout: float = 30.0,
        sleep: float = 0.35,
        retries: int = 6,
        retry_base_sleep: float = 1.5,
        **kwargs,
    ):
        self.network = network
        self.timeout = timeout
        # 每页请求后的固定间隔（秒）
        self.sleep = float(sleep)
        # 429 额外重试次数
        self.retries = int(retries)
        # 429 首次退避秒数（之后指数增长）
        self.retry_base_sleep = float(retry_base_sleep)
        self.extra = kwargs

    def _pace(self) -> None:
        if self.sleep > 0:
            time.sleep(self.sleep)

    def _retry(self, fn: Callable[[], T], *, label: str = "") -> T:
        return call_with_retry(
            fn,
            retries=self.retries,
            base_sleep=self.retry_base_sleep,
            label=label or self.exchange,
        )

    @abstractmethod
    def download(
        self,
        pair: str,
        timeframe: str,
        timerange: TimeRange,
    ) -> pd.DataFrame:
        """下载 [start_ms, stop_ms] 区间 OHLCV，返回标准 DataFrame。"""
        raise NotImplementedError
