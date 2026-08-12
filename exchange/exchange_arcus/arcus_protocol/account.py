"""
Arcus 账户辅助：生成 / 注册 / 撤销 API Key

注册走 REST POST /v1/createApiKey，需主钱包 EIP-712 签名。
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_account.signers.local import LocalAccount

from .perps_auth import (
    CREATE_API_KEY_TYPES,
    EIP712_CREATE_API_KEY_DOMAINS,
    ArcusAuth,
    Network,
)

if TYPE_CHECKING:
    from .perp_http import ArcusPerpHTTP


def generate_api_key_pair(*, network: Network = "mainnet") -> Dict[str, str]:
    """生成新的 Ed25519 API Key 对（尚未注册）。"""
    auth = ArcusAuth.generate(network=network)
    return {
        "api_key": auth.api_key,
        "private_key": auth.private_key_hex,
    }


def build_create_api_key_typed_data(
    *,
    public_key: str,
    api_wallet_name: str = "dd-bot",
    valid_until_ms: Optional[int] = None,
    network: Network = "mainnet",
) -> Dict[str, Any]:
    """构造 CreateApiKey EIP-712 full_message。"""
    pub = (public_key or "").removeprefix("0x")
    if len(pub) != 64:
        raise ValueError("publicKey 须为 64 hex chars")
    if valid_until_ms is None:
        # 默认约 90 天；官方要求落在 [now+1d, now+180d]
        valid_until_ms = int(time.time() * 1000) + 90 * 86_400_000
    domain = dict(EIP712_CREATE_API_KEY_DOMAINS[network])
    message = {
        "apiWalletName": api_wallet_name,
        "apiWalletPublicKey": pub,
        "validUntil": int(valid_until_ms),
    }
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            **CREATE_API_KEY_TYPES,
        },
        "primaryType": "CreateApiKey",
        "domain": domain,
        "message": message,
    }


def sign_create_api_key(
    wallet_private_key: str,
    *,
    public_key: str,
    api_wallet_name: str = "dd-bot",
    valid_until_ms: Optional[int] = None,
    network: Network = "mainnet",
) -> Dict[str, Any]:
    """
    用主钱包签署 CreateApiKey，返回请求体字段（含 r/s/v）。
    """
    account: LocalAccount = Account.from_key(wallet_private_key)
    typed = build_create_api_key_typed_data(
        public_key=public_key,
        api_wallet_name=api_wallet_name,
        valid_until_ms=valid_until_ms,
        network=network,
    )
    signed = account.sign_message(encode_typed_data(full_message=typed))
    sig = signed.signature
    if isinstance(sig, (bytes, bytearray)):
        sig_hex = sig.hex()
    else:
        sig_hex = str(sig)
    if sig_hex.startswith("0x"):
        sig_hex = sig_hex[2:]
    if len(sig_hex) != 130:
        raise ValueError(f"意外的签名长度: {len(sig_hex)}")
    r = "0x" + sig_hex[0:64]
    s = "0x" + sig_hex[64:128]
    v = "0x" + sig_hex[128:130]
    msg = typed["message"]
    return {
        "address": account.address,
        "publicKey": (public_key or "").removeprefix("0x"),
        "apiWalletName": msg["apiWalletName"],
        "validUntil": int(msg["validUntil"]),
        "signature": {"r": r, "s": s, "v": v},
        "typed_data": typed,
    }


def create_api_key(
    http: "ArcusPerpHTTP",
    *,
    wallet_private_key: str,
    api_private_key: Optional[str] = None,
    api_wallet_name: str = "dd-bot",
    valid_until_ms: Optional[int] = None,
    wait_ready: bool = True,
    wait_timeout_sec: float = 60.0,
) -> Dict[str, Any]:
    """
    生成（或复用）Ed25519 密钥、主钱包 EIP-712 签名并注册。

    Returns:
        api_key / private_key / address / accountIndex / raw response
    """
    import time as _time

    network = http.network  # type: ignore[attr-defined]
    if api_private_key:
        auth = ArcusAuth.from_private_key(api_private_key, network=network)  # type: ignore[arg-type]
    else:
        auth = ArcusAuth.generate(network=network)  # type: ignore[arg-type]

    body = sign_create_api_key(
        wallet_private_key,
        public_key=auth.api_key,
        api_wallet_name=api_wallet_name,
        valid_until_ms=valid_until_ms,
        network=network,  # type: ignore[arg-type]
    )
    # typed_data 仅本地用
    req = {
        "address": body["address"],
        "publicKey": body["publicKey"],
        "apiWalletName": body["apiWalletName"],
        "validUntil": body["validUntil"],
        "signature": body["signature"],
    }
    created = http.create_api_key(req)
    account_index = 0
    if isinstance(created, dict):
        account_index = int(created.get("accountIndex") or 0)

    if wait_ready:
        deadline = _time.time() + wait_timeout_sec
        while _time.time() < deadline:
            try:
                keys = http.get_api_keys(address=body["address"])
                items = keys.get("apiKeys", keys) if isinstance(keys, dict) else keys
                if isinstance(items, list) and any(
                    str(k.get("apiKey", "")).lower() == auth.api_key.lower()
                    for k in items
                    if isinstance(k, dict)
                ):
                    break
            except Exception:
                pass
            _time.sleep(1.0)

    return {
        "api_key": auth.api_key,
        "private_key": auth.private_key_hex,
        "address": body["address"],
        "accountIndex": account_index,
        "response": created,
    }
