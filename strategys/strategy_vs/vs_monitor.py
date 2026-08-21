#!/usr/bin/env python3
"""
两所公共 WSS 盘口对照：按 B 的 role 扣费后的净价差，打印到终端。

网格：样本 + 来回费用自适应上下沿；上沿以上开一侧、下沿以下开反向（带内持有，同向最多 max_lots）。
ledger.live=false 走模拟成交并记 CSV；true 走 DualLegBroker（B 按 role，A 市价，WSS 认仓）。
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import re
import sys
import time
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from accounts import AccountBook, AccountSnap, CombinedPnl  # noqa: E402
from adapters.factory import create_adapter  # noqa: E402
from feeds import (  # noqa: E402
    Quote,
    QuoteBook,
    _adapter_config,
    exec_fee_of,
    run_feed,
    taker_fee_of,
    venue_role,
)
from hedge import DualLegBroker  # noqa: E402
from journal import PaperJournal  # noqa: E402
from ledger import PositionLedger, SimBroker  # noqa: E402
from spread import (  # noqa: E402
    GridTick,
    SpreadGrid,
    SpreadWindow,
    load_windows,
    p_label,
    pair_legs,
    parse_percentiles,
    persist_path,
    save_windows,
    window_identity,
)


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _age_ms(quote: Optional[Quote]) -> Optional[int]:
    if quote is None or not quote.ts:
        return None
    return int(max(0.0, time.time() - quote.ts) * 1000)


def _is_stale(quote: Optional[Quote], stale_ms: int) -> bool:
    if quote is None or quote.bid is None or quote.ask is None:
        return True
    if quote.error:
        return True
    age = _age_ms(quote)
    return age is None or age > stale_ms


def _use_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    if not _use_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _disp_width(text: str) -> int:
    plain = re.sub(r"\033\[[0-9;]*m", "", text)
    width = 0
    for ch in plain:
        width += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
    return width


def _pad(text: str, width: int, align: str = ">") -> str:
    gap = max(0, width - _disp_width(text))
    if align == "<":
        return text + " " * gap
    return " " * gap + text


def _fmt_px(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if value >= 1000:
        return f"{value:,.2f}"
    if value >= 100:
        return f"{value:.2f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.6f}"


def _fmt_sz(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if value >= 100:
        return f"{value:.2f}"
    if value >= 1:
        return f"{value:.3f}"
    return f"{value:.4g}"


def _fmt_pct(value: Optional[float], signed: bool = False) -> str:
    if value is None:
        return "-"
    text = f"{value * 100:+.3f}%" if signed else f"{value * 100:.3f}%"
    if not signed:
        return text
    if value > 0:
        return _c("32", text)
    if value < 0:
        return _c("31", text)
    return _c("2", text)


def _fmt_money(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}"


def _fmt_pnl(value: Optional[float]) -> str:
    if value is None:
        return "-"
    text = f"{value:+,.2f}"
    if value > 0:
        return _c("32", text)
    if value < 0:
        return _c("31", text)
    return _c("2", text)


def _fmt_pos(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if abs(value) < 1e-12:
        return "0"
    text = f"{value:+.6g}"
    if value > 0:
        return _c("32", text)
    if value < 0:
        return _c("31", text)
    return text


def _acct_status(snap: Optional[AccountSnap]) -> str:
    if snap is None:
        return _c("33", "等待")
    if snap.error and snap.equity is None and snap.available is None and snap.pos_qty is None:
        return _c("31", str(snap.error)[:18])
    src = (snap.source or "").upper() or "-"
    if snap.error:
        src = _c("33", src)
    elif src == "WSS":
        src = _c("32", src)
    elif src == "REST":
        src = _c("33", src)
    age = ""
    if snap.ts:
        ms = int(max(0.0, time.time() - snap.ts) * 1000)
        age = f" {ms}ms" if ms < 1000 else f" {ms / 1000:.0f}s"
    return f"{src}{_c('2', age)}"


def _acct_pos(
    snap: Optional[AccountSnap], now: float, stale_sec: float
) -> tuple[Optional[float], float]:
    if snap is None or snap.pos_qty is None:
        return None, 0.0
    ts = float(snap.ts or 0.0)
    if ts and now - ts > stale_sec:
        return None, ts
    return float(snap.pos_qty), ts


def _merge_venue_keys(venue_cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(venue_cfg)
    try:
        from tools.generated_keys import merge_generated
    except Exception:
        return out
    exchange = str(out.get("exchange") or "").strip().lower()
    try:
        out = merge_generated(out, exchange, only_empty=True)
        if exchange in ("ondoperp", "ondoperps"):
            out = merge_generated(out, "ondo", only_empty=True)
        if exchange in ("rh_lighter", "rhlighter", "lighter_rh", "robinhood_lighter"):
            out = merge_generated(out, "lighter", only_empty=True)
    except Exception:
        return dict(venue_cfg)

    def _expand(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            return os.getenv(value[2:-1], "").strip()
        return value

    for key, value in list(out.items()):
        out[key] = _expand(value)
    return out


def _fmt_usd(value: Optional[float]) -> str:
    if value is None:
        return "-"
    text = f"{value:+.2f}"
    if value > 0:
        return _c("32", text)
    if value < 0:
        return _c("31", text)
    return text


def _age_text(ms: Optional[int], stale: bool) -> str:
    if ms is None:
        return _c("33", "等待")
    text = f"{ms}ms" if ms < 1000 else f"{ms / 1000:.1f}s"
    return _c("33", text) if stale else _c("2", text)


def _short(name: str) -> str:
    aliases = {
        "rh_lighter": "RH",
        "rhlighter": "RH",
        "lighter": "Lighter",
        "ondoperp": "Ondo",
        "ondoperps": "Ondo",
        "ondo": "Ondo",
        "popdex": "PopDEX",
    }
    return aliases.get(name.lower(), name)


def _clear_tty() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\033[H\033[J")


def _quote_status(q: Optional[Quote], stale: bool) -> str:
    if q is None:
        return _c("33", "连接中")
    if q.error and (stale or q.bid is None or q.ask is None):
        return _c("31", "断开")
    if stale:
        return _c("33", "过期")
    if (q.source or "").lower() == "rest":
        return _c("33", "REST")
    return _c("32", "OK")


def _window_sizes(win_cfg: Dict[str, Any]) -> tuple[int, int]:
    min_samples = max(1, int(win_cfg.get("min_samples", 30)))
    max_samples = int(win_cfg.get("max_samples", min_samples))
    if max_samples < min_samples:
        max_samples = min_samples
    return min_samples, max_samples


def _grid_cfg(vs_cfg: Dict[str, Any]) -> Dict[str, Any]:
    raw = vs_cfg.get("grid") or {}
    return {
        "fee_mult": float(raw.get("fee_mult", 1.3)),
        "q_lo": float(raw.get("q_lo", 10)),
        "q_hi": float(raw.get("q_hi", 90)),
        "max_lots": max(1, int(raw.get("max_lots", 5))),
        "step": max(1e-12, float(raw.get("step", 0.0001))),
    }


def _fee_tag(cfg: Dict[str, Any]) -> str:
    role = venue_role(cfg)
    return f"{role} {exec_fee_of(cfg) * 1e4:.1f}bp"


def _pair_legs_from_quotes(
    venues: Dict[str, Dict[str, Any]],
    qa: Quote,
    qb: Quote,
) -> tuple:
    a_cfg = venues["a"]
    b_cfg = venues["b"]
    a_name = _short(str(a_cfg.get("name") or a_cfg.get("exchange")))
    b_name = _short(str(b_cfg.get("name") or b_cfg.get("exchange")))
    return pair_legs(
        a_name=a_name,
        b_name=b_name,
        a_bid=float(qa.bid),
        a_ask=float(qa.ask),
        b_bid=float(qb.bid),
        b_ask=float(qb.ask),
        fee_a=taker_fee_of(a_cfg),
        fee_b=exec_fee_of(b_cfg),
        b_maker=venue_role(b_cfg) == "maker",
        a_bid_sz=qa.bid_sz,
        a_ask_sz=qa.ask_sz,
        b_bid_sz=qb.bid_sz,
        b_ask_sz=qb.ask_sz,
    )


def _maker_rest_ok(
    book: QuoteBook,
    venues: Dict[str, Dict[str, Any]],
    grid: SpreadGrid,
    delta: int,
    current_lots: int,
) -> bool:
    quotes = book.latest()
    qa = quotes.get("a")
    qb = quotes.get("b")
    if (
        qa is None
        or qb is None
        or qa.bid is None
        or qa.ask is None
        or qb.bid is None
        or qb.ask is None
    ):
        return False
    ab, ba = _pair_legs_from_quotes(venues, qa, qb)
    return grid.rest_ok(delta, ab.pct, ba.pct, current_lots)


def _order_delta(
    tick: Optional[GridTick],
    ledger: Optional[PositionLedger],
    *,
    quotes_ok: bool,
    hedge_busy: bool,
) -> int:
    """网格 ±1：行情过期或对账失败只平不开。"""
    if tick is None or hedge_busy:
        return 0
    delta = int(tick.delta)
    if delta not in (-1, 1):
        return 0
    if not quotes_ok and (ledger is None or not ledger.is_reduce(delta)):
        return 0
    if ledger is not None and not ledger.can_submit(delta):
        return 0
    return delta


def _execute_layer(
    hedge: DualLegBroker,
    ledger: PositionLedger,
    delta: int,
    reduce_only: bool,
    rest_ok=None,
):
    try:
        return hedge.execute(
            ledger, delta, reduce_only=reduce_only, rest_ok=rest_ok
        )
    except Exception as exc:
        ledger.abort_layer(f"一层异常 {exc}")
        return type("LayerFail", (), {"ok": False, "error": str(exc), "note": f"一层异常 {exc}"})()


def _tick_journal_kwargs(tick: Optional[GridTick], **extra: Any) -> Dict[str, Any]:
    delta = int(extra.get("delta") or getattr(tick, "delta", 0) or 0)
    ab = getattr(tick, "ab_pct", None)
    ba = getattr(tick, "ba_pct", None)
    # 本次下单方向对应净价差
    if delta > 0:
        edge = ab
    elif delta < 0:
        edge = ba
    else:
        edge = getattr(tick, "mag", None)
    out: Dict[str, Any] = {
        "mag": getattr(tick, "mag", None),
        "lower": getattr(tick, "lower", None),
        "upper": getattr(tick, "upper", None),
        "center": getattr(tick, "center", None),
        "cost": getattr(tick, "cost", None),
        "ab_pct": ab,
        "ba_pct": ba,
        "edge_pct": edge,
        "note": getattr(tick, "note", "") or "",
    }
    out.update(extra)
    return out


def _ledger_cfg(vs_cfg: Dict[str, Any]) -> Dict[str, Any]:
    raw = vs_cfg.get("ledger") or {}
    return {
        "qty": float(raw.get("qty", 0.001)),
        "fill_delay_sec": float(raw.get("fill_delay_sec", 0.5)),
        "leg_gap_sec": float(raw.get("leg_gap_sec", 0.25)),
        "rest_lag_sec": float(raw.get("rest_lag_sec", 0.0)),
        "reconcile_interval_sec": float(raw.get("reconcile_interval_sec", 2.0)),
        "pos_tolerance": float(raw.get("pos_tolerance", 1e-7)),
        "live": bool(raw.get("live", False)),
        "timeout_sec": float(raw.get("timeout_sec", 60.0)),
    }


def _wss_pos(accounts: AccountBook, slot: str) -> Optional[Decimal]:
    snap = accounts.latest().get(slot)
    if snap is None or snap.pos_qty is None:
        return None
    return Decimal(str(snap.pos_qty))


def _wss_bbo_b(book: QuoteBook) -> tuple[Optional[Decimal], Optional[Decimal]]:
    quote = book.latest().get("b")
    if quote is None or quote.bid is None or quote.ask is None:
        return None, None
    return Decimal(str(quote.bid)), Decimal(str(quote.ask))


def _state_bar(state: str, accounts_ready: bool = True) -> str:
    styles = {
        "idle": "1;32",
        "inflight": "1;33",
        "holding": "1;32",
        "reconcile_fail": "1;31",
    }
    labels = {
        "idle": "空闲",
        "inflight": "在途",
        "holding": "持有",
        "reconcile_fail": "对账失败",
    }
    current = _c(styles.get(state, "1"), labels.get(state, state))
    if state == "reconcile_fail":
        recon = _c("31", "对账失败")
    elif not accounts_ready:
        recon = _c("33", "对账等待")
    else:
        recon = _c("2", "对账正常")
    return f"{current}  {recon}"


def _band_bar(
    mag: Optional[float],
    lower: Optional[float],
    upper: Optional[float],
    width: int = 24,
) -> str:
    if mag is None or lower is None or upper is None or upper <= lower:
        return "-" * width
    span = upper - lower
    lo = lower - 0.5 * span
    hi = upper + 0.5 * span
    if hi <= lo:
        return "-" * width

    def _idx(value: float) -> int:
        pos = int(round((value - lo) / (hi - lo) * (width - 1)))
        return max(0, min(width - 1, pos))

    chars = ["-"] * width
    for i in range(_idx(lower), _idx(upper) + 1):
        chars[i] = "="
    chars[_idx(mag)] = "|"
    return "".join(chars)


def _leg_action(lots: int, delta: int, side: int) -> str:
    if lots == 0 and delta * side > 0:
        return _c("1;32", "开仓")
    if lots * side > 0 and delta * side > 0:
        return _c("1;36", "加仓")
    if lots * side > 0 and delta * side < 0:
        return _c("33", "平仓")
    if lots * side > 0:
        return _c("32", "持有")
    if lots == 0 and delta == 0:
        return _c("2", "空仓")
    return _c("2", "对侧")


def _render(
    *,
    vs_cfg: Dict[str, Any],
    venues: Dict[str, Dict[str, Any]],
    quotes: Dict[str, Quote],
    windows: Optional[Dict[str, SpreadWindow]] = None,
    grid: Optional[SpreadGrid] = None,
    ledger: Optional[PositionLedger] = None,
    accounts: Optional[Dict[str, AccountSnap]] = None,
    last_layer: str = "",
    hedge_busy: bool = False,
    live: bool = False,
    pnl: Optional[CombinedPnl] = None,
    paper: Optional[PaperJournal] = None,
) -> tuple[str, Optional[GridTick], bool]:
    stale_ms = int(vs_cfg.get("stale_ms", 2000))
    win_cfg = vs_cfg.get("window") or {}
    min_samples, max_samples = _window_sizes(win_cfg)
    percentiles = parse_percentiles(win_cfg.get("percentile", 90))
    gcfg = _grid_cfg(vs_cfg)
    a_cfg = venues["a"]
    b_cfg = venues["b"]
    a_raw = str(a_cfg.get("name") or a_cfg.get("exchange"))
    b_raw = str(b_cfg.get("name") or b_cfg.get("exchange"))
    a_name = _short(a_raw)
    b_name = _short(b_raw)
    qa = quotes.get("a")
    qb = quotes.get("b")
    a_stale = _is_stale(qa, stale_ms)
    b_stale = _is_stale(qb, stale_ms)
    width = 76
    rule = _c("2", "─" * width)
    now = time.strftime("%H:%M:%S")
    title_l = (
        f"{_c('1', a_name)} {_c('2', str(a_cfg.get('symbol')))}  vs  "
        f"{_c('1', b_name)} {_c('2', str(b_cfg.get('symbol')))}"
    )
    title_r = _c("2", f"{now}  价差网格")
    title_gap = max(2, width - _disp_width(title_l) - _disp_width(title_r))

    lines = [
        title_l + " " * title_gap + title_r,
        rule,
        f"{_pad('所', 8, '<')} {_pad('买一', 12)} {_pad('卖一', 12)} "
        f"{_pad('买量', 10)} {_pad('卖量', 10)} {_pad('延迟', 8)}  状态",
    ]
    for name, q, stale in (
        (a_name, qa, a_stale),
        (b_name, qb, b_stale),
    ):
        err = ""
        if q and q.error:
            err = "  " + _c("31", str(q.error)[:28])
        lines.append(
            f"{_pad(name, 8, '<')} {_pad(_fmt_px(q.bid if q else None), 12)} "
            f"{_pad(_fmt_px(q.ask if q else None), 12)} "
            f"{_pad(_fmt_sz(q.bid_sz if q else None), 10)} "
            f"{_pad(_fmt_sz(q.ask_sz if q else None), 10)} "
            f"{_pad(_age_text(_age_ms(q), stale), 8)}  {_quote_status(q, stale)}{err}"
        )

    lines.append(rule)
    lines.append(
        f"{_pad('所', 8, '<')} {_pad('净值$', 12)} {_pad('可用$', 12)} "
        f"{_pad('仓位(币)', 12)}  源"
    )
    for name, slot in ((a_name, "a"), (b_name, "b")):
        snap = (accounts or {}).get(slot)
        err = ""
        if snap and snap.error and (
            snap.equity is not None or snap.available is not None or snap.pos_qty is not None
        ):
            err = "  " + _c("33", str(snap.error)[:24])
        lines.append(
            f"{_pad(name, 8, '<')} {_pad(_fmt_money(snap.equity if snap else None), 12)} "
            f"{_pad(_fmt_money(snap.available if snap else None), 12)} "
            f"{_pad(_fmt_pos(snap.pos_qty if snap else None), 12)}  "
            f"{_acct_status(snap)}{err}"
        )
    if pnl is not None:
        sa = (accounts or {}).get("a")
        sb = (accounts or {}).get("b")
        tot = pnl.snapshot(
            sa.equity if sa else None,
            sb.equity if sb else None,
            sa.available if sa else None,
            sb.available if sb else None,
            sa.pos_qty if sa else None,
            sb.pos_qty if sb else None,
        )
        if tot["pnl"] is None:
            src = _c("33", "等待基线")
        else:
            src = "盈亏 " + _fmt_pnl(tot["pnl"])
        lines.append(
            f"{_pad('合计', 8, '<')} {_pad(_fmt_money(tot['equity']), 12)} "
            f"{_pad(_fmt_money(tot['available']), 12)} "
            f"{_pad(_fmt_pos(tot['net_pos']), 12)}  "
            f"{src}"
        )
        if tot["base"] is not None:
            lines.append(
                f"{_pad('', 8, '<')} "
                + _c("2", "A ")
                + _fmt_pnl(tot["pnl_a"])
                + _c("2", " / B ")
                + _fmt_pnl(tot["pnl_b"])
                + _c("2", f"  基线 {_fmt_money(tot['base'])}")
            )

    lines.append(rule)
    p_heads = "".join(f" {_pad(p_label(q), 8)}" for q in percentiles)
    lines.append(
        f"{_pad('方向', 16, '<')} {_pad('现净%', 9)} {_pad('估$', 8)} "
        f"{_pad('均', 8)}{p_heads} {_pad('n', 6)}  网格"
    )

    legs = []
    tick = grid.last if grid else None
    have_book = (
        qa is not None
        and qb is not None
        and qa.bid is not None
        and qa.ask is not None
        and qb.bid is not None
        and qb.ask is not None
    )
    if have_book:
        legs = list(_pair_legs_from_quotes(venues, qa, qb))
        if windows and not (a_stale or b_stale):
            windows["ab"].add(legs[0].pct)
            windows["ba"].add(legs[1].pct)
        lots_now = ledger.lots if ledger is not None else (grid.lots if grid else 0)
        if grid is not None and windows:
            grid.observe(
                windows["ab"].values(),
                windows["ba"].values(),
                lots_now,
            )
            tick = grid.peek(legs[0].pct, legs[1].pct, lots_now)

    sample_n = 0
    if windows:
        sample_n = min(windows["ab"].stats().n, windows["ba"].stats().n)
    warm = sample_n >= min_samples

    lots = ledger.lots if ledger is not None else (tick.lots if tick else (grid.lots if grid else 0))
    quotes_ok = not (a_stale or b_stale)
    delta = _order_delta(tick, ledger, quotes_ok=quotes_ok, hedge_busy=hedge_busy)
    win_keys = [("ab", a_name, b_name, 1), ("ba", b_name, a_name, -1)]
    if windows:
        for i, (key, buy_name, sell_name, side) in enumerate(win_keys):
            stats = windows[key].stats()
            current = legs[i].pct if len(legs) == 2 else None
            qty = legs[i].qty if len(legs) == 2 else None
            est = None
            if current is not None and len(legs) == 2:
                est = legs[i].pnl * qty if qty else legs[i].pnl
            label = f"买{buy_name}/卖{sell_name}"
            p_cols = "".join(
                f" {_pad(_fmt_pct(stats.by_p.get(q), signed=True), 8)}"
                for q in percentiles
            )
            lines.append(
                f"{_pad(label, 16, '<')} {_pad(_fmt_pct(current, signed=True), 9)} "
                f"{_pad(_fmt_usd(est), 8)} {_pad(_fmt_pct(stats.mean, signed=True), 8)}"
                f"{p_cols} {_pad(str(stats.n), 6)}  "
                f"{_leg_action(lots, delta, side)}"
            )

    lines.append(rule)
    if not warm:
        act = _c("2", f"采样 {sample_n}/{min_samples}")
    elif tick and tick.action == "开仓":
        act = _c("1;32", "开仓")
    elif tick and tick.action == "加仓":
        act = _c("1;36", "加仓")
    elif tick and tick.action == "反向":
        act = _c("1;35", "反向")
    elif tick and tick.action == "减仓":
        act = _c("33", "减仓")
    elif tick and tick.action == "持有":
        act = _c("32", "持有")
    elif lots == 0:
        act = _c("2", "观望")
    else:
        act = _c("32", "持有")
    hold = "空仓"
    if lots > 0:
        hold = f"买{a_name}/卖{b_name}"
    elif lots < 0:
        hold = f"买{b_name}/卖{a_name}"
    lower = tick.lower if tick else (grid.lower if grid else None)
    upper = tick.upper if tick else (grid.upper if grid else None)
    center = tick.center if tick else (grid.center if grid else None)
    cost = tick.cost if tick else (grid.cost if grid else None)
    band_w = tick.width if tick else (grid.width if grid else None)
    mag = tick.mag if tick else None
    next_add = tick.next_add if tick else None
    next_reduce = tick.next_reduce if tick else None
    max_lots = grid.max_lots if grid is not None else gcfg["max_lots"]
    step = grid.step if grid is not None else gcfg["step"]
    lines.append(
        f"带 {_band_bar(mag, lower, upper)}  "
        f"现 {_fmt_pct(mag, signed=True)}  "
        f"下沿 {_fmt_pct(lower)}  中枢 {_fmt_pct(center)}  上沿 {_fmt_pct(upper)}"
    )
    lines.append(
        f"动作 {act}  仓 {hold}  "
        f"{abs(lots)}/{max_lots}层  "
        f"间隔 {_fmt_pct(step)}  "
        f"下一加 {_fmt_pct(next_add)}  下一反向 {_fmt_pct(next_reduce)}  "
        f"来回 {_fmt_pct(cost)}  带宽 {_fmt_pct(band_w)}"
        + (_c("33", "  已冻") if tick and tick.frozen else "")
        + (_c("2", f"  {tick.note}") if tick and tick.note else "")
    )
    if ledger is not None:
        snap = ledger.snapshot()
        lines.append(
            f"账本 {_state_bar(snap.state, snap.accounts_ready)}  "
            f"纸 {a_name} {snap.pos_a:+.4g} / {b_name} {snap.pos_b:+.4g}  "
            f"{snap.lots:+d}/{max_lots}层"
            + (f"  在途{snap.pending}" if snap.pending else "")
            + ("" if (snap.can_open and not hedge_busy) else _c("33", "  禁开"))
            + (_c("33", "  只平") if snap.state == "reconcile_fail" else "")
            + (
                _c("33", "  超限只平")
                if ledger is not None and ledger.over_max_lots()
                else ""
            )
        )
        exp_a = snap.exp_a
        exp_b = snap.exp_b
        lines.append(
            f"     所 {a_name} {_fmt_pos(snap.exch_a)} / {b_name} {_fmt_pos(snap.exch_b)}  "
            f"期望 {_fmt_pos(exp_a)} / {_fmt_pos(exp_b)}"
            + (_c("2", "  实盘对账") if snap.live else _c("2", "  基线对账"))
        )
        if snap.note:
            lines.append(_c("2", f"     {snap.note}"))
        if snap.last_error:
            lines.append(_c("31", f"     {snap.last_error}"))
        if last_layer:
            lines.append(_c("2", f"     最近一层 {last_layer}"))
        if paper is not None:
            kind = "真单" if live else "模拟"
            lines.append(
                f"{kind} 开仓 {paper.opens}  平仓 {paper.closes}"
                + (_c("2", f"  {paper.last}") if paper.last else "")
            )

    persist_on = bool(win_cfg.get("persist", True))
    persist_note = "  已落盘" if persist_on else ""
    lines.append(rule)
    lines.append(
        _c(
            "2",
            f"FIFO {max_samples}  启动≥{min_samples}{persist_note}  "
            f"{a_name} {_fee_tag(a_cfg)} / {b_name} {_fee_tag(b_cfg)}  "
            f"带宽×{gcfg['fee_mult']:g}  "
            f"{'真单双腿' if live else '模拟成交'} "
            f"开{paper.opens if paper else 0}平{paper.closes if paper else 0}  "
            f"CSV {paper.path.name if paper else '-'}  "
            f"{'对账对照成交仓' if live else '对账对照启动基线'}  "
            f"断线/失败只平  合计盈亏=两所净值-启动基线",
        )
    )
    return "\n".join(lines), tick, quotes_ok


async def _print_loop(
    vs_cfg: Dict[str, Any],
    venues: Dict[str, Dict[str, Any]],
    book: QuoteBook,
    accounts: AccountBook,
    stop: asyncio.Event,
) -> None:
    interval = float(vs_cfg.get("print_interval_sec", 0.5))
    win_cfg = vs_cfg.get("window") or {}
    min_samples, maxlen = _window_sizes(win_cfg)
    persist_on = bool(win_cfg.get("persist", True))
    save_interval = float(win_cfg.get("save_interval_sec", 5))
    identity = window_identity(venues)
    store_path = persist_path(
        CURRENT_DIR,
        identity,
        override=win_cfg.get("persist_path"),
    )
    windows = {
        "ab": SpreadWindow(
            maxlen=maxlen,
            percentile=win_cfg.get("percentile", 90),
        ),
        "ba": SpreadWindow(
            maxlen=maxlen,
            percentile=win_cfg.get("percentile", 90),
        ),
    }
    gcfg = _grid_cfg(vs_cfg)
    grid = SpreadGrid(
        fee_a=taker_fee_of(venues["a"]),
        fee_b=exec_fee_of(venues["b"]),
        fee_mult=gcfg["fee_mult"],
        min_samples=min_samples,
        q_lo=gcfg["q_lo"],
        q_hi=gcfg["q_hi"],
        max_lots=gcfg["max_lots"],
        step=gcfg["step"],
    )
    lcfg = _ledger_cfg(vs_cfg)
    live = bool(lcfg["live"])
    ledger = PositionLedger(
        qty_per_layer=lcfg["qty"],
        pos_tolerance=lcfg["pos_tolerance"],
        live=live,
        max_lots=gcfg["max_lots"],
    )
    sim = None if live else SimBroker(
        fill_delay_sec=lcfg["fill_delay_sec"],
        leg_gap_sec=lcfg["leg_gap_sec"],
        rest_lag_sec=lcfg["rest_lag_sec"],
    )
    hedge = None
    adapter_a = None
    adapter_b = None
    if live:
        adapter_a = create_adapter(_adapter_config(venues["a"]))
        adapter_b = create_adapter(_adapter_config(venues["b"]))
        adapter_a.connect()
        adapter_b.connect()
        b_maker = venue_role(venues["b"]) == "maker"
        hedge = DualLegBroker(
            adapter_a,
            adapter_b,
            str(venues["a"].get("symbol") or ""),
            str(venues["b"].get("symbol") or ""),
            timeout_sec=lcfg["timeout_sec"],
            poll_sec=0.05,
            live=True,
            b_maker=b_maker,
            pos_lookup=lambda slot: _wss_pos(accounts, slot),
            bbo_lookup=lambda: _wss_bbo_b(book),
        )
        print(
            f"真单已开 qty={lcfg['qty']} timeout={lcfg['timeout_sec']:g}s "
            f"B {'Maker' if b_maker else '市价'}/A 市价  "
            f"{_fee_tag(venues['a'])} / {_fee_tag(venues['b'])}  "
            f"WSS 认仓  对账对照成交仓 断线/失败只平"
        )
    csv_name = f"{store_path.stem}_{'live' if live else 'paper'}.csv"
    paper = PaperJournal(store_path.with_name(csv_name))
    last_save = time.time()
    last_recon = 0.0
    last_layer = ""
    hedge_busy = False
    last_align = 0.0          # 后台敞口守护上次下单时间
    align_cooldown = float(vs_cfg.get("align_cooldown_sec", 10.0))
    order_task: Optional[asyncio.Task] = None
    pending_log: Optional[Dict[str, Any]] = None
    combined = CombinedPnl()
    if persist_on:
        _, saved_grid, saved_pnl = load_windows(store_path, identity, windows)
        grid.load(saved_grid)
        grid.lots = 0
        combined.load(saved_pnl)
    if sys.stdout.isatty():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
    try:
        while not stop.is_set():
            now = time.time()
            if sim is not None:
                sim.poll(ledger, now=now)
            if order_task is not None and order_task.done():
                with contextlib.suppress(Exception):
                    result = order_task.result()
                    note = ""
                    if result is not None:
                        note = str(getattr(result, "note", "") or "")
                        if getattr(result, "error", "") and not getattr(result, "ok", False):
                            note = str(result.error)
                    if pending_log is not None:
                        extra_note = str(pending_log.pop("note", "") or "")
                        if extra_note and note:
                            note = f"{extra_note} {note}"
                        elif extra_note:
                            note = extra_note
                        paper.record(
                            **pending_log,
                            lots_after=ledger.lots,
                            note=note,
                        )
                        last_layer = paper.last
                    elif note:
                        last_layer = note
                order_task = None
                pending_log = None
                hedge_busy = False
            snap = await book.snapshot()
            acct = await accounts.snapshot()
            if (
                not hedge_busy
                and (
                    (not ledger.accounts_ready)
                    or now - last_recon >= lcfg["reconcile_interval_sec"]
                )
            ):
                stale_sec = float(vs_cfg.get("account_stale_sec", 15.0))
                pos_a, ts_a = _acct_pos(acct.get("a"), now, stale_sec)
                pos_b, ts_b = _acct_pos(acct.get("b"), now, stale_sec)
                ledger.reconcile(
                    pos_a,
                    pos_b,
                    ts_a,
                    ts_b,
                    now=now,
                    live=live,
                )
                if ledger.accounts_ready:
                    last_recon = now
                    n = abs(ledger.lots)
                    if n and grid.peak_n < n:
                        grid.peak_n = n

            # 后台敞口守护：不论对账是否失败，只要 A+B 敞口超过容差就补 A
            # hedge_busy 时跳过（网格 execute 自己对齐），冷却 align_cooldown_sec
            if (
                live
                and hedge is not None
                and not hedge_busy
                and not ledger.inflight
                and ledger.accounts_ready
                and now - last_align >= align_cooldown
            ):
                stale_sec = float(vs_cfg.get("account_stale_sec", 15.0))
                pos_a_raw, _ = _acct_pos(acct.get("a"), now, stale_sec)
                pos_b_raw, _ = _acct_pos(acct.get("b"), now, stale_sec)
                if pos_a_raw is not None and pos_b_raw is not None:
                    _pa = Decimal(str(pos_a_raw))
                    _pb = Decimal(str(pos_b_raw))
                    _target = -_pb
                    _tol = max(Decimal(str(ledger.qty_per_layer)) * Decimal("0.05"), Decimal("1e-8"))
                    if abs(_pa - _target) > _tol:
                        if hedge.qty_per_layer <= 0:
                            hedge.qty_per_layer = ledger.qty_per_layer
                        _ok, _msg = hedge.align_a_only(_target)
                        last_layer = f"敞口补仓 {'OK' if _ok else 'ERR'} {_msg}"
                        last_align = now

            _clear_tty()
            text, tick, quotes_ok = _render(
                vs_cfg=vs_cfg,
                venues=venues,
                quotes=snap,
                windows=windows,
                grid=grid,
                ledger=ledger,
                accounts=acct,
                last_layer=last_layer,
                hedge_busy=hedge_busy,
                live=live,
                pnl=combined,
                paper=paper,
            )
            print(text, flush=True)
            grid.lots = ledger.lots
            delta = _order_delta(
                tick, ledger, quotes_ok=quotes_ok, hedge_busy=hedge_busy
            )
            if delta:
                qa = snap.get("a")
                qb = snap.get("b")
                px_a = px_b = None
                b_maker = venue_role(venues["b"]) == "maker"
                if qa is not None and qb is not None:
                    px_a = float(qa.ask if delta > 0 else qa.bid)
                    if b_maker:
                        px_b = float(qb.ask if delta > 0 else qb.bid)
                    else:
                        px_b = float(qb.bid if delta > 0 else qb.ask)
                lots_before = ledger.lots
                if ledger.is_reduce(delta):
                    action = "减仓"
                elif lots_before == 0:
                    action = "开仓"
                elif (lots_before > 0 and delta > 0) or (lots_before < 0 and delta < 0):
                    action = "加仓"
                else:
                    action = "反向"
                log_kw = _tick_journal_kwargs(
                    tick,
                    action=action,
                    delta=delta,
                    lots_before=lots_before,
                    qty=ledger.qty_per_layer,
                    px_a=px_a,
                    px_b=px_b,
                )
                if live and hedge is not None:
                    hedge_busy = True
                    pending_log = log_kw
                    reduce_only = ledger.is_reduce(delta)
                    rest_cb = None
                    if venue_role(venues["b"]) == "maker":
                        rest_cb = lambda d=delta, n=lots_before: _maker_rest_ok(
                            book, venues, grid, d, n
                        )
                    order_task = asyncio.create_task(
                        asyncio.to_thread(
                            _execute_layer,
                            hedge,
                            ledger,
                            delta,
                            reduce_only,
                            rest_cb,
                        )
                    )
                elif sim is not None and px_a is not None and px_b is not None:
                    if sim.submit(ledger, delta, px_a, px_b, now=time.time()):
                        sim.poll(ledger, now=time.time())
                        paper.record(**log_kw, lots_after=ledger.lots)
                        last_layer = paper.last
            now = time.time()
            if persist_on and now - last_save >= save_interval:
                try:
                    save_windows(store_path, identity, windows, grid=grid, pnl=combined)
                    last_save = now
                except OSError:
                    last_save = now
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
    finally:
        if order_task is not None and not order_task.done():
            order_task.cancel()
            with contextlib.suppress(Exception):
                await order_task
        for adapter in (adapter_a, adapter_b):
            if adapter is None:
                continue
            closer = getattr(adapter, "disconnect", None) or getattr(adapter, "close", None)
            if callable(closer):
                with contextlib.suppress(Exception):
                    closer()
        if persist_on:
            try:
                save_windows(store_path, identity, windows, grid=grid, pnl=combined)
            except OSError:
                pass
        if sys.stdout.isatty():
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()


async def _amain(config_path: str) -> None:
    cfg = _load_yaml(config_path)
    vs_cfg = cfg.get("vs") or {}
    venues = cfg.get("venues") or {}
    if "a" not in venues or "b" not in venues:
        raise SystemExit("config.venues 需要 a 和 b 两个交易所")
    stale_ms = int(vs_cfg.get("stale_ms", 2000))
    rest_interval = float(vs_cfg.get("rest_interval_sec", 1.0))
    account_rest = float(vs_cfg.get("account_rest_sec", 30.0))
    account_stale = float(vs_cfg.get("account_stale_sec", 15.0))
    for slot in ("a", "b"):
        if not venues[slot].get("exchange") or not venues[slot].get("symbol"):
            raise SystemExit(f"venues.{slot} 需要 exchange 和 symbol")
        venues[slot] = _merge_venue_keys(venues[slot])
        venues[slot].setdefault("stale_ms", stale_ms)
        venues[slot].setdefault("rest_interval_sec", rest_interval)
        venues[slot].setdefault("account_rest_sec", account_rest)
        venues[slot].setdefault("account_stale_sec", account_stale)

    book = QuoteBook()
    accounts = AccountBook()
    stop = asyncio.Event()
    tasks = [
        asyncio.create_task(
            run_feed("a", venues["a"], book, stop, accounts), name="feed-a"
        ),
        asyncio.create_task(
            run_feed("b", venues["b"], book, stop, accounts), name="feed-b"
        ),
        asyncio.create_task(
            _print_loop(vs_cfg, venues, book, accounts, stop), name="print"
        ),
    ]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        stop.set()
        raise
    finally:
        stop.set()
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=3.0,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="两所 WSS 盘口对照（扣 taker 费）")
    parser.add_argument(
        "-c",
        "--config",
        default=str(CURRENT_DIR / "config.yaml"),
        help="配置文件路径",
    )
    args = parser.parse_args()
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = str((Path.cwd() / config_path).resolve())
    try:
        asyncio.run(_amain(config_path))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
