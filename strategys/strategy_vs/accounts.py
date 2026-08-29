"""账户净值 / 可用 / 仓位。优先私有 WSS，REST 仅作慢速兜底。"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

_POS_EPS = 1e-12


class ThreadWake:
    """给同步执行线程用：WSS 回调 ping，执行循环 wait。先到的推送不会被 clear 丢掉。"""

    def __init__(self) -> None:
        self._ev = threading.Event()

    def ping(self) -> None:
        self._ev.set()

    def wait(self, timeout: float) -> bool:
        ok = self._ev.wait(max(0.0, float(timeout)))
        self._ev.clear()
        return ok


@dataclass
class AccountSnap:
    venue: str
    equity: Optional[float] = None
    available: Optional[float] = None
    pos_qty: Optional[float] = None
    pos_symbol: str = ""
    source: str = ""
    ts: float = 0.0
    balance_ts: float = 0.0
    error: str = ""
    force: bool = False


class AccountBook:
    """仓位：非 0 立刻采用。裸 0 默认沿用上次非 0（Hype REST 会闪空仓）。

    A 所 WSS 报 0 且 B 所非 0：丢弃本包（Lighter update 常只带变过的市场）。
    其余：WSS 报 0 认该所；REST 报 0 要对腿 raw 也是 0 才认。force=True 时按 REST 实数写入。
    """

    def __init__(self) -> None:
        self._data: Dict[str, AccountSnap] = {}
        self._lock = asyncio.Lock()
        self._tlock = threading.Lock()
        self._sticky: Dict[str, float] = {}
        self._flat_ok: set[str] = set()
        self._last_rest: Dict[str, float] = {}
        self._last_raw: Dict[str, float] = {}
        self._peers: Dict[str, str] = {}
        self._fill_seen: set[str] = set()
        self._fill_tape: list = []
        self._async_tick = asyncio.Event()
        self._thread_wake: Optional[ThreadWake] = None

    def set_thread_wake(self, wake: Optional[ThreadWake]) -> None:
        self._thread_wake = wake

    def _notify(self) -> None:
        self._async_tick.set()
        wake = self._thread_wake
        if wake is not None:
            wake.ping()

    async def wait_update(self, timeout: float) -> bool:
        """等下一次持仓/成交推送；超时返回 False。语义同 QuoteBook.wait_update。"""
        self._async_tick.clear()
        try:
            await asyncio.wait_for(self._async_tick.wait(), max(0.0, float(timeout)))
        except asyncio.TimeoutError:
            return False
        return True

    def set_peers(self, mapping: Dict[str, str]) -> None:
        """品种级对锁：a:QQQ ↔ b:QQQ-USD.P，避免多品种共用 a/b 把仓位盖掉。"""
        peers: Dict[str, str] = {}
        for left, right in mapping.items():
            if not left or not right:
                continue
            peers[str(left)] = str(right)
            peers[str(right)] = str(left)
        with self._tlock:
            self._peers = peers

    def _peer_slot(self, venue: str) -> Optional[str]:
        mapped = self._peers.get(venue)
        if mapped:
            return mapped
        if venue == "a":
            return "b"
        if venue == "b":
            return "a"
        if ":" in venue:
            slot, _, rest = venue.partition(":")
            other = "b" if slot == "a" else "a" if slot == "b" else ""
            if other:
                return f"{other}:{rest}"
        return None

    def _peer_pos(self, venue: str) -> Optional[float]:
        slot = self._peer_slot(venue)
        if slot is None:
            return None
        snap = self._data.get(slot)
        if snap is None or snap.pos_qty is None:
            return None
        return float(snap.pos_qty)

    def _is_a_slot(self, venue: str) -> bool:
        if venue == "a":
            return True
        return str(venue).startswith("a:")

    def _peer_nonzero(self, venue: str) -> bool:
        """对腿交易所 raw 是否非 0。没有 raw 时才看显示仓。"""
        slot = self._peer_slot(venue)
        if slot is None:
            return False
        if slot in self._last_raw:
            return abs(float(self._last_raw[slot])) > _POS_EPS
        snap = self._data.get(slot)
        if snap is not None and snap.pos_qty is not None:
            return abs(float(snap.pos_qty)) > _POS_EPS
        return False

    def _resolve_pos(
        self,
        venue: str,
        raw: float,
        *,
        source: str,
        prev: Optional[AccountSnap],
        force: bool = False,
    ) -> float:
        sticky = self._sticky.get(venue)
        if sticky is None and prev is not None and prev.pos_qty is not None:
            if abs(float(prev.pos_qty)) > _POS_EPS:
                sticky = float(prev.pos_qty)
                self._sticky[venue] = sticky
        src = (source or "").lower()
        if force:
            self._last_raw[venue] = float(raw)
            if src == "rest":
                self._last_rest[venue] = float(raw)
            if abs(raw) > _POS_EPS:
                self._sticky[venue] = float(raw)
                self._flat_ok.discard(venue)
            else:
                self._sticky[venue] = 0.0
                self._flat_ok.add(venue)
            return float(raw)
        if abs(raw) > _POS_EPS:
            self._last_raw[venue] = float(raw)
            if src == "rest":
                self._last_rest[venue] = float(raw)
            self._sticky[venue] = float(raw)
            self._flat_ok.discard(venue)
            return float(raw)
        # raw ≈ 0：A 所 WSS 报 0 且 B 非 0 → 当增量漏品种，丢弃本包
        if src == "wss" and self._is_a_slot(venue) and self._peer_nonzero(venue):
            if sticky is not None and abs(sticky) > _POS_EPS:
                return sticky
            if prev is not None and prev.pos_qty is not None:
                return float(prev.pos_qty)
            return 0.0
        self._last_raw[venue] = 0.0
        if src == "rest":
            self._last_rest[venue] = 0.0
        if venue in self._flat_ok:
            self._sticky[venue] = 0.0
            return 0.0
        if sticky is None or abs(sticky) <= _POS_EPS:
            self._sticky[venue] = 0.0
            return 0.0
        peer_slot = self._peer_slot(venue)
        peer_raw = self._last_raw.get(peer_slot) if peer_slot else None
        peer_also_flat = peer_raw is not None and abs(peer_raw) <= _POS_EPS
        # WSS 仓位频道报空：该所认 0。REST 空仓仍要等对腿 raw 也空（Hype 会闪 0）。
        accept = src == "wss" or (src == "rest" and peer_also_flat)
        if not accept:
            return sticky
        self._sticky[venue] = 0.0
        self._flat_ok.add(venue)
        if peer_slot and peer_also_flat:
            self._flat_ok.add(peer_slot)
            self._sticky[peer_slot] = 0.0
            other = self._data.get(peer_slot)
            if other is not None:
                other.pos_qty = 0.0
                other.ts = time.time()
        return 0.0

    def _commit(self, snap: AccountSnap) -> bool:
        incoming_balance = snap.equity is not None or snap.available is not None
        prev = self._data.get(snap.venue)
        raw_pos = snap.pos_qty
        if snap.error:
            if prev is not None:
                if snap.equity is None:
                    snap.equity = prev.equity
                if snap.available is None:
                    snap.available = prev.available
                snap.pos_qty = prev.pos_qty
                if not snap.pos_symbol:
                    snap.pos_symbol = prev.pos_symbol
            snap.balance_ts = (
                float(prev.balance_ts or 0.0) if prev is not None else 0.0
            )
            self._data[snap.venue] = snap
            return False
        if prev is not None:
            if snap.equity is None:
                snap.equity = prev.equity
            if snap.available is None:
                snap.available = prev.available
            if not snap.source:
                snap.source = prev.source
            if not snap.pos_symbol:
                snap.pos_symbol = prev.pos_symbol
        if raw_pos is None:
            snap.pos_qty = prev.pos_qty if prev is not None else None
        else:
            snap.pos_qty = self._resolve_pos(
                snap.venue,
                float(raw_pos),
                source=snap.source,
                prev=prev,
                force=bool(getattr(snap, "force", False)),
            )
        if incoming_balance:
            snap.balance_ts = float(snap.ts or time.time())
        elif prev is not None:
            snap.balance_ts = float(prev.balance_ts or 0.0)
        self._data[snap.venue] = snap
        return raw_pos is not None

    async def patch(self, snap: AccountSnap) -> None:
        async with self._lock:
            with self._tlock:
                notify = self._commit(snap)
        if notify:
            self._notify()

    def apply_fill(self, venue: str, signed_delta: float) -> Optional[float]:
        """本地乐观成交：对冲下单成功后立刻改粘性仓，避免 WSS 仍是 0 时连打。"""
        delta = float(signed_delta)
        if abs(delta) <= _POS_EPS:
            return None
        with self._tlock:
            prev = self._data.get(venue)
            cur = 0.0
            if prev is not None and prev.pos_qty is not None:
                cur = float(prev.pos_qty)
            elif venue in self._sticky:
                cur = float(self._sticky[venue])
            new = cur + delta
            if abs(new) <= _POS_EPS:
                new = 0.0
                self._flat_ok.add(venue)
                self._sticky[venue] = 0.0
            else:
                self._flat_ok.discard(venue)
                self._sticky[venue] = new
            now = time.time()
            if prev is None:
                self._data[venue] = AccountSnap(
                    venue=venue,
                    pos_qty=new,
                    source="local",
                    ts=now,
                )
            else:
                prev.pos_qty = new
                prev.source = "local"
                prev.ts = now
                prev.error = ""
        self._notify()
        return new

    def ingest_fill(
        self,
        venue: str,
        signed_qty: float,
        fill_id: str,
        ts: Optional[float] = None,
    ) -> bool:
        """记下一条成交。按 fill_id 去重。不改仓位快照，避免和持仓推送叠算。"""
        delta = float(signed_qty)
        fid = str(fill_id or "").strip()
        if abs(delta) <= _POS_EPS or not fid:
            return False
        now = time.time() if ts is None else float(ts)
        with self._tlock:
            if fid in self._fill_seen:
                return False
            self._fill_seen.add(fid)
            self._fill_tape.append((str(venue), delta, fid, now))
            if len(self._fill_tape) > 4000:
                cutoff = now - 3600.0
                self._fill_tape = [e for e in self._fill_tape if e[3] >= cutoff]
                self._fill_seen = {e[2] for e in self._fill_tape}
        self._notify()
        return True

    def signed_fills_since(self, venue: str, since_ts: float) -> float:
        """自 since_ts 起该品种成交的带符号数量合计（本机收到时间）。"""
        key = str(venue)
        start = float(since_ts)
        with self._tlock:
            return float(sum(d for v, d, _fid, ts in self._fill_tape if v == key and ts >= start))

    async def snapshot(self) -> Dict[str, AccountSnap]:
        async with self._lock:
            with self._tlock:
                return dict(self._data)

    def latest(self) -> Dict[str, AccountSnap]:
        """供同步执行器读仓；含粘性仓（未确认的 0 不会盖掉上次非 0）。"""
        with self._tlock:
            return dict(self._data)


def _add_opt(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    return float(left) + float(right)


class CombinedPnl:
    """两所净值相加，相对首次到齐的基线算合计盈亏。"""

    def __init__(self) -> None:
        self.eq_a0: Optional[float] = None
        self.eq_b0: Optional[float] = None
        self.ts0: float = 0.0
        self.dirty = False

    @property
    def ready(self) -> bool:
        return self.eq_a0 is not None and self.eq_b0 is not None

    def load(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        try:
            eq_a0 = payload.get("eq_a0")
            eq_b0 = payload.get("eq_b0")
            if eq_a0 is None or eq_b0 is None:
                return False
            self.eq_a0 = float(eq_a0)
            self.eq_b0 = float(eq_b0)
            self.ts0 = float(payload.get("ts0") or 0.0)
            self.dirty = False
            return True
        except (TypeError, ValueError):
            return False

    def dump(self) -> Dict[str, Any]:
        return {"eq_a0": self.eq_a0, "eq_b0": self.eq_b0, "ts0": self.ts0}

    def capture(
        self,
        eq_a: Optional[float],
        eq_b: Optional[float],
        now: Optional[float] = None,
    ) -> None:
        if self.ready or eq_a is None or eq_b is None:
            return
        self.eq_a0 = float(eq_a)
        self.eq_b0 = float(eq_b)
        self.ts0 = time.time() if now is None else float(now)
        self.dirty = True

    def snapshot(
        self,
        eq_a: Optional[float],
        eq_b: Optional[float],
        av_a: Optional[float] = None,
        av_b: Optional[float] = None,
        pos_a: Optional[float] = None,
        pos_b: Optional[float] = None,
    ) -> Dict[str, Optional[float]]:
        self.capture(eq_a, eq_b)
        equity = _add_opt(eq_a, eq_b)
        base = _add_opt(self.eq_a0, self.eq_b0)
        pnl = None
        pnl_a = None
        pnl_b = None
        if base is not None and equity is not None:
            pnl = equity - base
        if self.eq_a0 is not None and eq_a is not None:
            pnl_a = float(eq_a) - self.eq_a0
        if self.eq_b0 is not None and eq_b is not None:
            pnl_b = float(eq_b) - self.eq_b0
        return {
            "equity": equity,
            "available": _add_opt(av_a, av_b),
            "net_pos": _add_opt(pos_a, pos_b),
            "base": base,
            "pnl": pnl,
            "pnl_a": pnl_a,
            "pnl_b": pnl_b,
        }


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_float(payload: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key in payload:
            parsed = _to_float(payload.get(key))
            if parsed is not None:
                return parsed
    return None


def _symbol_match(have: str, want: str) -> bool:
    a = "".join(ch for ch in have.upper() if ch.isalnum())
    b = "".join(ch for ch in want.upper() if ch.isalnum())
    if not a or not b:
        return False
    if a == b:
        return True
    return a.startswith(b) or b.startswith(a)


def _pick_money(*layers: Dict[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    found: Optional[float] = None
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        val = _pick_float(layer, *keys)
        if val is None:
            continue
        if found is None:
            found = val
        if abs(val) > 1e-12:
            return val
    return found


def parse_lighter_user_stats(payload: Any) -> Dict[str, Optional[float]]:
    """user_stats：净值用 portfolio_value，可用用 available_balance。"""
    data = payload if isinstance(payload, dict) else {}
    stats = data.get("stats") or data.get("user_stats") or data
    if not isinstance(stats, dict):
        stats = {}
    total = stats.get("total_stats") if isinstance(stats.get("total_stats"), dict) else {}
    cross = stats.get("cross_stats") if isinstance(stats.get("cross_stats"), dict) else {}
    return {
        "equity": _pick_money(
            stats, total, cross, data, keys=("portfolio_value", "total_asset_value", "collateral")
        ),
        "available": _pick_money(
            stats, total, cross, data, keys=("available_balance", "buying_power")
        ),
    }


def parse_lighter_account(payload: Any) -> Dict[str, Optional[float]]:
    data = payload if isinstance(payload, dict) else {}
    account = data.get("account") if isinstance(data.get("account"), dict) else data
    if not isinstance(account, dict):
        account = data
    return {
        "equity": _pick_money(
            account, data, keys=("portfolio_value", "total_asset_value", "collateral")
        ),
        "available": _pick_money(
            account, data, keys=("available_balance", "buying_power")
        ),
    }


def parse_lighter_positions(payload: Any, symbol: str) -> Optional[float]:
    """解析 Lighter account_all 仓位。

    None = 本条不含该品种（空列表/增量），调用方不得写成 0。
    0.0 = 推送里明确匹配到该品种且仓为 0。
    """
    data = payload if isinstance(payload, dict) else {}
    positions = data.get("positions")
    if positions is None and isinstance(data.get("account"), dict):
        positions = data["account"].get("positions")
    rows: list = []
    if isinstance(positions, dict):
        rows = list(positions.values())
    elif isinstance(positions, list):
        rows = positions
    elif positions is None:
        return None
    if not rows:
        return None
    best: Optional[float] = None
    matched = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        have = str(row.get("symbol") or row.get("market") or "")
        if have and not _symbol_match(have, symbol):
            continue
        size = _to_float(row.get("position") or row.get("size") or row.get("qty"))
        if size is None:
            continue
        matched = True
        sign = row.get("sign")
        if sign is not None:
            try:
                signed = abs(size) if int(sign) > 0 else -abs(size)
            except (TypeError, ValueError):
                signed = size
        else:
            signed = size
        best = signed
        if have:
            break
    if matched:
        return best if best is not None else 0.0
    return None


def parse_lighter_positions_map(payload: Any) -> Dict[str, float]:
    """一条 account_all 拆成 {symbol: 仓位}，供多品种共享同一账户推送。"""
    data = payload if isinstance(payload, dict) else {}
    positions = data.get("positions")
    if positions is None and isinstance(data.get("account"), dict):
        positions = data["account"].get("positions")
    rows: list = []
    if isinstance(positions, dict):
        rows = list(positions.values())
    elif isinstance(positions, list):
        rows = positions
    out: Dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        have = str(row.get("symbol") or row.get("market") or "").strip()
        if not have:
            continue
        size = _to_float(row.get("position") or row.get("size") or row.get("qty"))
        if size is None:
            continue
        sign = row.get("sign")
        if sign is not None:
            try:
                signed = abs(size) if int(sign) > 0 else -abs(size)
            except (TypeError, ValueError):
                signed = size
        else:
            signed = size
        out[have] = float(signed)
    return out


def lighter_positions_complete(payload: Any) -> bool:
    """account_all 带非空 positions 时视为全量快照：没出现的品种就是 0。空列表仍不信任。"""
    data = payload if isinstance(payload, dict) else {}
    positions = data.get("positions")
    if positions is None and isinstance(data.get("account"), dict):
        positions = data["account"].get("positions")
    if isinstance(positions, dict):
        return len(positions) > 0
    if isinstance(positions, list):
        return len(positions) > 0
    return False


def parse_ondo_balance(message: Any) -> Dict[str, Optional[float]]:
    data = message.get("data") if isinstance(message, dict) else message
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        data = {}
    equity = _pick_float(data, "marginBalance", "walletBalance")
    available = _pick_float(data, "availableMargin", "withdrawableMargin")
    return {"equity": equity, "available": available}


def parse_ondo_positions(message: Any, symbol: str) -> Optional[float]:
    data = message.get("data") if isinstance(message, dict) else message
    is_list = isinstance(data, list)
    rows = data if is_list else [data] if isinstance(data, dict) else []
    qty = 0.0
    found = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        market = str(row.get("market") or "")
        if market and not _symbol_match(market, symbol):
            continue
        size = _to_float(row.get("netQuantity") or row.get("quantity") or row.get("size"))
        if size is None:
            continue
        direction = str(row.get("direction") or row.get("side") or "").lower()
        if direction in ("neutral",):
            found = True
            continue
        found = True
        if abs(size) < 1e-18:
            continue
        qty += -abs(size) if direction == "short" else abs(size)
    if found:
        return qty
    return 0.0 if is_list else None


def parse_ondo_positions_map(message: Any) -> Dict[str, float]:
    """一条 positions 推送拆成 {market: 仓位}。"""
    data = message.get("data") if isinstance(message, dict) else message
    rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    out: Dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        market = str(row.get("market") or "").strip()
        if not market:
            continue
        size = _to_float(row.get("netQuantity") or row.get("quantity") or row.get("size"))
        if size is None:
            continue
        direction = str(row.get("direction") or row.get("side") or "").lower()
        if direction in ("neutral",):
            out[market] = 0.0
            continue
        signed = -abs(size) if direction == "short" else abs(size)
        if abs(signed) < 1e-18:
            out[market] = 0.0
        else:
            out[market] = float(signed)
    return out


def ondo_positions_complete(message: Any) -> bool:
    """data 为列表且不是单条增量时，视为全量快照（空列表=全平）。"""
    data = message.get("data") if isinstance(message, dict) else message
    return isinstance(data, list) and len(data) != 1


def parse_popdex_account(message: Any) -> Dict[str, Optional[float]]:
    data = message.get("data") if isinstance(message, dict) else message
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        data = {}
    return {
        "equity": _pick_float(data, "accountEquity", "totalCollateral", "equity"),
        "available": _pick_float(data, "availableMargin", "available"),
    }


def parse_popdex_positions_map(message: Any) -> Dict[str, float]:
    """一条 position 推送拆成 {symbol: 仓位}。"""
    data = message.get("data") if isinstance(message, dict) else message
    rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    out: Dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        market = str(row.get("symbol") or row.get("market") or "").strip()
        if not market:
            continue
        size = _to_float(row.get("holdQty") or row.get("quantity") or row.get("size"))
        if size is None:
            continue
        direction = str(row.get("positionSide") or row.get("side") or "").lower()
        signed = -abs(size) if direction in ("short", "sell") else abs(size)
        out[market] = 0.0 if abs(signed) < 1e-18 else float(signed)
    return out


def parse_popdex_fills(message: Any) -> list:
    """WSS topic=fill：拆成 [{symbol, signed, fill_id}, ...]。snapshot 不入（历史单）。"""
    if not isinstance(message, dict):
        return []
    action = str(message.get("action") or "").lower()
    if action == "snapshot":
        return []
    data = message.get("data")
    rows: list = []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        nested = data.get("fills") or data.get("fill")
        if isinstance(nested, list):
            rows = nested
        elif isinstance(nested, dict):
            rows = [nested]
        else:
            rows = [data]
    out: list = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        market = str(row.get("symbol") or row.get("market") or "").strip()
        if not market:
            continue
        qty = _to_float(
            row.get("fillQty")
            or row.get("execQty")
            or row.get("lastFilledQty")
            or row.get("lastFillQty")
            or row.get("qty")
            or row.get("size")
            or row.get("quantity")
        )
        if qty is None or abs(qty) <= 1e-18:
            continue
        side = str(
            row.get("side")
            or row.get("orderSide")
            or row.get("positionSide")
            or ""
        ).lower()
        signed = -abs(qty) if side in ("sell", "short") else abs(qty)
        fid = str(
            row.get("execId")
            or row.get("fillId")
            or row.get("tradeId")
            or row.get("id")
            or ""
        ).strip()
        if not fid:
            oid = str(row.get("orderId") or row.get("order_id") or "")
            fid = f"{market}:{oid}:{signed}:{row.get('execTime') or row.get('ts') or i}"
        out.append({"symbol": market, "signed": float(signed), "fill_id": fid})
    return out


def parse_hype_fills(message: Any) -> list:
    """userFills 拆成 [{symbol, signed, fill_id}, ...]。snapshot 是历史单，不入带。"""
    if hype_fills_snapshot(message):
        return []
    data = message.get("data") if isinstance(message, dict) else message
    rows: list = []
    if isinstance(data, dict):
        raw = data.get("fills")
        if isinstance(raw, list):
            rows = raw
        elif isinstance(data.get("fill"), dict):
            rows = [data["fill"]]
    elif isinstance(data, list):
        rows = data
    out: list = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        coin = str(row.get("coin") or row.get("symbol") or "").strip()
        if not coin:
            continue
        qty = _to_float(row.get("sz") or row.get("size") or row.get("qty"))
        if qty is None or abs(qty) <= 1e-18:
            continue
        side = str(row.get("side") or "").strip().upper()
        if side in ("B", "BUY"):
            signed = abs(qty)
        elif side in ("A", "SELL"):
            signed = -abs(qty)
        else:
            continue
        fid = str(
            row.get("tid") or row.get("hash") or row.get("oid") or row.get("cloid") or ""
        ).strip()
        if not fid:
            fid = f"{coin}:{signed}:{row.get('time') or i}"
        out.append({"symbol": coin, "signed": float(signed), "fill_id": str(fid)})
    return out


def parse_hype_fill_coins(message: Any) -> list:
    """userFills 里出现过的 coin。用来决定要不要立刻 REST 刷新仓位。"""
    data = message.get("data") if isinstance(message, dict) else message
    fills: list = []
    if isinstance(data, dict):
        raw = data.get("fills")
        if isinstance(raw, list):
            fills = raw
        elif isinstance(data.get("fill"), dict):
            fills = [data["fill"]]
    elif isinstance(data, list):
        fills = data
    out: list = []
    seen = set()
    for row in fills:
        if not isinstance(row, dict):
            continue
        coin = str(row.get("coin") or row.get("symbol") or "").strip()
        if not coin or coin in seen:
            continue
        seen.add(coin)
        out.append(coin)
    return out


def hype_fills_snapshot(message: Any) -> bool:
    data = message.get("data") if isinstance(message, dict) else message
    if not isinstance(data, dict):
        return False
    return bool(data.get("isSnapshot") or data.get("is_snapshot"))


def popdex_positions_complete(message: Any) -> bool:
    """snapshot 且 data 是列表才算全量，缺的品种按空仓补 0。"""
    if not isinstance(message, dict):
        return False
    if not isinstance(message.get("data"), list):
        return False
    return str(message.get("action") or "").lower() == "snapshot"


def from_adapter_balance(balance: Any, positions: Any, symbol: str) -> Dict[str, Any]:
    equity = available = None
    if balance is not None:
        equity = _to_float(
            getattr(balance, "equity", None) or getattr(balance, "total_balance", None)
        )
        available = _to_float(getattr(balance, "available_balance", None))
    pos_qty = 0.0
    found = False
    for pos in positions or []:
        have = str(getattr(pos, "symbol", "") or "")
        if have and not _symbol_match(have, symbol):
            continue
        size = _to_float(getattr(pos, "size", None))
        if size is None:
            continue
        side = str(getattr(pos, "side", "") or "").lower()
        found = True
        if abs(size) < 1e-18:
            continue
        pos_qty += -abs(size) if side == "short" else abs(size)
    return {
        "equity": equity,
        "available": available,
        "pos_qty": pos_qty if found else 0.0,
        "pos_found": found,
    }
