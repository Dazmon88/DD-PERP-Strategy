"""双所回测：按对齐 5m 线推进，复用 VSStrategy。"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strategys.strategy_vs.backtest_adapter import (
    BacktestAdapter,
    align_pair,
    load_pair_df,
)
from strategys.strategy_vs.vs_core import Quote, VSStrategy


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _pos(adapter: BacktestAdapter) -> float:
    return float(adapter.position)


def _build_round_trips(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    把腿 A 的 fill 拼成开→平 round trip。
    开仓：kind in open/add（pos 从 0 变非 0 或加仓的第一笔）
    平仓：kind in close/reduce/flip 且仓位回到 0（或反向）
    """
    trips: List[Dict[str, Any]] = []
    open_fill: Optional[Dict[str, Any]] = None
    for t in trades:
        kind = t.get("kind")
        if kind in ("open", "add") and (open_fill is None or abs(float(t.get("pos_before", 0))) < 1e-12):
            open_fill = t
            continue
        if open_fill is None:
            continue
        if kind in ("close", "reduce", "flip") and abs(float(t.get("pos_after", 0))) < 1e-12:
            qty = float(open_fill["qty"])
            open_px = float(open_fill["price"])
            close_px = float(t["price"])
            side = open_fill["side"]  # buy=long, sell=short
            if side == "buy":
                pnl = (close_px - open_px) * qty
            else:
                pnl = (open_px - close_px) * qty
            fee = float(open_fill.get("fee", 0)) + float(t.get("fee", 0))
            trips.append(
                {
                    "open_time": open_fill["ts"],
                    "close_time": t["ts"],
                    "side": "long" if side == "buy" else "short",
                    "qty": qty,
                    "open_price": open_px,
                    "close_price": close_px,
                    "notional_open": float(open_fill.get("notional", qty * open_px)),
                    "notional_close": float(t.get("notional", qty * close_px)),
                    "fee": fee,
                    "pnl": pnl - fee,
                    "gross_pnl": pnl,
                }
            )
            open_fill = None
    return trips


def _fmt_ts(ts) -> str:
    return str(ts)


def run(config_path: str) -> int:
    cfg = _load_config(config_path)
    bt = cfg["backtest"]
    st = cfg["strategy"]

    initial_cash = float(bt.get("initial_cash", 1_000_000))
    df_a = load_pair_df(bt["exchange_a"], bt["pair_a"], bt["timeframe"], data_dir=bt.get("data_dir", "data"))
    df_b = load_pair_df(bt["exchange_b"], bt["pair_b"], bt["timeframe"], data_dir=bt.get("data_dir", "data"))
    merged = align_pair(df_a, df_b, timerange=bt.get("timerange") or None)
    if merged.empty:
        raise SystemExit("两边数据无交集，无法回测")

    def _leg_frame(prefix: str):
        cols = [f"{prefix}_{c}" for c in ("open", "high", "low", "close", "volume")]
        out = merged[["date"] + cols].copy()
        out.columns = ["date", "open", "high", "low", "close", "volume"]
        return out

    spread_bps = float(st.get("spread_bps", 0) or 0)
    use_bidask = bool(bt.get("use_bidask_for_spread", True))
    ad_a = BacktestAdapter(
        {"exchange_name": bt["exchange_a"], "symbol": bt["pair_a"]},
        exchange=bt["exchange_a"],
        pair=bt["pair_a"],
        timeframe=bt["timeframe"],
        df=_leg_frame("a"),
        fee_rate=float(bt.get("fee_rate_a", 0)),
        spread_bps=spread_bps if use_bidask else 0,
        initial_cash=initial_cash,
    )
    ad_b = BacktestAdapter(
        {"exchange_name": bt["exchange_b"], "symbol": bt["pair_b"]},
        exchange=bt["exchange_b"],
        pair=bt["pair_b"],
        timeframe=bt["timeframe"],
        df=_leg_frame("b"),
        fee_rate=float(bt.get("fee_rate_b", 0)),
        spread_bps=spread_bps if use_bidask else 0,
        initial_cash=initial_cash,
    )

    strategy = VSStrategy(
        order_size=float(st["order_size"]),
        max_position_size=float(st.get("max_position_size", 0)),
        min_profit_pct=float(st.get("min_profit_pct", 0.0005)),
        max_profit_pct=float(st.get("max_profit_pct", 0.003)),
        use_dynamic_profit_window=bool(st.get("use_dynamic_profit_window", False)),
        profit_buffer_pct=float(st.get("profit_buffer_pct", 0)),
        hedge_threshold=float(st.get("hedge_threshold", 1e-8)),
        hedge_cooldown_sec=float(st.get("hedge_cooldown_sec", 2.0)),
        threshold_mode=str(st.get("threshold_mode", "fixed")),
        lookback=int(st.get("lookback", 288)),
        open_q=float(st.get("open_q", 0.9)),
        close_q=float(st.get("close_q", 0.1)),
        open_z=float(st.get("open_z", 2.0)),
        close_z=float(st.get("close_z", 0.0)),
        min_edge=float(st.get("min_edge", 0.0003)),
    )

    n = len(merged)
    log_every = max(1, n // 40)
    print(
        f"初始资金: 每腿 {initial_cash:,.2f}，合计 {2 * initial_cash:,.2f} "
        f"| bars={n} | A={bt['exchange_a']} B={bt['exchange_b']}"
    )
    for i in range(n):
        ad_a.set_index(i)
        ad_b.set_index(i)
        ad_a.step()
        ad_b.step()

        ta = ad_a.get_ticker(bt["pair_a"])
        tb = ad_b.get_ticker(bt["pair_b"])
        qa = Quote(bid=ta["bid"], ask=ta["ask"], last=ta["last"], ts=ta["ts"])
        qb = Quote(bid=tb["bid"], ask=tb["ask"], last=tb["last"], ts=tb["ts"])

        pos_a = _pos(ad_a)
        act = strategy.decide_spread(qa, qb, pos_a)
        if act.kind in ("open", "close"):
            ad_a.place_order(
                symbol=bt["pair_a"],
                side=act.side,
                order_type="limit",
                quantity=Decimal(str(act.qty)),
                price=Decimal(str(act.price)),
                time_in_force="alo",
                reduce_only=act.reduce_only,
                client_order_id=f"vs_{i}_{act.kind}",
            )
        elif act.kind == "cancel":
            ad_a.cancel_all_orders(symbol=bt["pair_a"])

        pos_a = _pos(ad_a)
        pos_b = _pos(ad_b)
        bar_now = merged["date"].iloc[i].timestamp()
        hedge = strategy.decide_hedge(pos_a, pos_b, qb, now=bar_now)
        if hedge.kind == "hedge":
            ad_b.place_order(
                symbol=bt["pair_b"],
                side=hedge.side,
                order_type="market",
                quantity=Decimal(str(hedge.qty)),
                reduce_only=hedge.reduce_only,
                client_order_id=f"vs_{i}_hedge",
            )

        if i % log_every == 0 or i == n - 1:
            eq_a = float(ad_a.get_balance().equity)
            eq_b = float(ad_b.get_balance().equity)
            print(
                f"[{merged['date'].iloc[i]}] "
                f"closeA={ta['last']:.2f} closeB={tb['last']:.2f} "
                f"posA={_pos(ad_a):+.6f} posB={_pos(ad_b):+.6f} "
                f"net={_pos(ad_a)+_pos(ad_b):+.6f} "
                f"eqA={eq_a:.2f} eqB={eq_b:.2f} fills={len(ad_a.trades)+len(ad_b.trades)}"
            )

    trips = _build_round_trips(ad_a.trades)
    print("\n===== 成交明细（腿 A 开/平）=====")
    if not trips:
        print("(无完整开平仓 round-trip)")
    else:
        print(
            f"{'#':>4}  {'开仓时间':<28}  {'平仓时间':<28}  "
            f"{'方向':<6}  {'数量':>10}  {'开仓价':>10}  {'平仓价':>10}  "
            f"{'开仓名义':>12}  {'毛PnL':>10}  {'手续费':>8}  {'净PnL':>10}"
        )
        for i, tr in enumerate(trips, 1):
            print(
                f"{i:>4}  {_fmt_ts(tr['open_time']):<28}  {_fmt_ts(tr['close_time']):<28}  "
                f"{tr['side']:<6}  {tr['qty']:>10.6f}  {tr['open_price']:>10.2f}  {tr['close_price']:>10.2f}  "
                f"{tr['notional_open']:>12.2f}  {tr['gross_pnl']:>+10.4f}  {tr['fee']:>8.4f}  {tr['pnl']:>+10.4f}"
            )

    print("\n===== 腿 B 对冲成交 =====")
    if not ad_b.trades:
        print("(无对冲成交)")
    else:
        print(
            f"{'#':>4}  {'时间':<28}  {'方向':<6}  {'数量':>10}  "
            f"{'价格':>10}  {'名义':>12}  {'kind':<6}  {'手续费':>8}"
        )
        for i, t in enumerate(ad_b.trades, 1):
            print(
                f"{i:>4}  {_fmt_ts(t['ts']):<28}  {t['side']:<6}  {t['qty']:>10.6f}  "
                f"{t['price']:>10.2f}  {t['notional']:>12.2f}  {t['kind']:<6}  {t['fee']:>8.4f}"
            )

    def _summary(ad: BacktestAdapter):
        bal = ad.get_balance()
        return {
            "equity": float(bal.equity),
            "position": float(ad.position),
            "fills": len(ad.trades),
            "volume_base": float(ad.volume_base),
            "volume_quote": float(ad.volume_quote),
            "fee_paid": float(ad.fee_paid),
            "realized_pnl": float(ad.realized_pnl),
        }

    s_a, s_b = _summary(ad_a), _summary(ad_b)
    total_eq = s_a["equity"] + s_b["equity"]
    start_eq = 2 * initial_cash
    trip_pnl = sum(t["pnl"] for t in trips) if trips else 0.0
    print("\n===== 回测结果 =====")
    print(f"区间: {merged['date'].iloc[0]} -> {merged['date'].iloc[-1]} ({n} bars)")
    print(f"初始资金: 每腿 {initial_cash:,.2f}，合计 {start_eq:,.2f}")
    print(f"A({bt['exchange_a']} {bt['pair_a']}): {s_a}")
    print(f"B({bt['exchange_b']} {bt['pair_b']}): {s_b}")
    print(
        f"成交量合计: base={s_a['volume_base']+s_b['volume_base']:.6f}  "
        f"quote={s_a['volume_quote']+s_b['volume_quote']:,.2f}"
    )
    print(f"A 完整开平: {len(trips)} 笔，开平净PnL合计: {trip_pnl:+.4f}")
    print(f"合计权益: {total_eq:,.2f}  初始: {start_eq:,.2f}  PnL: {total_eq-start_eq:+.2f}")
    print(f"净敞口: {_pos(ad_a)+_pos(ad_b):+.6f}  未平挂单A: {len(ad_a.open_orders)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="strategy_vs 回测")
    p.add_argument("-c", "--config", required=True, help="config_vs yaml")
    args = p.parse_args()
    return run(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
