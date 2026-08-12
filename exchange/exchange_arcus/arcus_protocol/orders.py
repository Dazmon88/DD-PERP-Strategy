"""
Arcus 订单辅助

- 构造 REST/WS 请求体（decimal 字符串）
- 构造 Scheme 1 typed canonical payload（整数 ticks/quantums）
- tickSize / stepSize 精确换算
"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, Union

OP_PLACE = 1
OP_CANCEL = 2
OP_MODIFY = 3
OP_PLACE_UNTRIGGERED = 4

SIDE = {"BUY": 0, "SELL": 1, "buy": 0, "sell": 1, "long": 0, "short": 1}
TIF = {
    "GTT": 0,
    "FOK": 1,
    "IOC": 2,
    "ALO": 3,
}

PAYLOAD_VERSION = 1


def make_client_id(prefix: str = "dd") -> str:
    """生成 clientId（建议短 ASCII）。"""
    return f"{prefix}-{uuid.uuid4().hex}"[:64]


def normalize_side(side: str) -> str:
    s = (side or "").strip().upper()
    if s in ("BUY", "LONG", "B"):
        return "BUY"
    if s in ("SELL", "SHORT", "S"):
        return "SELL"
    raise ValueError("side 必须是 BUY/SELL")


def normalize_tif(time_in_force: Optional[str], *, order_type: str = "LIMIT") -> str:
    """
    返回官方枚举：GTT / FOK / IOC / ALO。

    MARKET 必须 IOC。GTC/postOnly 映射到 GTT/ALO。
    """
    ot = (order_type or "LIMIT").upper()
    if ot == "MARKET":
        return "IOC"
    raw = (time_in_force or "GTT").strip().upper().replace("-", "_")
    aliases = {
        "GTC": "GTT",
        "POSTONLY": "ALO",
        "POST_ONLY": "ALO",
    }
    raw = aliases.get(raw, raw)
    if raw not in ("GTT", "FOK", "IOC", "ALO"):
        raise ValueError("timeInForce 必须是 GTT/FOK/IOC/ALO")
    return raw


def to_engine_int(value: Union[str, int, float, Decimal], unit: Union[str, Decimal]) -> int:
    """
    人类可读小数 → 引擎整数（ticks / quantums）。

    要求 value 恰好是 unit 的整数倍，否则报错。
    """
    n = Decimal(str(value)) / Decimal(str(unit))
    if n != n.to_integral_value():
        raise ValueError(f"{value} 不是 {unit} 的整数倍")
    return int(n)


def default_good_til_time_us(*, months: int = 2) -> int:
    """
    goodTilTime：Unix 微秒，须至少约 1 个月以后。

    默认取当前 + 约 2 个月，留足余量。
    """
    now_us = int(time.time() * 1_000_000)
    return now_us + int(months * 30 * 86_400 * 1_000_000)


def _omit_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None and v != ""}


def build_place_typed_payload(
    *,
    address: str,
    account_index: int,
    market_id: int,
    side: str,
    price: Union[str, int, float, Decimal],
    quantity: Union[str, int, float, Decimal],
    tick_size: Union[str, Decimal],
    step_size: Union[str, Decimal],
    time_in_force: str = "GTT",
    reduce_only: bool = False,
    good_til_time_us: Optional[int] = None,
    client_id: Optional[str] = None,
    timestamp_ns: Optional[int] = None,
    op: int = OP_PLACE,
) -> str:
    """
    Scheme 1 placeOrder / placeUntriggered 签名串。

    键按字母序，无空格；空 clientId 整键省略。
    """
    addr = address.lower()
    if not addr.startswith("0x"):
        addr = "0x" + addr
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    gtt_us = int(good_til_time_us if good_til_time_us is not None else default_good_til_time_us())
    g_ns = gtt_us * 1000
    side_u = normalize_side(side)
    tif_u = normalize_tif(time_in_force)
    payload: Dict[str, Any] = {
        "ad": addr,
        "ai": int(account_index),
        "ct": ts,
        "g": g_ns,
        "m": int(market_id),
        "op": int(op),
        "p": to_engine_int(price, tick_size),
        "q": to_engine_int(quantity, step_size),
        "r": 1 if reduce_only else 0,
        "s": SIDE[side_u],
        "t": TIF[tif_u],
        "v": PAYLOAD_VERSION,
    }
    if client_id:
        payload["c"] = str(client_id).lower()
    # 固定字母序
    keys = sorted(payload.keys())
    inner = ",".join(f'"{k}":{_json_scalar(payload[k])}' for k in keys)
    return "{" + inner + "}"


def build_cancel_typed_payload(
    *,
    address: str,
    account_index: int,
    market_id: int,
    order_id: Optional[str] = None,
    client_id: Optional[str] = None,
    timestamp_ns: Optional[int] = None,
) -> str:
    """Scheme 1 cancelOrder：提供 orderId 或 clientId 之一。"""
    if not order_id and not client_id:
        raise ValueError("cancel 必须提供 order_id 或 client_id")
    addr = address.lower()
    if not addr.startswith("0x"):
        addr = "0x" + addr
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    payload: Dict[str, Any] = {
        "ad": addr,
        "ai": int(account_index),
        "ct": ts,
        "m": int(market_id),
        "op": OP_CANCEL,
        "v": PAYLOAD_VERSION,
    }
    if order_id:
        payload["id"] = str(order_id)
    if client_id and not order_id:
        payload["c"] = str(client_id).lower()
    elif client_id and order_id:
        # 官方：按 orderId 撤时可不带 c；若带 c 须与挂单一致
        payload["c"] = str(client_id).lower()
    keys = sorted(payload.keys())
    inner = ",".join(f'"{k}":{_json_scalar(payload[k])}' for k in keys)
    return "{" + inner + "}"


def build_modify_typed_payload(
    *,
    address: str,
    account_index: int,
    market_id: int,
    order_id: str,
    side: str,
    price: Union[str, int, float, Decimal],
    quantity: Union[str, int, float, Decimal],
    tick_size: Union[str, Decimal],
    step_size: Union[str, Decimal],
    time_in_force: str,
    reduce_only: bool,
    good_til_time_us: int,
    client_id: Optional[str] = None,
    timestamp_ns: Optional[int] = None,
) -> str:
    """Scheme 1 modifyOrder：id 必填；g/r/s/t 回显原单不可变属性。"""
    addr = address.lower()
    if not addr.startswith("0x"):
        addr = "0x" + addr
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    side_u = normalize_side(side)
    tif_u = normalize_tif(time_in_force)
    payload: Dict[str, Any] = {
        "ad": addr,
        "ai": int(account_index),
        "ct": ts,
        "g": int(good_til_time_us) * 1000,
        "id": str(order_id),
        "m": int(market_id),
        "op": OP_MODIFY,
        "p": to_engine_int(price, tick_size),
        "q": to_engine_int(quantity, step_size),
        "r": 1 if reduce_only else 0,
        "s": SIDE[side_u],
        "t": TIF[tif_u],
        "v": PAYLOAD_VERSION,
    }
    if client_id:
        payload["c"] = str(client_id).lower()
    keys = sorted(payload.keys())
    inner = ",".join(f'"{k}":{_json_scalar(payload[k])}' for k in keys)
    return "{" + inner + "}"


def build_place_order_body(
    *,
    address: str,
    account_index: int,
    market_id: int,
    side: str,
    quantity: Union[str, int, float, Decimal],
    price: Optional[Union[str, int, float, Decimal]] = None,
    order_type: str = "LIMIT",
    time_in_force: Optional[str] = None,
    reduce_only: bool = False,
    good_til_time_us: Optional[int] = None,
    client_id: Optional[str] = None,
    timestamp_ns: Optional[int] = None,
    signature: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """REST/WS placeOrder JSON body（price/quantity 为小数字符串）。"""
    ot = (order_type or "LIMIT").upper()
    if ot not in ("LIMIT", "MARKET"):
        raise ValueError("orderType 必须是 LIMIT 或 MARKET")
    if price is None:
        raise ValueError("必须提供 price（MARKET 用作滑点保护价）")
    tif = normalize_tif(time_in_force, order_type=ot)
    gtt = int(good_til_time_us if good_til_time_us is not None else default_good_til_time_us())
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    body: Dict[str, Any] = {
        "address": address if address.startswith("0x") else "0x" + address,
        "accountIndex": int(account_index),
        "marketId": int(market_id),
        "orderSide": normalize_side(side),
        "orderType": ot,
        "quantity": _dec_str(quantity),
        "price": _dec_str(price),
        "timeInForce": tif,
        "goodTilTime": str(gtt),
        "timestamp": ts,
        "reduceOnly": bool(reduce_only),
    }
    if client_id:
        body["clientId"] = str(client_id)
    if signature:
        body["signature"] = signature
    if extra:
        body.update(extra)
    return body


def build_cancel_order_body(
    *,
    address: str,
    account_index: int,
    market_id: int,
    order_id: Optional[str] = None,
    client_id: Optional[str] = None,
    timestamp_ns: Optional[int] = None,
    signature: Optional[str] = None,
) -> Dict[str, Any]:
    if not order_id and not client_id:
        raise ValueError("必须提供 order_id 或 client_id")
    ts = int(timestamp_ns if timestamp_ns is not None else time.time_ns())
    body: Dict[str, Any] = {
        "address": address if address.startswith("0x") else "0x" + address,
        "accountIndex": int(account_index),
        "marketId": int(market_id),
        "timestamp": ts,
    }
    if order_id:
        body["kind"] = "orderId"
        body["orderId"] = str(order_id)
    else:
        body["kind"] = "clientId"
        body["clientId"] = str(client_id)
    if signature:
        body["signature"] = signature
    return body


def snap_price(price: Union[str, float, Decimal], tick_size: Union[str, Decimal]) -> str:
    """向下取整到 tick。"""
    tick = Decimal(str(tick_size))
    p = Decimal(str(price))
    n = (p / tick).to_integral_value(rounding=ROUND_DOWN)
    return _dec_str(n * tick)


def snap_qty(qty: Union[str, float, Decimal], step_size: Union[str, Decimal]) -> str:
    step = Decimal(str(step_size))
    q = Decimal(str(qty))
    n = (q / step).to_integral_value(rounding=ROUND_DOWN)
    return _dec_str(n * step)


def _dec_str(value: Union[str, int, float, Decimal]) -> str:
    d = Decimal(str(value))
    # 去掉多余尾零，但保留至少一位整数
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _json_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json_escape(v)
    if isinstance(v, int):
        return str(v)
    if v is None:
        return "null"
    return json_escape(str(v))


def json_escape(s: str) -> str:
    import json as _json

    return _json.dumps(s, ensure_ascii=False)
