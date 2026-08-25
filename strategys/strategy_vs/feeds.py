"""公共 WSS 行情源：统一输出 Quote。运行时只挂配置里的两个所。"""
from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional

from adapters.factory import create_adapter
from adapters.ondo_adapter import normalize_ondo_symbol
from adapters.popdex_adapter import normalize_popdex_symbol

from accounts import (  # noqa: E402
    AccountBook,
    AccountSnap,
    from_adapter_balance,
    parse_lighter_positions,
    parse_lighter_positions_map,
    parse_lighter_user_stats,
    parse_ondo_balance,
    parse_ondo_positions,
    parse_ondo_positions_map,
    parse_popdex_account,
    parse_popdex_positions,
)

DEFAULT_TAKER_FEE = {
    "lighter": 0.0,
    "rh_lighter": 0.0,
    "rhlighter": 0.0,
    "lighter_rh": 0.0,
    "robinhood_lighter": 0.0,
    "ondo": 0.00025,
    "ondoperp": 0.00025,
    "ondoperps": 0.00025,
    "popdex": 0.0005,
}

DEFAULT_MAKER_FEE = {
    "lighter": 0.0,
    "rh_lighter": 0.0,
    "rhlighter": 0.0,
    "lighter_rh": 0.0,
    "robinhood_lighter": 0.0,
    "ondo": 0.0001,
    "ondoperp": 0.0001,
    "ondoperps": 0.0001,
    "popdex": 0.0002,
}

ACCOUNT_REST_SEC = 30.0
ACCOUNT_STALE_SEC = 15.0

LIGHTER_EXCHANGES = {
    "lighter",
    "rh_lighter",
    "rhlighter",
    "lighter_rh",
    "robinhood_lighter",
}
ONDO_EXCHANGES = {"ondo", "ondoperp", "ondoperps"}
POPDEX_EXCHANGES = {"popdex"}


@dataclass
class Quote:
    venue: str
    exchange: str
    symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_sz: Optional[float] = None
    ask_sz: Optional[float] = None
    ts: float = 0.0
    error: str = ""
    source: str = ""


class QuoteBook:
    def __init__(self) -> None:
        self._data: Dict[str, Quote] = {}
        self._lock = asyncio.Lock()

    async def update(self, quote: Quote) -> None:
        async with self._lock:
            prev = self._data.get(quote.venue)
            if prev is not None and not quote.error:
                if quote.bid is None:
                    quote.bid = prev.bid
                    if quote.bid_sz is None:
                        quote.bid_sz = prev.bid_sz
                if quote.ask is None:
                    quote.ask = prev.ask
                    if quote.ask_sz is None:
                        quote.ask_sz = prev.ask_sz
            self._data[quote.venue] = quote

    async def touch(self, venue: str, ts: float, source: str = "wss") -> None:
        """WSS 有推送但盘口字段没变时，只刷新存活时间。"""
        async with self._lock:
            prev = self._data.get(venue)
            if prev is None or prev.bid is None or prev.ask is None:
                return
            self._data[venue] = replace(prev, ts=ts, error="", source=source)

    async def snapshot(self) -> Dict[str, Quote]:
        async with self._lock:
            return dict(self._data)

    def latest(self) -> Dict[str, Quote]:
        """无锁快照，供同步执行器读 WSS 缓存。"""
        return dict(self._data)


def feed_symbols(venue_cfg: Dict[str, Any]) -> list:
    raw = venue_cfg.get("symbols")
    if isinstance(raw, (list, tuple)) and raw:
        return [str(s).strip() for s in raw if str(s).strip()]
    one = str(venue_cfg.get("symbol") or "").strip()
    return [one] if one else []


def slot_book_key(slot: str, symbol: str) -> str:
    return f"{slot}:{symbol}"


def _norm_sym(text: str) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def _same_symbol(have: str, want: str) -> bool:
    a, b = _norm_sym(have), _norm_sym(want)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def _pick_wanted_symbol(have: str, wanted: list) -> Optional[str]:
    for want in wanted:
        if _same_symbol(have, want):
            return want
    return None


def taker_fee_of(venue_cfg: Dict[str, Any]) -> float:
    exchange = str(venue_cfg.get("exchange") or "").strip().lower()
    if venue_cfg.get("taker_fee") is not None and venue_cfg.get("taker_fee") != "":
        return float(venue_cfg["taker_fee"])
    return float(DEFAULT_TAKER_FEE.get(exchange, 0.0))


def maker_fee_of(venue_cfg: Dict[str, Any]) -> float:
    exchange = str(venue_cfg.get("exchange") or "").strip().lower()
    if venue_cfg.get("maker_fee") is not None and venue_cfg.get("maker_fee") != "":
        return float(venue_cfg["maker_fee"])
    return float(DEFAULT_MAKER_FEE.get(exchange, 0.0))


def venue_role(venue_cfg: Dict[str, Any]) -> str:
    role = str(venue_cfg.get("role") or "taker").strip().lower()
    if role in ("maker", "make", "alo", "postonly", "post_only"):
        return "maker"
    return "taker"


def exec_fee_of(venue_cfg: Dict[str, Any]) -> float:
    """B 的执行费率：role=maker 用 maker_fee，否则 taker_fee。"""
    if venue_role(venue_cfg) == "maker":
        return maker_fee_of(venue_cfg)
    return taker_fee_of(venue_cfg)


def _adapter_config(venue_cfg: Dict[str, Any]) -> Dict[str, Any]:
    skip = {
        "taker_fee",
        "maker_fee",
        "role",
        "exchange",
        "name",
        "stale_ms",
        "rest_interval_sec",
        "account_rest_sec",
        "account_stale_sec",
        "symbols",
    }
    cfg = {k: v for k, v in venue_cfg.items() if k not in skip}
    cfg["exchange_name"] = str(venue_cfg["exchange"]).strip().lower()
    return cfg


def _level_px_sz(level: Any) -> tuple[Optional[float], Optional[float]]:
    if level is None:
        return None, None
    if isinstance(level, dict):
        px = level.get("price")
        sz = level.get("size")
        if sz is None:
            sz = level.get("remaining_base_amount") or level.get("qty") or level.get("amount")
        return _to_float(px), _to_float(sz)
    if isinstance(level, (list, tuple)) and len(level) >= 1:
        px = _to_float(level[0])
        sz = _to_float(level[1]) if len(level) > 1 else None
        return px, sz
    return _to_float(level), None


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bbo_from_book(
    bids: Any, asks: Any
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    live_bids = []
    for item in bids or []:
        px, sz = _level_px_sz(item)
        if px is None:
            continue
        if sz is not None and sz <= 0:
            continue
        live_bids.append((px, sz))
    live_asks = []
    for item in asks or []:
        px, sz = _level_px_sz(item)
        if px is None:
            continue
        if sz is not None and sz <= 0:
            continue
        live_asks.append((px, sz))
    bid_px = bid_sz = ask_px = ask_sz = None
    if live_bids:
        bid_px, bid_sz = max(live_bids, key=lambda x: x[0])
    if live_asks:
        ask_px, ask_sz = min(live_asks, key=lambda x: x[0])
    return bid_px, ask_px, bid_sz, ask_sz


async def _backoff(stop: asyncio.Event, delay: float) -> float:
    try:
        await asyncio.wait_for(stop.wait(), timeout=delay)
    except asyncio.TimeoutError:
        pass
    return min(delay * 2.0, 15.0)


async def run_feed(
    venue: str,
    venue_cfg: Dict[str, Any],
    book: QuoteBook,
    stop: asyncio.Event,
    accounts: Optional[AccountBook] = None,
) -> None:
    exchange = str(venue_cfg.get("exchange") or "").strip().lower()
    if exchange in LIGHTER_EXCHANGES:
        await _run_lighter(venue, venue_cfg, book, stop, accounts)
        return
    if exchange in ONDO_EXCHANGES:
        await _run_ondo(venue, venue_cfg, book, stop, accounts)
        return
    if exchange in POPDEX_EXCHANGES:
        await _run_popdex(venue, venue_cfg, book, stop, accounts)
        return
    raise ValueError(
        f"尚未实现 {exchange} 的 WSS feed。当前支持: "
        + ", ".join(sorted(LIGHTER_EXCHANGES | ONDO_EXCHANGES | POPDEX_EXCHANGES))
    )


def _ondo_authed(adapter: Any) -> bool:
    auth = getattr(adapter, "auth", None)
    if auth is None:
        return False
    return bool(getattr(auth, "has_api_key", False) or getattr(auth, "has_jwt", False))


async def _push_account_rest(
    *,
    venue: str,
    symbols: list,
    adapter: Any,
    accounts: AccountBook,
) -> None:
    """账户 REST：余额一次、持仓一次，再按品种拆到 venue:symbol。"""
    wanted = [str(s).strip() for s in symbols if str(s).strip()]
    if not wanted:
        return
    balance = await asyncio.wait_for(
        asyncio.to_thread(adapter.get_balance),
        timeout=8.0,
    )
    positions = await asyncio.wait_for(
        asyncio.to_thread(adapter.get_positions, None),
        timeout=8.0,
    )
    parsed0 = from_adapter_balance(balance, positions, wanted[0])
    now = time.time()
    await accounts.patch(
        AccountSnap(
            venue=venue,
            equity=parsed0["equity"],
            available=parsed0["available"],
            source="rest",
            ts=now,
        )
    )
    for symbol in wanted:
        parsed = from_adapter_balance(balance, positions, symbol)
        await accounts.patch(
            AccountSnap(
                venue=slot_book_key(venue, symbol),
                pos_qty=parsed["pos_qty"],
                pos_symbol=symbol,
                source="rest",
                ts=now,
            )
        )


async def _account_rest_loop(
    *,
    venue: str,
    venue_cfg: Dict[str, Any],
    symbol: str,
    adapter: Any,
    accounts: Optional[AccountBook],
    stop: asyncio.Event,
    has_auth: bool,
) -> None:
    if accounts is None:
        return
    rest_sec = float(venue_cfg.get("account_rest_sec", ACCOUNT_REST_SEC))
    stale_sec = float(venue_cfg.get("account_stale_sec", ACCOUNT_STALE_SEC))
    try:
        await asyncio.wait_for(stop.wait(), timeout=3.0)
        if stop.is_set():
            return
    except asyncio.TimeoutError:
        pass
    first = True
    while not stop.is_set():
        if not first:
            try:
                await asyncio.wait_for(stop.wait(), timeout=rest_sec)
                if stop.is_set():
                    return
            except asyncio.TimeoutError:
                pass
        first = False
        snap = (await accounts.snapshot()).get(venue)
        bal_ts = float(getattr(snap, "balance_ts", 0.0) or 0.0) if snap else 0.0
        if (
            snap
            and not snap.error
            and bal_ts
            and (time.time() - bal_ts) < stale_sec
            and (snap.source or "").lower() == "wss"
        ):
            continue
        if not has_auth:
            await accounts.patch(
                AccountSnap(
                    venue=venue,
                    error="无密钥",
                    ts=time.time(),
                    source="",
                )
            )
            continue
        try:
            await _push_account_rest(
                venue=venue,
                symbols=feed_symbols(venue_cfg) or [symbol],
                adapter=adapter,
                accounts=accounts,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await accounts.patch(
                AccountSnap(
                    venue=venue,
                    error=str(exc)[:80],
                    ts=time.time(),
                    source="rest",
                )
            )


async def _run_lighter(
    venue: str,
    venue_cfg: Dict[str, Any],
    book: QuoteBook,
    stop: asyncio.Event,
    accounts: Optional[AccountBook] = None,
) -> None:
    adapter = create_adapter(_adapter_config(venue_cfg))
    symbols = feed_symbols(venue_cfg)
    symbol = symbols[0] if symbols else str(venue_cfg.get("symbol") or "")
    exchange = str(venue_cfg.get("exchange") or "")
    loop = asyncio.get_running_loop()
    delay = 1.0
    account_index = int(getattr(adapter, "account_index", 0) or 0)
    rest_task: Optional[asyncio.Task] = None
    if accounts is not None:
        rest_task = asyncio.create_task(
            _account_rest_loop(
                venue=venue,
                venue_cfg=venue_cfg,
                symbol=symbol,
                adapter=adapter,
                accounts=accounts,
                stop=stop,
                has_auth=True,
            )
        )

    def _book_key(sym: str) -> str:
        return slot_book_key(venue, sym)

    def on_order_book_update(market_id, order_book):
        if stop.is_set():
            return
        payload = order_book if isinstance(order_book, dict) else {}
        meta = getattr(adapter, "_market_by_id", {}).get(market_id) or {}
        have = str(meta.get("symbol") or payload.get("symbol") or payload.get("market") or "")
        matched = _pick_wanted_symbol(have, symbols) if have else None
        if matched is None and len(symbols) == 1:
            matched = symbols[0]
        if matched is None:
            return
        bid, ask, bid_sz, ask_sz = _bbo_from_book(payload.get("bids"), payload.get("asks"))
        loop.create_task(
            book.update(
                Quote(
                    venue=_book_key(matched),
                    exchange=exchange,
                    symbol=matched,
                    bid=bid,
                    ask=ask,
                    bid_sz=bid_sz,
                    ask_sz=ask_sz,
                    ts=time.time(),
                    source="wss",
                )
            )
        )

    def on_account_update(_account_id, payload):
        """account_all：一次推送拆到各品种仓位。"""
        if accounts is None or stop.is_set():
            return
        by_sym = parse_lighter_positions_map(payload)
        now = time.time()
        if by_sym:
            for have, qty in by_sym.items():
                matched = _pick_wanted_symbol(have, symbols)
                if matched is None:
                    continue
                loop.create_task(
                    accounts.patch(
                        AccountSnap(
                            venue=_book_key(matched),
                            pos_qty=qty,
                            pos_symbol=matched,
                            source="wss",
                            ts=now,
                        )
                    )
                )
            return
        # 空列表：不写成 0，交给粘性仓
        for matched in symbols:
            pos_qty = parse_lighter_positions(payload, matched)
            if pos_qty is None:
                continue
            loop.create_task(
                accounts.patch(
                    AccountSnap(
                        venue=_book_key(matched),
                        pos_qty=pos_qty,
                        pos_symbol=matched,
                        source="wss",
                        ts=now,
                    )
                )
            )

    def on_user_stats_update(_account_id, payload):
        """user_stats：只更新净值/可用（账户级一次）。"""
        if accounts is None or stop.is_set():
            return
        parsed = parse_lighter_user_stats(payload)
        if parsed["equity"] is None and parsed["available"] is None:
            return
        loop.create_task(
            accounts.patch(
                AccountSnap(
                    venue=venue,
                    equity=parsed["equity"],
                    available=parsed["available"],
                    source="wss",
                    ts=time.time(),
                )
            )
        )

    async def _stop_ws(ws_client: Any, run_task: Optional[asyncio.Task]) -> None:
        ws = getattr(ws_client, "ws", None)
        if ws is not None:
            with contextlib.suppress(Exception):
                await ws.close()
        if run_task is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await run_task

    try:
        while not stop.is_set():
            ws_client = None
            run_task: Optional[asyncio.Task] = None
            stop_task: Optional[asyncio.Task] = None
            try:
                ws_kwargs: Dict[str, Any] = {
                    "order_book_symbols": list(symbols),
                    "on_order_book_update": on_order_book_update,
                }
                if accounts is not None:
                    ws_kwargs.update(
                        account_ids=[account_index],
                        user_stats_ids=[account_index],
                        on_account_update=on_account_update,
                        on_user_stats_update=on_user_stats_update,
                    )
                ws_client = await adapter.connect_ws(**ws_kwargs)
                run_task = asyncio.create_task(adapter.run_ws(ws_client))
                stop_task = asyncio.create_task(stop.wait())
                done, _pending = await asyncio.wait(
                    {run_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if stop.is_set() or stop_task in done:
                    await _stop_ws(ws_client, run_task)
                    return
                if run_task in done:
                    exc = run_task.exception()
                    if exc:
                        raise exc
                delay = 1.0
            except asyncio.CancelledError:
                if ws_client is not None:
                    await _stop_ws(ws_client, run_task)
                raise
            except Exception as exc:
                now = time.time()
                err = str(exc)
                for matched in symbols or [symbol]:
                    await book.update(
                        Quote(
                            venue=_book_key(matched),
                            exchange=exchange,
                            symbol=matched,
                            error=err,
                            ts=now,
                        )
                    )
                delay = await _backoff(stop, delay)
            finally:
                if stop_task is not None and not stop_task.done():
                    stop_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await stop_task
    finally:
        if rest_task is not None:
            rest_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await rest_task


async def _fetch_ondo_rest(adapter: Any, symbol: str) -> tuple[
    Optional[float], Optional[float], Optional[float], Optional[float]
]:
    raw = await asyncio.wait_for(
        asyncio.to_thread(adapter.get_orderbook, symbol, 1),
        timeout=5.0,
    )
    payload = raw if isinstance(raw, dict) else {}
    bid, ask, bid_sz, ask_sz = _bbo_from_book(payload.get("bids"), payload.get("asks"))
    if bid is not None and ask is not None:
        return bid, ask, bid_sz, ask_sz
    ticker = await asyncio.wait_for(
        asyncio.to_thread(adapter.get_ticker, symbol),
        timeout=5.0,
    )
    tick = ticker if isinstance(ticker, dict) else {}
    if bid is None:
        bid = _to_float(tick.get("bid_price"))
    if ask is None:
        ask = _to_float(tick.get("ask_price"))
    return bid, ask, bid_sz, ask_sz


async def _push_ondo_rest(
    *,
    adapter: Any,
    venue: str,
    exchange: str,
    symbol: str,
    book: QuoteBook,
) -> None:
    bid, ask, bid_sz, ask_sz = await _fetch_ondo_rest(adapter, symbol)
    if bid is None and ask is None:
        return
    await book.update(
        Quote(
            venue=venue,
            exchange=exchange,
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_sz=bid_sz,
            ask_sz=ask_sz,
            ts=time.time(),
            source="rest",
        )
    )


async def _run_ondo(
    venue: str,
    venue_cfg: Dict[str, Any],
    book: QuoteBook,
    stop: asyncio.Event,
    accounts: Optional[AccountBook] = None,
) -> None:
    symbols = [
        normalize_ondo_symbol(s) for s in (feed_symbols(venue_cfg) or [str(venue_cfg.get("symbol") or "")])
        if str(s).strip()
    ]
    symbol = symbols[0] if symbols else ""
    exchange = str(venue_cfg.get("exchange") or "")
    stale_ms = int(venue_cfg.get("stale_ms", 2000))
    rest_interval = float(venue_cfg.get("rest_interval_sec", 1.0))
    delay = 1.0
    adapter = create_adapter(_adapter_config(venue_cfg))
    last_book_ts = 0.0
    has_auth = _ondo_authed(adapter)
    rest_task: Optional[asyncio.Task] = None
    if accounts is not None:
        rest_task = asyncio.create_task(
            _account_rest_loop(
                venue=venue,
                venue_cfg=venue_cfg,
                symbol=symbol,
                adapter=adapter,
                accounts=accounts,
                stop=stop,
                has_auth=has_auth,
            )
        )

    def _book_key(sym: str) -> str:
        return slot_book_key(venue, sym)

    async def on_msg(message: Dict[str, Any]) -> None:
        nonlocal last_book_ts
        if stop.is_set():
            return
        channel = str(message.get("channel") or "")
        if channel and channel not in ("topOfBooksPerps", "book"):
            return
        now = time.time()
        last_book_ts = now
        data = message.get("data")
        rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        updated = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            market = str(row.get("market") or "")
            matched = _pick_wanted_symbol(normalize_ondo_symbol(market), symbols) if market else None
            if matched is None:
                continue
            bid, ask, bid_sz, ask_sz = _bbo_from_book(row.get("bids"), row.get("asks"))
            if bid is None and ask is None:
                bid, bid_sz = _level_px_sz(row.get("bid") or row.get("bestBid"))
                ask, ask_sz = _level_px_sz(row.get("ask") or row.get("bestAsk"))
            await book.update(
                Quote(
                    venue=_book_key(matched),
                    exchange=exchange,
                    symbol=matched,
                    bid=bid,
                    ask=ask,
                    bid_sz=bid_sz,
                    ask_sz=ask_sz,
                    ts=now,
                    source="wss",
                )
            )
            updated = True
        if not updated:
            for matched in symbols:
                await book.touch(_book_key(matched), now, source="wss")

    async def on_balance(message: Dict[str, Any]) -> None:
        if accounts is None or stop.is_set():
            return
        if str(message.get("type") or "") != "update":
            return
        parsed = parse_ondo_balance(message)
        if parsed["equity"] is None and parsed["available"] is None:
            return
        await accounts.patch(
            AccountSnap(
                venue=venue,
                equity=parsed["equity"],
                available=parsed["available"],
                source="wss",
                ts=time.time(),
            )
        )

    async def on_positions(message: Dict[str, Any]) -> None:
        if accounts is None or stop.is_set():
            return
        if str(message.get("type") or "") != "update":
            return
        now = time.time()
        by_mkt = parse_ondo_positions_map(message)
        if by_mkt:
            for have, qty in by_mkt.items():
                matched = _pick_wanted_symbol(normalize_ondo_symbol(have), symbols)
                if matched is None:
                    continue
                await accounts.patch(
                    AccountSnap(
                        venue=_book_key(matched),
                        pos_qty=qty,
                        pos_symbol=matched,
                        source="wss",
                        ts=now,
                    )
                )
            return
        for matched in symbols:
            pos_qty = parse_ondo_positions(message, matched)
            if pos_qty is None:
                continue
            await accounts.patch(
                AccountSnap(
                    venue=_book_key(matched),
                    pos_qty=pos_qty,
                    pos_symbol=matched,
                    source="wss",
                    ts=now,
                )
            )

    async def rest_once() -> None:
        """仅对过期品种拉 REST 盘口，避免每个品种无脑打接口。"""
        now = time.time()
        snap = book.latest()
        for matched in symbols:
            key = _book_key(matched)
            quote = snap.get(key)
            if (
                quote is not None
                and quote.bid is not None
                and quote.ask is not None
                and quote.ts
                and (now - quote.ts) * 1000 <= stale_ms
            ):
                continue
            with contextlib.suppress(Exception):
                await _push_ondo_rest(
                    adapter=adapter,
                    venue=key,
                    exchange=exchange,
                    symbol=matched,
                    book=book,
                )

    try:
        while not stop.is_set():
            try:
                await adapter.subscribe_market("book", callback=on_msg, markets=list(symbols))
                stream = adapter.market_stream
                if stream is not None:
                    stream.callbacks.setdefault("*", on_msg)
                if accounts is not None and has_auth:
                    try:
                        await adapter.subscribe_private("balance", callback=on_balance)
                        await adapter.subscribe_private("positions", callback=on_positions)
                    except Exception as exc:
                        await accounts.patch(
                            AccountSnap(
                                venue=venue,
                                error=(f"私有WSS失败: {exc}")[:80],
                                ts=time.time(),
                                source="wss",
                            )
                        )
                delay = 1.0
                last_rest = 0.0
                while not stop.is_set():
                    if stream is None or not stream.connected:
                        raise RuntimeError("Ondo WSS 已断开")
                    now = time.time()
                    ws_fresh = last_book_ts > 0 and (now - last_book_ts) * 1000 <= stale_ms
                    if not ws_fresh and now - last_rest >= rest_interval:
                        last_rest = now
                        await rest_once()
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=0.2)
                    except asyncio.TimeoutError:
                        continue
            except asyncio.CancelledError:
                raise
            except Exception:
                last_rest = 0.0
                backoff_until = time.time() + delay
                while not stop.is_set() and time.time() < backoff_until:
                    now = time.time()
                    if now - last_rest >= rest_interval:
                        last_rest = now
                        await rest_once()
                    remain = max(0.05, min(rest_interval, backoff_until - time.time()))
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=remain)
                    except asyncio.TimeoutError:
                        continue
                delay = min(delay * 2.0, 15.0)
            finally:
                stream = getattr(adapter, "market_stream", None)
                if stream is not None:
                    with contextlib.suppress(Exception):
                        await stream.close()
                    adapter.market_stream = None
    finally:
        if rest_task is not None:
            rest_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await rest_task


def _popdex_authed(adapter: Any) -> bool:
    return bool(str(getattr(adapter, "wallet_id", "") or "").strip())


async def _run_popdex(
    venue: str,
    venue_cfg: Dict[str, Any],
    book: QuoteBook,
    stop: asyncio.Event,
    accounts: Optional[AccountBook] = None,
) -> None:
    symbol = normalize_popdex_symbol(str(venue_cfg.get("symbol") or ""))
    exchange = str(venue_cfg.get("exchange") or "")
    stale_ms = int(venue_cfg.get("stale_ms", 2000))
    rest_interval = float(venue_cfg.get("rest_interval_sec", 1.0))
    delay = 1.0
    adapter = create_adapter(_adapter_config(venue_cfg))
    last_book_ts = 0.0
    has_auth = _popdex_authed(adapter)
    rest_task: Optional[asyncio.Task] = None
    if accounts is not None:
        rest_task = asyncio.create_task(
            _account_rest_loop(
                venue=venue,
                venue_cfg=venue_cfg,
                symbol=symbol,
                adapter=adapter,
                accounts=accounts,
                stop=stop,
                has_auth=has_auth,
            )
        )

    async def on_book(message: Dict[str, Any]) -> None:
        nonlocal last_book_ts
        if stop.is_set():
            return
        arg = message.get("arg") if isinstance(message.get("arg"), dict) else {}
        topic = str(arg.get("topic") or message.get("topic") or "").lower()
        if topic and topic not in ("books1", "book", "ticker"):
            return
        now = time.time()
        data = message.get("data")
        rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        updated = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            market = str(row.get("symbol") or arg.get("symbol") or "")
            if market and normalize_popdex_symbol(market) != symbol:
                continue
            bid, ask, bid_sz, ask_sz = _bbo_from_book(
                row.get("b") or row.get("bids"),
                row.get("a") or row.get("asks"),
            )
            if bid is None:
                bid = _to_float(row.get("bid1Price") or row.get("bid"))
                bid_sz = _to_float(row.get("bid1Size")) if bid_sz is None else bid_sz
            if ask is None:
                ask = _to_float(row.get("ask1Price") or row.get("ask"))
                ask_sz = _to_float(row.get("ask1Size")) if ask_sz is None else ask_sz
            await book.update(
                Quote(
                    venue=venue,
                    exchange=exchange,
                    symbol=symbol,
                    bid=bid,
                    ask=ask,
                    bid_sz=bid_sz,
                    ask_sz=ask_sz,
                    ts=now,
                    source="wss",
                )
            )
            last_book_ts = now
            updated = True
            break
        if not updated and last_book_ts > 0:
            last_book_ts = now
            await book.touch(venue, now, source="wss")

    async def on_account(message: Dict[str, Any]) -> None:
        if accounts is None or stop.is_set():
            return
        action = str(message.get("action") or "").lower()
        if action and action not in ("snapshot", "update"):
            return
        parsed = parse_popdex_account(message)
        if parsed["equity"] is None and parsed["available"] is None:
            return
        await accounts.patch(
            AccountSnap(
                venue=venue,
                equity=parsed["equity"],
                available=parsed["available"],
                pos_symbol=symbol,
                source="wss",
                ts=time.time(),
            )
        )

    async def on_position(message: Dict[str, Any]) -> None:
        if accounts is None or stop.is_set():
            return
        action = str(message.get("action") or "").lower()
        if action and action not in ("snapshot", "update"):
            return
        pos_qty = parse_popdex_positions(message, symbol)
        if pos_qty is None:
            return
        await accounts.patch(
            AccountSnap(
                venue=venue,
                pos_qty=pos_qty,
                pos_symbol=symbol,
                source="wss",
                ts=time.time(),
            )
        )

    async def rest_once() -> None:
        with contextlib.suppress(Exception):
            await _push_ondo_rest(
                adapter=adapter,
                venue=venue,
                exchange=exchange,
                symbol=symbol,
                book=book,
            )

    try:
        while not stop.is_set():
            try:
                await adapter.subscribe_market("book", symbol, callback=on_book)
                stream = adapter.market_stream
                if accounts is not None and has_auth:
                    try:
                        await adapter.subscribe_account("account", callback=on_account)
                        await adapter.subscribe_account("position", callback=on_position)
                    except Exception as exc:
                        await accounts.patch(
                            AccountSnap(
                                venue=venue,
                                error=(f"私有WSS失败: {exc}")[:80],
                                ts=time.time(),
                                source="wss",
                            )
                        )
                delay = 1.0
                last_rest = 0.0
                while not stop.is_set():
                    if stream is None or not stream.connected:
                        raise RuntimeError("PopDEX WSS 已断开")
                    now = time.time()
                    ws_fresh = last_book_ts > 0 and (now - last_book_ts) * 1000 <= stale_ms
                    if not ws_fresh and now - last_rest >= rest_interval:
                        last_rest = now
                        await rest_once()
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=0.2)
                    except asyncio.TimeoutError:
                        continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await book.update(
                    Quote(
                        venue=venue,
                        exchange=exchange,
                        symbol=symbol,
                        error=str(exc),
                        ts=time.time(),
                    )
                )
                last_rest = 0.0
                backoff_until = time.time() + delay
                while not stop.is_set() and time.time() < backoff_until:
                    now = time.time()
                    if now - last_rest >= rest_interval:
                        last_rest = now
                        await rest_once()
                    remain = max(0.05, min(rest_interval, backoff_until - time.time()))
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=remain)
                    except asyncio.TimeoutError:
                        continue
                delay = min(delay * 2.0, 15.0)
            finally:
                stream = getattr(adapter, "market_stream", None)
                if stream is not None:
                    with contextlib.suppress(Exception):
                        await stream.close()
                    adapter.market_stream = None
    finally:
        if rest_task is not None:
            rest_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await rest_task
