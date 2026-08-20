"""
双腿一层：B 所按 role 吃单（Maker 挂 best，Taker 市价），仓位增量再让 A 市价对冲。
Maker 只在带外挂；回到带内则撤单等待。best 远离我方则撤了再跟。
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from ledger import PositionLedger


def _d(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def signed_pos(adapter: Any, symbol: str) -> Decimal:
    pos = adapter.get_position(symbol)
    if pos is None or _d(pos.size) == 0:
        return Decimal("0")
    size = abs(_d(pos.size))
    side = str(getattr(pos, "side", "") or "").lower()
    return -size if side in ("short", "sell") else size


def _filled_along(before: Decimal, now: Decimal, side: str, qty: Decimal) -> Decimal:
    diff = now - before
    along = diff if side == "buy" else -diff
    if along < 0:
        along = Decimal("0")
    return min(qty, along)


def _bbo(adapter: Any, symbol: str) -> tuple[Optional[Decimal], Optional[Decimal]]:
    bid = ask = None
    try:
        ticker = adapter.get_ticker(symbol) or {}
        bid = ticker.get("bid_price", ticker.get("bid"))
        ask = ticker.get("ask_price", ticker.get("ask"))
    except Exception:
        ticker = {}
    if bid is None or ask is None:
        try:
            book = adapter.get_orderbook(symbol, depth=1) or {}
            bids = book.get("bids") or []
            asks = book.get("asks") or []
            if bid is None and bids:
                bid = bids[0][0] if isinstance(bids[0], (list, tuple)) else bids[0]
            if ask is None and asks:
                ask = asks[0][0] if isinstance(asks[0], (list, tuple)) else asks[0]
        except Exception:
            pass
    return (
        _d(bid) if bid not in (None, "") else None,
        _d(ask) if ask not in (None, "") else None,
    )


def _touch(side: str, bid: Optional[Decimal], ask: Optional[Decimal]) -> Optional[Decimal]:
    return bid if side == "buy" else ask


def _should_chase(side: str, our_px: Decimal, bid: Decimal, ask: Decimal) -> bool:
    """只追远离我的一侧：买则 bid 上涨，卖则 ask 下跌。best 就是我的价则不追。"""
    tick = ask - bid
    if tick <= 0:
        tick = max(our_px * Decimal("1e-8"), Decimal("1e-8"))
    half = tick / Decimal("2")
    if side == "buy":
        return bid > our_px + half
    return ask < our_px - half


def _place_maker(
    adapter: Any,
    *,
    symbol: str,
    side: str,
    qty: Decimal,
    price: Decimal,
) -> tuple[Any, str]:
    """B 所只挂 post_only GTC。Ondo 的 reduce_only 只能配 IOC，这里绝不带。"""
    try:
        order = adapter.place_order(
            symbol=symbol,
            side=side,
            order_type="limit",
            quantity=qty,
            price=price,
            time_in_force="gtc",
            reduce_only=False,
            post_only=True,
        )
        return order, ""
    except Exception as exc:
        return None, str(exc)


def _maker_fatal(err: str) -> bool:
    text = (err or "").lower()
    return "reduce_only" in text or "invalid_tif" in text


def _place_taker(
    adapter: Any,
    *,
    symbol: str,
    side: str,
    qty: Decimal,
    reduce_only: bool,
) -> tuple[Any, str]:
    try:
        order = adapter.place_order(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=qty,
            time_in_force="ioc",
            reduce_only=reduce_only,
            post_only=False,
        )
        return order, ""
    except Exception as exc:
        return None, str(exc)


def _cancel(adapter: Any, order_id: str) -> None:
    if not order_id:
        return
    try:
        adapter.cancel_order(order_id=order_id)
    except Exception:
        pass


@dataclass
class LegSnap:
    venue: str
    symbol: str
    side: str
    before: Decimal
    expect: Decimal
    after: Decimal = Decimal("0")
    filled: bool = False
    order_id: str = ""
    error: str = ""


@dataclass
class LayerResult:
    ok: bool
    delta: int
    a: LegSnap
    b: LegSnap
    flattened: bool = False
    error: str = ""
    note: str = ""
    logs: list[str] = field(default_factory=list)


class DualLegBroker:
    """B 所按 role 执行；仓位有增量后 A 所市价补差。"""

    def __init__(
        self,
        adapter_a: Any,
        adapter_b: Any,
        symbol_a: str,
        symbol_b: str,
        *,
        timeout_sec: float = 20.0,
        poll_sec: float = 0.05,
        live: bool = False,
        b_maker: bool = True,
        max_rejects: int = 12,
        max_chase: int = 8,
        log: Optional[Callable[[str], None]] = None,
        pos_lookup: Optional[Callable[[str], Optional[Decimal]]] = None,
        bbo_lookup: Optional[Callable[[], tuple[Optional[Decimal], Optional[Decimal]]]] = None,
        rest_ok: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.adapter_a = adapter_a
        self.adapter_b = adapter_b
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.timeout_sec = float(timeout_sec)
        self.poll_sec = float(poll_sec)
        self.live = bool(live)
        self.b_maker = bool(b_maker)
        self.max_rejects = max(1, int(max_rejects))
        self.max_chase = max(0, int(max_chase))
        self._log = log or (lambda _msg: None)
        self._pos_lookup = pos_lookup
        self._bbo_lookup = bbo_lookup
        self._rest_ok = rest_ok
        self.qty_per_layer: float = 0.0

    def _pos(self, which: str) -> Decimal:
        if self._pos_lookup is not None:
            got = self._pos_lookup(which)
            if got is not None:
                return _d(got)
        adapter = self.adapter_a if which == "a" else self.adapter_b
        symbol = self.symbol_a if which == "a" else self.symbol_b
        return signed_pos(adapter, symbol)

    def _quotes_b(self) -> tuple[Optional[Decimal], Optional[Decimal]]:
        if self._bbo_lookup is not None:
            bid, ask = self._bbo_lookup()
            if bid is not None and ask is not None:
                return _d(bid), _d(ask)
        return _bbo(self.adapter_b, self.symbol_b)

    def execute(
        self,
        ledger: PositionLedger,
        delta: int,
        *,
        reduce_only: bool = False,
        rest_ok: Optional[Callable[[], bool]] = None,
    ) -> LayerResult:
        if delta not in (-1, 1):
            return self._fail_empty(delta, "delta 只能是 ±1")
        self.qty_per_layer = ledger.qty_per_layer
        qty = Decimal(str(ledger.qty_per_layer))
        side_a = "buy" if delta > 0 else "sell"
        side_b = "sell" if delta > 0 else "buy"
        before_a = self._pos("a")
        before_b = self._pos("b")
        signed_a = qty if side_a == "buy" else -qty
        signed_b = qty if side_b == "buy" else -qty
        target_a = before_a + signed_a   # A 最终目标仓位
        snap_a = LegSnap("a", self.symbol_a, side_a, before_a, target_a)
        snap_b = LegSnap("b", self.symbol_b, side_b, before_b, before_b + signed_b)
        result = LayerResult(ok=False, delta=delta, a=snap_a, b=snap_b)

        cloids = ledger.submit_layer(delta)
        if cloids[0] is None or cloids[1] is None:
            result.error = ledger.last_error or "锁层失败"
            result.note = result.error
            return result
        cloid_a, cloid_b = cloids
        style = "Maker" if self.b_maker else "市价"
        result.logs.append(f"锁层 {delta:+d} 账本={ledger.state} B={side_b} {style} / A={side_a} 市价")

        if not self.live:
            ledger.abort_layer("dry-run")
            result.ok = True
            result.note = "dry-run"
            result.logs.append("dry-run 未下单")
            return result

        tol = max(qty * Decimal("0.05"), Decimal("1e-8"))
        deadline = time.time() + self.timeout_sec
        order_id = ""
        our_px: Optional[Decimal] = None
        rejects = 0
        chases = 0
        allow_rest = rest_ok if rest_ok is not None else self._rest_ok
        waiting_band = False
        last_taker = 0.0
        last_align_ts = 0.0          # A 上次下单时间，冷却 hedge_cooldown_sec
        hedge_cooldown_sec = 5.0

        try:
            while time.time() < deadline:
                pos_b = self._pos("b")
                # A 绝对对齐：target_a = -pos_b（两腿反号等量）
                # 用 -pos_b 而不是固定 target_a，这样 B 部分成交时 A 也跟着变
                cur_target_a = -pos_b
                pos_a = self._pos("a")
                gap_a = cur_target_a - pos_a
                snap_a.after = pos_a
                snap_b.after = pos_b

                a_aligned = abs(gap_a) <= tol
                b_done = abs(pos_b - (before_b + signed_b)) <= tol

                if a_aligned and b_done:
                    break

                # A 对冲：每 hedge_cooldown_sec 最多触发一次
                if not a_aligned and time.time() - last_align_ts >= hedge_cooldown_sec:
                    side = "buy" if gap_a > 0 else "sell"
                    order, err = _place_taker(
                        self.adapter_a,
                        symbol=self.symbol_a,
                        side=side,
                        qty=abs(gap_a),
                        reduce_only=False,
                    )
                    if err:
                        result.a.error = err
                        result.logs.append(f"A 对冲失败 {err}")
                    else:
                        oid = str(getattr(order, "order_id", "") or "")
                        result.a.order_id = oid or result.a.order_id
                        result.logs.append(
                            f"A {side} 对齐 {abs(gap_a)} target={cur_target_a:+.8f} id={oid}"
                        )
                    last_align_ts = time.time()

                # B 挂单逻辑（B 已齐时跳过）
                remain = abs(before_b + signed_b - pos_b)
                if remain <= tol:
                    time.sleep(self.poll_sec)
                    continue

                if self.b_maker and allow_rest is not None and not allow_rest():
                    if order_id:
                        result.logs.append(f"价差回带内，撤 {order_id} 等待")
                        _cancel(self.adapter_b, order_id)
                        order_id = ""
                        our_px = None
                    elif not waiting_band:
                        result.logs.append("价差在带内，等待出带再挂")
                    waiting_band = True
                    time.sleep(self.poll_sec)
                    continue
                waiting_band = False

                if not self.b_maker:
                    if time.time() - last_taker < 0.4:
                        time.sleep(self.poll_sec)
                        continue
                    last_taker = time.time()
                    order, err = _place_taker(
                        self.adapter_b,
                        symbol=self.symbol_b,
                        side=side_b,
                        qty=remain,
                        reduce_only=reduce_only,
                    )
                    if err or order is None:
                        rejects += 1
                        snap_b.error = err
                        result.logs.append(
                            f"B 市价失败 {err or '无单'} 重试 {rejects}/{self.max_rejects}"
                        )
                        if rejects >= self.max_rejects:
                            result.error = "B 市价多次失败"
                            break
                        time.sleep(self.poll_sec)
                        continue
                    rejects = 0
                    oid = str(getattr(order, "order_id", "") or "")
                    snap_b.order_id = oid or snap_b.order_id
                    result.logs.append(f"B {side_b} 市价 remain={remain} id={oid}")
                    time.sleep(self.poll_sec)
                    continue

                bid, ask = self._quotes_b()
                if bid is None or ask is None:
                    if not result.logs or result.logs[-1] != "B 盘口空，等待":
                        result.logs.append("B 盘口空，等待")
                    time.sleep(self.poll_sec)
                    continue
                touch = _touch(side_b, bid, ask)
                if touch is None or touch <= 0:
                    time.sleep(self.poll_sec)
                    continue

                if order_id and our_px is not None and _should_chase(side_b, our_px, bid, ask):
                    if chases >= self.max_chase:
                        result.logs.append(f"追价次数用尽 {chases}")
                        break
                    result.logs.append(f"追价 撤 {order_id} {our_px} → {touch}")
                    _cancel(self.adapter_b, order_id)
                    order_id = ""
                    our_px = None
                    chases += 1
                    continue

                if order_id:
                    time.sleep(self.poll_sec)
                    continue

                order, err = _place_maker(
                    self.adapter_b,
                    symbol=self.symbol_b,
                    side=side_b,
                    qty=remain,
                    price=touch,
                )
                if err or order is None:
                    rejects += 1
                    snap_b.error = err
                    if _maker_fatal(err or ""):
                        result.error = f"B Maker 拒单不可重挂: {err}"
                        result.logs.append(result.error)
                        break
                    result.logs.append(f"B Maker 失败 {err or '无单'} 重挂 {rejects}/{self.max_rejects}")
                    if rejects >= self.max_rejects:
                        result.error = "B 挂单多次失败"
                        break
                    time.sleep(self.poll_sec)
                    continue
                rejects = 0
                order_id = str(getattr(order, "order_id", "") or "")
                our_px = touch
                snap_b.order_id = order_id
                result.logs.append(f"B {side_b} Maker {touch} remain={remain} id={order_id}")
                time.sleep(self.poll_sec)
        finally:
            if order_id:
                _cancel(self.adapter_b, order_id)

        # 收尾：再对齐一次 A
        pos_b = self._pos("b")
        pos_a = self._pos("a")
        cur_target_a = -pos_b
        snap_a.after = pos_a
        snap_b.after = pos_b
        result.logs.append(
            f"仓位 A {before_a:+.8f}→{pos_a:+.8f} B {before_b:+.8f}→{pos_b:+.8f}"
        )
        self._align_a(cur_target_a, result, label="收尾对冲")

        # 两腿齐：用仓位对齐判断
        pos_a = self._pos("a")
        snap_a.after = pos_a
        hedge = ledger._hedge_from_exchange(float(pos_a), float(pos_b))
        want_n = int(round(float(before_a + signed_a) / ledger.qty_per_layer))
        got_n = None if hedge is None else int(round(hedge[0] / ledger.qty_per_layer))
        if hedge is not None and got_n == want_n:
            ledger.on_fill(cloid_a, float(qty))
            ledger.on_fill(cloid_b, float(qty))
            result.ok = True
            result.note = "两腿成交"
            result.logs.append(f"账本 {ledger.state} lots={ledger.lots}")
            return result

        result.logs.append(
            f"仓不对齐 A {pos_a:+.8f} B {pos_b:+.8f} 期望层 {want_n:+d} 实层 {got_n}"
        )
        result.error = result.error or "一层未齐"
        result.flattened = True
        ledger.abort_layer("一层未齐")
        result.note = "一层未齐"
        return result

    def _align_a(
        self,
        target_a: Decimal,
        result: LayerResult,
        label: str = "对冲",
    ) -> bool:
        """让 A 仓位对齐到 target_a。返回 True 表示下单成功（或已对齐）。"""
        pos_a = self._pos("a")
        gap = target_a - pos_a
        tol = max(Decimal(str(self.qty_per_layer)) * Decimal("0.05"), Decimal("1e-8"))
        if abs(gap) <= tol:
            return True
        side = "buy" if gap > 0 else "sell"
        qty = abs(gap)
        order, err = _place_taker(
            self.adapter_a,
            symbol=self.symbol_a,
            side=side,
            qty=qty,
            reduce_only=False,
        )
        if err:
            result.a.error = err
            result.logs.append(f"A {label} 失败 {err}")
            return False
        oid = str(getattr(order, "order_id", "") or "")
        result.a.order_id = oid or result.a.order_id
        result.logs.append(f"A {label} {side} {qty} target={target_a:+.8f} id={oid}")
        return True

    def align_a_only(self, target_a: Decimal) -> tuple[bool, str]:
        """仅对齐 A 仓位到 target_a，不触碰账本层逻辑（用于后台敞口守护）。

        返回 (已对齐, 日志消息)。
        已对齐 = 当前仓位已在容差内（或下单成功）。
        """
        pos_a = self._pos("a")
        qty = Decimal(str(getattr(self, "qty_per_layer", None) or 0))
        if qty <= 0:
            return False, "qty_per_layer 未初始化"
        tol = max(qty * Decimal("0.05"), Decimal("1e-8"))
        gap = target_a - pos_a
        if abs(gap) <= tol:
            return True, f"A 已对齐 pos={pos_a:+.8f} target={target_a:+.8f}"
        side = "buy" if gap > 0 else "sell"
        order, err = _place_taker(
            self.adapter_a,
            symbol=self.symbol_a,
            side=side,
            qty=abs(gap),
            reduce_only=False,
        )
        if err:
            return False, f"A 对齐失败 {side} {abs(gap)} err={err}"
        oid = str(getattr(order, "order_id", "") or "")
        return True, f"A 对齐 {side} {abs(gap)} target={target_a:+.8f} id={oid}"

    def _fail_empty(self, delta: int, error: str) -> LayerResult:
        zero = Decimal("0")
        return LayerResult(
            ok=False,
            delta=delta,
            a=LegSnap("a", self.symbol_a, "", zero, zero),
            b=LegSnap("b", self.symbol_b, "", zero, zero),
            error=error,
            note=error,
        )
