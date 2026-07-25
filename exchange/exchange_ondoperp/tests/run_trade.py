#!/usr/bin/env python3
"""
Ondo Perps 下单冒烟。

默认 dry-run：只打印签名头与 body，不真实下单。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ondoperp_protocol.orders import build_place_order_body, make_client_order_id
from ondoperp_protocol.perp_http import OndoPerpHTTP
from ondoperp_protocol.perps_auth import OndoPerpAuth


def main() -> None:
    parser = argparse.ArgumentParser(description="Ondo place order smoke")
    parser.add_argument("--network", default=os.getenv("ONDO_NETWORK", "mainnet"),
                        choices=["mainnet", "sandbox"])
    parser.add_argument("--key-id", default=os.getenv("ONDO_KEY_ID", "").strip())
    parser.add_argument("--api-secret", default=os.getenv("ONDO_API_SECRET", "").strip())
    parser.add_argument("--market", default="AAPL-USD.P")
    parser.add_argument("--side", default="buy", choices=["buy", "sell"])
    parser.add_argument("--price", default="1")
    parser.add_argument("--size", default="0.01")
    parser.add_argument("--post-only", action="store_true", default=True)
    parser.add_argument("--no-post-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true", help="真实广播（关闭 dry-run）")
    args = parser.parse_args()

    dry_run = not args.live
    post_only = False if args.no_post_only else True

    if not args.key_id or not args.api_secret:
        raise SystemExit("请设置 ONDO_KEY_ID / ONDO_API_SECRET（或 --key-id / --api-secret）")

    auth = OndoPerpAuth(key_id=args.key_id, api_secret=args.api_secret, network=args.network)
    http = OndoPerpHTTP(network=args.network, auth=auth, timeout=20.0)

    print("=" * 60)
    print(f"Ondo Perps 下单脚本 ({args.network}) dry_run={dry_run}")
    print("=" * 60)

    print("\n[1] account")
    try:
        print(json.dumps(http.get_account(), ensure_ascii=False)[:800])
    except Exception as e:
        print(f"  失败: {e}")

    print("\n[2] balance")
    try:
        print(json.dumps(http.get_balance(), ensure_ascii=False)[:800])
    except Exception as e:
        print(f"  失败: {e}")

    cloid = make_client_order_id("dd")
    body = build_place_order_body(
        market=args.market,
        side=args.side,
        size=args.size,
        price=args.price,
        order_type="limit",
        time_in_force="GTC",
        post_only=post_only,
        client_order_id=cloid,
    )
    print("\n[3] place body")
    print(json.dumps(body, ensure_ascii=False, indent=2))

    path = "/v1/perps/orders"
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    headers = auth.rest_headers(method="POST", request_path=path, body=body_str)
    print("\n[4] auth headers (sign only)")
    print({k: (v[:16] + "...") if k == "ONDO-SIGN" else v for k, v in headers.items()})

    if dry_run:
        print("\n--dry-run：不广播。加 --live 真实下单。")
        return

    print("\n[5] live place_order")
    result = http.place_order(
        market=args.market,
        side=args.side,
        size=args.size,
        price=args.price,
        order_type="limit",
        time_in_force="GTC",
        post_only=post_only,
        client_order_id=cloid,
    )
    print(json.dumps(result, ensure_ascii=False)[:1200])

    print("\n[6] open orders")
    try:
        print(json.dumps(http.get_orders(market=args.market), ensure_ascii=False)[:1200])
    except Exception as e:
        print(f"  失败: {e}")

    print("\n完成")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
