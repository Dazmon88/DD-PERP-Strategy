"""带宽时间采样、资金费只平、一层未齐收尾。

跑法（仓库根目录）:
  venv/bin/python -m pytest strategys/strategy_vs/tests/test_exec_guards.py -q
"""
from __future__ import annotations

import asyncio
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

STRATEGY_DIR = Path(__file__).resolve().parents[1]
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from decimal import Decimal

from accounts import AccountBook, AccountSnap, ThreadWake, parse_popdex_fills  # noqa: E402
from hedge import DualLegBroker, ahead_pos, layer_finish_kind  # noqa: E402
from spread import (  # noqa: E402
    SpreadWindow,
    _in_circular_range,
    flatten_block_reason,
)


def test_window_skips_ticks_inside_interval():
    w = SpreadWindow(maxlen=100, min_interval_sec=0.5)
    w.add(1.0, now=1000.0)
    w.add(2.0, now=1000.2)
    w.add(3.0, now=1000.5)
    assert [p for _, p in w._samples] == [1.0, 3.0]


def test_window_load_thins_dense_history():
    w = SpreadWindow(maxlen=100, min_interval_sec=1.0)
    rows = [[1000.0 + i * 0.1, float(i)] for i in range(50)]
    n = w.load(rows)
    assert n == 5
    assert w._samples[0][0] == 1000.0
    assert w._samples[-1][0] == 1004.0


def test_funding_window_around_utc_midnight():
    cfg = {
        "funding_hours_utc": [0, 8, 16],
        "minutes_before": 20,
        "minutes_after": 10,
    }
    in_ts = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc).timestamp()
    early = datetime(2026, 8, 26, 23, 40, tzinfo=timezone.utc).timestamp()
    late = datetime(2026, 8, 27, 0, 9, tzinfo=timezone.utc).timestamp()
    out_ts = datetime(2026, 8, 27, 0, 10, tzinfo=timezone.utc).timestamp()
    noon = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc).timestamp()
    assert "资金费00:00UTC前后只平" in flatten_block_reason(cfg, in_ts)
    assert flatten_block_reason(cfg, early)
    assert flatten_block_reason(cfg, late)
    assert flatten_block_reason(cfg, out_ts) == ""
    assert flatten_block_reason(cfg, noon) == ""


def test_circular_hour_range():
    assert _in_circular_range(23, 23, 8, 24)
    assert _in_circular_range(0, 23, 8, 24)
    assert _in_circular_range(7, 23, 8, 24)
    assert not _in_circular_range(8, 23, 8, 24)
    assert not _in_circular_range(12, 23, 8, 24)


def test_layer_finish_never_adopts_reverse():
    assert layer_finish_kind(want_n=-1, got_n=-1, hedged=True, b_moved=True) == "ok"
    # 减仓 1→-1：对锁但层数反了，必须拧平
    assert layer_finish_kind(want_n=0, got_n=-1, hedged=True, b_moved=True) == "unwind"
    assert layer_finish_kind(want_n=-1, got_n=1, hedged=True, b_moved=True) == "unwind"
    assert layer_finish_kind(want_n=-1, got_n=None, hedged=False, b_moved=True) == "unwind"
    assert layer_finish_kind(want_n=-1, got_n=None, hedged=False, b_moved=False) == "abort"


def test_ahead_pos_uses_whichever_is_further_along():
    assert ahead_pos(Decimal("0"), Decimal("0.001"), "buy") == Decimal("0.001")
    assert ahead_pos(Decimal("0.001"), Decimal("0"), "buy") == Decimal("0.001")
    assert ahead_pos(Decimal("0"), Decimal("-0.001"), "sell") == Decimal("-0.001")
    assert ahead_pos(Decimal("-0.001"), Decimal("0"), "sell") == Decimal("-0.001")


def test_parse_popdex_fills_skips_snapshot_and_reads_exec():
    snap = {"action": "snapshot", "data": [{"symbol": "BTC-USDT", "side": "buy", "fillQty": "0.001", "execId": "1"}]}
    assert parse_popdex_fills(snap) == []
    live = {
        "action": "update",
        "data": [
            {"symbol": "BTC-USDT", "side": "sell", "execQty": "0.001", "execId": "abc"},
            {"symbol": "ETH-USDT", "orderSide": "buy", "qty": "0.01", "fillId": "def"},
        ],
    }
    got = parse_popdex_fills(live)
    assert got == [
        {"symbol": "BTC-USDT", "signed": -0.001, "fill_id": "abc"},
        {"symbol": "ETH-USDT", "signed": 0.01, "fill_id": "def"},
    ]


def test_fill_tape_dedupes_and_sums_since():
    book = AccountBook()
    assert book.ingest_fill("b:BTC-USDT", 0.001, "a", ts=100.0)
    assert not book.ingest_fill("b:BTC-USDT", 0.001, "a", ts=100.1)
    assert book.ingest_fill("b:BTC-USDT", 0.001, "b", ts=101.0)
    assert book.signed_fills_since("b:BTC-USDT", 100.5) == 0.001
    assert book.signed_fills_since("b:BTC-USDT", 99.0) == 0.002
    assert book.signed_fills_since("b:ETH-USDT", 0.0) == 0.0


def test_thread_wake_consumes_ping():
    wake = ThreadWake()
    wake.ping()
    assert wake.wait(0.0) is True
    assert wake.wait(0.0) is False


def test_ingest_fill_pings_thread_wake():
    book = AccountBook()
    wake = ThreadWake()
    book.set_thread_wake(wake)
    assert book.ingest_fill("b:BTC-USDT", 0.001, "a", ts=100.0)
    assert wake.wait(0.0) is True
    assert not book.ingest_fill("b:BTC-USDT", 0.001, "a", ts=100.1)
    assert wake.wait(0.0) is False


def test_apply_fill_pings_thread_wake():
    book = AccountBook()
    wake = ThreadWake()
    book.set_thread_wake(wake)
    assert book.apply_fill("a:BTC-USDT", 0.001) == 0.001
    assert wake.wait(0.0) is True


def test_position_patch_wakes_waiters():
    async def main():
        book = AccountBook()
        wake = ThreadWake()
        book.set_thread_wake(wake)

        async def waiter():
            return await book.wait_update(1.0)

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)
        await book.patch(
            AccountSnap(venue="b:BTC-USDT", pos_qty=0.001, source="wss", ts=1.0)
        )
        assert await task is True
        assert wake.wait(0.0) is True

        await book.patch(
            AccountSnap(venue="a:BTC-USDT", equity=100.0, available=80.0, source="wss", ts=2.0)
        )
        assert wake.wait(0.0) is False

    asyncio.run(main())


def test_hedge_idle_wakes_on_fill_ping():
    wake = ThreadWake()
    broker = DualLegBroker(
        MagicMock(),
        MagicMock(),
        "BTC",
        "BTC-USDT",
        poll_sec=2.0,
        wake=wake,
    )
    threading.Timer(0.02, wake.ping).start()
    t0 = time.perf_counter()
    broker._idle()
    assert time.perf_counter() - t0 < 0.5


def test_hedge_stop_unblocks_idle():
    wake = ThreadWake()
    broker = DualLegBroker(
        MagicMock(),
        MagicMock(),
        "BTC",
        "BTC-USDT",
        poll_sec=2.0,
        wake=wake,
    )
    threading.Timer(0.02, broker.request_stop).start()
    t0 = time.perf_counter()
    broker._idle()
    assert time.perf_counter() - t0 < 0.5

