"""
PopDEX Perps Authentication Module

PopDEX 使用 Agent Key（secp256k1）做程序化写操作签名，而非传统 API Key。
EIP-712 域见官方快速入门；具体 primaryType / message 以各写接口文档为准。
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address

Network = Literal["mainnet", "testnet"]

# 官方文档：主网 / 测试网 EIP-712 domain
EIP712_DOMAINS: Dict[str, Dict[str, Any]] = {
    "mainnet": {
        "name": "Morph Tachyon",
        "version": "1",
        "chainId": 2184,
        "verifyingContract": "0x0000000000000000000000000000000000000000",
    },
    "testnet": {
        "name": "Morph Tachyon Testnet",
        "version": "1",
        "chainId": 34952,
        "verifyingContract": "0x0000000000000000000000000000000000000000",
    },
}

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class PopDEXAuth:
    """
    PopDEX Agent Key 认证 / 签名客户端。

    Agent Key 需先在网页端创建并由主钱包完成链上授权。
    本类负责持有密钥、生成 EIP-712 签名，以及拼装 eth_sendRawTransaction 所需材料。
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        network: Network = "mainnet",
        wallet_id: Optional[str] = None,
    ):
        """
        Args:
            private_key: Agent 私钥（hex，可带 0x）。为 None 时生成临时密钥（仅测试）。
            network: mainnet / testnet，决定 EIP-712 domain。
            wallet_id: 主账户（或子账户）钱包地址；私有 REST 路径需要。
        """
        if private_key:
            self._account: LocalAccount = Account.from_key(private_key)
        else:
            self._account = Account.create()

        self.network: Network = network
        self.wallet_id = (
            to_checksum_address(wallet_id) if wallet_id else None
        )

    @property
    def agent_address(self) -> str:
        """Agent Key 对应地址"""
        return self._account.address

    @property
    def private_key(self) -> str:
        """带 0x 前缀的私钥 hex"""
        return self._account.key.hex()

    @property
    def eip712_domain(self) -> Dict[str, Any]:
        return dict(EIP712_DOMAINS[self.network])

    def set_wallet_id(self, wallet_id: str) -> None:
        """设置主账户 / 子账户钱包地址"""
        self.wallet_id = to_checksum_address(wallet_id)

    def export_private_key(self) -> str:
        return self.private_key

    @classmethod
    def from_private_key(
        cls,
        private_key: str,
        network: Network = "mainnet",
        wallet_id: Optional[str] = None,
    ) -> "PopDEXAuth":
        return cls(private_key=private_key, network=network, wallet_id=wallet_id)

    def sign_message_hash(self, message_hash: Union[str, bytes]) -> str:
        """对任意 32 字节 hash 做 secp256k1 签名，返回 0x 签名串。"""
        if isinstance(message_hash, str):
            message_hash = bytes.fromhex(message_hash.removeprefix("0x"))
        signed = Account.unsafe_sign_hash(message_hash, private_key=self._account.key)
        return signed.signature.hex()

    def sign_typed_data(
        self,
        types: Dict[str, Any],
        primary_type: str,
        message: Dict[str, Any],
        domain: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        EIP-712 typed data 签名。

        Args:
            types: EIP-712 types（不含 EIP712Domain 时由 encode_typed_data 处理）
            primary_type: 主类型名（各写接口文档定义）
            message: 消息体
            domain: 可选，默认使用当前 network 的官方 domain

        Returns:
            dict: address / signature / message_hash / domain / primaryType / message
        """
        full_domain = domain or self.eip712_domain
        # eth_account encode_typed_data 需要完整结构
        typed = {
            "types": types,
            "primaryType": primary_type,
            "domain": full_domain,
            "message": message,
        }
        signable = encode_typed_data(full_message=typed)
        signed = self._account.sign_message(signable)
        mh = getattr(signed, "message_hash", None)
        if isinstance(mh, (bytes, bytearray)):
            message_hash = "0x" + mh.hex()
        elif mh is None:
            message_hash = None
        else:
            message_hash = mh if str(mh).startswith("0x") else "0x" + str(mh)
        sig = signed.signature
        sig_hex = sig.hex() if isinstance(sig, (bytes, bytearray)) else str(sig)
        if not sig_hex.startswith("0x"):
            sig_hex = "0x" + sig_hex
        return {
            "address": self.agent_address,
            "signature": sig_hex,
            "message_hash": message_hash,
            "domain": full_domain,
            "primaryType": primary_type,
            "message": message,
        }

    def sign_transaction(self, transaction: Dict[str, Any]) -> str:
        """
        签署原始交易，返回 rawTransaction hex（可提交 eth_sendRawTransaction）。

        Args:
            transaction: eth_account 可识别的交易字典（含 chainId / nonce / to / data 等）
        """
        tx = dict(transaction)
        if "chainId" not in tx:
            tx["chainId"] = self.eip712_domain["chainId"]
        signed = self._account.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        if isinstance(raw, (bytes, bytearray)):
            return "0x" + raw.hex()
        return raw if str(raw).startswith("0x") else "0x" + str(raw)
