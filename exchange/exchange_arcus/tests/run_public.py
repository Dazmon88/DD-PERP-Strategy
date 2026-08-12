"""
Arcus 公共接口冒烟测试

用法:
  cd exchange/exchange_arcus
  python tests/run_public.py
  python tests/run_public.py --network testnet
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from arcus_protocol.perp_http import ArcusPerpHTTP  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--network", default="testnet", choices=["mainnet", "testnet", "staging"])
    parser.add_argument("-m", "--market", default="BTC-USD")
    args = parser.parse_args()

    http = ArcusPerpHTTP(network=args.network)
    print("base_url:", http.base_url)

    try:
        print("health:", http.health())
    except Exception as e:
        print("health failed:", e)

    markets = http.get_markets()
    n = len(markets.get("markets", [])) if isinstance(markets, dict) else 0
    print(f"markets: {n}")

    meta = http.market_meta(market=args.market)
    print(
        f"market {args.market}: id={meta['marketId']} "
        f"tick={meta['tickSize']} step={meta['stepSize']}"
    )

    try:
        bbo = http.get_bbo(market=args.market)
        print("bbo:", bbo)
    except Exception as e:
        print("bbo failed:", e)

    try:
        book = http.get_l2_orderbook(market=args.market, levels=5)
        print("l2 keys:", list(book)[:8] if isinstance(book, dict) else type(book))
    except Exception as e:
        print("l2 failed:", e)


if __name__ == "__main__":
    main()
