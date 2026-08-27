"""
PopDEX 链上下单编解码

写操作通过 Order 预编译合约 placeOrder（非 REST）。
文档: https://popdex.xyz/zh-CN/docs/smart-contract/Order
合约地址: 0x0000000000000000000000000000000000001000
"""
from __future__ import annotations

import threading
import time
import uuid
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, Union

from eth_abi import encode as abi_encode
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_utils import function_signature_to_4byte_selector, to_checksum_address

from .perps_auth import EIP712_DOMAINS, Network

_nonce_lock = threading.Lock()
_last_agent_nonce = 0


def next_agent_nonce() -> int:
    """Agent 时间戳 nonce（毫秒）。同毫秒并发会撞 Invalid nonce，这里单调递增。"""
    global _last_agent_nonce
    with _nonce_lock:
        n = int(time.time() * 1000)
        if n <= _last_agent_nonce:
            n = _last_agent_nonce + 1
        _last_agent_nonce = n
        return n

ORDER_PRECOMPILE = "0x0000000000000000000000000000000000001000"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# 合约 Category / OrderType / Side / TimeInForce（与文档枚举顺序对齐）
CATEGORY = {"spot": 0, "margin": 1, "futures": 2}
ORDER_TYPE = {"limit": 0, "market": 1, "plan": 2, "tpsl": 3}
SIDE = {"buy": 0, "sell": 1}
TIME_IN_FORCE = {
    "default": 0,
    "gtc": 1,
    "ioc": 2,
    "fok": 3,
    "postonly": 4,
    "post_only": 4,
    "alo": 4,  # Hyperliquid 风格 post-only 别名
}
MARKET_UNIT = {"base": 0, "basetoken": 0, "quote": 1, "quotetoken": 1}
POSITION_SIDE = {"none": 0, "long": 1, "short": 2}
STP_MODE = {
    "none": 0,
    "canceltaker": 1,
    "cancelmaker": 2,
    "cancelboth": 3,
    "decrement": 4,
}

PLACE_ORDER_SIG = (
    "placeOrder(address,bytes32,uint16,bytes32,uint256,uint256,uint256,address,uint256)"
)
CANCEL_ORDER_SIG = "cancelOrder(address,uint128,bytes32)"


def _dec_to_1e18(value: Union[str, int, float, Decimal]) -> int:
    d = Decimal(str(value))
    scaled = (d * Decimal(10) ** 18).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return int(scaled)


def _to_bytes32(value: Optional[Union[str, bytes]]) -> bytes:
    """
    编码 clientOrderId 为 32 字节。

    PopDEX 预编译会把 clientOrderId 当 UTF-8 字符串校验；
    因此不能填随机二进制（如 uuid.bytes），应使用 ASCII/UTF-8 文本并右补 0x00。
    """
    if value is None:
        # uuid4().hex 恰好 32 个 ASCII 字符，可直接作为 bytes32
        raw = uuid.uuid4().hex.encode("ascii")
    elif isinstance(value, bytes):
        raw = value
    else:
        s = value.strip()
        if s.startswith("0x"):
            hex_body = s[2:]
            if len(hex_body) % 2:
                raise ValueError("client_order_id hex 长度必须为偶数")
            raw = bytes.fromhex(hex_body)
        else:
            raw = s.encode("utf-8")
    if len(raw) > 32:
        raise ValueError("client_order_id 超过 32 字节")
    # 允许尾部 0 填充；有效前缀必须是合法 UTF-8
    try:
        raw.rstrip(b"\x00").decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            "client_order_id 必须是合法 UTF-8（建议用 ascii 文本或 uuid4().hex）"
        ) from e
    return raw + b"\x00" * (32 - len(raw))


def pack_order_params(
    *,
    category: str = "Futures",
    order_type: str = "limit",
    side: str = "buy",
    time_in_force: str = "gtc",
    market_unit: str = "base",
    bbo: int = 0,
    reduce_only: bool = False,
    position_side: str = "none",
    stp_mode: str = "none",
) -> bytes:
    """
    打包 placeOrder 的 orderParams (bytes32)。

    字节布局（文档统一位图）:
      [0] category  [1] orderType  [2] side  [3] timeInForce
      [4] marketUnit  [5] bbo  [6] isReduceOnly  [7] positionSide
      [8] marginMode(placeOrder 置 0)  [9] stpMode  [10-31] 保留为 0
    """
    params = bytearray(32)
    params[0] = CATEGORY[category.lower()]
    params[1] = ORDER_TYPE[order_type.lower()]
    params[2] = SIDE[side.lower()]
    params[3] = TIME_IN_FORCE[time_in_force.lower().replace("-", "")]
    params[4] = MARKET_UNIT[market_unit.lower()]
    params[5] = int(bbo)
    params[6] = 1 if reduce_only else 0
    params[7] = POSITION_SIDE[position_side.lower()]
    params[8] = 0
    params[9] = STP_MODE[stp_mode.lower()]
    return bytes(params)


def encode_place_order_calldata(
    *,
    account: str,
    symbol_id: int,
    price: Union[str, Decimal, float, int],
    qty: Union[str, Decimal, float, int],
    side: str = "buy",
    order_type: str = "limit",
    time_in_force: str = "gtc",
    category: str = "Futures",
    reduce_only: bool = False,
    position_side: str = "none",
    slippage: Union[str, Decimal, float, int] = 0,
    client_order_id: Optional[str] = None,
    builder: str = ZERO_ADDRESS,
    builder_fee_rate: int = 0,
    market_unit: str = "base",
) -> Dict[str, Any]:
    """编码 placeOrder calldata，返回 data / orderParams / 数值字段。"""
    order_params = pack_order_params(
        category=category,
        order_type=order_type,
        side=side,
        time_in_force=time_in_force,
        market_unit=market_unit,
        reduce_only=reduce_only,
        position_side=position_side,
    )
    client_oid = _to_bytes32(client_order_id)
    price_x18 = _dec_to_1e18(price)
    qty_x18 = _dec_to_1e18(qty)
    slip_x18 = _dec_to_1e18(slippage)

    selector = function_signature_to_4byte_selector(PLACE_ORDER_SIG)
    encoded = abi_encode(
        [
            "address",
            "bytes32",
            "uint16",
            "bytes32",
            "uint256",
            "uint256",
            "uint256",
            "address",
            "uint256",
        ],
        [
            to_checksum_address(account),
            client_oid,
            int(symbol_id),
            order_params,
            price_x18,
            qty_x18,
            slip_x18,
            to_checksum_address(builder),
            int(builder_fee_rate),
        ],
    )
    data = "0x" + (selector + encoded).hex()
    return {
        "to": ORDER_PRECOMPILE,
        "data": data,
        "client_order_id": "0x" + client_oid.hex(),
        "order_params": "0x" + order_params.hex(),
        "price_x18": price_x18,
        "qty_x18": qty_x18,
        "symbol_id": int(symbol_id),
    }


def encode_cancel_order_calldata(
    *,
    account: str,
    order_id: Optional[Union[str, int]] = None,
    client_order_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    编码 cancelOrder calldata。

    文档: 用 orderId 撤单时 clientOrderId 填 0；用 clientOrderId 时 orderId 填 0。
    """
    if not order_id and not client_order_id:
        raise ValueError("必须提供 order_id 或 client_order_id")

    oid = 0
    if order_id not in (None, "", 0, "0"):
        oid_raw = str(order_id).strip()
        # 防止把 eth tx hash 当成 uint128 orderId
        if oid_raw.startswith("0x") and len(oid_raw) >= 42:
            raise ValueError(
                f"order_id 看起来是交易哈希而非交易所 orderId: {oid_raw[:18]}... "
                "请改用 client_order_id 撤单，或等待索引返回真实 orderId"
            )
        oid = int(oid_raw)
    if client_order_id and oid == 0:
        client_oid = _to_bytes32(client_order_id)
    elif oid > 0:
        # 按 orderId 撤：clientOrderId 必须为零
        client_oid = b"\x00" * 32
    else:
        client_oid = _to_bytes32(client_order_id)

    selector = function_signature_to_4byte_selector(CANCEL_ORDER_SIG)
    encoded = abi_encode(
        ["address", "uint128", "bytes32"],
        [to_checksum_address(account), oid, client_oid],
    )
    data = "0x" + (selector + encoded).hex()
    return {
        "to": ORDER_PRECOMPILE,
        "data": data,
        "order_id": oid,
        "client_order_id": "0x" + client_oid.hex(),
    }


def client_oid_text(client_order_id: str) -> str:
    """将 bytes32 hex / 0x 编码还原为 UTF-8 clientOid 文本。"""
    s = (client_order_id or "").strip()
    if not s:
        return ""
    if s.startswith("0x"):
        raw = bytes.fromhex(s[2:])
        return raw.rstrip(b"\x00").decode("utf-8")
    return s


def build_agent_tx(
    *,
    private_key: str,
    to: str,
    data: str,
    network: Network = "mainnet",
    nonce: Optional[int] = None,
    gas: int = 1_000_000,
    chain_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    使用 Agent Key 签署免 Gas 交易（timestamp nonce）。

    Agent 使用时间戳 nonce（毫秒）：需落在 (now-1h, now+1d)。
    """
    account: LocalAccount = Account.from_key(private_key)
    if chain_id is None:
        chain_id = int(EIP712_DOMAINS[network]["chainId"])
    if nonce is None:
        nonce = next_agent_nonce()

    tx = {
        "chainId": chain_id,
        "nonce": nonce,
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

    return {
        "from": account.address,
        "nonce": nonce,
        "raw_transaction": raw_hex,
        "hash": "0x" + signed.hash.hex()
        if isinstance(signed.hash, (bytes, bytearray))
        else signed.hash,
        "tx": tx,
    }
