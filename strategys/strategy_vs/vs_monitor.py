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
import signal
import sys
import time
import unicodedata
from decimal import Decimal
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
from pairs import (  # noqa: E402
    PairSpec,
    enabled_pairs,
    load_pairs,
    pair_venues,
    peer_map,
    resolve_pairs_path,
    symbols_for_slot,
)
from journal import PaperJournal, RunLog  # noqa: E402
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


@dataclass
class PairRuntime:
    spec: PairSpec
    venues: Dict[str, Dict[str, Any]]
    windows: Dict[str, SpreadWindow]
    grid: SpreadGrid
    ledger: PositionLedger
    sim: Optional[SimBroker]
    hedge: Optional[DualLegBroker]
    paper: PaperJournal
    identity: Dict[str, Any]
    store_path: Path
    combined: CombinedPnl = field(default_factory=CombinedPnl)
    last_layer: str = ""
    last_recon: float = 0.0
    last_align: float = 0.0
    last_save: float = 0.0
    last_recon_log: float = 0.0
    last_ready: Optional[bool] = None
    last_exec_end: float = 0.0
    last_fail_ts: float = 0.0
    pending_log: Optional[Dict[str, Any]] = None
    order_task: Any = None


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
    """有粘性仓就用。仓位 WSS 不是每秒推，超时清掉会导致一直对账等待。"""
    if snap is None or snap.pos_qty is None:
        return None, 0.0
    return float(snap.pos_qty), float(snap.ts or 0.0)


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
    key_a: str = "a",
    key_b: str = "b",
) -> bool:
    quotes = book.latest()
    qa = quotes.get(key_a)
    qb = quotes.get(key_b)
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


def _signal_score(tick: Optional[GridTick], delta: int) -> float:
    """出带越深越优先，避免永远只执行 CSV 第一对。"""
    if tick is None or delta not in (-1, 1):
        return -1.0
    mag = tick.mag
    lo, hi = tick.lower, tick.upper
    if mag is None:
        return 0.0
    if lo is not None and mag < lo:
        return float(lo - mag)
    if hi is not None and mag > hi:
        return float(mag - hi)
    return 0.0


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


def _pair_busy(rt: PairRuntime) -> bool:
    task = rt.order_task
    return task is not None and not task.done()


def _settle_layer(rt: PairRuntime, runlog: RunLog) -> None:
    task = rt.order_task
    if task is None or not task.done():
        return
    result = None
    note = ""
    err = ""
    exec_fields: Dict[str, Any] = {}
    try:
        result = task.result()
    except Exception as exc:
        err = f"一层异常 {exc}"
        runlog.line(err, pair=rt.spec.name)
        rt.last_fail_ts = time.time()
    if result is not None:
        note = str(getattr(result, "note", "") or "")
        err = str(getattr(result, "error", "") or "") or err
        if err and not getattr(result, "ok", False):
            note = err
        logs = list(getattr(result, "logs", None) or [])
        if not getattr(result, "ok", False):
            for line in logs[-20:]:
                runlog.line(str(line), pair=rt.spec.name)
            if err:
                runlog.line(f"错误 {err}", pair=rt.spec.name)
            elif note:
                runlog.line(f"结束 {note}", pair=rt.spec.name)
        jf = getattr(result, "journal_fields", None)
        if callable(jf):
            exec_fields = jf()
    ok = bool(getattr(result, "ok", False)) if result is not None else False
    b_before = exec_fields.get("pos_b_before")
    b_after = exec_fields.get("pos_b_after")
    b_moved = False
    try:
        if b_before is not None and b_after is not None:
            b_moved = abs(float(b_after) - float(b_before)) > 1e-12
    except (TypeError, ValueError):
        b_moved = False
    if rt.pending_log is not None and "让出执行" in note:
        rt.last_layer = note
        runlog.line(f"让出 {note}", pair=rt.spec.name)
    elif rt.pending_log is not None and (ok or b_moved):
        extra_note = str(rt.pending_log.pop("note", "") or "")
        if extra_note and note:
            note = f"{extra_note} {note}"
        elif extra_note:
            note = extra_note
        rt.paper.record(
            **rt.pending_log,
            **exec_fields,
            lots_after=rt.ledger.lots,
            note=note,
        )
        rt.last_layer = rt.paper.last
        runlog.line(rt.paper.last, pair=rt.spec.name)
    elif rt.pending_log is not None:
        rt.last_fail_ts = time.time()
        rt.last_layer = note or err
        runlog.line(
            f"未挂成 {note or err or '一层未齐'} B仓{b_before}→{b_after}",
            pair=rt.spec.name,
        )
    elif note:
        rt.last_layer = note
    rt.pending_log = None
    rt.last_exec_end = time.time()
    rt.order_task = None


async def _stop_executors(
    runtimes: List[PairRuntime],
    adapter_a: Any,
    adapter_b: Any,
    runlog: RunLog,
    live: bool,
) -> None:
    """停执行线程、撤两所挂单、解开账本在途。"""
    runlog.line("正在退出：停止执行并撤挂单")
    for rt in runtimes:
        if rt.hedge is not None:
            rt.hedge.request_stop()
    if live:

        def _wipe() -> None:
            if adapter_b is not None:
                try:
                    adapter_b.cancel_all_orders()
                    runlog.line("B 所全部挂单已撤")
                except Exception as exc:
                    runlog.line(f"B 所全撤失败 {exc}")
                    for rt in runtimes:
                        with contextlib.suppress(Exception):
                            adapter_b.cancel_all_orders(symbol=rt.spec.symbol_b)
            if adapter_a is None:
                return
            get_open = getattr(adapter_a, "get_open_orders", None)
            cancel_one = getattr(adapter_a, "cancel_order", None)
            if not callable(get_open) or not callable(cancel_one):
                return
            for rt in runtimes:
                try:
                    orders = get_open(symbol=rt.spec.symbol_a) or []
                except Exception as exc:
                    runlog.line(f"A 所查挂单失败 {rt.spec.symbol_a} {exc}", pair=rt.spec.name)
                    continue
                for od in orders:
                    oid = str(getattr(od, "order_id", "") or "")
                    if not oid:
                        continue
                    with contextlib.suppress(Exception):
                        cancel_one(order_id=oid, symbol=rt.spec.symbol_a)
                    runlog.line(f"A 所撤 {rt.spec.symbol_a} {oid}", pair=rt.spec.name)

        await asyncio.to_thread(_wipe)
    wait = [
        rt.order_task
        for rt in runtimes
        if rt.order_task is not None and not rt.order_task.done()
    ]
    if wait:
        _done, pending = await asyncio.wait(wait, timeout=10.0)
        if pending:
            runlog.line(f"仍有 {len(pending)} 个执行任务超时，取消等待")
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
    for rt in runtimes:
        _settle_layer(rt, runlog)
        if rt.ledger.inflight:
            rt.ledger.abort_layer("进程退出")


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
        from hedge import LayerResult, LegSnap
        from decimal import Decimal as _D

        zero = _D("0")
        fail = LayerResult(
            ok=False,
            delta=delta,
            a=LegSnap("a", hedge.symbol_a, "", zero, zero),
            b=LegSnap("b", hedge.symbol_b, "", zero, zero),
            error=str(exc),
            note=f"一层异常 {exc}",
        )
        fail.logs.append(fail.note)
        return fail


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


def _wss_bbo(book: QuoteBook, key: str = "b") -> tuple[Optional[Decimal], Optional[Decimal]]:
    quote = book.latest().get(key)
    if quote is None or quote.bid is None or quote.ask is None:
        return None, None
    return Decimal(str(quote.bid)), Decimal(str(quote.ask))


def _wss_bbo_b(book: QuoteBook) -> tuple[Optional[Decimal], Optional[Decimal]]:
    return _wss_bbo(book, "b")


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


def _acct_bal_status(snap: Optional[AccountSnap]) -> str:
    """净值/可用的新鲜度用 balance_ts，避免仓位心跳把账户延迟刷掉或撑到几十秒。"""
    if snap is None:
        return _c("33", "等待")
    if snap.error and snap.equity is None and snap.available is None:
        return _c("31", str(snap.error)[:18])
    src = (snap.source or "").upper() or "-"
    if snap.error:
        src = _c("33", src)
    elif src == "WSS":
        src = _c("32", src)
    elif src == "REST":
        src = _c("33", src)
    ts = float(snap.balance_ts or 0.0)
    age = ""
    if ts:
        ms = int(max(0.0, time.time() - ts) * 1000)
        age = f" {ms}ms" if ms < 1000 else f" {ms / 1000:.0f}s"
    return f"{src}{_c('2', age)}"


def _px_txt(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if value >= 1000:
        return f"{value:,.2f}"
    if value >= 100:
        return f"{value:.2f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.6f}"


def _age_cell(ms: Optional[int], stale: bool, width: int = 6) -> str:
    if ms is None:
        raw = "—"
    elif ms < 1000:
        raw = f"{ms}ms"
    else:
        raw = f"{ms / 1000:.1f}s"
    cell = _pad(raw, width)
    return _c("33", cell) if stale or ms is None else _c("2", cell)


def _fmt_bp_cell(value: Optional[float], width: int = 7, signed: bool = True) -> str:
    if value is None:
        raw = "-"
    elif signed:
        raw = f"{value * 1e4:+.1f}"
    else:
        raw = f"{value * 1e4:.1f}"
    cell = _pad(raw, width)
    if value is None:
        return cell
    if not signed:
        return cell
    if value > 0:
        return _c("32", cell)
    if value < 0:
        return _c("31", cell)
    return _c("2", cell)


def _bbo_cell(q: Optional[Quote], stale_ms: int) -> str:
    """买 / 卖 / 延迟 / 状态，各列定宽。"""
    w_px, w_age, w_st = 12, 6, 4
    if q is None:
        return (
            f"{_pad('', w_px)} {_pad('', w_px)} "
            f"{_age_cell(None, True, w_age)} {_pad(_c('33', '等待'), w_st, '<')}"
        )
    stale = _is_stale(q, stale_ms)
    if q.error and (q.bid is None or q.ask is None):
        err = _c("31", str(q.error)[: w_px * 2 + 1])
        return f"{_pad(err, w_px * 2 + 1, '<')} {_age_cell(_age_ms(q), True, w_age)} {_pad(_c('31', '断开'), w_st, '<')}"
    st = _quote_status(q, stale)
    return (
        f"{_pad(_px_txt(q.bid), w_px)} {_pad(_px_txt(q.ask), w_px)} "
        f"{_age_cell(_age_ms(q), stale, w_age)} {_pad(st, w_st, '<')}"
    )


def _bbo_header(name: str) -> str:
    w_px, w_age, w_st = 12, 6, 4
    return (
        f"{_pad(name + '买', w_px, '<')} {_pad(name + '卖', w_px, '<')} "
        f"{_pad('延迟', w_age, '<')} {_pad('态', w_st, '<')}"
    )


def _sync_pair_tick(
    *,
    vs_cfg: Dict[str, Any],
    venues: Dict[str, Dict[str, Any]],
    quotes: Dict[str, Quote],
    windows: Optional[Dict[str, SpreadWindow]],
    grid: Optional[SpreadGrid],
    ledger: Optional[PositionLedger],
    key_a: str,
    key_b: str,
) -> tuple[Optional[GridTick], bool, Optional[Quote], Optional[Quote]]:
    stale_ms = int(vs_cfg.get("stale_ms", 2000))
    qa = quotes.get(key_a) or quotes.get("a")
    qb = quotes.get(key_b) or quotes.get("b")
    a_stale = _is_stale(qa, stale_ms)
    b_stale = _is_stale(qb, stale_ms)
    tick = grid.last if grid else None
    have_book = (
        qa is not None
        and qb is not None
        and qa.bid is not None
        and qa.ask is not None
        and qb.bid is not None
        and qb.ask is not None
    )
    if have_book and qa is not None and qb is not None:
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
    return tick, not (a_stale or b_stale), qa, qb


def _pair_action_label(
    tick: Optional[GridTick],
    *,
    warm: bool,
    sample_n: int,
    min_samples: int,
    lots: int,
    ledger: Optional[PositionLedger] = None,
    hedge_busy: bool = False,
) -> str:
    if not warm:
        return _c("2", f"采样{sample_n}/{min_samples}")
    blocked = False
    if tick is not None and int(getattr(tick, "delta", 0) or 0) in (-1, 1):
        if hedge_busy:
            blocked = True
        elif ledger is not None and not ledger.can_submit(int(tick.delta)):
            blocked = True
    if tick and tick.action == "开仓":
        if blocked:
            return _c("33", "在途" if hedge_busy else "禁开")
        return _c("1;32", "开仓")
    if tick and tick.action == "加仓":
        return _c("33", "在途") if blocked else _c("1;36", "加仓")
    if tick and tick.action == "反向":
        return _c("33", "在途") if blocked else _c("1;35", "反向")
    if tick and tick.action == "减仓":
        return _c("33", "减仓")
    if tick and tick.action == "持有":
        return _c("32", "持有")
    if lots == 0:
        return _c("2", "观望")
    return _c("32", "持有")


def _render_multi_board(
    *,
    vs_cfg: Dict[str, Any],
    venues: Dict[str, Dict[str, Any]],
    runtimes: List[PairRuntime],
    quotes: Dict[str, Quote],
    accounts: Dict[str, AccountSnap],
    live: bool,
    ticks: List[tuple],
) -> str:
    stale_ms = int(vs_cfg.get("stale_ms", 2000))
    win_cfg = vs_cfg.get("window") or {}
    min_samples, _ = _window_sizes(win_cfg)
    a_name = _short(str(venues["a"].get("name") or venues["a"].get("exchange")))
    b_name = _short(str(venues["b"].get("name") or venues["b"].get("exchange")))
    sa = accounts.get("a")
    sb = accounts.get("b")
    now = time.strftime("%H:%M:%S")
    running = [rt.spec.name for rt in runtimes if _pair_busy(rt)]
    busy = f"执行 {','.join(running)}" if running else "各对独立"
    w_pair, w_qty, w_bp, w_lot, w_act, w_led, w_pos = 5, 8, 7, 6, 10, 8, 15
    rule = _c("2", "─" * 118)
    lines = [
        f"{_c('1', a_name)} vs {_c('1', b_name)}   {_c('2', now)}   "
        f"{len(runtimes)}对   {busy}   "
        f"{'真单' if live else '模拟'}   每所一条连接",
        f"{_pad('所', 6, '<')} {_pad('净值$', 12)} {_pad('可用$', 12)}  账户源",
        f"{_pad(a_name, 6, '<')} {_pad(_fmt_money(sa.equity if sa else None), 12)} "
        f"{_pad(_fmt_money(sa.available if sa else None), 12)}  {_acct_bal_status(sa)}",
        f"{_pad(b_name, 6, '<')} {_pad(_fmt_money(sb.equity if sb else None), 12)} "
        f"{_pad(_fmt_money(sb.available if sb else None), 12)}  {_acct_bal_status(sb)}",
        rule,
        f"{_pad('对', w_pair, '<')} {_pad('qty', w_qty)} "
        f"{_bbo_header(a_name)} {_bbo_header(b_name)} "
        f"{_pad('AB', w_bp)} {_pad('BA', w_bp)} {_pad('层', w_lot)} "
        f"{_pad('动作', w_act, '<')} {_pad('账本', w_led, '<')} {_pad('仓A/B', w_pos, '<')}",
    ]
    for rt, tick, quotes_ok, qa, qb in ticks:
        sample_n = 0
        if rt.windows:
            sample_n = min(rt.windows["ab"].stats().n, rt.windows["ba"].stats().n)
        warm = sample_n >= min_samples
        lots = rt.ledger.lots
        ab = ba = None
        if (
            qa is not None
            and qb is not None
            and qa.bid is not None
            and qa.ask is not None
            and qb.bid is not None
            and qb.ask is not None
        ):
            legs = list(_pair_legs_from_quotes(rt.venues, qa, qb))
            ab, ba = legs[0].pct, legs[1].pct
        led = rt.ledger.snapshot()
        if led.state == "reconcile_fail":
            book_s = _c("31", "对账失败")
        elif not led.accounts_ready:
            book_s = _c("33", "对账等待")
        elif _pair_busy(rt):
            book_s = _c("33", "在途")
        elif not led.can_open:
            book_s = _c("33", "只平")
        else:
            book_s = _c("2", "正常")
        pa = _acct_display(accounts, rt.spec.book_a(), "a")
        pb = _acct_display(accounts, rt.spec.book_b(), "b")
        pos = f"{_fmt_pos(pa.pos_qty if pa else None)}/{_fmt_pos(pb.pos_qty if pb else None)}"
        act = _pair_action_label(
            tick,
            warm=warm,
            sample_n=sample_n,
            min_samples=min_samples,
            lots=lots,
            ledger=rt.ledger,
            hedge_busy=_pair_busy(rt),
        )
        extra = ""
        if not quotes_ok:
            extra += "  行情过期只平"
        lines.append(
            f"{_pad(rt.spec.name, w_pair, '<')} {_pad(f'{rt.spec.qty:g}', w_qty)} "
            f"{_bbo_cell(qa, stale_ms)} {_bbo_cell(qb, stale_ms)} "
            f"{_fmt_bp_cell(ab, w_bp)} {_fmt_bp_cell(ba, w_bp)} "
            f"{_pad(f'{lots:+d}/{rt.grid.max_lots}', w_lot)} "
            f"{_pad(act, w_act, '<')} {_pad(book_s, w_led, '<')} {_pad(pos, w_pos, '<')}"
        )
        mag = tick.mag if tick else None
        lower = tick.lower if tick else rt.grid.lower
        upper = tick.upper if tick else rt.grid.upper
        lines.append(
            _c(
                "2",
                f"{_pad('', w_pair)} {_pad('', w_qty)} "
                f"{_band_bar(mag, lower, upper, 24)}  "
                f"现{_fmt_bp_cell(mag, 7)} 下{_fmt_bp_cell(lower, 6, signed=False)} "
                f"上{_fmt_bp_cell(upper, 6, signed=False)} "
                f"来回{_fmt_bp_cell(tick.cost if tick else rt.grid.cost, 6, signed=False)} "
                f"×{rt.spec.fee_mult:g}{extra}",
            )
        )
    lines.append(rule)
    return "\n".join(lines)


def _acct_display(
    accounts: Optional[Dict[str, AccountSnap]],
    pos_key: str,
    slot: str,
) -> Optional[AccountSnap]:
    """净值看所级账户，仓位看品种 key。"""
    pos = (accounts or {}).get(pos_key)
    bal = (accounts or {}).get(slot)
    if pos is None and bal is None:
        return None
    if pos is None:
        return bal
    if bal is None:
        return pos
    return AccountSnap(
        venue=pos.venue,
        equity=bal.equity if bal.equity is not None else pos.equity,
        available=bal.available if bal.available is not None else pos.available,
        pos_qty=pos.pos_qty,
        pos_symbol=pos.pos_symbol or bal.pos_symbol,
        source=pos.source or bal.source,
        ts=max(float(pos.ts or 0), float(bal.ts or 0)),
        balance_ts=float(bal.balance_ts or pos.balance_ts or 0),
        error=pos.error or bal.error,
    )


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
    key_a: str = "a",
    key_b: str = "b",
    pair_name: str = "",
    compact: bool = False,
    show_equity: bool = True,
    show_footer: bool = True,
    observe: bool = True,
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
    if observe:
        tick, quotes_ok, qa, qb = _sync_pair_tick(
            vs_cfg=vs_cfg,
            venues=venues,
            quotes=quotes,
            windows=windows,
            grid=grid,
            ledger=ledger,
            key_a=key_a,
            key_b=key_b,
        )
    else:
        qa = quotes.get(key_a) or quotes.get("a")
        qb = quotes.get(key_b) or quotes.get("b")
        quotes_ok = not (_is_stale(qa, stale_ms) or _is_stale(qb, stale_ms))
        tick = grid.last if grid else None
    a_stale = _is_stale(qa, stale_ms)
    b_stale = _is_stale(qb, stale_ms)
    width = 76
    rule = _c("2", "─" * width)
    now = time.strftime("%H:%M:%S")
    title_pair = pair_name or f"{a_cfg.get('symbol')} / {b_cfg.get('symbol')}"
    title_l = (
        f"{_c('1', title_pair)}  {_c('1', a_name)} {_c('2', str(a_cfg.get('symbol')))}  vs  "
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
    if show_equity:
        lines.append(
            f"{_pad('所', 8, '<')} {_pad('净值$', 12)} {_pad('可用$', 12)} "
            f"{_pad('仓位(币)', 12)}  源"
        )
        for name, slot, pos_key in (
            (a_name, "a", key_a),
            (b_name, "b", key_b),
        ):
            snap = _acct_display(accounts, pos_key, slot)
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
            sa = _acct_display(accounts, key_a, "a")
            sb = _acct_display(accounts, key_b, "b")
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

    if not compact:
        lines.append(rule)
        p_heads = "".join(f" {_pad(p_label(q), 8)}" for q in percentiles)
        lines.append(
            f"{_pad('方向', 16, '<')} {_pad('现净%', 9)} {_pad('估$', 8)} "
            f"{_pad('均', 8)}{p_heads} {_pad('n', 6)}  网格"
        )

    legs = []
    have_book = (
        qa is not None
        and qb is not None
        and qa.bid is not None
        and qa.ask is not None
        and qb.bid is not None
        and qb.ask is not None
    )
    if have_book and qa is not None and qb is not None:
        legs = list(_pair_legs_from_quotes(venues, qa, qb))

    sample_n = 0
    if windows:
        sample_n = min(windows["ab"].stats().n, windows["ba"].stats().n)
    warm = sample_n >= min_samples

    lots = ledger.lots if ledger is not None else (tick.lots if tick else (grid.lots if grid else 0))
    delta = _order_delta(tick, ledger, quotes_ok=quotes_ok, hedge_busy=hedge_busy)
    win_keys = [("ab", a_name, b_name, 1), ("ba", b_name, a_name, -1)]
    if windows and not compact:
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
        if paper is not None:
            kind = "真单" if live else "模拟"
            lines.append(f"{kind} 开仓 {paper.opens}  平仓 {paper.closes}")

    persist_on = bool(win_cfg.get("persist", True))
    persist_note = "  已落盘" if persist_on else ""
    if show_footer:
        lines.append(rule)
        fee_mult = grid.fee_mult if grid is not None else gcfg["fee_mult"]
        lines.append(
            _c(
                "2",
                f"FIFO {max_samples}  启动≥{min_samples}{persist_note}  "
                f"{a_name} {_fee_tag(a_cfg)} / {b_name} {_fee_tag(b_cfg)}  "
                f"带宽×{fee_mult:g}  qty {ledger.qty_per_layer if ledger else '-'}  "
                f"{'真单双腿' if live else '模拟成交'} "
                f"开{paper.opens if paper else 0}平{paper.closes if paper else 0}  "
                f"CSV {paper.path.name if paper else '-'}  "
                f"{'对账对照成交仓' if live else '对账对照启动基线'}  "
                f"断线/失败只平",
            )
        )
    return "\n".join(lines), tick, quotes_ok


def _load_pair_specs(
    vs_cfg: Dict[str, Any], venues: Dict[str, Dict[str, Any]]
) -> List[PairSpec]:
    path = resolve_pairs_path(vs_cfg, CURRENT_DIR)
    if path is not None:
        specs = enabled_pairs(load_pairs(path))
        if not specs:
            raise SystemExit(f"{path} 没有 enabled=1 的交易对")
        return specs
    sa = str(venues["a"].get("symbol") or "").strip()
    sb = str(venues["b"].get("symbol") or "").strip()
    if not sa or not sb:
        raise SystemExit("未配置 vs.pairs_csv，且 venues.a/b 缺少 symbol")
    gcfg = _grid_cfg(vs_cfg)
    lcfg = _ledger_cfg(vs_cfg)
    return [
        PairSpec(
            name=sa,
            symbol_a=sa,
            symbol_b=sb,
            qty=lcfg["qty"],
            max_lots=gcfg["max_lots"],
            fee_mult=gcfg["fee_mult"],
        )
    ]


def _pair_store_path(
    spec: PairSpec,
    venues: Dict[str, Dict[str, Any]],
    win_cfg: Dict[str, Any],
    n_pairs: int,
) -> tuple[Dict[str, Any], Path]:
    identity = window_identity(venues)
    override = win_cfg.get("persist_path")
    if override and n_pairs > 1:
        base = persist_path(CURRENT_DIR, identity, override=override)
        store = base.with_name(f"{base.stem}_{spec.name}{base.suffix}")
        return identity, store
    if n_pairs > 1:
        override = None
    return identity, persist_path(CURRENT_DIR, identity, override=override)


async def _print_loop(
    vs_cfg: Dict[str, Any],
    venues: Dict[str, Dict[str, Any]],
    book: QuoteBook,
    accounts: AccountBook,
    stop: asyncio.Event,
    specs: List[PairSpec],
) -> None:
    interval = float(vs_cfg.get("print_interval_sec", 0.5))
    win_cfg = vs_cfg.get("window") or {}
    min_samples, maxlen = _window_sizes(win_cfg)
    persist_on = bool(win_cfg.get("persist", True))
    save_interval = float(win_cfg.get("save_interval_sec", 5))
    gcfg = _grid_cfg(vs_cfg)
    lcfg = _ledger_cfg(vs_cfg)
    live = bool(lcfg["live"])
    multi = len(specs) > 1
    raw_log = vs_cfg.get("log_path") or "vs_monitor.log"
    log_path = CURRENT_DIR / Path(str(raw_log)).name
    runlog = RunLog(log_path)
    print(f"诊断日志 {log_path}")
    runtimes: List[PairRuntime] = []
    adapter_a = None
    adapter_b = None
    b_maker = venue_role(venues["b"]) == "maker"
    if live:
        adapter_a = create_adapter(_adapter_config(venues["a"]))
        adapter_b = create_adapter(_adapter_config(venues["b"]))
        adapter_a.connect()
        adapter_b.connect()
        names = ",".join(s.name for s in specs)
        print(
            f"真单已开 对={names} timeout={lcfg['timeout_sec']:g}s "
            f"B {'Maker' if b_maker else '市价'}/A 市价  "
            f"{_fee_tag(venues['a'])} / {_fee_tag(venues['b'])}  "
            f"所级 WSS/账户各一次  每对独立挂单  断线/失败只平"
        )
        runlog.line(
            f"真单 对={names} timeout={lcfg['timeout_sec']:g}s "
            f"B={'Maker' if b_maker else 'taker'} live={live}"
        )
    for spec in specs:
        pv = pair_venues(venues, spec)
        identity, store_path = _pair_store_path(spec, pv, win_cfg, len(specs))
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
        grid = SpreadGrid(
            fee_a=taker_fee_of(pv["a"]),
            fee_b=exec_fee_of(pv["b"]),
            fee_mult=spec.fee_mult,
            min_samples=min_samples,
            q_lo=gcfg["q_lo"],
            q_hi=gcfg["q_hi"],
            max_lots=spec.max_lots,
            step=gcfg["step"],
        )
        ledger = PositionLedger(
            qty_per_layer=spec.qty,
            pos_tolerance=lcfg["pos_tolerance"],
            live=live,
            max_lots=spec.max_lots,
        )
        sim = None if live else SimBroker(
            fill_delay_sec=lcfg["fill_delay_sec"],
            leg_gap_sec=lcfg["leg_gap_sec"],
            rest_lag_sec=lcfg["rest_lag_sec"],
        )
        ka, kb = spec.book_a(), spec.book_b()
        hedge = None
        if live and adapter_a is not None and adapter_b is not None:
            hedge = DualLegBroker(
                adapter_a,
                adapter_b,
                spec.symbol_a,
                spec.symbol_b,
                timeout_sec=lcfg["timeout_sec"],
                poll_sec=0.05,
                live=True,
                b_maker=b_maker,
                pos_lookup=lambda slot, ka=ka, kb=kb: _wss_pos(
                    accounts, ka if slot == "a" else kb
                ),
                pos_apply=lambda slot, qty, ka=ka: (
                    accounts.apply_fill(ka, qty) if slot == "a" else None
                ),
                bbo_lookup=lambda kb=kb: _wss_bbo(book, kb),
                log=lambda m, name=spec.name: runlog.line(m, pair=name),
            )
        csv_name = f"{store_path.stem}_{'live' if live else 'paper'}.csv"
        paper = PaperJournal(store_path.with_name(csv_name))
        rt = PairRuntime(
            spec=spec,
            venues=pv,
            windows=windows,
            grid=grid,
            ledger=ledger,
            sim=sim,
            hedge=hedge,
            paper=paper,
            identity=identity,
            store_path=store_path,
        )
        if persist_on:
            _, saved_grid, saved_pnl = load_windows(store_path, identity, windows)
            grid.load(saved_grid)
            grid.lots = 0
            rt.combined.load(saved_pnl)
        rt.last_save = time.time()
        runtimes.append(rt)

    last_align_any = 0.0
    align_cooldown = float(vs_cfg.get("align_cooldown_sec", 10.0))
    if sys.stdout.isatty():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
    try:
        while not stop.is_set():
            now = time.time()
            for rt in runtimes:
                if rt.sim is not None:
                    rt.sim.poll(rt.ledger, now=now)
                _settle_layer(rt, runlog)
            snap = await book.snapshot()
            acct = await accounts.snapshot()
            stale_sec = float(vs_cfg.get("account_stale_sec", 15.0))
            for rt in runtimes:
                if rt.ledger.inflight:
                    continue
                ka, kb = rt.spec.book_a(), rt.spec.book_b()
                if (not rt.ledger.accounts_ready) or (
                    now - rt.last_recon >= lcfg["reconcile_interval_sec"]
                ):
                    pos_a, ts_a = _acct_pos(acct.get(ka), now, stale_sec)
                    pos_b, ts_b = _acct_pos(acct.get(kb), now, stale_sec)
                    rt.ledger.reconcile(
                        pos_a,
                        pos_b,
                        ts_a,
                        ts_b,
                        now=now,
                        live=live,
                    )
                    if rt.ledger.accounts_ready:
                        rt.last_recon = now
                        n = abs(rt.ledger.lots)
                        if n and rt.grid.peak_n < n:
                            rt.grid.peak_n = n
                    ready = rt.ledger.accounts_ready
                    err = str(rt.ledger.last_error or "")
                    if rt.last_ready is None or rt.last_ready != ready:
                        runlog.line(
                            f"对账 {'就绪' if ready else '未就绪'} lots={rt.ledger.lots} {err}",
                            pair=rt.spec.name,
                        )
                        rt.last_ready = ready
                        rt.last_recon_log = now
                    elif not ready and now - rt.last_recon_log >= 15:
                        runlog.line(f"对账仍等待 {err}", pair=rt.spec.name)
                        rt.last_recon_log = now

            if live and now - last_align_any >= align_cooldown:
                for rt in runtimes:
                    if (
                        rt.hedge is None
                        or _pair_busy(rt)
                        or rt.ledger.inflight
                        or not rt.ledger.accounts_ready
                    ):
                        continue
                    if now - rt.last_align < align_cooldown:
                        continue
                    ka, kb = rt.spec.book_a(), rt.spec.book_b()
                    pos_a_raw, _ = _acct_pos(acct.get(ka), now, stale_sec)
                    pos_b_raw, _ = _acct_pos(acct.get(kb), now, stale_sec)
                    if pos_a_raw is None or pos_b_raw is None:
                        continue
                    _pa = Decimal(str(pos_a_raw))
                    _pb = Decimal(str(pos_b_raw))
                    _target = -_pb
                    _tol = max(
                        Decimal(str(rt.ledger.qty_per_layer)) * Decimal("0.05"),
                        Decimal("1e-8"),
                    )
                    if abs(_pa - _target) <= _tol:
                        continue
                    if rt.hedge.qty_per_layer <= 0:
                        rt.hedge.qty_per_layer = rt.ledger.qty_per_layer
                    _ok, _msg, _fields = rt.hedge.align_a_only(_target)
                    rt.last_align = now
                    last_align_any = now
                    rt.paper.record(
                        action="敞口补仓",
                        delta=1 if (_pa - _target) < 0 else -1,
                        lots_before=rt.ledger.lots,
                        lots_after=rt.ledger.lots,
                        qty=rt.ledger.qty_per_layer,
                        note=_msg,
                        **_fields,
                    )
                    rt.last_layer = rt.paper.last
                    runlog.line(rt.paper.last, pair=rt.spec.name)
                    break

            _clear_tty()
            ticks: List[tuple] = []
            pending: List[tuple] = []
            for rt in runtimes:
                tick, quotes_ok, qa, qb = _sync_pair_tick(
                    vs_cfg=vs_cfg,
                    venues=rt.venues,
                    quotes=snap,
                    windows=rt.windows,
                    grid=rt.grid,
                    ledger=rt.ledger,
                    key_a=rt.spec.book_a(),
                    key_b=rt.spec.book_b(),
                )
                rt.grid.lots = rt.ledger.lots
                ticks.append((rt, tick, quotes_ok, qa, qb))
                if _pair_busy(rt):
                    continue
                if now - rt.last_fail_ts < 3.0:
                    continue
                want = _order_delta(
                    tick, rt.ledger, quotes_ok=quotes_ok, hedge_busy=False
                )
                if want:
                    pending.append((rt, tick, want))
            if multi:
                text = _render_multi_board(
                    vs_cfg=vs_cfg,
                    venues=venues,
                    runtimes=runtimes,
                    quotes=snap,
                    accounts=acct,
                    live=live,
                    ticks=ticks,
                )
            else:
                rt0 = runtimes[0]
                text, _, _ = _render(
                    vs_cfg=vs_cfg,
                    venues=rt0.venues,
                    quotes=snap,
                    windows=rt0.windows,
                    grid=rt0.grid,
                    ledger=rt0.ledger,
                    accounts=acct,
                    last_layer=rt0.last_layer,
                    hedge_busy=_pair_busy(rt0),
                    live=live,
                    pnl=rt0.combined,
                    paper=rt0.paper,
                    key_a=rt0.spec.book_a(),
                    key_b=rt0.spec.book_b(),
                    pair_name=rt0.spec.name,
                    observe=False,
                )
            print(text, flush=True)
            if not stop.is_set():
                for rt, tick, delta in pending:
                    ka, kb = rt.spec.book_a(), rt.spec.book_b()
                    qa = snap.get(ka)
                    qb = snap.get(kb)
                    px_a = px_b = None
                    if qa is not None and qb is not None:
                        px_a = float(qa.ask if delta > 0 else qa.bid)
                        if b_maker:
                            px_b = float(qb.ask if delta > 0 else qb.bid)
                        else:
                            px_b = float(qb.bid if delta > 0 else qb.ask)
                    lots_before = rt.ledger.lots
                    if rt.ledger.is_reduce(delta):
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
                        qty=rt.ledger.qty_per_layer,
                        px_a=px_a,
                        px_b=px_b,
                    )
                    if multi:
                        extra = str(log_kw.get("note") or "").strip()
                        log_kw["note"] = f"{rt.spec.name} {extra}".strip()
                    if live and rt.hedge is not None:
                        rt.pending_log = log_kw
                        reduce_only = rt.ledger.is_reduce(delta)
                        rest_cb = None
                        if b_maker:
                            rest_cb = lambda d=delta, n=lots_before, rt=rt: _maker_rest_ok(
                                book,
                                rt.venues,
                                rt.grid,
                                d,
                                n,
                                rt.spec.book_a(),
                                rt.spec.book_b(),
                            )
                        runlog.line(
                            f"{action} 开始 delta={delta:+d} lots={lots_before} "
                            f"qty={rt.ledger.qty_per_layer} reduce={reduce_only}",
                            pair=rt.spec.name,
                        )
                        rt.order_task = asyncio.create_task(
                            asyncio.to_thread(
                                _execute_layer,
                                rt.hedge,
                                rt.ledger,
                                delta,
                                reduce_only,
                                rest_cb,
                            )
                        )
                    elif rt.sim is not None and px_a is not None and px_b is not None:
                        if rt.sim.submit(rt.ledger, delta, px_a, px_b, now=time.time()):
                            rt.sim.poll(rt.ledger, now=time.time())
                            rt.paper.record(**log_kw, lots_after=rt.ledger.lots)
                            rt.last_layer = rt.paper.last
                            runlog.line(rt.paper.last, pair=rt.spec.name)
            now = time.time()
            if persist_on:
                for rt in runtimes:
                    if now - rt.last_save < save_interval:
                        continue
                    try:
                        save_windows(
                            rt.store_path,
                            rt.identity,
                            rt.windows,
                            grid=rt.grid,
                            pnl=rt.combined,
                        )
                        rt.last_save = now
                    except OSError:
                        rt.last_save = now
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        stop.set()
    finally:
        if sys.stdout.isatty():
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
        with contextlib.suppress(Exception):
            sys.stderr.write("正在撤单并退出...\n")
            sys.stderr.flush()
        try:
            await _stop_executors(runtimes, adapter_a, adapter_b, runlog, live)
        except Exception as exc:
            with contextlib.suppress(Exception):
                runlog.line(f"退出清理失败 {exc}")
        for adapter in (adapter_a, adapter_b):
            if adapter is None:
                continue
            closer = getattr(adapter, "disconnect", None) or getattr(adapter, "close", None)
            if callable(closer):
                with contextlib.suppress(Exception):
                    closer()
        if persist_on:
            for rt in runtimes:
                with contextlib.suppress(OSError):
                    save_windows(
                        rt.store_path,
                        rt.identity,
                        rt.windows,
                        grid=rt.grid,
                        pnl=rt.combined,
                    )
        runlog.close()


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
        if not venues[slot].get("exchange"):
            raise SystemExit(f"venues.{slot} 需要 exchange")
        venues[slot] = _merge_venue_keys(venues[slot])
        venues[slot].setdefault("stale_ms", stale_ms)
        venues[slot].setdefault("rest_interval_sec", rest_interval)
        venues[slot].setdefault("account_rest_sec", account_rest)
        venues[slot].setdefault("account_stale_sec", account_stale)
    specs = _load_pair_specs(vs_cfg, venues)
    venues["a"]["symbols"] = symbols_for_slot(specs, "a")
    venues["b"]["symbols"] = symbols_for_slot(specs, "b")
    venues["a"]["symbol"] = venues["a"]["symbols"][0]
    venues["b"]["symbol"] = venues["b"]["symbols"][0]
    if not venues["a"]["symbols"] or not venues["b"]["symbols"]:
        raise SystemExit("匹配表没有可订阅品种")

    book = QuoteBook()
    accounts = AccountBook()
    accounts.set_peers(peer_map(specs))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    sig_hits = {"n": 0}
    tasks: List[asyncio.Task] = []

    def _request_stop() -> None:
        sig_hits["n"] += 1
        stop.set()
        if sig_hits["n"] >= 2:
            for task in tasks:
                if not task.done():
                    task.cancel()

    tasks.extend(
        [
            asyncio.create_task(
                run_feed("a", venues["a"], book, stop, accounts), name="feed-a"
            ),
            asyncio.create_task(
                run_feed("b", venues["b"], book, stop, accounts), name="feed-b"
            ),
            asyncio.create_task(
                _print_loop(vs_cfg, venues, book, accounts, stop, specs), name="print"
            ),
        ]
    )
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, _request_stop)
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        stop.set()
    finally:
        stop.set()
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=20.0,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            for task in tasks:
                if not task.done():
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
