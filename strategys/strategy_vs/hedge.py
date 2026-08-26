"""
双腿一层：B 所按 role 吃单（Maker 挂 best，Taker 市价），仓位增量再让 A 市价对冲。
Maker 只在带外挂；回到带内则撤单等待。best 远离我方则撤了再跟。
"""
from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
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


def _px_str(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _spread_tick(bid: Decimal, ask: Decimal) -> Decimal:
    mag = max(abs(bid), abs(ask), Decimal("1"))
    if mag >= 10000:
        return Decimal("0.1")
    if mag >= 200:
        return Decimal("0.01")
    return Decimal("0.01")


def _round_to_inc(value: Decimal, inc: Decimal, *, up: bool) -> Decimal:
    if value <= 0:
        return value
    if inc <= 0:
        return value
    n = (value / inc).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)
    out = n * inc
    if not up and out > value:
        out = (n - 1) * inc
    return out if out > 0 else inc if up else Decimal("0")


def _touch(
    side: str,
    bid: Optional[Decimal],
    ask: Optional[Decimal],
    *,
    extra_ticks: int = 0,
    quote_inc: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """买挂 bid、卖挂 ask；按品种 tick 取整，加密货币不能用价差当步进。"""
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return None
    tick = quote_inc if quote_inc is not None and quote_inc > 0 else _spread_tick(bid, ask)
    extra = max(0, int(extra_ticks))
    if side == "buy":
        px = bid - tick * extra
        if px >= ask:
            px = bid - tick * (extra + 1)
        px = _round_to_inc(px, tick, up=False)
    else:
        px = ask + tick * extra
        if px <= bid:
            px = ask + tick * (extra + 1)
        px = _round_to_inc(px, tick, up=True)
    return px if px > 0 else None


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
            quantity=_d(_px_str(qty)),
            price=_d(_px_str(price)),
            time_in_force="gtc",
            reduce_only=False,
            post_only=True,
        )
        return order, ""
    except Exception as exc:
        return None, str(exc)


def _maker_fatal(err: str) -> bool:
    text = (err or "").lower()
    if "post_only_has_match" in text or "would match" in text or "post only" in text:
        return False
    keys = (
        "reduce_only",
        "invalid_tif",
        "invalid_size",
        "min_size",
        "min_qty",
        "min_notional",
        "size_increment",
        "baseincrement",
        "invalid_price",
        "price_increment",
        "quoteincrement",
        "tick size",
        "too small",
        "precision",
    )
    return any(k in text for k in keys)


def _maker_would_take(err: str) -> bool:
    text = (err or "").lower()
    return "post_only_has_match" in text or "would match" in text or "would have immediately" in text


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


def _cancel(adapter: Any, order_id: str, symbol: str = "") -> None:
    if not order_id:
        return
    try:
        adapter.cancel_order(order_id=order_id, symbol=symbol or None)
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
    a_order_count: int = 0
    a_order_qty: Decimal = Decimal("0")
    a_order_log: list[str] = field(default_factory=list)

    def journal_fields(self) -> dict:
        """供 CSV 记录：A 下单明细 + 两所仓位快照。"""
        a_log = list(self.a_order_log) or [
            x for x in self.logs if x.startswith("A ")
        ]
        b_log = [x for x in self.logs if x.startswith("B ")]
        return {
            "pos_a_before": float(self.a.before),
            "pos_a_after": float(self.a.after),
            "pos_b_before": float(self.b.before),
            "pos_b_after": float(self.b.after),
            "a_side": self.a.side,
            "b_side": self.b.side,
            "a_order_id": self.a.order_id,
            "b_order_id": self.b.order_id,
            "a_order_count": int(self.a_order_count),
            "a_order_qty": float(self.a_order_qty),
            "a_order_log": " | ".join(a_log),
            "b_order_log": " | ".join(b_log[-8:]),
            "exec_log": " | ".join(self.logs[-16:]),
        }


class _TapList(list):
    """builtin list 在 3.11+ 不能改 append；用子类把每条日志同步写出。"""

    def __init__(self, log: Callable[[str], None], seq: Optional[list] = None) -> None:
        super().__init__(seq or [])
        self._log = log

    def append(self, msg: object) -> None:  # type: ignore[override]
        super().append(msg)
        try:
            self._log(str(msg))
        except Exception:
            pass


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
        pos_apply: Optional[Callable[[str, float], Any]] = None,
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
        self._pos_apply = pos_apply
        self._bbo_lookup = bbo_lookup
        self._rest_ok = rest_ok
        self.qty_per_layer: float = 0.0
        self._stop = threading.Event()
        self._working_lock = threading.Lock()
        self._working_oid = ""
        self._b_filters: Optional[dict] = None

    def _load_b_filters(self) -> dict:
        if self._b_filters is not None:
            return self._b_filters
        filters = {
            "base_inc": Decimal("0"),
            "quote_inc": Decimal("0"),
            "min_size": Decimal("0"),
        }
        getter = getattr(self.adapter_b, "get_market_filters", None)
        if callable(getter):
            try:
                got = getter(self.symbol_b) or {}
                for key in ("base_inc", "quote_inc", "min_size"):
                    val = got.get(key)
                    if val not in (None, ""):
                        filters[key] = _d(val)
            except Exception as exc:
                self._log(f"B 精度查询失败 {self.symbol_b}: {exc}")
        if filters["base_inc"] <= 0 or filters["quote_inc"] <= 0:
            name = (self.symbol_b or "").upper()
            if name.startswith("BTC"):
                filters["base_inc"] = filters["base_inc"] or Decimal("0.00001")
                filters["quote_inc"] = filters["quote_inc"] or Decimal("0.1")
                filters["min_size"] = filters["min_size"] or Decimal("0.0001")
            elif name.startswith("ETH"):
                filters["base_inc"] = filters["base_inc"] or Decimal("0.001")
                filters["quote_inc"] = filters["quote_inc"] or Decimal("0.01")
                filters["min_size"] = filters["min_size"] or Decimal("0.001")
            else:
                filters["base_inc"] = filters["base_inc"] or Decimal("0.01")
                filters["quote_inc"] = filters["quote_inc"] or Decimal("0.01")
                filters["min_size"] = filters["min_size"] or Decimal("0.01")
        self._b_filters = filters
        self._log(
            f"B 精度 {self.symbol_b} base={filters['base_inc']} "
            f"quote={filters['quote_inc']} min={filters['min_size']}"
        )
        return filters

    def _fit_b_qty(self, qty: Decimal) -> Decimal:
        filters = self._load_b_filters()
        inc = filters["base_inc"]
        min_size = filters["min_size"] or inc
        fitted = qty
        if inc > 0:
            fitted = _round_to_inc(qty, inc, up=True)
        if min_size > 0 and fitted < min_size:
            fitted = min_size
            if inc > 0:
                fitted = _round_to_inc(fitted, inc, up=True)
        return fitted

    def request_stop(self) -> None:
        """Ctrl+C：停循环并撤掉本对正在挂的 B 单。"""
        self._stop.set()
        oid = ""
        with self._working_lock:
            oid = self._working_oid
        if oid:
            _cancel(self.adapter_b, oid, self.symbol_b)

    def _set_working(self, order_id: str) -> None:
        with self._working_lock:
            self._working_oid = str(order_id or "")

    def _tap_logs(self, result: LayerResult) -> LayerResult:
        """result.logs 同步写到 DualLegBroker.log（vs_monitor 落 .log）。"""
        if not isinstance(result.logs, _TapList):
            result.logs = _TapList(self._log, list(result.logs))
        return result

    def _pos(self, which: str) -> Decimal:
        if self._pos_lookup is not None:
            got = self._pos_lookup(which)
            if got is not None:
                return _d(got)
        adapter = self.adapter_a if which == "a" else self.adapter_b
        symbol = self.symbol_a if which == "a" else self.symbol_b
        return signed_pos(adapter, symbol)

    def _credit_a(self, side: str, qty: Decimal) -> None:
        if self._pos_apply is None or qty <= 0:
            return
        signed = float(qty if side == "buy" else -qty)
        self._pos_apply("a", signed)

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
        result = self._tap_logs(LayerResult(ok=False, delta=delta, a=snap_a, b=snap_b))

        cloids = ledger.submit_layer(delta)
        if cloids[0] is None or cloids[1] is None:
            result.error = ledger.last_error or "锁层失败"
            result.note = result.error
            result.logs.append(result.error)
            return result
        cloid_a, cloid_b = cloids
        style = "Maker" if self.b_maker else "市价"
        result.logs.append(f"锁层 {delta:+d} 账本={ledger.state} B={side_b} {style} / A={side_a} 市价")
        self._load_b_filters()

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
        passive_ticks = 0
        allow_rest = rest_ok if rest_ok is not None else self._rest_ok
        last_taker = 0.0
        last_align_ts = 0.0          # A 上次下单时间，冷却 hedge_cooldown_sec
        hedge_cooldown_sec = 5.0
        yield_exec = False
        inband_since = 0.0

        try:
            while time.time() < deadline:
                if self._stop.is_set():
                    result.logs.append("进程退出，停止挂单")
                    break
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
                b_moved = abs(pos_b - before_b) > tol

                if a_aligned and b_done:
                    break

                # A 只在 B 本层有增量后才对冲，避免 WSS 假 0 空转
                if (
                    (not self._stop.is_set())
                    and b_moved
                    and not a_aligned
                    and time.time() - last_align_ts >= hedge_cooldown_sec
                ):
                    side = "buy" if gap_a > 0 else "sell"
                    qty_a = abs(gap_a)
                    order, err = _place_taker(
                        self.adapter_a,
                        symbol=self.symbol_a,
                        side=side,
                        qty=qty_a,
                        reduce_only=False,
                    )
                    if err:
                        result.a.error = err
                        msg = (
                            f"A 对冲失败 {side} {qty_a} "
                            f"pos_a={pos_a:+.8f} pos_b={pos_b:+.8f} "
                            f"target={cur_target_a:+.8f} err={err}"
                        )
                        result.logs.append(msg)
                        result.a_order_log.append(msg)
                    else:
                        oid = str(getattr(order, "order_id", "") or "")
                        result.a.order_id = oid or result.a.order_id
                        result.a_order_count += 1
                        result.a_order_qty += qty_a
                        self._credit_a(side, qty_a)
                        msg = (
                            f"A {side} {qty_a} "
                            f"pos_a={pos_a:+.8f}→target={cur_target_a:+.8f} "
                            f"pos_b={pos_b:+.8f} id={oid}"
                        )
                        result.logs.append(msg)
                        result.a_order_log.append(msg)
                    last_align_ts = time.time()

                # B 挂单逻辑（B 已齐时跳过）
                remain = abs(before_b + signed_b - pos_b)
                if remain <= tol:
                    time.sleep(self.poll_sec)
                    continue

                if self.b_maker and allow_rest is not None and not allow_rest():
                    if order_id:
                        result.logs.append(f"价差回带内，撤 {order_id} 让出")
                        _cancel(self.adapter_b, order_id, self.symbol_b)
                        order_id = ""
                        self._set_working("")
                        our_px = None
                        yield_exec = True
                        break
                    # 未挂单：给盘口抖 1.5s，避免 BTC 刚抢到通道就被 QQQ 立刻挤走
                    if inband_since <= 0:
                        inband_since = time.time()
                        result.logs.append("价差未出带，待挂")
                    elif time.time() - inband_since >= 1.5:
                        result.logs.append("价差未出带，未挂让出")
                        yield_exec = True
                        break
                    time.sleep(self.poll_sec)
                    continue
                inband_since = 0.0
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
                touch = _touch(
                    side_b,
                    bid,
                    ask,
                    extra_ticks=passive_ticks,
                    quote_inc=self._load_b_filters()["quote_inc"],
                )
                if touch is None or touch <= 0:
                    time.sleep(self.poll_sec)
                    continue

                if order_id and our_px is not None and _should_chase(side_b, our_px, bid, ask):
                    if chases >= self.max_chase:
                        result.logs.append(f"追价次数用尽 {chases}")
                        break
                    result.logs.append(f"追价 撤 {order_id} {our_px} → {touch}")
                    _cancel(self.adapter_b, order_id, self.symbol_b)
                    order_id = ""
                    self._set_working("")
                    our_px = None
                    chases += 1
                    continue

                if order_id:
                    time.sleep(self.poll_sec)
                    continue

                place_qty = self._fit_b_qty(remain)
                if place_qty <= 0:
                    result.error = f"B 数量无效 remain={remain}"
                    result.logs.append(result.error)
                    break
                if place_qty != remain:
                    result.logs.append(
                        f"B 数量 {remain} → {place_qty}（按步进/最小量）"
                    )
                order, err = _place_maker(
                    self.adapter_b,
                    symbol=self.symbol_b,
                    side=side_b,
                    qty=place_qty,
                    price=touch,
                )
                if err or order is None:
                    rejects += 1
                    snap_b.error = err
                    if _maker_fatal(err or ""):
                        result.error = f"B Maker 拒单不可重挂: {err}"
                        result.logs.append(result.error)
                        break
                    if _maker_would_take(err or ""):
                        passive_ticks += 1
                        result.logs.append(
                            f"B Maker 会吃单，退 {passive_ticks} tick 重挂 {err}"
                        )
                    else:
                        result.logs.append(
                            f"B Maker 失败 {err or '无单'} 重挂 {rejects}/{self.max_rejects}"
                        )
                    if rejects >= self.max_rejects:
                        result.error = "B 挂单多次失败"
                        break
                    time.sleep(self.poll_sec)
                    continue
                rejects = 0
                order_id = str(getattr(order, "order_id", "") or "")
                self._set_working(order_id)
                our_px = touch
                snap_b.order_id = order_id
                result.logs.append(
                    f"B {side_b} Maker {touch} remain={remain} "
                    f"pos_b={pos_b:+.8f} id={order_id}"
                )
                time.sleep(self.poll_sec)
        finally:
            if order_id:
                _cancel(self.adapter_b, order_id, self.symbol_b)
            self._set_working("")

        if self._stop.is_set():
            ledger.abort_layer("进程退出")
            result.ok = False
            result.error = ""
            result.note = "进程退出"
            result.flattened = False
            return result

        if yield_exec:
            ledger.abort_layer("让出执行")
            result.ok = False
            result.error = ""
            result.note = "让出执行"
            result.flattened = False
            return result

        # 收尾：B 有增量才再对齐 A（B 没动则不因假 0 去打 Lighter）
        pos_b = self._pos("b")
        pos_a = self._pos("a")
        cur_target_a = -pos_b
        snap_a.after = pos_a
        snap_b.after = pos_b
        result.logs.append(
            f"仓位 A {before_a:+.8f}→{pos_a:+.8f} B {before_b:+.8f}→{pos_b:+.8f}"
        )
        if abs(pos_b - before_b) > tol:
            self._align_a(cur_target_a, result, label="收尾对冲")

        # 两腿齐：用仓位对齐判断；成功/失败都优先按交易所绝对仓认领，避免账本归零叠仓
        pos_a = self._pos("a")
        snap_a.after = pos_a
        hedge = ledger._hedge_from_exchange(float(pos_a), float(pos_b))
        want_n = int(round(float(before_a + signed_a) / ledger.qty_per_layer))
        got_n = None if hedge is None else int(round(hedge[0] / ledger.qty_per_layer))
        if hedge is not None and got_n == want_n:
            ledger.adopt_exchange(float(pos_a), float(pos_b), note="两腿成交")
            result.ok = True
            result.note = "两腿成交"
            result.logs.append(f"账本 {ledger.state} lots={ledger.lots}")
            return result

        result.logs.append(
            f"仓不对齐 A {pos_a:+.8f} B {pos_b:+.8f} 期望层 {want_n:+d} 实层 {got_n}"
        )
        result.error = result.error or "一层未齐"
        # 对锁则认领真实仓，绝不 abort 成 0（否则网格会当空仓反复开）
        if ledger.adopt_exchange(
            float(pos_a), float(pos_b), note="一层未齐已认领"
        ):
            result.note = ledger.note or "一层未齐已认领"
            result.logs.append(result.note)
            result.flattened = False
            return result
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
        pos_b = self._pos("b")
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
            msg = (
                f"A {label}失败 {side} {qty} "
                f"pos_a={pos_a:+.8f} pos_b={pos_b:+.8f} "
                f"target={target_a:+.8f} err={err}"
            )
            result.logs.append(msg)
            result.a_order_log.append(msg)
            return False
        oid = str(getattr(order, "order_id", "") or "")
        result.a.order_id = oid or result.a.order_id
        result.a_order_count += 1
        result.a_order_qty += qty
        self._credit_a(side, qty)
        msg = (
            f"A {label} {side} {qty} "
            f"pos_a={pos_a:+.8f}→target={target_a:+.8f} "
            f"pos_b={pos_b:+.8f} id={oid}"
        )
        result.logs.append(msg)
        result.a_order_log.append(msg)
        return True

    def align_a_only(self, target_a: Decimal) -> tuple[bool, str, dict]:
        """仅对齐 A 仓位到 target_a，不触碰账本层逻辑（用于后台敞口守护）。

        返回 (已对齐或下单成功, 日志消息, 仓位/下单字段)。
        """
        pos_a = self._pos("a")
        pos_b = self._pos("b")
        fields = {
            "pos_a_before": float(pos_a),
            "pos_b_before": float(pos_b),
            "pos_a_after": float(pos_a),
            "pos_b_after": float(pos_b),
            "a_side": "",
            "b_side": "",
            "a_order_id": "",
            "b_order_id": "",
            "a_order_count": 0,
            "a_order_qty": 0.0,
            "a_order_log": "",
            "b_order_log": "",
            "exec_log": "",
        }
        qty = Decimal(str(getattr(self, "qty_per_layer", None) or 0))
        if qty <= 0:
            return False, "qty_per_layer 未初始化", fields
        tol = max(qty * Decimal("0.05"), Decimal("1e-8"))
        gap = target_a - pos_a
        if abs(gap) <= tol:
            msg = (
                f"A 已对齐 pos_a={pos_a:+.8f} pos_b={pos_b:+.8f} "
                f"target={target_a:+.8f}"
            )
            fields["a_order_log"] = msg
            fields["exec_log"] = msg
            return True, msg, fields
        side = "buy" if gap > 0 else "sell"
        order_qty = abs(gap)
        fields["a_side"] = side
        order, err = _place_taker(
            self.adapter_a,
            symbol=self.symbol_a,
            side=side,
            qty=order_qty,
            reduce_only=False,
        )
        if err:
            msg = (
                f"A 对齐失败 {side} {order_qty} "
                f"pos_a={pos_a:+.8f} pos_b={pos_b:+.8f} "
                f"target={target_a:+.8f} err={err}"
            )
            fields["a_order_log"] = msg
            fields["exec_log"] = msg
            return False, msg, fields
        oid = str(getattr(order, "order_id", "") or "")
        fields["a_order_id"] = oid
        fields["a_order_count"] = 1
        fields["a_order_qty"] = float(order_qty)
        self._credit_a(side, order_qty)
        pos_a2 = self._pos("a")
        fields["pos_a_after"] = float(pos_a2)
        fields["pos_b_after"] = float(self._pos("b"))
        msg = (
            f"A 对齐 {side} {order_qty} "
            f"pos_a={pos_a:+.8f}→{pos_a2:+.8f} "
            f"pos_b={pos_b:+.8f} target={target_a:+.8f} id={oid}"
        )
        fields["a_order_log"] = msg
        fields["exec_log"] = msg
        try:
            self._log(msg)
        except Exception:
            pass
        return True, msg, fields

    def _fail_empty(self, delta: int, error: str) -> LayerResult:
        zero = Decimal("0")
        result = LayerResult(
            ok=False,
            delta=delta,
            a=LegSnap("a", self.symbol_a, "", zero, zero),
            b=LegSnap("b", self.symbol_b, "", zero, zero),
            error=error,
            note=error,
        )
        self._tap_logs(result)
        result.logs.append(error)
        return result
