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
from ledger import PositionLedger  # noqa: E402
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
    assert layer_finish_kind(before_n=-1, got_n=-1, hedged=True, b_moved=True) == "ok"
    # 动手前 +1，所仓对锁在 -1：翻向才拧
    assert layer_finish_kind(before_n=1, got_n=-1, hedged=True, b_moved=True) == "unwind"
    assert layer_finish_kind(before_n=-1, got_n=1, hedged=True, b_moved=True) == "unwind"
    # 对不上：补 A，不拆 B
    assert layer_finish_kind(before_n=-1, got_n=None, hedged=False, b_moved=True) == "abort"
    assert layer_finish_kind(before_n=-1, got_n=None, hedged=False, b_moved=False) == "abort"


def test_layer_finish_adopts_exchange_lots_not_target():
    """想加到 -5、所仓已对锁在 -4：认 4 层，不拧。重启后也只看所仓。"""
    assert layer_finish_kind(before_n=-4, got_n=-4, hedged=True, b_moved=True) == "ok"
    assert layer_finish_kind(before_n=-4, got_n=-5, hedged=True, b_moved=True) == "ok"
    assert layer_finish_kind(before_n=0, got_n=-2, hedged=True, b_moved=True) == "ok"
    assert layer_finish_kind(before_n=2, got_n=0, hedged=True, b_moved=True) == "ok"


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


def test_sticky_wss_zero_is_trusted():
    """RH 仓位 WSS 报 0 应立刻显示空仓，不能被对腿粘性挡住。"""

    async def main():
        book = AccountBook()
        book.set_peers({"a:ANTH": "b:ANTH", "b:ANTH": "a:ANTH"})
        await book.patch(AccountSnap(venue="a:ANTH", pos_qty=0.026, source="wss", ts=1.0))
        await book.patch(AccountSnap(venue="b:ANTH", pos_qty=0.2, source="rest", ts=1.0))
        await book.patch(AccountSnap(venue="a:ANTH", pos_qty=0.0, source="wss", ts=2.0))
        assert book.latest()["a:ANTH"].pos_qty == 0.0
        assert abs(book.latest()["b:ANTH"].pos_qty - 0.2) < 1e-12

    asyncio.run(main())


def test_sticky_rest_zero_needs_peer_raw_zero():
    """Hype REST 单独闪 0 不得盖掉仓；两边 raw 都是 0 才能清粘性。"""

    async def main():
        book = AccountBook()
        book.set_peers({"a:ANTH": "b:ANTH", "b:ANTH": "a:ANTH"})
        await book.patch(AccountSnap(venue="a:ANTH", pos_qty=0.026, source="wss", ts=1.0))
        await book.patch(AccountSnap(venue="b:ANTH", pos_qty=0.2, source="rest", ts=1.0))
        await book.patch(AccountSnap(venue="b:ANTH", pos_qty=0.0, source="rest", ts=2.0))
        assert abs(book.latest()["b:ANTH"].pos_qty - 0.2) < 1e-12
        await book.patch(AccountSnap(venue="a:ANTH", pos_qty=0.0, source="wss", ts=3.0))
        await book.patch(AccountSnap(venue="b:ANTH", pos_qty=0.0, source="rest", ts=4.0))
        assert book.latest()["a:ANTH"].pos_qty == 0.0
        assert book.latest()["b:ANTH"].pos_qty == 0.0

    asyncio.run(main())


def test_sticky_manual_flat_both_rest_does_not_deadlock():
    """两所都 REST 报 0：即使用粘性显示还非 0，第二腿 raw 0 应一次清掉两边。"""

    async def main():
        book = AccountBook()
        book.set_peers({"a:ANTH": "b:ANTH", "b:ANTH": "a:ANTH"})
        await book.patch(AccountSnap(venue="a:ANTH", pos_qty=0.026, source="rest", ts=1.0))
        await book.patch(AccountSnap(venue="b:ANTH", pos_qty=0.2, source="rest", ts=1.0))
        await book.patch(AccountSnap(venue="a:ANTH", pos_qty=0.0, source="rest", ts=2.0))
        assert abs(book.latest()["a:ANTH"].pos_qty - 0.026) < 1e-12
        await book.patch(AccountSnap(venue="b:ANTH", pos_qty=0.0, source="rest", ts=3.0))
        assert book.latest()["a:ANTH"].pos_qty == 0.0
        assert book.latest()["b:ANTH"].pos_qty == 0.0

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


def test_yield_inband_does_not_touch_a():
    """回带让出时，即使 fill_since/所仓报 0，也不得市价打 A。"""
    pos = {"a": Decimal("0.1"), "b": Decimal("-0.1")}
    adapter_a = MagicMock()
    adapter_b = MagicMock()
    adapter_b.get_market_filters.return_value = {
        "base_inc": Decimal("0.0001"),
        "quote_inc": Decimal("0.1"),
        "min_size": Decimal("0.0001"),
    }
    adapter_b.get_position.return_value = MagicMock(signed_qty=0, quantity=0, side="net")

    ledger = PositionLedger(qty_per_layer=0.1, live=True, max_lots=2)
    ledger.accounts_ready = True
    ledger.pos_a = 0.1
    ledger.pos_b = -0.1

    broker = DualLegBroker(
        adapter_a,
        adapter_b,
        "SNDK",
        "io:SNDK",
        live=True,
        b_maker=True,
        timeout_sec=3.0,
        poll_sec=0.05,
        pos_lookup=lambda which: pos[which],
        fill_since=lambda _t0: Decimal("0.1"),
        rest_ok=lambda: False,
    )
    result = broker.execute(ledger, -1, rest_ok=lambda: False)
    assert result.note == "让出执行"
    assert "未动A" in " ".join(str(x) for x in result.logs)
    adapter_a.place_order.assert_not_called()
    assert pos["a"] == Decimal("0.1")
    assert pos["b"] == Decimal("-0.1")


def test_ahead_pos_buy_zero_must_not_override_short():
    """所仓 REST 空/0 在买方向上比空单 -0.1 更「靠前」，收尾绝不能用这个去平 A。"""
    assert ahead_pos(Decimal("0"), Decimal("-0.1"), "buy") == Decimal("0")


def test_residual_counts_as_one_lot_and_closes_actual_qty():
    """一层 0.03、残仓 0.01：仍算 ±1 层，减仓按 0.01 收，不开/不平一整层。"""
    ledger = PositionLedger(qty_per_layer=0.03, live=True, max_lots=2)
    ledger.accounts_ready = True
    ledger.pos_a = 0.01
    ledger.pos_b = -0.01
    assert ledger.lots == 1
    assert ledger.is_reduce(-1)
    assert abs(ledger.layer_qty(-1) - 0.01) < 1e-12
    assert abs(ledger.layer_qty(1) - 0.03) < 1e-12
    cloid_a, cloid_b = ledger.submit_layer(-1)
    assert cloid_a is not None and cloid_b is not None
    assert abs(ledger.orders[cloid_a].qty - 0.01) < 1e-12
    assert abs(ledger.orders[cloid_b].qty - 0.01) < 1e-12


def test_fit_b_qty_reduce_does_not_bump_dust():
    """减仓残量不得按最小量上抬：0.01 不能抬成 0.03。"""
    adapter_b = MagicMock()
    adapter_b.get_market_filters.return_value = {
        "base_inc": Decimal("0.01"),
        "quote_inc": Decimal("0.01"),
        "min_size": Decimal("0.03"),
    }
    broker = DualLegBroker(
        MagicMock(),
        adapter_b,
        "QQQ",
        "QQQ-USD.P",
        live=True,
        b_maker=True,
    )
    assert broker._fit_b_qty(Decimal("0.01"), reduce=True) == Decimal("0.01")
    assert broker._fit_b_qty(Decimal("0.01"), reduce=False) == Decimal("0.03")


def test_reconcile_flat_adopts_even_if_fill_ts_ahead():
    """手动平仓后两所都是 0：即使仓位时间戳落后成交，也要认领空仓，不能幽灵持有。"""
    ledger = PositionLedger(qty_per_layer=0.02, live=True, max_lots=10)
    ledger.accounts_ready = True
    ledger.pos_a = -0.2
    ledger.pos_b = 0.2
    ledger.exch_a0 = -0.2
    ledger.exch_b0 = 0.2
    ledger.last_fill_ts = 1_000.0
    assert ledger.lots == -10
    ok = ledger.reconcile(0.0, 0.0, ts_a=900.0, ts_b=900.0, now=1_001.0, live=True)
    assert ok
    assert ledger.lots == 0
    assert abs(ledger.pos_a) < 1e-12
    assert abs(ledger.pos_b) < 1e-12
    assert "持仓" in (ledger.note or "")


def test_lots_follow_exchange_when_idle():
    """空闲实盘层数跟所仓：本地幽灵仓不能挡住空仓/实仓。"""
    ledger = PositionLedger(qty_per_layer=0.02, live=True, max_lots=10)
    ledger.pos_a = -0.2
    ledger.pos_b = 0.2
    ledger.last_exch_a = 0.0
    ledger.last_exch_b = 0.0
    assert ledger.lots == 0
    ledger.last_exch_a = -0.04
    ledger.last_exch_b = 0.04
    assert ledger.lots == -2


def test_restart_reconcile_adopts_exchange_lots():
    """重启后账本从 0 开始，第一次对账按所仓认层，不会当空仓再开。"""
    ledger = PositionLedger(qty_per_layer=0.02, live=True, max_lots=10)
    assert ledger.lots == 0
    ok = ledger.reconcile(-0.04, 0.04, ts_a=1.0, ts_b=1.0, live=True)
    assert ok
    assert ledger.lots == -2
    assert abs(ledger.pos_a + 0.04) < 1e-12
    assert abs(ledger.pos_b - 0.04) < 1e-12


def test_full_layer_gap_is_not_hedged():
    """一整层敞口不是对锁：A −0.12 / B +0.09 不能认成 4 层。"""
    ledger = PositionLedger(qty_per_layer=0.03, live=True, max_lots=10)
    assert ledger._hedge_from_exchange(-0.12, 0.12) == (-0.12, 0.12)
    assert ledger.signed_lots(-0.12, 0.12) == -4
    assert ledger._hedge_from_exchange(-0.12, 0.09) is None
    assert ledger.signed_lots(-0.12, 0.09) == -4


def test_restart_lots_ignore_local_memory():
    """本地还记着满仓，所仓是 0：层数跟所仓，重启不会按内存再开。"""
    ledger = PositionLedger(qty_per_layer=0.03, live=True, max_lots=10)
    ledger.pos_a = -0.3
    ledger.pos_b = 0.3
    ledger.last_exch_a = 0.0
    ledger.last_exch_b = 0.0
    assert ledger.lots == 0
    ledger.last_exch_a = -0.09
    ledger.last_exch_b = 0.09
    assert ledger.lots == -3

