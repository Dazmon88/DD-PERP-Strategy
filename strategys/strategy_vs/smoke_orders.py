#!/usr/bin/env python3
"""
两所最小仓开平冒烟。默认 dry-run，不接入 vs_monitor，不下真单。

用法（仓库根目录）:
  venv/bin/python strategys/strategy_vs/smoke_orders.py
  venv/bin/python strategys/strategy_vs/smoke_orders.py --live
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from adapters.factory import create_adapter  # noqa: E402
from vs_monitor import _load_yaml, _merge_venue_keys  # noqa: E402

SKIP_CFG = {
    "taker_fee",
    "maker_fee",
    "role",
    "exchange",
    "name",
    "stale_ms",
    "rest_interval_sec",
    "account_rest_sec",
    "account_stale_sec",
}


def _adapter_config(venue_cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = {k: v for k, v in venue_cfg.items() if k not in SKIP_CFG}
    cfg["exchange_name"] = str(venue_cfg["exchange"]).strip().lower()
    return cfg


def _d(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _signed_pos(adapter: Any, symbol: str) -> Decimal:
    pos = adapter.get_position(symbol)
    if pos is None or _d(pos.size) == 0:
        return Decimal("0")
    size = abs(_d(pos.size))
    side = str(getattr(pos, "side", "") or "").lower()
    return -size if side in ("short", "sell") else size


def _min_qty(adapter: Any, symbol: str, override: Optional[Decimal]) -> Decimal:
    if override is not None and override > 0:
        return override
    getter = getattr(adapter, "_get_market_meta", None)
    if callable(getter):
        try:
            meta = getter(symbol)
            dec = int(
                meta.get("size_decimals")
                or meta.get("supported_size_decimals")
                or 0
            )
            if dec > 0:
                return Decimal(10) ** -dec
        except Exception:
            pass
    http = getattr(adapter, "http_client", None)
    if http is not None and hasattr(http, "get_contracts"):
        try:
            from adapters.ondo_adapter import normalize_ondo_symbol, _as_list

            want = normalize_ondo_symbol(symbol)
            for row in _as_list(http.get_contracts()):
                if not isinstance(row, dict):
                    continue
                market = str(row.get("market") or "")
                if market and normalize_ondo_symbol(market) != want:
                    continue
                for key in (
                    "minOrderSize",
                    "minSize",
                    "qtyIncrement",
                    "sizeIncrement",
                    "lotSize",
                ):
                    raw = row.get(key)
                    if raw not in (None, "", 0, "0"):
                        qty = _d(raw)
                        if qty > 0:
                            return qty
        except Exception:
            pass
    return Decimal("0.0001")


def _wait_pos(
    adapter: Any,
    symbol: str,
    expect: Decimal,
    timeout: float,
    tol: Decimal,
) -> Decimal:
    deadline = time.time() + timeout
    last = _signed_pos(adapter, symbol)
    while time.time() < deadline:
        last = _signed_pos(adapter, symbol)
        if abs(last - expect) <= tol:
            return last
        time.sleep(0.4)
    return last


def _smoke_one(
    *,
    slot: str,
    venue_cfg: Dict[str, Any],
    qty_override: Optional[Decimal],
    side: str,
    wait_sec: float,
    live: bool,
) -> int:
    exchange = str(venue_cfg.get("exchange") or "")
    symbol = str(venue_cfg.get("symbol") or "")
    print(f"\n=== {slot} {exchange} {symbol} ===")
    adapter = create_adapter(_adapter_config(venue_cfg))
    adapter.connect()
    qty = _min_qty(adapter, symbol, qty_override)
    before = _signed_pos(adapter, symbol)
    ticker = {}
    with_err = None
    try:
        ticker = adapter.get_ticker(symbol) or {}
    except Exception as exc:
        with_err = str(exc)
    bid = ticker.get("bid_price")
    ask = ticker.get("ask_price")
    close_side = "sell" if side == "buy" else "buy"
    signed = qty if side == "buy" else -qty
    expect_open = before + signed
    print(f"仓位前  {before:+.8f}")
    print(f"买一/卖一 {bid} / {ask}" + (f"  ticker失败: {with_err}" if with_err else ""))
    print(f"计划    开 {side} {qty}  → 平 {close_side} {qty} reduce_only")
    print(f"期望    开后 {expect_open:+.8f}  平后 {before:+.8f}")
    if not live:
        print("dry-run  未下单")
        return 0

    tol = max(qty * Decimal("0.05"), Decimal("1e-8"))
    opened = False
    try:
        open_order = adapter.place_order(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=qty,
            time_in_force="ioc",
            reduce_only=False,
            post_only=False,
        )
        opened = True
        print(
            f"开仓    id={getattr(open_order, 'order_id', '')} "
            f"status={getattr(open_order, 'status', '')}"
        )
        after_open = _wait_pos(adapter, symbol, expect_open, wait_sec, tol)
        print(f"仓位开后 {after_open:+.8f}")
        if abs(after_open - expect_open) > tol:
            print("开仓仓位未对齐，仍尝试减掉本次数量")
        close_order = adapter.place_order(
            symbol=symbol,
            side=close_side,
            order_type="market",
            quantity=qty,
            time_in_force="ioc",
            reduce_only=True,
            post_only=False,
        )
        print(
            f"平仓    id={getattr(close_order, 'order_id', '')} "
            f"status={getattr(close_order, 'status', '')}"
        )
        after_close = _wait_pos(adapter, symbol, before, wait_sec, tol)
        print(f"仓位平后 {after_close:+.8f}")
        if abs(after_close - before) > tol:
            print(f"警告    未回到开仓前仓位，请手工检查 {exchange} {symbol}")
            return 1
        print("结果    开平回到原仓位")
        return 0
    except Exception as exc:
        print(f"失败    {exc}")
        if opened:
            print("警告    可能已开仓未平，请手工检查")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="两所最小仓开平冒烟（默认 dry-run）")
    parser.add_argument(
        "-c",
        "--config",
        default=str(CURRENT_DIR / "config.yaml"),
        help="配置文件路径",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="真下单；还需要 config.smoke.enable: true",
    )
    parser.add_argument(
        "--venue",
        choices=("a", "b", "both"),
        default=None,
        help="只跑 a / b，默认跟配置 smoke.venues",
    )
    args = parser.parse_args()
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = str((Path.cwd() / config_path).resolve())
    cfg = _load_yaml(config_path)
    venues = cfg.get("venues") or {}
    smoke = cfg.get("smoke") or {}
    enable = bool(smoke.get("enable", False))
    live = bool(args.live) and enable
    if args.live and not enable:
        raise SystemExit(
            "拒绝下单：config.smoke.enable 仍是 false。"
            "确认后改成 true，再加 --live。"
        )
    if enable and not args.live:
        print("smoke.enable 已开，但未加 --live，仍 dry-run")

    qty_raw = smoke.get("qty")
    qty_override = _d(qty_raw) if qty_raw not in (None, "") else None
    side = str(smoke.get("side") or "buy").strip().lower()
    if side in ("long",):
        side = "buy"
    elif side in ("short",):
        side = "sell"
    if side not in ("buy", "sell"):
        raise SystemExit("smoke.side 只能是 buy 或 sell")
    wait_sec = float(smoke.get("wait_sec", 8.0))
    which = args.venue or str(smoke.get("venues") or "both")
    slots = ("a", "b") if which == "both" else (which,)

    print(f"模式    {'LIVE' if live else 'dry-run'}")
    print(f"配置    {config_path}")
    rc = 0
    for slot in slots:
        if slot not in venues:
            raise SystemExit(f"config.venues.{slot} 不存在")
        venue_cfg = _merge_venue_keys(dict(venues[slot]))
        if not venue_cfg.get("exchange") or not venue_cfg.get("symbol"):
            raise SystemExit(f"venues.{slot} 需要 exchange 和 symbol")
        rc |= _smoke_one(
            slot=slot,
            venue_cfg=venue_cfg,
            qty_override=qty_override,
            side=side,
            wait_sec=wait_sec,
            live=live,
        )
    return rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
