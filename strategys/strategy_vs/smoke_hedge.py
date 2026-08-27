#!/usr/bin/env python3
"""
双腿一层冒烟：B 所 Maker 挂 best，WSS 仓位增量后 A 所市价对冲；再反向平掉。
不接入 vs_monitor。

用法（仓库根目录）:
  venv/bin/python strategys/strategy_vs/smoke_hedge.py
  venv/bin/python strategys/strategy_vs/smoke_hedge.py --live
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Optional

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from accounts import AccountBook, ThreadWake  # noqa: E402
from adapters.factory import create_adapter  # noqa: E402
from feeds import QuoteBook, run_feed, venue_role  # noqa: E402
from hedge import DualLegBroker  # noqa: E402
from ledger import PositionLedger  # noqa: E402
from smoke_orders import _adapter_config, _min_qty, _d  # noqa: E402
from vs_monitor import _load_yaml, _merge_venue_keys  # noqa: E402


def _print_layer(title: str, result) -> None:
    print(f"\n=== {title} delta={result.delta:+d} ===")
    for line in result.logs:
        print(f"  {line}")
    if result.error and not result.ok:
        print(f"  错误  {result.error}")
    print(f"  结果  {'OK' if result.ok else 'FAIL'}  {result.note}")


def _pos_lookup(accounts: AccountBook, slot: str) -> Optional[Decimal]:
    snap = accounts.latest().get(slot)
    if snap is None or snap.pos_qty is None:
        return None
    return Decimal(str(snap.pos_qty))


def _bbo_lookup(book: QuoteBook) -> tuple[Optional[Decimal], Optional[Decimal]]:
    quote = book.latest().get("b")
    if quote is None or quote.bid is None or quote.ask is None:
        return None, None
    return Decimal(str(quote.bid)), Decimal(str(quote.ask))


def _fmt_src(item) -> str:
    if item is None:
        return "无"
    src = getattr(item, "source", "") or "?"
    ts = float(getattr(item, "ts", 0) or 0)
    age = f"{max(0.0, time.time() - ts) * 1000:.0f}ms" if ts else "-"
    return f"{src} {age}"


async def _wait_wss(
    book: QuoteBook,
    accounts: AccountBook,
    timeout: float = 20.0,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        quotes = book.latest()
        accts = accounts.latest()
        qa, qb = quotes.get("a"), quotes.get("b")
        aa, ab = accts.get("a"), accts.get("b")
        book_ok = (
            qa is not None
            and qb is not None
            and qa.bid is not None
            and qa.ask is not None
            and qb.bid is not None
            and qb.ask is not None
            and not qa.error
            and not qb.error
        )
        pos_ok = (
            aa is not None
            and ab is not None
            and aa.pos_qty is not None
            and ab.pos_qty is not None
        )
        if book_ok and pos_ok:
            return True
        await asyncio.sleep(0.15)
    return False


async def _amain() -> int:
    parser = argparse.ArgumentParser(description="双腿一层冒烟（默认 dry-run）")
    parser.add_argument("-c", "--config", default=str(CURRENT_DIR / "config.yaml"))
    parser.add_argument(
        "--live",
        action="store_true",
        help="真下单；还需要 config.smoke.enable: true",
    )
    args = parser.parse_args()
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = str((Path.cwd() / config_path).resolve())
    cfg = _load_yaml(config_path)
    venues = cfg.get("venues") or {}
    smoke = cfg.get("smoke") or {}
    vs_cfg = cfg.get("vs") or {}
    enable = bool(smoke.get("enable", False))
    live = bool(args.live) and enable
    if args.live and not enable:
        raise SystemExit(
            "拒绝下单：config.smoke.enable 仍是 false。"
            "确认后改成 true，再加 --live。"
        )
    if enable and not args.live:
        print("smoke.enable 已开，但未加 --live，仍 dry-run")
    if "a" not in venues or "b" not in venues:
        raise SystemExit("config.venues 需要 a 和 b")

    a_cfg = _merge_venue_keys(dict(venues["a"]))
    b_cfg = _merge_venue_keys(dict(venues["b"]))
    for venue_cfg in (a_cfg, b_cfg):
        venue_cfg.setdefault("stale_ms", vs_cfg.get("stale_ms", 2000))
        venue_cfg.setdefault("rest_interval_sec", vs_cfg.get("rest_interval_sec", 1))
        venue_cfg.setdefault("account_rest_sec", vs_cfg.get("account_rest_sec", 30))
        venue_cfg.setdefault("account_stale_sec", vs_cfg.get("account_stale_sec", 15))
    adapter_a = create_adapter(_adapter_config(a_cfg))
    adapter_b = create_adapter(_adapter_config(b_cfg))
    adapter_a.connect()
    adapter_b.connect()
    symbol_a = str(a_cfg.get("symbol") or "")
    symbol_b = str(b_cfg.get("symbol") or "")
    qty_raw = smoke.get("qty")
    qty_override = _d(qty_raw) if qty_raw not in (None, "") else None
    qty = min(
        _min_qty(adapter_a, symbol_a, qty_override),
        _min_qty(adapter_b, symbol_b, qty_override),
    )
    timeout_sec = float(smoke.get("timeout_sec") or smoke.get("wait_sec") or 60.0)
    ledger = PositionLedger(qty_per_layer=float(qty), pos_tolerance=1e-7, live=False)
    ledger.accounts_ready = True

    book = QuoteBook()
    accounts = AccountBook()
    stop = asyncio.Event()
    feed_a = asyncio.create_task(run_feed("a", a_cfg, book, stop, accounts), name="feed-a")
    feed_b = asyncio.create_task(run_feed("b", b_cfg, book, stop, accounts), name="feed-b")
    try:
        ready = await _wait_wss(book, accounts)
        quotes = book.latest()
        accts = accounts.latest()
        print(f"模式    {'LIVE' if live else 'dry-run'}")
        print(f"配置    {config_path}")
        print(f"数量    {qty}")
        print(f"等待    {timeout_sec:g}s（B Maker 未成则撤单）")
        print(
            f"WSS     {'就绪' if ready else '未齐，仓/盘口 REST 兜底'}  "
            f"盘口A={_fmt_src(quotes.get('a'))} B={_fmt_src(quotes.get('b'))}  "
            f"仓A={_fmt_src(accts.get('a'))} B={_fmt_src(accts.get('b'))}"
        )
        b_maker = venue_role(b_cfg) == "maker"
        hedge_wake = ThreadWake()
        book.set_thread_wake(hedge_wake)
        accounts.set_thread_wake(hedge_wake)
        broker = DualLegBroker(
            adapter_a,
            adapter_b,
            symbol_a,
            symbol_b,
            timeout_sec=timeout_sec,
            poll_sec=0.05,
            live=live,
            b_maker=b_maker,
            log=print,
            pos_lookup=lambda slot: _pos_lookup(accounts, slot),
            bbo_lookup=lambda: _bbo_lookup(book),
            wake=hedge_wake,
        )
        pos_a = broker._pos("a")
        pos_b = broker._pos("b")
        print(f"A {a_cfg.get('exchange')} {symbol_a} 仓 {pos_a:+.8f}")
        print(f"B {b_cfg.get('exchange')} {symbol_b} 仓 {pos_b:+.8f}")
        b_style = "Maker" if b_maker else "市价"
        print(f"计划    开 +1 卖B({b_style})/买A(市价) → 平 -1 买B({b_style})/卖A(市价)")

        tol = max(qty * Decimal("0.05"), Decimal("1e-8"))
        skip_open = False
        if abs(pos_a) > tol or abs(pos_b) > tol:
            leftover_open = abs(pos_a - qty) <= tol and abs(pos_b + qty) <= tol
            if leftover_open:
                print("已有一层未平（上次开仓残留），跳过开仓只平")
                skip_open = True
            else:
                print(
                    f"拒绝下单：所仓非空 A {pos_a:+.8f} / B {pos_b:+.8f}，"
                    "请先手工平掉再冒烟"
                )
                return 1

        if not skip_open:
            opened = await asyncio.to_thread(
                lambda: broker.execute(ledger, 1, reduce_only=False)
            )
            _print_layer("开一层", opened)
            if not opened.ok:
                return 1
        else:
            ledger.pos_a = float(pos_a)
            ledger.pos_b = float(pos_b)

        closed = await asyncio.to_thread(
            lambda: broker.execute(ledger, -1, reduce_only=True)
        )
        _print_layer("平一层", closed)
        print(
            f"\n账本    state={ledger.state} lots={ledger.lots} "
            f"纸 {ledger.pos_a:+.6g}/{ledger.pos_b:+.6g}"
        )
        print(f"所仓    A {broker._pos('a'):+.8f} / B {broker._pos('b'):+.8f}")
        if not closed.ok:
            return 1
        if abs(Decimal(str(ledger.pos_a))) > Decimal("1e-8") or abs(
            Decimal(str(ledger.pos_b))
        ) > Decimal("1e-8"):
            print("警告    账本未回到空仓")
            return 1
        print("结果    双腿开平完成，账本空仓")
        return 0
    finally:
        stop.set()
        try:
            await asyncio.wait_for(
                asyncio.gather(feed_a, feed_b, return_exceptions=True),
                timeout=3.0,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            feed_a.cancel()
            feed_b.cancel()
            await asyncio.gather(feed_a, feed_b, return_exceptions=True)


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
