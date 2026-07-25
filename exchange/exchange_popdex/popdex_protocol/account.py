"""
PopDEX Account 预编译：Agent 授权

合约: 0x0000000000000000000000000000000000001008
文档: https://popdex.xyz/zh-CN/docs/smart-contract/Account
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from eth_abi import encode as abi_encode
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_utils import function_signature_to_4byte_selector, to_checksum_address

from .perps_auth import EIP712_DOMAINS, Network

ACCOUNT_PRECOMPILE = "0x0000000000000000000000000000000000001008"

APPROVE_AGENT_SIG = (
    "approveAgent(address,address,bytes32,uint64,uint64,bool)"
)


def name_to_bytes32(name: str = "") -> bytes:
    """空名称 / 'default' → bytes32(0)（每个委托人最多 1 个默认 Agent）。"""
    if not name or name.lower() in ("default", "0", "0x0"):
        return b"\x00" * 32
    raw = name.encode("utf-8")
    if len(raw) > 32:
        raise ValueError("Agent name 超过 32 字节")
    return raw + b"\x00" * (32 - len(raw))


def encode_approve_agent_calldata(
    *,
    agent: str,
    delegator: str,
    name: str = "dd-bot",
    expires_at_ms: int = 0,
    initial_nonce: Optional[int] = None,
    is_global: bool = True,
) -> Dict[str, Any]:
    """
    编码 approveAgent calldata。

    Args:
        agent: 新 Agent 地址
        delegator: 委托账户（通常等于主钱包地址）
        name: Agent 名称；空则用 bytes32(0)
        expires_at_ms: 过期时间（毫秒），0=永不过期
        initial_nonce: Agent 初始 timestamp nonce；默认当前毫秒时间
        is_global: True=主账户+全部子账户
    """
    if initial_nonce is None:
        initial_nonce = int(time.time() * 1000)

    name_b32 = name_to_bytes32(name)
    selector = function_signature_to_4byte_selector(APPROVE_AGENT_SIG)
    encoded = abi_encode(
        ["address", "address", "bytes32", "uint64", "uint64", "bool"],
        [
            to_checksum_address(agent),
            to_checksum_address(delegator),
            name_b32,
            int(expires_at_ms),
            int(initial_nonce),
            bool(is_global),
        ],
    )
    data = "0x" + (selector + encoded).hex()
    return {
        "to": ACCOUNT_PRECOMPILE,
        "data": data,
        "agent": to_checksum_address(agent),
        "delegator": to_checksum_address(delegator),
        "name": "0x" + name_b32.hex(),
        "expires_at_ms": int(expires_at_ms),
        "initial_nonce": int(initial_nonce),
        "is_global": bool(is_global),
    }


def build_wallet_tx(
    *,
    private_key: str,
    to: str,
    data: str,
    network: Network = "mainnet",
    nonce: int,
    gas: int = 1_000_000,
    chain_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    主钱包签署交易（严格递增 Wallet Nonce，非 Agent 时间戳 nonce）。
    """
    account: LocalAccount = Account.from_key(private_key)
    if chain_id is None:
        chain_id = int(EIP712_DOMAINS[network]["chainId"])

    tx = {
        "chainId": chain_id,
        "nonce": int(nonce),
        "to": to_checksum_address(to),
        "value": 0,
        "gas": gas,
        "gasPrice": 0,
        "data": data,
    }
    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    if isinstance(raw, (bytes, bytearray)):
        raw_hex = "0x" + raw.hex()
    else:
        raw_hex = raw if str(raw).startswith("0x") else "0x" + str(raw)

    tx_hash = getattr(signed, "hash", None)
    if isinstance(tx_hash, (bytes, bytearray)):
        tx_hash = "0x" + tx_hash.hex()

    return {
        "from": account.address,
        "nonce": int(nonce),
        "raw_transaction": raw_hex,
        "hash": tx_hash,
        "tx": tx,
    }


def generate_agent() -> Dict[str, str]:
    """生成新的 Trade Agent 密钥对。"""
    acct = Account.create()
    key = acct.key.hex()
    if not key.startswith("0x"):
        key = "0x" + key
    return {"address": acct.address, "private_key": key}
