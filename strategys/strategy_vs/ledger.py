"""
跨所持仓账本：热路径只认成交，交易所仓位只对账。

四态: idle 空闲 / inflight 在途 / holding 持有 / reconcile_fail 对账失败。
SimBroker 用延迟成交推进状态，不真下单。

纸盘（live=False）：对账对照启动时的交易所基线，模拟成交不参与比较。
实盘（live=True）：对账对照本地成交仓；在途或推送未追上成交时跳过。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

STATE_IDLE = "idle"
STATE_INFLIGHT = "inflight"
STATE_HOLDING = "holding"
STATE_RECONCILE_FAIL = "reconcile_fail"

STATE_CN = {
    STATE_IDLE: "空闲",
    STATE_INFLIGHT: "在途",
    STATE_HOLDING: "持有",
    STATE_RECONCILE_FAIL: "对账失败",
}


@dataclass
class WorkingOrder:
    cloid: str
    venue: str
    side: str
    qty: float
    filled: float = 0.0
    status: str = "pending"

    @property
    def done(self) -> bool:
        return self.status in ("filled", "rejected")


@dataclass
class LedgerSnapshot:
    state: str
    state_cn: str
    lots: int
    qty_per_layer: float
    pos_a: float
    pos_b: float
    exch_a: Optional[float]
    exch_b: Optional[float]
    exp_a: Optional[float]
    exp_b: Optional[float]
    reserved_delta: int
    pending: int
    can_open: bool
    accounts_ready: bool
    live: bool
    last_error: str
    note: str = ""


@dataclass
class _PendingFill:
    due: float
    venue: str
    cloid: str
    qty: float
    side: str
    price: float


class PositionLedger:
    """本地仓位：发单即锁层，fill 才改仓，REST 对账失败则禁开。"""

    def __init__(
        self,
        qty_per_layer: float,
        pos_tolerance: float = 1e-7,
        live: bool = False,
    ) -> None:
        self.qty_per_layer = max(1e-12, float(qty_per_layer))
        self.pos_tolerance = float(pos_tolerance)
        self.live = bool(live)
        self.pos_a = 0.0
        self.pos_b = 0.0
        self.exch_a0: Optional[float] = None
        self.exch_b0: Optional[float] = None
        self.last_exch_a: Optional[float] = None
        self.last_exch_b: Optional[float] = None
        self.accounts_ready = False
        self.reserved_delta = 0
        self.orders: Dict[str, WorkingOrder] = {}
        self.reconcile_fail = False
        self.last_error = ""
        self.last_fill_ts = 0.0
        self._seq = 0
        self.note = ""

    @property
    def lots(self) -> int:
        return int(round(self.pos_a / self.qty_per_layer))

    @property
    def inflight(self) -> bool:
        return any(not o.done for o in self.orders.values())

    @property
    def state(self) -> str:
        if self.reconcile_fail:
            return STATE_RECONCILE_FAIL
        if self.inflight:
            return STATE_INFLIGHT
        if abs(self.pos_a) > self.pos_tolerance or abs(self.pos_b) > self.pos_tolerance:
            return STATE_HOLDING
        return STATE_IDLE

    def can_open(self) -> bool:
        if not self.accounts_ready:
            return False
        return self.state not in (STATE_INFLIGHT, STATE_RECONCILE_FAIL)

    def is_reduce(self, delta: int) -> bool:
        lots = self.lots
        return lots != 0 and int(delta) * lots < 0

    def can_submit(self, delta: int) -> bool:
        """加仓要 can_open；减仓在对账失败时仍允许（只平不开）。"""
        if int(delta) not in (-1, 1):
            return False
        if self.inflight:
            return False
        if self.is_reduce(delta):
            return True
        return self.can_open()

    def expected_exchange(self) -> Tuple[Optional[float], Optional[float]]:
        if self.live:
            return self.pos_a, self.pos_b
        return self.exch_a0, self.exch_b0

    def snapshot(self) -> LedgerSnapshot:
        st = self.state
        exp_a, exp_b = self.expected_exchange()
        return LedgerSnapshot(
            state=st,
            state_cn=STATE_CN[st],
            lots=self.lots,
            qty_per_layer=self.qty_per_layer,
            pos_a=self.pos_a,
            pos_b=self.pos_b,
            exch_a=self.last_exch_a,
            exch_b=self.last_exch_b,
            exp_a=exp_a,
            exp_b=exp_b,
            reserved_delta=self.reserved_delta,
            pending=sum(1 for o in self.orders.values() if not o.done),
            can_open=self.can_open(),
            accounts_ready=self.accounts_ready,
            live=self.live,
            last_error=self.last_error,
            note=self.note,
        )

    def submit_layer(self, delta: int, now: Optional[float] = None) -> Tuple[Optional[str], Optional[str]]:
        """锁一层并生成两腿 cloid。delta=+1 买A卖B，-1 卖A买B。"""
        now = time.time() if now is None else now
        if delta not in (-1, 1):
            self.last_error = "delta 只能是 ±1"
            return None, None
        if not self.can_submit(delta):
            self.last_error = "在途或禁开，拒绝发单"
            return None, None
        self._seq += 1
        cloid_a = f"{int(now * 1000)}-{self._seq}-a"
        cloid_b = f"{int(now * 1000)}-{self._seq}-b"
        if delta > 0:
            side_a, side_b = "buy", "sell"
        else:
            side_a, side_b = "sell", "buy"
        qty = self.qty_per_layer
        self.orders[cloid_a] = WorkingOrder(cloid_a, "a", side_a, qty)
        self.orders[cloid_b] = WorkingOrder(cloid_b, "b", side_b, qty)
        self.reserved_delta = delta
        self.last_error = ""
        self.note = f"锁层 {delta:+d}"
        return cloid_a, cloid_b

    def on_fill(
        self,
        cloid: str,
        qty: float,
        price: float = 0.0,
        now: Optional[float] = None,
    ) -> None:
        now = time.time() if now is None else now
        order = self.orders.get(cloid)
        if order is None or order.done:
            return
        fill_qty = min(float(qty), order.qty - order.filled)
        if fill_qty <= 0:
            return
        signed = fill_qty if order.side == "buy" else -fill_qty
        if order.venue == "a":
            self.pos_a += signed
        else:
            self.pos_b += signed
        order.filled += fill_qty
        if order.filled + 1e-12 >= order.qty:
            order.status = "filled"
        self.last_fill_ts = now
        _ = price
        if not self.inflight:
            self.reserved_delta = 0
            self.orders = {k: v for k, v in self.orders.items() if not v.done}
            self.note = "两腿成交"

    def on_reject(self, cloid: str, reason: str = "拒单") -> None:
        order = self.orders.get(cloid)
        if order is None or order.done:
            return
        order.status = "rejected"
        self.last_error = reason
        if not self.inflight:
            self.reserved_delta = 0
            self.orders = {k: v for k, v in self.orders.items() if not v.done}
            self.note = reason

    def abort_layer(self, reason: str = "一层失败") -> None:
        """两腿都未计入成交：全部拒掉，解锁。"""
        for cloid in list(self.orders):
            self.on_reject(cloid, reason)

    def _hedge_tol(self) -> float:
        """净敞口容差：半层内视为对锁（允许部分成交零头）。"""
        return max(self.pos_tolerance, self.qty_per_layer * 0.5)

    def _hedge_from_exchange(
        self, pos_a: float, pos_b: float
    ) -> Optional[Tuple[float, float]]:
        """两所仓对锁（含空仓）则返回实际仓；否则 None。

        对锁：|A+B| ≤ 半层，且两侧异号或一侧为空。
        层数由 lots = round(pos_a / qty) 按实际仓计算，不再要求 qty 整数倍。
        """
        qa, qb = float(pos_a), float(pos_b)
        tol = self.pos_tolerance
        hedge_tol = self._hedge_tol()
        if abs(qa) <= tol and abs(qb) <= tol:
            return 0.0, 0.0
        if abs(qa + qb) > hedge_tol:
            return None
        # 同向且都显著：不是对锁
        if abs(qa) > tol and abs(qb) > tol and qa * qb > 0:
            return None
        return qa, qb

    def _mark_ok(self, note: str = "") -> None:
        self.accounts_ready = True
        recovered = self.reconcile_fail
        self.reconcile_fail = False
        if self.last_error.startswith("对账"):
            self.last_error = ""
        if note:
            self.note = note
        elif recovered:
            self.note = "对账恢复"

    def reconcile(
        self,
        pos_a: Optional[float],
        pos_b: Optional[float],
        ts_a: float = 0.0,
        ts_b: float = 0.0,
        now: Optional[float] = None,
        *,
        live: Optional[bool] = None,
    ) -> bool:
        """交易所仓位只对账。缺数 / 在途 / 未追上成交时跳过，对不上才失败。"""
        now = time.time() if now is None else now
        if live is not None:
            self.live = bool(live)
        if pos_a is not None:
            self.last_exch_a = float(pos_a)
        if pos_b is not None:
            self.last_exch_b = float(pos_b)
        if pos_a is None or pos_b is None:
            if self.exch_a0 is None or self.exch_b0 is None:
                self.accounts_ready = False
                self.note = "账户仓位未就绪，跳过对账"
            return True
        if self.live and self.inflight:
            return True
        ts = min(float(ts_a or 0.0), float(ts_b or 0.0))
        if self.live and self.last_fill_ts > 0 and ts + 1e-9 < self.last_fill_ts:
            self.note = "仓位推送未追上成交，跳过对账"
            return True
        if self.exch_a0 is None or self.exch_b0 is None:
            self.exch_a0 = float(pos_a)
            self.exch_b0 = float(pos_b)
            if not self.live:
                self._mark_ok(
                    f"对账基线 A {self.exch_a0:+.6g} / B {self.exch_b0:+.6g}"
                )
                return True
        if self.live:
            hedge = self._hedge_from_exchange(float(pos_a), float(pos_b))
            if hedge is not None:
                pa, pb = hedge
                note = ""
                if (
                    abs(self.pos_a - pa) > self.pos_tolerance
                    or abs(self.pos_b - pb) > self.pos_tolerance
                ):
                    n = int(round(pa / self.qty_per_layer))
                    self.pos_a, self.pos_b = pa, pb
                    note = f"按交易所认领 {pa:+.6g}/{pb:+.6g} {n:+d}层"
                self._mark_ok(note)
                return True
        exp_a, exp_b = self.expected_exchange()
        assert exp_a is not None and exp_b is not None
        ok_a = abs(float(pos_a) - exp_a) <= self.pos_tolerance
        ok_b = abs(float(pos_b) - exp_b) <= self.pos_tolerance
        if ok_a and ok_b:
            self._mark_ok()
            return True
        self.accounts_ready = True
        self.reconcile_fail = True
        self.last_error = (
            f"对账失败 A 所 {float(pos_a):+.6g} 期望 {exp_a:+.6g} / "
            f"B 所 {float(pos_b):+.6g} 期望 {exp_b:+.6g}"
        )
        self.note = "禁开，只平"
        return False


class SimBroker:
    """模拟成交：发单后延迟 fill，REST 快照可滞后。"""

    def __init__(
        self,
        fill_delay_sec: float = 0.5,
        leg_gap_sec: float = 0.25,
        rest_lag_sec: float = 0.0,
    ) -> None:
        self.fill_delay_sec = max(0.0, float(fill_delay_sec))
        self.leg_gap_sec = max(0.0, float(leg_gap_sec))
        self.rest_lag_sec = max(0.0, float(rest_lag_sec))
        self.true_a = 0.0
        self.true_b = 0.0
        self._fills: List[_PendingFill] = []
        self._rest_q: List[Tuple[float, float, float]] = []
        self.rest_a = 0.0
        self.rest_b = 0.0
        self.rest_ts = 0.0

    def submit(
        self,
        ledger: PositionLedger,
        delta: int,
        price_a: float = 0.0,
        price_b: float = 0.0,
        now: Optional[float] = None,
    ) -> bool:
        now = time.time() if now is None else now
        cloids = ledger.submit_layer(delta, now=now)
        if cloids[0] is None or cloids[1] is None:
            return False
        cloid_a, cloid_b = cloids
        oa = ledger.orders[cloid_a]
        ob = ledger.orders[cloid_b]
        self._fills.append(
            _PendingFill(now + self.fill_delay_sec, "a", cloid_a, oa.qty, oa.side, price_a)
        )
        self._fills.append(
            _PendingFill(
                now + self.fill_delay_sec + self.leg_gap_sec,
                "b",
                cloid_b,
                ob.qty,
                ob.side,
                price_b,
            )
        )
        return True

    def poll(self, ledger: PositionLedger, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        n = 0
        due = [p for p in self._fills if p.due <= now]
        self._fills = [p for p in self._fills if p.due > now]
        for item in due:
            signed = item.qty if item.side == "buy" else -item.qty
            if item.venue == "a":
                self.true_a += signed
            else:
                self.true_b += signed
            ledger.on_fill(item.cloid, item.qty, item.price, now=now)
            self._rest_q.append((now + self.rest_lag_sec, self.true_a, self.true_b))
            n += 1
        while self._rest_q and self._rest_q[0][0] <= now:
            _, ra, rb = self._rest_q.pop(0)
            self.rest_a, self.rest_b = ra, rb
            self.rest_ts = now
        if self.rest_lag_sec <= 0 and due:
            self.rest_a, self.rest_b = self.true_a, self.true_b
            self.rest_ts = now
        return n
