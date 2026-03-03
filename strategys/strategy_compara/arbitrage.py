import argparse
import asyncio
import json
import os
import sys
import threading
import time
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal

import yaml
import queue

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from adapters.factory import create_adapter


PRICE_MAP: Dict[str, Dict[str, float]] = {}
PRICE_LOCK = threading.Lock()
POSITION_MAP: Dict[str, Dict[str, float]] = {}
POSITION_LOCK = threading.Lock()
BALANCE_MAP: Dict[str, Dict[str, Any]] = {}
BALANCE_LOCK = threading.Lock()
ORDER_MAP: Dict[str, Dict[str, Any]] = {}
ORDER_LOCK = threading.Lock()
COOLDOWN_LOCK = threading.Lock()
COOLDOWN_UNTIL = 0.0
ORDER_COOLDOWN_SEC = 5.0
ARB_SETTINGS = {
    "position_threshold": 1e-8,
    "print_interval_sec": 2.0,
    "order_max_retries": 1,
    "order_timeout_sec": 1.0,
    "order_poll_interval_sec": 0.2,
}
SIGNAL_QUEUE: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)


def _log(message: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] {message}")


def _update_position(exchange_key: str, symbol: str, qty: float):
    with POSITION_LOCK:
        if exchange_key not in POSITION_MAP:
            POSITION_MAP[exchange_key] = {}
        POSITION_MAP[exchange_key][symbol] = qty


def _ensure_account(exchange_key: str):
    if exchange_key not in BALANCE_MAP:
        BALANCE_MAP[exchange_key] = {
            "balances": {},
            "ts": 0,
        }


def _update_account_position(exchange_key: str, symbol: str, qty: float):
    _update_position(exchange_key, symbol, qty)


def _update_account_orders(exchange_key: str, symbol: str, orders: list):
    _update_order_map(exchange_key, symbol, orders)


def _update_order_map(exchange_key: str, symbol: str, orders: list):
    with ORDER_LOCK:
        if exchange_key not in ORDER_MAP:
            ORDER_MAP[exchange_key] = {}
        ORDER_MAP[exchange_key][symbol] = orders


def _update_account_balance(exchange_key: str, asset: str, total: float, available: Optional[float] = None):
    with BALANCE_LOCK:
        _ensure_account(exchange_key)
        BALANCE_MAP[exchange_key]["balances"][asset] = {
            "total": total,
            "available": available if available is not None else total,
        }
        BALANCE_MAP[exchange_key]["ts"] = int(time.time() * 1000)


def _set_order_cooldown():
    global COOLDOWN_UNTIL
    with COOLDOWN_LOCK:
        COOLDOWN_UNTIL = time.time() + ORDER_COOLDOWN_SEC


def _can_place_order() -> bool:
    with COOLDOWN_LOCK:
        return time.time() >= COOLDOWN_UNTIL


def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def convert_symbol(symbol: str, exchange_name: str) -> str:
    name = exchange_name.lower()
    _log(f"[convert_symbol] {symbol} {exchange_name} {name}")
    if name == "standx":
        return f"{symbol}-USD"
    if name == "grvt":
        return f"{symbol}_USDT_Perp"
    if name == "lighter":
        return symbol
    return symbol


def _update_price(exchange_key: str, bid: float, ask: float):
    with PRICE_LOCK:
        PRICE_MAP[exchange_key] = {"bid": bid, "ask": ask, "ts": int(time.time() * 1000)}


async def _standx_wss(adapter, exchange_key: str, symbol: str):
    try:
        adapter.connect()
    except Exception:
        pass
    await adapter.connect_market_stream()

    async def on_depth(message):
        payload = message.get("data", {})
        bids = payload.get("bids") or []
        asks = payload.get("asks") or []
        bid = float(bids[0][0]) if bids and len(bids[0]) > 0 else None
        ask = float(asks[0][0]) if asks and len(asks[0]) > 0 else None
        if bid is None or ask is None:
            return
        _update_price(exchange_key, bid, ask)

    await adapter.subscribe_market("depth_book", symbol, callback=on_depth)

    try:
        positions = adapter.get_positions(symbol=symbol)
        for pos in positions or []:
            qty = float(pos.size)
            if pos.side == "short":
                qty = -abs(qty)
            _update_position(exchange_key, pos.symbol or symbol, qty)
    except Exception:
        pass

    try:
        balance = adapter.get_balance()
        total_val = float(balance.total_balance)
        avail_val = float(balance.available_balance)
        _update_account_balance(exchange_key, "DUSD", total_val, avail_val)
    except Exception:
        pass

    try:
        open_orders = adapter.get_open_orders(symbol=symbol)
        symbol_map: Dict[str, list] = {}
        for order in open_orders or []:
            symbol_val = getattr(order, "symbol", None) or symbol
            size = getattr(order, "quantity", None)
            price = getattr(order, "price", None)
            cl_ord_id = getattr(order, "client_order_id", None)
            side = getattr(order, "side", None)
            symbol_map.setdefault(symbol_val, []).append(
                {
                    "symbol": symbol_val,
                    "size": str(size) if size is not None else None,
                    "price": str(price) if price is not None else None,
                    "cl_ord_id": cl_ord_id,
                    "side": side,
                }
            )
        for sym, items in symbol_map.items():
            _update_account_orders(exchange_key, sym, items)
    except Exception:
        pass

    async def on_position(message: dict):
        data = message.get("data")
        positions = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            symbol_val = pos.get("symbol") or symbol
            qty_val = pos.get("qty") or pos.get("size") or pos.get("position")
            if qty_val is None:
                continue
            try:
                qty_float = float(qty_val)
            except (TypeError, ValueError):
                continue
            side = str(pos.get("side", "")).lower()
            if side in ["short", "sell"]:
                qty_float = -abs(qty_float)
            _update_account_position(exchange_key, symbol_val, qty_float)

    async def on_order(message: dict):
        data = message.get("data")
        orders = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        symbol_map: Dict[str, list] = {}
        for order in orders:
            if not isinstance(order, dict):
                continue
            status = str(order.get("status", "")).lower()
            symbol_val = order.get("symbol") or symbol
            symbol_map.setdefault(symbol_val, []).append(
                {
                    "symbol": symbol_val,
                    "size": order.get("qty"),
                    "price": order.get("price"),
                    "cl_ord_id": order.get("cl_ord_id"),
                    "side": order.get("side"),
                    "status": status,
                }
            )
        for sym, items in symbol_map.items():
            with ORDER_LOCK:
                existing = ORDER_MAP.get(exchange_key, {}).get(sym, [])
            existing_map = {
                (item.get("cl_ord_id") or item.get("order_id") or item.get("id")): item
                for item in existing
                if isinstance(item, dict)
            }
            open_statuses = {"open", "pending", "partially_filled"}
            cancel_statuses = {"cancelled", "canceled", "rejected", "filled", "closed"}
            for item in items:
                key = item.get("cl_ord_id") or item.get("order_id") or item.get("id")
                if not key:
                    continue
                status = (item.get("status") or "").lower()
                if status in cancel_statuses:
                    existing_map.pop(key, None)
                    continue
                if status in open_statuses or status == "":
                    existing_map[key] = item
            cleaned = []
            for item in existing_map.values():
                status = (item.get("status") or "").lower()
                if status == "" or status in open_statuses:
                    cleaned.append(
                        {
                            k: item.get(k)
                            for k in ["symbol", "size", "price", "cl_ord_id", "side"]
                        }
                    )
            _update_account_orders(exchange_key, sym, cleaned)

    async def on_balance(message: dict):
        data = message.get("data")
        if not isinstance(data, dict):
            return
        asset = data.get("token") or data.get("asset") or data.get("symbol") or data.get("currency")
        if not asset:
            return
        total = data.get("total") or data.get("balance") or data.get("equity")
        available = data.get("free") or data.get("available") or data.get("available_balance")
        try:
            total_val = float(total)
        except (TypeError, ValueError):
            return
        avail_val = None
        if available is not None:
            try:
                avail_val = float(available)
            except (TypeError, ValueError):
                avail_val = None
        _update_account_balance(exchange_key, asset, total_val, avail_val)

    if adapter.token:
        streams = [{"channel": "order"}, {"channel": "position"}, {"channel": "balance"}]
        await adapter.market_stream.authenticate(adapter.token, streams=streams)
        await adapter.market_stream.subscribe("order", callback=on_order)
        await adapter.market_stream.subscribe("position", callback=on_position)
        await adapter.market_stream.subscribe("balance", callback=on_balance)
    await asyncio.Event().wait()


async def _grvt_wss(adapter, exchange_key: str, symbol: str):
    await adapter.connect_ws()

    def on_price(message: dict):
        feed = message.get("feed") or message.get("data", {}).get("feed") or message.get("params", {}).get("feed") or {}
        bid = feed.get("best_bid_price") or feed.get("best_bid")
        ask = feed.get("best_ask_price") or feed.get("best_ask")
        if bid is None or ask is None:
            return
        _update_price(exchange_key, float(bid), float(ask))

    await adapter.subscribe_ws("ticker.s", {"instrument": symbol}, on_price)

    def on_position(message: dict):
        feed = message.get("feed") or message.get("data", {}).get("feed") or message.get("params", {}).get("feed") or {}
        symbol_val = feed.get("instrument") or symbol
        qty_val = feed.get("size") or feed.get("qty") or feed.get("position")
        if qty_val is None:
            return
        try:
            qty_float = float(qty_val)
        except (TypeError, ValueError):
            return
        side = str(feed.get("side", "")).lower()
        if side in ["short", "sell"]:
            qty_float = -abs(qty_float)
        _update_account_position(exchange_key, symbol_val, qty_float)

    def on_order(message: dict):
        feed = message.get("feed") or message.get("data", {}).get("feed") or message.get("params", {}).get("feed") or {}
        legs = feed.get("legs") or []
        leg = legs[0] if isinstance(legs, list) and legs else {}
        symbol_val = leg.get("instrument") or feed.get("instrument") or symbol
        cl_ord_id = feed.get("order_id") or feed.get("id") or feed.get("metadata", {}).get("client_order_id")
        is_buying = leg.get("is_buying_asset")
        side_val = feed.get("side")
        if side_val is None and is_buying is not None:
            side_val = "buy" if is_buying else "sell"
        order_item = {
            "symbol": symbol_val,
            "size": leg.get("size") or feed.get("qty"),
            "price": leg.get("limit_price") or feed.get("price"),
            "cl_ord_id": cl_ord_id,
            "side": side_val,
        }
        status = (
            feed.get("state", {}).get("status")
            or feed.get("status")
            or feed.get("metadata", {}).get("status")
            or ""
        )
        status = str(status).upper()
        closed_statuses = {"CANCELLED", "CANCELED", "REJECTED", "FILLED", "CLOSED"}
        with ORDER_LOCK:
            existing = ORDER_MAP.get(exchange_key, {}).get(symbol_val, [])
        existing_map = {}
        for item in existing:
            if not isinstance(item, dict):
                continue
            key = item.get("cl_ord_id")
            if key is not None:
                existing_map[key] = item
        if cl_ord_id is not None and status in closed_statuses:
            existing_map.pop(cl_ord_id, None)
        elif cl_ord_id is not None:
            existing_map[cl_ord_id] = order_item
        merged = list(existing_map.values())
        _update_account_orders(exchange_key, symbol_val, merged)

    # def on_state(message: dict):
    #     feed = message.get("feed") or message.get("data", {}).get("feed") or message.get("params", {}).get("feed") or {}
    #     asset = feed.get("asset") or feed.get("symbol") or "USDC"
    #     total = feed.get("balance") or feed.get("equity")
    #     available = feed.get("available") or feed.get("available_balance")
    #     try:
    #         total_val = float(total)
    #     except (TypeError, ValueError):
    #         return
    #     avail_val = None
    #     if available is not None:
    #         try:
    #             avail_val = float(available)
    #         except (TypeError, ValueError):
    #             avail_val = None
    #     _update_account_balance(exchange_key, asset, total_val, avail_val)

    await adapter.subscribe_ws("position", {}, on_position)
    await adapter.subscribe_ws("order", {"instrument": symbol}, on_order)
    # await adapter.subscribe_ws("state", {}, on_state)
    await asyncio.Event().wait()


async def _lighter_wss(adapter, exchange_key: str, symbol: str):
    def on_order_book_update(_, order_book):
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        if not bids or not asks:
            return
        best_bid = max(float(item["price"]) for item in bids)
        best_ask = min(float(item["price"]) for item in asks)
        _update_price(exchange_key, best_bid, best_ask)

    def on_account_update(_, payload):
        if not isinstance(payload, dict):
            return
        positions = payload.get("positions")
        if isinstance(positions, dict):
            positions = positions.values()
        if not isinstance(positions, list) and not isinstance(positions, type({}.values())):
            return
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            qty = pos.get("position")
            if qty is None:
                continue
            try:
                qty_float = float(qty)
            except (TypeError, ValueError):
                continue
            sign = pos.get("sign")
            if sign is not None:
                try:
                    qty_float = abs(qty_float) * (1 if int(sign) > 0 else -1)
                except (TypeError, ValueError):
                    pass
            _update_position(exchange_key, pos.get("symbol") or symbol, qty_float)

    def on_account_orders_update(_, payload):
        if not isinstance(payload, dict):
            return
        orders = payload.get("orders")
        if not isinstance(orders, dict):
            return
        # Lighter orders payload uses market_id as key, array of orders as value
        symbol_map: Dict[str, list] = {}
        for _, items in orders.items():
            if not isinstance(items, list):
                continue
            for order in items:
                if not isinstance(order, dict):
                    continue
                symbol_val = order.get("symbol") or symbol
                size = order.get("remaining_base_amount") or order.get("initial_base_amount")
                price = order.get("price")
                order_index = order.get("order_index")
                symbol_map.setdefault(symbol_val, []).append(
                    {
                        "symbol": symbol_val,
                        "size": size,
                        "price": price,
                        "order_index": order_index,
                    }
                )
        for sym, items in symbol_map.items():
            _update_order_map(exchange_key, sym, items)

    def on_user_stats_update(_, payload):
        if not isinstance(payload, dict):
            return
        stats = payload.get("stats") or {}
        total_stats = stats.get("total_stats") if isinstance(stats, dict) else None
        source = total_stats if isinstance(total_stats, dict) else stats
        if not isinstance(source, dict):
            return
        total = source.get("portfolio_value") or source.get("collateral")
        available = source.get("available_balance")
        try:
            total_val = float(total)
        except (TypeError, ValueError):
            return
        avail_val = None
        if available is not None:
            try:
                avail_val = float(available)
            except (TypeError, ValueError):
                avail_val = None
        _update_account_balance(exchange_key, "USDC", total_val, avail_val)

    ws_client = await adapter.connect_ws(
        order_book_symbols=[symbol],
        account_ids=[int(adapter.account_index)],
        on_order_book_update=on_order_book_update,
        on_account_update=on_account_update,
        account_orders_ids=[int(adapter.account_index)],
        on_account_orders_update=on_account_orders_update,
        user_stats_ids=[int(adapter.account_index)],
        on_user_stats_update=on_user_stats_update,
    )
    await adapter.run_ws(ws_client)


def _run_ws_thread(exchanges: List[Tuple[str, Dict[str, Any], str]]):
    async def runner():
        tasks = []
        for exchange_key, exchange_cfg, symbol in exchanges:
            adapter = create_adapter(exchange_cfg)
            name = exchange_cfg["exchange_name"].lower()
            if name == "standx":
                tasks.append(asyncio.create_task(_standx_wss(adapter, exchange_key, symbol)))
            elif name == "grvt":
                tasks.append(asyncio.create_task(_grvt_wss(adapter, exchange_key, symbol)))
            elif name == "lighter":
                tasks.append(asyncio.create_task(_lighter_wss(adapter, exchange_key, symbol)))
            else:
                raise ValueError(f"不支持的交易所: {exchange_cfg['exchange_name']}")
        await asyncio.gather(*tasks)
    # 每个线程独立 event loop，避免跨 loop 的 aiohttp/client 绑定问题
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner())




def _run_print_thread(
    ex1_key: str,
    ex2_key: str,
    min_profit_pct: float,
    max_profit_pct: float,
    use_dynamic_profit_window: bool,
    profit_buffer_pct: float,
    interval_sec: float,
):
    def _profit_ratio(buy_price: float, sell_price: float) -> float:
        if buy_price <= 0:
            return 0.0
        cost = buy_price
        proceeds = sell_price
        return (proceeds - cost) / cost

    window_size = max_profit_pct - min_profit_pct
    current_min = min_profit_pct
    current_max = max_profit_pct
    while True:
        with PRICE_LOCK:
            ex1_price = PRICE_MAP.get(ex1_key)
            ex2_price = PRICE_MAP.get(ex2_key)
        if not ex1_price or not ex2_price:
            _log("套利检测：价格未就绪，等待中...")
            time.sleep(interval_sec)
            continue

        # 方向A：卖出 ex1 的 bid，对应买入 ex2 的 ask
        profit_sell_ex1_buy_ex2 = _profit_ratio(
            buy_price=ex2_price["ask"],
            sell_price=ex1_price["bid"],
        )
        # 方向B：卖出 ex2 的 bid，对应买入 ex1 的 ask
        profit_sell_ex2_buy_ex1 = _profit_ratio(
            buy_price=ex1_price["ask"],
            sell_price=ex2_price["bid"],
        )

        if profit_sell_ex1_buy_ex2 >= profit_sell_ex2_buy_ex1:
            direction = f"{ex1_key}卖/{ex2_key}买"
            best_profit = profit_sell_ex1_buy_ex2
            ex1_side = "sell"
        else:
            direction = f"{ex2_key}卖/{ex1_key}买"
            best_profit = profit_sell_ex2_buy_ex1
            ex1_side = "buy"

        effective_min = current_min
        effective_max = current_max
        if use_dynamic_profit_window and window_size > 0:
            buffer = max(0.0, profit_buffer_pct)
            if best_profit < effective_min - buffer:
                effective_min = best_profit + buffer
                effective_max = effective_min + window_size
                current_min, current_max = effective_min, effective_max
            elif best_profit > effective_max + buffer:
                effective_max = best_profit - buffer
                effective_min = effective_max - window_size
                current_min, current_max = effective_min, effective_max

        if best_profit > effective_max:
            _push_signal(
                {
                    "type": "open",
                    "ex1_side": ex1_side,
                    "profit": best_profit,
                    "direction": direction,
                }
            )
        elif best_profit < effective_min:
            _push_signal(
                {
                    "type": "close",
                    "profit": best_profit,
                    "direction": direction,
                }
            )
        else:
            _push_signal(
                {
                    "type": "cancel",
                    "profit": best_profit,
                    "direction": direction,
                }
            )
        time.sleep(interval_sec)


def _run_state_print_thread(interval_sec: float):
    while True:
        with PRICE_LOCK:
            price_snapshot = dict(PRICE_MAP)
        with POSITION_LOCK:
            position_snapshot = dict(POSITION_MAP)
        with BALANCE_LOCK:
            account_snapshot = dict(BALANCE_MAP)
        with ORDER_LOCK:
            order_snapshot = dict(ORDER_MAP)
        _log(
            "[state] "
            f"price={json.dumps(price_snapshot, ensure_ascii=False)} "
            f"position={json.dumps(position_snapshot, ensure_ascii=False)} "
            f"account={json.dumps(account_snapshot, ensure_ascii=False)} "
            f"order={json.dumps(order_snapshot, ensure_ascii=False)}"
        )
        time.sleep(interval_sec)


async def _position_compare_loop(
    ex1_key: str,
    ex2_key: str,
    ex1_symbol: str,
    ex2_symbol: str,
    interval_sec: float,
    ex2_cfg: Dict[str, Any],
):
    ex2_adapter = create_adapter(ex2_cfg)
    try:
        await asyncio.to_thread(ex2_adapter.connect)
    except Exception:
        pass

    async def _place_hedge(order_side: str, qty: float, reduce_only: bool):
        if hasattr(ex2_adapter, "place_order_async"):
            return await ex2_adapter.place_order_async(
                symbol=ex2_symbol,
                side=order_side,
                order_type="market",
                quantity=Decimal(str(qty)),
                reduce_only=reduce_only,
            )
        return await asyncio.to_thread(
            ex2_adapter.place_order,
            symbol=ex2_symbol,
            side=order_side,
            order_type="market",
            quantity=Decimal(str(qty)),
            reduce_only=reduce_only,
        )

    last_hedge_ts = 0.0
    threshold = float(ARB_SETTINGS.get("position_threshold", 1e-8))
    last_ex1_pos = None
    while True:
        with POSITION_LOCK:
            ex1_pos = POSITION_MAP.get(ex1_key, {}).get(ex1_symbol, 0.0)
            ex2_pos = POSITION_MAP.get(ex2_key, {}).get(ex2_symbol, 0.0)
        delta = -float(ex1_pos) - float(ex2_pos)
        delta_display = round(delta, 5)
        if abs(delta_display) < 1e-4:
            delta_display = 0.0
        if abs(delta) <= threshold:
            hedge_msg = "已对冲"
        else:
            if last_ex1_pos is None or ex1_pos != last_ex1_pos:
                try:
                    print(f"同步ex2持仓：{ex2_key} {ex2_symbol}")
                    if ex2_key.lower() == "lighter":
                        positions = await ex2_adapter.get_positions_async(symbol=ex2_symbol)
                        print(f"1同步ex2持仓：{ex2_key} {ex2_symbol} {positions}")
                    else:
                        positions = await asyncio.to_thread(ex2_adapter.get_positions, symbol=ex2_symbol)
                        print(f"2同步ex2持仓：{ex2_key} {ex2_symbol} {positions}")
                    _apply_positions(ex2_key, ex2_symbol, positions)
                except Exception as e:
                    _log(f"ex1持仓变化后同步ex2失败：{ex2_key} {ex2_symbol}，错误={e}")
                last_ex1_pos = ex1_pos
                with POSITION_LOCK:
                    ex2_pos = POSITION_MAP.get(ex2_key, {}).get(ex2_symbol, 0.0)
            hedge_side = "做多" if delta_display > 0 else "做空"
            hedge_msg = f"{hedge_side} {abs(delta_display)}"
            if time.time() - last_hedge_ts >= max(1.0, interval_sec):
                if not _can_place_order():
                    await asyncio.sleep(0.2)
                    continue
                order_side = "buy" if delta > 0 else "sell"
                reduce_only = ex2_pos != 0 and (ex2_pos * delta < 0)
                try:
                    print(f"对冲：{ex2_key} {ex2_symbol} {order_side} {abs(delta)} {reduce_only}")
                    await _place_hedge(order_side, abs(delta), reduce_only)
                    _set_order_cooldown()
                    last_hedge_ts = time.time()
                except Exception as e:
                    print(f"对冲失败：{ex2_key} {ex2_symbol} {order_side} {abs(delta)} {reduce_only}，错误={e}")
                    pass

        await asyncio.sleep(0.35)


def _run_position_compare_thread(
    ex1_key: str,
    ex2_key: str,
    ex1_symbol: str,
    ex2_symbol: str,
    interval_sec: float,
    ex2_cfg: Dict[str, Any],
):
    async def runner():
        await asyncio.sleep(5)
        await _position_compare_loop(
            ex1_key,
            ex2_key,
            ex1_symbol,
            ex2_symbol,
            interval_sec,
            ex2_cfg,
        )

    # 每个线程独立 event loop，避免跨 loop 的 aiohttp/client 绑定问题
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner())


def _default_balance_asset(exchange_key: str) -> str:
    return "USDC" if exchange_key.lower() == "lighter" else "DUSD"


def _apply_positions(exchange_key: str, symbol: str, positions: List[Any]):
    seen_symbols = set()
    for pos in positions or []:
        qty = float(pos.size)
        if pos.side == "short":
            qty = -abs(qty)
        pos_symbol = pos.symbol or symbol
        seen_symbols.add(pos_symbol)
        _update_position(exchange_key, pos_symbol, qty)
    if symbol not in seen_symbols:
        _update_position(exchange_key, symbol, 0.0)


def _sync_positions(adapter, exchange_key: str, symbol: str):
    try:
        positions = adapter.get_positions(symbol=symbol)
        _apply_positions(exchange_key, symbol, positions)
    except Exception as e:
        _log(f"同步持仓失败：{exchange_key} {symbol}，错误={e}")


def _apply_balance(exchange_key: str, balance):
    total_val = float(balance.total_balance)
    avail_val = float(balance.available_balance)
    _update_account_balance(exchange_key, _default_balance_asset(exchange_key), total_val, avail_val)


def _sync_balances(adapter, exchange_key: str):
    try:
        balance = adapter.get_balance()
        _apply_balance(exchange_key, balance)
    except Exception as e:
        _log(f"同步余额失败：{exchange_key}，错误={e}")


def _apply_open_orders(exchange_key: str, symbol: str, open_orders: List[Any]):
    symbol_map: Dict[str, list] = {}
    if not open_orders:
        _update_order_map(exchange_key, symbol, [])
        return
    for order in open_orders or []:
        symbol_val = getattr(order, "symbol", None) or symbol
        cl_ord_id = getattr(order, "client_order_id", None) or getattr(order, "order_id", None)
        symbol_map.setdefault(symbol_val, []).append(
            {
                "symbol": symbol_val,
                "size": str(getattr(order, "quantity", None)),
                "price": str(getattr(order, "price", None)),
                "cl_ord_id": cl_ord_id,
                "order_type": getattr(order, "order_type", None),
                "side": getattr(order, "side", None),
                "reduce_only": getattr(order, "reduce_only", None),
            }
        )
    for sym, items in symbol_map.items():
        _update_order_map(exchange_key, sym, items)


def _sync_open_orders(adapter, exchange_key: str, symbol: str):
    try:
        open_orders = adapter.get_open_orders(symbol=symbol)
        _apply_open_orders(exchange_key, symbol, open_orders)
    except Exception as e:
        _log(f"同步未成交失败：{exchange_key} {symbol}，错误={e}")


def _run_accounts_sync_thread(
    exchanges: List[Tuple[str, Dict[str, Any], str]],
    interval_sec: float = 1.0,
):
    async def runner():
        adapters: List[Tuple[str, Any, str]] = []
        for exchange_key, exchange_cfg, symbol in exchanges:
            adapter = create_adapter(exchange_cfg)
            try:
                await asyncio.to_thread(adapter.connect)
            except Exception:
                _log(f"账户同步线程连接失败：{exchange_key} {symbol}")
            adapters.append((exchange_key, adapter, symbol))

        while True:
            for exchange_key, adapter, symbol in adapters:
                if exchange_key.lower() == "lighter":
                    try:
                        positions = await adapter.get_positions_async(symbol=symbol)
                        _apply_positions(exchange_key, symbol, positions)
                    except Exception as e:
                        _log(f"同步持仓失败：{exchange_key} {symbol}，错误={e}")
                    try:
                        balance = await adapter.get_balance_async()
                        _apply_balance(exchange_key, balance)
                    except Exception as e:
                        _log(f"同步余额失败：{exchange_key}，错误={e}")
                    try:
                        open_orders = await adapter.get_open_orders_async(symbol=symbol)
                        _apply_open_orders(exchange_key, symbol, open_orders)
                    except Exception as e:
                        _log(f"同步未成交失败：{exchange_key} {symbol}，错误={e}")
                else:
                    await asyncio.to_thread(_sync_positions, adapter, exchange_key, symbol)
                    await asyncio.to_thread(_sync_balances, adapter, exchange_key)
                    await asyncio.to_thread(_sync_open_orders, adapter, exchange_key, symbol)
            await asyncio.sleep(interval_sec)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner())

def _push_signal(signal: Dict[str, Any]):
    try:
        if SIGNAL_QUEUE.full():
            SIGNAL_QUEUE.get_nowait()
        SIGNAL_QUEUE.put_nowait(signal)
    except Exception:
        pass


def _run_signal_thread(
    ex1_key: str,
    ex2_key: str,
    ex1_cfg: Dict[str, Any],
    symbol: str,
    order_size: float,
    order_max_retries: int,
    order_timeout_sec: float,
    order_poll_interval_sec: float,
    max_position_size: float,
):
    ex1_adapter = create_adapter(ex1_cfg)
    try:
        ex1_adapter.connect()
    except Exception:
        pass
    pending_open = False
    opened = False
    max_retries = order_max_retries
    timeout_sec = order_timeout_sec
    poll_interval_sec = order_poll_interval_sec
    last_open_orders_sync_ts = 0.0

    def _get_ex1_price(side: str) -> Optional[float]:
        with PRICE_LOCK:
            ex1_price = PRICE_MAP.get(ex1_key)
        if not ex1_price:
            return None
        return ex1_price["bid"] if side == "buy" else ex1_price["ask"]

    def _format_price_compare() -> str:
        with PRICE_LOCK:
            ex1_price = PRICE_MAP.get(ex1_key)
            ex2_price = PRICE_MAP.get(ex2_key)
        if not ex1_price or not ex2_price:
            return "对比价=NA"
        return (
            f"对比价 {ex1_key} {ex1_price['bid']}/{ex1_price['ask']} "
            f"{ex2_key} {ex2_price['bid']}/{ex2_price['ask']}"
            f"价差比例={profit:.6f}"
        )

    def _find_open_order(side: str, reduce_only: bool):
        with ORDER_LOCK:
            order_items = ORDER_MAP.get(ex1_key, {}).get(symbol, [])
        for order in order_items or []:
            if not isinstance(order, dict):
                continue
            if order.get("order_type") and order.get("order_type") != "limit":
                continue
            if order.get("side") and order.get("side") != side:
                continue
            if order.get("reduce_only") is not None and bool(order.get("reduce_only")) != bool(reduce_only):
                continue
            return order
        return None

    def _price_match(order_price: Optional[Decimal], target_price: float) -> bool:
        if order_price is None:
            return False
        try:
            return abs(float(order_price) - float(target_price)) <= 1e-8
        except (TypeError, ValueError):
            return False

    def _sync_open_orders():
        nonlocal last_open_orders_sync_ts
        now = time.time()
        if now - last_open_orders_sync_ts < 2:
            return
        try:
            open_orders = ex1_adapter.get_open_orders(symbol=symbol)
        except Exception as e:
            _log(f"同步未成交失败：{ex1_key} {symbol}，错误={e}")
            return
        symbol_map: Dict[str, list] = {}
        for order in open_orders or []:
            symbol_val = getattr(order, "symbol", None) or symbol
            symbol_map.setdefault(symbol_val, []).append(
                {
                    "symbol": symbol_val,
                    "size": str(getattr(order, "quantity", None)),
                    "price": str(getattr(order, "price", None)),
                    "cl_ord_id": getattr(order, "client_order_id", None),
                    "order_type": getattr(order, "order_type", None),
                    "side": getattr(order, "side", None),
                    "reduce_only": getattr(order, "reduce_only", None),
                }
            )
        for sym, items in symbol_map.items():
            _update_order_map(ex1_key, sym, items)
        last_open_orders_sync_ts = now

    def _get_position_from_map() -> Optional[float]:
        with POSITION_LOCK:
            return POSITION_MAP.get(ex1_key, {}).get(symbol)

    def _get_ex1_position() -> float:
        current_pos = _get_position_from_map()
        if current_pos is None:
            return 0.0
        return float(current_pos)

    def _place_limit_order(
        side: str,
        qty: float,
        price: float,
        reduce_only: bool,
        client_order_id: str,
    ) -> bool:
        print(f"place_limit_order: {side} {qty} {price} {reduce_only} {client_order_id}")
        try:
            ex1_adapter.place_order(
                symbol=symbol,
                side=side,
                order_type="limit",
                quantity=Decimal(str(qty)),
                price=Decimal(str(price)),
                time_in_force="alo",
                reduce_only=reduce_only,
                client_order_id=client_order_id,
            )
            return True
        except Exception as e:
            _log(f"挂单失败：{ex1_key} {symbol}，错误={e}")
            return False

    def _make_client_order_id(prefix: str, attempt: int) -> str:
        if ex1_key == "grvt":
            return str(int(time.time() * 1000))
        return f"{prefix}_{int(time.time() * 1000)}_{attempt}"

    def _wait_for_position_change(start_pos: float) -> bool:
        start_ts = time.time()
        while time.time() - start_ts < timeout_sec:
            current_pos = _get_position_from_map()
            if current_pos is not None and current_pos != start_pos:
                return True
            time.sleep(poll_interval_sec)
        return False
        
    while True:
        try:
            signal = SIGNAL_QUEUE.get(timeout=1)
        except Exception:
            continue

        signal_type = signal.get("type")
        profit = signal.get("profit")

        if signal_type == "open":
            ex1_side = signal.get("ex1_side")
            action = "做多" if ex1_side == "buy" else "做空"
            for attempt in range(1, max_retries + 1):
                _sync_open_orders()
                if max_position_size > 0:
                    current_pos = _get_position_from_map()
                    if current_pos is None:
                        current_pos = _get_ex1_position()
                    if abs(float(current_pos)) >= max_position_size:
                        _log(
                            f"挂单跳过：{ex1_key} {symbol} 当前持仓={current_pos} "
                            f"达到最大持仓={max_position_size}"
                            f"{_format_price_compare()}"
                        )
                        break
                price = _get_ex1_price(ex1_side)
                if price is None:
                    _log(f"挂单失败：{ex1_key} 价格未就绪")
                    break
                if not _can_place_order():
                    time.sleep(poll_interval_sec)
                    continue
                existing_order = _find_open_order(ex1_side, False)
                if existing_order and _price_match(existing_order.get("price"), price):
                    client_order_id = existing_order.get("cl_ord_id")
                    pending_open = True
                    _log(
                        f"挂单复用：开仓{action} {ex1_key} {symbol}，"
                        f"价格={price}，数量={order_size} "
                        f"{_format_price_compare()}"
                    )
                else:
                    if existing_order:
                        try:
                            ex1_adapter.cancel_all_orders(symbol=symbol)
                        except Exception as e:
                            _log(f"撤单失败：{ex1_key} {symbol}，错误={e}")
                    client_order_id = _make_client_order_id("arb_open", attempt)
                    print(f"place_limit_order: {ex1_side} {order_size} {price} False {client_order_id}")
                    if not _place_limit_order(ex1_side, order_size, price, False, client_order_id):
                        pending_open = False
                        continue
                    pending_open = True
                    _log(
                        f"挂单信号：开仓{action} {ex1_key} {symbol}，"
                        f"价格={price}，数量={order_size}"
                        f"重试={attempt}/{max_retries} {_format_price_compare()}"
                    )

                start_pos = _get_position_from_map()
                if start_pos is None:
                    start_pos = _get_ex1_position()
                if _wait_for_position_change(start_pos):
                    pending_open = False
                    _log(
                        f"开仓信号：{ex1_key} {symbol} 成交，"
                        f"方向={action}，数量={order_size} "
                        f"{_format_price_compare()}"
                    )
                    break

                pending_open = False
        elif signal_type == "close":
            try:
                ex1_pos = _get_ex1_position()
            except Exception as e:
                _log(f"平单跳过：读取 {ex1_key} 持仓失败，错误={e} {_format_price_compare()}")
                continue

            if ex1_pos == 0:
                pending_open = False
                _log(f"平单跳过：{ex1_key} {symbol} 无持仓 {_format_price_compare()}")
                with ORDER_LOCK:
                    has_orders = bool(ORDER_MAP.get(ex1_key, {}).get(symbol))
                if has_orders:
                    try:
                        ex1_adapter.cancel_all_orders(symbol=symbol)
                    except Exception as e:
                        _log(f"撤销失败：{ex1_key} {symbol}，错误={e}")
                continue

            close_side = "sell" if ex1_pos > 0 else "buy"
            close_action = "做空" if close_side == "sell" else "做多"
            close_qty = min(abs(ex1_pos), float(order_size))

            for attempt in range(1, max_retries + 1):
                price = _get_ex1_price(close_side)
                if price is None:
                    _log(f"平单失败：{ex1_key} 价格未就绪")
                    break
                if not _can_place_order():
                    time.sleep(poll_interval_sec)
                    continue
                existing_order = _find_open_order(close_side, False)
                if existing_order and _price_match(existing_order.get("price"), price):
                    client_order_id = existing_order.get("cl_ord_id")
                    _log(
                        f"挂单复用：平单{close_action} {ex1_key} {symbol}，"
                        f"价格={price}，数量={close_qty}"
                        f"{_format_price_compare()}"
                    )
                else:
                    if existing_order:
                        try:
                            ex1_adapter.cancel_all_orders(symbol=symbol)
                        except Exception as e:
                            _log(f"撤单失败：{ex1_key} {symbol}，错误={e}")
                    client_order_id = _make_client_order_id("arb_close", attempt)
                    if not _place_limit_order(close_side, close_qty, price, True, client_order_id):
                        continue
                    _log(
                        f"挂单信号：平单{close_action} {ex1_key} {symbol}，"
                        f"价格={price}，数量={close_qty}"
                        f"重试={attempt}/{max_retries} {_format_price_compare()}"
                    )

                if _wait_for_position_change(ex1_pos):
                    pending_open = False
                    _log(
                        f"平单信号：{ex1_key} {symbol} 成交，"
                        f"方向={close_action}，数量={close_qty} "
                        f"{_format_price_compare()}"
                    )
                    break

        elif signal_type == "cancel":
            _log(
                f"信号：撤销 {ex1_key} {symbol} 未成交限价单，"
                f" {_format_price_compare()}"
            )
            with ORDER_LOCK:
                has_orders = bool(ORDER_MAP.get(ex1_key, {}).get(symbol))
            if has_orders:
                try:
                    ex1_adapter.cancel_all_orders(symbol=symbol)
                except Exception as e:
                    _log(f"撤销失败：{ex1_key} {symbol}，错误={e}")
            pending_open = False


def main():
    parser = argparse.ArgumentParser(description="Arbitrage runner")
    parser.add_argument(
        "-c",
        "--config",
        default="arbitrage_config.yaml",
        help="配置文件路径（默认: arbitrage_config.yaml）",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    exchanges_cfg = config["exchanges"]
    arbitrage_cfg = config["arbitrage"]

    ARB_SETTINGS["position_threshold"] = float(arbitrage_cfg.get("position_threshold", ARB_SETTINGS["position_threshold"]))
    ARB_SETTINGS["print_interval_sec"] = float(arbitrage_cfg.get("print_interval_sec", ARB_SETTINGS["print_interval_sec"]))
    ARB_SETTINGS["order_max_retries"] = int(arbitrage_cfg.get("order_max_retries", ARB_SETTINGS["order_max_retries"]))
    ARB_SETTINGS["order_timeout_sec"] = float(arbitrage_cfg.get("order_timeout_sec", ARB_SETTINGS["order_timeout_sec"]))
    ARB_SETTINGS["order_poll_interval_sec"] = float(arbitrage_cfg.get("order_poll_interval_sec", ARB_SETTINGS["order_poll_interval_sec"]))

    symbol = arbitrage_cfg["symbol"]
    ex1_name = arbitrage_cfg["ex1"]["exchange_name"]
    ex2_name = arbitrage_cfg["ex2"]["exchange_name"]

    if ex1_name not in exchanges_cfg or ex2_name not in exchanges_cfg:
        missing = [name for name in (ex1_name, ex2_name) if name not in exchanges_cfg]
        raise ValueError(f"arbitrage.ex1/ex2.exchange_name 不存在: {missing}")

    ex1_cfg = exchanges_cfg[ex1_name]
    ex2_cfg = exchanges_cfg[ex2_name]

    ex1_symbol = convert_symbol(symbol, ex1_cfg["exchange_name"])
    ex2_symbol = convert_symbol(symbol, ex2_cfg["exchange_name"])

    t1 = threading.Thread(
        target=_run_ws_thread,
        args=([(ex1_name, ex1_cfg, ex1_symbol), (ex2_name, ex2_cfg, ex2_symbol)],),
        daemon=True,
    )
    t2 = threading.Thread(
        target=_run_state_print_thread,
        args=(ARB_SETTINGS["print_interval_sec"],),
        daemon=True,
    )
    t3 = threading.Thread(
        target=_run_print_thread,
        args=(
            ex1_name,
            ex2_name,
            float(arbitrage_cfg.get("min_profit_pct", 0.0)),
            float(arbitrage_cfg.get("max_profit_pct", 0.0)),
            bool(arbitrage_cfg.get("use_dynamic_profit_window", False)),
            float(arbitrage_cfg.get("profit_buffer_pct", 0.0)),
            ARB_SETTINGS["print_interval_sec"],
        ),
        daemon=True,
    )
    t4 = threading.Thread(
        target=_run_signal_thread,
        args=(
            ex1_name,
            ex2_name,
            ex1_cfg,
            ex1_symbol,
            float(arbitrage_cfg.get("order_size", 0.0)),
            ARB_SETTINGS["order_max_retries"],
            ARB_SETTINGS["order_timeout_sec"],
            ARB_SETTINGS["order_poll_interval_sec"],
            float(arbitrage_cfg.get("max_position_size", 0.0)),
        ),
        daemon=True,
    )
    t5 = threading.Thread(
        target=_run_position_compare_thread,
        args=(
            ex1_name,
            ex2_name,
            ex1_symbol,
            ex2_symbol,
            ARB_SETTINGS["print_interval_sec"],
            ex2_cfg,
        ),
        daemon=True,
    )
    t6 = threading.Thread(
        target=_run_accounts_sync_thread,
        args=([(ex1_name, ex1_cfg, ex1_symbol), (ex2_name, ex2_cfg, ex2_symbol)],),
        daemon=True,
    )
    # 线程1:wss获取ex1/ex2价格和账户数据，并更新map
    t1.start()
    # 线程2:打印各类 map 状态
    # t2.start()
    # 线程3:监控套利机会
    t3.start()
    # # # 线程4:根据信号下单
    t4.start()
    # # 线程5:监控持仓对比，对冲仓位
    t5.start()
    # 线程6:定时同步ex1/ex2持仓、余额、订单
    t6.start()

    t1.join()
    # t2.join()
    t3.join()
    t4.join()
    t5.join()
    t6.join()

if __name__ == "__main__":
    main()