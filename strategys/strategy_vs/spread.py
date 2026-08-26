"""两所 taker 吃单的扣费净价差，以及滑动窗口统计。"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple


@dataclass
class LegResult:
    buy_venue: str
    sell_venue: str
    buy_ask: float
    sell_bid: float
    buy_fee: float
    sell_fee: float
    cost: float
    proceeds: float
    pnl: float
    pct: float
    qty: Optional[float]


@dataclass
class WindowStats:
    n: int
    mean: Optional[float]
    p50: Optional[float]
    p_hi: Optional[float]
    percentile: float
    percentiles: List[float]
    by_p: Dict[float, Optional[float]]


def parse_percentiles(raw: Any) -> List[float]:
    """配置可以是 90，或 [10, 50, 90]。"""
    if raw is None or raw == "":
        vals: List[float] = [90.0]
    elif isinstance(raw, (list, tuple)):
        vals = [float(x) for x in raw]
    elif isinstance(raw, str) and ("," in raw or " " in raw):
        vals = [float(p) for p in raw.replace(",", " ").split() if p]
    else:
        vals = [float(raw)]
    out: List[float] = []
    for value in vals:
        q = max(0.0, min(100.0, float(value)))
        if q not in out:
            out.append(q)
    return out or [90.0]


def p_label(q: float) -> str:
    if abs(q - round(q)) < 1e-9:
        return f"p{int(round(q))}"
    return f"p{q:g}"


class SpreadWindow:
    """按条数 FIFO 的净收益率样本。满了挤掉最旧一条，可落盘重启接着用。"""

    def __init__(self, maxlen: int, percentile: Any = 90.0) -> None:
        self.maxlen = max(1, int(maxlen))
        self.percentiles = parse_percentiles(percentile)
        self.percentile = self.percentiles[-1]
        self._samples: Deque[Tuple[float, float]] = deque(maxlen=self.maxlen)
        self.dirty = False

    def add(self, pct: float, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        self._samples.append((now, float(pct)))
        self.dirty = True

    def stats(self) -> WindowStats:
        values = [p for _, p in self._samples]
        n = len(values)
        if n == 0:
            by_p = {q: None for q in self.percentiles}
            return WindowStats(
                n=0,
                mean=None,
                p50=None,
                p_hi=None,
                percentile=self.percentile,
                percentiles=list(self.percentiles),
                by_p=by_p,
            )
        by_p = {q: _percentile(values, q) for q in self.percentiles}
        return WindowStats(
            n=n,
            mean=sum(values) / n,
            p50=_percentile(values, 50.0),
            p_hi=by_p.get(self.percentile),
            percentile=self.percentile,
            percentiles=list(self.percentiles),
            by_p=by_p,
        )

    def values(self) -> List[float]:
        return [pct for _, pct in self._samples]

    def dump(self) -> List[List[float]]:
        return [[ts, pct] for ts, pct in self._samples]

    def load(self, samples: Iterable[Iterable[float]]) -> int:
        self._samples.clear()
        rows = [row for row in samples if isinstance(row, (list, tuple)) and len(row) >= 2]
        for row in rows[-self.maxlen :]:
            try:
                self._samples.append((float(row[0]), float(row[1])))
            except (TypeError, ValueError):
                continue
        self.dirty = False
        return len(self._samples)


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * max(0.0, min(100.0, pct)) / 100.0
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


@dataclass
class GridTick:
    lots: int
    target: int
    delta: int
    edge: float
    next_add: Optional[float]
    next_reduce: Optional[float]
    action: str
    lower: Optional[float] = None
    upper: Optional[float] = None
    center: Optional[float] = None
    cost: Optional[float] = None
    width: Optional[float] = None
    mag: Optional[float] = None
    ab_pct: Optional[float] = None
    ba_pct: Optional[float] = None
    ready: bool = False
    frozen: bool = False
    note: str = ""


class SpreadGrid:
    """自适应持有带 + 对称网格：上沿以上开一侧，下沿以下开反向；带内持有。同向最多 max_lots 层。"""

    def __init__(
        self,
        fee_a: float = 0.0,
        fee_b: float = 0.0,
        fee_mult: float = 1.3,
        min_samples: int = 5000,
        q_lo: float = 10.0,
        q_hi: float = 90.0,
        max_lots: int = 5,
        step: float = 0.0001,
    ) -> None:
        self.fee_a = max(0.0, float(fee_a))
        self.fee_b = max(0.0, float(fee_b))
        self.fee_mult = max(1.0, float(fee_mult))
        self.min_samples = max(1, int(min_samples))
        self.q_lo = float(q_lo)
        self.q_hi = float(q_hi)
        self.max_lots = max(1, int(max_lots))
        self.step = max(1e-12, float(step))
        self.lots = 0
        self.peak_n = 0
        self.dirty = False
        self.last: Optional[GridTick] = None
        self.ready = False
        self.frozen = False
        self.center: Optional[float] = None
        self.lower: Optional[float] = None
        self.upper: Optional[float] = None
        self.cost: Optional[float] = None
        self.cost_cfg = 2.0 * (self.fee_a + self.fee_b)
        self.width: Optional[float] = None
        self.sample_n = 0
        self.note = ""

    def observe(
        self,
        ab_samples: Iterable[float],
        ba_samples: Iterable[float],
        current_lots: int = 0,
    ) -> None:
        """空仓时按窗口重算上下沿；有仓则冻结，避免窗口滑动把持仓扫掉。"""
        ab = [float(x) for x in ab_samples]
        ba = [float(x) for x in ba_samples]
        n = min(len(ab), len(ba))
        self.sample_n = n
        if n < self.min_samples:
            if current_lots == 0:
                self.ready = False
                self.frozen = False
                self.center = self.lower = self.upper = self.cost = self.width = None
                self.note = f"采样 {n}/{self.min_samples}"
            return
        if current_lots != 0 and self.ready and self.lower is not None:
            self.frozen = True
            self.note = "有仓，上下沿已冻"
            return
        mags = [max(ab[i], ba[i]) for i in range(n)]
        costs = [-(ab[i] + ba[i]) for i in range(n)]
        cost_emp = max(0.0, _percentile(costs, 50.0))
        cost = max(self.cost_cfg, cost_emp)
        width_fee = cost * self.fee_mult
        width_sample = max(0.0, _percentile(mags, self.q_hi) - _percentile(mags, self.q_lo))
        width = max(width_fee, width_sample)
        center = _percentile(mags, 50.0)
        self.cost = cost
        self.width = width
        self.center = center
        self.lower = center - width / 2.0
        self.upper = center + width / 2.0
        self.ready = True
        self.frozen = False
        if width_sample + 1e-12 < width_fee:
            self.note = "样本波动不够来回费，带宽已撑开"
        else:
            self.note = ""
        self.dirty = True

    def _crossed(self, edge: float, start: float, *, above: bool) -> int:
        """严格越过 start 后，按 step 数出层数。"""
        if above:
            gap = float(edge) - float(start)
            if gap <= 0:
                return 0
            return 1 + int(gap / self.step - 1e-12)
        gap = float(start) - float(edge)
        if gap <= 0:
            return 0
        return 1 + int(gap / self.step - 1e-12)

    def _hold_edge(self, ab_pct: float, ba_pct: float, current_lots: int) -> tuple[float, int]:
        if current_lots > 0:
            return float(ab_pct), 1
        if current_lots < 0:
            return float(ba_pct), -1
        sign = 1 if ab_pct >= ba_pct else -1
        return (float(ab_pct) if sign > 0 else float(ba_pct)), sign

    def desired_lots(self, ab_pct: float, ba_pct: float, current_lots: int) -> int:
        if not self.ready or self.lower is None or self.upper is None:
            return 0
        # 超限：只收到 ±max_lots，不继续加、不借机反向新开
        if abs(int(current_lots)) > self.max_lots:
            return (1 if current_lots > 0 else -1) * self.max_lots
        n = abs(int(current_lots))
        if n == 0:
            edge, sign = self._hold_edge(ab_pct, ba_pct, 0)
            add_up = min(self.max_lots, self._crossed(edge, self.upper, above=True))
            if add_up > 0:
                return sign * add_up
            add_lo = min(self.max_lots, self._crossed(edge, self.lower, above=False))
            return -sign * add_lo if add_lo > 0 else 0
        # edge 取持仓方向那条腿，与 mags=max(ab,ba) 标定的上下沿同尺，
        # 所以多空共用一套判断：越上沿=同向加层，跌破下沿=开反向。
        hold = 1 if current_lots > 0 else -1
        edge, _ = self._hold_edge(ab_pct, ba_pct, current_lots)
        add_up = min(self.max_lots, self._crossed(edge, self.upper, above=True))
        add_lo = min(self.max_lots, self._crossed(edge, self.lower, above=False))
        if add_up > n:
            return hold * add_up
        if add_lo > 0:
            return -hold * add_lo
        return current_lots

    def rest_ok(self, delta: int, ab_pct: float, ba_pct: float, current_lots: int) -> bool:
        """Maker 只在网格仍要求同一方向再走一层时挂着。

        必须跟 desired_lots / peek.delta 一致。空仓若按「当前更好的一侧」重算 sign，
        BTC/ETH 的 AB/BA 会抖，刚抢到通道就判定回带、未挂就让出。
        """
        if self.lower is None or self.upper is None or int(delta) not in (-1, 1):
            return False
        lots = int(current_lots)
        d = int(delta)
        target = self.desired_lots(ab_pct, ba_pct, lots)
        if d > 0:
            return target > lots
        return target < lots

    def peek(self, ab_pct: float, ba_pct: float, current_lots: int) -> GridTick:
        target = self.desired_lots(ab_pct, ba_pct, current_lots)
        if target > current_lots:
            delta = 1
        elif target < current_lots:
            delta = -1
        else:
            delta = 0
        n = abs(int(current_lots))
        mag, _ = self._hold_edge(ab_pct, ba_pct, current_lots)
        if not self.ready:
            action = "采样"
        elif current_lots == 0 and delta == 0:
            action = "观望"
        elif current_lots != 0 and target == current_lots:
            action = "持有"
        elif current_lots == 0 and delta:
            action = "开仓"
        elif current_lots != 0 and target != 0 and (current_lots > 0) != (target > 0):
            action = "反向"
        elif abs(target) > n:
            action = "加仓"
        else:
            action = "减仓"
        next_add = None
        next_reduce = None
        if self.upper is not None and self.lower is not None:
            if current_lots >= 0 and n < self.max_lots:
                next_add = self.upper + n * self.step
            if current_lots <= 0 and n < self.max_lots:
                next_reduce = self.lower - n * self.step
        tick = GridTick(
            lots=current_lots,
            target=target,
            delta=delta,
            edge=ab_pct if ab_pct >= ba_pct else -ba_pct,
            next_add=next_add,
            next_reduce=next_reduce,
            action=action,
            lower=self.lower,
            upper=self.upper,
            center=self.center,
            cost=self.cost,
            width=self.width,
            mag=mag,
            ab_pct=ab_pct,
            ba_pct=ba_pct,
            ready=self.ready,
            frozen=self.frozen,
            note=self.note,
        )
        self.last = tick
        return tick

    def update(self, ab_pct: float, ba_pct: float) -> GridTick:
        target = self.desired_lots(ab_pct, ba_pct, self.lots)
        cur = self.lots
        if target > cur:
            self.lots = cur + 1
        elif target < cur:
            self.lots = cur - 1
        if self.lots != cur:
            self.dirty = True
        return self.peek(ab_pct, ba_pct, self.lots)

    def dump(self) -> Dict[str, Any]:
        return {
            "mode": "band",
            "lots": 0,
            "center": self.center,
            "lower": self.lower,
            "upper": self.upper,
            "cost": self.cost,
            "width": self.width,
            "peak_n": self.peak_n,
            "max_lots": self.max_lots,
            "step": self.step,
        }

    def load(self, data: Optional[Dict[str, Any]]) -> None:
        self.lots = 0
        self.peak_n = 0
        self.frozen = False
        if not data or data.get("mode") != "band":
            self.dirty = False
            return
        try:
            center = data.get("center")
            lower = data.get("lower")
            upper = data.get("upper")
            if center is None or lower is None or upper is None:
                return
            self.center = float(center)
            self.lower = float(lower)
            self.upper = float(upper)
            self.cost = None if data.get("cost") is None else float(data["cost"])
            self.width = None if data.get("width") is None else float(data["width"])
            self.ready = self.upper > self.lower
            peak = data.get("peak_n")
            if peak is not None:
                self.peak_n = max(0, int(peak))
        except (TypeError, ValueError):
            return
        self.dirty = False


def entry_ready(
    *,
    current_pct: float,
    stats: WindowStats,
    min_samples: int,
    min_net_pct: float,
) -> tuple[bool, str]:
    """样本够且当前净价差超过阈值 → 满足开仓条件（仅统计，不下单）。"""
    if stats.n < min_samples:
        return False, f"样本不足 {stats.n}/{min_samples}"
    if current_pct < min_net_pct:
        return False, f"当前<{min_net_pct * 100:.4f}%"
    return True, "满足开仓条件"


def net_leg(
    *,
    buy_venue: str,
    sell_venue: str,
    buy_ask: float,
    sell_bid: float,
    buy_fee: float,
    sell_fee: float,
    buy_ask_sz: Optional[float],
    sell_bid_sz: Optional[float],
) -> LegResult:
    cost = buy_ask * (1.0 + buy_fee)
    proceeds = sell_bid * (1.0 - sell_fee)
    pnl = proceeds - cost
    pct = pnl / cost if cost > 0 else 0.0
    qty = None
    if buy_ask_sz is not None and sell_bid_sz is not None:
        qty = min(buy_ask_sz, sell_bid_sz)
    elif buy_ask_sz is not None:
        qty = buy_ask_sz
    elif sell_bid_sz is not None:
        qty = sell_bid_sz
    return LegResult(
        buy_venue=buy_venue,
        sell_venue=sell_venue,
        buy_ask=buy_ask,
        sell_bid=sell_bid,
        buy_fee=buy_fee,
        sell_fee=sell_fee,
        cost=cost,
        proceeds=proceeds,
        pnl=pnl,
        pct=pct,
        qty=qty,
    )


def pair_legs(
    *,
    a_name: str,
    b_name: str,
    a_bid: float,
    a_ask: float,
    b_bid: float,
    b_ask: float,
    fee_a: float,
    fee_b: float,
    b_maker: bool,
    a_bid_sz: Optional[float] = None,
    a_ask_sz: Optional[float] = None,
    b_bid_sz: Optional[float] = None,
    b_ask_sz: Optional[float] = None,
) -> Tuple[LegResult, LegResult]:
    """AB / BA 净价差。B taker：买 ask 卖 bid；B maker：卖挂 ask、买挂 bid。"""
    if b_maker:
        ab = net_leg(
            buy_venue=a_name,
            sell_venue=b_name,
            buy_ask=a_ask,
            sell_bid=b_ask,
            buy_fee=fee_a,
            sell_fee=fee_b,
            buy_ask_sz=a_ask_sz,
            sell_bid_sz=b_ask_sz,
        )
        ba = net_leg(
            buy_venue=b_name,
            sell_venue=a_name,
            buy_ask=b_bid,
            sell_bid=a_bid,
            buy_fee=fee_b,
            sell_fee=fee_a,
            buy_ask_sz=b_bid_sz,
            sell_bid_sz=a_bid_sz,
        )
    else:
        ab = net_leg(
            buy_venue=a_name,
            sell_venue=b_name,
            buy_ask=a_ask,
            sell_bid=b_bid,
            buy_fee=fee_a,
            sell_fee=fee_b,
            buy_ask_sz=a_ask_sz,
            sell_bid_sz=b_bid_sz,
        )
        ba = net_leg(
            buy_venue=b_name,
            sell_venue=a_name,
            buy_ask=b_ask,
            sell_bid=a_bid,
            buy_fee=fee_b,
            sell_fee=fee_a,
            buy_ask_sz=b_ask_sz,
            sell_bid_sz=a_bid_sz,
        )
    return ab, ba


def ok_to_rest(
    delta: int,
    mag: Optional[float],
    lower: Optional[float],
    upper: Optional[float],
) -> bool:
    """Maker 只在带外：开多侧 mag>上沿，开空侧 mag<下沿。"""
    if mag is None or lower is None or upper is None:
        return False
    if int(delta) > 0:
        return mag > upper
    return mag < lower


def window_identity(venues: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    def _part(cfg: Dict[str, Any]) -> Dict[str, Any]:
        from feeds import exec_fee_of, venue_role

        role = venue_role(cfg)
        fee = exec_fee_of(cfg)
        return {
            "exchange": str(cfg.get("exchange") or "").strip().lower(),
            "symbol": str(cfg.get("symbol") or "").strip(),
            "network": str(cfg.get("network") or "").strip().lower(),
            "role": role,
            "fee": fee,
        }

    return {"a": _part(venues["a"]), "b": _part(venues["b"])}


def persist_path(base_dir: Path, identity: Dict[str, Any], override: Optional[str] = None) -> Path:
    if override:
        path = Path(override)
        return path if path.is_absolute() else (base_dir / path).resolve()
    a, b = identity["a"], identity["b"]

    def _token(part: Dict[str, Any]) -> str:
        role = str(part.get("role") or "taker")
        fee = part.get("fee")
        fee_s = "na" if fee is None else f"{fee:.8f}".rstrip("0").rstrip(".")
        raw = f"{part['exchange']}_{part['network']}_{part['symbol']}_{role}_{fee_s}"
        return "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in raw)

    return (base_dir / "data" / f"{_token(a)}__{_token(b)}.json").resolve()


def load_windows(
    path: Path,
    identity: Dict[str, Any],
    windows: Dict[str, SpreadWindow],
) -> Tuple[int, Dict[str, Any], Dict[str, Any]]:
    if not path.is_file():
        return 0, {}, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, {}, {}
    if not isinstance(payload, dict) or payload.get("identity") != identity:
        return 0, {}, {}
    loaded = 0
    for key, window in windows.items():
        rows = payload.get(key) or []
        if isinstance(rows, list):
            loaded += window.load(rows)
    extra = payload.get("grid") if isinstance(payload.get("grid"), dict) else {}
    pnl = payload.get("pnl") if isinstance(payload.get("pnl"), dict) else {}
    return loaded, extra, pnl


def save_windows(
    path: Path,
    identity: Dict[str, Any],
    windows: Dict[str, SpreadWindow],
    grid: Optional[SpreadGrid] = None,
    pnl: Any = None,
) -> None:
    dirty = any(w.dirty for w in windows.values())
    if grid is not None:
        dirty = dirty or grid.dirty
    if pnl is not None:
        dirty = dirty or bool(getattr(pnl, "dirty", False))
    if not dirty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "identity": identity,
        "saved_at": time.time(),
        **{key: window.dump() for key, window in windows.items()},
    }
    if grid is not None:
        payload["grid"] = grid.dump()
    if pnl is not None and getattr(pnl, "ready", False):
        payload["pnl"] = pnl.dump()
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    for window in windows.values():
        window.dirty = False
    if grid is not None:
        grid.dirty = False
    if pnl is not None:
        pnl.dirty = False
