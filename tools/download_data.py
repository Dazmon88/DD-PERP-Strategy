#!/usr/bin/env python3
"""
下载交易所 OHLCV 到 data/ 目录（风格对齐 freqtrade download-data）。

用法:
  python -m tools.download_data -e arcus -p BTC-USD -t 5m --timerange 20240615-20260701
  python -m tools.download_data -e hype -p BTC -t 5m --days 7 --erase
  python -m tools.download_data -e popdex -p BTCUSDT -t 5m --days 7 --sleep 0.5

默认行为:
  - 页间 sleep（--sleep，默认 0.35s）
  - 429 指数退避重试（--retries / --retry-base-sleep）
  - 增量续传：补本地前后缺口；本地不在目标区间时自动覆盖重拉
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.downloaders import get_downloader
from tools.ohlcv_store import (
    DEFAULT_DATA_DIR,
    ensure_data_dir,
    load_ohlcv,
    ohlcv_path,
    save_ohlcv,
)
from tools.timerange import TimeRange, parse_timerange, timeframe_to_ms


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="下载 OHLCV 到 data/{exchange}/{PAIR}-{timeframe}.csv"
    )
    p.add_argument(
        "-e",
        "--exchange",
        required=True,
        help="交易所: arcus / popdex / hype / ondo",
    )
    p.add_argument(
        "-p",
        "--pairs",
        nargs="+",
        required=True,
        help="交易对，可多个。例: BTC-USD 或 BTCUSDT XAU-USD.P",
    )
    p.add_argument(
        "-t",
        "--timeframes",
        nargs="+",
        default=["5m"],
        help="周期，可多个。默认: 5m。例: 1m 5m 1h",
    )
    p.add_argument(
        "--timerange",
        default="",
        help="时间区间 YYYYMMDD-YYYYMMDD。例: 20240615-20260701",
    )
    p.add_argument(
        "--days",
        type=int,
        default=None,
        help="下载最近 N 天（与 --timerange 互斥）",
    )
    p.add_argument(
        "--erase",
        action="store_true",
        help="覆盖已有文件并全量重拉（关闭增量续传）",
    )
    p.add_argument(
        "--no-incremental",
        action="store_true",
        help="不从本地最后一根续传（仍会与旧文件合并，除非 --erase）",
    )
    p.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help=f"数据目录（默认: {DEFAULT_DATA_DIR}）",
    )
    p.add_argument(
        "-n",
        "--network",
        default=None,
        help="网络: mainnet / testnet（按交易所支持）",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP 超时秒数",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.35,
        help="分页请求间隔秒数（默认 0.35；限流时可加大到 0.5~1）",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=6,
        help="遇 429 时额外重试次数（默认 6）",
    )
    p.add_argument(
        "--retry-base-sleep",
        type=float,
        default=1.5,
        help="429 首次退避秒数，之后指数翻倍（默认 1.5）",
    )
    return p


def resolve_timerange(args: argparse.Namespace) -> TimeRange:
    if args.days is not None and args.timerange:
        raise SystemExit("--days 与 --timerange 不能同时使用")
    if args.days is not None:
        if args.days <= 0:
            raise SystemExit("--days 必须 > 0")
        return parse_timerange("-", default_days=args.days)
    if args.timerange:
        return parse_timerange(args.timerange)
    return parse_timerange("-", default_days=30)


def apply_incremental(
    timerange: TimeRange,
    *,
    path: Path,
    timeframe: str,
    erase: bool,
    no_incremental: bool,
) -> tuple[TimeRange, str, bool]:
    """
    增量续传：在本地连续缓存上补缺口。

    Returns:
        (adjusted_timerange, note, force_erase)
        force_erase=True 表示本地文件与目标区间无关，应覆盖写入避免脏数据残留。
    """
    if erase or no_incremental:
        return timerange, "全量", erase
    if not path.exists():
        return timerange, "全量(无本地文件)", False

    old = load_ohlcv(path)
    if old.empty or timerange.stop_ms is None or timerange.start_ms is None:
        return timerange, "全量(本地为空)", False

    tf_ms = timeframe_to_ms(timeframe)
    first_ms = int(old["date"].iloc[0].timestamp() * 1000)
    last_ms = int(old["date"].iloc[-1].timestamp() * 1000)
    start_ms = timerange.start_ms
    stop_ms = timerange.stop_ms

    # 本地完全落在目标区间之外（例如之前 --days 2 的烟测文件）
    if first_ms > stop_ms or last_ms < start_ms:
        return timerange, "全量(本地不在目标区间，将覆盖)", True

    missing_prefix = first_ms > start_ms + tf_ms
    missing_suffix = last_ms + tf_ms < stop_ms

    if not missing_prefix and not missing_suffix:
        return timerange, "已是最新", False

    # 前后都缺：无法单段续传，整段重拉并覆盖，避免中间空洞
    if missing_prefix and missing_suffix:
        return timerange, "全量(本地两端都有缺口，将覆盖)", True

    if missing_prefix:
        adjusted = TimeRange(start_ms=start_ms, stop_ms=min(first_ms, stop_ms))
        return adjusted, f"补齐前端 -> {adjusted.stop_dt}", False

    next_ms = last_ms + tf_ms
    adjusted = TimeRange(start_ms=next_ms, stop_ms=stop_ms)
    return adjusted, f"增量续传 from {adjusted.start_dt}", False


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    timerange = resolve_timerange(args)
    data_dir = ensure_data_dir(args.data_dir)

    default_network = {
        "arcus": "mainnet",
        "popdex": "mainnet",
        "hype": "mainnet",
        "hyperliquid": "mainnet",
        "ondo": "mainnet",
        "ondoperp": "mainnet",
        "ondoperps": "mainnet",
    }.get(args.exchange.lower(), "mainnet")
    network = args.network or default_network

    print(f"exchange={args.exchange} network={network}")
    print(
        f"timerange={timerange.start_dt} -> {timerange.stop_dt} "
        f"({timerange.start_ms} - {timerange.stop_ms})"
    )
    print(
        f"data_dir={data_dir} sleep={args.sleep}s "
        f"retries={args.retries} retry_base_sleep={args.retry_base_sleep}s"
    )

    downloader = get_downloader(
        args.exchange,
        network=network,
        timeout=args.timeout,
        sleep=args.sleep,
        retries=args.retries,
        retry_base_sleep=args.retry_base_sleep,
    )
    exch_name = getattr(downloader, "exchange", args.exchange).lower()

    total_files = 0
    for pair in args.pairs:
        for tf in args.timeframes:
            path = ohlcv_path(exch_name, pair, tf, data_dir=data_dir)
            fetch_range, mode, force_erase = apply_incremental(
                timerange,
                path=path,
                timeframe=tf,
                erase=args.erase,
                no_incremental=args.no_incremental,
            )
            do_erase = bool(args.erase or force_erase)
            print(f"\n>>> 下载 {args.exchange} {pair} {tf} [{mode}] ...")
            if mode == "已是最新":
                old = load_ohlcv(path)
                print(
                    f"[跳过] 本地已覆盖区间 "
                    f"({len(old)} bars, last={old['date'].iloc[-1] if not old.empty else 'n/a'}) "
                    f"-> {path}"
                )
                total_files += 1
                continue

            print(
                f"    fetch {fetch_range.start_dt} -> {fetch_range.stop_dt}"
            )
            try:
                df = downloader.download(pair, tf, fetch_range)
            except Exception as e:
                print(f"[失败] {pair} {tf}: {e}")
                continue

            if df is None or df.empty:
                print(f"[空] {pair} {tf}: 无数据，跳过写入 -> {path}")
                continue

            save_ohlcv(df, path, erase=do_erase)
            total_files += 1
            merged = load_ohlcv(path)
            print(
                f"[完成] 本次 +{len(df)} bars，合计 {len(merged)} bars "
                f"{merged['date'].iloc[0]} -> {merged['date'].iloc[-1]} "
                f"-> {path}"
            )

    print(f"\n共处理 {total_files} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
