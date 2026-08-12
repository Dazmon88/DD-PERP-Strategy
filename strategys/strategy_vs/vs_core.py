"""
策略核心（回测/实盘共用）：双所价差 maker-taker + 对冲。

不持有任何线程/IO；每 tick 调用 decide_* 决定动作。

约定：
- 腿 A = 信号腿：挂 limit（用 BBO），按 spread 开/平
- 腿 B = 对冲腿：净敞口 delta = pos_a + pos_b 偏离 0 时，B 用 market 对冲
- 仓位符号：多=+，空=-

阈值模式 threshold_mode:
- fixed    : 写死 min/max_profit_pct
- quantile : 滚动 lookback 分位数自适应（推荐）
- zscore   : 滚动均值 ± Nσ
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Quote:
    bid: float
    ask: float
    last: float
    ts: int = 0


@dataclass
class LegState:
    exchange: str
    symbol: str
    quote: Optional[Quote] = None
    position: float = 0.0
    open_orders: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Action:
    kind: str  # open | close | hedge | cancel | none
    leg: Optional[str] = None  # a | b
    side: Optional[str] = None  # buy | sell
    price: Optional[float] = None
    qty: float = 0.0
    reduce_only: bool = False
    order_type: str = "limit"
    reason: str = ""


def profit_ratio(buy_price: float, sell_price: float) -> float:
    if buy_price <= 0:
        return 0.0
    return (sell_price - buy_price) / buy_price


class VSStrategy:
    """纯逻辑，不依赖 BasePerpAdapter 具体实现。"""

    def __init__(
        self,
        *,
        order_size: float,
        max_position_size: float = 0.0,
        min_profit_pct: float = 0.0005,
        max_profit_pct: float = 0.003,
        use_dynamic_profit_window: bool = False,
        profit_buffer_pct: float = 0.0,
        hedge_threshold: float = 1e-8,
        hedge_cooldown_sec: float = 2.0,
        # ---- 自适应阈值 ----
        threshold_mode: str = "fixed",  # fixed | quantile | zscore
        lookback: int = 288,  # 5m*288 ≈ 1 天
        open_q: float = 0.9,
        close_q: float = 0.1,
        open_z: float = 2.0,
        close_z: float = 0.0,
        min_edge: float = 0.0003,  # 覆盖成本的下限
    ):
        self.order_size = float(order_size)
        self.max_position_size = float(max_position_size or 0.0)
        self.min_profit_pct = float(min_profit_pct)
        self.max_profit_pct = float(max_profit_pct)
        self.use_dynamic_profit_window = bool(use_dynamic_profit_window)
        self.profit_buffer_pct = float(profit_buffer_pct or 0.0)
        self.hedge_threshold = float(hedge_threshold)
        self.hedge_cooldown_sec = float(hedge_cooldown_sec)

        self.threshold_mode = (threshold_mode or "fixed").lower()
        self.lookback = max(10, int(lookback))
        self.open_q = float(open_q)
        self.close_q = float(close_q)
        self.open_z = float(open_z)
        self.close_z = float(close_z)
        self.min_edge = float(min_edge)

        self._cur_min = self.min_profit_pct
        self._cur_max = self.max_profit_pct
        self._last_hedge_ts = 0.0
        self._spread_hist: List[float] = []

    # ---- 价差方向 ----
    @staticmethod
    def best_spread(a: Quote, b: Quote) -> Dict[str, Any]:
        """
        返回最优方向：
        - a 卖(bid) / b 买(ask): 开 = a short + b long
        - b 卖(bid) / a 买(ask): 开 = a long + b short
        """
        p_a_short = profit_ratio(b.ask, a.bid)  # a 卖高，b 买低
        p_a_long = profit_ratio(a.ask, b.bid)  # a 买低，b 卖高
        if p_a_short >= p_a_long:
            return {
                "direction": "a_short",
                "profit": p_a_short,
                "a_side": "sell",
            }
        return {
            "direction": "a_long",
            "profit": p_a_long,
            "a_side": "buy",
        }

    def _update_window(self, profit: float) -> None:
        """旧 compara 漂移窗口（仅 fixed + use_dynamic_profit_window）。"""
        if not self.use_dynamic_profit_window:
            self._cur_min, self._cur_max = self.min_profit_pct, self.max_profit_pct
            return
        window = self.max_profit_pct - self.min_profit_pct
        if window <= 0:
            self._cur_min, self._cur_max = self.min_profit_pct, self.max_profit_pct
            return
        buf = max(0.0, self.profit_buffer_pct)
        if profit < self._cur_min - buf:
            self._cur_min = profit + buf
            self._cur_max = self._cur_min + window
        elif profit > self._cur_max + buf:
            self._cur_max = profit - buf
            self._cur_min = self._cur_max - window

    # ---- 自适应阈值 ----
    def _observe_spread(self, profit: float) -> None:
        if self.threshold_mode == "fixed":
            return
        self._spread_hist.append(profit)
        if len(self._spread_hist) > self.lookback:
            self._spread_hist.pop(0)

    @staticmethod
    def _quantile(xs: List[float], q: float) -> float:
        if not xs:
            return 0.0
        xs = sorted(xs)
        q = min(max(q, 0.0), 1.0)
        idx = q * (len(xs) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(xs) - 1)
        frac = idx - lo
        return xs[lo] * (1 - frac) + xs[hi] * frac

    def _auto_thresholds(self) -> Optional[Tuple[float, float]]:
        if len(self._spread_hist) < max(20, self.lookback // 6):
            return None
        hist = self._spread_hist
        if self.threshold_mode == "quantile":
            close_th = self._quantile(hist, self.close_q)
            open_th = self._quantile(hist, self.open_q)
        elif self.threshold_mode == "zscore":
            mean = sum(hist) / len(hist)
            var = sum((x - mean) ** 2 for x in hist) / max(1, len(hist) - 1)
            std = var ** 0.5
            close_th = mean + self.close_z * std
            open_th = mean + self.open_z * std
        else:
            return None
        # 不越界 + 至少覆盖成本
        open_th = max(open_th, close_th + 1e-6, self.min_edge)
        return close_th, open_th

    def current_thresholds(self) -> Tuple[float, float]:
        """对外暴露当前开/平阈值（调试用）。"""
        if self.threshold_mode == "fixed":
            return self._cur_min, self._cur_max
        auto = self._auto_thresholds()
        if auto is None:
            return self.min_profit_pct, self.max_profit_pct
        return auto

    def decide_spread(self, a: Quote, b: Quote, pos_a: float) -> Action:
        best = self.best_spread(a, b)
        profit = best["profit"]

        if self.threshold_mode == "fixed":
            self._update_window(profit)
            close_th, open_th = self._cur_min, self._cur_max
        else:
            self._observe_spread(profit)
            auto = self._auto_thresholds()
            if auto is None:
                close_th, open_th = self.min_profit_pct, self.max_profit_pct
            else:
                close_th, open_th = auto

        # 持仓则优先判断平仓
        if abs(pos_a) > 1e-12:
            if profit < close_th:
                side = "sell" if pos_a > 0 else "buy"
                price = a.bid if side == "sell" else a.ask
                return Action(
                    kind="close",
                    leg="a",
                    side=side,
                    price=price,
                    qty=min(abs(pos_a), self.order_size),
                    reduce_only=True,
                    reason=(
                        f"spread {profit:.6f} < close {close_th:.6f} "
                        f"mode={self.threshold_mode}"
                    ),
                )
            return Action(kind="none", reason="hold position")

        # 无持仓判断开仓
        if self.max_position_size > 0 and abs(pos_a) >= self.max_position_size:
            return Action(kind="none", reason="max position")
        if profit > open_th:
            side = best["a_side"]
            price = a.bid if side == "sell" else a.ask
            return Action(
                kind="open",
                leg="a",
                side=side,
                price=price,
                qty=self.order_size,
                reduce_only=False,
                reason=(
                    f"spread {profit:.6f} > open {open_th:.6f} "
                    f"mode={self.threshold_mode} dir={best['direction']}"
                ),
            )
        return Action(kind="cancel", leg="a", reason="spread inside window")

    def decide_hedge(
        self,
        pos_a: float,
        pos_b: float,
        b: Quote,
        now: Optional[float] = None,
    ) -> Action:
        """
        目标：让 B 尽量镜像 A（pos_b ≈ -pos_a），使净敞口归 0。

        说明：若 A 先平了，B 还残留旧仓（pos_a≈0 但 pos_b≠0），
        此时“对冲”实际是主动平 B，所以 reduce_only=False。

        now: 注入时间（回测传 bar 时间，实盘默认 time.time()）。
        """
        delta = pos_a + pos_b
        if abs(delta) <= self.hedge_threshold:
            return Action(kind="none", reason="hedged")
        now = time.time() if now is None else float(now)
        if self._last_hedge_ts and now - self._last_hedge_ts < self.hedge_cooldown_sec:
            return Action(kind="none", reason="cooldown")
        side = "sell" if delta > 0 else "buy"
        self._last_hedge_ts = now
        return Action(
            kind="hedge",
            leg="b",
            side=side,
            qty=abs(delta),
            reduce_only=False,
            order_type="market",
            reason=f"delta={delta}",
        )
