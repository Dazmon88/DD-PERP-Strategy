"""
回测适配器：从 data/{exchange}/{PAIR}-{tf}.csv 提供行情并本地撮合。

实现 BasePerpAdapter 子集（策略 vs 只用 get_ticker/get_positions/place_order/
cancel_all_orders/get_open_orders/get_balance）。

撮合模型（保守近似）：
- limit buy: 成交价 = min(price, candle.close)（只看 close 是否跌破限价）
- limit sell: 成交价 = max(price, candle.close)
- 若 candle.low <= price 视为本根可成交（保守用 close 夹）
- market: 按当前 close 成交
- fee: fee_rate * notional，从 cash 扣
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters.base_adapter import Balance, BasePerpAdapter, Order, Position
from tools.ohlcv_store import load_ohlcv, ohlcv_path


def _pair_file(exchange: str, pair: str) -> str:
    s = pair.strip().upper().replace("/", "_").replace(":", "_").replace("-", "_")
    return s


class BacktestAdapter(BasePerpAdapter):
    """单所 CSV 回测撮合器。"""

    def __init__(
        self,
        config: Dict[str, Any],
        *,
        exchange: str,
        pair: str,
        timeframe: str,
        df: pd.DataFrame,
        fee_rate: float = 0.0,
        spread_bps: float = 0.0,
        quote_asset: str = "USD",
        timeframe_ms: int = 300_000,
        initial_cash: float = 1_000_000.0,
    ):
        super().__init__(config)
        self.exchange_name = exchange
        self.pair = pair
        self.symbol = config.get("symbol") or pair
        self.timeframe = timeframe
        self.timeframe_ms = int(timeframe_ms)
        self.fee_rate = float(fee_rate or 0.0)
        self.spread_bps = float(spread_bps or 0.0)
        self.quote_asset = quote_asset

        self.df = df.reset_index(drop=True).copy()
        self.i = 0  # 当前 bar 索引（含）
        self.initial_cash = Decimal(str(initial_cash))
        self.cash = Decimal(str(initial_cash))
        self.position = Decimal("0")  # 正=多
        self.entry_price = Decimal("0")
        self.open_orders: List[Order] = []
        self.realized_pnl = Decimal("0")
        self.fee_paid = Decimal("0")
        self.trades: List[Dict[str, Any]] = []
        self._order_seq = 0
        self.volume_base = Decimal("0")  # 累计成交量（标的数量）
        self.volume_quote = Decimal("0")  # 累计成交额

    # ---- 数据推进 ----
    @property
    def n(self) -> int:
        return len(self.df)

    def set_index(self, i: int) -> None:
        self.i = max(0, min(i, self.n - 1))

    def current_bar(self) -> pd.Series:
        return self.df.iloc[self.i]

    def current_ts(self):
        return self.current_bar()["date"]

    def _px(self, field: str = "close") -> Decimal:
        return Decimal(str(self.current_bar()[field]))

    def bid_ask(self):
        mid = self._px("close")
        half = mid * Decimal(str(self.spread_bps)) / Decimal("20000")
        return mid - half, mid + half

    # ---- BasePerpAdapter 接口 ----
    def connect(self) -> bool:
        return True

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        bid, ask = self.bid_ask()
        last = self._px("close")
        return {
            "symbol": symbol,
            "bid": float(bid),
            "ask": float(ask),
            "last": float(last),
            "mid": float((bid + ask) / 2),
            "mark": float(last),
            "ts": int(self.current_ts().timestamp() * 1000),
        }

    def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        bid, ask = self.bid_ask()
        return {"bids": [[float(bid), 1e9]], "asks": [[float(ask), 1e9]]}

    def get_balance(self) -> Balance:
        mark = self._px("close")
        pos_val = self.position * mark
        equity = self.cash + pos_val
        return Balance(
            total_balance=equity,
            available_balance=self.cash,
            equity=equity,
            unrealized_pnl=Decimal("0"),
            position_value=pos_val,
        )

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        if self.position == 0:
            return []
        side = "long" if self.position > 0 else "short"
        return [
            Position(
                symbol=self.symbol,
                size=abs(self.position),
                side=side,
                entry_price=self.entry_price,
                mark_price=self._px("close"),
                unrealized_pnl=Decimal("0"),
            )
        ]

    def _next_id(self) -> str:
        self._order_seq += 1
        return f"bt-{self._order_seq}"

    def _charge_fee(self, qty: Decimal, price: Decimal) -> Decimal:
        fee = abs(qty) * price * Decimal(str(self.fee_rate))
        self.cash -= fee
        self.fee_paid += fee
        return fee

    def _fill(self, side: str, qty: Decimal, price: Decimal, reduce_only: bool) -> None:
        signed = qty if side == "buy" else -qty
        old = self.position
        new = old + signed
        entry_before = self.entry_price
        realized = Decimal("0")
        # realized pnl on reducing
        if old > 0 and signed < 0:
            close_qty = min(abs(signed), old)
            realized = (price - self.entry_price) * close_qty
            self.realized_pnl += realized
            self.cash += realized
        elif old < 0 and signed > 0:
            close_qty = min(signed, abs(old))
            realized = (self.entry_price - price) * close_qty
            self.realized_pnl += realized
            self.cash += realized
        # update entry for increased position
        if old == 0 or (old > 0 and signed > 0) or (old < 0 and signed < 0):
            prev_val = abs(old) * self.entry_price
            add_val = abs(signed) * price
            tot_qty = abs(old) + abs(signed)
            self.entry_price = (prev_val + add_val) / tot_qty if tot_qty else Decimal("0")
            kind = "open" if old == 0 else "add"
        elif new == 0 or (old > 0 > new) or (old < 0 < new):
            self.entry_price = price if new != 0 else Decimal("0")
            kind = "close" if new == 0 else "flip"
        else:
            kind = "reduce"
        self.position = new
        fee = self._charge_fee(qty, price)
        self.volume_base += abs(qty)
        self.volume_quote += abs(qty) * price
        self.trades.append(
            {
                "ts": self.current_ts(),
                "side": side,
                "qty": float(qty),
                "price": float(price),
                "notional": float(abs(qty) * price),
                "fee": float(fee),
                "kind": kind,
                "reduce_only": reduce_only,
                "pos_before": float(old),
                "pos_after": float(self.position),
                "entry_before": float(entry_before),
                "realized": float(realized),
            }
        )

    def _try_fill_limits(self) -> None:
        bar = self.current_bar()
        low = Decimal(str(bar["low"]))
        high = Decimal(str(bar["high"]))
        remaining: List[Order] = []
        for o in self.open_orders:
            if o.price is None:
                continue
            px = Decimal(o.price)
            filled = False
            if o.side == "buy" and low <= px:
                fill_px = min(px, Decimal(str(bar["close"])))
                self._fill("buy", o.quantity, fill_px, o.reduce_only)
                filled = True
            elif o.side == "sell" and high >= px:
                fill_px = max(px, Decimal(str(bar["close"])))
                self._fill("sell", o.quantity, fill_px, o.reduce_only)
                filled = True
            if not filled:
                remaining.append(o)
        self.open_orders = remaining

    def step(self) -> None:
        """推进一根 bar，并撮合挂单。"""
        self._try_fill_limits()

    def advance(self) -> None:
        """前进一根并推进模拟时钟；引擎必须调用它推进时间。"""
        self.i = min(self.i + 1, self.n - 1)
        self._now = self.i * self.timeframe_ms

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: str = "gtc",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs,
    ) -> Order:
        side = side.lower()
        if side in ("long",):
            side = "buy"
        if side in ("short",):
            side = "sell"
        if order_type == "market":
            px = self._px("close")
            self._fill(side, quantity, px, reduce_only)
            return Order(
                order_id=self._next_id(),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=px,
                filled_quantity=quantity,
                status="filled",
                reduce_only=reduce_only,
                client_order_id=client_order_id,
                created_at=int(self.current_ts().timestamp() * 1000),
            )
        # limit：挂起，等 step 撮合
        order = Order(
            order_id=self._next_id(),
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="open",
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            client_order_id=client_order_id,
            created_at=int(self.current_ts().timestamp() * 1000),
        )
        self.open_orders.append(order)
        # 立即尝试本根成交（保守）
        self._try_fill_limits()
        return order

    def cancel_order(self, order_id: Optional[str] = None, symbol: Optional[str] = None, client_order_id: Optional[str] = None) -> bool:
        before = len(self.open_orders)
        self.open_orders = [
            o
            for o in self.open_orders
            if not (
                (order_id and o.order_id == order_id)
                or (client_order_id and o.client_order_id == client_order_id)
            )
        ]
        return len(self.open_orders) != before

    def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        if symbol is None:
            n = len(self.open_orders)
            self.open_orders = []
            return n > 0
        before = len(self.open_orders)
        self.open_orders = [o for o in self.open_orders if o.symbol != symbol]
        return len(self.open_orders) != before

    def get_order(self, order_id: Optional[str] = None, symbol: Optional[str] = None, client_order_id: Optional[str] = None) -> Optional[Order]:
        for o in self.open_orders:
            if order_id and o.order_id == order_id:
                return o
            if client_order_id and o.client_order_id == client_order_id:
                return o
        return None

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        if symbol is None:
            return list(self.open_orders)
        return [o for o in self.open_orders if o.symbol == symbol]


def load_pair_df(
    exchange: str,
    pair: str,
    timeframe: str,
    *,
    data_dir: str = "data",
) -> pd.DataFrame:
    path = ohlcv_path(exchange, pair, timeframe, data_dir=data_dir)
    df = load_ohlcv(path)
    if df.empty:
        raise FileNotFoundError(f"回测数据为空: {path}")
    return df


def align_pair(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    timerange: Optional[str] = None,
) -> pd.DataFrame:
    """按 date inner join 两边 close/high/low，并可选裁剪 timerange。"""
    a = df_a.rename(columns={c: f"a_{c}" for c in ["open", "high", "low", "close", "volume"]})
    b = df_b.rename(columns={c: f"b_{c}" for c in ["open", "high", "low", "close", "volume"]})
    merged = pd.merge(a, b, on="date", how="inner", suffixes=("", ""))
    merged = merged.sort_values("date").reset_index(drop=True)
    if timerange:
        from tools.timerange import parse_timerange

        tr = parse_timerange(timerange)
        if tr.start_ms is not None:
            start = pd.to_datetime(tr.start_ms, unit="ms", utc=True)
            merged = merged[merged["date"] >= start]
        if tr.stop_ms is not None:
            stop = pd.to_datetime(tr.stop_ms, unit="ms", utc=True)
            merged = merged[merged["date"] <= stop]
        merged = merged.reset_index(drop=True)
    return merged
