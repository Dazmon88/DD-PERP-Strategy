"""双所实盘：与回测共用 VSStrategy；支持 --dry-run。"""
from __future__ import annotations

import argparse
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters.factory import create_adapter
from strategys.strategy_vs.vs_core import Quote, VSStrategy

try:
    from tools.generated_keys import merge_generated
except Exception:  # pragma: no cover
    def merge_generated(base, name, only_empty=False):  # type: ignore
        return base


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_quote(adapter, symbol: str) -> Quote:
    t = adapter.get_ticker(symbol)
    bid = float(t.get("bid") or t.get("bestBid") or t.get("last") or t.get("mid") or 0)
    ask = float(t.get("ask") or t.get("bestAsk") or t.get("last") or t.get("mid") or 0)
    last = float(t.get("last") or t.get("mark") or (bid + ask) / 2 if bid and ask else 0)
    if not bid or not ask:
        mid = float(t.get("mid") or t.get("last") or 0)
        bid = bid or mid
        ask = ask or mid
    return Quote(bid=bid, ask=ask, last=last, ts=int(t.get("ts") or 0))


def _get_pos(adapter, symbol: str) -> float:
    pos = adapter.get_position(symbol)
    if not pos:
        return 0.0
    qty = float(pos.size)
    return -abs(qty) if pos.side in ("short", "sell") else abs(qty)


class LiveRunner:
    def __init__(self, cfg: Dict[str, Any], dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        st = cfg["strategy"]
        self.strategy = VSStrategy(
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
        live = cfg.get("live", {})
        ex_cfg = cfg["exchanges"]
        self.key_a = live.get("legs", {}).get("a") or live.get("order_exchange") or "a"
        self.key_b = live.get("legs", {}).get("b") or live.get("hedge_exchange") or "b"
        self.pair_a = live.get("pair_a") or ex_cfg[self.key_a].get("symbol")
        self.pair_b = live.get("pair_b") or ex_cfg[self.key_b].get("symbol")
        self.poll = float(live.get("poll_interval_sec", 2.0))

        cfg_a = dict(ex_cfg[self.key_a])
        cfg_b = dict(ex_cfg[self.key_b])
        cfg_a = merge_generated(cfg_a, cfg_a.get("exchange_name", self.key_a))
        cfg_b = merge_generated(cfg_b, cfg_b.get("exchange_name", self.key_b))

        self.ad_a = None
        self.ad_b = None
        if not dry_run:
            self.ad_a = create_adapter(cfg_a)
            self.ad_b = create_adapter(cfg_b)
            try:
                self.ad_a.connect()
            except Exception as e:
                print(f"[warn] {self.key_a} connect: {e}")
            try:
                self.ad_b.connect()
            except Exception as e:
                print(f"[warn] {self.key_b} connect: {e}")

    def _place(self, adapter, symbol: str, *, side: str, order_type: str, qty: float, price=None, reduce_only=False, tag=""):
        if self.dry_run:
            print(f"[dry-run] {tag} {side} {qty} {price or 'mkt'} reduce={reduce_only}")
            return None
        return adapter.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=Decimal(str(qty)),
            price=Decimal(str(price)) if price is not None else None,
            time_in_force="alo",
            reduce_only=reduce_only,
        )

    def loop(self) -> int:
        print(f"[live] A={self.key_a}:{self.pair_a} B={self.key_b}:{self.pair_b} dry_run={self.dry_run}")
        while True:
            try:
                qa = _get_quote(self.ad_a, self.pair_a)
                qb = _get_quote(self.ad_b, self.pair_b)
            except Exception as e:
                print(f"[warn] quote: {e}")
                time.sleep(self.poll)
                continue
            pos_a = _get_pos(self.ad_a, self.pair_a)
            pos_b = _get_pos(self.ad_b, self.pair_b)

            act = self.strategy.decide_spread(qa, qb, pos_a)
            if act.kind in ("open", "close"):
                self._place(
                    self.ad_a,
                    self.pair_a,
                    side=act.side,
                    order_type="limit",
                    qty=act.qty,
                    price=act.price,
                    reduce_only=act.reduce_only,
                    tag=f"A.{act.kind}",
                )
            elif act.kind == "cancel":
                if self.dry_run:
                    print(f"[dry-run] A.cancel_all")
                else:
                    try:
                        self.ad_a.cancel_all_orders(symbol=self.pair_a)
                    except Exception as e:
                        print(f"[warn] cancel A: {e}")

            # A 可能已在本轮成交，重新读持仓再对冲
            pos_a = _get_pos(self.ad_a, self.pair_a)
            pos_b = _get_pos(self.ad_b, self.pair_b)
            hedge = self.strategy.decide_hedge(pos_a, pos_b, qb)
            if hedge.kind == "hedge":
                self._place(
                    self.ad_b,
                    self.pair_b,
                    side=hedge.side,
                    order_type="market",
                    qty=hedge.qty,
                    reduce_only=hedge.reduce_only,
                    tag="B.hedge",
                )

            print(
                f"[tick] A {qa.bid:.2f}/{qa.ask:.2f}  B {qb.bid:.2f}/{qb.ask:.2f}  "
                f"posA={pos_a:+.6f} posB={pos_b:+.6f} net={pos_a+pos_b:+.6f}  "
                f"act={act.kind}:{act.reason}"
            )
            time.sleep(self.poll)


def main() -> int:
    p = argparse.ArgumentParser(description="strategy_vs 实盘")
    p.add_argument("-c", "--config", required=True)
    p.add_argument("--dry-run", action="store_true", help="只打印，不下单")
    args = p.parse_args()
    cfg = _load_config(args.config)
    return LiveRunner(cfg, dry_run=args.dry_run).loop()


if __name__ == "__main__":
    raise SystemExit(main())
