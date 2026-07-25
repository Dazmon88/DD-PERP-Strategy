"""
Ondo Perps 订单辅助

REST 下单/撤单的请求体与 ID 规范化（非链上 ABI）。
文档: https://docs.ondoperps.xyz/api-reference/orders/create-order
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Sequence, Union


_CLIENT_OID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def normalize_market(market: str) -> str:
    """
    规范化市场名。

    已是 AAPL-USD.P 则保持；AAPL-USD / AAPLUSDT 等尽量转成 *.P 形式需调用方确认。
    此处只做 strip / 大写字母段保留官方大小写风格：保持输入主符号大写。
    """
    s = (market or "").strip()
    if not s:
        raise ValueError("market 不能为空")
    # 常见：aapl-usd.p -> AAPL-USD.P
    if "." in s:
        base, suf = s.rsplit(".", 1)
        return f"{base.upper()}.{suf.upper()}" if suf.lower() == "p" else s
    return s.upper()


def make_client_order_id(prefix: str = "dd") -> str:
    """生成合法 clientOrderId（字母数字/_/-，≤64）。"""
    raw = f"{prefix}-{uuid.uuid4().hex}"
    return raw[:64]


def validate_client_order_id(client_order_id: str) -> str:
    s = (client_order_id or "").strip()
    if not _CLIENT_OID_RE.match(s):
        raise ValueError(
            "clientOrderId 须为 1–64 位字母数字/下划线/横线"
        )
    return s


def build_place_order_body(
    *,
    market: str,
    side: str,
    size: Union[str, float, int],
    order_type: str = "limit",
    price: Optional[Union[str, float, int]] = None,
    quote_size: Optional[Union[str, float, int]] = None,
    client_order_id: Optional[str] = None,
    time_in_force: Optional[str] = None,
    post_only: Optional[bool] = None,
    reduce_only: Optional[bool] = None,
    take_profit: Optional[Dict[str, Any]] = None,
    stop_loss: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    构造 AddOrderReq。

    side: buy/sell
    type: limit/market
    timeInForce: GTC/IOC（市价单勿设）
    """
    side_l = side.lower().strip()
    if side_l in ("long",):
        side_l = "buy"
    elif side_l in ("short",):
        side_l = "sell"
    if side_l not in ("buy", "sell"):
        raise ValueError("side 必须是 buy 或 sell")

    typ = (order_type or "limit").lower().strip()
    if typ not in ("limit", "market"):
        raise ValueError("type 必须是 limit 或 market")

    body: Dict[str, Any] = {
        "market": normalize_market(market),
        "side": side_l,
        "type": typ,
        "size": str(size),
    }

    if typ == "limit":
        if price is None:
            raise ValueError("限价单必须提供 price")
        body["price"] = str(price)
        tif = (time_in_force or "GTC").upper()
        if tif not in ("GTC", "IOC"):
            # 兼容小写 / postonly 场景：postOnly 单独字段
            if tif in ("ALO", "POSTONLY", "POST_ONLY"):
                tif = "GTC"
                if post_only is None:
                    post_only = True
            else:
                raise ValueError("timeInForce 必须是 GTC 或 IOC")
        body["timeInForce"] = tif
    else:
        if quote_size is not None:
            body["quoteSize"] = str(quote_size)

    if client_order_id:
        body["clientOrderId"] = validate_client_order_id(client_order_id)
    if post_only is not None:
        body["postOnly"] = bool(post_only)
    if reduce_only is not None:
        body["reduceOnly"] = bool(reduce_only)
    if take_profit is not None:
        body["takeProfit"] = take_profit
    if stop_loss is not None:
        body["stopLoss"] = stop_loss
    if extra:
        body.update(extra)
    return body


def format_order_id_ref(order_id: Optional[str] = None, client_order_id: Optional[str] = None) -> str:
    """
    路径/批撤用的订单引用。

    - 内部 orderId 原样
    - clientOrderId → client:{id}
    """
    if order_id:
        oid = str(order_id).strip()
        if oid.startswith("client:"):
            return oid
        return oid
    if client_order_id:
        return f"client:{validate_client_order_id(client_order_id)}"
    raise ValueError("必须提供 order_id 或 client_order_id")


def format_batch_cancel_ids(
    order_ids: Optional[Sequence[Union[str, int]]] = None,
    client_order_ids: Optional[Sequence[str]] = None,
) -> str:
    """批量撤单 orderIDs query：逗号分隔。"""
    parts: List[str] = []
    for oid in order_ids or []:
        parts.append(format_order_id_ref(order_id=str(oid)))
    for cloid in client_order_ids or []:
        parts.append(format_order_id_ref(client_order_id=str(cloid)))
    if not parts:
        raise ValueError("批量撤单至少提供一个 ID")
    return ",".join(parts)
