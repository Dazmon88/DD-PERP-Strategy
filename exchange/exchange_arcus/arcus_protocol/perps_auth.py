"""
Arcus Perps Authentication Module

- API Key = 本地生成的 Ed25519 公钥（64 hex）
- 写操作：Ed25519 签名（Scheme 1 typed payload / Scheme 2 legacy message）
- 注册 API Key：主钱包 EIP-712（CreateApiKey）
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Literal, Optional, Union

from cryptography.hazmat.primitives.asymmetric import ed25519

Network = Literal["mainnet", "testnet", "staging"]

# createApiKey EIP-712 domain（无 verifyingContract）
EIP712_CREATE_API_KEY_DOMAINS: Dict[str, Dict[str, Any]] = {
    "mainnet": {
        "name": "Arcus API Key",
        "version": "1",
        "chainId": 4663,
    },
    "testnet": {
        "name": "Arcus API Key",
        "version": "1",
        "chainId": 46630,
    },
    "staging": {
        "name": "Arcus API Key",
        "version": "1",
        "chainId": 421614,
    },
}

CREATE_API_KEY_TYPES = {
    "CreateApiKey": [
        {"name": "apiWalletName", "type": "string"},
        {"name": "apiWalletPublicKey", "type": "string"},
        {"name": "validUntil", "type": "uint256"},
    ],
}


def canonical_json(obj: Any) -> str:
    """无空格、按 key 排序的 JSON（Scheme 2 / legacy EIP-191）。"""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def timestamp_ns() -> int:
    return time.time_ns()


class ArcusAuth:
    """
    Arcus Ed25519 API Key 认证客户端。

    Args:
        private_key: Ed25519 私钥（32 字节 hex，可带 0x；或 cryptography 可识别的 raw）
        address: 主钱包 Ethereum 地址（写操作 / 账户查询需要）
        account_index: 子账户索引，默认 0
        network: mainnet / testnet / staging
    """

    def __init__(
        self,
        *,
        private_key: Optional[str] = None,
        address: Optional[str] = None,
        account_index: int = 0,
        network: Network = "mainnet",
    ):
        if private_key:
            raw = _parse_ed25519_private_key(private_key)
            self._private = ed25519.Ed25519PrivateKey.from_private_bytes(raw)
        else:
            self._private = ed25519.Ed25519PrivateKey.generate()

        self.network: Network = network
        self.address = _normalize_address(address) if address else None
        self.account_index = int(account_index)

    @classmethod
    def from_private_key(
        cls,
        private_key: str,
        *,
        address: Optional[str] = None,
        account_index: int = 0,
        network: Network = "mainnet",
    ) -> "ArcusAuth":
        return cls(
            private_key=private_key,
            address=address,
            account_index=account_index,
            network=network,
        )

    @classmethod
    def generate(
        cls,
        *,
        address: Optional[str] = None,
        account_index: int = 0,
        network: Network = "mainnet",
    ) -> "ArcusAuth":
        return cls(
            address=address,
            account_index=account_index,
            network=network,
        )

    @property
    def api_key(self) -> str:
        """Ed25519 公钥 hex（64 chars，无 0x）——即 X-API-Key。"""
        return self._private.public_key().public_bytes_raw().hex()

    @property
    def private_key_hex(self) -> str:
        return "0x" + self._private.private_bytes_raw().hex()

    @property
    def has_key(self) -> bool:
        return True

    def set_address(self, address: str) -> None:
        self.address = _normalize_address(address)

    def set_account_index(self, account_index: int) -> None:
        self.account_index = int(account_index)

    def sign_bytes(self, message: Union[str, bytes]) -> str:
        """Ed25519 签名，返回 128 hex（小写，无 0x）。"""
        if isinstance(message, str):
            message = message.encode("utf-8")
        return self._private.sign(message).hex()

    def sign_typed_payload(self, payload: str) -> str:
        """Scheme 1：直接对 typed canonical payload 字符串签名。"""
        return self.sign_bytes(payload)

    def sign_legacy_action(
        self,
        *,
        action: str,
        body: Any,
        timestamp: Optional[Union[int, str]] = None,
    ) -> Dict[str, str]:
        """
        Scheme 2：ed25519(timestamp + action + canonical_json(body))

        用于 cancelAllOrders / setLeverage / WS authenticate。
        """
        ts = str(timestamp if timestamp is not None else timestamp_ns())
        msg = f"{ts}{action}{canonical_json(body)}"
        return {
            "timestamp": ts,
            "signature": self.sign_bytes(msg),
            "apiKey": self.api_key,
        }

    def api_key_headers(self) -> Dict[str, str]:
        """只读接口：仅需 X-API-Key。"""
        return {"X-API-Key": self.api_key}

    def signed_headers(
        self,
        *,
        signature: str,
        timestamp: Union[int, str],
        extra: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """写接口三件套：X-API-Key / X-Timestamp / X-Signature。"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.api_key,
            "X-Timestamp": str(timestamp),
            "X-Signature": signature,
        }
        if extra:
            headers.update(extra)
        return headers

    @property
    def create_api_key_domain(self) -> Dict[str, Any]:
        return dict(EIP712_CREATE_API_KEY_DOMAINS[self.network])


def _parse_ed25519_private_key(value: str) -> bytes:
    s = (value or "").strip()
    if s.startswith("0x"):
        s = s[2:]
    raw = bytes.fromhex(s)
    if len(raw) == 32:
        return raw
    if len(raw) == 64:
        # 部分工具导出 seed||pubkey
        return raw[:32]
    raise ValueError("Ed25519 私钥须为 32 字节 hex（或 64 字节 seed||pubkey）")


def _normalize_address(address: str) -> str:
    a = (address or "").strip()
    if not a:
        raise ValueError("address 不能为空")
    if not a.startswith("0x"):
        a = "0x" + a
    return a.lower()
