"""各交易所 OHLCV 下载器。"""
from __future__ import annotations

from typing import Dict, Type

from .base import BaseDownloader
from .arcus import ArcusDownloader
from .popdex import PopDEXDownloader
from .hype import HypeDownloader
from .ondo import OndoDownloader

DOWNLOADER_REGISTRY: Dict[str, Type[BaseDownloader]] = {
    "arcus": ArcusDownloader,
    "popdex": PopDEXDownloader,
    "hype": HypeDownloader,
    "hyperliquid": HypeDownloader,
    "ondo": OndoDownloader,
    "ondoperp": OndoDownloader,
    "ondoperps": OndoDownloader,
}


def get_downloader(exchange: str, **kwargs) -> BaseDownloader:
    key = (exchange or "").strip().lower()
    if key not in DOWNLOADER_REGISTRY:
        available = ", ".join(sorted(DOWNLOADER_REGISTRY))
        raise ValueError(f"不支持的交易所: {exchange}。可选: {available}")
    return DOWNLOADER_REGISTRY[key](**kwargs)
