#!/usr/bin/env python3
"""
生成 PopDEX Trade Agent，并用主钱包调用 approveAgent 授权。

用法:
  export POPDEX_WALLET_KEY=0x你的主钱包私钥

  cd exchange/exchange_popdex/tests
  python create_agent.py --dry-run
  python create_agent.py
  python create_agent.py --name dd-bot --save ./agent.key

授权成功后，把输出的 Agent 私钥配到:
  POPDEX_AGENT_KEY=...
  POPDEX_WALLET_ID=<主钱包地址>
再运行 run_trade.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eth_account import Account

from popdex_protocol.account import (
    ACCOUNT_PRECOMPILE,
    encode_approve_agent_calldata,
    build_wallet_tx,
    generate_agent,
)
from popdex_protocol.perp_http import PopDEXPerpHTTP


def _unwrap(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def get_wallet_nonce(http: PopDEXPerpHTTP, address: str) -> int:
    result = http.web3_rpc("eth_getTransactionCount", params=[address, "pending"])
    if isinstance(result, dict) and result.get("result") is not None:
        return int(result["result"], 16)
    raise ValueError(f"无法获取钱包 nonce: {result}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create & approve PopDEX Trade Agent")
    parser.add_argument("--network", default=os.getenv("POPDEX_NETWORK", "mainnet"),
                        choices=["mainnet", "testnet"])
    parser.add_argument(
        "--wallet-key",
        default=os.getenv("POPDEX_WALLET_KEY", "").strip(),
        help="主钱包私钥（用于签署 approveAgent，不是 Agent 私钥）",
    )
    parser.add_argument("--name", default="dd-bot", help="Agent 名称（bytes32），default=空名称")
    parser.add_argument(
        "--expires-days",
        type=int,
        default=0,
        help="过期天数，0=永不过期",
    )
    parser.add_argument("--no-global", action="store_true", help="仅授权当前主账户，不含全部子账户")
    parser.add_argument("--dry-run", action="store_true", help="只生成密钥并编码，不广播")
    parser.add_argument("--wait", type=float, default=3.0)
    parser.add_argument("--save", default="", help="把 Agent 私钥写入文件（小心保管）")
    args = parser.parse_args()

    if not args.wallet_key:
        raise SystemExit(
            "请通过 --wallet-key 或环境变量 POPDEX_WALLET_KEY 提供【主钱包】私钥"
        )

    wallet = Account.from_key(args.wallet_key)
    wallet_id = wallet.address
    http = PopDEXPerpHTTP(network=args.network, timeout=20.0)

    print("=" * 60)
    print(f"PopDEX 创建 Trade Agent ({args.network})")
    print("=" * 60)
    print(f"\n主钱包地址 (WALLET_ID): {wallet_id}")
    print(f"Account 预编译: {ACCOUNT_PRECOMPILE}")

    print("\n[1] 生成新 Agent 密钥对")
    agent = generate_agent()
    print(f"  Agent 地址: {agent['address']}")
    print(f"  Agent 私钥: {agent['private_key']}")
    print("  ⚠️  请立即保存 Agent 私钥；丢失无法找回，泄露请立刻 revokeAgent")

    expires_at = 0
    if args.expires_days > 0:
        expires_at = int((time.time() + args.expires_days * 86400) * 1000)

    print("\n[2] 编码 approveAgent")
    encoded = encode_approve_agent_calldata(
        agent=agent["address"],
        delegator=wallet_id,
        name=args.name,
        expires_at_ms=expires_at,
        is_global=not args.no_global,
    )
    print(f"  delegator={encoded['delegator']}")
    print(f"  name={encoded['name']}")
    print(f"  expires_at_ms={encoded['expires_at_ms']}")
    print(f"  initial_nonce={encoded['initial_nonce']}")
    print(f"  is_global={encoded['is_global']}")
    print(f"  data={encoded['data'][:74]}...")

    if args.save:
        path = os.path.abspath(args.save)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "network": args.network,
                        "wallet_id": wallet_id,
                        "agent_address": agent["address"],
                        "agent_private_key": agent["private_key"],
                        "name": args.name,
                    },
                    indent=2,
                )
                + "\n"
            )
        os.chmod(path, 0o600)
        print(f"\n已写入 {path} (chmod 600)")

    if args.dry_run:
        print("\n--dry-run：不广播授权交易")
        print("\n完成后请配置:")
        print(f'  export POPDEX_WALLET_ID="{wallet_id}"')
        print(f'  export POPDEX_AGENT_KEY="{agent["private_key"]}"')
        print("\n完成")
        return

    print("\n[3] 读取主钱包 nonce 并广播")
    nonce = get_wallet_nonce(http, wallet_id)
    print(f"  wallet_nonce={nonce}")
    signed = build_wallet_tx(
        private_key=args.wallet_key,
        to=encoded["to"],
        data=encoded["data"],
        network=args.network,
        nonce=nonce,
    )
    rpc = http.send_raw_transaction(signed["raw_transaction"])
    print(f"  local_hash={signed['hash']}")
    print(f"  rpc={json.dumps(rpc, ensure_ascii=False)}")

    tx_hash = rpc.get("result") if isinstance(rpc, dict) else None
    if tx_hash and args.wait > 0:
        print(f"\n[4] 等待回执 {args.wait}s ...")
        time.sleep(args.wait)
        try:
            receipt = http.get_transaction_receipt(tx_hash)
            print(json.dumps(receipt, ensure_ascii=False)[:1200])
        except Exception as e:
            print(f"  回执查询失败: {e}")
        try:
            fail = http.get_transaction_failure(tx_hash)
            print("  failure:", fail)
        except Exception:
            pass

    print("\n[5] 校验 Agent 列表 / 信息")
    try:
        agents = _unwrap(http.query_agents(wallet_id))
        print("  agents:", json.dumps(agents, ensure_ascii=False)[:1000])
    except Exception as e:
        print(f"  query_agents 失败: {e}")
    try:
        info = _unwrap(http.query_agent(agent["address"]))
        print("  agent_info:", json.dumps(info, ensure_ascii=False)[:800])
    except Exception as e:
        print(f"  query_agent 失败: {e}")

    print("\n" + "=" * 60)
    print("授权流程结束。请保存并配置:")
    print(f'  export POPDEX_WALLET_ID="{wallet_id}"')
    print(f'  export POPDEX_AGENT_KEY="{agent["private_key"]}"')
    print("然后运行: python run_trade.py")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
