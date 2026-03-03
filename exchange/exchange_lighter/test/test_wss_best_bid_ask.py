import asyncio
import os
import sys
from contextlib import suppress

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from adapters.lighter_adapter import LighterAdapter
import lighter


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("-", "").replace("_", "").upper()


async def _get_market_id(symbol: str, base_url: str) -> tuple[int, list[str]]:
    api_client = lighter.ApiClient(configuration=lighter.Configuration(host=base_url))
    order_api = lighter.OrderApi(api_client)
    try:
        details = await order_api.order_books(filter="perp")
        target = _normalize_symbol(symbol)
        fallback_target = target
        if "-" in symbol or "_" in symbol:
            fallback_target = _normalize_symbol(symbol.split("-")[0].split("_")[0])
        symbols = []
        for market in details.order_books or []:
            symbols.append(market.symbol)
            normalized = _normalize_symbol(market.symbol)
            if normalized == target or normalized == fallback_target:
                return int(market.market_id), symbols
        return -1, symbols
    finally:
        await api_client.close()


async def _run_wss_best_bid_ask(symbol: str, timeout_sec: int = 15, use_pytest: bool = True):
    adapter = LighterAdapter(
        {
            "exchange_name": "lighter",
            "account_index": 1,
        }
    )

    market_id, symbols = await _get_market_id(symbol, adapter.base_url)
    if market_id < 0:
        msg = f"symbol not found: {symbol}. Available symbols: {symbols}"
        if use_pytest:
            pytest.skip(msg)
        else:
            print(msg)
            await adapter.api_client.close()
            return

    def on_order_book_update(_, order_book):
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        if not bids or not asks:
            return
        best_bid = max(float(item["price"]) for item in bids)
        best_ask = min(float(item["price"]) for item in asks)
        print(f"best_bid={best_bid} best_ask={best_ask}")

    ws_client = await adapter.connect_ws(
        order_book_ids=[market_id],
        on_order_book_update=on_order_book_update,
    )

    task = asyncio.create_task(adapter.run_ws(ws_client))
    try:
        await task
    finally:
        if ws_client.ws:
            await ws_client.ws.close()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await adapter.api_client.close()

if __name__ == "__main__":
    symbol = os.getenv("LIGHTER_WSS_SYMBOL", "BTC")
    asyncio.run(_run_wss_best_bid_ask(symbol, use_pytest=False))
