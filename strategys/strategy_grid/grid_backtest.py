#!/usr/bin/env python3
"""
网格方案回测：按 config 中 strategies 列表逐个跑，最后对照。

mode: long | short | neutral | adaptive
K 线默认来自币安（与实盘 Risk 同源）。每根已收盘 K 线作为一轮网格。
限价成交用 H/L 触及；无盘口、无资金费，只作方案可行性对照。
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd
import requests
import yaml

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parents[1]
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(project_root))

from grid_mm import generate_grid_arrays  # noqa: E402
from risk.indicators import to_binance_symbol  # noqa: E402
from tools.ohlcv_store import load_ohlcv  # noqa: E402

try:
    import talib
except ImportError as e:
    raise SystemExit("需要 TA-Lib：pip install TA-Lib") from e


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fetch_binance_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """分页拉币安现货 K 线。"""
    import time as _time

    symbol = to_binance_symbol(symbol)
    end_ms = int(pd.Timestamp.utcnow().timestamp() * 1000)
    start_ms = end_ms - int(days) * 24 * 3600 * 1000
    rows: List[list] = []
    cursor = start_ms
    url = "https://api.binance.com/api/v3/klines"
    while cursor < end_ms:
        resp = requests.get(
            url,
            params={
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": 1000,
            },
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        last_open = int(batch[-1][0])
        nxt = last_open + 1
        if nxt <= cursor:
            break
        cursor = nxt
        if len(batch) < 1000:
            break
        _time.sleep(0.15)

    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows)
    # 币安 kline: 0 open_time, 1 open, 2 high, 3 low, 4 close, 5 volume
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[0], unit="ms", utc=True),
            "open": pd.to_numeric(df[1]),
            "high": pd.to_numeric(df[2]),
            "low": pd.to_numeric(df[3]),
            "close": pd.to_numeric(df[4]),
            "volume": pd.to_numeric(df[5]),
        }
    )
    out = out.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return out


def add_indicators(df: pd.DataFrame, adx_period: int, rsi_period: int) -> pd.DataFrame:
    out = df.copy()
    high, low, close = out["high"], out["low"], out["close"]
    out["adx"] = talib.ADX(high, low, close, timeperiod=adx_period)
    out["rsi"] = talib.RSI(close, timeperiod=rsi_period)
    out["plus_di"] = talib.PLUS_DI(high, low, close, timeperiod=adx_period)
    out["minus_di"] = talib.MINUS_DI(high, low, close, timeperiod=adx_period)
    # 用上一根已收盘值下决策，避免未来函数
    for col in ("adx", "rsi", "plus_di", "minus_di"):
        out[col] = out[col].shift(1)
    return out


def classify_regime(
    adx: Optional[float],
    rsi: Optional[float],
    plus_di: Optional[float],
    minus_di: Optional[float],
    *,
    adx_flatten: float,
    adx_range: float,
    rsi_up: float,
    rsi_down: float,
) -> str:
    """返回 flatten | long | short | neutral。"""
    if adx is None or pd.isna(adx):
        return "neutral"
    if adx > adx_flatten:
        return "flatten"
    direction = None
    if rsi is not None and not pd.isna(rsi):
        if rsi >= rsi_up:
            direction = "long"
        elif rsi <= rsi_down:
            direction = "short"
    if direction is None and plus_di is not None and minus_di is not None:
        if not pd.isna(plus_di) and not pd.isna(minus_di):
            if plus_di > minus_di:
                direction = "long"
            elif minus_di > plus_di:
                direction = "short"
    if adx < adx_range:
        return direction or "neutral"
    # 25–30：弱趋势，跟方向但不 flatten
    return direction or "neutral"


@dataclass
class SimResult:
    name: str
    equity: List[float] = field(default_factory=list)
    fills: int = 0
    flatten_n: int = 0
    fees: float = 0.0
    regimes: Dict[str, int] = field(default_factory=dict)
    max_abs_pos: float = 0.0
    final_pos: float = 0.0
    final_equity: float = 0.0
    ret_pct: float = 0.0
    max_dd_pct: float = 0.0
    buy_fills: int = 0
    sell_fills: int = 0
    volume: float = 0.0
    pnl: float = 0.0


def _max_dd(equity: Sequence[float]) -> float:
    peak = equity[0] if equity else 0.0
    dd = 0.0
    for x in equity:
        if x > peak:
            peak = x
        if peak > 0:
            dd = min(dd, x / peak - 1.0)
    return abs(dd) * 100.0


def _fill_side(
    prices: List[float],
    last: float,
    now: float,
    *,
    falling: bool,
) -> List[float]:
    """价格从 last 走到 now 时被触及的挂单价（按路径顺序）。"""
    if falling:
        touched = [p for p in prices if now <= p <= last]
        return sorted(touched, reverse=True)
    touched = [p for p in prices if last <= p <= now]
    return sorted(touched)


def _optional_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def parse_strategies(cfg: dict) -> List[dict]:
    """从 yaml 读 strategies 列表。每项: name, mode, close_step_mult, 可选买卖倍数。"""
    raw = cfg.get("strategies")
    if not raw:
        raise SystemExit("config 需要 strategies 列表（至少一个方向）")
    grid_cfg = cfg.get("grid") or {}
    default_close = float(grid_cfg.get("close_step_mult", 1.0))
    out: List[dict] = []
    seen = set()
    for i, item in enumerate(raw):
        if isinstance(item, str):
            item = {"name": item, "mode": item}
        if not isinstance(item, dict):
            raise SystemExit(f"strategies[{i}] 必须是对象或字符串")
        mode = str(item.get("mode") or "long").strip().lower()
        if mode not in ("long", "short", "neutral", "adaptive"):
            raise SystemExit(
                f"strategies[{i}].mode 必须是 long / short / neutral / adaptive，收到 {mode!r}"
            )
        name = str(item.get("name") or mode).strip()
        if not name:
            raise SystemExit(f"strategies[{i}].name 不能为空")
        if name in seen:
            raise SystemExit(f"strategies 名称重复: {name}")
        seen.add(name)
        flip = item.get("flatten_on_flip")
        out.append(
            {
                "name": name,
                "mode": mode,
                "close_step_mult": float(item.get("close_step_mult", default_close)),
                "buy_step_mult": _optional_float(item.get("buy_step_mult")),
                "sell_step_mult": _optional_float(item.get("sell_step_mult")),
                "flatten_on_flip": None if flip is None else bool(flip),
            }
        )
    return out


def simulate(
    df: pd.DataFrame,
    *,
    strategy: dict,
    grid_cfg: dict,
    regime_cfg: dict,
    initial_cash: float,
    maker_fee: float,
    taker_fee: float,
    flatten_on_flip: bool,
) -> SimResult:
    qty = float(grid_cfg["order_quantity"])
    max_pos = qty * float(grid_cfg.get("max_position_multiplier", 8))
    price_step = float(grid_cfg["price_step"])
    grid_count = int(grid_cfg["grid_count"])
    lower = float(grid_cfg["lower_price"])
    upper = float(grid_cfg["upper_price"])
    strat_mode = strategy["mode"]
    close_mult = float(strategy["close_step_mult"])
    buy_mult = strategy.get("buy_step_mult")
    sell_mult = strategy.get("sell_step_mult")
    if strategy.get("flatten_on_flip") is not None:
        flatten_on_flip = bool(strategy["flatten_on_flip"])

    cash = float(initial_cash)
    pos = 0.0
    res = SimResult(name=strategy["name"])
    last_mode = "neutral"

    for row in df.itertuples(index=False):
        o, h, l, c = float(row.open), float(row.high), float(row.low), float(row.close)
        adx = None if pd.isna(row.adx) else float(row.adx)
        rsi = None if pd.isna(row.rsi) else float(row.rsi)
        pdi = None if pd.isna(row.plus_di) else float(row.plus_di)
        mdi = None if pd.isna(row.minus_di) else float(row.minus_di)

        if strat_mode == "adaptive":
            regime = classify_regime(
                adx,
                rsi,
                pdi,
                mdi,
                adx_flatten=float(regime_cfg["adx_flatten"]),
                adx_range=float(regime_cfg["adx_range"]),
                rsi_up=float(regime_cfg["rsi_up"]),
                rsi_down=float(regime_cfg["rsi_down"]),
            )
        else:
            regime = strat_mode

        res.regimes[regime] = res.regimes.get(regime, 0) + 1

        def flatten(px: float, fee_rate: float) -> None:
            nonlocal cash, pos
            if abs(pos) < 1e-12:
                return
            notional = abs(pos) * px
            fee = notional * fee_rate
            cash += pos * px - fee
            res.fees += fee
            res.volume += notional
            pos = 0.0
            res.flatten_n += 1

        if strat_mode == "adaptive":
            if regime == "flatten":
                flatten(o, taker_fee)
                last_mode = "flatten"
                res.equity.append(cash + pos * c)
                res.max_abs_pos = max(res.max_abs_pos, abs(pos))
                continue
            mode = regime if regime in ("long", "short", "neutral") else "neutral"
            if flatten_on_flip and last_mode in ("long", "short") and mode in ("long", "short"):
                if mode != last_mode:
                    flatten(o, taker_fee)
            last_mode = mode
        else:
            mode = strat_mode

        buys, sells = generate_grid_arrays(
            o,
            price_step,
            grid_count,
            signed_position_size=Decimal(str(pos)),
            order_quantity=Decimal(str(qty)),
            max_position_multiplier=grid_cfg.get("max_position_multiplier", 8),
            lower_price=lower,
            upper_price=upper,
            mode=mode,
            close_step_mult=close_mult,
            buy_step_mult=buy_mult,
            sell_step_mult=sell_mult,
        )
        buys = [float(x) for x in buys]
        sells = [float(x) for x in sells]

        path = [o, l, h, c] if c >= o else [o, h, l, c]
        last_px = o
        for px in path[1:]:
            falling = px < last_px - 1e-12
            rising = px > last_px + 1e-12
            if falling:
                for bp in _fill_side(buys, last_px, px, falling=True):
                    if pos + qty > max_pos + 1e-12:
                        continue
                    if mode == "short" and pos >= 0:
                        continue
                    fee = bp * qty * maker_fee
                    notional = bp * qty
                    cash -= notional + fee
                    pos += qty
                    res.fees += fee
                    res.volume += notional
                    res.fills += 1
                    res.buy_fills += 1
                    buys = [x for x in buys if x != bp]
            if rising:
                for sp in _fill_side(sells, last_px, px, falling=False):
                    if pos - qty < -max_pos - 1e-12:
                        continue
                    if mode == "long" and pos <= 0:
                        continue
                    fee = sp * qty * maker_fee
                    notional = sp * qty
                    cash += notional - fee
                    pos -= qty
                    res.fees += fee
                    res.volume += notional
                    res.fills += 1
                    res.sell_fills += 1
                    sells = [x for x in sells if x != sp]
            last_px = px

        res.max_abs_pos = max(res.max_abs_pos, abs(pos))
        res.equity.append(cash + pos * c)

    if res.equity:
        res.final_equity = res.equity[-1]
        res.pnl = res.final_equity - initial_cash
        res.ret_pct = (res.final_equity / initial_cash - 1.0) * 100.0
        res.max_dd_pct = _max_dd(res.equity)
    res.final_pos = pos
    return res


def _print_report(rows: List[SimResult], initial_cash: float, meta: str) -> None:
    print(meta)
    print()
    nw = max(12, max((len(r.name) for r in rows), default=12) + 1)
    ranked = sorted(rows, key=lambda x: x.pnl, reverse=True)

    hdr = (
        f"{'方案':<{nw}} {'总盈亏':>12} {'收益%':>8} {'最大回撤%':>10} "
        f"{'总费用':>12} {'总交易量':>14} {'成交':>6} {'买/卖':>9}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in ranked:
        print(
            f"{r.name:<{nw}} {r.pnl:12.2f} {r.ret_pct:8.2f} {r.max_dd_pct:10.2f} "
            f"{r.fees:12.2f} {r.volume:14.2f} {r.fills:6d} "
            f"{r.buy_fills:4d}/{r.sell_fills:<4d}"
        )
    print()
    hdr2 = (
        f"{'方案':<{nw}} {'flatten':>8} {'末仓':>8} {'峰值|仓|':>8} "
        f"{'期末权益':>12}"
    )
    print(hdr2)
    print("-" * len(hdr2))
    for r in ranked:
        print(
            f"{r.name:<{nw}} {r.flatten_n:8d} {r.final_pos:8.4f} {r.max_abs_pos:8.4f} "
            f"{r.final_equity:12.2f}"
        )
    print()
    for r in ranked:
        if r.regimes:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(r.regimes.items()))
            print(f"  {r.name} 状态占用: {parts}")
        print(
            f"  {r.name} 总盈亏={r.pnl:.2f}  总费用={r.fees:.2f}  "
            f"总交易量={r.volume:.2f}  费用/量={((r.fees / r.volume * 100) if r.volume else 0):.4f}%"
        )
    print()
    if ranked:
        best, worst = ranked[0], ranked[-1]
        print(
            f"对比: 共 {len(ranked)} 套，按总盈亏 {best.name} 最好 ({best.pnl:.2f})，"
            f"{worst.name} 最差 ({worst.pnl:.2f})"
        )
    print("说明: 总盈亏=期末盯市权益-初始资金（含未实现）；总交易量=成交名义本金（含 flatten）。")
    print("flatten 按开盘市价+taker。无资金费/排队损失，只能对比相对优劣。")
    print(f"初始资金 {initial_cash:.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="网格多方向回测对照（由 config.strategies 指定）")
    parser.add_argument(
        "-c",
        "--config",
        default=str(current_dir / "config_grid_backtest.yaml"),
        help="回测配置 yaml",
    )
    parser.add_argument("--csv", default="", help="覆盖配置中的本地 CSV")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--interval", default="", help="覆盖 K 线周期，如 1h / 5m")
    args = parser.parse_args()

    cfg = _load_yaml(args.config)
    bt = cfg.get("backtest") or {}
    grid_cfg = cfg.get("grid") or {}
    regime_cfg = cfg.get("regime") or {}

    symbol = str(bt.get("symbol", "BTCUSDT"))
    interval = str(args.interval or bt.get("interval") or "1h")
    days = int(args.days if args.days is not None else bt.get("days", 180))
    csv_path = str(args.csv or bt.get("csv") or "").strip()
    initial_cash = float(bt.get("initial_cash", 100000))
    maker_fee = float(bt.get("maker_fee", 0.0002))
    taker_fee = float(bt.get("taker_fee", 0.0005))
    flatten_on_flip = bool(bt.get("flatten_on_flip", True))

    if csv_path:
        df = load_ohlcv(csv_path)
        if df.empty:
            raise SystemExit(f"CSV 为空或不存在: {csv_path}")
        print(f"加载本地 K 线: {csv_path}  rows={len(df)}")
    else:
        print(f"下载币安 K 线: {to_binance_symbol(symbol)} {interval} 最近 {days} 天...")
        df = fetch_binance_klines(symbol, interval, days)
        if df.empty:
            raise SystemExit("币安返回空 K 线")
        print(f"  {df['date'].iloc[0]} → {df['date'].iloc[-1]}  n={len(df)}")

    df = add_indicators(
        df,
        adx_period=int(regime_cfg.get("adx_period", 14)),
        rsi_period=int(regime_cfg.get("rsi_period", 14)),
    )
    warmup = max(int(regime_cfg.get("adx_period", 14)) * 3, 40)
    df = df.iloc[warmup:].reset_index(drop=True)
    if df.empty:
        raise SystemExit("K 线不足以计算 ADX/RSI")

    strategies = parse_strategies(cfg)
    print(f"对照方案: {', '.join(s['name'] + '(' + s['mode'] + ')' for s in strategies)}")
    results: List[SimResult] = []
    for strategy in strategies:
        results.append(
            simulate(
                df,
                strategy=strategy,
                grid_cfg=grid_cfg,
                regime_cfg=regime_cfg,
                initial_cash=initial_cash,
                maker_fee=maker_fee,
                taker_fee=taker_fee,
                flatten_on_flip=flatten_on_flip,
            )
        )

    meta = (
        f"{to_binance_symbol(symbol)} {interval}  "
        f"{df['date'].iloc[0]} → {df['date'].iloc[-1]}  bars={len(df)}"
    )
    _print_report(results, initial_cash, meta)


if __name__ == "__main__":
    main()
