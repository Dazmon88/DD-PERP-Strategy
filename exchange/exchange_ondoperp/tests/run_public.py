#!/usr/bin/env python3
"""Ondo Perps 公共接口冒烟测试。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ondoperp_protocol.perp_http import OndoPerpHTTP
from ondoperp_protocol.perps_wss import OndoPerpStream


def main() -> None:
    parser = argparse.ArgumentParser(description="Ondo public smoke test")
    parser.add_argument("--network", default="mainnet", choices=["mainnet", "sandbox"])
    parser.add_argument("--market", default="AAPL-USD.P")
    parser.add_argument("--ws", action="store_true", help="订阅 topOfBooks 几秒")
    parser.add_argument("--ws-seconds", type=float, default=5.0)
    args = parser.parse_args()

    http = OndoPerpHTTP(network=args.network, timeout=15.0)

    print("=" * 60)
    print(f"Ondo Perps 公共冒烟 ({args.network})")
    print("=" * 60)

    print("\n[1] hello")
    print(json.dumps(http.hello(), ensure_ascii=False)[:500])

    print("\n[2] status")
    print(json.dumps(http.get_status(), ensure_ascii=False)[:500])

    print("\n[3] markets (head)")
    markets = http.get_markets()
    print(json.dumps(markets, ensure_ascii=False)[:800])

    print(f"\n[4] contracts / mark / depth ({args.market})")
    try:
        print("contracts:", json.dumps(http.get_contracts(), ensure_ascii=False)[:600])
    except Exception as e:
        print("contracts 失败:", e)
    try:
        print("mark:", json.dumps(http.get_mark_prices(), ensure_ascii=False)[:600])
    except Exception as e:
        print("mark 失败:", e)
    try:
        print(
            "depth:",
            json.dumps(http.get_orderbook(args.market), ensure_ascii=False)[:600],
        )
    except Exception as e:
        print("depth 失败:", e)

    if args.ws:
        asyncio.run(_ws_smoke(args.network, args.market, args.ws_seconds))

    print("\n完成")


async def _ws_smoke(network: str, market: str, seconds: float) -> None:
    print(f"\n[5] WSS topOfBooksPerps ({seconds}s)")
    stream = OndoPerpStream(network=network)
    n = {"count": 0}

    def on_msg(msg):
        n["count"] += 1
        if n["count"] <= 3:
            print("  push:", json.dumps(msg, ensure_ascii=False)[:300])

    await stream.connect()
    await stream.subscribe_market(
        "topOfBooksPerps", markets=[market], callback=on_msg
    )
    await asyncio.sleep(seconds)
    await stream.close()
    print(f"  收到 {n['count']} 条消息")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
