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
    """实盘以交易所持仓为账本；在途才锁本地层。纸盘仍按本地成交。"""

    def __init__(
        self,
        qty_per_layer: float,
        pos_tolerance: float = 1e-7,
        live: bool = False,
        max_lots: int = 5,
    ) -> None:
        self.qty_per_layer = max(1e-12, float(qty_per_layer))
        self.pos_tolerance = float(pos_tolerance)
        self.live = bool(live)
        self.max_lots = max(1, int(max_lots))
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

    def _book_pos(self) -> Tuple[float, float]:
        """空闲实盘用所仓；在途/纸盘用本地仓。"""
        if self.live and not self.inflight:
            ea, eb = self.last_exch_a, self.last_exch_b
            if ea is not None and eb is not None:
                return float(ea), float(eb)
        return float(self.pos_a), float(self.pos_b)

    def signed_lots(self, pos_a: float, pos_b: float) -> int:
        """由两所数量算层数。不足一层的残仓也算 ±1，避免 round 成 0 再开一整层。"""
        pa, pb = float(pos_a), float(pos_b)
        if abs(pa) <= self.pos_tolerance:
            if abs(pb) <= self.pos_tolerance:
                return 0
            pa = -pb
        n = pa / self.qty_per_layer
        if abs(n) < 1.0 - 1e-12:
            return 1 if n > 0 else -1
        return int(round(n))

    @property
    def lots(self) -> int:
        """空闲实盘跟所仓；在途/纸盘跟本地仓。重启后第一次对账即按所仓认层。"""
        pa, pb = self._book_pos()
        return self.signed_lots(pa, pb)

    def layer_qty(self, delta: int) -> float:
        """开/加用整层；减仓用剩余实际仓，避免 0.03 去扫 0.01。"""
        full = float(self.qty_per_layer)
        if not self.is_reduce(int(delta)):
            return full
        cands: List[float] = []
        pa, pb = self._book_pos()
        for raw in (pa, pb, self.last_exch_a, self.last_exch_b):
            if raw is None:
                continue
            av = abs(float(raw))
            if av > self.pos_tolerance:
                cands.append(av)
        if not cands:
            return full
        return min(full, min(cands))

    @property
    def inflight(self) -> bool:
        return any(not o.done for o in self.orders.values())

    @property
    def state(self) -> str:
        if self.reconcile_fail:
            return STATE_RECONCILE_FAIL
        if self.inflight:
            return STATE_INFLIGHT
        pa, pb = self._book_pos()
        if abs(pa) > self.pos_tolerance or abs(pb) > self.pos_tolerance:
            return STATE_HOLDING
        return STATE_IDLE

    def can_open(self) -> bool:
        if not self.accounts_ready:
            return False
        return self.state not in (STATE_INFLIGHT, STATE_RECONCILE_FAIL)

    def is_reduce(self, delta: int) -> bool:
        lots = self.lots
        if lots != 0 and int(delta) * lots < 0:
            return True
        # 账本空但交易所已有仓：delta 与所仓异号视为只平
        ea = self.last_exch_a
        if ea is not None and abs(ea) > self.pos_tolerance and int(delta) * ea < 0:
            return True
        return False

    def over_max_lots(self) -> bool:
        if abs(self.lots) > self.max_lots:
            return True
        ea = self.last_exch_a
        if ea is None:
            return False
        max_qty = self.max_lots * self.qty_per_layer
        return abs(ea) >= max_qty - self.pos_tolerance

    def _exch_blocks_add(self, delta: int) -> bool:
        """交易所仓已达/超 max_lots，且 delta 同向加仓 → 挡。"""
        ea = self.last_exch_a
        if ea is None:
            return False
        max_qty = self.max_lots * self.qty_per_layer
        if abs(ea) < max_qty - self.pos_tolerance:
            return False
        return ea * int(delta) > 0

    def can_submit(self, delta: int) -> bool:
        """加仓要 can_open 且未超 max_lots；减仓在对账失败/超限时仍允许。"""
        if int(delta) not in (-1, 1):
            return False
        if self.inflight:
            return False
        if self.is_reduce(delta):
            return True
        if abs(self.lots) >= self.max_lots:
            return False
        if self._exch_blocks_add(delta):
            return False
        return self.can_open()

    def expected_exchange(self) -> Tuple[Optional[float], Optional[float]]:
        if self.live:
            return self.pos_a, self.pos_b
        return self.exch_a0, self.exch_b0

    def snapshot(self) -> LedgerSnapshot:
        st = self.state
        exp_a, exp_b = self.expected_exchange()
        pa, pb = self._book_pos()
        return LedgerSnapshot(
            state=st,
            state_cn=STATE_CN[st],
            lots=self.lots,
            qty_per_layer=self.qty_per_layer,
            pos_a=pa,
            pos_b=pb,
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
        qty = self.layer_qty(delta)
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

    def adopt_exchange(
        self,
        pos_a: float,
        pos_b: float,
        *,
        note: str = "",
        now: Optional[float] = None,
    ) -> bool:
        """清空在途，按交易所对锁仓认领到账本。对锁则 True，否则 False（调用方再 abort）。"""
        now = time.time() if now is None else now
        self.last_exch_a = float(pos_a)
        self.last_exch_b = float(pos_b)
        hedge = self._hedge_from_exchange(float(pos_a), float(pos_b))
        # 无论成败都先解锁在途，避免卡在 inflight
        self.orders = {}
        self.reserved_delta = 0
        if hedge is None:
            return False
        pa, pb = hedge
        self.pos_a, self.pos_b = pa, pb
        self.last_fill_ts = now
        n = self.lots
        msg = note or f"按交易所认领 {pa:+.6g}/{pb:+.6g} {n:+d}层"
        if abs(n) > self.max_lots:
            msg += f" 超{self.max_lots}层只平"
        self._mark_ok(msg)
        return True

    def _hedge_tol(self) -> float:
        """净敞口容差：半层以内视为对锁。一整层敞口必须补腿，不能当做成层。"""
        return max(self.pos_tolerance, self.qty_per_layer * 0.5)

    def _hedge_from_exchange(
        self, pos_a: float, pos_b: float
    ) -> Optional[Tuple[float, float]]:
        """两所仓对锁（含空仓）则返回实际仓；否则 None。

        对锁：|A+B| ≤ 半层，且两侧异号或一侧为空。层数由所仓数量计算。
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
        """实盘账本跟所仓。缺数 / 在途 / 非空仓且推送未追上成交时跳过。"""
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
        exch_flat = (
            abs(float(pos_a)) <= self.pos_tolerance
            and abs(float(pos_b)) <= self.pos_tolerance
        )
        # 非空仓且时间戳落后：可能是刚成交 REST 还没跟上，不能用旧仓盖掉
        if (
            self.live
            and not exch_flat
            and self.last_fill_ts > 0
            and ts + 1e-9 < self.last_fill_ts
        ):
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
            old_a, old_b = self.pos_a, self.pos_b
            self.pos_a, self.pos_b = float(pos_a), float(pos_b)
            if exch_flat:
                self.last_fill_ts = 0.0
            hedge = self._hedge_from_exchange(float(pos_a), float(pos_b))
            if hedge is None:
                self.accounts_ready = True
                self.reconcile_fail = True
                self.last_error = (
                    f"对账失败 A 所 {float(pos_a):+.6g} / "
                    f"B 所 {float(pos_b):+.6g} 未对锁"
                )
                self.note = "禁开，只平"
                return False
            changed = (
                abs(old_a - self.pos_a) > self.pos_tolerance
                or abs(old_b - self.pos_b) > self.pos_tolerance
            )
            note = ""
            if changed:
                n = self.lots
                note = f"按交易所持仓 {self.pos_a:+.6g}/{self.pos_b:+.6g} {n:+d}层"
                if abs(n) > self.max_lots:
                    note += f" 超{self.max_lots}层只平"
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
