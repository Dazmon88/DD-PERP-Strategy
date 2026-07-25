#!/usr/bin/env python3
"""
PopDEX 挂单测试脚本

默认：BTCUSDT 限价买单，价格 60000，数量 0.001

确认方式：先订 WSS order 频道，再广播，用推送里的 clientOid 确认受理。

用法:
  export POPDEX_WALLET_ID=0x你的主账户地址
  export POPDEX_AGENT_KEY=0x已授权的Agent私钥

  cd exchange/exchange_popdex/tests
  python run_trade.py
  python run_trade.py --dry-run
  python run_trade.py --side sell --price 60000 --qty 0.001
  python run_trade.py --receipt   # WSS 超时后再查链上回执
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eth_account import Account

from popdex_protocol.orders import build_agent_tx, encode_place_order_calldata
from popdex_protocol.perp_http import PopDEXPerpHTTP
from popdex_protocol.perps_wss import PopDEXAccountStream


def _unwrap(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def client_oid_text(client_order_id: str) -> str:
    """bytes32 hex → 链上/推送用的 UTF-8 clientOid 文本。"""
    s = client_order_id.strip()
    raw = bytes.fromhex(s[2:] if s.startswith("0x") else s)
    return raw.rstrip(b"\x00").decode("utf-8")


def _order_client_oid(order: Dict[str, Any]) -> str:
    for key in ("clientOid", "clientOrderId", "client_oid", "client_order_id"):
        val = order.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _iter_order_payloads(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = msg.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        # 偶发包一层 order / orders
        if isinstance(data.get("orders"), list):
            return [x for x in data["orders"] if isinstance(x, dict)]
        return [data]
    return []


def assert_agent_ready(http: PopDEXPerpHTTP, agent_key: str, wallet_id: str) -> str:
    """确认 Agent 已链上授权；未授权时给出明确指引。"""
    agent_addr = Account.from_key(agent_key).address
    info = _unwrap(http.query_agent(agent_addr))
    exists = bool(isinstance(info, dict) and info.get("exists"))
    if not exists:
        raise SystemExit(
            f"Agent {agent_addr} 尚未链上授权（exists=false）。\n"
            "原因：该地址还没有 Core account，无法 eth_sendRawTransaction。\n"
            "处理：用主钱包私钥跑 create_agent.py（不要 --dry-run），然后用脚本打印的 "
            "POPDEX_AGENT_KEY 重新下单。\n"
            f"  cd exchange/exchange_popdex/tests\n"
            f'  export POPDEX_WALLET_KEY="0x主钱包私钥"\n'
            f"  python create_agent.py --save ./agent.key\n"
            f"  # 确认输出里 agent_info.exists=true 后再:\n"
            f'  export POPDEX_WALLET_ID="{wallet_id}"\n'
            f'  export POPDEX_AGENT_KEY="$(python -c \'import json;print(json.load(open(\"agent.key\"))[\"agent_private_key\"])\')"\n'
            f"  python run_trade.py"
        )
    delegator = (info.get("delegator") or "").lower() if isinstance(info, dict) else ""
    if delegator and wallet_id and delegator != wallet_id.lower():
        print(
            f"  警告: Agent.delegator={info.get('delegator')} "
            f"与 POPDEX_WALLET_ID={wallet_id} 不一致"
        )
    if isinstance(info, dict) and info.get("isExpired"):
        raise SystemExit(f"Agent {agent_addr} 已过期，请重新 create_agent.py 授权")
    return agent_addr


def resolve_symbol_id(http: PopDEXPerpHTTP, category: str, symbol: str) -> int:
    raw = _unwrap(http.get_symbol(category=category, symbol=symbol))
    if isinstance(raw, dict) and raw.get("symbolId") is not None:
        return int(raw["symbolId"])
    tickers = _unwrap(http.get_tickers(category=category, symbol=symbol, limit=1))
    item = tickers[0] if isinstance(tickers, list) and tickers else tickers
    if isinstance(item, dict) and item.get("symbolId") is not None:
        return int(item["symbolId"])
    raise ValueError(f"无法解析 {symbol} 的 symbolId")


def wait_receipt(
    http: PopDEXPerpHTTP,
    tx_hash: str,
    *,
    timeout: float = 3.0,
    interval: float = 0.15,
) -> tuple[Any, Any]:
    """短间隔轮询回执（WSS 超时后的可选诊断）。"""
    deadline = time.time() + max(timeout, 0)
    last_receipt: Any = None
    last_err: Exception | None = None
    while True:
        try:
            last_receipt = http.get_transaction_receipt(tx_hash)
            result = (
                last_receipt.get("result")
                if isinstance(last_receipt, dict)
                else last_receipt
            )
            if isinstance(result, dict) and result.get("status") is not None:
                return last_receipt, result.get("status")
        except Exception as e:
            last_err = e
        if time.time() >= deadline:
            if last_receipt is not None:
                result = (
                    last_receipt.get("result")
                    if isinstance(last_receipt, dict)
                    else last_receipt
                )
                status = result.get("status") if isinstance(result, dict) else None
                return last_receipt, status
            if last_err is not None:
                raise last_err
            return None, None
        time.sleep(interval)


async def place_and_confirm_via_wss(
    *,
    http: PopDEXPerpHTTP,
    network: str,
    wallet_id: str,
    agent_key: str,
    symbol_id: int,
    encoded: Dict[str, Any],
    side: str,
    price: str,
    qty: str,
    tif: str,
    category: str,
    reduce_only: bool,
    wait: float,
    use_receipt_fallback: bool,
) -> None:
    expect_oid = client_oid_text(encoded["client_order_id"])
    expect_oid_l = expect_oid.lower()
    matched: asyncio.Event = asyncio.Event()
    found: Dict[str, Any] = {"order": None, "raw": None}
    subscribed = asyncio.Event()

    def on_order(msg: Dict[str, Any]) -> None:
        if msg.get("event") == "subscribe":
            subscribed.set()
            return
        for order in _iter_order_payloads(msg):
            oid = _order_client_oid(order)
            if oid.lower() == expect_oid_l or oid.lower() == encoded["client_order_id"].lower():
                found["order"] = order
                found["raw"] = msg
                matched.set()
                return

    stream = PopDEXAccountStream(network=network)
    print("\n[5] 订阅 WSS order")
    await stream.connect()
    # 同时挂 event=subscribe 确认与 order 推送
    stream.callbacks["subscribe"] = on_order
    await stream.subscribe_account(wallet_id, "order", callback=on_order)
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=2.0)
        print("  订阅确认 ok")
    except asyncio.TimeoutError:
        print("  未收到 subscribe ack，继续广播（仍监听推送）")

    print(f"\n[6] 广播限价单 {side} {qty} @ {price}")
    print(f"  expect clientOid={expect_oid}")
    t0 = time.time()
    result = await asyncio.to_thread(
        http.place_order_onchain,
        wallet_id=wallet_id,
        agent_private_key=agent_key,
        symbol_id=symbol_id,
        price=price,
        qty=qty,
        side=side,
        order_type="limit",
        time_in_force=tif,
        category=category,
        reduce_only=reduce_only,
        client_order_id=encoded["client_order_id"],
        network=network,
    )
    print(f"  agent={result['signed']['from']}")
    print(f"  nonce={result['signed']['nonce']}")
    print(f"  local_hash={result['signed']['hash']}")
    print(f"  rpc={json.dumps(result['rpc'], ensure_ascii=False)}")

    tx_hash = None
    rpc = result.get("rpc") or {}
    if isinstance(rpc, dict):
        tx_hash = rpc.get("result")

    if wait <= 0:
        print("\n[7] --wait 0：跳过 WSS 确认")
        print(f"  tx_hash={tx_hash}")
        await stream.close()
        return

    print(f"\n[7] 等待 WSS order 推送（最长 {wait}s）...")
    try:
        await asyncio.wait_for(matched.wait(), timeout=wait)
        elapsed = time.time() - t0
        order = found["order"] or {}
        print(f"  确认成功 耗时 {elapsed:.2f}s")
        print(
            f"  orderId={order.get('orderId')} status={order.get('status')} "
            f"clientOid={_order_client_oid(order)}"
        )
        print(json.dumps(order, ensure_ascii=False)[:1000])
    except asyncio.TimeoutError:
        elapsed = time.time() - t0
        print(f"  WSS 超时（{elapsed:.2f}s），未匹配到 clientOid={expect_oid}")
        if use_receipt_fallback and tx_hash:
            print("\n[7b] 回退查询链上回执...")
            try:
                receipt, status = await asyncio.to_thread(
                    wait_receipt, http, tx_hash, timeout=min(wait, 3.0) or 3.0
                )
                print(json.dumps(receipt, ensure_ascii=False)[:1000])
                if status in ("0x0", 0, "0"):
                    fail = await asyncio.to_thread(http.get_transaction_failure, tx_hash)
                    print("  failure:", json.dumps(fail, ensure_ascii=False)[:1200])
            except Exception as e:
                print(f"  回执查询失败: {e}")
    finally:
        await stream.close()

    try:
        opens = _unwrap(http.query_open_orders(wallet_id))
        print("\n[8] 当前委托")
        print(json.dumps(opens, ensure_ascii=False)[:1200])
    except Exception as e:
        print(f"  委托查询失败: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PopDEX place limit order")
    parser.add_argument("--network", default=os.getenv("POPDEX_NETWORK", "mainnet"),
                        choices=["mainnet", "testnet"])
    parser.add_argument("--wallet-id", default=os.getenv("POPDEX_WALLET_ID", "").strip())
    parser.add_argument("--agent-key", default=os.getenv("POPDEX_AGENT_KEY", "").strip(),
                        help="已链上授权的 Trade Agent 私钥")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--category", default="Futures")
    parser.add_argument("--side", default="buy", choices=["buy", "sell"])
    parser.add_argument("--price", default="60000")
    parser.add_argument("--qty", default="0.001")
    parser.add_argument("--tif", default="gtc", choices=["gtc", "ioc", "fok", "postonly", "default"])
    parser.add_argument("--reduce-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="只编码/查询，不广播")
    parser.add_argument(
        "--wait",
        type=float,
        default=5.0,
        help="等待 WSS order 推送的最长秒数（默认 5；0=不等待）",
    )
    parser.add_argument(
        "--receipt",
        action="store_true",
        help="WSS 超时时回退查询 eth 回执 / failure",
    )
    args = parser.parse_args()

    if not args.wallet_id:
        raise SystemExit("请通过 --wallet-id 或环境变量 POPDEX_WALLET_ID 提供主账户地址")
    if not args.agent_key and not args.dry_run:
        raise SystemExit("请通过 --agent-key 或环境变量 POPDEX_AGENT_KEY 提供 Agent 私钥")

    http = PopDEXPerpHTTP(network=args.network, timeout=15.0)

    print("=" * 60)
    print(f"PopDEX 挂单脚本 ({args.network})")
    print("=" * 60)

    print("\n[1] 服务器时间")
    print(json.dumps(http.get_server_time(), ensure_ascii=False))

    print("\n[2] 解析交易对")
    symbol_id = resolve_symbol_id(http, args.category, args.symbol)
    print(f"  {args.symbol} symbolId={symbol_id}")

    print("\n[3] 账户概览")
    try:
        overview = _unwrap(http.query_overview(args.wallet_id))
        if isinstance(overview, dict):
            print(
                f"  equity={overview.get('accountEquity')} "
                f"available={overview.get('availableMargin')}"
            )
        else:
            print(overview)
    except Exception as e:
        print(f"  查询失败（可继续）: {e}")

    if args.agent_key:
        print("\n[3.5] 校验 Agent 授权")
        agent_addr = assert_agent_ready(http, args.agent_key, args.wallet_id)
        info = _unwrap(http.query_agent(agent_addr))
        print(
            f"  agent={agent_addr} exists={info.get('exists')} "
            f"delegator={info.get('delegator')} expired={info.get('isExpired')}"
        )

    print("\n[4] 编码 placeOrder")
    encoded = encode_place_order_calldata(
        account=args.wallet_id,
        symbol_id=symbol_id,
        price=args.price,
        qty=args.qty,
        side=args.side,
        order_type="limit",
        time_in_force=args.tif,
        category=args.category,
        reduce_only=args.reduce_only,
    )
    print(f"  to={encoded['to']}")
    print(f"  client_order_id={encoded['client_order_id']}")
    print(f"  clientOid={client_oid_text(encoded['client_order_id'])}")
    print(f"  order_params={encoded['order_params']}")
    print(f"  price_x18={encoded['price_x18']} qty_x18={encoded['qty_x18']}")
    print(f"  data={encoded['data'][:66]}...")

    if args.dry_run:
        print("\n--dry-run：不广播交易")
        if args.agent_key:
            signed = build_agent_tx(
                private_key=args.agent_key,
                to=encoded["to"],
                data=encoded["data"],
                network=args.network,
            )
            print(f"  agent={signed['from']} nonce={signed['nonce']}")
            print(f"  tx_hash(local)={signed['hash']}")
        print("\n完成")
        return

    asyncio.run(
        place_and_confirm_via_wss(
            http=http,
            network=args.network,
            wallet_id=args.wallet_id,
            agent_key=args.agent_key,
            symbol_id=symbol_id,
            encoded=encoded,
            side=args.side,
            price=args.price,
            qty=args.qty,
            tif=args.tif,
            category=args.category,
            reduce_only=args.reduce_only,
            wait=args.wait,
            use_receipt_fallback=args.receipt,
        )
    )

    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
