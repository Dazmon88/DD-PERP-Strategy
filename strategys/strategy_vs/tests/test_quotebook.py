"""QuoteBook 的 WSS 推送唤醒机制。

跑法（仓库根目录）:
  venv/bin/python -m pytest strategys/strategy_vs/tests/test_quotebook.py -q
  venv/bin/python strategys/strategy_vs/tests/test_quotebook.py
"""
import asyncio
import sys
import time
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]   # feeds 会 import adapters.*
for _p in (str(STRATEGY_DIR), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from feeds import Quote, QuoteBook  # noqa: E402


def q(venue="a:BTC", bid=100.0, ask=100.1, ts=None):
    return Quote(venue=venue, exchange="x", symbol="BTC", bid=bid, ask=ask,
                 bid_sz=1.0, ask_sz=1.0, ts=ts or time.time(), source="wss")


def run(coro):
    return asyncio.run(coro)


def test_update_wakes_waiter_immediately():
    async def main():
        book = QuoteBook()

        async def push():
            await asyncio.sleep(0.02)
            await book.update(q())

        t0 = time.perf_counter()
        asyncio.create_task(push())
        woke = await book.wait_update(timeout=5.0)
        return woke, time.perf_counter() - t0

    woke, elapsed = run(main())
    assert woke is True
    assert elapsed < 0.5, f"应被推送唤醒而不是等满超时，实际 {elapsed:.3f}s"


def test_touch_also_wakes():
    async def main():
        book = QuoteBook()
        await book.update(q())

        async def push():
            await asyncio.sleep(0.02)
            await book.touch("a:BTC", time.time())

        asyncio.create_task(push())
        return await book.wait_update(timeout=5.0)

    assert run(main()) is True


def test_touch_on_unknown_venue_does_not_wake():
    """没有实际更新就不该唤醒，否则会空转。"""
    async def main():
        book = QuoteBook()

        async def push():
            await asyncio.sleep(0.02)
            await book.touch("b:NOPE", time.time())

        asyncio.create_task(push())
        return await book.wait_update(timeout=0.15)

    assert run(main()) is False


def test_timeout_returns_false():
    async def main():
        book = QuoteBook()
        t0 = time.perf_counter()
        woke = await book.wait_update(timeout=0.1)
        return woke, time.perf_counter() - t0

    woke, elapsed = run(main())
    assert woke is False
    assert elapsed >= 0.09


def test_counts_every_push():
    async def main():
        book = QuoteBook()
        for i in range(5):
            await book.update(q(bid=100.0 + i))
        await book.touch("a:BTC", time.time())
        return book.updates

    assert run(main()) == 6


def test_consecutive_waits_each_need_a_push():
    """连续两次等待都必须各自被推送唤醒，事件不能粘住。"""
    async def main():
        book = QuoteBook()

        async def push_twice():
            await asyncio.sleep(0.02)
            await book.update(q(bid=101.0))
            await asyncio.sleep(0.05)
            await book.update(q(bid=102.0))

        asyncio.create_task(push_twice())
        first = await book.wait_update(timeout=1.0)
        second = await book.wait_update(timeout=1.0)
        third = await book.wait_update(timeout=0.1)   # 没有第三次推送
        return first, second, third

    first, second, third = run(main())
    assert first is True
    assert second is True
    assert third is False


def test_snapshot_still_isolated():
    async def main():
        book = QuoteBook()
        await book.update(q())
        snap = await book.snapshot()
        await book.update(q(bid=999.0))
        return snap["a:BTC"].bid, (await book.snapshot())["a:BTC"].bid

    old, new = run(main())
    assert old == 100.0 and new == 999.0


def test_error_update_keeps_last_bbo():
    """断线错误包不带盘口时，必须留下上次买一卖一，否则只平路径会 float(None)。"""
    async def main():
        book = QuoteBook()
        await book.update(q(bid=100.0, ask=100.1))
        await book.update(
            Quote(
                venue="a:BTC",
                exchange="x",
                symbol="BTC",
                error="no close frame received",
                ts=time.time(),
                source="wss",
            )
        )
        got = (await book.snapshot())["a:BTC"]
        return got.bid, got.ask, got.error

    bid, ask, err = run(main())
    assert bid == 100.0 and ask == 100.1
    assert "close frame" in err


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} 项全部通过")
