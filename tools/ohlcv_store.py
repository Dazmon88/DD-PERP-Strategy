"""
OHLCV 落盘 / 读取。

默认保存到仓库根目录 data/{exchange}/{PAIR}-{timeframe}.csv
列: date, open, high, low, close, volume
date 为 UTC ISO8601。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def pair_to_filename(pair: str) -> str:
    """BTC-USD -> BTC_USD；BTCUSDT 保持。"""
    s = (pair or "").strip().upper()
    s = s.replace("/", "_").replace(":", "_").replace("-", "_")
    return s


def ohlcv_path(
    exchange: str,
    pair: str,
    timeframe: str,
    *,
    data_dir: Optional[Union[str, Path]] = None,
) -> Path:
    root = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    return root / exchange.lower() / f"{pair_to_filename(pair)}-{timeframe}.csv"


def normalize_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    out = df.copy()
    # 兼容 date / timestamp / openTime
    if "date" not in out.columns:
        for col in ("timestamp", "openTime", "startTime", "t", "time"):
            if col in out.columns:
                out = out.rename(columns={col: "date"})
                break
    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"OHLCV 缺少列: {missing}")

    out = out[OHLCV_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "open", "high", "low", "close"])
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    out = out.reset_index(drop=True)
    return out


def load_ohlcv(path: Union[str, Path]) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = pd.read_csv(path)
    return normalize_ohlcv_df(df)


def save_ohlcv(
    df: pd.DataFrame,
    path: Union[str, Path],
    *,
    erase: bool = False,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_df = normalize_ohlcv_df(df)
    if erase or not path.exists():
        merged = new_df
    else:
        old = load_ohlcv(path)
        merged = normalize_ohlcv_df(pd.concat([old, new_df], ignore_index=True))
    merged.to_csv(path, index=False)
    return path


def ensure_data_dir(data_dir: Optional[Union[str, Path]] = None) -> Path:
    root = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root
