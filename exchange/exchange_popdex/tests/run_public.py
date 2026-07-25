#!/usr/bin/env python3
"""
PopDEX 公共接口冒烟脚本（无需私钥）

用法:
  cd exchange/exchange_popdex/tests
  python run_public.py
  python run_public.py --network testnet --symbol BTCUSDT
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from popdex_protocol.perp_http import PopDEXPerpHTTP
from popdex_protocol.perps_wss import PopDEXMarketStream


def main() -> None:
    parser = argparse.ArgumentParser(description="PopDEX public API smoke test")
    parser.add_argument("--network", default="mainnet", choices=["mainnet", "testnet"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--category", default="Futures")
    parser.add_argument("--ws", action="store_true", help="订阅 books1 几秒后退出")
    args = parser.parse_args()

    http = PopDEXPerpHTTP(network=args.network)
    print("=" * 60)
    print(f"PopDEX public smoke ({args.network})")
    print("=" * 60)

    print("\n[1] server time")
    print(json.dumps(http.get_server_time(), indent=2, ensure_ascii=False)[:500])

    print("\n[2] tickers")
    tickers = http.get_tickers(category=args.category, symbol=args.symbol, limit=5)
    print(json.dumps(tickers, indent=2, ensure_ascii=False)[:800])

    print("\n[3] orderbook")
    book = http.get_orderbook(category=args.category, symbol=args.symbol, levels=5)
    print(json.dumps(book, indent=2, ensure_ascii=False)[:800])

    if args.ws:
        asyncio.run(_ws_smoke(args.network, args.category, args.symbol))

    print("\n完成")


async def _ws_smoke(network: str, category: str, symbol: str) -> None:
    print("\n[4] websocket books1")
    stream = PopDEXMarketStream(network=network)
    await stream.connect()

    got = asyncio.Event()

    async def on_msg(msg):
        print("ws:", json.dumps(msg, ensure_ascii=False)[:400])
        got.set()

    await stream.subscribe_market(
        "books1", symbol, category=category, callback=on_msg
    )
    try:
        await asyncio.wait_for(got.wait(), timeout=15)
    except asyncio.TimeoutError:
        print("ws: 15s 内未收到深度推送")
    finally:
        await stream.close()


if __name__ == "__main__":
    main()
